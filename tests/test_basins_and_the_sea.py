"""A catchment may not contain the sea.

**The basin delineation swallowed the estuaries.** Reported by rewt-46 on 3 September
2026 and re-derived twice since: the tidal surface was not removed before delineation,
so every watercourse entering a common firth accumulates to one sink and the firth ends
up inside the resulting catchment. `River Nith` is 9,655 km² against a real catchment
near 1,230 and encloses the mid Solway and the Firth of Clyde; `River Earn` is 4,176 km²
and encloses open sea off Arbroath. It is not a Scottish fault — `River Deben` contains
sea off its own mouth and `River Lea` contains the mid Thames estuary.

**Nothing reported it.** `outletless_basins.unexplained` is 0, every stage passes and
`release-check` called the build green. The per-basin table is the deliverable of the
audit (PLAN.md §6: *a national 97% hides a basin at 40%, and the basin at 40% is the
entire finding*) and its denominators are wrong wherever a polygon includes sea.

These read `published/` only — the network GeoPackage and the audit's own per-basin
table — so they hold no database lock and any session can re-run them.

**There is no threshold here, and that is deliberate.** The obvious test is "no basin
may enclose more than N km of sea", and the data does not support any N. Clipped to the
polygon, the smallest enclosures are 50.0, 70.7, 100.0 and 141.4 m — the 50 m
delineation cell and its diagonal — and the distribution is continuous upward from
there, the largest gap in the bottom 60 being 148.6 m. A basin whose outlet reaches the
coast legitimately touches the sea network at its mouth, and that case clips to a cell
or two rather than to zero, so "touches" cannot be separated from "contains" by a
length alone. Both tests below therefore compare the sea against something else that
was measured, rather than against a constant somebody chose.

**Measured against this repository's own sea network**, which `rules/0001.md` R-01 says
is probably mis-specified — the proposal is to define the coast by OS Mean High Water
instead. When that lands these numbers move, and the tests should be re-derived rather
than re-baselined.
"""

from __future__ import annotations

import json

import pytest

from rewt import paths

pytestmark = pytest.mark.published

NETWORK = paths.PUBLISHED / "rewt_stage1_network.gpkg"
BASIN_REACH = paths.PUBLISHED / "audit" / "basin_reach.json"

# Measured on v0.2.0-alpha: the sea network enclosed by all in-scope basin polygons,
# clipped to them. A measurement, not a target — see the test that uses it.
ENCLOSED_SEA_KM = 2896.9


@pytest.fixture(scope="module")
def sea_inside_basins():
    """Sea network km enclosed by each in-scope basin, clipped to the polygon.

    Clipped, not summed whole. Summing the full length of every route that intersects
    a polygon counts water far outside it — 24,205.5 km by that reading against
    2,896.9 km actually enclosed, an eightfold difference — and the question is what
    the polygon contains.
    """
    geopandas = pytest.importorskip("geopandas", reason="geopandas reads the GeoPackage")

    for path in (NETWORK, BASIN_REACH):
        if not path.exists():
            pytest.skip(f"{paths.rel(path)} does not exist; the export stage has not run")

    basins = geopandas.read_file(NETWORK, layer="basin", engine="pyogrio")
    in_scope = basins[basins["in_scope"]][["basin_id", "label", "area_km2", "geometry"]]
    if not len(in_scope):
        pytest.skip("no basin is in scope; the delineation has not run")

    sea = geopandas.read_file(NETWORK, layer="sea_route", engine="pyogrio")
    if not len(sea):
        pytest.skip(
            "the published GeoPackage has no sea_route layer. The sea network is "
            "exported only when the sea stage has built it (rewt/stages/export.py)."
        )

    clipped = geopandas.overlay(
        sea[["link_id", "geometry"]], in_scope, how="intersection", keep_geom_type=True
    )
    clipped["sea_km"] = clipped.geometry.length / 1000
    per_basin = clipped.groupby("basin_id", dropna=False)["sea_km"].sum()

    # `dropna=False`, and it is not a nicety: 76 of the 334 in-scope basins carry no
    # label, and grouping on a null key silently drops the row. That is how the first
    # reading of this measurement reported 87 basins where there are 110 — a selector
    # that excluded a quarter of the population and returned a plausible total (D-070,
    # D-081).
    rows = {r["basin_id"]: r for r in json.loads(BASIN_REACH.read_text(encoding="utf-8"))}
    meta = in_scope.set_index("basin_id")
    return [
        {
            "basin_id": basin_id,
            "label": meta.at[basin_id, "label"] or "(no label)",
            "area_km2": float(meta.at[basin_id, "area_km2"]),
            "sea_km": float(sea_km),
            # A basin with no audit row has no network in it at all, which is a
            # stronger form of the same fault, not a reason to skip it. Four of the
            # 110 are in that state and an inner join loses them.
            "network_km": float(rows.get(basin_id, {}).get("km", 0.0)),
        }
        for basin_id, sea_km in per_basin.items()
    ]


