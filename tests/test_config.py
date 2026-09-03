"""The source registry and the parameter file, which are the two places a value may
legitimately come from.

**Declare every input; hard-code no URL. Thresholds and parameters live in
configuration too, not as literals in a function** (PLAN.md §2, AGENTS.md). The point
of testing the registry rather than only the values in it is that both rules are
enforced by `rewt/config.py` refusing things — and a refusal that stopped refusing
would be invisible.
"""

from __future__ import annotations

import pytest

from rewt import config, paths
from rewt.config import Params, Sources, UnregisteredSource


def test_the_repository_root_is_where_the_paths_assume():
    paths.check_root()
    assert paths.SOURCES_YML.exists()
    assert paths.PARAMS_YML.exists()
    assert paths.ROOT == paths.SOURCES_YML.parent.parent


def test_every_path_is_under_the_root():
    """Paths in code are relative; nothing reaches outside the checkout."""
    for path in (paths.RAW, paths.INTERIM, paths.CURATED, paths.DB_DIR, paths.PUBLISHED):
        assert paths.ROOT in path.parents, f"{path} is not under {paths.ROOT}"


def test_rel_is_what_a_report_prints():
    assert paths.rel(paths.SOURCES_YML) == "conf/sources.yml"


def test_the_registry_reads_every_declared_source():
    sources = config.sources()
    assert len(sources) >= 4, (
        f"conf/sources.yml declares {len(sources)} sources; PLAN.md §4 names four OS "
        "products plus two LiDAR services"
    )
    assert sources.ids == sorted(sources.ids)


def test_a_source_without_a_licence_is_not_a_source():
    """A source without a licence and an attribution is not declared."""
    with pytest.raises(ValueError, match="missing required field"):
        Sources(
            {
                "sources": [
                    {
                        "id": "half_declared",
                        "title": "A source with no licence",
                        "publisher": "nobody",
                        "cache_path": "data/raw/nowhere/",
                    }
                ]
            }
        )


def test_a_duplicate_source_id_is_an_error():
    entry = {
        "id": "twice",
        "title": "t",
        "publisher": "p",
        "licence": "l",
        "attribution": "a",
        "access": "open",
        "redistribution": "permitted",
        "cache_path": "data/raw/nowhere/",
    }
    with pytest.raises(ValueError, match="duplicate"):
        Sources({"sources": [entry, dict(entry)]})


def test_asking_a_source_for_something_it_does_not_declare():
    """`get` answers None; `require` raises. The difference is deliberate."""
    src = config.source(config.sources().ids[0])
    assert src.get("nothing", "here") is None
    with pytest.raises(UnregisteredSource):
        src.require("nothing", "here")


def test_a_parameter_has_no_silent_default():
    """*Thresholds live in configuration, not in a function.*

    A lookup that quietly returned zero would put a literal back in the code, in the
    least visible place possible.
    """
    params = Params({"a": {"b": 1}})
    assert params("a.b") == 1
    with pytest.raises(KeyError):
        params("a.c")
    assert params("a.c", 7) == 7


def test_a_section_is_a_section():
    params = Params({"a": {"b": 1}})
    assert params.section("a") == {"b": 1}
    with pytest.raises(KeyError, match="not a section"):
        params.section("a.b")


@pytest.mark.parametrize(
    "path",
    [
        "crs.working",
        "crs.export",
        "topology",
        "seeds",
        "forms",
        "terrain",
        "basins",
        "scope",
        "repair",
        "audit",
        "determinism.seed",
    ],
)
def test_the_parameters_the_plan_depends_on_are_declared(path):
    """Each of these is a threshold PLAN.md argues about; none may be a literal."""
    assert config.param(path) is not None, f"conf/params.yml declares no {path!r}"


def test_the_forms_are_the_survey_s_own():
    """inlandRiver, canal, lake, tidalRiver — the four §6 breaks the audit down by."""
    forms = config.param("forms")
    flat = " ".join(str(v) for v in (forms.values() if isinstance(forms, dict) else forms))
    for form in ("inlandRiver", "canal", "lake", "tidalRiver"):
        assert form in flat, (
            f"conf/params.yml's forms section does not mention {form!r}. The audit "
            "breaks its findings down by the form of the water arriving, because the "
            "classes have different causes and different remedies (§6)."
        )


