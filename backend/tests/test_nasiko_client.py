"""Tests for the Nasiko client against a fake server (no network)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from backend.app.services.nasiko_client import (
    NasikoClient,
    NasikoError,
    message_payload,
    parse_event_stream,
    parse_task,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeNasiko:
    """A tiny stand-in for the Nasiko API; records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.logins = 0
        self.revoked = False
        self.build_states = iter(["queued", "building", "completed"])
        self.overrides: dict[str, Callable[[httpx.Request], httpx.Response]] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path in self.overrides:
            return self.overrides[path](request)
        if path == "/api/auth/login":
            self.logins += 1
            self.revoked = False
            return httpx.Response(200, json={"token": f"tok-{self.logins}", "expires_in": 3600})
        if self.revoked or request.headers.get("authorization") != f"Bearer tok-{self.logins}":
            return httpx.Response(401)
        if path == "/api/agents" and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "a1",
                        "name": "hello",
                        "status": "running",
                        "version": "0.1.0",
                        "url": "http://x",
                    }
                ],
            )
        if path == "/api/agents/upload":
            return httpx.Response(
                202,
                json={"data": {"agent_id": "a2", "build_id": "b1", "validation_errors": []}},
            )
        if path == "/api/agents/uploads/b1":
            state = next(self.build_states)
            return httpx.Response(
                200,
                json={"status": state, "status_message": f"is {state}", "agent_url": "http://y"},
            )
        if path.startswith("/api/agents/a1") and request.method == "POST":
            return httpx.Response(200, json={"result": TASK_RESULT, "id": "1", "jsonrpc": "2.0"})
        if path == "/api/orchestrator/a2a":
            return httpx.Response(200, text=EVENT_STREAM)
        return httpx.Response(404)


TASK_RESULT = {
    "task": {
        "status": {"state": "TASK_STATE_COMPLETED"},
        "artifacts": [
            {"parts": [{"text": "Hello "}, {"text": "world"}, {"data": {"score": 7}}]},
        ],
    }
}


def _event(payload: dict[str, Any]) -> str:
    return "data: " + json.dumps(payload)


_TRACE_PART = {"data": {"type": "trace_meta", "trace_id": "t-123"}}
EVENT_STREAM = "\n\n".join(
    [
        _event({"statusUpdate": {"status": {"state": "TASK_STATE_WORKING"}}}),
        _event(
            {
                "statusUpdate": {
                    "status": {"state": "TASK_STATE_WORKING", "message": {"parts": [_TRACE_PART]}}
                }
            }
        ),
        _event({"artifactUpdate": {"artifact": {"parts": [{"text": "To"}]}}}),
        "data: not json",
        _event({"artifactUpdate": {"artifact": {"parts": [{"text": " go"}]}}}),
        _event({"statusUpdate": {"status": {"state": "TASK_STATE_COMPLETED"}}}),
    ]
)


def make(fake: FakeNasiko, clock: FakeClock | None = None) -> NasikoClient:
    clock = clock or FakeClock()
    return NasikoClient(
        "http://nasiko.test",
        "admin",
        "pw",
        client=httpx.Client(transport=httpx.MockTransport(fake)),
        clock=clock.clock,
        sleep=clock.sleep,
    )


def test_message_payload_shapes() -> None:
    body = message_payload("hi", {"k": 1})
    parts = body["params"]["message"]["parts"]
    assert parts == [{"text": "hi"}, {"data": {"k": 1}}]
    assert body["method"] == "SendMessage"
    assert body["params"]["message"]["role"] == "ROLE_USER"
    with pytest.raises(ValueError, match="needs text"):
        message_payload()


def test_parse_task_and_event_stream() -> None:
    reply = parse_task(TASK_RESULT)
    assert reply.completed
    assert reply.text == "Hello world"
    assert reply.data == [{"score": 7}]
    streamed = parse_event_stream(EVENT_STREAM)
    assert streamed.text == "To go"
    assert streamed.trace_id == "t-123"
    assert streamed.completed


def test_login_happens_once_and_token_is_reused() -> None:
    fake = FakeNasiko()
    client = make(fake)
    client.list_agents()
    client.list_agents()
    assert fake.logins == 1


