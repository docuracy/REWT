"""Stage 1 and nothing else.

CLAUDE.md's first override, and PLAN.md §1's closing line: **if a task requires
knowing what year it is, it is not Stage 1.** The failure mode is not refusing this
outright; it is drifting into it a little at a time because a field looked easy to
add. So this file guards the boundary at the place drift would show — the schema and
the published output — rather than trusting that nobody drifted.

The one legitimate date in the whole model is on a `correction`: *a person and the
date they looked* is evidence, and evidence is required (§7). That is a statement
about the adjudication, not about the river.
"""

from __future__ import annotations

import re

import pytest

from conftest import require_tables

from rewt import paths, schema


# Columns that would make Stage 1 into Stage 2. Each names something PLAN.md §1
# puts explicitly out of scope: dating channels, old courses, attestation, flow.
FORBIDDEN = re.compile(
    r"\b("
    r"year|epoch|century|centuries|period|circa|"
    r"attested|attestation|historic\w*|antiqu\w*|medieval|premodern|"
    r"old\s+course|former\s+course|palaeo\w*|paleo\w*|"
    r"discharge|flow\s+rate|flow\s+m3|velocity|cumecs|gauged"
    r")\b",
    re.IGNORECASE,
)


def _forbidden(text: str):
    """An underscore is a word boundary to a reader and not to a regex."""
    return FORBIDDEN.search(text.replace("_", " "))

# The network's own tables. `correction` is excluded: its `dated` field is the date a
# person looked, which is evidence and is required.
NETWORK_TABLES = [
    "link", "node", "basin", "edge", "retirement",
    "link_scope", "link_reach", "link_flag",
]


def _column_names(ddl: str) -> list[str]:
    """Column names out of a CREATE TABLE, ignoring comments and types.

    The opening bracket is found after CREATE TABLE and not by searching from the
    start: several of these declarations open with a comment citing a section, and
    `(§5)` is a bracket too.
    """
    opening = re.search(r"CREATE TABLE\s+\w+\s*\(", ddl)
    assert opening, f"not a CREATE TABLE: {ddl[:60]!r}"
    body = ddl[opening.end() : ddl.rindex(")")]
    names = []
    for line in body.splitlines():
        line = line.split("--")[0].strip().rstrip(",")
        if not line:
            continue
        names.append(line.split()[0])
    return names


@pytest.mark.parametrize("table", NETWORK_TABLES)
def test_no_network_table_declares_a_date_or_a_flow(table):
    """Dates, old courses, attestation and flow belong to later stages (§1)."""
    assert table in schema.TABLES, (
        f"rewt/schema.py no longer declares {table!r}; this guard has lost its subject"
    )
    offending = [c for c in _column_names(schema.TABLES[table]) if _forbidden(c)]
    assert not offending, (
        f"table {table!r} declares {', '.join(offending)}. Stage 1 makes no "
        "historical claim at all, and a field that looked easy to add is how the "
        "drift starts (CLAUDE.md, PLAN.md §1)."
    )


def test_the_model_stays_small():
    """*Keep it small. Stage 1 needs four tables and no more* (§3).

    The others exist for one reason each, and schema.py says what each reason is —
    so this checks that nothing has been added without one.
    """
    four = {"link", "node", "basin", "correction"}
    derived = {
        "edge", "retirement", "link_scope", "link_reach", "link_flag",
        # §10's sea network, added 2026-09-01 when the sea became a test rather
        # than a definition. Their reasons are in schema.py's docstring with the
        # rest; this set is deliberately not the place to state them.
        "sea_entry", "sea_link",
        # The second reachability reading, added 2026-09-02. The sea network was
        # built, published and drawn while no per-link reading could see it, so
        # nothing downstream could ask whether a region the sea already drains
        # needs geometry invented to drain it.
        "link_sea_reach",
    }
    unexplained = set(schema.TABLES) - four - derived
    assert not unexplained, (
        f"tables in rewt/schema.py that §3 does not account for: "
        f"{', '.join(sorted(unexplained))}. Each derived table exists for one "
        "reason; add the reason to schema.py's docstring and to this test together."
    )


