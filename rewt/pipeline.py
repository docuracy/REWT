"""Stages, declared inputs and outputs, and the fingerprints that make them cache.

PLAN.md §2 asks for four things this module supplies:

* **Declare stage inputs and outputs so the order is enforced, not remembered.**
  In the earlier work one stage rebuilt a table another had written columns into;
  running them in the wrong order produced a plausible network with stale values.
* **Every stage is idempotent** — it clears what it wrote before writing it.
* **No cached intermediate is ever preferred to the configuration that produced it
  without a recorded fingerprint of that configuration.** A corrected setting once
  sat unused for a month behind a cached raster, and nothing said so.
* **The audit is part of the build**, not a script someone remembers to run.

A stage's fingerprint covers its own source code, the parameters it declares it
reads, the sources it declares it reads, and the fingerprints of the stages upstream
of it. Change any of those and the cache is not used.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import inspect
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from . import config, db, paths
from .report import log


class StageError(RuntimeError):
    """A stage could not run, or ran and found the world not as declared."""


@dataclass(frozen=True)
class Artefact:
    """Something a stage produces: a database table, or a file on disk."""

    name: str
    kind: str = "table"          # "table" | "file" | "dir"
    path: str | None = None      # for file/dir, relative to the repository root

    def exists(self) -> bool:
        if self.kind == "table":
            return db.table_exists(self.name)
        target = paths.ROOT / (self.path or self.name)
        if self.kind == "dir":
            return target.is_dir() and any(target.iterdir())
        return target.exists()

    def describe(self) -> str:
        if self.kind == "table":
            return f"table {self.name} ({db.count(self.name):,} rows)"
        return f"{self.kind} {self.path or self.name}"


_ARTEFACTS: dict[str, Artefact] = {}


def artefact(name: str, kind: str = "table", path: str | None = None) -> Artefact:
    """Declare an artefact once; every stage refers to it by name."""
    existing = _ARTEFACTS.get(name)
    if existing is not None:
        if existing.kind != kind or existing.path != path:
            raise StageError(f"artefact {name!r} redeclared with different definition")
        return existing
    art = Artefact(name=name, kind=kind, path=path)
    _ARTEFACTS[name] = art
    return art


# ---------------------------------------------------------------- module reach
# What a stage can reach, so that its fingerprint can cover it. Read from the
# source text rather than from `sys.modules`, because an import that has not
# happened yet in this process is still an import the stage depends on.

_PACKAGE = __name__.split(".")[0]


@functools.lru_cache(maxsize=None)
def _module_file(name: str) -> Path | None:
    rel = Path(*name.split("."))
    for candidate in (rel.with_suffix(".py"), rel / "__init__.py"):
        path = paths.ROOT / candidate
        if path.is_file():
            return path
    return None


@functools.lru_cache(maxsize=None)
def _module_digest(name: str) -> str:
    path = _module_file(name)
    if path is None:
        return "absent"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@functools.lru_cache(maxsize=None)
def _direct_imports(name: str) -> tuple[str, ...]:
    """The `rewt.*` modules this module imports, relative imports resolved."""
    path = _module_file(name)
    if path is None:
        return ()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:                                  # pragma: no cover
        raise StageError(f"cannot parse {paths.rel(path)} to fingerprint it: {exc}")

    parts = name.split(".")
    package = parts[:-1] if _module_file(name) and path.name != "__init__.py" else parts
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == _PACKAGE:
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1]
                target = base + ([node.module] if node.module else [])
            elif node.module and node.module.split(".")[0] == _PACKAGE:
                target = node.module.split(".")
            else:
                continue
            stem = ".".join(target)
            if not stem or stem.split(".")[0] != _PACKAGE:
                continue
            found.add(stem)
            # `from . import db, graph` names modules, not attributes.
            for alias in node.names:
                child = f"{stem}.{alias.name}"
                if _module_file(child) is not None:
                    found.add(child)
    return tuple(sorted(found))


@functools.lru_cache(maxsize=None)
def _reachable_modules(name: str) -> tuple[str, ...]:
    """`name` and everything it transitively imports inside the package."""
    seen: set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        if current in seen or _module_file(current) is None:
            continue
        seen.add(current)
        stack.extend(_direct_imports(current))
    return tuple(sorted(seen))


@dataclass
class Stage:
    """One step of the build, with what it reads and what it writes declared."""

    name: str
    summary: str
    fn: Callable[..., dict | None]
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    params: tuple[str, ...] = ()      # dotted paths in conf/params.yml
    sources: tuple[str, ...] = ()     # ids in conf/sources.yml
    cacheable: bool = True
    always: bool = False              # runs every build regardless of cache (the audit)

    def source_hash(self) -> str:
        """The stage's own body **and every project module it can reach.**

        The narrow version of this — hashing only `inspect.getsource(self.fn)` —
        was wrong, and wrong in the way that does not announce itself. A stage
        function is a few lines that call into `ids`, `graph`, `topology`,
        `curated`, `schema`. Rewrite any of those and the stage's own text is
        unchanged, so its fingerprint is unchanged, so the build serves the
        artefact the *previous* code produced and reports success.

        It happened. `ids.publisher` was changed from `os:link:{id}` to
        `os:link/{id}` — one character, deliberate, so that a CURIE expands by
        concatenation onto a URI w3id actually routes. No stage's fingerprint
        moved. The database kept 195,689 links and 198,457 nodes identified in a
        scheme the code on disk no longer produces, and `rewt build` exited 0 with
        every figure intact. Only a unit test comparing `ids` against a literal
        caught it, and only because it imports the module directly rather than
        reading the database.

        So the fingerprint now covers the transitive closure of `rewt.*` imports
        from the module the stage is defined in. It is deliberately coarse: a
        change to `db.py` rebuilds nearly everything, because nearly everything
        imports it. That is the right direction to be wrong in. A rebuild that
        was not needed costs an hour; a cached artefact built by code that no
        longer exists costs the reproducibility guarantee §2 is built on, and
        costs it silently.
        """
        try:
            src = inspect.getsource(self.fn)
        except (OSError, TypeError):
            src = self.fn.__qualname__
        payload = [src]
        for name in _reachable_modules(self.fn.__module__):
            payload.append(f"{name}\n{_module_digest(name)}")
        return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()[:16]

    def config_slice(self) -> dict:
        p = config.params()
        return {
            "params": {path: p(path, None) for path in sorted(self.params)},
            "sources": {
                sid: config.source(sid).raw for sid in sorted(self.sources)
            },
        }

    def fingerprint(self, upstream: dict[str, str]) -> str:
        payload = {
            "stage": self.name,
            "code": self.source_hash(),
            "config": self.config_slice(),
            "upstream": {k: upstream[k] for k in sorted(upstream)},
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]


class Pipeline:
    """The registry. Order comes from the declarations, not from memory."""

    def __init__(self) -> None:
        self._stages: dict[str, Stage] = {}
        self._order: list[str] = []

    def add(self, stage: Stage) -> Stage:
        if stage.name in self._stages:
            raise StageError(f"stage {stage.name!r} registered twice")
        for source_id in stage.sources:
            declared_stage = config.source(source_id).get("stage", default=1)
            if declared_stage != 1:
                raise StageError(
                    f"stage {stage.name!r} declares source {source_id!r}, which "
                    f"conf/sources.yml marks as stage {declared_stage}. **Stage 1 and "
                    "nothing else** (AGENTS.md): the failure mode is not refusing this "
                    "outright, it is drifting into it a little at a time because a "
                    "field looked easy to add. A source may be registered for a later "
                    "stage or for the documentation; it may not be read by this build."
                )
        for art in stage.writes:
            producer = self.producer_of(art)
            if producer is not None:
                raise StageError(
                    f"artefact {art!r} is written by both {producer} and {stage.name}. "
                    "Two stages writing one table is how stale values arrive."
                )
        self._stages[stage.name] = stage
        self._order.append(stage.name)
        return stage

    def stage(
        self,
        name: str,
        summary: str,
        *,
        reads: Iterable[str] = (),
        writes: Iterable[str] = (),
        params: Iterable[str] = (),
        sources: Iterable[str] = (),
        cacheable: bool = True,
        always: bool = False,
    ):
        """Decorator form: `@pipeline.stage("load", ..., writes=["link"])`."""

        def wrap(fn):
            self.add(
                Stage(
                    name=name,
                    summary=summary,
                    fn=fn,
                    reads=tuple(reads),
                    writes=tuple(writes),
                    params=tuple(params),
                    sources=tuple(sources),
                    cacheable=cacheable,
                    always=always,
                )
            )
            return fn

        return wrap

    # -- introspection ----------------------------------------------------
    def producer_of(self, artefact_name: str) -> str | None:
        for st in self._stages.values():
            if artefact_name in st.writes:
                return st.name
        return None

    def __getitem__(self, name: str) -> Stage:
        try:
            return self._stages[name]
        except KeyError:
            raise StageError(
                f"no stage {name!r}. Known: {', '.join(self._order)}"
            ) from None

    def __contains__(self, name: object) -> bool:
        return name in self._stages

    @property
    def names(self) -> list[str]:
        return list(self._order)

    def dependencies(self, name: str) -> list[str]:
        """Stages that must have run before this one, in order, deduplicated."""
        seen: list[str] = []

        def walk(n: str, trail: tuple[str, ...] = ()) -> None:
            if n in trail:
                raise StageError(f"stage cycle: {' -> '.join(trail + (n,))}")
            st = self[n]
            for art in st.reads:
                producer = self.producer_of(art)
                if producer is None:
                    if art not in _ARTEFACTS:
                        raise StageError(
                            f"stage {n!r} reads undeclared artefact {art!r}"
                        )
                    continue  # supplied from outside the pipeline (e.g. curated files)
                if producer != n:
                    walk(producer, trail + (n,))
            if n not in seen:
                seen.append(n)

        walk(name)
        return seen

    def plan(self, targets: Iterable[str] | None = None) -> list[str]:
        """The stages to run, in dependency order."""
        targets = list(targets) if targets else self.names
        order: list[str] = []
        for t in targets:
            for n in self.dependencies(t):
                if n not in order:
                    order.append(n)
        return order


PIPELINE = Pipeline()


# --------------------------------------------------------------------------
# The run ledger. It lives in the database because it describes the database.
# --------------------------------------------------------------------------

_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS stage_run (
    stage               VARCHAR NOT NULL,
    fingerprint         VARCHAR NOT NULL,
    config_fingerprint  VARCHAR NOT NULL,
    status              VARCHAR NOT NULL,
    started_at          TIMESTAMP NOT NULL,
    seconds             DOUBLE,
    detail              VARCHAR,
    PRIMARY KEY (stage)
)
"""


