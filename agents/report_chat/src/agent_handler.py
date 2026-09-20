"""What the report-chat agent does with one validated request (plan steps 5.3.2, 5.3.3).

Kept tiny on purpose: the guardrails and prompt live in
``backend.app.services.report_chat_agent`` (unit-tested on the host with a mocked LLM); this
module only builds the LLM client that talks to Nasiko's LLM Router.
"""

from __future__ import annotations

from agent_base.runner import AgentResult

from backend.app.services.report_chat_agent import (
    AGENT_NAME,
    AGENT_VERSION,
    ChatRequest,
    answer_question,
)
from shared.llm.client import LLMClient

__all__ = ["AGENT_NAME", "AGENT_VERSION", "handle"]

_client = LLMClient(use_router=True)


async def handle(request: ChatRequest) -> AgentResult:
    """Answer the question, grounded in the analysis data it was given."""
    answer = answer_question(_client, request)
    return AgentResult(payload=answer.model_dump())
