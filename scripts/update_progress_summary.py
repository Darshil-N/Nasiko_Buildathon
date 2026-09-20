"""Refresh the summary block of progress.md from its checkboxes.

Counts parts, steps and micro-tasks per phase, plus decision statuses, and rewrites only the
text between the SUMMARY-START and SUMMARY-END markers. Run from the repository root:

    python scripts/update_progress_summary.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

PROGRESS = Path("progress.md")
DOT = "·"
DECISION_ORDER = ["open", "partly answered", "proposed", "answered", "deferred", "closed"]
DECISION_LABELS = {"proposed": "proposed (awaiting your confirmation)"}


def phase_rows(text: str) -> list[tuple[int, str, int, int, int, int]]:
    """Return (phase, name, parts, steps, micro_tasks, done) for every phase section."""
    names = {int(m.group(1)): m.group(2) for m in re.finditer(r"^## Phase (\d): (.+)$", text, re.M)}
    chunks = re.split(r"^## Phase (\d): .+$", text, flags=re.M)
    rows = []
    for i in range(1, len(chunks), 2):
        phase = int(chunks[i])
        body = chunks[i + 1].split("\n## 7. Change log")[0]
        parts = len(re.findall(r"^### Part", body, re.M))
        steps = len(re.findall(r"^\*\*\d+\.\d+\.\d+ ", body, re.M))
        done = len(re.findall(r"^- \[x\]", body, re.M))
        tasks = done + len(re.findall(r"^- \[[ ~!]\]", body, re.M))
        rows.append((phase, names[phase], parts, steps, tasks, done))
    return rows


def decision_counts(text: str) -> Counter[str]:
    """Count decision rows by status (the fourth cell of each `| D-nn |` row)."""
    counts: Counter[str] = Counter()
    for m in re.finditer(r"^\| D-\d+ \|(.*)$", text, re.M):
        cells = [c.strip() for c in ("|" + m.group(1)).split("|")]
        counts[cells[3]] += 1
    return counts


def build_block(text: str) -> str:
    rows = phase_rows(text)
    totals = [sum(r[i] for r in rows) for i in (2, 3, 4, 5)]
    lines = [
        "| Phase | Name | Parts | Steps | Micro-tasks | Done | Progress | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for phase, name, parts, steps, tasks, done in rows:
        status = "not started" if done == 0 else ("done" if done == tasks else "in progress")
        lines.append(
            f"| {phase} | {name} | {parts} | {steps} | {tasks} | {done} "
            f"| {round(100 * done / tasks)}% | {status} |"
        )
    pct = round(100 * totals[3] / totals[2])
    lines.append(
        f"| | **Total** | **{totals[0]}** | **{totals[1]}** | **{totals[2]}** "
        f"| **{totals[3]}** | **{pct}%** | |"
    )
    counts = decision_counts(text)
    decisions = f" {DOT} ".join(
        f"{counts[s]} {DECISION_LABELS.get(s, s)}" for s in DECISION_ORDER if counts[s]
    )
    lines += ["", f"Decisions ({sum(counts.values())} total): {decisions}"]
    return "\n".join(lines)


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")
    block = build_block(text)
    new_text, n = re.subn(
        r"(<!-- SUMMARY-START -->\n).*?(\n<!-- SUMMARY-END -->)",
        lambda m: m.group(1) + block + m.group(2),
        text,
        flags=re.S,
    )
    if n != 1:
        sys.stderr.write("SUMMARY markers not found exactly once in progress.md\n")
        return 1
    PROGRESS.write_text(new_text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(block + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
