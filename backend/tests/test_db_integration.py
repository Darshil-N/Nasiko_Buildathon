"""Read-only checks against the real SiteScout database (marker: integration).

Run explicitly:
DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5433/sitescout pytest -m integration

Every statement here is a SELECT or SHOW; nothing in the database is created or changed.
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db import models  # noqa: F401  (registers every table on Base.metadata)
from backend.app.db.base import Base
from backend.app.db.repositories import list_ready_cities
from backend.app.db.session import get_engine

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.fixture
def read_session() -> Iterator[Session]:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is not set")
    engine = get_engine(DATABASE_URL).execution_options(postgresql_readonly=True)
    with Session(engine) as session:
        yield session


def test_read_session_is_really_read_only(read_session: Session) -> None:
    assert read_session.execute(text("SHOW transaction_read_only")).scalar_one() == "on"


def test_live_tables_and_columns_match_the_models(read_session: Session) -> None:
    rows = read_session.execute(
        text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )
    ).all()
    live: dict[str, set[str]] = defaultdict(set)
    for table, column in rows:
        live[table].add(column)
    for name, table in Base.metadata.tables.items():
        assert name in live, f"table {name} is missing from the database"
        assert live[name] == {c.name for c in table.columns}, f"columns differ in {name}"


def test_postgis_is_installed(read_session: Session) -> None:
    assert str(read_session.execute(text("SELECT postgis_version()")).scalar_one()).startswith("3")


def test_ready_cities_query_runs(read_session: Session) -> None:
    assert isinstance(list_ready_cities(read_session), list)
