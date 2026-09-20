"""Calling SiteScout agents through Nasiko (plan steps 5.x and D-04: the backend orchestrates).

An agent replies with one JSON envelope (see ``agents/_shared/runner.py``):

    {"agent": ..., "version": ..., "latency_ms": ..., "warnings": [...], "payload": {...}}

or the same envelope with an ``error`` object. ``AgentGateway`` sends a request, checks the
envelope and returns the payload; every failure becomes an ``AgentCallError`` so callers can fall
back. ``NasikoScorer`` uses it to run the scoring step on the ``sitescout-scoring`` agent.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.app.services.analysis_service import (
    DEFAULT_TOP_N,
    AnalysisRecord,
    ScoreResult,
    ScorerUnavailableError,
    StoredZone,
)
from backend.app.services.nasiko_client import A2AReply, AgentInfo, NasikoError

logger = logging.getLogger(__name__)

SCORING_AGENT = "sitescout-scoring"
RUNNING_STATES = frozenset({"running", "ready", "active", "deployed"})


class AgentCallError(RuntimeError):
    """An agent could not be reached or did not answer usefully."""


class NasikoLike(Protocol):
    """The parts of ``NasikoClient`` the gateway uses (so tests can substitute a fake)."""

    def find_agent(self, name: str) -> AgentInfo | None: ...

    def send_message(
        self, agent_id: str, text: str | None = None, data: dict[str, Any] | None = None
    ) -> A2AReply: ...

    def route_message(self, text: str) -> A2AReply: ...


@dataclass(frozen=True)
class AgentReply:
    """A validated agent answer."""

    agent: str
    version: str
    latency_ms: int
    payload: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class AgentGateway:
    """Finds agents by name (caching their ids) and calls them with JSON requests."""

    def __init__(self, client: NasikoLike) -> None:
        self._client = client
        self._ids: dict[str, str] = {}
        self._lock = threading.Lock()

    def _agent_id(self, name: str) -> str:
        with self._lock:
            if name in self._ids:
                return self._ids[name]
        info = self._client.find_agent(name)
        if info is None:
            raise AgentCallError(f"agent {name!r} is not deployed on Nasiko")
        if info.status.lower() not in RUNNING_STATES:
            raise AgentCallError(f"agent {name!r} is not running (status {info.status!r})")
        with self._lock:
            self._ids[name] = info.id
        return info.id

    def call(self, name: str, request: Mapping[str, Any]) -> AgentReply:
        """Send ``request`` to the agent called ``name`` and return its payload."""
        try:
            agent_id = self._agent_id(name)
            reply = self._client.send_message(agent_id, text=json.dumps(request))
        except NasikoError as exc:
            self._forget(name)
            raise AgentCallError(str(exc)) from exc
        try:
            envelope = json.loads(reply.text)
        except json.JSONDecodeError as exc:
            self._forget(name)
            raise AgentCallError(f"agent {name!r} answered with text that is not JSON") from exc
        if not isinstance(envelope, dict):
            raise AgentCallError(f"agent {name!r} answered with an unexpected shape")
        if "error" in envelope:
            error = envelope["error"]
            raise AgentCallError(f"agent {name!r} reported an error: {error}")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise AgentCallError(f"agent {name!r} answered without a payload")
        return AgentReply(
            agent=str(envelope.get("agent", name)),
            version=str(envelope.get("version", "")),
            latency_ms=int(envelope.get("latency_ms", 0)),
            payload=payload,
            warnings=[str(w) for w in envelope.get("warnings", [])],
        )

    def _forget(self, name: str) -> None:
        """Drop a cached id so the next call looks the agent up again (it may have been rebuilt)."""
        with self._lock:
            self._ids.pop(name, None)

    def route(self, request: Mapping[str, Any]) -> AgentReply:
        """Ask Nasiko's routing engine to pick an agent for ``request`` (plan step 5.6.3)."""
        try:
            reply = self._client.route_message(json.dumps(request))
        except NasikoError as exc:
            raise AgentCallError(str(exc)) from exc
        try:
            envelope = json.loads(reply.text)
        except json.JSONDecodeError as exc:
            raise AgentCallError("the routed agent answered with text that is not JSON") from exc
        if not isinstance(envelope, dict):
            raise AgentCallError("the routed agent answered with an unexpected shape")
        if "error" in envelope:
            raise AgentCallError(f"the routed agent reported an error: {envelope['error']}")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise AgentCallError("the routed agent answered without a payload")
        return AgentReply(
            agent=str(envelope.get("agent", "unknown")),
            version=str(envelope.get("version", "")),
            latency_ms=int(envelope.get("latency_ms", 0)),
            payload=payload,
            warnings=[str(w) for w in envelope.get("warnings", [])],
        )


def scoring_request(record: AnalysisRecord) -> dict[str, Any]:
    """The JSON the scoring agent expects for one analysis."""
    return {
        "city": record.city_key,
        "category": record.category,
        "tier": record.tier,
        "answers": record.answers,
        "constraints": {k: v for k, v in record.constraints.items() if k != "top_n"},
        "top_n": int(record.constraints.get("top_n", DEFAULT_TOP_N)),
    }


def stored_zones_from_payload(zones: list[dict[str, Any]]) -> list[StoredZone]:
    """Rebuild ``StoredZone`` objects from the agent's JSON."""
    return [
        StoredZone(
            rank=int(z["rank"]),
            h3_index=str(z["h3_index"]),
            zone_name=str(z["zone_name"]),
            score=float(z["score"]),
            confidence=float(z["confidence"]),
            contributions={str(k): float(v) for k, v in z["contributions"].items()},
            top_drivers=[str(x) for x in z["top_drivers"]],
            top_risks=[str(x) for x in z["top_risks"]],
            narrative=z.get("narrative"),
        )
        for z in zones
    ]


class NasikoScorer:
    """A ``Scorer`` that runs the scoring step on the Nasiko ``sitescout-scoring`` agent."""

    def __init__(self, gateway: AgentGateway, agent_name: str = SCORING_AGENT) -> None:
        self._gateway = gateway
        self._agent = agent_name

    def __call__(self, record: AnalysisRecord, city_name: str) -> ScoreResult:
        try:
            reply = self._gateway.call(self._agent, scoring_request(record))
            zones = stored_zones_from_payload(list(reply.payload["zones"]))
            config_version = str(reply.payload["config_version"])
            notes = [str(n) for n in reply.payload.get("notes", [])]
        except (AgentCallError, KeyError, TypeError, ValueError) as exc:
            raise ScorerUnavailableError(str(exc)) from exc
        logger.info(
            "scored %s on Nasiko agent %s v%s in %d ms",
            record.id,
            reply.agent,
            reply.version,
            reply.latency_ms,
        )
        return ScoreResult(zones=zones, config_version=config_version, notes=notes)
