"""Tests for the pure agent runtime (no A2A SDK, no network)."""

from __future__ import annotations

import asyncio
import logging

import pytest
from pydantic import BaseModel, Field

from agents._shared.runner import AgentResult, envelope, extract_payload, run_json_agent


class ScoreRequest(BaseModel):
    city: str
    top_n: int = Field(default=10, ge=1, le=50)


class Ticker:
    """A clock that advances 5 ms every time it is read."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.005
        return self.now


def run(text: str | None, handler, clock=None):  # type: ignore[no-untyped-def]
    return asyncio.run(
        run_json_agent(
            agent="scoring",
            version="0.1.0",
            input_model=ScoreRequest,
            handler=handler,
            message_text=text,
            clock=clock or Ticker(),
        )
    )


async def ok_handler(request: ScoreRequest) -> AgentResult:
    return AgentResult(
        {"city": request.city, "top_n": request.top_n}, warnings=["rent data missing"]
    )


def test_extract_payload_variants() -> None:
    assert extract_payload('{"a": 1}') == {"a": 1}
    assert extract_payload("hello there") == {"text": "hello there"}
    assert extract_payload("[1, 2]") == {"text": "[1, 2]"}  # only objects are structured input
    assert extract_payload("") == {}
    assert extract_payload(None) == {}


def test_success_envelope_has_the_required_fields() -> None:
    reply = run('{"city": "bengaluru", "top_n": 5}', ok_handler)
    assert reply == {
        "agent": "scoring",
        "version": "0.1.0",
        "latency_ms": 5,
        "warnings": ["rent data missing"],
        "payload": {"city": "bengaluru", "top_n": 5},
    }


def test_defaults_are_applied_by_the_input_model() -> None:
    assert run('{"city": "x"}', ok_handler)["payload"]["top_n"] == 10


def test_invalid_input_returns_a_structured_error_not_an_exception() -> None:
    reply = run('{"top_n": 500}', ok_handler)
    assert "payload" not in reply
    assert reply["error"]["code"] == "INVALID_INPUT"
    fields = {d["field"] for d in reply["error"]["details"]}
    assert fields == {"city", "top_n"}


def test_plain_text_that_does_not_fit_the_model_is_invalid_input() -> None:
    assert run("what is the best area?", ok_handler)["error"]["code"] == "INVALID_INPUT"


def test_handler_crash_becomes_internal_error_without_leaking_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def boom(request: ScoreRequest) -> AgentResult:
        raise RuntimeError("password is hunter2")

    with caplog.at_level(logging.ERROR):
        reply = run('{"city": "x"}', boom)
    assert reply["error"]["code"] == "INTERNAL"
    assert "hunter2" not in str(reply)
    assert "hunter2" in caplog.text  # the detail stays in the log


def test_envelope_is_json_serialisable_and_has_no_payload_on_error() -> None:
    body = envelope("a", "1", 3, error={"code": "X", "message": "m"})
    assert "payload" not in body
    assert body["warnings"] == []
    assert envelope("a", "1", 3)["payload"] == {}
