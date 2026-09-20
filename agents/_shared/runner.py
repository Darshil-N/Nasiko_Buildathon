"""Pure logic shared by every SiteScout agent (architecture section 9.4, plan step 5.1.1).

An agent receives one message, validates it against its own Pydantic model, runs its handler,
and answers with a JSON envelope:

    {"agent": "...", "version": "...", "latency_ms": 12, "warnings": [], "payload": {...}}

or, when something went wrong, the same envelope with an ``error`` object instead of a payload.
Nothing here imports the A2A SDK, so it is fully unit-testable outside a container.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)


@dataclass(frozen=True)
class AgentResult:
    """What a handler returns: the payload plus any warnings worth showing the user."""

    payload: Mapping[str, Any]
    warnings: list[str] = field(default_factory=list)


Handler = Callable[[InputT], Awaitable[AgentResult]]


def extract_payload(text: str | None) -> dict[str, Any]:
    """Turn the user's message text into a dict.

    JSON objects are parsed as-is; any other text becomes ``{"text": <text>}`` so plain
    natural-language questions still reach the handler.
    """
    if text is None or not text.strip():
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"text": text}


def envelope(
    agent: str,
    version: str,
    latency_ms: int,
    *,
    payload: Mapping[str, Any] | None = None,
    warnings: list[str] | None = None,
    error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard response envelope."""
    body: dict[str, Any] = {
        "agent": agent,
        "version": version,
        "latency_ms": latency_ms,
        "warnings": list(warnings or []),
    }
    if error is not None:
        body["error"] = dict(error)
    else:
        body["payload"] = dict(payload or {})
    return body


async def run_json_agent(
    *,
    agent: str,
    version: str,
    input_model: type[InputT],
    handler: Handler[InputT],
    message_text: str | None,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Validate the message, run the handler, and return the envelope. Never raises."""
    started = clock()

    def elapsed_ms() -> int:
        return round((clock() - started) * 1000)

    try:
        request = input_model.model_validate(extract_payload(message_text))
    except ValidationError as exc:
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]} for e in exc.errors()
        ]
        error = {
            "code": "INVALID_INPUT",
            "message": "The request is not valid.",
            "details": details,
        }
        return envelope(agent, version, elapsed_ms(), error=error)

    try:
        result = await handler(request)
    except Exception:
        logger.exception("agent %s failed", agent)  # details stay in the log, not the reply
        error = {"code": "INTERNAL", "message": "The agent failed while handling the request."}
        return envelope(agent, version, elapsed_ms(), error=error)
    return envelope(agent, version, elapsed_ms(), payload=result.payload, warnings=result.warnings)
