"""Package an agent directory into the zip Nasiko builds (plan steps 5.4.1, 5.4.2).

Layout of the zip (what Nasiko expects, and what each Dockerfile's ``COPY src/ /app`` uses)::

    AgentCard.json
    Dockerfile
    src/...                 the agent's own code
    src/<name>/...          optional shared packages copied in (for example ``agent_base``)
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REQUIRED_FILES = ("AgentCard.json", "Dockerfile")
EXCLUDED_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})


class PackagingError(ValueError):
    """The agent directory cannot be packaged; the message says what to fix."""


def load_card(agent_dir: Path) -> dict[str, Any]:
    """Read and minimally validate ``AgentCard.json``."""
    path = agent_dir / "AgentCard.json"
    if not path.exists():
        raise PackagingError(f"{agent_dir}: AgentCard.json is missing")
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackagingError(f"{path}: not valid JSON ({exc})") from exc
    for key in ("name", "version", "skills"):
        if not card.get(key):
            raise PackagingError(f"{path}: '{key}' is missing or empty")
    return dict(card)


def _files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and not (set(p.relative_to(root).parts) & EXCLUDED_PARTS)
        and p.suffix not in EXCLUDED_SUFFIXES
        and p.name != ".gitkeep"
    )


def package_agent(agent_dir: Path, shared: Mapping[str, Path] | None = None) -> bytes:
    """Build the zip for ``agent_dir``, copying each ``shared`` package into ``src/<name>/``.

    Raises:
        PackagingError: for a missing card, Dockerfile or ``src/``, or a file-name clash.
    """
    load_card(agent_dir)
    for required in REQUIRED_FILES:
        if not (agent_dir / required).is_file():
            raise PackagingError(f"{agent_dir}: {required} is missing")
    src = agent_dir / "src"
    if not src.is_dir() or not _files(src):
        raise PackagingError(f"{agent_dir}: src/ is missing or empty")

    entries: dict[str, Path] = {name: agent_dir / name for name in REQUIRED_FILES}
    for path in _files(src):
        entries[f"src/{path.relative_to(src).as_posix()}"] = path
    for name, package_dir in (shared or {}).items():
        if not package_dir.is_dir():
            raise PackagingError(f"shared package {name!r}: {package_dir} is not a directory")
        for path in _files(package_dir):
            if path.suffix != ".py":
                continue
            target = f"src/{name}/{path.relative_to(package_dir).as_posix()}"
            if target in entries:
                raise PackagingError(f"file name clash inside the zip: {target}")
            entries[target] = path
        entries.setdefault(f"src/{name}/__init__.py", _EMPTY)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for target, path in sorted(entries.items()):
            if path is _EMPTY:
                archive.writestr(target, "")
            else:
                archive.write(path, target)
    return buffer.getvalue()


_EMPTY = Path("<empty>")  # marker for a generated empty __init__.py