def test_no_in_scope_basin_holds_more_sea_than_river(sea_inside_basins):
    """The threshold-free statement of the fault: a catchment that is more sea than
    river is not a catchment on any definition.

    It needs no constant, no tolerance and no judgement about where a mouth ends. It
    is also a floor rather than a full account — a basin can enclose 480 km of sea and
    still hold more river than sea, and `River Earn` does — so it is deliberately the
    weakest claim that cannot be argued with, and the companion test below carries the
    rest.

    **The network figure is the audit's own per-basin length**, which D-079 records as
    possibly summed over the naive in-scope population (`link_scope JOIN link`, which
    loses the 2,435 links living in `repair_link`). If that is corrected this set may
    change. That is a reason to look again, not to weaken the comparison.
    """
    drowned = sorted(
        (b for b in sea_inside_basins if b["sea_km"] > b["network_km"]),
        key=lambda b: b["sea_km"] - b["network_km"],
        reverse=True,
    )
    assert not drowned, (
        f"{len(drowned)} in-scope basin(s) enclose more sea network than river "
        f"network. The tidal surface is not being removed before delineation, so a "
        f"shared estuary accumulates to one sink and the firth falls inside the "
        f"catchment (PLAN.md §4.1, occurring in the topographic delineation rather "
        f"than in the component test it was written about). Their per-basin "
        f"reachability denominators are wrong:\n      "
        + "\n      ".join(
            f"{b['label']} ({b['basin_id']}): {b['sea_km']:,.1f} km of sea against "
            f"{b['network_km']:,.1f} km of river, in {b['area_km2']:,.1f} km²"
            for b in drowned
        )
    )


def test_the_sea_enclosed_by_the_basins_is_not_growing(sea_inside_basins):
    """The whole quantity, pinned to what was measured rather than to a limit.

    2,896.9 km of the 13,117.3 km sea network lies inside an in-scope basin polygon.
    There is no defensible non-zero value for this — the right answer is nearly zero,
    reached only by removing the tidal surface before delineation — so this fails when
    it GROWS and not when it falls. A fall is the repair working, and the number here
    should then be lowered to whatever was achieved, so the next regression is caught
    against the improved figure and not against the old damage.

    Recorded rather than asserted because a delineation change can move it in either
    direction for good reasons: it is a tripwire on a known fault, and it says so.
    """
    total = sum(b["sea_km"] for b in sea_inside_basins)
    assert total <= ENCLOSED_SEA_KM + 0.5, (
        f"in-scope basin polygons now enclose {total:,.1f} km of the sea network, "
        f"against {ENCLOSED_SEA_KM:,.1f} km when this was measured. The delineation "
        f"has swallowed more sea than it had. If a change to the sea network or to "
        f"the delineation makes this legitimate, re-derive the figure and say in this "
        f"docstring what moved it — R-01 (OS Mean High Water as the coast) is the "
        f"change most likely to."
    )
