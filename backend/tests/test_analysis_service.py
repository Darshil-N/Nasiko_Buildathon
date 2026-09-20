"""Tests for the analysis logic against an in-memory store (no database)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import h3

from backend.app.services.analysis_service import (
    AnalysisRecord,
    CellMeta,
    StoredZone,
    apply_answers,
    data_notes,
    make_narrative,
    matches_preferred,
    new_analysis_id,
    rank_changes,
    run_analysis,
    score_analysis,
    zone_names,
)
from pipelines.features_store import FeatureBundle
from pipelines.grid import describe_cell, point_to_cell
from shared.config import CategoryConfig
from shared.contracts import ZoneScore

CENTRE = point_to_cell(12.9716, 77.5946, 9)
CELLS = [describe_cell(c) for c in sorted(h3.grid_disk(CENTRE, 3))]


# --- answers ---------------------------------------------------------------------------------
def test_no_answers_leave_features_untouched(
    bundles: list[FeatureBundle], cafe: CategoryConfig
) -> None:
    result = apply_answers(bundles, cafe, {})
    assert result == [b.features for b in bundles]


def test_students_raise_college_weight_and_change_f1_and_f6(
    bundles: list[FeatureBundle], cafe: CategoryConfig
) -> None:
    result = apply_answers(bundles, cafe, {"target_customer": ["students"]})
    before = [b.features.raw.F1_anchor_footfall_raw for b in bundles]
    after = [f.raw.F1_anchor_footfall_raw for f in result]
    assert any(a > b for a, b in zip(after, before, strict=True))
    assert all(
        a >= b - 1e-9 for a, b in zip(after, before, strict=True)
    )  # only college weight rose
    assert any(
        f.normalised.F6_gap_opportunity_norm != b.features.normalised.F6_gap_opportunity_norm
        for f, b in zip(result, bundles, strict=True)
    )
    for f in result:
        assert 0.0 <= f.normalised.F1_anchor_footfall_norm <= 1.0
        assert 0.0 <= f.normalised.F6_gap_opportunity_norm <= 1.0


def test_unrelated_answers_change_nothing(
    bundles: list[FeatureBundle], cafe: CategoryConfig
) -> None:
    assert apply_answers(bundles, cafe, {"format": "takeaway"}) == [b.features for b in bundles]


# --- scoring ---------------------------------------------------------------------------------
def test_score_analysis_ranks_every_cell(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta], cafe: CategoryConfig
) -> None:
    outcome = score_analysis(bundles, meta, cafe, "mid", {}, {})
    assert len(outcome.zones) == len(CELLS)
    assert [z.rank for z in outcome.ranked] == list(range(1, len(outcome.ranked) + 1))
    scores = [z.score for z in outcome.ranked]
    assert scores == sorted(scores, reverse=True)


def test_rent_budget_is_not_applied_without_rent_data(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta], cafe: CategoryConfig
) -> None:
    constrained = score_analysis(
        bundles, meta, cafe, "mid", {}, {"monthly_rent_budget_inr": 1, "shop_size_sqft": 10_000}
    )
    assert not any(z.excluded for z in constrained.zones)  # no rent data -> filter cannot apply


def test_preferred_areas_filter_and_fallback_note(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta], cafe: CategoryConfig
) -> None:
    only = score_analysis(bundles, meta, cafe, "mid", {}, {"preferred_areas": ["koramangala"]})
    expected = {h for h, m in meta.items() if m.locality_name == "Koramangala"}
    assert {z.h3_index for z in only.zones} == expected
    fallback = score_analysis(bundles, meta, cafe, "mid", {}, {"preferred_areas": ["nowhere"]})
    assert len(fallback.zones) == len(CELLS)
    assert any("preferred areas" in n for n in fallback.notes)


def test_matches_preferred_is_case_insensitive_and_ignores_blanks() -> None:
    assert matches_preferred("HSR Layout", ["hsr"])
    assert not matches_preferred("HSR Layout", ["", "  "])
    assert not matches_preferred(None, ["hsr"])


def test_zone_names_are_numbered_when_repeated(meta: dict[str, CellMeta]) -> None:
    zones = [
        ZoneScore(
            h3_index=c.h3_index,
            rank=i + 1,
            score=50,
            confidence=1,
            contributions={"a": 50},
            top_drivers=[],
            top_risks=[],
        )
        for i, c in enumerate(CELLS[:4])
    ]
    names = zone_names(zones, meta)
    assert names[CELLS[0].h3_index] == "Indiranagar"
    assert names[CELLS[2].h3_index] == "Indiranagar (2)"
    assert names[CELLS[3].h3_index] == "Unnamed area"


def test_narrative_uses_only_numbers_from_the_zone() -> None:
    zone = ZoneScore(
        h3_index="x",
        rank=3,
        score=71.6,
        confidence=0.9,
        contributions={"a": 71.6},
        top_drivers=["Strong footfall", "Good access"],
        top_risks=["High competition"],
    )
    text = make_narrative(zone, "Indiranagar", "Bengaluru", "cafe", "Niche")
    assert "#3" in text
    assert "72 out of 100" in text
    assert "90%" in text
    assert "Strong footfall; Good access" in text
    assert "High competition" in text


def test_data_notes_are_honest_about_missing_rent_data() -> None:
    notes = data_notes("Bengaluru", ["extra"])
    assert any("Rent and property-price data is not available for Bengaluru" in n for n in notes)
    assert notes[-1] == "extra"


def test_rank_changes_report_movement(meta: dict[str, CellMeta]) -> None:
    def zone(i: int, rank: int) -> ZoneScore:
        return ZoneScore(
            h3_index=CELLS[i].h3_index,
            rank=rank,
            score=50,
            confidence=1,
            contributions={"a": 50},
            top_drivers=[],
            top_risks=[],
        )

    changes = rank_changes([zone(0, 1), zone(1, 2)], [zone(1, 1), zone(0, 2), zone(2, 3)], meta)
    assert [(c["from_rank"], c["to_rank"]) for c in changes] == [(2, 1), (1, 2), (None, 3)]


def test_new_analysis_ids_look_right_and_differ() -> None:
    a, b = new_analysis_id(), new_analysis_id()
    assert a.startswith("an_")
    assert len(a) == 11
    assert a != b


# --- orchestration ---------------------------------------------------------------------------
class MemoryStore:
    def __init__(
        self, bundles: list[FeatureBundle], meta: dict[str, CellMeta], record: AnalysisRecord
    ) -> None:
        self._bundles, self._meta, self.record = bundles, meta, record
        self.statuses: list[str] = []
        self.saved: list[StoredZone] = []
        self.narrative: str | None = None
        self.fail_with: Exception | None = None

    def cell_meta(self, city_id: int) -> dict[str, CellMeta]:
        return self._meta

    def tier_bundles(self, category: str, tier: str) -> list[FeatureBundle]:
        if self.fail_with:
            raise self.fail_with
        return self._bundles

    def load_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        return self.record if analysis_id == self.record.id else None

    def set_status(
        self,
        analysis_id: str,
        status: str,
        *,
        narrative: str | None = None,
        config_version: str | None = None,
    ) -> None:
        self.statuses.append(status)
        self.narrative = narrative if narrative is not None else self.narrative

    def save_recommendations(self, analysis_id: str, zones: Sequence[StoredZone]) -> None:
        self.saved = list(zones)

    def load_recommendations(self, analysis_id: str) -> list[StoredZone]:
        return self.saved


def record(**overrides: Any) -> AnalysisRecord:
    values: dict[str, Any] = {
        "id": "an_test0001",
        "city_id": 1,
        "city_key": "bengaluru",
        "category": "cafe",
        "tier": "mid",
        "answers": {},
        "constraints": {"top_n": 5},
        "config_version": None,
        "status": "queued",
        "summary_narrative": None,
    }
    values.update(overrides)
    return AnalysisRecord(**values)


def test_run_analysis_happy_path(bundles: list[FeatureBundle], meta: dict[str, CellMeta]) -> None:
    store = MemoryStore(bundles, meta, record())
    run_analysis(store, "an_test0001", city_name="Bengaluru")
    assert store.statuses == ["running", "done"]
    assert [z.rank for z in store.saved] == [1, 2, 3, 4, 5]
    assert all(z.narrative and "Bengaluru" in z.narrative for z in store.saved)
    assert store.narrative
    assert store.narrative.startswith("Top zone:")


def test_run_analysis_failure_is_recorded_and_never_raised(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta]
) -> None:
    store = MemoryStore(bundles, meta, record())
    store.fail_with = RuntimeError("password is hunter2")
    run_analysis(store, "an_test0001", city_name="Bengaluru")  # must not raise
    assert store.statuses == ["running", "failed"]
    assert "hunter2" not in (store.narrative or "")


def test_run_analysis_with_no_candidates_says_so(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta]
) -> None:
    residential = {
        h: CellMeta(h, m.locality_name, "residential", m.lat, m.lon) for h, m in meta.items()
    }
    store = MemoryStore(bundles, residential, record(category="clothing"))
    run_analysis(store, "an_test0001", city_name="Bengaluru")
    assert store.statuses == ["running", "failed"]
    assert "NO_CANDIDATES" in (store.narrative or "")


def test_run_analysis_ignores_an_unknown_id(
    bundles: list[FeatureBundle], meta: dict[str, CellMeta]
) -> None:
    store = MemoryStore(bundles, meta, record())
    run_analysis(store, "an_missing", city_name="Bengaluru")
    assert store.statuses == []
