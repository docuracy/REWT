"""Derived artefacts, tested on their distribution and not only on their validity.

This file exists because of a delineation that passed every check there was. Burning
tidal water into the DEM produced **1,123 basins — a plausible count for a coastline
— from a conditioned surface with a sensible elevation range, and one of those basins
held 88% of the country.** Nothing about validity catches that: the raster was finite,
in range, and correctly projected; the basin count was reasonable; the total area was
reasonable. The only tell was the shape of the distribution, a median of 0.1 km²
against a largest of 181,672.

So the rule this file applies is: **a total is not a check.** A derived artefact that
is right in aggregate and wrong in distribution is the failure this project keeps
meeting — §6 makes the same argument about the audit, where a national 97% hides a
basin at 40%, and the basin at 40% is the entire finding.

Every threshold here is stated against a measurement, with the headroom written down,
so that a future failure can be told from a change of scale.
"""

from __future__ import annotations

import pytest

from conftest import require_tables


pytestmark = pytest.mark.db


# Measured on the first delineation that ran clean: 714 basins, 174,382 km² in total,
# largest 11,827 km² (River Aire) at 6.8% of the total, median 12.3 km², none under
# 1 km². The failed delineation scored 88% on the first of these and 0.1 km² on the
# third. Thresholds sit far enough from the good run to survive a change of scale and
# nowhere near far enough to admit the bad one.
MAX_SHARE_IN_ONE_BASIN = 0.25          # measured 0.068; the failure was 0.88
MIN_MEDIAN_AREA_KM2 = 1.0              # measured 12.3; the failure was 0.1
MIN_BASINS = 50                        # measured 714
MAX_BASINS = 20_000                    # a delineation this fragmented is noise


@pytest.fixture(scope="module")
def basins(con):
    require_tables(con, "basin")
    row = con.execute(
        "SELECT count(*), sum(area_km2), max(area_km2), median(area_km2) FROM basin"
    ).fetchone()
    if not row or not row[0]:
        pytest.skip("the basin table is empty; the basins stage has not run")
    count, total, largest, median = row
    return {"count": count, "total": total, "largest": largest, "median": median}


def test_no_single_basin_holds_most_of_the_country(basins, con):
    """The one that got past everything else.

    A basin holding most of the delineated area means the conditioning has merged
    catchments that no watershed separates — which is the §4.1 failure in raster
    form. *A shared estuary is not a shared catchment*, and neither is a flooded
    surface.
    """
    share = basins["largest"] / basins["total"]
    if share > MAX_SHARE_IN_ONE_BASIN:
        worst = con.execute(
            "SELECT label, outlet_node, round(area_km2, 1) FROM basin "
            "ORDER BY area_km2 DESC LIMIT 1"
        ).fetchone()
        # Report at the place, not only in the total (AGENTS.md).
        pytest.fail(
            f"one basin holds {share:.1%} of {basins['total']:,.0f} km² across "
            f"{basins['count']:,} basins: {worst[0]!r} at {worst[2]:,.1f} km², "
            f"outlet {worst[1]}. A single basin this large is catchments merged by "
            "the conditioning, not a catchment."
        )


def test_the_median_basin_is_not_a_sliver(basins):
    """Slivers plus one blob is what a flooded surface delineates.

    The count looks right and the total looks right; what gives it away is that the
    typical basin has become a fragment.
    """
    assert basins["median"] > MIN_MEDIAN_AREA_KM2, (
        f"the median basin is {basins['median']:.2f} km² across "
        f"{basins['count']:,} basins, with the largest at {basins['largest']:,.1f} "
        "km². A delineation of slivers around one blob has a plausible count and a "
        "plausible total and is wrong everywhere."
    )


def test_the_basin_count_is_of_the_right_order(basins):
    """Not a tight bound — a loose one, to catch a delineation that has collapsed."""
    assert MIN_BASINS <= basins["count"] <= MAX_BASINS, (
        f"{basins['count']:,} basins. Below {MIN_BASINS} the delineation has merged "
        f"the country; above {MAX_BASINS:,} it has shattered it."
    )


def test_every_basin_has_an_area(con):
    """`area_km2` is NOT NULL in the schema; this checks it is also meaningful."""
    require_tables(con, "basin")
    broken = con.execute(
        "SELECT basin_id, label, area_km2 FROM basin "
        "WHERE area_km2 IS NULL OR area_km2 <= 0 ORDER BY basin_id LIMIT 10"
    ).fetchall()
    assert not broken, (
        "basins with no area: " + "; ".join(f"{b[0]} ({b[1]})" for b in broken)
    )


def test_a_basin_without_an_outlet_is_the_coastal_case_and_not_the_rule(con):
    """*Count that case, do not drop it silently* (§6).

    A basin whose outlet could not be anchored to a network node is expected and is
    not a defect: **where a DEM is masked over the sea the outlet sits on nodata,
    which is itself confirmation that the component reaches tidal water.** The id
    scheme names them `rewt:basin-unanchored/…`, which is the right way to carry the
    case forward.

    What would be a defect is anchoring failing wholesale, because a basin with no
    outlet cannot answer §6's question — *what share of this basin can reach its own
    sea?* — as a complete question. Measured on the first clean delineation: 245 of
    714 basins unanchored, and 108 of the 343 in scope, covering 48,452 km². So the
    bound is set at half the in-scope basins, well above that and far below a
    collapse.
    """
    require_tables(con, "basin")
    total, unanchored, area = con.execute(
        "SELECT count(*), "
        "count(*) FILTER (WHERE outlet_node IS NULL), "
        "coalesce(sum(area_km2) FILTER (WHERE outlet_node IS NULL), 0) "
        "FROM basin WHERE in_scope"
    ).fetchone()
    if not total:
        pytest.skip("no basin is in scope; the scope rule has not run")
    share = unanchored / total
    assert share < 0.5, (
        f"{unanchored:,} of {total:,} in-scope basins have no outlet node "
        f"({share:.1%}, {area:,.0f} km²). A basin with no outlet cannot answer what "
        "share of itself reaches its own sea, and at this rate the anchoring has "
        "failed rather than met the coast."
    )


