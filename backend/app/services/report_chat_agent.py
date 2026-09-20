"""What the report-chat agent does (plan steps 5.3.2, 5.3.3): a grounded follow-up answer.

The primary model is small and local (D-03), so it can drift on numbers. The guardrail here is
literal: every number the answer states must already appear somewhere in the question or the zone
data it was given, and the answer must be 3 to 5 sentences. One regeneration is allowed before
falling back to an honest "can't confirm that" reply instead of guessing.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from shared.llm.client import LLMClient
from shared.llm.strict_json import LLMJsonParseError, generate_strict_json

AGENT_NAME = "sitescout-report-chat"
AGENT_VERSION = "0.1.1"
MIN_SENTENCES = 3
MAX_SENTENCES = 5
MAX_REGENERATIONS = 1

SAFE_FALLBACK = (
    "I can't confirm a grounded answer to that from this analysis's own data. "
    "Please check the zone detail screen for the figures directly."
)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?%?")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_ALWAYS_ALLOWED_NUMBERS = frozenset({"100", "0"})  # the score/percentage scale, not a data fact

SYSTEM_PROMPT = (
    "You are SiteScout's analysis assistant. Answer the owner's question about the store "
    "location analysis below using ONLY the numbers and facts given to you. Never invent a "
    "number that is not in the data provided. Answer in 3 to 5 sentences."
)


class ZoneContext(BaseModel):
    """One ranked zone's data, exactly as already shown to the owner."""

    rank: int
    zone_name: str
    score: float
    confidence: float
    contributions: dict[str, float] = Field(default_factory=dict)
    top_drivers: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    narrative: str | None = None


class ChatRequest(BaseModel):
    """One follow-up question about an already-run analysis."""

    question: str = Field(min_length=1, max_length=500)
    city: str
    category: str
    tier: str
    zones: list[ZoneContext] = Field(default_factory=list, max_length=10)


class _RawAnswer(BaseModel):
    """What the LLM must return: the answer text alone."""

    answer: str


class ChatAnswer(BaseModel):
    """What the agent returns: the answer plus which zones it drew on."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    grounded: bool


def _numbers_in(text: str) -> set[str]:
    return {n.rstrip("%") for n in _NUMBER_RE.findall(text)}


def _context_text(request: ChatRequest) -> str:
    parts = [request.question, request.city, request.category, request.tier]
    for zone in request.zones:
        parts += [zone.zone_name, f"{zone.score:.0f}", f"{zone.confidence * 100:.0f}"]
        parts += zone.top_drivers
        parts += zone.top_risks
        if zone.narrative:
            parts.append(zone.narrative)
        parts += [f"{v:.0f}" for v in zone.contributions.values()]
    return " ".join(parts)


def _sentence_count(text: str) -> int:
    return len([s for s in _SENTENCE_RE.split(text.strip()) if s])


def _is_grounded_and_sized(answer: str, request: ChatRequest) -> bool:
    allowed = _numbers_in(_context_text(request)) | _ALWAYS_ALLOWED_NUMBERS
    if not _numbers_in(answer).issubset(allowed):
        return False
    return MIN_SENTENCES <= _sentence_count(answer) <= MAX_SENTENCES


def answer_question(client: LLMClient, request: ChatRequest) -> ChatAnswer:
    """Answer a follow-up question about an analysis, grounded in the data it was given."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Analysis data:\n{request.model_dump_json()}\n\nQuestion: {request.question}"
            ),
        },
    ]
    for attempt in range(MAX_REGENERATIONS + 1):
        try:
            raw = generate_strict_json(client, _RawAnswer, messages, max_retries=0)
        except LLMJsonParseError:
            continue
        if _is_grounded_and_sized(raw.answer, request):
            sources = [zone.zone_name for zone in request.zones]
            return ChatAnswer(answer=raw.answer, sources=sources, grounded=True)
        if attempt < MAX_REGENERATIONS:
            messages += [
                {"role": "assistant", "content": raw.answer},
                {
                    "role": "user",
                    "content": (
                        "That answer used a number that isn't in the data, or wasn't 3 to 5 "
                        "sentences. Answer again, using only the numbers given above."
                    ),
                },
            ]
    return ChatAnswer(answer=SAFE_FALLBACK, sources=[], grounded=False)
