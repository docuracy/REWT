"""Stage: the terrain screen on flow direction, and the component-root test.

Two jobs, and PLAN.md §5 is blunt that the DEM is good at one of them.

**Direction: a screen, never an authority.** Sampling the raw 50 m surface at both ends
of every in-scope link produces a table whose last row is the useful one — links where
the DEM says the water runs *uphill* by more than the error bar. That is a human-sized
list worth adjudicating one by one. **Never let it flip a link on its own, and never
report a direction correction as made on terrain evidence when the evidence was inside
the error bar** (D-007).

**And look where the DEM goes quiet.** Terrain 50 posts every 50 m with an RMSE of
about 4 m, so a fall inside ±4 m is inside its own error bar. It screens the uplands,
where you least need it, and is silent on the levels, where you most do.

**The component-root test** (§6, D-009) is the other job. Testing whether each
component's flow direction drains to its lowest node does *not* pay as a fault
detector — reversing one link mid-tree does not move the component's outlet, so the
test is blind to the common fault. What it is genuinely for is establishing that **a
component's lowest node is a trustworthy root**, which is what licenses orienting a
spanning tree toward it to give a level canal a direction that no gradient can.

The surface sampled here is the **unconditioned** one. A burned DEM has the network's
own direction stamped into it, so checking direction against it proves nothing;
`rewt.raster` refuses to open the conditioned surface for this.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config, db, graph, paths, raster
from ..pipeline import PIPELINE, artefact
from ..report import Finding, Report, log

LINK_GRADIENT = artefact("link_gradient")
COMPONENT_ROOT = artefact("component_root")

# PLAN.md §5's measured screen, for comparison. Measured on the predecessor's in-scope
# set, so a difference of a few per cent is expected; the shape is the thing to check.
PLAN_SCREEN = {
    "falls more than 4 m — clearly agrees": (54747, 0.449),
    "falls 0.5-4 m — agrees, weakly": (29953, 0.245),
    "within +/-0.5 m — says nothing at all": (29639, 0.243),
    "rises 0.5-4 m — disagrees, weakly": (6963, 0.057),
    "rises more than 4 m — clearly disagrees": (757, 0.006),
}
PLAN_MUTE_BY_FORM = {
    "inlandRiver": 0.466, "canal": 0.823, "tidalRiver": 0.891, "lake": 0.918
}


def _band(fall: np.ndarray, weak: float, clear: float) -> np.ndarray:
    """Classify each link by what the DEM says about its stated direction."""
    out = np.full(len(fall), "no reading", dtype=object)
    known = np.isfinite(fall)
    out[known & (fall > clear)] = "falls more than 4 m — clearly agrees"
    out[known & (fall > weak) & (fall <= clear)] = "falls 0.5-4 m — agrees, weakly"
    out[known & (np.abs(fall) <= weak)] = "within +/-0.5 m — says nothing at all"
    out[known & (fall < -weak) & (fall >= -clear)] = "rises 0.5-4 m — disagrees, weakly"
    out[known & (fall < -clear)] = "rises more than 4 m — clearly disagrees"
    return out


@PIPELINE.stage(
    "screen",
    "terrain screen on direction, and the component-root test — neither decides anything",
    reads=["terrain50_unconditioned", "edge", "node", "link_scope"],
    writes=["link_gradient", "component_root"],
    params=["terrain", "lidar"],
    sources=["os_terrain_50"],
)
def run() -> dict:
    p = config.params()
    con = db.get()
    report = Report("screen")

    weak = float(p("terrain.screen_bands_m.weak"))
    clear = float(p("terrain.screen_bands_m.clear_agree"))

    # The sampler refuses a conditioned surface for this question (D-007).
    raster.assert_unconditioned(raster.UNCONDITIONED)

    ends = db.df(
        """
        SELECT e.link_id, e.form, e.length_m,
               fu.easting AS up_e, fu.northing AS up_n,
               td.easting AS down_e, td.northing AS down_n,
               s.in_scope
        FROM edge e
        JOIN node fu ON fu.node_id = e.from_node
        JOIN node td ON td.node_id = e.to_node
        LEFT JOIN link_scope s ON s.link_id = e.link_id
        ORDER BY e.link_id
        """
    )

    with raster.open_unconditioned() as ds:
        up = raster.sample_points(ds, ends["up_e"].to_numpy(), ends["up_n"].to_numpy())
        down = raster.sample_points(ds, ends["down_e"].to_numpy(), ends["down_n"].to_numpy())

    fall = up - down          # positive means the water runs downhill as stated
    ends["up_m"] = up
    ends["down_m"] = down
    ends["fall_m"] = fall
    ends["verdict"] = _band(fall, weak, clear)

    con.execute("DROP TABLE IF EXISTS link_gradient")
    with db.registered("_grad_in", ends[
        ["link_id", "form", "length_m", "in_scope", "up_m", "down_m", "fall_m", "verdict"]
    ]):
        con.execute("CREATE TABLE link_gradient AS SELECT * FROM _grad_in ORDER BY link_id")

    scoped = ends[ends["in_scope"].fillna(False)]
    counts = scoped["verdict"].value_counts()
    total = int(counts.sum())
    rows = []
    for band, (plan_n, plan_share) in PLAN_SCREEN.items():
        n = int(counts.get(band, 0))
        rows.append((band, n, f"{n / total:.1%}" if total else "—", plan_n, f"{plan_share:.1%}"))
    if "no reading" in counts:
        rows.append(
            ("no reading — the sea is masked out of the DEM", int(counts["no reading"]),
             f"{counts['no reading'] / total:.1%}", "—", "—")
        )
    log.table(
        "what Terrain 50 says about the direction OS states, in scope",
        ["the DEM says", "links", "share", "PLAN.md §5", "plan share"],
        rows,
    )

    # The useful row: a human-sized list to adjudicate one by one.
    against = scoped[scoped["verdict"] == "rises more than 4 m — clearly disagrees"]
    log.info(
        f"  {len(against):,} links, {against['length_m'].sum() / 1000:,.0f} km, where "
        "the DEM clearly disagrees with the stated direction. This is a list of "
        "candidates for a person to look at, and nothing more: no link is flipped on "
        "terrain evidence alone (D-007)."
    )

    # And where the DEM goes quiet — which is exactly where direction is ambiguous.
    mute = (
        scoped.assign(mute=scoped["verdict"] == "within +/-0.5 m — says nothing at all")
        .groupby("form")["mute"]
        .mean()
    )
    log.table(
        "the share of each form the DEM cannot adjudicate — it is silent on the levels",
        ["form", "this build", "PLAN.md §5"],
        [
            (form, f"{mute.get(form, float('nan')):.1%}", f"{plan:.1%}")
            for form, plan in PLAN_MUTE_BY_FORM.items()
        ],
    )

    # ------------------------------------------------- the component-root test
    root = _component_roots()
    report.add("screen", {band: int(counts.get(band, 0)) for band in PLAN_SCREEN})
    report.add("clearly_disagrees", {
        "links": int(len(against)),
        "km": round(float(against["length_m"].sum()) / 1000.0, 1),
    })
    report.add("component_root", root)

    for row in against.sort_values("fall_m").head(int(p("audit.report_top_n"))).itertuples():
        report.finding(
            Finding(
                kind="direction_screen",
                subject=row.link_id,
                detail=(
                    f"Terrain 50 says this {row.form} rises {-row.fall_m:,.1f} m over "
                    f"{row.length_m:,.0f} m in the direction the survey states"
                ),
                easting=float(ends.loc[row.Index, "up_e"]),
                northing=float(ends.loc[row.Index, "up_n"]),
                metrics={"fall_m": round(float(row.fall_m), 2)},
            )
        )
    report.write_json(paths.PUBLISHED / "audit" / "screen.json")

    return {
        "screened": total,
        "clearly_disagrees": int(len(against)),
        "clearly_disagrees_km": round(float(against["length_m"].sum()) / 1000.0, 1),
        **root,
    }


def _component_roots() -> dict:
    """Does each component's flow direction drain to its lowest node? (§6, D-009)

    Measured, and reported as what it is: a licence to treat the lowest node as a
    trustworthy root, not a fault detector. **One caveat on the figures**: where a DEM
    is masked over the sea the outlet sits on nodata, which is itself confirmation that
    the component reaches tidal water. Count that case; do not drop it silently.
    """
    con = db.get()
    g = graph.load("edge")
    labels = g.weak_components()
    node_ids = g.nodes

    places = db.df("SELECT node_id, easting, northing FROM node")
    lookup = {r.node_id: (r.easting, r.northing) for r in places.itertuples()}
    eastings = np.array([lookup.get(str(n), (np.nan, np.nan))[0] for n in node_ids])
    northings = np.array([lookup.get(str(n), (np.nan, np.nan))[1] for n in node_ids])

    with raster.open_unconditioned() as ds:
        elevation = raster.sample_points(ds, eastings, northings)

    outdeg = g.outdegree()
    indeg = g.indegree()
    has_edge = (outdeg + indeg) > 0
    sink = has_edge & (outdeg == 0)

    edge_component = labels[g.u]
    length_by_component = pd.Series(g.length).groupby(edge_component).sum() / 1000.0

    rows = []
    for component, km in length_by_component.items():
        members = np.flatnonzero((labels == component) & has_edge)
        if members.size == 0:
            continue
        member_elev = elevation[members]
        sinks_here = members[sink[members]]
        if sinks_here.size == 0:
            rows.append((int(component), km, None, None, "no sink at all — a cycle"))
            continue
        outlet_elev = elevation[sinks_here]
        if np.all(np.isnan(outlet_elev)):
            # The outlet stands on nodata: the sea is masked out, which confirms the
            # component reaches tidal water rather than meaning the reading failed.
            rows.append((int(component), km, None, None, "outlet on nodata — at the sea"))
            continue
        best_outlet = float(np.nanmin(outlet_elev))
        if np.all(np.isnan(member_elev)):
            rows.append((int(component), km, best_outlet, None, "component on nodata"))
            continue
        minimum = float(np.nanmin(member_elev))
        rows.append((int(component), km, best_outlet, minimum, "measured"))

    frame = pd.DataFrame(
        rows, columns=["component_id", "length_km", "outlet_m", "component_min_m", "note"]
    )
    frame["above_minimum_m"] = frame["outlet_m"] - frame["component_min_m"]
    con.execute("DROP TABLE IF EXISTS component_root")
    with db.registered("_root_in", frame):
        con.execute("CREATE TABLE component_root AS SELECT * FROM _root_in ORDER BY component_id")

    measured = frame[frame["note"] == "measured"].dropna(subset=["above_minimum_m"])
    bands = []
    for label, lo, hi in (("1-10 km", 1.0, 10.0), (">= 10 km", 10.0, float("inf"))):
        sub = measured[(measured["length_km"] >= lo) & (measured["length_km"] < hi)]
        if sub.empty:
            bands.append((label, 0, "—", 0))
            continue
        within2 = float((sub["above_minimum_m"].abs() <= 2.0).mean())
        over5 = int((sub["above_minimum_m"] > 5.0).sum())
        bands.append((label, len(sub), f"{within2:.1%}", f"{over5} of {len(sub)}"))
    log.table(
        "does a component's outlet sit at its lowest point? (§6's measured table)",
        ["component size", "measured", "within 2 m of the minimum", "more than 5 m above"],
        bands,
    )
    log.detail(
        "    PLAN.md §6: 92.2% and 90.4% within 2 m; 30 of 1,787 and 7 of 729 more "
        "than 5 m above. Read as a licence, not a null result: the lowest node is a "
        "trustworthy root, which is what orients a level canal (D-009)."
    )
    on_nodata = int((frame["note"] == "outlet on nodata — at the sea").sum())
    no_sink = int((frame["note"] == "no sink at all — a cycle").sum())
    log.detail(
        f"    {on_nodata:,} components have their outlet on nodata — the sea is masked "
        f"out of Terrain 50, so that is confirmation they reach tidal water, not a "
        f"failed reading. {no_sink:,} components have no sink at all."
    )
    return {
        "components_measured": int(len(measured)),
        "outlet_on_nodata": on_nodata,
        "components_with_no_sink": no_sink,
    }
