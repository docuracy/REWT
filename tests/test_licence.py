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

import re

import pytest

from conftest import require_tables

from rewt import config, paths
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


def _encumbered() -> list[str]:
    """Sources conf/sources.yml does not clear for redistribution."""
    return sorted(
        src.id
        for src in config.sources()
        if not (src.is_open and src.is_redistributable)
    )


def test_every_source_the_build_reads_is_redistributable():
    """The guarantee, put where AGENTS.md puts it: on what is read and exported.

    *The exporter refuses to write a feature whose source is not openly licensed.*
    Declaring a source whose terms are unknown is honest bookkeeping — it records
    what is known, which is the opposite of the failure this project guards against.
    Reading one into the build is the act that cannot be undone once the repository
    is public, because the output would carry terms nobody has established.
    """
    import rewt.stages  # noqa: F401  (registers every stage)

    from rewt.pipeline import PIPELINE

    read = sorted({sid for name in PIPELINE.names for sid in PIPELINE[name].sources})
    offenders = [sid for sid in read if sid in set(_encumbered())]
    assert not offenders, (
        "stages read sources that may not be redistributed: " + ", ".join(offenders)
    )
    for sid in read:
        config.source(sid).require_redistributable()


def test_a_source_that_may_not_be_redistributed_is_quarantined():
    """Declared, and kept where it cannot reach an output.

    Three conditions, because any one of them alone leaks. It must be marked for a
    later stage, so `Pipeline.add` refuses any stage that reaches for it; no stage
    may declare it; and the build must not fetch it in bulk, because a file on disk
    is the start of somebody using it.
    """
    import rewt.stages  # noqa: F401

    from rewt import acquire
    from rewt.pipeline import PIPELINE

    for source_id in _encumbered():
        src = config.source(source_id)
        assert src.get("stage", default=1) != 1, (
            f"{source_id} may not be redistributed and is not marked for a later "
            "stage, so nothing stops a stage reading it"
        )
        declaring = [n for n in PIPELINE.names if source_id in PIPELINE[n].sources]
        assert not declaring, (
            f"{source_id} may not be redistributed and is declared by "
            + ", ".join(declaring)
        )
        assert source_id not in acquire.national_sources(), (
            f"{source_id} may not be redistributed and is fetched in bulk"
        )


