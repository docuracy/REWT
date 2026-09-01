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
    assert ids.publisher("link", "watercourse_link.1234") == "os:link/watercourse_link.1234"
    assert ids.is_publisher("os:link/x")
    assert not ids.is_ours("os:link/x")
    assert ids.publisher_id_of("os:link/watercourse_link.1234") == "watercourse_link.1234"
    assert ids.publisher_id_of("rewt:link/abcdef") is None


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


# --------------------------------------------------------------------------
# The fingerprint must cover what the stage can reach, not only what it says
# --------------------------------------------------------------------------


def test_a_stage_fingerprint_covers_the_modules_the_stage_calls():
    """The gap that let a rebuilt identifier scheme go unrebuilt.

    A stage function is a few lines that call into `ids`, `graph`, `topology`,
    `curated`. Hashing only the function's own text means any of those can be
    rewritten without a single fingerprint moving — so the build serves the
    artefact the *previous* code produced, and says it succeeded.

    That is not hypothetical. `ids.publisher` changed from `os:link:{id}` to
    `os:link/{id}` and no fingerprint noticed; the database held 195,689 links
    identified in a scheme the code no longer produced, and the build exited 0.

    The test perturbs a module the stage does not mention and requires the
    fingerprint to move. It restores the file in a `finally` — a test that
    edits the working tree must not leave it edited when it fails.
    """
    import pathlib

    from rewt import cli

    cli._import_stages()
    stage = pipeline.PIPELINE._stages["load"]
    assert "rewt.ids" in pipeline._reachable_modules(stage.fn.__module__), (
        "the load stage no longer reaches rewt.ids; this test is watching the "
        "wrong module and should be pointed at one the stage actually calls"
    )

    caches = (
        pipeline._module_file,
        pipeline._module_digest,
        pipeline._direct_imports,
        pipeline._reachable_modules,
    )

    def clear():
        for cache in caches:
            cache.cache_clear()

    target = pathlib.Path("rewt/ids.py")
    original = target.read_bytes()
    before = stage.source_hash()
    try:
        target.write_bytes(original + b"\n# fingerprint probe\n")
        clear()
        after = stage.source_hash()
    finally:
        target.write_bytes(original)
        clear()

    assert after != before, (
        "editing rewt/ids.py did not change the load stage's fingerprint. A "
        "cached artefact can now be served by code that no longer exists."
    )
    assert stage.source_hash() == before, "the probe did not restore ids.py"


def test_the_reachability_walk_follows_relative_imports():
    """`from . import db` and `from ..config import x` must both be followed.

    Nearly every import in this package is relative, so a walk that only
    understood absolute ones would return almost nothing and would look like it
    was working — the fingerprint would still be *a* hash, just a blind one.
    """
    reach = pipeline._reachable_modules("rewt.stages.audit")
    for expected in ("rewt.db", "rewt.graph", "rewt.config", "rewt.paths"):
        assert expected in reach, f"{expected} not reached from rewt.stages.audit"
    assert all(name.startswith("rewt") for name in reach), (
        f"the walk escaped the package: {[n for n in reach if not n.startswith('rewt')]}"
    )


def test_no_module_but_ids_mints_an_identifier():
    """`rewt/ids.py` is the only place an identifier may be composed.

    The rule existed and was not enforced, so it was broken quietly. `basins.py`
    built `f"rewt:basin-unanchored:{raster_id}"` inline; when the scheme moved to
    slashes, that line kept emitting the colon form and went on expanding to
    `https://w3id.org/rewt/basin-unanchored:1002` — a legal URI resolving to
    nothing. **An identifier minted outside the module does not get the module's
    corrections.**

    Grepping for the prefix in an f-string is crude, and crude is the point: it
    catches the shape of the mistake without needing to understand the code.
    """
    import re

    from rewt import paths

    offenders = []
    pattern = re.compile(r'f"(?:os|rewt):|f\'(?:os|rewt):')
    for path in sorted((paths.ROOT / "rewt").rglob("*.py")):
        if path.name == "ids.py":
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{paths.rel(path)}:{number}: {line.strip()}")

    assert not offenders, (
        "identifiers composed outside rewt/ids.py:\n  " + "\n  ".join(offenders)
    )


# --------------------------------------------------------------------------
# The scheme itself, pinned (PLAN.md §10)
# --------------------------------------------------------------------------

SCHEME = {
    "publisher":  ("os:link/watercourse_link.1234",   lambda i: i.publisher("link", "watercourse_link.1234")),
    "point":      ("rewt:node/0598edb94450",          lambda i: i.point(412345.678, 287654.321)),
    "line":       ("rewt:link/a5f165434027",          lambda i: i.line([[400000.0, 300000.0], [400100.0, 300100.0]])),
    "basin":      ("rewt:basin/000e9ed6b8",           lambda i: i.basin("os:node/C8DD2B03-5398-4053-9767-A8D5ABD58F4B")),
    "unanchored": ("rewt:basin-unanchored/1002",      lambda i: i.basin_unanchored(1002)),
    "derived":    ("rewt:link/58f95877bcd6",          lambda i: i.derived("os:link/1", "link", "0.000,0.000;5.000,5.000")),
    "correction": ("rewt:correction-reversal/bb343b1986", lambda i: i.correction("reversal", "os:link/1", "because")),
}


def test_the_identifier_scheme_has_not_moved():
    """§10: *a derived identifier inherits every instability of what it was
    derived from* — including instability we introduce.

    The freeze (D-054) stops Ordnance Survey moving identifiers under us. Nothing
    stopped *us*. Changing `ids.publisher` from `os:link:` to `os:link/` this
    morning also changed every anchored basin id, because a basin id is a digest
    of its outlet node's id: `rewt:basin/d5921800ed` became `rewt:basin/000e9ed6b8`
    for the same basin. Not a rename — a different value, with nothing about the
    new string to say the old one ever meant anything.

    That went unnoticed through a full build. These golden values make the next
    one loud: change a composition rule and this fails, naming what moved, before
    the renumbering reaches a published file or anybody's stored reference.

    **A failure here is not a bug in this test.** It means the scheme changed. If
    that was deliberate, update the value and record the change as a decision —
    every identifier this project has ever published is now different.
    """
    from rewt import ids

    moved = {
        name: (expected, fn(ids))
        for name, (expected, fn) in SCHEME.items()
        if fn(ids) != expected
    }
    assert not moved, "the identifier scheme moved:\n" + "\n".join(
        f"  {name}: was {was!r}, now {now!r}" for name, (was, now) in moved.items()
    )
