"""Static drift check: the ORM models must describe exactly the tables and columns in the SQL.

No database is contacted; the SQL file is parsed as text.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.db import models  # noqa: F401  (registers every table on Base.metadata)
from backend.app.db.base import Base

SQL_PATH = Path("backend/app/db/migrations/sql/0001_initial_upgrade.sql")
_CONSTRAINT_KEYWORDS = frozenset({"PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"})


def parse_sql_tables(sql: str) -> dict[str, set[str]]:
    """Return {table: {column names}} from the CREATE TABLE statements."""
    without_comments = re.sub(r"--[^\n]*", "", sql)
    tables: dict[str, set[str]] = {}
    for match in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", without_comments, flags=re.DOTALL):
        name, body = match.group(1), match.group(2)
        columns: set[str] = set()
        depth = 0
        current = ""
        # split the body on top-level commas so "CHECK (a, b)" or NUMERIC(5, 4) stay intact
        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                columns.add(current.strip())
                current = ""
            else:
                current += ch
        columns.add(current.strip())
        tables[name] = {
            item.split()[0]
            for item in columns
            if item and item.split()[0].upper() not in _CONSTRAINT_KEYWORDS
        }
    return tables


def test_orm_tables_match_the_sql() -> None:
    sql_tables = parse_sql_tables(SQL_PATH.read_text(encoding="utf-8"))
    orm_tables = {name: {c.name for c in t.columns} for name, t in Base.metadata.tables.items()}
    assert set(orm_tables) == set(sql_tables), "table lists differ"
    for table, columns in sql_tables.items():
        assert orm_tables[table] == columns, f"columns differ in {table}"


def test_deviation_columns_are_present() -> None:
    tables = Base.metadata.tables
    assert "key" in tables["cities"].c
    assert "category" in tables["cell_features"].c
    assert "ingest_jobs" in tables
    assert "scrape_jobs" not in tables
    assert "cell_attributes" in tables


def test_cell_features_primary_key_includes_category() -> None:
    pk = {c.name for c in Base.metadata.tables["cell_features"].primary_key.columns}
    assert pk == {"h3_index", "category", "feature_version"}
