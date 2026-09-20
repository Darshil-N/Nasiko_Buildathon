"""POST /v1/analyses/{id}/chat (plan step 5.6.3): a grounded follow-up question about a
completed analysis, routed through Nasiko to the report-chat agent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.api.deps import ReadStore
from backend.app.core.auth import require_api_key
from backend.app.core.errors import AppError, ErrorCode
from backend.app.services.chat_service import answer_chat

router = APIRouter(dependencies=[Depends(require_api_key)])


class ChatQuestion(BaseModel):
    """The owner's follow-up question."""

    question: str = Field(min_length=1, max_length=500)


class ChatAnswerOut(BaseModel):
    """The answer, honest about whether it could be verified against the analysis's own data."""

    answer: str
    sources: list[str]
    grounded: bool


@router.post(
    "/analyses/{analysis_id}/chat",
    response_model=ChatAnswerOut,
    summary="Ask a follow-up question about a completed analysis",
)
def chat(analysis_id: str, body: ChatQuestion, request: Request, store: ReadStore) -> ChatAnswerOut:
    try:
        result = answer_chat(store, request.app.state.agent_gateway, analysis_id, body.question)
    except LookupError as exc:
        raise AppError(ErrorCode.NOT_FOUND, str(exc)) from exc
    return ChatAnswerOut(answer=result.answer, sources=result.sources, grounded=result.grounded)
