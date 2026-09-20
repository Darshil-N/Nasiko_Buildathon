"""Deploy one SiteScout agent to Nasiko and optionally smoke-test it.

    python -m scripts.deploy_agent hello_world --smoke "What makes a good pharmacy site?"
    python -m scripts.deploy_agent scoring --include agent_base=agents/_shared

Credentials come from NASIKO_BASE_URL / NASIKO_USERNAME / NASIKO_PASSWORD, or (local dev only)
from a Nasiko ``.env`` file via ``--nasiko-env-file``. Secrets are never printed.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from backend.app.services.nasiko_client import A2AReply, NasikoClient
from scripts.agent_packaging import load_card, package_agent

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
AGENTS_ROOT = Path("agents")


def read_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (comments and blank lines are ignored)."""
    text = path.read_text(encoding="utf-8")
    return {k: v.strip() for k, v in re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", text, re.M)}


def client_from_environment(env_file: Path | None = None) -> NasikoClient:
    """Build a client from environment variables, or from a Nasiko ``.env`` file."""
    if env_file is not None:
        values = read_env_file(env_file)
        username, password = values.get("ADMIN_USERNAME"), values.get("ADMIN_PASSWORD")
        base = os.environ.get("NASIKO_BASE_URL", DEFAULT_BASE_URL)
    else:
        username, password = os.environ.get("NASIKO_USERNAME"), os.environ.get("NASIKO_PASSWORD")
        base = os.environ.get("NASIKO_BASE_URL", DEFAULT_BASE_URL)
    if not username or not password:
        raise SystemExit("Nasiko credentials not found (NASIKO_USERNAME / NASIKO_PASSWORD).")
    return NasikoClient(base, username, password)


def parse_includes(values: list[str]) -> dict[str, Path]:
    """Turn ``name=path`` arguments into a mapping."""
    result: dict[str, Path] = {}
    for item in values:
        name, sep, path = item.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"--include expects name=path, got {item!r}")
        result[name] = Path(path)
    return result


def deploy(
    agent: str,
    client: NasikoClient,
    *,
    shared: Mapping[str, Path] | None = None,
    smoke: str | None = None,
    agents_root: Path = AGENTS_ROOT,
    out: Callable[[str], None] = print,
) -> A2AReply | None:
    """Package, upload and build ``agent``; return the smoke-test reply if one was requested."""
    agent_dir = agents_root / agent
    card = load_card(agent_dir)
    archive = package_agent(agent_dir, shared)
    out(f"packaged {agent} ({len(archive):,} bytes) as '{card['name']}' v{card['version']}")
    ticket = client.upload_agent(str(card["name"]), archive)
    out(f"uploaded; building (build {ticket.build_id})")
    status = client.wait_for_build(ticket.build_id)
    out(f"build {status.status}: {status.message}")
    if smoke is None:
        return None
    reply = client.send_message(ticket.agent_id, smoke)
    out(f"smoke test state={reply.state}: {reply.text[:300]}")
    return reply


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy a SiteScout agent to Nasiko")
    parser.add_argument("agent", help="folder name under agents/, for example hello_world")
    parser.add_argument("--smoke", help="send this message after the build and print the reply")
    parser.add_argument("--include", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--nasiko-env-file", type=Path, help="read admin credentials from it")
    args = parser.parse_args(argv)
    client = client_from_environment(args.nasiko_env_file)
    reply = deploy(args.agent, client, shared=parse_includes(args.include), smoke=args.smoke)
    return 0 if reply is None or reply.completed else 1


if __name__ == "__main__":
    sys.exit(main())
