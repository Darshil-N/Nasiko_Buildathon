"""Package an agent directory into the zip Nasiko builds (plan steps 5.4.1, 5.4.2).

Layout of the zip (what Nasiko expects, and what each Dockerfile's ``COPY src/ /app`` uses)::

    AgentCard.json
    Dockerfile
    src/...                 the agent's own code
    src/<name>/...          optional shared code packages copied in (for example ``agent_base``);
                             only ``.py`` files are copied, and a package always gets an
                             ``__init__.py``
    src/<name>/...          optional data directories copied in verbatim (for example category
                             config YAMLs), passed separately via ``data`` so a stray non-Python
                             file in a code package is still caught as a mistake
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


def _add_tree(
    entries: dict[str, Path],
    name: str,
    source_dir: Path,
    *,
    only_py: bool,
) -> None:
    if not source_dir.is_dir():
        kind = "shared package" if only_py else "data directory"
        raise PackagingError(f"{kind} {name!r}: {source_dir} is not a directory")
    for path in _files(source_dir):
        if only_py and path.suffix != ".py":
            continue
        target = f"src/{name}/{path.relative_to(source_dir).as_posix()}"
        if target in entries:
            raise PackagingError(f"file name clash inside the zip: {target}")
        entries[target] = path
    if only_py:
        entries.setdefault(f"src/{name}/__init__.py", _EMPTY)


def package_agent(
    agent_dir: Path,
    shared: Mapping[str, Path] | None = None,
    data: Mapping[str, Path] | None = None,
) -> bytes:
    """Build the zip for ``agent_dir``.

    Each ``shared`` package is copied (``.py`` files only, plus a generated ``__init__.py``) into
    ``src/<name>/``. Each ``data`` directory is copied verbatim (every file) into ``src/<name>/``,
    for non-code assets a package needs at runtime, such as category config YAMLs.

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
        _add_tree(entries, name, package_dir, only_py=True)
    for name, data_dir in (data or {}).items():
        _add_tree(entries, name, data_dir, only_py=False)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for target, path in sorted(entries.items()):
            if path is _EMPTY:
                archive.writestr(target, "")
            else:
                archive.write(path, target)
    return buffer.getvalue()


_EMPTY = Path("<empty>")  # marker for a generated empty __init__.py
