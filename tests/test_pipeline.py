"""The stage declarations, which are what enforce the order.

**Declare stage inputs and outputs so the order is enforced, not remembered**
(PLAN.md §2). In the earlier work one stage rebuilt a table another had written
columns into; running them in the wrong order produced a plausible network with stale
values on it. These checks are all static — they read the declarations, they do not
run a build.
"""

from __future__ import annotations

import pytest

from rewt import pipeline
from rewt.pipeline import PIPELINE, StageError


@pytest.fixture(scope="module", autouse=True)
def _registered():
    import rewt.stages  # noqa: F401  (importing registers every stage)


def test_the_pipeline_has_stages():
    assert PIPELINE.names, "no stages are registered"


def test_the_build_ends_in_an_export_and_contains_an_audit():
    """*The audit is part of the build*, not a script someone remembers to run."""
    assert "audit" in PIPELINE, (
        f"no audit stage. Registered: {', '.join(PIPELINE.names)}"
    )
    assert PIPELINE["audit"].always, (
        "the audit is cacheable, so a build can report a stale audit as this build's"
    )
    assert "export" in PIPELINE, "no export stage; §7's deliverable is never written"


def test_no_artefact_has_two_producers():
    """Two stages writing one table is how stale values arrive."""
    producers: dict[str, list[str]] = {}
    for name in PIPELINE.names:
        for artefact in PIPELINE[name].writes:
            producers.setdefault(artefact, []).append(name)
    clashes = {a: p for a, p in producers.items() if len(p) > 1}
    assert not clashes, (
        "artefacts written by more than one stage: "
        + "; ".join(f"{a} <- {', '.join(p)}" for a, p in sorted(clashes.items()))
    )


def test_every_read_is_a_declared_artefact():
    """A stage that reads something nothing declares cannot have its order enforced."""
    undeclared = []
    for name in PIPELINE.names:
        for artefact in PIPELINE[name].reads:
            if artefact not in pipeline._ARTEFACTS:
                undeclared.append(f"{name} reads {artefact!r}")
    assert not undeclared, "\n  ".join(["undeclared artefacts:"] + undeclared)


def test_the_plan_is_a_valid_topological_order():
    """Whatever a stage reads is produced before it runs, or comes from outside."""
    order = PIPELINE.plan()
    position = {name: i for i, name in enumerate(order)}
    violations = []
    for name in order:
        for artefact in PIPELINE[name].reads:
            producer = PIPELINE.producer_of(artefact)
            if producer is None or producer == name:
                continue
            if position.get(producer, len(order)) >= position[name]:
                violations.append(
                    f"{name} reads {artefact!r} but its producer {producer} "
                    "does not run first"
                )
    assert not violations, "\n  ".join(["order:"] + violations)


def test_the_plan_is_deterministic():
    assert PIPELINE.plan() == PIPELINE.plan()


def test_the_plan_covers_every_stage():
    """`rewt build` runs the whole pipeline; a stage nothing reaches is dead."""
    assert set(PIPELINE.plan()) == set(PIPELINE.names)


def test_dependencies_of_the_last_stage_reach_back_to_the_first():
    """The deliverable depends on the acquisition, or something is disconnected."""
    deps = PIPELINE.dependencies("export")
    assert "load" in deps, (
        f"export does not depend on load. Its chain is: {', '.join(deps)}"
    )


def test_a_stage_cycle_is_an_error():
    """Not a hang, and not an arbitrary order."""
    other = pipeline.Pipeline()
    other.add(
        pipeline.Stage(name="a", summary="", fn=lambda: None,
                       reads=("_test_cycle_b",), writes=("_test_cycle_a",))
    )
    other.add(
        pipeline.Stage(name="b", summary="", fn=lambda: None,
                       reads=("_test_cycle_a",), writes=("_test_cycle_b",))
    )
    with pytest.raises(StageError, match="cycle"):
        other.dependencies("a")


def test_registering_a_stage_twice_is_an_error():
    other = pipeline.Pipeline()
    stage = pipeline.Stage(name="only", summary="", fn=lambda: None)
    other.add(stage)
    with pytest.raises(StageError, match="twice"):
        other.add(pipeline.Stage(name="only", summary="", fn=lambda: None))


def test_two_stages_may_not_write_one_artefact():
    """The registry refuses it, rather than the build discovering it."""
    other = pipeline.Pipeline()
    other.add(pipeline.Stage(name="first", summary="", fn=lambda: None,
                             writes=("_test_shared",)))
    with pytest.raises(StageError, match="written by both"):
        other.add(pipeline.Stage(name="second", summary="", fn=lambda: None,
                                 writes=("_test_shared",)))


def test_an_unknown_stage_names_the_known_ones():
    """Fail loudly, and usefully."""
    with pytest.raises(StageError) as excinfo:
        PIPELINE["a_stage_that_does_not_exist"]
    assert "load" in str(excinfo.value)


def test_every_stage_declares_what_it_writes_or_says_why_not():
    """A stage writing nothing declared cannot be cached, and must not claim to be."""
    for name in PIPELINE.names:
        stage = PIPELINE[name]
        if stage.writes:
            continue
        assert stage.always or not stage.cacheable, (
            f"stage {name!r} declares no outputs and is still cacheable: nothing "
            "can tell whether it has run"
        )


def test_stages_that_read_hand_edited_files_are_never_cached():
    """The curated files are hand-edited; a cached answer about them can be stale."""
    assert PIPELINE["curated"].always, (
        "the curated stage may be cached, so an edit to data/curated/ can be "
        "invisible to the next build"
    )


def test_every_stage_declares_the_parameters_it_reads():
    """*Thresholds and parameters live in configuration* — and in the fingerprint.

    A parameter a stage reads but does not declare is one whose correction will not
    invalidate that stage's cache. That is the month-long stale raster, exactly.
    """
    from rewt import config

    unknown = []
    for name in PIPELINE.names:
        for path in PIPELINE[name].params:
            try:
                config.param(path)
            except KeyError:
                unknown.append(f"{name} declares {path!r}, which conf/params.yml lacks")
    assert not unknown, "\n  ".join(["parameters:"] + unknown)


def test_every_stage_declares_sources_that_exist():
    from rewt import config

    unknown = []
    for name in PIPELINE.names:
        for source_id in PIPELINE[name].sources:
            if source_id not in config.sources():
                unknown.append(f"{name} declares source {source_id!r}")
    assert not unknown, "\n  ".join(["sources:"] + unknown)


def test_a_stage_that_touches_the_terrain_declares_the_terrain_source():
    """The fingerprint must cover the input, or a reissue is invisible."""
    for name in ("terrain", "screen"):
        if name not in PIPELINE:
            continue
        assert "os_terrain_50" in PIPELINE[name].sources, (
            f"stage {name!r} works on Terrain 50 without declaring it as a source, "
            "so a new issue of it would not invalidate the cache"
        )