def test_an_encumbered_source_records_what_is_not_known_about_it():
    """*Never add a source without recording its licence and required attribution.*

    A source whose terms are unestablished must say so in words, not merely score
    badly in a field. The next person to read the file needs to know what was
    checked and what was not.
    """
    for source_id in _encumbered():
        src = config.source(source_id)
        assert src.licence.strip(), f"{source_id} records no licence at all"
        assert len(src.licence.strip()) > 30, (
            f"{source_id} is not cleared for redistribution and its licence field "
            f"says only {src.licence!r}. What is not known about it has to be "
            "written down, or the next reader will assume it was checked."
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
                # A BARE SCHEME IS NOT A URL. `"https://" + url` completes an address
                # the NRW tile catalogue returns without one (rewt/elevation.py) — the
                # address is data from a declared source, and the literal names no host
                # to fetch from. Matching it made this gate fire on a correct line, and
                # a gate that cries wolf is the one somebody deletes. Anything with a
                # host after the scheme is still an offender.
                and not re.fullmatch(r"https?://", node.value.strip())
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

    # Every source the build actually reads passes the gate.
    import rewt.stages  # noqa: F401

    from rewt.pipeline import PIPELINE

    export._licence_gate(
        {sid for name in PIPELINE.names for sid in PIPELINE[name].sources}
    )

    # And a real encumbered source is refused by it — better evidence than the
    # synthetic one above, because this is a source that genuinely exists here.
    for source_id in _encumbered():
        with pytest.raises(UnlicensedSource):
            export._licence_gate([source_id])


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


# --------------------------------------------------------------------------
# The obligation is discharged twice, so it is checked against the authority twice
# --------------------------------------------------------------------------


def test_both_renderings_of_the_attributions_agree_with_the_manifest():
    """`published/ATTRIBUTION.md` and `docs/_data/sources.yml` credit the same people.

    They are generated by different code, on different schedules, from one manifest:
    the first by the export stage into a build artefact, the second by
    `tools/docs/sources_page.py` into a committed projection. Each can go stale without
    the other noticing, and the failure is silent — a page that credits the wrong
    people while looking authoritative.
    """
    from rewt import paths, release

    if not (paths.PUBLISHED / "ATTRIBUTION.md").exists():
        pytest.skip("published/ has not been built in this checkout")
    drift = release.attribution_drift()
    assert not drift, "an attribution has drifted from conf/sources.yml:\n" + "\n".join(drift)


def test_the_drift_check_can_actually_fail(tmp_path, monkeypatch):
    """Point it at an ATTRIBUTION.md crediting nobody and watch it object.

    A check that has only ever been run against a passing repository is a check that
    has never been run. This is the same reasoning as the encumbered-source gate above.
    """
    from rewt import paths, release

    empty = tmp_path / "published"
    empty.mkdir()
    (empty / "ATTRIBUTION.md").write_text("# Attribution\n\nNobody, for anything.\n")
    monkeypatch.setattr(paths, "PUBLISHED", empty)
    monkeypatch.setattr(release.paths, "PUBLISHED", empty)

    drift = release.attribution_drift()
    assert drift, "an ATTRIBUTION.md naming no source at all was accepted"
    assert any("ATTRIBUTION.md" in d for d in drift)


# --------------------------------------------------------------------------- D-072
# THE VIEWER AND THE TRACER TREAT THE SAME NLS LAYERS OPPOSITELY, AND THE DIFFERENCE IS
# WHETHER THERE IS A GATE.
#
# The National Library of Scotland state one condition on their georeferenced layers:
# *"Re-use of these layers is intended within a desktop or local environment. If you
# wish to present these layers online in a public website, please use our Historic Maps
# API layers, or contact us."*
#
# Stephen's ruling (D-072): the request concerns PUBLIC PRESENTATION, and does not reach
# a tool that presents to nobody. The viewer renders to any visitor and is squarely
# inside that sentence, so it serves no layer taken from the Library's tile bucket. The
# tracer renders nothing without a token — an anonymous visitor gets a wall and fetches
# no tile — so it may carry all of them.
#
# Nothing but this compares the ruling to the files. Both halves are one JSON file and
# one JavaScript file, and either could be undone by an edit that looks like a feature.

VIEWER_BACKDROPS = paths.ROOT / "docs" / "viewer" / "backdrops.json"
TRACER_APP = paths.ROOT / "docs" / "trace" / "js" / "app.js"

# The bucket the Library does not publish addresses for, harvested by enumerating a
# bucket that permits ListBucket. `tools/nls_layers.json` — the catalogue of 2,016 of
# them — is gitignored for the same reason.
NLS_BUCKET = "mapseries-tilesets.s3.amazonaws.com"


def test_the_public_viewer_serves_no_layer_from_the_library_s_own_bucket():
    """D-072's first half, and the one with a licence behind it.

    68 layers served directly from the bucket were removed from the viewer and the
    file records it. What replaced them is the Library's mapping through MapTiler,
    which is the route NLS's own sentence points at — so this is not a test that the
    viewer shows no historic mapping, which it does. It is a test that it does not
    reach past the sanctioned route to the bucket.
    """
    import json

    if not VIEWER_BACKDROPS.exists():
        pytest.skip(f"{paths.rel(VIEWER_BACKDROPS)} does not exist; run the viewer build")
    text = VIEWER_BACKDROPS.read_text(encoding="utf-8")
    options = json.loads(text).get("options", {})
    assert options, f"{paths.rel(VIEWER_BACKDROPS)} declares no backdrops at all"

    offending = sorted(
        name
        for name, option in options.items()
        if isinstance(option, dict)
        and any(NLS_BUCKET in str(option.get(field, "")) for field in ("tiles", "url"))
    )
    assert not offending, (
        f"{len(offending)} backdrop(s) in {paths.rel(VIEWER_BACKDROPS)} serve tiles "
        f"from {NLS_BUCKET} to a public website:\n      " + "\n      ".join(offending)
        + f"\n      NLS ask that online public presentation go through their Historic "
        "Maps API rather than these layers (D-072, D-043). The tracer may carry them "
        "because it presents to nobody without a token; the viewer presents to "
        "everybody."
    )
    # The selector reads the tile URLs, so it says nothing unless there are tile URLs
    # to read. A backdrops file that had lost its layers would pass it silently.
    with_tiles = [o for o in options.values() if isinstance(o, dict) and o.get("tiles")]
    assert len(with_tiles) >= 2, (
        f"only {len(with_tiles)} backdrop(s) in {paths.rel(VIEWER_BACKDROPS)} carry a "
        "tile URL, so this check inspected almost nothing. Either the file changed "
        "shape or the layers are gone."
    )


def test_the_tracer_draws_no_map_before_a_token_is_accepted():
    """D-072's second half: the gate is what earns the layers.

    The ruling turns entirely on `startMap()` being unreachable without a successful
    sign-in. If it is ever called from boot — to show a preview, to warm a cache, to
    make the wall less stark — the tracer becomes a public presentation of every NLS
    layer it carries, and the ruling that permits them stops applying at that moment.

    A shape test, and it says so: it reads where the call sits in the source, not what
    the browser does. It cannot see a gate defeated some other way, and a stronger
    check belongs with the tracer's own harness (`tools/tracer/check_*.mjs`), which
    exercises the real module.
    """
    if not TRACER_APP.exists():
        pytest.skip(f"{paths.rel(TRACER_APP)} does not exist")
    source = TRACER_APP.read_text(encoding="utf-8")

    definition = re.search(r"(?:async\s+)?function\s+startMap\s*\(", source)
    assert definition, (
        f"{paths.rel(TRACER_APP)} defines no `startMap`; this test was written around "
        "the tracer starting its map in one place and no longer knows where to look."
    )
    calls = [
        m.start() for m in re.finditer(r"\bstartMap\s*\(", source)
        if m.start() != definition.start() + (definition.group(0).find("startMap"))
    ]
    assert len(calls) == 1, (
        f"`startMap()` is called from {len(calls)} places in "
        f"{paths.rel(TRACER_APP)}. D-072 permits the tracer to carry every NLS layer "
        "ONLY because it renders nothing to an anonymous visitor, so the map must "
        "start in exactly one place and that place must be behind the token."
    )

    sign_in = re.search(r"(?:async\s+)?function\s+signIn\s*\(", source)
    assert sign_in, f"{paths.rel(TRACER_APP)} defines no `signIn`"
    following = re.compile(r"\n(?:async\s+)?function\s+\w+\s*\(")
    end = following.search(source, sign_in.end())
    end = end.start() if end else len(source)
    assert sign_in.start() < calls[0] < end, (
        f"`startMap()` is called from outside `signIn()` in {paths.rel(TRACER_APP)}. "
        "An anonymous visitor must get a wall and fetch no tile: that is the whole of "
        "why this tool may publish the layers the viewer may not (D-072)."
    )
