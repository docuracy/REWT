"""The one module that owns the database connection.

Everything else asks it for one (AGENTS.md). This is what keeps a move to PostGIS
cheap, and it is why there is one module and not six.

Two things worth knowing before reading further:

* **The database is a build artefact, not a source of truth.** It is gitignored,
  rebuilt from scratch and never hand-edited. The sources of truth are `data/raw/`
  (immutable, checksummed) and `data/curated/` (hand-authored, committed).
* **A read-only DuckDB connection blocks writers.** Anything long-running that holds
  one — a viewer, a served map, a notebook — must be stopped before a build.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any, Iterable, Iterator, Sequence

import duckdb

from . import paths

_local = threading.local()

# Loaded once per process. INSTALL reaches the network on a cold cache; LOAD does not.
_SPATIAL_READY = False


def _prepare(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    global _SPATIAL_READY
    if not _SPATIAL_READY:
        con.execute("INSTALL spatial")
        _SPATIAL_READY = True
    con.execute("LOAD spatial")
    # Deterministic ordering wherever a result depends on iteration order (PLAN.md §2).
    con.execute("SET preserve_insertion_order = true")
    con.execute("SET threads TO 8")
    return con


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """A connection to the build database, spatial extension loaded.

    Call `close()` when finished, or use `session()`.
    """
    paths.ensure_dirs()
    con = duckdb.connect(str(paths.DB_PATH), read_only=read_only)
    return _prepare(con)


def get() -> duckdb.DuckDBPyConnection:
    """The process-wide writable connection, opened on first use."""
    con = getattr(_local, "con", None)
    if con is None:
        con = connect()
        _local.con = con
    return con


def current() -> duckdb.DuckDBPyConnection | None:
    """The connection this thread already has, or None — never opening one.

    `get()` opens a connection if there is not one, which is right for a stage and
    wrong for anything that only wants to join an existing build: a read-only DuckDB
    connection blocks writers, so a caller that opens one speculatively can deadlock
    the build it meant to inspect. Tests and inspection tools ask here first.
    """
    return getattr(_local, "con", None)


def close() -> None:
    con = getattr(_local, "con", None)
    if con is not None:
        con.close()
        _local.con = None


@contextlib.contextmanager
def adopt(con: duckdb.DuckDBPyConnection) -> Iterator[duckdb.DuckDBPyConnection]:
    """Install a connection as this thread's, and put back what was there.

    For a caller that already holds a connection and wants the rest of the code to use
    it rather than open a second one. DuckDB refuses to open the same file twice with
    different settings, so a module reaching for `get()` under an existing read-only
    connection does not merely waste a handle — it raises. The restore is this
    function's job rather than the caller's, because a caller that forgets leaves the
    process pointing at a closed connection.
    """
    previous = getattr(_local, "con", None)
    _local.con = con
    try:
        yield con
    finally:
        _local.con = previous


@contextlib.contextmanager
def session(read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    """A scoped connection. Use this in scripts and tests; stages use `get()`."""
    con = connect(read_only=read_only)
    try:
        yield con
    finally:
        con.close()


# --------------------------------------------------------------------------
# Small conveniences, so that no other module reaches for duckdb directly.
# --------------------------------------------------------------------------


def execute(sql: str, params: Sequence[Any] | None = None) -> duckdb.DuckDBPyConnection:
    return get().execute(sql, params) if params is not None else get().execute(sql)


def query(sql: str, params: Sequence[Any] | None = None) -> list[tuple]:
    return execute(sql, params).fetchall()


def scalar(sql: str, params: Sequence[Any] | None = None) -> Any:
    row = execute(sql, params).fetchone()
    return None if row is None else row[0]


def df(sql: str, params: Sequence[Any] | None = None):
    """A pandas frame. Used for reporting, never in a per-row loop."""
    return execute(sql, params).df()


def table_exists(name: str) -> bool:
    return bool(
        scalar(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = ?",
            [name],
        )
    )


def columns(name: str) -> list[str]:
    return [
        r[0]
        for r in query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
            [name],
        )
    ]


def count(name: str, where: str = "") -> int:
    if not table_exists(name):
        return 0
    clause = f" WHERE {where}" if where else ""
    return int(scalar(f"SELECT count(*) FROM {name}{clause}") or 0)


def drop(*names: str) -> None:
    """Every stage clears what it wrote before writing it (PLAN.md §2).

    A stage that appends leaves the second run's output describing the first run's
    world.
    """
    con = get()
    for name in names:
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(f"DROP VIEW IF EXISTS {name}")


def register(name: str, frame) -> None:
    """Expose a pandas/pyarrow frame for a *bulk* insert.

    AGENTS.md: per-row inserts that parse geometry per row are pathological — ten
    minutes for 122,000 rows where a single bulk insert took moments. There is no
    per-row insert helper in this module on purpose.
    """
    get().register(name, frame)


def unregister(name: str) -> None:
    with contextlib.suppress(Exception):
        get().unregister(name)


@contextlib.contextmanager
def registered(name: str, frame) -> Iterator[str]:
    register(name, frame)
    try:
        yield name
    finally:
        unregister(name)


def vacuum() -> None:
    get().execute("CHECKPOINT")


def tables() -> list[str]:
    return [
        r[0]
        for r in query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        )
    ]


def summarise() -> list[tuple[str, int]]:
    return [(t, count(t)) for t in tables()]