def ensure_ledger() -> None:
    db.get().execute(_LEDGER_DDL)


def recorded_fingerprint(stage_name: str) -> str | None:
    ensure_ledger()
    return db.scalar(
        "SELECT fingerprint FROM stage_run WHERE stage = ? AND status = 'ok'",
        [stage_name],
    )


def record(stage_name: str, fp: str, status: str, seconds: float, detail: dict) -> None:
    ensure_ledger()
    db.get().execute("DELETE FROM stage_run WHERE stage = ?", [stage_name])
    db.get().execute(
        "INSERT INTO stage_run VALUES (?, ?, ?, ?, current_timestamp, ?, ?)",
        [
            stage_name,
            fp,
            config.config_fingerprint(),
            status,
            seconds,
            json.dumps(detail, default=str, sort_keys=True),
        ],
    )


def invalidate(stage_name: str) -> None:
    ensure_ledger()
    db.get().execute("DELETE FROM stage_run WHERE stage = ?", [stage_name])


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


def run(
    targets: Iterable[str] | None = None,
    *,
    force: bool = False,
    force_all: bool = False,
    dry_run: bool = False,
) -> dict[str, dict]:
    """Run the stages needed for `targets`, in declared order.

    A stage is skipped only when its fingerprint matches the recorded one *and*
    every artefact it writes still exists. Nothing else licenses a skip.
    """
    paths.check_root()
    paths.ensure_dirs()
    ensure_ledger()

    order = PIPELINE.plan(targets)
    requested = set(targets) if targets else set(order)
    upstream_fps: dict[str, str] = {}
    results: dict[str, dict] = {}

    if dry_run:
        log.rule("build plan")
        for name in order:
            st = PIPELINE[name]
            log.info(f"  {name:<16} {st.summary}")
            if st.reads:
                log.detail(f"      reads  {', '.join(st.reads)}")
            if st.writes:
                log.detail(f"      writes {', '.join(st.writes)}")
        return {}

    for name in order:
        st = PIPELINE[name]
        deps = {
            d: upstream_fps[d]
            for d in PIPELINE.dependencies(name)
            if d != name and d in upstream_fps
        }
        fp = st.fingerprint(deps)
        upstream_fps[name] = fp

        writes = [_ARTEFACTS[w] for w in st.writes if w in _ARTEFACTS]
        have_outputs = all(a.exists() for a in writes) if writes else False
        recorded = recorded_fingerprint(name)
        must_force = force_all or (force and name in requested)

        if (
            st.cacheable
            and not st.always
            and not must_force
            and recorded == fp
            and have_outputs
        ):
            log.skip(f"{name}: unchanged (fingerprint {fp})")
            results[name] = {"status": "cached", "fingerprint": fp}
            continue

        # Reads must exist before the stage runs. Order is enforced, not remembered.
        missing = [
            r
            for r in st.reads
            if r in _ARTEFACTS and not _ARTEFACTS[r].exists()
        ]
        if missing:
            raise StageError(
                f"stage {name!r} reads {', '.join(missing)}, which do not exist. "
                f"Produced by: "
                + ", ".join(
                    f"{m}<-{PIPELINE.producer_of(m) or 'nothing declared'}"
                    for m in missing
                )
            )

        log.rule(f"{name} — {st.summary}")
        started = time.time()
        try:
            detail = st.fn() or {}
        except Exception as exc:  # fail loudly; record the failure
            record(name, fp, "failed", time.time() - started, {"error": str(exc)})
            db.vacuum()
            raise
        seconds = time.time() - started

        still_missing = [a.name for a in writes if not a.exists()]
        if still_missing:
            record(name, fp, "failed", seconds, {"missing": still_missing})
            raise StageError(
                f"stage {name!r} finished without writing {', '.join(still_missing)}"
            )

        record(name, fp, "ok", seconds, detail)
        db.vacuum()
        log.done(f"{name} in {seconds:,.1f}s")
        for a in writes:
            log.detail(f"    {a.describe()}")
        results[name] = {"status": "ok", "fingerprint": fp, "seconds": seconds, **detail}

    return results
