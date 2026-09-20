"""Tests for the report-chat agent's guardrails (plan step 5.3.3): grounding and length checks."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from backend.app.services.report_chat_agent import (
    SAFE_FALLBACK,
    ChatRequest,
    ZoneContext,
    answer_question,
)
from shared.llm.client import LLMClient

ZONE = ZoneContext(
    rank=1,
    zone_name="Indiranagar",
    score=82.6,
    confidence=0.95,
    contributions={"F1_anchor_footfall": 26.3},
    top_drivers=["High footfall anchors"],
    top_risks=["High competition"],
    narrative="Indiranagar ranks #1 with a score of 83.",
)


def request(question: str = "Why is Indiranagar top?") -> ChatRequest:
    return ChatRequest(
        question=question, city="Bengaluru", category="cafe", tier="mid", zones=[ZONE]
    )


def fake_client(*answers: str) -> LLMClient:
    client = MagicMock(spec=LLMClient)
    client.generate.side_effect = [json.dumps({"answer": a}) for a in answers]
    return client


def test_a_grounded_answer_is_returned_with_sources() -> None:
    answer = (
        "Indiranagar leads with a score of 83 out of 100. It has strong footfall anchors "
        "nearby. Confidence in this ranking is 95 percent, though competition is high."
    )
    client = fake_client(answer)
    result = answer_question(client, request())
    assert result.answer == answer
    assert result.grounded is True
    assert result.sources == ["Indiranagar"]


def test_a_hallucinated_number_triggers_one_regeneration_then_succeeds() -> None:
    bad = "Indiranagar has 4200 competitors nearby, giving it a score of 83 out of 100."
    good = (
        "Indiranagar has a score of 83 out of 100. It benefits from strong footfall anchors "
        "nearby. Confidence in this ranking is 95 percent."
    )
    client = fake_client(bad, good)
    result = answer_question(client, request())
    assert client.generate.call_count == 2  # type: ignore[attr-defined]
    assert result.answer == good
    assert result.grounded is True


def test_repeated_hallucination_falls_back_to_the_safe_answer() -> None:
    bad = "There are 4200 competitors nearby, so the score is 83 out of 100."
    client = fake_client(bad, bad)
    result = answer_question(client, request())
    assert result.answer == SAFE_FALLBACK
    assert result.grounded is False
    assert result.sources == []


def test_an_answer_that_is_too_short_is_rejected() -> None:
    short = "Yes."
    client = fake_client(short, short)
    result = answer_question(client, request())
    assert result.grounded is False


def test_invalid_json_from_the_model_is_treated_like_a_failed_attempt() -> None:
    client = MagicMock(spec=LLMClient)
    ok = (
        "Indiranagar has a score of 83 out of 100. It has strong footfall anchors nearby. "
        "This ranks it #1 in the area."
    )
    client.generate.side_effect = ["not json at all", json.dumps({"answer": ok})]
    result = answer_question(client, request())
    assert result.grounded is True
    assert result.answer == ok