def test_token_is_refreshed_before_it_expires() -> None:
    fake, clock = FakeNasiko(), FakeClock()
    client = make(fake, clock)
    client.list_agents()
    clock.now = 3600 - 30  # inside the 60 s refresh margin
    client.list_agents()
    assert fake.logins == 2


def test_a_401_triggers_one_relogin_and_retry() -> None:
    fake = FakeNasiko()
    client = make(fake)
    client.list_agents()
    fake.revoked = True  # the server forgets the token; the next login clears it
    assert client.list_agents()[0].name == "hello"
    assert fake.logins == 2


def test_login_failure_is_reported_without_the_password() -> None:
    fake = FakeNasiko()
    fake.overrides["/api/auth/login"] = lambda r: httpx.Response(401)
    with pytest.raises(NasikoError) as excinfo:
        make(fake).list_agents()
    assert "pw" not in str(excinfo.value)
    assert "login failed" in str(excinfo.value)


def test_find_agent() -> None:
    client = make(FakeNasiko())
    found = client.find_agent("hello")
    assert found is not None
    assert found.id == "a1"
    assert found.status == "running"
    assert client.find_agent("nope") is None


def test_upload_and_wait_for_build() -> None:
    fake, clock = FakeNasiko(), FakeClock()
    client = make(fake, clock)
    ticket = client.upload_agent("sitescout-x", b"zipbytes")
    assert (ticket.agent_id, ticket.build_id) == ("a2", "b1")
    upload = next(r for r in fake.requests if r.url.path == "/api/agents/upload")
    assert b"zipbytes" in upload.content
    assert b'name="name"' in upload.content
    final = client.wait_for_build("b1", poll_s=2)
    assert final.status == "completed"
    assert clock.sleeps == [2, 2]  # queued, building, then completed


def test_failed_and_slow_builds_raise() -> None:
    fake = FakeNasiko()
    fake.build_states = iter(["failed"])
    with pytest.raises(NasikoError, match="build failed"):
        make(fake).wait_for_build("b1")

    slow = FakeNasiko()
    slow.build_states = iter(["building"] * 100)
    with pytest.raises(NasikoError, match="still 'building'"):
        make(slow, FakeClock()).wait_for_build("b1", timeout_s=20, poll_s=5)


def test_invalid_package_is_rejected() -> None:
    fake = FakeNasiko()
    fake.overrides["/api/agents/upload"] = lambda r: httpx.Response(
        202,
        json={"data": {"agent_id": "a", "build_id": "b", "validation_errors": ["no Dockerfile"]}},
    )
    with pytest.raises(NasikoError, match="no Dockerfile"):
        make(fake).upload_agent("x", b"z")


def test_send_message_sends_the_a2a_version_header_and_parses_the_reply() -> None:
    fake = FakeNasiko()
    reply = make(fake).send_message("a1", "hi", {"k": 1})
    request = next(r for r in fake.requests if r.url.path == "/api/agents/a1")
    assert request.headers["a2a-version"] == "1.0"
    sent: dict[str, Any] = json.loads(request.content)
    assert sent["params"]["message"]["parts"] == [{"text": "hi"}, {"data": {"k": 1}}]
    assert reply.text == "Hello world"
    assert reply.data == [{"score": 7}]


def test_agent_errors_and_upstream_failures_become_nasiko_errors() -> None:
    fake = FakeNasiko()
    fake.overrides["/api/agents/a1"] = lambda r: httpx.Response(
        200, json={"error": {"code": -32000}}
    )
    with pytest.raises(NasikoError, match="agent returned an error"):
        make(fake).send_message("a1", "hi")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    down = NasikoClient(
        "http://nasiko.test", "a", "b", client=httpx.Client(transport=httpx.MockTransport(refuse))
    )
    with pytest.raises(NasikoError, match="could not reach Nasiko"):
        down.list_agents()


def test_timeouts_are_reported_as_nasiko_errors() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client = NasikoClient(
        "http://nasiko.test", "a", "b", client=httpx.Client(transport=httpx.MockTransport(slow))
    )
    with pytest.raises(NasikoError, match="timed out"):
        client.list_agents()


def test_route_message_uses_the_routing_engine() -> None:
    fake = FakeNasiko()
    reply = make(fake).route_message("Which area suits a cafe?")
    assert reply.text == "To go"
    assert reply.trace_id == "t-123"
    assert any(r.url.path == "/api/orchestrator/a2a" for r in fake.requests)