# --------------------------------------------------------------------------
# The pin (D-054)
# --------------------------------------------------------------------------


def test_os_open_rivers_is_pinned_to_a_single_issue():
    """Stephen's ruling on the identifier card: freeze rather than mint our own.

    OS's specification says its GUIDs are not persistent *between product
    versions*. With exactly one version there is no second version for them to be
    inconsistent with, so §10's stability requirement is bought by refusing
    reissues. That makes the pin the mechanism the whole identifier scheme rests
    on, rather than a note about provenance.
    """
    frozen = config.source("os_open_rivers").get("frozen_issue", default=None)
    assert frozen, (
        "os_open_rivers has no frozen_issue. The identifier scheme depends on the "
        "input being pinned (D-054); without it, a reissue renumbers 195,689 links "
        "and every judgement in data/curated/ that keys on them."
    )
    assert frozen == "2026-04-14", f"the pin moved to {frozen} — was that decided?"


def test_the_pin_is_enforced_and_not_merely_declared():
    """A pin nobody checks is a comment.

    The reissue is twice a year, so the failure it guards against is one nobody is
    present for: the file changes, the build goes green, and the first sign of
    trouble is a curated correction that matches nothing. This test reads the
    stage's own source for the comparison rather than trusting that it exists.
    """
    import inspect

    from rewt.stages import load

    src = inspect.getsource(load)
    assert "frozen_issue" in src, (
        "rewt/stages/load.py never reads frozen_issue, so the pin in "
        "conf/sources.yml is a comment rather than a constraint"
    )
    assert "raise StageError" in src.split("frozen_issue", 1)[1][:1200], (
        "load reads frozen_issue but does not fail on a mismatch. A warning on a "
        "twice-yearly event is a warning nobody is present for."
    )


def test_the_bathymetry_is_pinned_by_its_bytes():
    """§10's sea terminus rests on a coverage whose identifier cannot be pinned.

    `emodnet__mean` is whatever release is current and will move when 2026 ships;
    the dated coverage ids are *past* releases, and there is no `_2024`, so asking
    for a dated id takes older data rather than freezing the current one. The
    publisher's identifier simply cannot express "the release I built against", so
    the digest does — a manifest over the sorted `name:sha256` of all 120 windows.

    This matters more here than for a vector source: the cost surface, every sea
    route, and every figure measured against them come out of these bytes.
    """
    src = config.source("emodnet_bathymetry")
    declared = src.get("checksum", default=None)
    assert declared, (
        "emodnet_bathymetry declares no checksum. Its coverage id cannot be pinned, "
        "so without this the build has no way to say which release it used."
    )
    assert len(declared) == 64, f"not a sha256: {declared!r}"


def test_the_bathymetry_pin_is_compared_and_not_merely_declared():
    """Verified by firing it: a single appended byte across 481 MB was caught.

    Read from the source rather than trusted, for the same reason as the OS pin —
    a digest nothing compares is provenance theatre, and this repository has
    already shipped one artefact whose consistency check could not see the thing
    that was wrong with it.
    """
    import inspect

    from rewt import acquire

    body = inspect.getsource(acquire.fetch_wcs)
    assert 'src.get("checksum"' in body, (
        "fetch_wcs never reads the declared checksum, so the pin in "
        "conf/sources.yml is a comment rather than a constraint"
    )
    assert "raise AcquisitionError" in body.split('src.get("checksum"', 1)[1][:900], (
        "fetch_wcs reads the checksum but does not fail on a mismatch"
    )


# --------------------------------------------------------------------------
# Every declared source has a consumer, or says why it has none (D-059)
# --------------------------------------------------------------------------


def _read_by_a_stage() -> set[str]:
    import rewt.stages  # noqa: F401  (registers every stage)

    from rewt.pipeline import PIPELINE

    return {sid for name in PIPELINE.names for sid in PIPELINE[name].sources}


