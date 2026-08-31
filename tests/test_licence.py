"""Licensing, which is not a formality (AGENTS.md).

**This repository is private and is intended to become public.** Everything in it
must stay open and redistributable. Two independent things are checked here:

* the *declaration* — every source in `conf/sources.yml` carries a licence, the
  attribution it requires, and both of `access` and `redistribution`;
* the *gate* — the exporter refuses to write a feature whose source is not openly
  licensed, and still refuses when handed one that is not.

The gate is checked by constructing an encumbered source and watching it be refused.
Asserting only that today's six sources are open would pass just as well with the
check deleted.
"""

from __future__ import annotations

import pytest

from conftest import require_tables

from rewt import config
from rewt.config import Source, UnlicensedSource, UnregisteredSource


def _source(**overrides) -> Source:
    base = dict(
        id="test_source",
        title="A source invented by the test suite",
        publisher="nobody",
        licence="All rights reserved",
        attribution="none",
        access="open",
        redistribution="permitted",
        cache_path="data/raw/nowhere/",
    )
    base.update(overrides)
    return Source(**base)


# --------------------------------------------------------------------------
# The declaration
# --------------------------------------------------------------------------


def test_every_source_declares_a_licence_and_an_attribution():
    for src in config.sources():
        assert src.licence.strip(), f"source {src.id!r} declares no licence"
        assert src.attribution.strip(), (
            f"source {src.id!r} declares no attribution. Never add a source without "
            "recording its licence and required attribution first (AGENTS.md)."
        )


def test_every_declared_source_is_open_and_redistributable():
    """The repository is intended to become public.

    A source that is not both is not necessarily a bug — but it must never reach an
    export, and declaring one is a decision that belongs in DECISIONS.md rather than
    in a quiet edit to conf/sources.yml.
    """
    encumbered = [
        f"{src.id} (access={src.access}, redistribution={src.redistribution})"
        for src in config.sources()
        if not (src.is_open and src.is_redistributable)
    ]
    assert not encumbered, (
        "sources that may not be redistributed: " + ", ".join(encumbered) + ". "
        "Nothing licence-encumbered may be committed or exported."
    )


def test_the_four_os_products_need_no_api_key():
    """Do not build an authentication path you will not use (PLAN.md §7)."""
    for src in config.sources():
        raw = " ".join(str(v).lower() for v in src.raw.values())
        assert "api_key" not in raw and "apikey" not in raw, (
            f"source {src.id!r} mentions an API key. The OS products are open and "
            "need none."
        )


def test_attribution_block_names_every_source():
    """Provenance travels as a pointer: a short attribution may never attribute less."""
    block = config.sources().attribution_block()
    for src in config.sources():
        assert src.title in block, f"{src.id} missing from the attribution block"
        assert src.attribution in block, (
            f"{src.id}'s required attribution is not reproduced in full"
        )


def test_an_undeclared_source_is_an_error_not_a_warning():
    """An unregistered source is an error, not a warning (PLAN.md §2)."""
    with pytest.raises(UnregisteredSource):
        config.source("a_source_that_was_never_declared")


def test_no_url_is_hard_coded_in_the_code():
    """Declare every input; hard-code no URL (PLAN.md §2).

    A URL in a docstring or a comment is a citation and is fine — `conf/sources.yml`
    is full of them and so is PLAN.md. What is not fine is a string literal the code
    could fetch, because an input reached that way is undeclared, unlicensed and
    unchecksummed.
    """
    import ast

    from rewt import paths

    offenders = []
    for path in sorted((paths.ROOT / "rewt").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                first = node.body[0] if node.body else None
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and ("http://" in node.value or "https://" in node.value)
            ):
                offenders.append(f"{paths.rel(path)}:{node.lineno}: {node.value[:80]!r}")
    assert not offenders, (
        "URLs as string literals in code. Sources live in conf/sources.yml and are "
        "fetched by one module; an unregistered source is an error, not a "
        "warning:\n  " + "\n  ".join(offenders)
    )


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"access": "restricted"},
        {"redistribution": "prohibited"},
        {"access": "restricted", "redistribution": "prohibited"},
        {"redistribution": "share-alike"},
    ],
)
def test_the_gate_refuses_an_encumbered_source(overrides):
    """Keep that check; do not work around it (AGENTS.md)."""
    with pytest.raises(UnlicensedSource):
        _source(**overrides).require_redistributable()


def test_the_gate_admits_an_open_source():
    _source().require_redistributable()          # must not raise


def test_the_exporter_gate_rejects_what_the_registry_rejects():
    """The exporter's own gate, not a reimplementation of it."""
    from rewt.stages import export

    with pytest.raises(UnregisteredSource):
        export._licence_gate(["a_source_that_was_never_declared"])

    # 'rewt' is this project's own geometry and is deliberately exempt: a connector
    # has no publisher. Everything else must be declared.
    export._licence_gate(["rewt", None])
    export._licence_gate([src.id for src in config.sources()])


@pytest.mark.db
def test_every_source_in_the_database_is_declared_and_open(con):
    """The gate's real subject: what is actually about to be published."""
    require_tables(con, "link", "node")
    ids = {
        row[0]
        for row in con.execute(
            "SELECT DISTINCT source_id FROM link "
            "UNION SELECT DISTINCT source_id FROM node"
        ).fetchall()
        if row[0] and row[0] != "rewt"
    }
    assert ids, "no source_id on any link or node; provenance has been lost"
    undeclared = sorted(i for i in ids if i not in config.sources())
    assert not undeclared, (
        "features carry source ids that conf/sources.yml does not declare: "
        + ", ".join(undeclared)
    )
    for source_id in sorted(ids):
        config.source(source_id).require_redistributable()
