"""Every identifier in `data/curated/` resolves against the database.

This is the test AGENTS.md and PLAN.md §7 and §9 all name explicitly, and it is here
because of a specific failure rather than a general principle:

    A correction that references a feature by id does nothing, silently, when the id
    is wrong — while the stage reports it applied. Twice in one day, once through a
    column nothing reads, so the error was invisible.

So the check is not "did the stage say it worked". It is: take every identifier a
human authored, look it up, and name every one that is not there.
"""

from __future__ import annotations

import pytest

from conftest import require_tables

from rewt import config, curated, paths, pipeline


@pytest.fixture(scope="module")
def resolved(con, curated_judgements):
    require_tables(con, "link", "node")
    return curated.resolve(curated_judgements)


@pytest.mark.db
def test_every_curated_identifier_resolves(resolved):
    """The one in the definition of done. Name every failure; do not count them."""
    failures = [
        f"{j.kind} {j.subject!r} ({j.source_file} row {j.source_row}): {why}"
        for j, _, why in resolved
        if why
    ]
    assert not failures, (
        f"{len(failures)} curated identifier(s) do not resolve against the database. "
        "A mistyped id does nothing while the stage reports success:\n  "
        + "\n  ".join(failures)
    )


@pytest.mark.db
def test_non_connector_judgements_resolve_to_something(resolved):
    """A resolution is a value, not the absence of an error.

    A connector resolves to nothing by id on purpose — it is defined by its geometry,
    not by any link id (§5) — so it is the one kind excluded here.
    """
    unresolved = [
        f"{j.kind} {j.subject!r} ({j.source_file} row {j.source_row})"
        for j, resolved_id, why in resolved
        if j.kind != "connector" and why is None and not resolved_id
    ]
    assert not unresolved, (
        "these judgements reported no failure and yet resolved to nothing, which is "
        "the invisible case: " + ", ".join(unresolved)
    )


@pytest.mark.db
def test_junctions_name_a_target_that_exists(con, curated_judgements):
    """A junction merges a node onto a link, and must name both.

    `curated.resolve` already refuses a junction with no target; this checks the
    target end independently, because the failure it guards against is a correction
    that resolves its subject and then acts on nothing.
    """
    require_tables(con, "link")
    known = {
        r[0]
        for r in con.execute(
            "SELECT publisher_id FROM link WHERE publisher_id IS NOT NULL"
        ).fetchall()
    }
    problems = []
    for j in curated_judgements:
        if j.kind != "junction":
            continue
        target = j.fields.get("target_publisher_id") or j.fields.get("target")
        if not target:
            problems.append(f"{j.source_file} row {j.source_row}: no target link named")
        elif target not in known:
            problems.append(
                f"{j.source_file} row {j.source_row}: target link {target!r} "
                "is not in the database"
            )
    assert not problems, "\n  ".join(["junction targets:"] + problems)


@pytest.mark.db
def test_every_judgement_reaches_the_correction_table(con, curated_judgements):
    """What was authored is what was recorded.

    The correction table is what the exporter publishes, so a judgement that never
    arrives in it is a judgement the reader cannot see — and the difference between
    the survey and the published network stops being inspectable (§7).
    """
    require_tables(con, "correction")
    if not curated_judgements:
        pytest.skip("data/curated/ holds no judgements yet; nothing to record")
    recorded = {
        r[0] for r in con.execute("SELECT correction_id FROM correction").fetchall()
    }
    missing = [
        f"{j.kind} {j.subject!r} ({j.source_file} row {j.source_row})"
        for j in curated_judgements
        if j.correction_id not in recorded
    ]
    assert not missing, (
        "authored judgements absent from the correction table: " + ", ".join(missing)
    )


