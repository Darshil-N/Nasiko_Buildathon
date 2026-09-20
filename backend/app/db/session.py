"""Database sessions.

Reads and writes use deliberately different dependencies. ``get_read_session`` opens every
transaction as READ ONLY, so an endpoint that only reads can never change data by mistake
(rule 2: no database change without approval). Write paths will get their own, explicitly
named dependency when they are built.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from backend.app.core.settings import Settings


@lru_cache
def get_engine(url: str) -> Engine:
    """One pooled engine per database URL."""
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def get_read_session(request: Request) -> Iterator[Session]:
    """A session whose transactions are READ ONLY."""
    settings: Settings = request.app.state.settings
    engine = get_engine(settings.database_url).execution_options(postgresql_readonly=True)
    with Session(engine) as session:
        yield session
