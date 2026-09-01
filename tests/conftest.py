"""Fixtures for the build's own tests.

Two things this file exists to get right.

**The database is a build artefact, not a source of truth** (AGENTS.md), so a test
that needs it must say so, and must say what is missing when it is not there. Nothing
here fails because the build has not run; it skips, and **every skip is named** — a
silent skip is the failure mode this repository has been bitten by twice.

**A read-only DuckDB connection blocks writers** (AGENTS.md). So the `con` fixture
prefers a connection the process already holds — which is the case under
`rewt check`, where the build has just run in this same process — and only opens its
own when there is none. A lock held by another process is a skip, not a failure: it
means someone is building, and a test suite that broke their build to report on it
would be worse than useless.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Everything runs from the repository root and paths in code are relative (AGENTS.md).
# Under `pytest tests/` the root is not otherwise on the path.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rewt import db, paths  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "db: needs the build database")
    config.addinivalue_line("markers", "interim: reads a derived raster under data/interim/")
    config.addinivalue_line(
        "markers", "published: reads published/ only, so it holds no database lock"
    )


@pytest.fixture(scope="session")
def con():
    """A connection to the build database, or a named skip.

    `db.current()` and not `db.get()`: `get()` opens a connection when there is
    none, and a read-only DuckDB connection blocks writers, so a suite that opened
    one speculatively could deadlock the build it meant to inspect.
    """
    existing = db.current()
    if existing is not None:
        yield existing            # the build's own connection, under `rewt check`
        return

    if not paths.DB_PATH.exists():
        pytest.skip(
            f"{paths.rel(paths.DB_PATH)} does not exist. "
            "These checks describe a built database; run `rewt build` first."
        )
    try:
        connection = db.connect(read_only=True)
    except Exception as exc:                      # a writer holds the exclusive lock
        pytest.skip(
            f"could not open {paths.rel(paths.DB_PATH)} read-only ({exc}). "
            "A build is probably running: a read-only DuckDB connection blocks "
            "writers, so this is a skip and not a failure."
        )
    # The build's own helpers — `curated.resolve()` among them — reach the database
    # through `db.get()`, which opens a connection of its own when the thread has
    # none. DuckDB refuses a second connection to one file under a different
    # configuration, so that call fails against the read-only one opened here.
    #
    # Inside `rewt check` the question does not arise: the build's connection is
    # already installed and `db.get()` returns it. Standalone, this fixture has to
    # install the connection it opened, and there is no public way to say so.
    #
    # NOTE for rewt/db.py's owner: a `db.adopt(con)` — or a context manager, which
    # would be better — would replace this. It is deliberately narrow: read-only,
    # restored on the way out, and never left installed for another test session.
    db._local.con = connection
    try:
        yield connection
    finally:
        db._local.con = None
        connection.close()


def table_names(con) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }


def require_tables(con, *names: str) -> None:
    """Skip, naming what is missing. Never skip without saying what and why."""
    missing = sorted(set(names) - table_names(con))
    if missing:
        pytest.skip(
            f"the database has no {', '.join(missing)}. "
            f"Present: {', '.join(sorted(table_names(con))) or 'nothing'}. "
            "Run `rewt build` for the checks that describe a built network."
        )


@pytest.fixture(scope="session")
def curated_judgements():
    """Every curated judgement, read from the files. Independent of the database."""
    from rewt import curated

    return curated.read_all()
