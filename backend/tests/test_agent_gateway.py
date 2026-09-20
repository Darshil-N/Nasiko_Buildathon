"""Tests for calling agents through Nasiko: envelope handling, id caching, scorer and fallback."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import pytest

from backend.app.services.agent_gateway import (
    SCORING_AGENT,
    AgentCallError,
    AgentGateway,
    NasikoScorer,
    scoring_request,
)
from backend.app.services.analysis_service import (
    AnalysisRecord,
    ScoreResult,
    ScorerUnavailableError,
    StoredZone,
    run_analysis,
)
from backend.app.services.nasiko_client import A2AReply, AgentInfo, NasikoError
from backend.tests.test_analysis_service import MemoryStore, record

ZONE = StoredZone(
    rank=1,
    h3_index="8960145b49bffff",
    zone_name="Indiranagar",
    score=81.5,
    confidence=0.9,
    contributions={"F1_anchor_footfall": 20.0},
    top_drivers=["Strong footfall"],
    top_risks=["High competition"],
    narrative="Indiranagar ranks #1.",
)


def reply_for(envelope: dict[str, Any]) -> A2AReply:
    return A2AReply(state="TASK_STATE_COMPLETED", text=json.dumps(envelope))


def ok_envelope(**payload: Any) -> dict[str, Any]:
    body = {"zones": [asdict(ZONE)], "config_version": "2026-09-a", "notes": ["a note"]}
    body.update(payload)
    return {
        "agent": SCORING_AGENT,
        "version": "0.1.0",
        "latency_ms": 12,
        "warnings": [],
        "payload": body,
    }


class FakeNasiko:
    def __init__(self, reply: A2AReply | Exception, status: str = "running") -> None:
        self.reply = reply
        self.status = status
        self.lookups = 0
        self.sent: list[dict[str, Any]] = []

    def find_agent(self, name: str) -> AgentInfo | None:
        self.lookups += 1
        if name != SCORING_AGENT:
            return None
        return AgentInfo(id="agent-1", name=name, status=self.status, version=None, url=None)

    def send_message(
        self, agent_id: str, text: str | None = None, data: dict[str, Any] | None = None
    ) -> A2AReply:
        assert agent_id == "agent-1"
        self.sent.append(json.loads(text or "{}"))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def analysis_record() -> AnalysisRecord:
    return record(constraints={"top_n": 3, "monthly_rent_budget_inr": 50000})


def test_scoring_request_carries_top_n_separately() -> None:
    request = scoring_request(analysis_record())
    assert request["top_n"] == 3
    assert request["constraints"] == {"monthly_rent_budget_inr": 50000}
    assert request["city"] == "bengaluru"


def test_gateway_returns_the_payload_and_caches_the_agent_id() -> None:
    nasiko = FakeNasiko(reply_for(ok_envelope()))
    gateway = AgentGateway(nasiko)
    first = gateway.call(SCORING_AGENT, {"x": 1})
    gateway.call(SCORING_AGENT, {"x": 2})
    assert first.latency_ms == 12
    assert first.payload["config_version"] == "2026-09-a"
    assert nasiko.lookups == 1
    assert nasiko.sent == [{"x": 1}, {"x": 2}]


@pytest.mark.parametrize(
    "nasiko",
    [
        FakeNasiko(reply_for(ok_envelope()), status="building"),
        FakeNasiko(A2AReply(state="x", text="not json")),
        FakeNasiko(A2AReply(state="x", text="[1, 2]")),
        FakeNasiko(reply_for({"agent": "a", "error": {"code": "INTERNAL", "message": "boom"}})),
        FakeNasiko(reply_for({"agent": "a", "version": "1"})),
        FakeNasiko(NasikoError("timed out")),
    ],
)
def test_gateway_turns_every_failure_into_agent_call_error(nasiko: FakeNasiko) -> None:
    with pytest.raises(AgentCallError):
        AgentGateway(nasiko).call(SCORING_AGENT, {})


def test_gateway_reports_an_agent_that_is_not_deployed() -> None:
    with pytest.raises(AgentCallError, match="not deployed"):
        AgentGateway(FakeNasiko(reply_for(ok_envelope()))).call("sitescout-other", {})


def test_gateway_forgets_the_cached_id_after_a_failure() -> None:
    nasiko = FakeNasiko(NasikoError("gone"))
    gateway = AgentGateway(nasiko)
    for _ in range(2):
        with pytest.raises(AgentCallError):
            gateway.call(SCORING_AGENT, {})
    assert nasiko.lookups == 2


def test_nasiko_scorer_rebuilds_zones_from_the_payload() -> None:
    scorer = NasikoScorer(AgentGateway(FakeNasiko(reply_for(ok_envelope()))))
    result = scorer(analysis_record(), "Bengaluru")
    assert result.zones == [ZONE]
    assert result.config_version == "2026-09-a"
    assert result.notes == ["a note"]


def test_nasiko_scorer_signals_unavailable_on_a_bad_payload() -> None:
    bad = ok_envelope(zones=[{"rank": 1}])
    scorer = NasikoScorer(AgentGateway(FakeNasiko(reply_for(bad))))
    with pytest.raises(ScorerUnavailableError):
        scorer(analysis_record(), "Bengaluru")


def test_run_analysis_uses_the_scorer_result(bundles: Any, meta: Any) -> None:
    store = MemoryStore(bundles, meta, record())
    scorer = NasikoScorer(AgentGateway(FakeNasiko(reply_for(ok_envelope()))))
    run_analysis(store, "an_test0001", city_name="Bengaluru", scorer=scorer)
    assert store.statuses == ["running", "done"]
    assert [z.zone_name for z in store.saved] == ["Indiranagar"]


def test_run_analysis_falls_back_to_local_scoring_when_the_agent_is_down(
    bundles: Any, meta: Any
) -> None:
    store = MemoryStore(bundles, meta, record())

    def down(rec: AnalysisRecord, name: str) -> ScoreResult:
        raise ScorerUnavailableError("agent offline")

    run_analysis(store, "an_test0001", city_name="Bengaluru", scorer=down)
    assert store.statuses == ["running", "done"]
    assert [z.rank for z in store.saved] == [1, 2, 3, 4, 5]