def test_every_stage_1_source_is_read_by_a_stage_or_says_why_not():
    """*Resist adding a source that no stage reads* — D-059's rule, which is the
    one with teeth.

    §4 states it as a count: four OS products plus two LiDAR services. Measured,
    the build read exactly six — **and not those six.** Both LiDAR services had
    gone unread while CRT structures and EMODnet took their places, so a reader
    checking the total would have found it correct and concluded nothing had
    drifted. That is this repository's own recurring shape appearing in its own
    specification: the figure exact, the sentence false.

    A count cannot catch that and this can. The one distinction it needs is that
    *unread* covers three different things:

    * `stage: 2` — waiting for a stage that does not exist yet;
    * `per_section: true` — consumed by something that is not a stage;
    * `read_by:` — read by nothing in this repository, and nothing should read it.

    Neither of the first two fits a source whose only consumer is a sentence on a
    documentation page. `ada_internal_drainage_districts` is declared so that the
    Internal Drainage District figure on /scale, /evidence and /regions can be
    RE-DERIVED rather than inherited from the predecessor, which AGENTS.md forbids
    and D-090 records. It is not waiting for anything and nothing consumes it
    programmatically at all. Stephen's ruling: teach the test the third category.

    **It is the category most likely to be abused, and that shaped how it is
    written.** The other two name a future in which the source becomes read, and
    go stale loudly when that future arrives. This one names a permanent state, so
    it is the one somebody reaching for green will find first. Three things make
    that expensive: the value must be from a declared vocabulary rather than a
    free string, the reason must be a sentence rather than a flag, and — the part
    with teeth — **a source that claims nothing reads it must really be read by no
    stage**, so the claim breaks loudly if a stage ever starts.
    """
    unread = sorted(
        src.id
        for src in config.sources()
        if src.get("stage", default=1) == 1
        and not src.get("per_section", default=False)
        and not src.get("read_by", default=None)
        and src.id not in _read_by_a_stage()
    )
    assert not unread, (
        "sources declared for Stage 1 that no stage reads: " + ", ".join(unread)
        + ". Either a stage should read it, or the declaration should say why "
        "nothing does — `stage: 2` for one waiting on later work, `per_section: "
        "true` for one fetched a place at a time, `read_by:` with a "
        "`read_by_reason` for one nothing in this repository reads or should. The "
        "sentence that was missing is the point of this failing, not the flag."
    )


# THE VOCABULARY, DECLARED. A free string here would be a `reason` column all over
# again (D-070, D-039): prose that becomes a controlled vocabulary the moment a
# template makes every value share a phrase, with nothing saying it is one. Adding a
# value is a decision somebody takes here, in front of this comment, rather than a
# word typed into conf/sources.yml at the moment a test is inconvenient.
_NON_STAGE_READERS = {
    # Read by no code at all. Its consumer is a sentence on a documentation page, and
    # it is declared so that sentence can be re-derived rather than inherited.
    "documentation-only",
}


def _declares_a_non_stage_reader():
    return sorted(src.id for src in config.sources() if src.get("read_by", default=None))


@pytest.mark.parametrize("source_id", _declares_a_non_stage_reader())
def test_a_non_stage_reader_is_one_of_the_declared_kinds(source_id):
    """`read_by` is a vocabulary, not a comment field."""
    value = str(config.source(source_id).get("read_by")).strip()
    assert value in _NON_STAGE_READERS, (
        f"{source_id} declares `read_by: {value}`, which is not one of "
        f"{sorted(_NON_STAGE_READERS)}. The point of the vocabulary is that adding a "
        "kind is a decision taken in tests/test_config.py rather than a string typed "
        "into conf/sources.yml — the flag exempts a source from D-059's rule, and an "
        "exemption anyone can invent in passing is not an exemption."
    )