def test_every_derived_table_says_why_it_exists():
    """The instruction the previous test gives, enforced rather than asked for.

    Its failure message says *add the reason to schema.py's docstring and to this
    test together* — a convention, followed by whoever read the message, and
    checked by nothing. So the test above goes green the moment somebody adds a
    name to a Python set, and the reason it exists to demand need never be written.

    It has already happened three times. `link_scope`, `link_reach` and `link_flag`
    are in the derived set with no mention in `rewt/schema.py`'s docstring, and the
    set's own comment says of the sea tables *their reasons are in schema.py's
    docstring with the rest* — which is true for those two and was not true for the
    three that went in before them.

    **§3 says keep it small.** A table with no stated reason is how a small model
    stops being one: nothing is ever added without a reason at the time, and the
    reason is what a reader needs a year later to know whether it still applies.
    Naming the table in the docstring is the cheapest possible enforcement — it
    does not check that the sentence is a good one — and it is enough to make the
    two halves move together, which is all the previous test's message asks for.
    """
    doc = schema.__doc__ or ""
    unexplained = sorted(name for name in schema.TABLES if name not in doc)
    assert not unexplained, (
        f"tables in rewt/schema.py that its own docstring never names: "
        f"{', '.join(unexplained)}. §3 allows four tables and each of the others "
        "exists for one reason; the reason belongs where a reader of the schema "
        "will find it. One line each — what it holds and what asked for it."
    )


def test_a_correction_may_carry_the_date_a_person_looked():
    """The exception, and the reason it is one.

    *A correction without evidence is indistinguishable from a guess a year later.*
    """
    columns = _column_names(schema.TABLES["correction"])
    assert "dated" in columns and "author" in columns, (
        "the correction table no longer records who looked and when, which is the "
        "evidence §7 requires"
    )


def test_the_node_terminus_has_no_third_escape_clause():
    """*There is no second escape clause* (§1).

    An exit at the edge of the study area is not a legitimate terminus — it is a
    defect, because scope is whole basins and every basin drains to a coast. The
    loader may not quietly classify one as an ending.
    """
    ddl = schema.TABLES["node"]
    assert "boundary" in ddl, (
        "the node DDL no longer discusses the 'boundary' case at all; §1's argument "
        "for why it is a defect should not disappear silently"
    )
    assert "defect" in ddl.lower(), (
        "the node DDL declares a terminus classification without recording that an "
        "exit at the edge of scope is a defect rather than an ending"
    )


@pytest.mark.db
def test_no_node_is_classified_as_a_boundary_terminus(con):
    """The declaration, enforced against what was actually loaded."""
    require_tables(con, "node")
    count = con.execute(
        "SELECT count(*) FROM node WHERE terminus = 'boundary'"
    ).fetchone()[0]
    assert count == 0, (
        f"{count:,} nodes are classified terminus='boundary'. An exit at the edge of "
        "the study area means the scope was drawn wrong, not that the water went "
        "somewhere unmodelled (§1)."
    )


@pytest.mark.db
@pytest.mark.parametrize("table", NETWORK_TABLES)
def test_no_built_network_table_grew_a_date_column(con, table):
    """The same guard, against the database as built rather than as declared."""
    from conftest import table_names

    if table not in table_names(con):
        pytest.skip(f"the database has no {table} yet")
    columns = [
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table],
        ).fetchall()
    ]
    offending = [c for c in columns if _forbidden(c)]
    assert not offending, (
        f"the built table {table!r} carries {', '.join(offending)}"
    )


def test_the_published_output_makes_no_historical_claim():
    """*No dates, no historical claims, no flow, anywhere in the output* (§9)."""
    readme = paths.PUBLISHED / "README.md"
    if not readme.exists():
        pytest.skip(
            f"{paths.rel(readme)} does not exist; the export stage has not run"
        )
    text = readme.read_text(encoding="utf-8")
    # The build date and the OS copyright year are statements about the build and
    # the licence, not about the river, so they are stripped before the check.
    text = re.sub(r"Built \d{4}-\d{2}-\d{2}", "", text)
    text = re.sub(r"database rights \d{4}", "", text)
    text = re.sub(r"issue \S+", "", text)
    offending = sorted(set(m.group(0).lower() for m in FORBIDDEN.finditer(text)))
    assert not offending, (
        f"{paths.rel(readme)} makes what reads as a historical or flow claim: "
        + ", ".join(offending)
    )


def _later_stage_sources() -> list[str]:
    """Sources conf/sources.yml marks as belonging to a stage after this one."""
    from rewt import config

    return sorted(
        src.id for src in config.sources() if src.get("stage", default=1) != 1
    )


