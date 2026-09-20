"""Typed client for the parts of Nasiko's HTTP API that SiteScout uses (plan step 5.6.1).

* login (bearer token, refreshed automatically),
* list agents, upload an agent zip, wait for its build,
* send an A2A ``SendMessage`` to a named agent through Nasiko's proxy,
* ask the routing engine to pick the agent (``/api/orchestrator/a2a``, server-sent events).

The client is synchronous (FastAPI runs sync endpoints in a thread pool) and every call has a
timeout. Secrets are never logged.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

A2A_VERSION = "1.0"
TOKEN_REFRESH_MARGIN_S = 60.0
DONE_BUILD_STATES = frozenset({"completed", "failed"})


class NasikoError(RuntimeError):
    """Nasiko could not do what was asked; the message is safe to show in logs."""


@dataclass(frozen=True)
class AgentInfo:
    """One registered agent."""

    id: str
    name: str
    status: str
    version: str | None
    url: str | None


@dataclass(frozen=True)
class UploadTicket:
    """Identifiers returned when an agent zip is accepted."""

    agent_id: str
    build_id: str


@dataclass(frozen=True)
class BuildStatus:
    """State of an agent build."""

    status: str
    message: str
    agent_url: str | None = None


@dataclass(frozen=True)
class A2AReply:
    """The useful parts of an A2A task result."""

    state: str
    text: str
    data: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None

    @property
    def completed(self) -> bool:
        return self.state == "TASK_STATE_COMPLETED"


def message_payload(text: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build an A2A v1.0 ``SendMessage`` JSON-RPC body with text and/or structured data parts."""
    parts: list[dict[str, Any]] = []
    if text is not None:
        parts.append({"text": text})
    if data is not None:
        parts.append({"data": data})
    if not parts:
        raise ValueError("a message needs text, data, or both")
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "SendMessage",
        "params": {
            "message": {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": parts},
            "configuration": {"acceptedOutputModes": ["text/plain", "application/json"]},
        },
    }


def parse_task(result: dict[str, Any]) -> A2AReply:
    """Extract state, text and data parts from a JSON-RPC ``result``."""
    task = result.get("task", result)
    state = str(task.get("status", {}).get("state", "TASK_STATE_UNKNOWN"))
    texts: list[str] = []
    data: list[dict[str, Any]] = []
    for artifact in task.get("artifacts", []):
        for part in artifact.get("parts", []):
            if "text" in part:
                texts.append(str(part["text"]))
            if isinstance(part.get("data"), dict):
                data.append(part["data"])
    return A2AReply(state=state, text="".join(texts), data=data)


def parse_event_stream(body: str) -> A2AReply:
    """Fold a server-sent-events body from the routing engine into one reply."""
    state = "TASK_STATE_UNKNOWN"
    text: list[str] = []
    data: list[dict[str, Any]] = []
    trace_id: str | None = None
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line.removeprefix("data:").strip())
        except json.JSONDecodeError:
            continue
        if "statusUpdate" in event:
            status = event["statusUpdate"]["status"]
            state = str(status.get("state", state))
            for part in status.get("message", {}).get("parts", []):
                meta = part.get("data")
                if isinstance(meta, dict) and meta.get("type") == "trace_meta":
                    trace_id = str(meta.get("trace_id"))
        elif "artifactUpdate" in event:
            for part in event["artifactUpdate"]["artifact"].get("parts", []):
                if "text" in part:
                    text.append(str(part["text"]))
                if isinstance(part.get("data"), dict):
                    data.append(part["data"])
    return A2AReply(state=state, text="".join(text), data=data, trace_id=trace_id)


