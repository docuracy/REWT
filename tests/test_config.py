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