@pytest.mark.parametrize("source_id", _declares_a_non_stage_reader())
def test_a_non_stage_reader_says_why_in_a_sentence(source_id):
    """The flag is the mechanism; the reasoning is what a reader needs.

    Same argument as the `per_section` pair above, and it matters more here: this
    category describes a state that never resolves, so the sentence is the only
    thing that will look wrong to a reader when it stops being true. A flag cannot
    look wrong.
    """
    reason = str(config.source(source_id).get("read_by_reason") or "").strip()
    assert len(reason) > 40 and " " in reason, (
        f"{source_id} declares `read_by` and gives no reason worth reading "
        f"({reason!r}). Say what does consume it and why no stage should — the "
        "sentence is what somebody checks in a year, and the flag is what they "
        "would have to take on trust."
    )


@pytest.mark.parametrize("source_id", _declares_a_non_stage_reader())
def test_a_non_stage_reader_is_really_read_by_no_stage(source_id):
    """The part with teeth, and the reason this is a category rather than an
    exemption.

    `per_section` is enforced — the fetcher refuses a national pass — and this is
    the equivalent: a declaration that nothing reads a source is checkable against
    the pipeline that would read it. Without this the flag would be the one thing
    in the file that means whatever the last person to type it wanted, and the
    drift it was written to permit would cover the drift it was not.
    """
    assert source_id not in _read_by_a_stage(), (
        f"{source_id} declares `read_by: "
        f"{config.source(source_id).get('read_by')}` — nothing in this repository "
        "reads it — and a stage reads it. One of the two is wrong: if the stage is "
        "right, remove the declaration, because the source is no longer exempt from "
        "D-059's rule and should not be counted as though it were."
    )


@pytest.mark.parametrize(
    "source_id",
    sorted(
        src.id for src in config.sources() if src.get("per_section", default=False)
    ),
)
def test_a_per_section_source_cannot_be_fetched_in_bulk(source_id):
    """LiDAR has no bulk national download, and this is what enforces it.

    `per_section` is the declaration that stops the previous test reading these as
    drift, so it has to mean something enforced rather than something asserted.

    **THE FLAG CONFLATES TWO THINGS AND ONLY ONE OF THEM SURVIVED D-085.** D-006
    said LiDAR is fetched per section, *when a person is adjudicating a place*, and
    never nationally — a claim about the OCCASION and a claim about the UNIT. D-085
    overrode the first on Stephen's instruction: the elevation sweep is national,
    every node, deliberately. rewt-e8 recorded that override without looking for
    what enforced the thing being overridden, and wrote in `conf/sources.yml` that
    this test now enforces a superseded decision.

    It does not, and the distinction is worth keeping rather than deleting the
    guard. What this asserts is the UNIT: there is no bulk national file for these
    products, and `acquire.fetch()` refuses to pretend there is. That is still true
    under D-085 — `rewt/elevation.py` fetches a kilometre square at a time through
    its own WCS and WMS code, and `national_sources()` returns only the
    `api: os_downloads` products, of which these are not any. A national SWEEP made
    of per-square requests is not a national DOWNLOAD.

    So the flag stays true for `ea_lidar_composite_dtm_1m` and `nrw_lidar_dtm_1m`,
    and the sentence that had gone stale was this docstring's, not the assertion's.
    **A decision with a test cannot be superseded in prose alone** — which is
    rewt-e8's own line, and it cuts both ways: the test also cannot be retired
    because a decision moved next to it.
    """
    from rewt import acquire

    assert source_id not in acquire.national_sources(), (
        f"{source_id} declares per_section and is fetched in bulk anyway"
    )
    with pytest.raises(acquire.AcquisitionError, match="per section|nationally"):
        acquire.fetch(source_id)


@pytest.mark.parametrize(
    "source_id",
    sorted(
        src.id for src in config.sources() if src.get("per_section", default=False)
    ),
)
def test_a_per_section_source_records_why_nothing_reads_it(source_id):
    """The flag is the mechanism; the reasoning is what a reader needs.

    A flag alone would make this pair of tests pass while leaving the next person
    to work out why two declared sources have no consumer — which is the state
    D-059 found and the reason it was hard to see.
    """
    src = config.source(source_id)
    notes = str(src.get("notes") or "")
    assert len(notes.strip()) > 40, (
        f"{source_id} declares per_section and records no reasoning. The flag "
        "stops a test failing; it does not tell anyone why the source has no "
        "batch consumer."
    )
