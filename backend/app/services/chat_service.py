"""Chat orchestration (plan step 5.6.3): ask the report-chat agent a follow-up question about
an already-run analysis, grounded in its own stored recommendations.

Calls the agent directly by name rather than through Nasiko's generic routing engine
(``/api/orchestrator/a2a``): that endpoint turned out to run its own LLM reasoning over the
message and answer in free text, rather than relaying the agent's JSON envelope, which would
bypass the numeric-grounding guardrail entirely (verified against the real deployment). Decision
D-04 already settled this the other way: the orchestrator lives in the backend, which calls each
agent directly, so a named call is the correct shape here, not a routing shortcut.

Returns an explicit "not available" answer, never a guess, when the agent can't be reached or its
reply cannot be trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.services.agent_gateway import AgentCallError, AgentGateway
from backend.app.services.analysis_service import AnalysisStore
from backend.app.services.report_chat_agent import AGENT_NAME as REPORT_CHAT_AGENT

MAX_ZONES_IN_CONTEXT = 5

NOT_AVAILABLE = (
    "I can't reach the chat agent right now, so I can't answer that. "
    "The zone detail screen has the same figures directly."
)


@dataclass(frozen=True)
class ChatAnswer:
    """A chat reply, honest about whether it could be verified."""

    answer: str
    sources: list[str] = field(default_factory=list)
    grounded: bool = False


def _chat_request_payload(store: AnalysisStore, analysis_id: str) -> dict[str, Any] | None:
    record = store.load_analysis(analysis_id)
    if record is None or record.status != "done":
        return None
    zones = store.load_recommendations(analysis_id)[:MAX_ZONES_IN_CONTEXT]
    return {
        "city": record.city_key,
        "category": record.category,
        "tier": record.tier,
        "zones": [
            {
                "rank": z.rank,
                "zone_name": z.zone_name,
                "score": z.score,
                "confidence": z.confidence,
                "contributions": z.contributions,
                "top_drivers": z.top_drivers,
                "top_risks": z.top_risks,
                "narrative": z.narrative,
            }
            for z in zones
        ],
    }


def answer_chat(
    store: AnalysisStore, gateway: AgentGateway | None, analysis_id: str, question: str
) -> ChatAnswer:
    """Answer ``question`` about ``analysis_id``, or an honest "not available" reply."""
    context = _chat_request_payload(store, analysis_id)
    if context is None:
        raise LookupError(f"no completed analysis {analysis_id!r} to chat about")
    if gateway is None:
        return ChatAnswer(answer=NOT_AVAILABLE)
    request = {"question": question, **context}
    try:
        reply = gateway.call(REPORT_CHAT_AGENT, request)
        return ChatAnswer(
            answer=str(reply.payload["answer"]),
            sources=[str(s) for s in reply.payload.get("sources", [])],
            grounded=bool(reply.payload.get("grounded", False)),
        )
    except (AgentCallError, KeyError, TypeError, ValueError):
        return ChatAnswer(answer=NOT_AVAILABLE)
