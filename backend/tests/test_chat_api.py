"""Tests for POST /v1/analyses/{id}/chat (plan step 5.6.3), through the real app."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.services.agent_gateway import AgentGateway
from backend.app.services.analysis_service import CellMeta
from backend.app.services.nasiko_client import A2AReply, AgentInfo
from backend.tests.test_analysis_api import HEADERS, MemoryStore, create
from pipelines.features_store import FeatureBundle


@pytest.fixture
def store(bundles: list[FeatureBundle], meta: dict[str, CellMeta]) -> MemoryStore:
    return MemoryStore(bundles, meta)


@contextmanager
def _store_context(store: MemoryStore) -> Iterator[MemoryStore]:
    yield store


@pytest.fixture
def client(store: MemoryStore) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@127.0.0.1:5433/x",
        backend_api_key=HEADERS["X-API-Key"],
    )
    app = create_app(settings)
    app.state.open_store = lambda write: _store_context(store)
    return TestClient(app, raise_server_exceptions=False)


class FakeReportChat:
    """Stands in for Nasiko: the report-chat agent is called directly, by name."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.sent: dict[str, Any] | None = None

    def find_agent(self, name: str) -> AgentInfo | None:
        if name != "sitescout-report-chat":
            return None
        return AgentInfo(id="agent-1", name=name, status="running", version=None, url=None)

    def send_message(self, agent_id: str, text: str | None = None, data: Any = None) -> A2AReply:
        self.sent = json.loads(text or "{}")
        envelope = {"agent": "sitescout-report-chat", "version": "0.1.1", "latency_ms": 5}
        envelope["payload"] = self.payload
        return A2AReply(state="TASK_STATE_COMPLETED", text=json.dumps(envelope))

    def route_message(self, text: str) -> A2AReply:
        raise AssertionError("chat should call the agent directly, not the routing engine")


def test_chat_answers_through_the_report_chat_agent_when_a_gateway_is_configured(
    client: TestClient, store: MemoryStore
) -> None:
    analysis_id = create(client)
    payload = {
        "answer": "Officers Colony leads.",
        "sources": ["Officers Colony"],
        "grounded": True,
    }
    agent = FakeReportChat(payload)
    client.app.state.agent_gateway = AgentGateway(agent)  # type: ignore[attr-defined]

    response = client.post(
        f"/v1/analyses/{analysis_id}/chat", json={"question": "Why?"}, headers=HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.json() == payload
    assert agent.sent is not None
    assert agent.sent["question"] == "Why?"
    assert agent.sent["category"] == "cafe"


def test_chat_says_not_available_when_no_gateway_is_configured(
    client: TestClient, store: MemoryStore
) -> None:
    analysis_id = create(client)
    client.app.state.agent_gateway = None  # type: ignore[attr-defined]

    response = client.post(
        f"/v1/analyses/{analysis_id}/chat", json={"question": "Why?"}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert "can't reach the chat agent" in body["answer"]


def test_chat_on_an_unknown_analysis_is_not_found(client: TestClient) -> None:
    response = client.post(
        "/v1/analyses/an_missing01/chat", json={"question": "Why?"}, headers=HEADERS
    )
    assert response.status_code == 404


def test_chat_rejects_an_empty_question(client: TestClient, store: MemoryStore) -> None:
    analysis_id = create(client)
    response = client.post(
        f"/v1/analyses/{analysis_id}/chat", json={"question": ""}, headers=HEADERS
    )
    assert response.status_code == 422