def test_no_stage_reads_a_source_declared_for_a_later_stage():
    """A source may be registered for a later stage; it may not be read by this build.

    Registering a dated historical source is legitimate — the documentation quotes
    counts measured from one — and it is also exactly how the drift starts, because
    the entry is already there and reading it looks like a small step. So the rule is
    checked against the declarations rather than trusted.
    """
    import rewt.stages  # noqa: F401  (registers every stage)

    from rewt import config
    from rewt.pipeline import PIPELINE

    later = set(_later_stage_sources())
    if not later:
        pytest.skip("conf/sources.yml declares no source for a later stage")
    offenders = [
        f"{name} declares {source_id!r} (stage "
        f"{config.source(source_id).get('stage', default=1)})"
        for name in PIPELINE.names
        for source_id in PIPELINE[name].sources
        if source_id in later
    ]
    assert not offenders, (
        "Stage 1 and nothing else (AGENTS.md):\n  " + "\n  ".join(offenders)
    )


def test_the_guard_against_a_later_stage_source_refuses_one():
    """The mechanism, exercised — not merely the state it currently produces.

    `Pipeline.add` raises at registration, so a stage that reached for a stage 2
    source could not even be imported. This constructs exactly that stage and
    watches it be refused.
    """
    from rewt import pipeline
    from rewt.pipeline import StageError

    later = _later_stage_sources()
    if not later:
        pytest.skip("conf/sources.yml declares no source for a later stage to test with")
    other = pipeline.Pipeline()
    with pytest.raises(StageError, match="stage 2|Stage 1 and"):
        other.add(
            pipeline.Stage(
                name="a_stage_that_reaches_too_far",
                summary="",
                fn=lambda: None,
                sources=(later[0],),
            )
        )


@pytest.mark.parametrize("source_id", _later_stage_sources())
def test_a_later_stage_source_still_declares_its_licence(source_id):
    """Registering it early is only safe if it is registered properly.

    A source declared for stage 2 is one nobody is checking yet, which is when an
    encumbered licence is easiest to let through.
    """
    from rewt import config

    src = config.source(source_id)
    assert src.licence.strip(), f"{source_id} declares no licence"
    assert src.attribution.strip(), f"{source_id} declares no attribution"
    # Not require_redistributable(): a later-stage source may legitimately have
    # unestablished terms, and recording that is the honest thing to do. What must
    # hold is that it cannot be read or exported — tests/test_licence.py has that.


@pytest.mark.parametrize("source_id", _later_stage_sources())
def test_a_later_stage_source_is_not_acquired_by_this_build(source_id):
    """Registered is not the same as fetched.

    `rewt acquire` with no arguments fetches `national_sources()`, and a later-stage
    source must not be in it. Nothing in Stage 1 reads such a source, so nothing in
    Stage 1 should be downloading one either — an unfetched source cannot drift into
    a stage by way of a file that happens to be on disk.
    """
    from rewt import acquire

    assert source_id not in acquire.national_sources(), (
        f"{source_id} is declared for a later stage and yet is fetched in bulk by "
        "this build"
    )


@pytest.mark.parametrize("source_id", _later_stage_sources())
def test_fetching_a_later_stage_source_fails_loudly(source_id):
    """Fail loudly (AGENTS.md): refused by name, not quietly skipped."""
    from rewt import acquire

    with pytest.raises(acquire.AcquisitionError):
        acquire.fetch(source_id)


def test_a_source_may_declare_several_files_rather_than_one_url():
    """A source is identified by its declaration, not by having a single URL.

    An article or a catalogue record may publish several files under one licence,
    and only some of them may be the thing wanted — so an entry naming two layers
    out of an article is a legitimate shape. Nothing in the registry requires a
    `url`, and this pins that, because a schema that quietly demanded one would push
    the next such entry towards declaring the whole article instead.
    """
    from rewt.config import Sources

    registry = Sources(
        {
            "sources": [
                {
                    "id": "several_files",
                    "title": "A source published as named files",
                    "publisher": "somebody",
                    "licence": "CC BY 4.0",
                    "attribution": "Cite the authors.",
                    "access": "open",
                    "redistribution": "permitted",
                    "cache_path": "data/raw/nowhere/",
                    "stage": 2,
                    "download": [
                        {"file": "one.shp", "url": "https://example.invalid/one.shp"},
                        {"file": "two.shp", "url": "https://example.invalid/two.shp"},
                    ],
                    "excluded": ["a layer resting on someone else's licence"],
                }
            ]
        }
    )
    src = registry["several_files"]
    src.require_redistributable()
    assert len(src.require("download")) == 2
    assert src.get("stage") == 2
