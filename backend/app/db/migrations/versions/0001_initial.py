"""Initial SiteScout schema (architecture section 8.2 with the deviations listed in the SQL).

The exact SQL lives in ../sql/ so it can be reviewed as plain text before anything runs.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _run(name: str) -> None:
    op.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def upgrade() -> None:
    _run("0001_initial_upgrade.sql")


def downgrade() -> None:
    _run("0001_initial_downgrade.sql")
