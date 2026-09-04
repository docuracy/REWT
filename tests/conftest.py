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


# --------------------------------------------------------------- standing failures
#
# **A STANDING FAILURE THAT GETS FIXED LEAVES A STALE RECORD, AND NOTHING CAUGHT THAT.**
#
# tests/README.md names the failures that are expected and what clears each, so that a
# reader can tell "red because the work is not done" from "red because something broke"
# — rewt-46's point, that a permanently red suite trains people to read the failure
# count as weather. It worked in the direction it was written for. It had no answer in
# the other direction: when D-079 was fixed and the build rebuilt, its row sat there
# claiming a rebuild would not clear it, and I only noticed because I happened to be
# editing the file for another reason.
#
# That is the same shape as the four stale comments this repository found in a day
# (D-091): a sentence describing the state of the tree, written by whoever had just
# measured it, going quietly false afterwards. The remedy is the one that worked
# everywhere else — do not write down what you saw, write down what to check — so the
# table is now a claim the suite tests rather than a note somebody maintains.
#
# It does NOT make a red run green. An expected failure still fails; this only adds the
# opposite direction, which nothing had: a listed test that PASSES fails the run until
# its row is removed. Deselected and skipped tests are ignored, because a run that did
# not reach a test has learnt nothing about it (D-082).

_STANDING_ROW = None  # set in pytest_configure, so parsing failure is reported once


def _standing_failures() -> set[str]:
    """The test ids tests/README.md declares as expected failures.

    Parsed from the table rather than duplicated into a second file: two renderings of
    one fact drift, and this file exists because one of them did (D-067).
    """
    import re

    readme = ROOT / "tests" / "README.md"
    if not readme.exists():
        return set()
    text = readme.read_text(encoding="utf-8")
    if "## Failures that are expected" not in text:
        return set()
    section = text.split("## Failures that are expected", 1)[1].split("\n## ", 1)[0]
    # The table writes ids as `test_x.py::test_y`, and pytest reports node ids as
    # `tests/test_x.py::test_y`. Accept either and normalise to the node id — the
    # first version of this required the prefix, matched nothing, and was caught by
    # the guard below rather than by me.
    found = set()
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        for m in re.finditer(r"`(?:tests/)?(test_[\w]+\.py::[\w\[\]\-.]+)`", line):
            found.add(f"tests/{m.group(1)}")
    return found


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "call" or (report.when == "setup" and report.skipped):
        _OUTCOMES[report.nodeid] = report.outcome


_OUTCOMES: dict[str, str] = {}


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run when a declared standing failure has started passing.

    The row is then wrong, and a wrong row is worse than no row: it is what a reader
    consults to decide whether a red line needs their attention.
    """
    declared = _standing_failures()
    section_exists = (
        (ROOT / "tests" / "README.md").exists()
        and "## Failures that are expected"
        in (ROOT / "tests" / "README.md").read_text(encoding="utf-8")
    )
    if section_exists and not declared:
        # The section is there and nothing was parsed out of it: the table's shape has
        # changed under a regex that then silently checks nothing.
        session.config.stash  # noqa: B018  (keep the import-free branch obvious)
        print(
            "\nSTANDING FAILURES: tests/README.md has the section and no row this "
            "could read. The check is looking at a table it no longer understands, "
            "which is a check that cannot reach its subject rather than one that "
            "passed."
        )
        session.exitstatus = session.exitstatus or 1
        return

    fixed = sorted(
        nodeid
        for nodeid in declared
        if _OUTCOMES.get(nodeid) == "passed"
    )
    if fixed:
        print(
            "\nSTANDING FAILURES THAT NOW PASS — the table in tests/README.md is "
            "out of date and says these are expected to fail:\n  "
            + "\n  ".join(fixed)
            + "\nRemove the row, and say in the commit what fixed it. A row claiming "
            "a failure that no longer happens is what a reader consults to decide "
            "whether a red line needs their attention."
        )
        session.exitstatus = session.exitstatus or 1
