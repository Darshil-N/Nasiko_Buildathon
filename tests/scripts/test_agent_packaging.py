"""Tests for agent packaging and the deploy flow (fake Nasiko client; no network)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from backend.app.services.nasiko_client import A2AReply, BuildStatus, UploadTicket
from scripts.agent_packaging import PackagingError, load_card, package_agent
from scripts.deploy_agent import deploy, parse_includes, read_env_file

CARD = {"name": "demo", "version": "0.1.0", "skills": [{"id": "s"}]}


def make_agent(root: Path, name: str = "demo", *, card: dict[str, Any] | None = None) -> Path:
    directory = root / name
    (directory / "src").mkdir(parents=True)
    (directory / "AgentCard.json").write_text(json.dumps(card or CARD), encoding="utf-8")
    (directory / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (directory / "src" / "__main__.py").write_text("print('hi')\n", encoding="utf-8")
    return directory


def names(archive: bytes) -> set[str]:
    return set(zipfile.ZipFile(io.BytesIO(archive)).namelist())


def test_real_hello_world_agent_packages() -> None:
    archive = package_agent(Path("agents/hello_world"))
    assert {"AgentCard.json", "Dockerfile", "src/__main__.py", "src/llm.py"} <= names(archive)
    assert not any("__pycache__" in n for n in names(archive))


def test_package_layout_and_exclusions(tmp_path: Path) -> None:
    agent = make_agent(tmp_path)
    (agent / "src" / "__pycache__").mkdir()
    (agent / "src" / "__pycache__" / "x.pyc").write_bytes(b"x")
    (agent / "src" / "helper.py").write_text("x = 1\n", encoding="utf-8")
    assert names(package_agent(agent)) == {
        "AgentCard.json",
        "Dockerfile",
        "src/__main__.py",
        "src/helper.py",
    }


def test_shared_packages_are_copied_under_src(tmp_path: Path) -> None:
    agent = make_agent(tmp_path)
    shared = tmp_path / "base"
    shared.mkdir()
    (shared / "runner.py").write_text("y = 2\n", encoding="utf-8")
    (shared / "notes.md").write_text("ignored", encoding="utf-8")
    archive = package_agent(agent, {"agent_base": shared})
    assert "src/agent_base/runner.py" in names(archive)
    assert "src/agent_base/__init__.py" in names(archive)
    assert "src/agent_base/notes.md" not in names(archive)


def test_data_directories_are_copied_verbatim_under_src(tmp_path: Path) -> None:
    agent = make_agent(tmp_path)
    config = tmp_path / "config"
    (config / "categories").mkdir(parents=True)
    (config / "categories" / "cafe.yaml").write_text("weights: {}\n", encoding="utf-8")
    archive = package_agent(agent, data={"config": config})
    assert "src/config/categories/cafe.yaml" in names(archive)
    assert "src/config/__init__.py" not in names(archive)  # not a code package


def test_shared_name_clash_is_rejected(tmp_path: Path) -> None:
    agent = make_agent(tmp_path)
    (agent / "src" / "base").mkdir()
    (agent / "src" / "base" / "runner.py").write_text("z = 3\n", encoding="utf-8")
    shared = tmp_path / "base"
    shared.mkdir()
    (shared / "runner.py").write_text("y = 2\n", encoding="utf-8")
    with pytest.raises(PackagingError, match="clash"):
        package_agent(agent, {"base": shared})


@pytest.mark.parametrize(
    ("break_it", "message"),
    [
        (lambda a: (a / "AgentCard.json").unlink(), "AgentCard.json is missing"),
        (lambda a: (a / "Dockerfile").unlink(), "Dockerfile is missing"),
        (lambda a: (a / "src" / "__main__.py").unlink(), "src/ is missing or empty"),
        (lambda a: (a / "AgentCard.json").write_text("{", encoding="utf-8"), "not valid JSON"),
        (
            lambda a: (a / "AgentCard.json").write_text('{"name": "x"}', encoding="utf-8"),
            "'version' is missing",
        ),
    ],
)
def test_broken_agents_are_rejected_with_a_clear_message(
    tmp_path: Path, break_it: Any, message: str
) -> None:
    agent = make_agent(tmp_path)
    break_it(agent)
    with pytest.raises(PackagingError, match=message):
        package_agent(agent)


def test_load_card_requires_skills(tmp_path: Path) -> None:
    agent = make_agent(tmp_path, card={"name": "x", "version": "1", "skills": []})
    with pytest.raises(PackagingError, match="'skills'"):
        load_card(agent)


class FakeClient:
    def __init__(self, reply_state: str = "TASK_STATE_COMPLETED") -> None:
        self.calls: list[tuple[str, Any]] = []
        self.reply_state = reply_state

    def upload_agent(self, name: str, zip_bytes: bytes) -> UploadTicket:
        self.calls.append(("upload", (name, len(zip_bytes))))
        return UploadTicket(agent_id="a1", build_id="b1")

    def wait_for_build(self, build_id: str) -> BuildStatus:
        self.calls.append(("wait", build_id))
        return BuildStatus("completed", "deployed")

    def send_message(self, agent_id: str, text: str) -> A2AReply:
        self.calls.append(("send", (agent_id, text)))
        return A2AReply(state=self.reply_state, text="an answer")


def test_deploy_runs_package_upload_wait_and_smoke_in_order(tmp_path: Path) -> None:
    make_agent(tmp_path)
    client = FakeClient()
    lines: list[str] = []
    reply = deploy(
        "demo",
        client,
        smoke="hello?",
        agents_root=tmp_path,
        out=lines.append,  # type: ignore[arg-type]
    )
    assert [c[0] for c in client.calls] == ["upload", "wait", "send"]
    assert client.calls[0][1][0] == "demo"  # named after the card, not the folder
    assert reply is not None
    assert reply.completed
    assert any("smoke test" in line for line in lines)


def test_deploy_without_smoke_does_not_send_a_message(tmp_path: Path) -> None:
    make_agent(tmp_path)
    client = FakeClient()
    assert deploy("demo", client, agents_root=tmp_path, out=lambda s: None) is None  # type: ignore[arg-type]
    assert [c[0] for c in client.calls] == ["upload", "wait"]


def test_data_directory_missing_is_rejected(tmp_path: Path) -> None:
    agent = make_agent(tmp_path)
    with pytest.raises(PackagingError, match="data directory"):
        package_agent(agent, data={"config": tmp_path / "missing"})


def test_parse_includes_and_env_file(tmp_path: Path) -> None:
    assert parse_includes(["agent_base=agents/_shared"]) == {"agent_base": Path("agents/_shared")}
    with pytest.raises(SystemExit):
        parse_includes(["broken"])
    env = tmp_path / ".env"
    env.write_text("# c\nADMIN_USERNAME=admin\nADMIN_PASSWORD=p=w\n\nOTHER=1\n", encoding="utf-8")
    values = read_env_file(env)
    assert values["ADMIN_USERNAME"] == "admin"
    assert values["ADMIN_PASSWORD"] == "p=w"  # noqa: S105  (parser test value, not a secret)