class NasikoClient:
    """Talks to one Nasiko server as one user."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        client: httpx.Client | None = None,
        timeout_s: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._client = client or httpx.Client(timeout=timeout_s)
        self._clock = clock
        self._sleep = sleep
        self._token: str | None = None
        self._token_expires_at = 0.0

    # --- auth -----------------------------------------------------------------------------------
    def _login(self) -> None:
        response = self._send(
            "POST",
            "/api/auth/login",
            json={"username": self._username, "password": self._password},
            authenticated=False,
        )
        if response.status_code != 200:
            raise NasikoError(f"login failed with HTTP {response.status_code}")
        body = response.json()
        self._token = str(body["token"])
        self._token_expires_at = self._clock() + float(body.get("expires_in", 3600))

    def _bearer(self) -> str:
        if self._token is None or self._clock() >= self._token_expires_at - TOKEN_REFRESH_MARGIN_S:
            self._login()
        if self._token is None:
            raise NasikoError("login did not produce a token")
        return self._token

    def _send(
        self, method: str, path: str, *, authenticated: bool = True, **kwargs: Any
    ) -> httpx.Response:
        headers: dict[str, str] = dict(kwargs.pop("headers", {}))
        if authenticated:
            headers["Authorization"] = f"Bearer {self._bearer()}"
        try:
            return self._client.request(method, f"{self._base}{path}", headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise NasikoError(f"timed out calling Nasiko {method} {path}") from exc
        except httpx.HTTPError as exc:
            raise NasikoError(f"could not reach Nasiko at {self._base}: {exc}") from exc

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Authenticated request; on 401 log in again once and retry."""
        response = self._send(method, path, **kwargs)
        if response.status_code == 401:
            self._token = None
            response = self._send(method, path, **kwargs)
        return response

    # --- agents ---------------------------------------------------------------------------------
    def list_agents(self) -> list[AgentInfo]:
        """All agents visible to this user."""
        response = self._request("GET", "/api/agents")
        if response.status_code != 200:
            raise NasikoError(f"listing agents failed with HTTP {response.status_code}")
        rows = response.json()
        return [
            AgentInfo(
                id=str(r["id"]),
                name=str(r["name"]),
                status=str(r.get("status", "unknown")),
                version=r.get("version"),
                url=r.get("url"),
            )
            for r in rows
        ]

    def find_agent(self, name: str) -> AgentInfo | None:
        """The agent called ``name``, or None."""
        return next((a for a in self.list_agents() if a.name == name), None)

    def upload_agent(self, name: str, zip_bytes: bytes) -> UploadTicket:
        """Upload an agent zip (AgentCard.json plus Dockerfile); the server builds it."""
        response = self._request(
            "POST",
            "/api/agents/upload",
            data={"name": name},
            files={"file": (f"{name}.zip", zip_bytes, "application/zip")},
        )
        if response.status_code not in {200, 202}:
            raise NasikoError(
                f"upload rejected: HTTP {response.status_code}: {response.text[:300]}"
            )
        data = response.json()["data"]
        if data.get("validation_errors"):
            raise NasikoError(f"agent package is invalid: {data['validation_errors']}")
        return UploadTicket(agent_id=str(data["agent_id"]), build_id=str(data["build_id"]))

    def build_status(self, build_id: str) -> BuildStatus:
        """Current state of a build."""
        response = self._request("GET", f"/api/agents/uploads/{build_id}")
        if response.status_code != 200:
            raise NasikoError(f"build status failed with HTTP {response.status_code}")
        body = response.json()
        return BuildStatus(
            status=str(body.get("status", "unknown")).lower(),
            message=str(body.get("status_message", "")),
            agent_url=body.get("agent_url"),
        )

    def wait_for_build(
        self, build_id: str, *, timeout_s: float = 600.0, poll_s: float = 5.0
    ) -> BuildStatus:
        """Poll until the build completes or fails.

        Raises:
            NasikoError: if the build fails or does not finish within ``timeout_s``.
        """
        deadline = self._clock() + timeout_s
        while True:
            status = self.build_status(build_id)
            if status.status in DONE_BUILD_STATES:
                if status.status == "failed":
                    raise NasikoError(f"build failed: {status.message}")
                return status
            if self._clock() >= deadline:
                raise NasikoError(f"build still {status.status!r} after {timeout_s:.0f}s")
            self._sleep(poll_s)

    # --- talking to agents ----------------------------------------------------------------------
    def send_message(
        self, agent_id: str, text: str | None = None, data: dict[str, Any] | None = None
    ) -> A2AReply:
        """Send an A2A message to one agent through Nasiko's proxy and wait for the result."""
        response = self._request(
            "POST",
            f"/api/agents/{agent_id}",
            json=message_payload(text, data),
            headers={"A2A-Version": A2A_VERSION},
        )
        if response.status_code != 200:
            raise NasikoError(f"agent call failed with HTTP {response.status_code}")
        body = response.json()
        if "error" in body:
            raise NasikoError(f"agent returned an error: {body['error']}")
        return parse_task(body["result"])

    def route_message(self, text: str) -> A2AReply:
        """Let Nasiko's routing engine pick the agent and answer."""
        response = self._request(
            "POST",
            "/api/orchestrator/a2a",
            json=message_payload(text),
            headers={"A2A-Version": A2A_VERSION},
        )
        if response.status_code != 200:
            raise NasikoError(f"routing call failed with HTTP {response.status_code}")
        return parse_event_stream(response.text)