def test_scope_is_a_decision_with_a_reason(con):
    """*scope_reason* is why, in words: this is a decision, not a flag (§4.1).

    Nothing is deleted — out-of-scope basins are kept so the rule can be changed
    without re-reading the source, and "what was excluded, and was it right?" stays
    answerable. That is only true if each one says why.
    """
    require_tables(con, "basin")
    silent = con.execute(
        "SELECT count(*) FROM basin "
        "WHERE scope_reason IS NULL OR trim(scope_reason) = ''"
    ).fetchone()[0]
    assert not silent, (
        f"{silent:,} basins carry no scope_reason, so what was excluded cannot be "
        "checked"
    )


def test_the_network_is_of_the_order_the_plan_measured(con):
    """§6's calibration: *if these do not match, the loader is wrong.*

    PLAN.md §6 gives 192,865 links for Great Britain as shipped and about 198,000
    explicit nodes. This is a loose order-of-magnitude bound and not the calibration
    itself — the audit stage checks the figures properly, by form. What it catches is
    a loader that half-ran.
    """
    require_tables(con, "link", "node")
    links = con.execute("SELECT count(*) FROM link").fetchone()[0]
    nodes = con.execute("SELECT count(*) FROM node").fetchone()[0]
    assert 150_000 < links < 250_000, (
        f"{links:,} links, against §6's 192,865 for Great Britain as shipped. "
        "If the count is wrong the loader is wrong and nothing downstream is worth "
        "looking at."
    )
    assert 150_000 < nodes < 260_000, (
        f"{nodes:,} nodes, against §6's roughly 198,000"
    )


def test_this_project_has_introduced_no_self_loop(con):
    """*Any cycles that appear later were introduced by your own repairs* (§6).

    A link from a node back to itself is a cycle of one, and a closed loop with no
    exit strands everything above it while staying invisible in any total.

    The survey ships five, all `origin = 'survey'`, all inlandRiver, 326 m to 2,996 m,
    one of them Great Mussels Sewer — consistent with §6's statement that OS Open
    Rivers has no cycle of 10 km or more. Those are the survey's, and Stage 1 does not
    delete a geometry to correct it. What must not happen is this project adding one.
    """
    require_tables(con, "link")
    ours = con.execute(
        "SELECT link_id, publisher_id, origin, round(length_m, 1) FROM link "
        "WHERE from_node = to_node AND origin <> 'survey' ORDER BY length_m DESC"
    ).fetchall()
    assert not ours, (
        "self-loops this project created: "
        + "; ".join(f"{r[0]} ({r[2]}, {r[3]:,.1f} m)" for r in ours)
    )


def test_the_surveys_own_self_loops_are_still_the_five_we_know_about(con):
    """A known figure, so a change in it is visible rather than absorbed.

    Not an assertion that five is correct — it is what OS ships. If this fails
    because the count moved, the survey was reissued or the loader changed, and
    either is worth a look before anything downstream is trusted.
    """
    require_tables(con, "link")
    count = con.execute(
        "SELECT count(*) FROM link WHERE from_node = to_node AND origin = 'survey'"
    ).fetchone()[0]
    assert count == 5, (
        f"the survey now ships {count:,} self-looping links, not the 5 measured on "
        "OS Open Rivers issue 2026-04. Check the issue before trusting the audit."
    )


def test_the_in_scope_population_has_a_length_for_every_link(con):
    """`in_scope_link` is now the one definition of the in-scope network, so a row it
    cannot measure is a row four published figures silently disagree about.

    **D-079's remedy, guarded.** The view resolves length as
    `COALESCE(l.length_m, r.length_m)` over left joins to `link` and `repair_link`. A
    `link_scope` row naming an id in NEITHER table survives both joins, arrives with a
    null length, and is counted by `count(*)` while contributing nothing to
    `sum(length_m)` — so the link count and the kilometre total would come apart with
    nothing to say they had. It would also be labelled `is_repair`, because that column
    is `l.link_id IS NULL` and an absent row satisfies it exactly as a repair link does.

    Nothing suggests such a row exists today. The test is here because the view is new
    and four audit files, the calibration table against PLAN.md §4.1 and the release
    notes now read from it, so the cost of it being quietly wrong went up when the
    duplication that would have contradicted it went away. **One definition is right,
    and it is also the removal of the disagreement that caught the last defect.**

    Written by rewt-c1, who holds no database connection and could not run it: it is
    `db`-marked and first runs inside `rewt check` on a machine that has built.
    """
    from conftest import require_tables, table_names

    require_tables(con, "link_scope", "link", "repair_link", "retirement")
    if "in_scope_link" not in table_names(con):
        from rewt import schema

        schema.in_scope_view()

    orphans = con.execute(
        "SELECT count(*) FROM in_scope_link WHERE length_m IS NULL"
    ).fetchone()[0]
    assert orphans == 0, (
        f"{orphans:,} row(s) of `in_scope_link` have no length: their `link_scope` id "
        "is in neither `link` nor `repair_link`. `count(*)` counts them and "
        "`sum(length_m)` does not, so the published link count and kilometre total are "
        "measuring different populations — and each is labelled `is_repair`, since "
        "that column asks only whether the `link` row is absent."
    )
