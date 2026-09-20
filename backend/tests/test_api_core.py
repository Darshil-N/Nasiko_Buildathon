"""Tests for the backend skeleton: settings, envelope, auth, request ids, health, cities.

No database is used: the read session is replaced by a fake, and a real ``TestClient`` drives the
real app. Fakes never write anything.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from backend.app.core.logging import JsonFormatter, request_id_var
from backend.app.core.settings import Settings
from backend.app.db.session import get_read_session
from backend.app.main import create_app

KEY = "test-key-12345"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql+psycopg://u:p@localhost:5433/x",
        "backend_api_key": KEY,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class FakeSession:
    """Stands in for a SQLAlchemy session; records statements, never touches a database."""

    def __init__(self, rows: list[Any] | None = None, fail: bool = False) -> None:
        self.rows = rows or []
        self.fail = fail
        self.statements: list[str] = []

    def execute(self, statement: Any) -> SimpleNamespace:
        self.statements.append(str(statement))
        if self.fail:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        return SimpleNamespace(all=lambda: self.rows)


def client_with(session: FakeSession, app: FastAPI | None = None) -> TestClient:
    app = app or create_app(make_settings())

    def override() -> Iterator[FakeSession]:
        yield session

    app.dependency_overrides[get_read_session] = override
    return TestClient(app, raise_server_exceptions=False)


# --- settings --------------------------------------------------------------------------------
def test_cors_origins_are_split_and_trimmed() -> None:
    s = make_settings(allowed_origins="http://a.test, http://b.test ,,")
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_short_api_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(backend_api_key="short")


def test_placeholder_key_is_rejected_only_in_production() -> None:
    make_settings(backend_api_key="change-me", environment="dev")
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(backend_api_key="change-me", environment="prod")


def test_secret_is_not_printed() -> None:
    assert KEY not in repr(make_settings())


# --- health ----------------------------------------------------------------------------------
def test_health_is_public_and_reports_database_ok() -> None:
    session = FakeSession()
    response = client_with(session).get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ok",
        "api_version": "v1",
        "app_version": "0.1.0",
        "database": "ok",
    }
    assert session.statements == ["SELECT 1"]


def test_health_survives_a_database_outage() -> None:
    response = client_with(FakeSession(fail=True)).get("/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "unavailable"


# --- auth and the error envelope -------------------------------------------------------------
@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong-key-value"}, {"X-API-Key": ""}])
def test_cities_requires_the_api_key(headers: dict[str, str]) -> None:
    response = client_with(FakeSession()).get("/v1/cities", headers=headers)
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "UNAUTHORIZED"
    assert error["retryable"] is False
    assert "request_id" in error


def test_cities_lists_ready_cities_only() -> None:
    row = SimpleNamespace(id=1, key="bengaluru", name="Bengaluru", state="Karnataka", country="IN")
    session = FakeSession(rows=[row])
    response = client_with(session).get("/v1/cities", headers={"X-API-Key": KEY})
    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "key": "bengaluru", "name": "Bengaluru", "state": "Karnataka", "country": "IN"}
    ]
    sql = session.statements[0]
    assert "cities.status = " in sql
    assert "ORDER BY cities.name" in sql


def test_unknown_route_uses_the_envelope() -> None:
    response = client_with(FakeSession()).get("/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_validation_errors_use_the_envelope_with_details() -> None:
    app = create_app(make_settings())

    @app.get("/v1/echo")
    def echo(n: int) -> dict[str, int]:
        return {"n": n}

    response = client_with(FakeSession(), app).get("/v1/echo", params={"n": "abc"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_INPUT"
    assert error["details"][0]["field"] == "query.n"


def test_unhandled_errors_do_not_leak_details() -> None:
    app = create_app(make_settings())

    @app.get("/v1/boom")
    def boom() -> None:
        raise RuntimeError("secret database password is hunter2")

    response = client_with(FakeSession(), app).get("/v1/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert "hunter2" not in response.text
    assert response.headers["X-Request-ID"]


# --- request ids and logging -----------------------------------------------------------------
def test_request_id_is_echoed_or_generated() -> None:
    client = client_with(FakeSession())
    assert (
        client.get("/v1/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"]
        == "abc-123"
    )
    generated = client.get("/v1/health").headers["X-Request-ID"]
    assert len(generated) == 32
    too_long = client.get("/v1/health", headers={"X-Request-ID": "x" * 200}).headers["X-Request-ID"]
    assert too_long != "x" * 200


def test_cors_allows_only_configured_origins() -> None:
    client = client_with(FakeSession())
    allowed = client.options(
        "/v1/health",
        headers={"Origin": "http://localhost:8501", "Access-Control-Request-Method": "GET"},
    )
    denied = client.options(
        "/v1/health",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:8501"
    assert "access-control-allow-origin" not in denied.headers


def test_json_formatter_includes_request_id_and_extras() -> None:
    token = request_id_var.set("rid-1")
    try:
        record = logging.LogRecord("t", logging.INFO, "f.py", 1, "hello %s", ("x",), None)
        record.status = 200
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["message"] == "hello x"
    assert payload["request_id"] == "rid-1"
    assert payload["status"] == 200
    assert payload["level"] == "INFO"
