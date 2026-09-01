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