@pytest.mark.db
def test_no_correction_was_skipped_without_a_reason(con):
    """Name every skip (AGENTS.md).

    Eleven of twenty-five once did nothing silently, including the largest single
    defect in the country. An unapplied correction is allowed; an unapplied
    correction with nothing said about it is not.
    """
    require_tables(con, "correction")
    silent = con.execute(
        "SELECT kind, subject, source_file, source_row FROM correction "
        "WHERE NOT applied AND (skip_reason IS NULL OR trim(skip_reason) = '') "
        "ORDER BY kind, source_file, source_row"
    ).fetchall()
    assert not silent, (
        "corrections that were not applied and do not say why:\n  "
        + "\n  ".join(f"{k} {s} ({f} row {r})" for k, s, f, r in silent)
    )


# --------------------------------------------------------------------------
# That the validation runs in the build at all — which needs no database
# --------------------------------------------------------------------------


def test_curated_validation_is_part_of_the_build():
    """*A test that runs in the build*, not a script someone remembers to run.

    Three properties, each of which would silently disarm the check above:
    the stage is registered; it never serves a cached answer about hand-edited
    files; and an unresolved identifier fails the build rather than warning.
    """
    import rewt.stages  # noqa: F401  (registers every stage)

    assert "curated" in pipeline.PIPELINE, (
        "no 'curated' stage is registered, so nothing validates the curated "
        f"identifiers during a build. Registered: {', '.join(pipeline.PIPELINE.names)}"
    )
    stage = pipeline.PIPELINE["curated"]
    assert stage.always, (
        "the curated stage is cacheable. The files under data/curated/ are "
        "hand-edited, so a cached answer about them can be stale the moment "
        "someone saves one."
    )
    assert {"link", "node"} <= set(stage.reads), (
        "the curated stage does not declare that it reads link and node, so the "
        f"build may run it before there is anything to validate against: {stage.reads}"
    )
    assert config.param("repair.fail_on_unresolved") is True, (
        "conf/params.yml sets repair.fail_on_unresolved false. An unresolved "
        "identifier would then be a log line, which is precisely how the error was "
        "invisible before."
    )


def test_curated_directory_is_where_the_judgements_live():
    """data/curated/ is a source of truth and is committed; it is not derived."""
    assert paths.CURATED.is_dir(), f"{paths.rel(paths.CURATED)} does not exist"
    unexpected = sorted(
        p.name
        for p in paths.CURATED.iterdir()
        if p.is_file()
        and not p.name.startswith(".")          # .gitkeep holds the directory in git
        and p.name not in set(curated.CLASSES.values())
        and p.name != "README.md"
    )
    assert not unexpected, (
        f"unrecognised files in {paths.rel(paths.CURATED)}: {', '.join(unexpected)}. "
        f"One diffable file per correction class (§7): {', '.join(sorted(curated.CLASSES.values()))}"
    )


@pytest.mark.db
def test_the_identifier_check_is_not_vacuous_after_a_build(con):
    """A skip after a successful build is a silent pass, and that is the bug.

    Everything above skips when the tables it needs are absent, which is right
    before a build and wrong after one: a suite that skipped its way to green
    inside `rewt check` would report that the curated identifiers had been
    validated when nothing had looked at them.

    So this asks the run ledger what the build believes it did. If `load` recorded
    success, `link` and `node` exist, and the skips above cannot be reached.
    """
    from conftest import table_names

    if "stage_run" not in table_names(con):
        pytest.skip(
            "no stage_run ledger, so no build has been recorded in this database"
        )
    ran = {
        row[0]
        for row in con.execute(
            "SELECT stage FROM stage_run WHERE status = 'ok'"
        ).fetchall()
    }
    if "load" not in ran:
        pytest.skip(
            f"the load stage has not recorded a successful run. Recorded: "
            f"{', '.join(sorted(ran)) or 'nothing'}"
        )
    missing = sorted({"link", "node"} - table_names(con))
    assert not missing, (
        f"the ledger records load as 'ok' and yet {', '.join(missing)} "
        f"{'is' if len(missing) == 1 else 'are'} not in the database. Every check "
        "that validates a curated identifier against the network would have skipped "
        "silently, and the build would have called that a pass."
    )
