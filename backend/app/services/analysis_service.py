"""Analysis logic (plan steps 4.5.2, 4.6.1, 4.6.2): score a category for a tier, explain, compare.

Pure functions plus one orchestrating function that talks to a small storage interface
(``AnalysisStore``), so everything here is unit-testable without a database.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import numpy as np

from pipelines.build_features import rank_pct
from pipelines.features_store import FeatureBundle
from scoring.features import apply_answer_modifiers, gap_opportunity
from scoring.score import ScoreEngine
from shared.config import CategoryConfig, load_category_config
from shared.contracts import CellFeatures, ZoneScore

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 10
UNNAMED_AREA = "Unnamed area"
FAILURE_MESSAGE = "The analysis could not be completed. Please try again."


@dataclass(frozen=True)
class CellMeta:
    """Where a cell is and what it is called."""

    h3_index: str
    locality_name: str | None
    land_use: str | None
    lat: float
    lon: float


@dataclass(frozen=True)
class StoredZone:
    """A ranked zone as persisted in ``recommendations``."""

    rank: int
    h3_index: str
    zone_name: str
    score: float
    confidence: float
    contributions: dict[str, float]
    top_drivers: list[str]
    top_risks: list[str]
    narrative: str | None = None


@dataclass(frozen=True)
class AnalysisRecord:
    """An analysis as persisted in ``analyses``."""

    id: str
    city_id: int
    city_key: str
    category: str
    tier: str
    answers: dict[str, Any]
    constraints: dict[str, Any]
    config_version: str | None
    status: str
    summary_narrative: str | None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class AnalysisStore(Protocol):
    """Everything the analysis logic needs from storage (SQL in production, memory in tests)."""

    def cell_meta(self, city_id: int) -> dict[str, CellMeta]: ...

    def tier_bundles(self, category: str, tier: str) -> list[FeatureBundle]: ...

    def load_analysis(self, analysis_id: str) -> AnalysisRecord | None: ...

    def set_status(
        self,
        analysis_id: str,
        status: str,
        *,
        narrative: str | None = None,
        config_version: str | None = None,
    ) -> None: ...  # fmt: skip

    def save_recommendations(self, analysis_id: str, zones: Sequence[StoredZone]) -> None: ...

    def load_recommendations(self, analysis_id: str) -> list[StoredZone]: ...


@dataclass(frozen=True)
class ScoringOutcome:
    """Every cell scored: ranked zones first (rank 1..n), then greyed, then excluded."""

    zones: list[ZoneScore]
    notes: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[ZoneScore]:
        return [z for z in self.zones if not z.excluded and not z.greyed]


def new_analysis_id() -> str:
    """An id like ``an_7f3a9c21``."""
    return "an_" + uuid.uuid4().hex[:8]


# --- answers: re-weight F1 and recompute what depends on it ---------------------------------
def apply_answers(
    bundles: Sequence[FeatureBundle], config: CategoryConfig, answers: Mapping[str, Any]
) -> list[CellFeatures]:
    """Apply questionnaire answers (for example "students" raises the college weight).

    Answers change the landmark weights, so F1 is recomputed from the stored per-category sums,
    re-ranked across the city, and F6 (which uses F1) is recomputed with it. With no effective
    change the stored features are returned untouched.
    """
    features = [b.features for b in bundles]
    base = config.poi_weights
    adjusted = apply_answer_modifiers(dict(base), config.answer_modifiers, dict(answers))
    if adjusted == base or not features:
        return features

    f1_raw = np.array(
        [sum(adjusted.get(cat, 0.0) * v for cat, v in b.anchor_components.items()) for b in bundles]
    )
    f1_norm = rank_pct(f1_raw)
    gap = np.array(
        [
            gap_opportunity(
                float(f1_raw[i]),
                f.normalised.F2_affluence_fit_norm,
                f.raw.F5_competition_pressure_raw,
            )
            for i, f in enumerate(features)
        ]
    )
    f6_norm = rank_pct(gap)
    return [
        f.model_copy(
            update={
                "raw": f.raw.model_copy(update={"F1_anchor_footfall_raw": float(f1_raw[i])}),
                "normalised": f.normalised.model_copy(
                    update={
                        "F1_anchor_footfall_norm": float(f1_norm[i]),
                        "F6_gap_opportunity_norm": float(f6_norm[i]),
                    }
                ),
            }
        )
        for i, f in enumerate(features)
    ]


# --- scoring ---------------------------------------------------------------------------------
def matches_preferred(locality: str | None, preferred: Sequence[str]) -> bool:
    """True if the locality name contains any preferred area (case-insensitive)."""
    name = (locality or "").lower()
    return any(p.strip().lower() in name for p in preferred if p.strip())


def score_analysis(
    bundles: Sequence[FeatureBundle],
    meta: Mapping[str, CellMeta],
    config: CategoryConfig,
    tier: str,
    answers: Mapping[str, Any],
    constraints: Mapping[str, Any],
) -> ScoringOutcome:
    """Score every cell with the scoring engine, honouring answers and hard constraints."""
    features = apply_answers(bundles, config, answers)
    notes: list[str] = []
    preferred = [str(p) for p in constraints.get("preferred_areas", []) or []]
    if preferred:
        matching = {h for h, m in meta.items() if matches_preferred(m.locality_name, preferred)}
        if matching:
            features = [f for f in features if f.h3_index in matching]
        else:
            notes.append("No area matched your preferred areas, so city-wide results are shown.")
    engine_constraints = {
        k: float(constraints[k])
        for k in ("monthly_rent_budget_inr", "shop_size_sqft")
        if constraints.get(k) is not None
    }
    land_uses: dict[str, str | None] = {h: m.land_use for h, m in meta.items()}
    zones = ScoreEngine(config, tier).rank(
        features, engine_constraints, top_n=max(len(features), 1), land_uses=land_uses
    )
    return ScoringOutcome(zones=zones, notes=notes)


def zone_names(zones: Sequence[ZoneScore], meta: Mapping[str, CellMeta]) -> dict[str, str]:
    """Readable names: the locality, numbered when repeated (Koramangala, Koramangala (2))."""
    seen: Counter[str] = Counter()
    names: dict[str, str] = {}
    for zone in zones:
        base = (
            meta[zone.h3_index].locality_name if zone.h3_index in meta else None
        ) or UNNAMED_AREA
        seen[base] += 1
        names[zone.h3_index] = base if seen[base] == 1 else f"{base} ({seen[base]})"
    return names


def data_notes(city_name: str, outcome_notes: Sequence[str] = ()) -> list[str]:
    """Honest caveats shown with every result (plan standard 9)."""
    return [
        "Scores rank areas for further on-site checks; they are based on public data proxies "
        "and do not predict revenue.",
        f"Rent and property-price data is not available for {city_name}: your rent budget is "
        "not applied and rent efficiency is left out of the score.",
        "Footfall is estimated from nearby landmarks (OpenStreetMap), not measured.",
        "Area growth data is not available yet, so growth is treated as neutral.",
        "Map data from OpenStreetMap contributors (ODbL).",
        *outcome_notes,
    ]


def make_narrative(
    zone: ZoneScore, name: str, city_name: str, category: str, tier_label: str
) -> str:
    """A deterministic, number-safe summary; every figure comes straight from the zone."""
    strengths = "; ".join(zone.top_drivers[:2]) or "no standout strength"
    risk = zone.top_risks[-1] if zone.top_risks else "no major risk flagged"
    return (
        f"{name} ranks #{zone.rank} in {city_name} for a {tier_label.lower()} {category}, "
        f"with a score of {zone.score:.0f} out of 100 and data confidence of "
        f"{zone.confidence:.0%}. Strengths: {strengths}. Watch out for: {risk}. "
        "Visit at peak hours and check parking and footfall before committing."
    )


def to_stored_zones(
    outcome: ScoringOutcome,
    meta: Mapping[str, CellMeta],
    *,
    top_n: int,
    city_name: str,
    category: str,
    tier_label: str,
) -> list[StoredZone]:
    """The top ``top_n`` ranked zones, named and with narratives."""
    ranked = outcome.ranked[:top_n]
    names = zone_names(ranked, meta)
    return [
        StoredZone(
            rank=z.rank,
            h3_index=z.h3_index,
            zone_name=names[z.h3_index],
            score=z.score,
            confidence=z.confidence,
            contributions=dict(z.contributions),
            top_drivers=list(z.top_drivers),
            top_risks=list(z.top_risks),
            narrative=make_narrative(z, names[z.h3_index], city_name, category, tier_label),
        )
        for z in ranked
    ]


def rank_changes(
    before: Sequence[ZoneScore],
    after: Sequence[ZoneScore],
    meta: Mapping[str, CellMeta],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """How the top zones of a what-if scenario moved compared with the original ranking."""
    old = {z.h3_index: z.rank for z in before if not z.excluded and not z.greyed}
    names = zone_names([z for z in after if not z.excluded and not z.greyed][:limit], meta)
    return [
        {
            "h3_index": z.h3_index,
            "zone_name": names[z.h3_index],
            "from_rank": old.get(z.h3_index),
            "to_rank": z.rank,
        }
        for z in [z for z in after if not z.excluded and not z.greyed][:limit]
    ]


def run_analysis(
    store: AnalysisStore,
    analysis_id: str,
    *,
    city_name: str,
    config_loader: Callable[[str], CategoryConfig] = load_category_config,
) -> None:
    """Run one queued analysis end to end and record the outcome. Never raises."""
    record = store.load_analysis(analysis_id)
    if record is None:
        logger.error("analysis %s vanished before it could run", analysis_id)
        return
    store.set_status(analysis_id, "running")
    try:
        config = config_loader(record.category)
        bundles = store.tier_bundles(record.category, record.tier)
        if not bundles:
            raise LookupError(f"no stored features for {record.category}/{record.tier}")
        meta = store.cell_meta(record.city_id)
        outcome = score_analysis(
            bundles, meta, config, record.tier, record.answers, record.constraints
        )
        top_n = int(record.constraints.get("top_n", DEFAULT_TOP_N))
        zones = to_stored_zones(
            outcome,
            meta,
            top_n=top_n,
            city_name=city_name,
            category=record.category,
            tier_label=config.tier_labels.get(record.tier, record.tier),
        )
        if not zones:
            store.set_status(
                analysis_id,
                "failed",
                narrative="NO_CANDIDATES: no zone passes your constraints. Loosen them and retry.",
                config_version=config.version,
            )
            return
        store.save_recommendations(analysis_id, zones)
        summary = f"Top zone: {zones[0].zone_name} (score {zones[0].score:.0f})."
        store.set_status(analysis_id, "done", narrative=summary, config_version=config.version)
    except Exception:
        logger.exception("analysis %s failed", analysis_id)
        store.set_status(analysis_id, "failed", narrative=FAILURE_MESSAGE)


def compute_outcome(
    store: AnalysisStore,
    record: AnalysisRecord,
    *,
    category: str | None = None,
    tier: str | None = None,
    constraints: Mapping[str, Any] | None = None,
    config_loader: Callable[[str], CategoryConfig] = load_category_config,
) -> tuple[ScoringOutcome, CategoryConfig, dict[str, CellMeta]]:
    """Score an analysis again, optionally with a different category, tier or constraints.

    Used by the map, compare and what-if endpoints. Scoring all 6,631 cells takes well under a
    second, so nothing extra needs to be stored.
    """
    use_category = category or record.category
    use_tier = tier or record.tier
    config = config_loader(use_category)
    if use_tier not in config.tier_targets:
        raise ValueError(f"tier {use_tier!r} is not offered for {use_category}")
    merged = dict(record.constraints)
    if constraints:
        merged.update({k: v for k, v in constraints.items() if v is not None})
    bundles = store.tier_bundles(use_category, use_tier)
    meta = store.cell_meta(record.city_id)
    answers = record.answers if use_category == record.category else {}
    return score_analysis(bundles, meta, config, use_tier, answers, merged), config, meta
