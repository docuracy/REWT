"""Stage: the component census, run before any attempt to link anything (PLAN.md §6).

This is the map of what linking has to resolve, and it is available on day one. It is
computed over the survey's own orientation, in `link`, and it is deliberately *not*
computed over the repaired graph: its whole value is as a description of the ground
before anything was done to it.

The productive number here is **sinks per component**. A well-formed river system has
one. Testing instead whether each component drains to its lowest node was measured and
does not pay (D-009): reversing one link mid-tree does not move the component's outlet,
it creates a *new* sink partway up, so the lowest-point test is blind to precisely the
fault that is common. That test still runs — in the terrain stage — but for what it is
actually good for, which is establishing that the lowest node is a trustworthy root.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config, db, graph, topology
from ..pipeline import PIPELINE, artefact
from ..report import Finding, Report, log

CENSUS_COMPONENT = artefact("census_component")
CENSUS_SINK = artefact("census_sink")
CENSUS_FINDING = artefact("census_finding")

# PLAN.md §6's figures for OS Open Rivers as shipped, for comparison. They are
# measurements of the publisher's product, which is legitimate to check against
# (AGENTS.md); nothing about the reconstructed network may be quoted from there.
PLAN_COMPONENTS = 5617
PLAN_LARGEST_KM = 4126
PLAN_TEN_KM_PLUS = 1065
PLAN_UNDER_1KM = 1415
PLAN_SINKS_GB = 6197
PLAN_MULTI_SINK_10KM = 158
PLAN_WORST_SINKS = 48
PLAN_BIFURCATIONS = 1324


def _component_frame(g: graph.Graph) -> pd.DataFrame:
    labels = g.weak_components()
    edge_component = labels[g.u]
    indeg, outdeg = g.indegree(), g.outdegree()
    sink_nodes = np.flatnonzero((indeg > 0) & (outdeg == 0))
    node_has_edge = (indeg + outdeg) > 0

    frame = pd.DataFrame(
        {
            "component": edge_component,
            "length_m": g.length,
            "form": g.form,
        }
    )
    agg = (
        frame.groupby("component")
        .agg(links=("length_m", "size"), length_m=("length_m", "sum"))
        .reset_index()
    )
    sinks_per = pd.Series(labels[sink_nodes]).value_counts()
    agg["sinks"] = agg["component"].map(sinks_per).fillna(0).astype(int)
    agg["nodes"] = agg["component"].map(
        pd.Series(labels[node_has_edge]).value_counts()
    ).fillna(0).astype(int)

    # Which forms a component holds decides whether a canal-only component needs new
    # geometry at all (§5): 1,932 km of canal already sits in a component holding
    # river, lake or tidal water.
    forms = (
        frame.groupby(["component", "form"])["length_m"].sum().unstack(fill_value=0.0)
    )
    for col in ("inlandRiver", "lake", "tidalRiver", "canal"):
        agg[f"km_{col}"] = agg["component"].map(forms.get(col, pd.Series(dtype=float))).fillna(0.0) / 1000.0
    agg["canal_only"] = (agg["km_canal"] > 0) & (
        agg[["km_inlandRiver", "km_lake", "km_tidalRiver"]].sum(axis=1) == 0
    )
    agg["has_tidal"] = agg["km_tidalRiver"] > 0
    agg["length_km"] = agg["length_m"] / 1000.0
    return agg.sort_values("length_km", ascending=False).reset_index(drop=True), labels, sink_nodes


@PIPELINE.stage(
    "census",
    "the component census of the survey as shipped, before anything is linked",
    reads=["link", "node"],
    writes=["census_component", "census_sink", "census_finding"],
    params=["topology", "forms", "canals", "seeds"],
)
def run() -> dict:
    p = config.params()
    con = db.get()
    g = graph.load("link")

    agg, labels, sink_nodes = _component_frame(g)
    report = Report("census")

    # ------------------------------------------------------------ components
    fragment_km = p("topology.fragment_km")
    bands = p("topology.component_bands_km")
    n_components = len(agg)
    largest_km = float(agg["length_km"].iloc[0])
    total_km = float(agg["length_km"].sum())
    ten_plus = int((agg["length_km"] >= bands[-1]).sum())
    under_1 = int((agg["length_km"] < fragment_km).sum())
    # 24 components hold a third of it, in the plan's measurement.
    cum = agg["length_km"].cumsum() / total_km
    to_a_third = int((cum < (1 / 3)).sum() + 1)

    log.table(
        "the component census (OS Open Rivers as shipped)",
        ["measure", "this issue", "PLAN.md §6"],
        [
            ("weakly connected components", n_components, PLAN_COMPONENTS),
            ("largest component, km", round(largest_km, 0), PLAN_LARGEST_KM),
            ("largest as share of network", f"{largest_km / total_km:.1%}", "2.7%"),
            ("components holding a third of it", to_a_third, 24),
            ("components >= 10 km", ten_plus, PLAN_TEN_KM_PLUS),
            ("components < 1 km", under_1, PLAN_UNDER_1KM),
        ],
    )

    # -------------------------------------------------- sinks per component
    # "The most productive single number in this audit: a well-formed river system
    # has one. Report every component with more than one, ranked."
    multi = agg[agg["sinks"] > 1].sort_values(
        ["sinks", "length_km"], ascending=[False, False]
    )
    multi_10km = int(((agg["sinks"] > 1) & (agg["length_km"] >= bands[-1])).sum())
    worst = int(agg["sinks"].max())
    log.table(
        "sinks per component — the productive signal (D-009)",
        ["measure", "this issue", "PLAN.md §6"],
        [
            ("components with more than one sink", len(multi), "—"),
            ("of those, >= 10 km", multi_10km, PLAN_MULTI_SINK_10KM),
            ("most sinks in one component", worst, PLAN_WORST_SINKS),
            ("nodes with inflow and no outflow, GB", len(sink_nodes), PLAN_SINKS_GB),
        ],
    )

    # ---------------------------------------------- dead ends, by what arrives
    node_ids = g.nodes
    sink_node_ids = [node_ids[i] for i in sink_nodes]
    with db.registered("_sink_in", pd.DataFrame({"node_id": sink_node_ids})):
        con.execute("DROP TABLE IF EXISTS census_sink")
        con.execute(
            """
            CREATE TABLE census_sink AS
            SELECT n.node_id,
                   n.terminus,
                   n.category,
                   n.easting,
                   n.northing,
                   count(l.link_id)          AS inflows,
                   sum(l.length_m)           AS inflow_length_m,
                   min(l.form)               AS form_min,
                   max(l.form)               AS form_max,
                   any_value(l.name)         AS name
            FROM _sink_in s
            JOIN node n USING (node_id)
            JOIN link l ON l.to_node = n.node_id
            GROUP BY 1, 2, 3, 4, 5
            """
        )

    by_form = con.execute(
        """
        SELECT l.form,
               CASE WHEN n.terminus = 'tidal' THEN 'at tidal water' ELSE 'not at tidal water' END AS place,
               count(*) AS links,
               sum(l.length_m) / 1000.0 AS km
        FROM census_sink s
        JOIN node n USING (node_id)
        JOIN link l ON l.to_node = s.node_id
        GROUP BY 1, 2 ORDER BY 2, 4 DESC
        """
    ).df()
    log.frame("dead ends, by the form of the water arriving there", by_form, 12)

    tidal_sinks = int(
        con.execute(
            "SELECT count(*) FROM census_sink WHERE terminus = 'tidal'"
        ).fetchone()[0]
    )
    defect_sinks = len(sink_node_ids) - tidal_sinks
    log.info(
        f"  of {len(sink_node_ids):,} sinks in Great Britain, {tidal_sinks:,} stand at "
        f"tidal water and are correct; {defect_sinks:,} do not, and are the work. "
        "(PLAN.md §6's in-scope figures are 469 and 2,516; these are national and "
        "before scope, so they are the larger set that contains them.)"
    )

    # ---------------------------------------------------- direction faults
    one_two = g.one_in_two_out()
    log.info(
        f"  {len(one_two):,} nodes have one inflow and two or more outflows — the "
        f"signature of a tributary drawn flowing away from its parent. "
        f"{len(g.bifurcations()):,} nodes have more than one outflow at all "
        f"(PLAN.md §6: {PLAN_BIFURCATIONS:,})."
    )

    # ------------------------------------------------- touching, not joined
    pairs = topology.unjoined_pairs()
    log.info(
        f"  {len(pairs):,} pairs of distinct nodes stand within "
        f"{p('topology.coincidence_tolerance_m')} m of each other — touching, not joined."
    )

    # -------------------------------------------------------------- cycles
    cyc = g.cycles()
    if cyc:
        log.warn(
            f"{len(cyc)} cycles in the survey as shipped. PLAN.md §6 says there are "
            "none of 10 km or more as shipped, so any large one here is a finding "
            "about this issue of the product."
        )
    else:
        log.detail("    no cycles: no component is a closed loop with no exit")

    # ------------------------------------------------------------- canals
    canal_summary = _canal_shape(agg, labels, g)

    # ---------------------------------------------------------- persist it
    agg_out = agg.assign(
        component_id=agg["component"].astype(int),
    )[
        [
            "component_id", "links", "nodes", "length_km", "sinks",
            "km_inlandRiver", "km_lake", "km_tidalRiver", "km_canal",
            "canal_only", "has_tidal",
        ]
    ]
    with db.registered("_comp_in", agg_out):
        con.execute("DROP TABLE IF EXISTS census_component")
        con.execute("CREATE TABLE census_component AS SELECT * FROM _comp_in")

    findings: list[dict] = []
    # Report at the place, not only in the total. Every finding carries a coordinate.
    worst_multi = multi.head(p("audit.report_top_n"))
    comp_place = _component_places(worst_multi["component"].tolist(), labels, g)
    for _, row in worst_multi.iterrows():
        e, n = comp_place.get(int(row["component"]), (None, None))
        findings.append(
            Finding(
                kind="multi_sink_component",
                subject=f"component {int(row['component'])}",
                detail=(
                    f"{int(row['sinks'])} sinks in one component of "
                    f"{row['length_km']:,.1f} km"
                ),
                easting=e,
                northing=n,
                metrics={"sinks": int(row["sinks"]), "length_km": round(float(row["length_km"]), 3)},
            ).to_row()
        )
    for _, row in pairs.head(p("audit.report_top_n")).iterrows():
        findings.append(
            Finding(
                kind="touching_not_joined",
                subject=f"{row['node_a']} / {row['node_b']}",
                detail=f"distinct nodes {row['gap_m']:.2f} m apart",
                easting=float(row["easting"]),
                northing=float(row["northing"]),
                metrics={"gap_m": round(float(row["gap_m"]), 3)},
            ).to_row()
        )
    for nodes_in_cycle in cyc[: p("audit.report_top_n")]:
        idx = int(nodes_in_cycle[0])
        place = con.execute(
            "SELECT easting, northing FROM node WHERE node_id = ?", [str(g.nodes[idx])]
        ).fetchone()
        findings.append(
            Finding(
                kind="cycle",
                subject=str(g.nodes[idx]),
                detail=f"closed loop over {len(nodes_in_cycle)} nodes with no exit",
                easting=place[0] if place else None,
                northing=place[1] if place else None,
                metrics={"nodes": int(len(nodes_in_cycle))},
            ).to_row()
        )

    finding_frame = pd.DataFrame(
        findings,
        columns=["kind", "subject", "detail", "easting", "northing", "metrics", "basin_id"],
    )
    with db.registered("_find_in", finding_frame):
        con.execute("DROP TABLE IF EXISTS census_finding")
        con.execute("CREATE TABLE census_finding AS SELECT * FROM _find_in")

    report.add("components", {
        "count": n_components,
        "largest_km": round(largest_km, 1),
        "total_km": round(total_km, 1),
        "ten_km_plus": ten_plus,
        "under_1km": under_1,
        "components_holding_a_third": to_a_third,
    })
    report.add("sinks", {
        "national": len(sink_node_ids),
        "at_tidal_water": tidal_sinks,
        "not_at_tidal_water": defect_sinks,
        "components_with_more_than_one": len(multi),
        "components_10km_with_more_than_one": multi_10km,
        "most_in_one_component": worst,
    })
    report.add("direction", {
        "one_in_two_out": int(len(one_two)),
        "bifurcations": int(len(g.bifurcations())),
    })
    report.add("touching_not_joined", int(len(pairs)))
    report.add("cycles", int(len(cyc)))
    report.add("canals", canal_summary)
    from .. import paths
    report.write_json(paths.PUBLISHED / "audit" / "census.json")

    return {
        "components": n_components,
        "sinks": len(sink_node_ids),
        "sinks_not_tidal": defect_sinks,
        "multi_sink_components": len(multi),
        "touching_not_joined": int(len(pairs)),
        "cycles": int(len(cyc)),
    }


def _component_places(components: list[int], labels: np.ndarray, g: graph.Graph) -> dict[int, tuple]:
    """One coordinate per component, so a finding about it has a place."""
    if not components:
        return {}
    wanted = set(int(c) for c in components)
    rep: dict[int, str] = {}
    for node_idx, label in enumerate(labels):
        label = int(label)
        if label in wanted and label not in rep:
            rep[label] = str(g.nodes[node_idx])
            if len(rep) == len(wanted):
                break
    if not rep:
        return {}
    frame = pd.DataFrame({"component": list(rep), "node_id": list(rep.values())})
    with db.registered("_rep_in", frame):
        places = db.df(
            "SELECT r.component, n.easting, n.northing FROM _rep_in r "
            "JOIN node n USING (node_id)"
        )
    return {
        int(r.component): (float(r.easting), float(r.northing))
        for r in places.itertuples()
    }


def _canal_shape(agg: pd.DataFrame, labels: np.ndarray, g: graph.Graph) -> dict:
    """The shape of the canal work, before any of it is done (§5, D-011).

    Canals are inside the reachability requirement. The point of measuring this here
    is that D-011 asserts the work is bounded — 289 canal-only components, every one
    with a non-canal watercourse within 2 km — and an assertion in a decision log is
    worth re-earning on the issue actually in hand.
    """
    canal_km = float(agg["km_canal"].sum())
    canal_components = agg[agg["km_canal"] > 0]
    canal_only = agg[agg["canal_only"]]
    with_other = canal_km - float(canal_only["km_canal"].sum())

    log.table(
        "canals, and the shape of the work D-011 committed to",
        ["measure", "this issue", "D-011"],
        [
            ("canal length, km", round(canal_km, 0), 2706),
            ("components holding canal", len(canal_components), 538),
            ("km already sharing a component with river, lake or tidal", round(with_other, 0), 1932),
            ("canal-only components", len(canal_only), 289),
            ("km in canal-only components", round(float(canal_only["km_canal"].sum()), 0), 774),
        ],
    )

    # How far is the nearest non-canal watercourse from each canal-only component?
    # D-011's answer is "every one of them within 2 km", and it decides whether these
    # are junctions (a node merged, nothing invented) or connectors (new geometry).
    bands = config.param("canals.nearest_bands_m")
    # Measured from the component's whole geometry, not from one representative node:
    # the question is how far the *component* is from other water, and the answer is
    # the minimum over everything in it. The first band is closed at zero, because
    # most of these are not "near" a watercourse at all — they are touching it, and a
    # band written `> 0` silently drops the majority of the finding.
    wanted = set(int(c) for c in canal_only["component"].tolist())
    edge_component = labels[g.u]
    member = np.isin(edge_component, list(wanted))
    members = pd.DataFrame(
        {
            "link_id": g.link_ids[member],
            "component": edge_component[member].astype(int),
        }
    )
    near_links = topology.nearest_link_to_links(
        members["link_id"].tolist(), max(bands), exclude_forms=["canal"]
    )
    near = (
        members.merge(near_links, on="link_id", how="left")
        .groupby("component", as_index=False)["distance_m"]
        .min()
    )
    counts = {}
    prev = None
    for b in bands:
        if prev is None:
            counts[f"within {b:g} m"] = int((near["distance_m"] <= b).sum())
        else:
            counts[f"{prev:g}-{b:g} m"] = int(
                ((near["distance_m"] > prev) & (near["distance_m"] <= b)).sum()
            )
        prev = b
    counts["beyond 2 km or not found"] = int(near["distance_m"].isna().sum())
    log.table(
        "canal-only components: distance to the nearest non-canal watercourse",
        ["band", "components", "D-011"],
        [
            (k, v, d)
            for (k, v), d in zip(counts.items(), [163, 65, 33, 28, 0])
        ],
    )

    # D-011 reads the nearest band as "touching, merely unjoined — junctions, not
    # connectors". That is true only where the touch is at an END of the canal. Where
    # a canal line crosses a river line with both its ends elsewhere, the crossing is
    # very probably an aqueduct or a culvert — a structure built to keep the two
    # waters apart — and merging a node there would route the river down the canal.
    # The distinction is free to make here and expensive to discover later.
    touching = near.loc[near["distance_m"] <= 0.0, "component"].tolist()
    endpoint_touches = 0
    if touching:
        touch_links = members[members["component"].isin(touching)]["link_id"].tolist()
        ends = topology.nearest_links(
            _endpoint_nodes(touch_links), 0.001, exclude_forms=["canal"]
        )
        endpoint_touches = len(set(ends["node_id"])) if len(ends) else 0
    log.detail(
        f"    {len(touching)} components touch a non-canal watercourse at 0 m; "
        f"{endpoint_touches} of those touches are at an end of a canal link "
        "(a junction — a node is merged, nothing is invented). The remainder cross "
        "mid-line and are candidates for an aqueduct or culvert, which must not be "
        "joined. Each still has to be adjudicated at the place."
    )

    return {
        "canal_km": round(canal_km, 1),
        "components_holding_canal": len(canal_components),
        "canal_only_components": len(canal_only),
        "canal_only_km": round(float(canal_only["km_canal"].sum()), 1),
        "km_sharing_with_non_canal": round(with_other, 1),
        "nearest_non_canal_bands": counts,
        "touching_at_zero": len(touching),
        "touching_at_a_canal_end": endpoint_touches,
    }


def _endpoint_nodes(link_ids: list[str]) -> list[str]:
    """The nodes at either end of the given links, deduplicated and ordered."""
    if not link_ids:
        return []
    with db.registered("_ep_in", pd.DataFrame({"link_id": link_ids})):
        frame = db.df(
            """
            SELECT DISTINCT n FROM (
                SELECT l.from_node AS n FROM link l JOIN _ep_in USING (link_id)
                UNION ALL
                SELECT l.to_node FROM link l JOIN _ep_in USING (link_id)
            ) ORDER BY n
            """
        )
    return frame["n"].tolist()
