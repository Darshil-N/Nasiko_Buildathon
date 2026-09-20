"""Alembic environment.

The URL comes from the DATABASE_URL environment variable only. Offline mode (``--sql``)
renders the SQL without connecting to any database, which is how migrations are reviewed.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from backend.app.db import models  # noqa: F401  (registers every table on Base.metadata)
from backend.app.db.base import Base

target_metadata = Base.metadata
config = context.config

# Placeholder used only to pick the PostgreSQL dialect when rendering SQL offline.
OFFLINE_URL = "postgresql+psycopg://offline:offline@localhost/offline"


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; refusing to guess a database to migrate")
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database."""
    context.configure(
        url=OFFLINE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the database named by DATABASE_URL (approval required)."""
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
