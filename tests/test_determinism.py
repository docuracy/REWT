"""Reproducibility comes first, not last (PLAN.md §2).

**One command from an empty checkout to the finished network, producing the same
result every time.** Determinism is not a property you can test by building twice in
a unit test, so what is tested here is every piece the build's determinism rests on:

* the identifier scheme, which must survive a rebuild;
* the configuration fingerprint, which is what stops a cached intermediate being
  preferred to the configuration that produced it;
* the stage fingerprints, which must change when — and only when — something they
  cover changes;
* declared ordering, wherever a result depends on iteration order.
"""

from __future__ import annotations

import json

import pytest

from rewt import config, ids, pipeline


# --------------------------------------------------------------------------
# The identifier scheme (PLAN.md §10)
# --------------------------------------------------------------------------


def test_a_publisher_feature_keeps_the_publishers_identity():
    assert ids.publisher("link", "watercourse_link.1234") == "os:link:watercourse_link.1234"
    assert ids.is_publisher("os:link:x")
    assert not ids.is_ours("os:link:x")
    assert ids.publisher_id_of("os:link:watercourse_link.1234") == "watercourse_link.1234"
    assert ids.publisher_id_of("rewt:link:abcdef") is None


def test_our_ids_are_derived_from_what_the_feature_is():
    """*A stretch present in two published editions must carry the same id in both.*

    So no id may depend on iteration order, a row number, or the time of the build.
    """
    first = ids.point(412345.678, 287654.321)
    second = ids.point(412345.678, 287654.321)
    assert first == second
    assert ids.is_ours(first)


def test_a_node_id_is_stable_to_the_millimetre_and_no_further():
    """Rounded to the millimetre, far below the survey's own precision."""
    assert ids.point(412345.6781, 287654.3211) == ids.point(412345.6784, 287654.3214)
    assert ids.point(412345.678, 287654.321) != ids.point(412345.679, 287654.321)


def test_a_line_id_does_not_depend_on_which_way_it_was_drawn():
    """*A reversal moves no geometry* (§5), so it may not move the identifier either."""
    coords = [(100.0, 200.0), (150.0, 250.0), (200.0, 300.0)]
    assert ids.line(coords) == ids.line(list(reversed(coords)))


def test_different_geometry_is_a_different_feature():
    assert ids.line([(0.0, 0.0), (1.0, 1.0)]) != ids.line([(0.0, 0.0), (1.0, 2.0)])


def test_a_derived_id_does_not_depend_on_which_side_was_processed_first():
    """One link cut at a junction yields two children; the pair must be stable."""
    left = ids.derived("os:link:1", "link", "0.000,0.000;5.000,5.000")
    right = ids.derived("os:link:1", "link", "5.000,5.000;9.000,9.000")
    assert left != right
    assert left == ids.derived("os:link:1", "link", "0.000,0.000;5.000,5.000")


def test_a_basin_is_identified_by_its_outlet():
    """The thing that defines it — not the order delineation happened to emit it in."""
    assert ids.basin("os:node:99") == ids.basin("os:node:99")
    assert ids.basin("os:node:99") != ids.basin("os:node:98")


def test_a_correction_is_identified_by_what_it_acts_on_and_what_it_does():
    assert ids.correction("reversal", "os:link:1") == ids.correction("reversal", "os:link:1")
    assert ids.correction("reversal", "os:link:1") != ids.correction("junction", "os:link:1")
    assert ids.correction("mode", "os:link:1", "both") != ids.correction("mode", "os:link:1", "")


# --------------------------------------------------------------------------
# The configuration fingerprint (PLAN.md §2)
# --------------------------------------------------------------------------


def test_the_config_fingerprint_is_stable_across_calls():
    assert config.config_fingerprint() == config.config_fingerprint()


def test_the_config_fingerprint_changes_when_the_configuration_does():
    """*A corrected setting sat unused for a month behind a cached raster.*"""
    doc = json.loads(json.dumps(config.params().doc, default=str))
    assert config.fingerprint_of(doc) == config.fingerprint_of(doc)
    changed = dict(doc)
    changed["__a_setting_that_did_not_exist__"] = 1
    assert config.fingerprint_of(changed) != config.fingerprint_of(doc)


def test_the_fingerprint_does_not_depend_on_key_order():
    """It is a digest of the configuration, not of the file's formatting."""
    assert config.fingerprint_of({"a": 1, "b": 2}) == config.fingerprint_of({"b": 2, "a": 1})


# --------------------------------------------------------------------------
# Stage fingerprints — what licenses a cached answer
# --------------------------------------------------------------------------


def test_every_stage_fingerprint_is_stable_across_calls():
    import rewt.stages  # noqa: F401

    for name in pipeline.PIPELINE.names:
        stage = pipeline.PIPELINE[name]
        upstream = {"upstream_stage": "0" * 16}
        assert stage.fingerprint(upstream) == stage.fingerprint(upstream), (
            f"stage {name!r} fingerprints differently on two consecutive calls, so "
            "its cache can never be trusted"
        )


def test_a_stage_fingerprint_covers_its_upstream():
    """Change a stage and everything downstream of it must rebuild."""
    import rewt.stages  # noqa: F401

    stage = pipeline.PIPELINE[pipeline.PIPELINE.names[-1]]
    assert stage.fingerprint({"x": "a" * 16}) != stage.fingerprint({"x": "b" * 16})


def test_a_stage_fingerprint_does_not_depend_on_upstream_ordering():
    import rewt.stages  # noqa: F401

    stage = pipeline.PIPELINE[pipeline.PIPELINE.names[-1]]
    forward = {"a": "1" * 16, "b": "2" * 16}
    backward = {"b": "2" * 16, "a": "1" * 16}
    assert stage.fingerprint(forward) == stage.fingerprint(backward)


# --------------------------------------------------------------------------
# Declared ordering
# --------------------------------------------------------------------------


def test_deterministic_ordering_is_declared_not_assumed():
    """*Deterministic ordering wherever a result depends on iteration order.*"""
    assert config.param("determinism.order_by"), (
        "conf/params.yml declares no determinism.order_by"
    )
    seed = config.param("determinism.seed")
    assert isinstance(seed, int), (
        f"determinism.seed is {seed!r}; a seed wherever anything is sampled (§2)"
    )


def test_the_database_preserves_insertion_order():
    """`db._prepare` sets this, and a build that lost it would reorder silently."""
    import inspect

    from rewt import db

    source = inspect.getsource(db._prepare)
    assert "preserve_insertion_order" in source, (
        "rewt/db.py no longer sets preserve_insertion_order, so a result that "
        "depends on iteration order can change between builds"
    )


def test_the_working_crs_is_metric():
    """EPSG:27700 throughout; EPSG:4326 only at export (AGENTS.md).

    This project does metric work — buffers, distances, gradients — which needs a
    projected CRS.
    """
    assert config.param("crs.working") == "EPSG:27700", (
        "the working CRS is not EPSG:27700. Metric work in degrees is wrong "
        "everywhere and looks right at the equator."
    )
