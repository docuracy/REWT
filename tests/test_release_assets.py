"""The release's assets, checked against each other on every build.

`rewt release-check` already asks these questions well. This file exists so they are
asked whenever anything else is, rather than only when somebody is cutting a release
— *if a step only runs when a person remembers to run it, it is not part of the
build* (AGENTS.md), and a release is exactly the moment nobody wants to discover a
gap.

The class these guard is the one this repository kept meeting: **two artefacts, each
internally consistent, never compared.** The packaged tar against the tiles the
viewer serves, the published attribution against the manifest it is generated from,
the audit against the network published beside it. None of them is findable by a gate
that compares the build with itself, and each was found by someone holding the two
things at once.

The tar was the sharpest instance. `rewt.tiles.pack()` existed and was called by no
code path, so `published/viewer-data.tar` was whatever had last been built by hand
and would have stayed that way through any number of rebuilds — and the release would
have attached it without complaint.
"""

from __future__ import annotations

import pytest

from rewt import paths

pytestmark = pytest.mark.published


@pytest.fixture(scope="module")
def release():
    from rewt import release as module

    if not paths.PUBLISHED.is_dir() or not any(paths.PUBLISHED.iterdir()):
        pytest.skip(
            f"{paths.rel(paths.PUBLISHED)} is empty; the export stage has not run"
        )
    return module


def test_the_viewer_data_drift_check_detects_a_mismatch(release, tmp_path, monkeypatch):
    """The mechanism, not the moment — and the moment belongs to `release-check`.

    Asserting the *current* tar against the *current* tiles cannot live in the build.
    `rewt build` does not produce the tar; only `rewt viewer-data` repacks it. So the
    build would fail, every time the data changed, for a disagreement it has no way
    to resolve — a test that is right about the world and wrong about whose job it
    is. That assertion lives in `release-check`, where a stale tar is a reason not
    to proceed.

    What belongs here is that the checker works, because a checker that has never
    caught anything is indistinguishable from one that cannot. Three cases, and the
    third is the one that matters: **same size, different bytes**. A size comparison
    passes it, and that is exactly how `summary.json` slipped through.
    """
    import tarfile

    from rewt import paths as paths_module, tiles

    def lay_out(packed: dict[str, bytes], built: dict[str, bytes]):
        published, out = tmp_path / "published", tmp_path / "out"
        published.mkdir(exist_ok=True)
        out.mkdir(exist_ok=True)
        for name, data in built.items():
            (out / name).write_bytes(data)
        staged = tmp_path / "staged"
        staged.mkdir(exist_ok=True)
        with tarfile.open(published / "viewer-data.tar", "w") as tar:
            for name, data in packed.items():
                member = staged / name
                member.write_bytes(data)
                tar.add(member, arcname=name)
        monkeypatch.setattr(paths_module, "PUBLISHED", published)
        monkeypatch.setattr(tiles, "OUT", out)

    same = {"summary.json": b'{"links": 1}'}
    lay_out(same, dict(same))
    assert release.viewer_data_drift() == [], "agreeing artefacts reported as drift"

    lay_out({"summary.json": b'{"links": 1}'}, {"summary.json": b'{"links": 100}'})
    assert release.viewer_data_drift(), "a size difference was not detected"

    # The case that makes the digest worth its cost.
    lay_out({"summary.json": b'{"links": 1}'}, {"summary.json": b'{"links": 2}'})
    drift = release.viewer_data_drift()
    assert drift, (
        "two files of the same size and different content were reported as agreeing. "
        "This is how summary.json passed every check while the tar was ninety "
        "minutes and 35 MB out of date."
    )

    lay_out({"summary.json": b"{}", "gone.json": b"{}"}, {"summary.json": b"{}"})
    assert release.viewer_data_drift(), "a file in the tar and no longer built passed"


def test_the_drift_checks_are_wired_into_the_release(release):
    """A check called by nothing fails exactly as silently as no check at all.

    `rewt.tiles.pack()` existed, was called by no code path, and left the tar
    frozen at whatever had last been built by hand — through any number of
    rebuilds, with the release attaching it without complaint. A drift function
    nothing calls has the identical failure mode, and it is invisible for the same
    reason: everything it would have caught goes on passing.

    So the wiring is asserted, crudely and on purpose, in the same spirit as the
    grep for identifiers minted outside `ids.py`.
    """
    import inspect

    from rewt import cli

    source = inspect.getsource(cli.release_check_cmd)
    for name in ("viewer_data_drift", "attribution_drift", "audit_is_its_own_asset"):
        assert name in source, (
            f"release.{name} is not called by `rewt release-check`. A check nothing "
            "calls is not a check — rewt.tiles.pack() is the worked example."
        )


def test_the_published_attribution_agrees_with_the_manifest(release):
    """*Provenance travels as a pointer.*

    Two renderings of one obligation, generated by different code on different
    schedules from a single manifest. A short attribution may never attribute less
    than `conf/sources.yml` does, and the only way to know it does not is to compare
    them.
    """
    drift = release.attribution_drift()
    assert not drift, (
        "the published attribution and the manifest disagree:\n  "
        + "\n  ".join(drift)
    )


def test_the_audit_is_attached_in_its_own_right(release):
    """*The audit, machine-readable and human-readable, per basin and national* (§7).

    An audit reachable only by unpacking a tar of map tiles is an audit nobody
    checking a claim will open.
    """
    assert release.audit_is_its_own_asset(), (
        "the audit is not attached as its own asset, so a reader has to unpack "
        "something else to reach the evidence for the headline figure"
    )


def test_every_declared_asset_exists(release):
    """A release manifest naming a file that is not there fails at the worst moment."""
    missing = [
        f"{path} ({label})"
        for path, label in release.assets()
        if not path.exists()
    ]
    assert not missing, (
        "the release declares assets that do not exist: " + ", ".join(missing)
    )
