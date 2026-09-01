"""Stage: the audit. It runs with every build and fails loudly (PLAN.md §6).

Everything §6 asks for, and in the order it asks for it:

* **Dead ends.** Nodes with inflows and no outflow, classified: at tidal water
  (correct) or not (a defect). Broken down by the form of the water arriving, because
  the classes have different causes and different remedies, and a single total conceals
  that canals are ten times over-represented. Count, length above each, and the largest
  by catchment.
* **Direction faults.** Nodes with one inflow and two outflows — the signature of a
  tributary drawn flowing away from its parent.
* **Touching but not joined.** Endpoints coincident within a metre sharing no node.
* **Cycles.** A closed loop with no exit strands everything above it and is invisible
  in any total. As shipped, OS Open Rivers has none of 10 km or more, so any that appear
  here were introduced by our own repairs.
* **Sinks per component.** A well-formed river system has one.
* **Reachability.** The share of length from which the sea can be reached — the
  headline number and the one to watch.
* **Per basin, and ranked.** A national figure of 97% hides a basin at 40%, and the
  basin at 40% is the entire finding.
* **At the place, not only in the total.** Every finding carries a coordinate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import acquire, config, db, graph, paths, sea, topology
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Finding, Report, log

AUDIT_FINDING = artefact("audit_finding")
AUDIT_BASIN = artefact("audit_basin")

# PLAN.md §6's defect list, on the orientation OS ships, in scope.
PLAN_IN_SCOPE_SINKS = 2985
PLAN_AT_TIDAL = 469
PLAN_DEFECTS = 2516
PLAN_BY_FORM = {
    "inlandRiver": (2323, 2861),
    "canal": (635, 1535),
    "lake": (261, 94),
}


@PIPELINE.stage(
    "audit",
    "the audit: dead ends, direction faults, cycles, reachability, per basin",
    reads=["edge", "node", "link_reach", "link_scope", "basin", "node_basin",
           "sea_entry", "sea_link", "raw_os_boundary_line"],
    writes=["audit_finding", "audit_basin"],
    params=["audit", "topology", "forms", "seeds"],
    sources=["os_boundary_line"],
    always=True,
)
def run() -> dict:
    p = config.params()
    con = db.get()
    report = Report("audit")
    findings: list[Finding] = []

    g = graph.load("edge")
    sinks = g.sinks()
    labels = g.weak_components()

    # ------------------------------------------------------------- dead ends
    sink_ids = [str(g.nodes[i]) for i in sinks]
    upstream_m = g.upstream_length(sinks)

    # HOW MUCH OF THAT IS ACTUALLY STRANDED, which is not the same number and is the
    # one a reader should work down. A dead end can sit on water that leaves by another
    # route: Stanlow Pool, on the Manchester Ship Canal, tops the Cheshire list with
    # **1,514.5 km upstream and nothing stranded at all** — all three links arriving
    # there reach the sea, because the node above it also drains west to Eastham. It is
    # a cul-de-sac off a working drain, not a defect.
    #
    # Ranking by upstream length therefore puts a non-defect first in the list §6 asks
    # someone to work down, which is the most expensive place to be wrong: the reader
    # spends their attention where there is nothing to find. Both figures are reported;
    # the ranking uses the stranded one.
    unreached = {
        r[0] for r in con.execute(
            "SELECT link_id FROM link_reach WHERE NOT reaches_tidal"
        ).fetchall()
    }
    mask = np.array([str(lid) in unreached for lid in g.link_ids], dtype=bool)
    stranded_m = g.upstream_length(sinks, mask=mask)
    sink_frame = pd.DataFrame({
        "node_id": sink_ids, "upstream_m": upstream_m, "stranded_m": stranded_m,
    })

    con.execute("DROP TABLE IF EXISTS _sink")
    with db.registered("_sink_in", sink_frame):
        con.execute(
            """
            CREATE TEMP TABLE _sink AS
            SELECT s.node_id, s.upstream_m, n.terminus, n.easting, n.northing,
                   s.stranded_m,
                   coalesce(sc.in_scope, false) AS in_scope,
                   nb.basin_id,
                   (SELECT any_value(e.form) FROM edge e WHERE e.to_node = s.node_id) AS form,
                   (SELECT count(*) FROM edge e WHERE e.to_node = s.node_id) AS inflows,
                   (SELECT any_value(l.name) FROM edge e JOIN link l USING (link_id)
                    WHERE e.to_node = s.node_id AND l.name IS NOT NULL) AS name
            FROM _sink_in s
            JOIN node n USING (node_id)
            LEFT JOIN node_basin nb ON nb.node_id = s.node_id
            LEFT JOIN (
                SELECT e.to_node AS node_id, bool_or(sc.in_scope) AS in_scope
                FROM edge e JOIN link_scope sc ON sc.link_id = e.link_id
                GROUP BY 1
            ) sc ON sc.node_id = s.node_id
            """
        )

    totals = con.execute(
        """
        SELECT count(*) FILTER (WHERE in_scope) AS in_scope,
               count(*) FILTER (WHERE in_scope AND terminus = 'tidal') AS at_tidal,
               count(*) FILTER (WHERE in_scope AND terminus <> 'tidal') AS defects,
               count(*) AS national
        FROM _sink
        """
    ).fetchone()
    log.table(
        "dead ends — nodes with inflows and no outflow (§6's calibration)",
        ["measure", "this build", "PLAN.md §6"],
        [
            ("inflow and no outflow, Great Britain", totals[3], 6197),
            ("the same, in scope", totals[0], PLAN_IN_SCOPE_SINKS),
            ("of those, at tidal water — correct", totals[1], PLAN_AT_TIDAL),
            ("not at tidal water — the work", totals[2], PLAN_DEFECTS),
        ],
    )

    by_form = con.execute(
        """
        SELECT s.form,
               count(DISTINCT e.link_id) AS links,
               sum(e.length_m) / 1000.0 AS km,
               count(DISTINCT s.node_id) AS nodes
        FROM _sink s JOIN edge e ON e.to_node = s.node_id
        WHERE s.in_scope AND s.terminus <> 'tidal'
        GROUP BY 1 ORDER BY 3 DESC, 1
        """
    ).df()
    log.table(
        "the work, by the form of the water arriving — the classes have different causes",
        ["form", "links", "km", "nodes", "PLAN.md §6 links/km"],
        [
            (
                r.form, int(r.links), round(float(r.km), 1), int(r.nodes),
                f"{PLAN_BY_FORM[r.form][0]} / {PLAN_BY_FORM[r.form][1]}"
                if r.form in PLAN_BY_FORM else "—",
            )
            for r in by_form.itertuples()
        ],
    )
    canal_row = by_form[by_form["form"] == "canal"]
    if len(canal_row):
        canal_km = float(canal_row["km"].iloc[0])
        all_canal_km = float(
            con.execute("SELECT sum(length_m)/1000.0 FROM edge WHERE form = 'canal'").fetchone()[0]
            or 1.0
        )
        log.detail(
            f"    that canal figure is {canal_km / all_canal_km:.0%} of all canal "
            "length in the network. PLAN.md §6 reads its own 56% as one structural "
            "fact about canals, not as 635 bugs — a canal reaches the sea through a "
            "structure the survey does not draw (D-011)."
        )

    # The largest by catchment: how much water stands above each dead end.
    worst = con.execute(
        f"""
        SELECT node_id, name, form, upstream_m / 1000.0 AS upstream_km,
               stranded_m / 1000.0 AS stranded_km, inflows,
               easting, northing, basin_id
        FROM _sink WHERE in_scope AND terminus <> 'tidal'
        ORDER BY stranded_m DESC, upstream_m DESC, node_id LIMIT {int(p('audit.report_top_n'))}
        """
    ).df()
    log.frame(
        "the largest dead ends by the catchment standing above them — work down this list",
        worst[["name", "form", "upstream_km", "inflows", "easting", "northing"]],
        20,
    )
    for row in worst.itertuples():
        findings.append(
            Finding(
                kind="dead_end",
                subject=row.node_id,
                detail=(
                    f"{row.upstream_km:,.1f} km of {row.form or 'watercourse'} "
                    f"{'(' + row.name + ') ' if row.name else ''}drains to a node with "
                    "no outflow, and not at tidal water"
                ),
                easting=float(row.easting),
                northing=float(row.northing),
                metrics={"upstream_km": round(float(row.upstream_km), 3),
                         "inflows": int(row.inflows)},
                basin_id=row.basin_id,
            )
        )

    nominal = float(p("audit.nominal_upstream_km"))
    over_nominal = int(
        con.execute(
            "SELECT count(*) FROM _sink WHERE in_scope AND terminus <> 'tidal' "
            f"AND upstream_m > {nominal * 1000}"
        ).fetchone()[0]
    )
    log.info(
        f"  {over_nominal:,} dead ends carry more than the nominal {nominal:g} km "
        "draining into nowhere. PLAN.md §1's exit condition is that none do."
    )

    # ------------------------------------------------------- direction faults
    one_two = g.one_in_two_out()
    fault_nodes = [str(g.nodes[i]) for i in one_two]
    log.info(
        f"  {len(fault_nodes):,} nodes have one inflow and two or more outflows — the "
        "signature of a tributary drawn flowing away from its parent (§6)"
    )
    for node_id in fault_nodes[: int(p("audit.report_top_n"))]:
        place = con.execute(
            "SELECT easting, northing FROM node WHERE node_id = ?", [node_id]
        ).fetchone()
        findings.append(
            Finding(
                kind="direction_fault",
                subject=node_id,
                detail="one inflow, two or more outflows",
                easting=place[0] if place else None,
                northing=place[1] if place else None,
            )
        )

    # ---------------------------------------------------- touching, not joined
    pairs = topology.unjoined_pairs()
    log.info(
        f"  {len(pairs):,} pairs of distinct nodes stand within "
        f"{p('topology.coincidence_tolerance_m')} m of one another, sharing no node"
    )
    for row in pairs.head(int(p("audit.report_top_n"))).itertuples():
        findings.append(
            Finding(
                kind="touching_not_joined",
                subject=f"{row.node_a} / {row.node_b}",
                detail=f"{row.gap_m:.2f} m apart, no node in common",
                easting=float(row.easting),
                northing=float(row.northing),
                metrics={"gap_m": round(float(row.gap_m), 3)},
            )
        )

    # --------------------------------------------------------------- cycles
    # §6 defines the defect precisely: *A closed loop with no exit strands everything
    # above it... Detect them as components with **no sink at all**.* A loop that DOES
    # have an exit is a braided channel, which is a real feature of a river and not a
    # fault. Counting both together reported thirteen cycles where five were braids,
    # three of which this project had just created by joining a channel to itself —
    # correctly, as it turns out, because the water leaves.
    all_loops = g.cycles()
    reached_links = set(
        db.df("SELECT link_id FROM link_reach WHERE reaches_tidal")["link_id"]
    )
    cycles, braids = [], []
    for nodes_in_cycle in all_loops:
        member = np.isin(g.u, nodes_in_cycle) & np.isin(g.v, nodes_in_cycle)
        drains = any(lid in reached_links for lid in g.link_ids[member])
        (braids if drains else cycles).append(nodes_in_cycle)
    if braids:
        braid_km = sum(
            float(g.length[np.isin(g.u, b) & np.isin(g.v, b)].sum()) / 1000.0
            for b in braids
        )
        log.detail(
            f"    {len(braids)} closed loops totalling {braid_km:,.1f} km DO have an "
            "exit — braided channels, not faults, and not counted as cycles"
        )
    cycle_km = 0.0
    for nodes_in_cycle in cycles:
        member = np.isin(g.u, nodes_in_cycle) & np.isin(g.v, nodes_in_cycle)
        cycle_km += float(g.length[member].sum()) / 1000.0
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
            )
        )
    if cycles:
        largest = max(
            float(g.length[np.isin(g.u, c) & np.isin(g.v, c)].sum()) / 1000.0
            for c in cycles
        )
        log.warn(
            f"{len(cycles)} closed loops with NO exit, {cycle_km:,.1f} km, the largest "
            f"{largest:,.2f} km. §6: as shipped OS Open Rivers has none of 10 km or "
            "more, so a large one here would have been introduced by our own repairs."
        )
    else:
        log.detail("    no cycles")

    # ----------------------------------------------- sinks per component
    sinks_per = pd.Series(labels[sinks]).value_counts()
    edge_component = labels[g.u]
    comp_km = pd.Series(g.length).groupby(edge_component).sum() / 1000.0
    multi = (
        pd.DataFrame({"sinks": sinks_per})
        .join(pd.DataFrame({"length_km": comp_km}), how="inner")
        .query("sinks > 1")
        .sort_values(["sinks", "length_km"], ascending=False)
    )
    log.info(
        f"  {len(multi):,} components have more than one sink; the worst has "
        f"{int(multi['sinks'].max()) if len(multi) else 0}. A well-formed river system "
        "has one (§6)."
    )

    # --------------------------------------------------------- reachability
    national = con.execute(
        """
        SELECT sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END) / 1000.0,
               sum(e.length_m) / 1000.0
        FROM edge e JOIN link_reach r USING (link_id)
        """
    ).fetchone()
    scoped = con.execute(
        """
        SELECT sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END) / 1000.0,
               sum(e.length_m) / 1000.0
        FROM edge e JOIN link_reach r USING (link_id)
        JOIN link_scope s USING (link_id) WHERE s.in_scope
        """
    ).fetchone()

    # ------------------------------------------------------------- per basin
    basin_rows = con.execute(
        """
        SELECT b.basin_id, b.label, b.area_km2, b.in_scope, b.outlet_node,
               sum(e.length_m) / 1000.0 AS km,
               sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END) / 1000.0 AS reached_km,
               count(*) AS links
        FROM basin b
        JOIN node_basin nb ON nb.basin_id = b.basin_id
        JOIN edge e ON e.to_node = nb.node_id
        JOIN link_reach r ON r.link_id = e.link_id
        GROUP BY 1, 2, 3, 4, 5
        ORDER BY b.basin_id
        """
    ).df()
    basin_rows["unreached_km"] = basin_rows["km"] - basin_rows["reached_km"]
    basin_rows["share"] = basin_rows["reached_km"] / basin_rows["km"].replace(0, np.nan)
    basin_rows = _name_the_shortfalls(basin_rows)
    con.execute("DROP TABLE IF EXISTS audit_basin")
    with db.registered("_ab_in", basin_rows):
        con.execute("CREATE TABLE audit_basin AS SELECT * FROM _ab_in ORDER BY basin_id")

    # A tiebreaker on the identifier, not because ties are common but because a sort
    # without one is a sort whose output depends on the order the rows arrived in.
    # Two consecutive builds ranked two 6.74 km basins differently and the published
    # audit differed, which is exactly what §2's "deterministic ordering wherever a
    # result depends on iteration order" is about.
    ranked = basin_rows[basin_rows["in_scope"]].sort_values(
        ["unreached_km", "basin_id"], ascending=[False, True]
    )
    log.table(
        "reachability — the headline number (§6)",
        ["extent", "reached km", "total km", "share"],
        [
            ("Great Britain", round(national[0] or 0, 0), round(national[1] or 0, 0),
             f"{(national[0] or 0) / (national[1] or 1):.2%}"),
            ("in scope", round(scoped[0] or 0, 0), round(scoped[1] or 0, 0),
             f"{(scoped[0] or 0) / (scoped[1] or 1):.2%}"),
        ],
    )
    log.frame(
        "in-scope basins ranked by unreached length — work down this list (§6)",
        ranked.head(20)[["label", "km", "reached_km", "unreached_km", "share"]],
        20,
    )
    worst_basin = ranked.head(1)
    if len(worst_basin) and float(worst_basin["share"].iloc[0] or 1) < 1.0:
        log.detail(
            "    a national figure hides a basin at a much lower share, and that basin "
            "is the entire finding. This list, not the national number, is the work."
        )

    # ------------------------------------- the stranded components, ranked
    # A dead end is a place; a stranded component is a REGION with no way out, and it
    # is the unit the remaining work actually comes in. Reporting only dead ends
    # understates it: one missing structure can strand four hundred kilometres, and
    # the dead ends inside that region are symptoms of the one absence.
    stranded = _stranded_components(g, labels)
    if len(stranded):
        log.frame(
            "in-scope components with NO way to tidal water, largest first — "
            "each needs one connection, not one per dead end",
            stranded.head(20)[["label", "km", "forms", "easting", "northing"]],
            20,
        )
        for row in stranded.head(int(p("audit.report_top_n"))).itertuples():
            findings.append(
                Finding(
                    kind="stranded_component",
                    subject=str(row.label),
                    detail=(
                        f"{row.km:,.1f} km of {row.forms} has no way to tidal water at "
                        f"all; the whole region needs one connection, not one per dead "
                        f"end"
                    ),
                    easting=float(row.easting),
                    northing=float(row.northing),
                    metrics={"km": round(float(row.km), 3)},
                )
            )

    # ----------------------------------- the crossings D-016 refuses to join
    # Published as their own finding so they can be looked at. D-016 refuses a
    # connector where a stranded line touches draining water at exactly 0 m, on the
    # reasoning that such a crossing is an aqueduct or a culvert far more often than a
    # confluence. D-030 tested that against 3,291 located structures and 77% of the
    # refusals have one within 150 m. **The other 23% are the interesting ones** and
    # cannot be looked at unless they are written down with a coordinate.
    crossings = _refused_crossings()
    if len(crossings):
        corroborated = int(crossings["structure_m"].notna().sum())
        log.info(
            f"  {len(crossings):,} zero-metre crossings refused as aqueducts or "
            f"culverts (D-016); {corroborated:,} have a Canal & River Trust structure "
            f"within 150 m and {len(crossings) - corroborated:,} do not — the latter "
            "are the ones to look at"
        )
        _write_refused_crossings(crossings)
        for row in crossings.head(int(p("audit.report_top_n"))).itertuples():
            findings.append(
                Finding(
                    kind="refused_crossing",
                    subject=f"{row.mine or 'unnamed'} x {row.theirs or 'unnamed'}",
                    detail=(
                        "touches draining water at exactly 0 m and is NOT joined: a "
                        "crossing here is an aqueduct or a culvert far more often than "
                        "a confluence (D-016). "
                        + (
                            f"Corroborated: {row.structure} recorded "
                            f"{row.structure_m:,.0f} m away."
                            if pd.notna(row.structure_m)
                            else "No Canal & River Trust structure is recorded within "
                            "150 m — but the Trust covers 101 waterways only, so that "
                            "is not evidence of absence. Worth looking at."
                        )
                    ),
                    easting=float(row.easting),
                    northing=float(row.northing),
                    metrics={"corroborated": bool(pd.notna(row.structure_m))},
                )
            )

    # ------------------------------------------------------------- persist
    frame = pd.DataFrame(
        [f.to_row() for f in findings],
        columns=["kind", "subject", "detail", "easting", "northing", "metrics", "basin_id"],
    )
    # ------------------------------------------- termini outside any basin
    # Named because §8 reports per basin and these cannot be. Not a defect of the
    # terminus layer: 27% of all nodes fall outside a delineated basin, and termini
    # sit on the coast where the delineation runs out. Reported so that a per-basin
    # figure is never read as covering the whole coast.
    unplaced = con.execute(
        """
        SELECT count(*) FILTER (WHERE nb.basin_id IS NULL) AS no_basin,
               count(*) FILTER (WHERE nb.basin_id IS NULL AND s.node_id IS NOT NULL)
                   AS no_basin_but_seeded,
               count(*) AS termini
        FROM node n
        LEFT JOIN node_basin nb ON nb.node_id = n.node_id
        LEFT JOIN seed s ON s.node_id = n.node_id
        WHERE n.terminus = 'tidal'
        """
    ).fetchone()
    report.add("termini_without_basin", unplaced[0])
    log.skip(
        f"{unplaced[0]:,} of {unplaced[2]:,} tidal termini fall outside any delineated "
        f"basin and cannot appear in a per-basin figure; {unplaced[1]:,} of them are "
        "crawl seeds. The delineation runs out at the coast, which is where termini are."
    )

    # ------------------------------------ the sea, as a definition and as a test
    # §10: attaching the sea network turns "reaches the sea" from true-by-definition
    # into something a mouth can fail. **Both readings are published, side by side.**
    # The point is not tidiness: reachability moving because the sea became a test it
    # can fail is NOT the network improving or worsening, and a single number replacing
    # the old one would put a discontinuity in the series that no reader could see —
    # the figures either side would stop being comparable while still looking like a
    # trend. rewt-1d wrote that clause into §10 and I would not remove it.
    if db.table_exists("sea_entry"):
        reachable_by_sea = sea.systems_the_sea_can_take(con)
        con.execute("DROP TABLE IF EXISTS _sea_ok")
        con.execute("CREATE TEMP TABLE _sea_ok (node_id VARCHAR)")
        if reachable_by_sea:
            con.executemany("INSERT INTO _sea_ok VALUES (?)",
                            [(n,) for n in sorted(reachable_by_sea)])
        tested = con.execute(
            """
            -- OVER `edge`, EXACTLY AS THE REACHABILITY SECTION ABOVE DOES. The point
            -- of publishing both readings is that they are comparable, so they must be
            -- summed over the same thing — and the first version of this was not. It
            -- summed over `link`, which omits the 2,650 links this project ADDS, and
            -- reported 103,855 km in scope beside the audit's own 105,699. Two totals
            -- for one quantity in one document, differing by 1,844 km, and the smaller
            -- one made the sea share look higher. `edge` already excludes retired
            -- links, because a retired link has no edge.
            SELECT sum(e.length_m) / 1000.0 AS total_km,
                   sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END) / 1000.0
                       AS tidal_km,
                   sum(CASE WHEN r.reaches_tidal
                             AND r.seed_node IN (SELECT node_id FROM _sea_ok)
                            THEN e.length_m ELSE 0 END) / 1000.0 AS sea_km
            FROM edge e
            JOIN link_reach r USING (link_id)
            JOIN link_scope sc USING (link_id)
            WHERE sc.in_scope
            """
        ).fetchone()
        total_km, tidal_km, sea_km = (float(x or 0) for x in tested)
        report.add("reachability_tested_against_the_sea", {
            "in_scope_total_km": round(total_km, 1),
            "reaches_tidal_water_km": round(tidal_km, 1),
            "reaches_tidal_water_share": round(tidal_km / (total_km or 1), 6),
            "reaches_the_sea_km": round(sea_km, 1),
            "reaches_the_sea_share": round(sea_km / (total_km or 1), 6),
        })
        log.rule("The sea as a definition, and the sea as a test (§10)")
        log.table(
            "in-scope reachability under both readings",
            ["reading", "km", "share"],
            [
                ["reaches tidal water — true by definition",
                 f"{tidal_km:,.0f}", _share(tidal_km / (total_km or 1))],
                ["and that tidal water reaches the sea — tested",
                 f"{sea_km:,.0f}", _share(sea_km / (total_km or 1))],
            ],
        )
        log.info(
            f"{tidal_km - sea_km:,.0f} km reaches tidal water that does not itself "
            f"reach the sea — {(tidal_km - sea_km) / (total_km or 1):.2%} of the "
            "in-scope network, and invisible until the sea became a test. "
            "BOTH figures are published: the fall is a change of question, not of "
            "network, and the series is not comparable across it."
        )

    # --------------------------------------------- the survey's own generalisation
    gen = _generalisation()
    report.add("generalisation", gen)
    log.rule("What the survey has already generalised away")
    log.table(
        "OS Open Rivers vertex geometry, as delivered",
        ["percentile", "vertex spacing (m)", "sagitta (m)"],
        [[f"{k}th", f"{gen['spacing_m'][k]:,.1f}", f"{gen['sagitta_m'][k]:,.2f}"]
         for k in (5, 25, 50, 75, 95, 99)],
    )
    log.info(
        "OS Open Rivers is generalised: median vertex spacing "
        f"{gen['spacing_m'][50]:.0f} m (5th–95th {gen['spacing_m'][5]:.0f}–{gen['spacing_m'][95]:.0f} m), "
        f"median sagitta {gen['sagitta_m'][50]:.2f} m (95th {gen['sagitta_m'][95]:.2f} m), "
        f"from {gen['vertices']:,} vertices on {gen['links_measured']:,} as-surveyed links. "
        "Detail smaller than this is absent from the record, not from the river."
    )
    log.detail(
        f"Closest two vertices anywhere: {gen['spacing_min_m']:,.2f} m. "
        f"Largest single bend retained: {gen['sagitta_max_m']:,.1f} m."
    )
    con.execute("DROP TABLE IF EXISTS audit_finding")
    with db.registered("_af_in", frame):
        con.execute("CREATE TABLE audit_finding AS SELECT * FROM _af_in")

    for f in findings:
        report.finding(f)
    report.add("dead_ends", {
        "national": totals[3], "in_scope": totals[0],
        "at_tidal_water": totals[1], "defects": totals[2],
        "over_nominal": over_nominal,
    })
    report.add("by_form", by_form.to_dict("records"))
    report.add("direction_faults", int(len(fault_nodes)))
    report.add("touching_not_joined", int(len(pairs)))
    report.add("cycles", {"count": len(cycles), "km": round(cycle_km, 1)})
    report.add("multi_sink_components", int(len(multi)))
    # `*_km` used to mean the length REACHED, while the prose beside it read
    # "93.28% of 97,786 km" — which states that 97,786 km is the total and that
    # 93.28% of *that* reaches the sea. Both halves wrong: the total is 104,829 km
    # and 97,786 km is what reaches. The line is internally consistent and reads
    # perfectly, which is why it survived a dozen readings by me — I already knew
    # which number was which. It is invisible to anyone with the context and
    # visible only to a reader without it, and that reader is who the deliverable
    # is for. Found by rewt-6a recomputing both readings to see which was meant.
    report.add("reachability", {
        "reached_gb_km": round(national[0] or 0, 1),
        "total_gb_km": round(national[1] or 0, 1),
        "gb_share": round((national[0] or 0) / (national[1] or 1), 6),
        "reached_in_scope_km": round(scoped[0] or 0, 1),
        "total_in_scope_km": round(scoped[1] or 0, 1),
        "in_scope_share": round((scoped[0] or 0) / (scoped[1] or 1), 6),
    })
    report.add("basins", ranked.head(200).to_dict("records"))

    # ------------------------------------------- what a static reader needs whole
    # The viewer computes these at boot today, from a server that reads the database
    # per request. On Pages there is no server, so either the build emits them or the
    # viewer bakes them into its own bundle — and a baked figure can only ever agree
    # with itself. rewt-fc's boot-time check compares its numbers against the
    # published file, and that check is what found the basin-attribution defect this
    # morning, which neither side could see alone. So the build emits them.
    #
    # The top 200 in `audit.json` is a reading list. These are the whole tables.
    import json as _json

    from ..report import write_text as _write_text

    # EVERY basin, not the in-scope ones. `ranked` is filtered to in-scope because
    # that is the work list; this file backs a map that draws all of them, and a
    # basin a reader can click and get nothing for is worse than one labelled
    # out of scope. `in_scope` is on every row so the viewer can say which it is.
    # And the 54 with no link arriving at all. They are delineated ground that
    # nothing in the network drains through — a real category rather than an
    # omission, and a map that draws 1,049 basins should be able to say so for
    # every one of them rather than falling silent on the ones with no rivers.
    empty = con.execute(
        """
        SELECT b.basin_id, b.label, b.area_km2, b.in_scope, b.outlet_node
        FROM basin b
        WHERE NOT EXISTS (
            SELECT 1 FROM node_basin nb JOIN edge e ON e.to_node = nb.node_id
            WHERE nb.basin_id = b.basin_id)
        """
    ).df()
    for col in ("km", "reached_km", "unreached_km", "share", "links",
                "shortfall_reason"):
        empty[col] = 0.0 if col in ("km", "reached_km", "unreached_km", "links") else None
    all_basins = (
        pd.concat([basin_rows, empty], ignore_index=True)
        .sort_values(["unreached_km", "basin_id"], ascending=[False, True])
        .replace({np.nan: None})
    )
    _write_text(
        paths.PUBLISHED / "audit" / "basin_reach.json",
        _json.dumps(all_basins.to_dict("records"), indent=1, sort_keys=True,
                    allow_nan=False, default=str),
    )
    dead = con.execute(
        """
        SELECT node_id, name, form, easting, northing, in_scope, inflows,
               round(upstream_m / 1000.0, 3) AS upstream_km,
               round(stranded_m / 1000.0, 3) AS stranded_km
        FROM _sink
        WHERE terminus IS DISTINCT FROM 'tidal'
        ORDER BY stranded_m DESC, upstream_m DESC, node_id
        """
    ).df()
    _write_text(
        paths.PUBLISHED / "audit" / "dead_ends.json",
        _json.dumps(dead.to_dict("records"), indent=1, sort_keys=True,
                    allow_nan=False, default=str),
    )
    log.detail(
        f"published/audit/: {len(all_basins):,} basins with their reached share "
        f"({int(all_basins['in_scope'].sum()):,} in scope), and "
        f"{len(dead):,} dead ends carrying BOTH upstream_km and stranded_km — rank on "
        "stranded_km, since upstream_km counts water that has another way out"
    )
    _sweep_the_outletless_basins(report, findings)

    report.add("stranded_components", {
        "count": int(len(stranded)),
        "km": round(float(stranded["km"].sum()), 1) if len(stranded) else 0.0,
        "largest": stranded.head(25).to_dict("records") if len(stranded) else [],
    })
    report.write_json(paths.PUBLISHED / "audit" / "audit.json")
    _write_human_report(report, ranked, by_form, worst)

    if p("audit.fail_build_on_defects") and totals[2] > 0:
        raise StageError(
            f"{totals[2]:,} dead ends in scope are not at tidal water. "
            "conf/params.yml sets audit.fail_build_on_defects, and PLAN.md §1's exit "
            "condition is that the audit runs clean or every exception is named."
        )

    return {
        "dead_ends_in_scope": totals[0],
        "defects": totals[2],
        "direction_faults": int(len(fault_nodes)),
        "cycles": len(cycles),
        "reachable_share_in_scope": round((scoped[0] or 0) / (scoped[1] or 1), 4),
    }


def _write_refused_crossings(frame: pd.DataFrame) -> None:
    """All of them, in their own file, uncapped.

    The ranked lists in this audit are capped because they are ordered by magnitude and
    the tail is small. **These are not ordered by magnitude.** An uncorroborated
    crossing is a question — is this an aqueduct or a confluence? — and a cap on a list
    of questions silently decides which ones get asked. So every one is written, with
    `corroborated` as a real boolean and the nearest structure named where there is
    one, so that a reader can sort and colour them rather than take the order given.
    """
    import json as _json

    from pyproj import Transformer

    # **GeoJSON is WGS84 by definition.** RFC 7946 fixes the coordinate reference
    # system at CRS84 and explicitly deprecates the `crs` member that earlier practice
    # used to declare otherwise, so a conforming reader ignores such a declaration and
    # reads 203862.05 as a longitude — which put this whole layer a few hundred
    # kilometres off West Africa and drew nothing. AGENTS.md already says EPSG:27700
    # throughout and EPSG:4326 only at export; a published .geojson IS an export, and
    # is the one format that cannot carry the projected coordinates. A GeoPackage can,
    # and does.
    to_wgs84 = Transformer.from_crs(
        config.param("crs.working"), "EPSG:4326", always_xy=True
    )

    features = []
    for row in frame.sort_values(
        ["structure_m", "easting", "northing"], na_position="first"
    ).itertuples():
        corroborated = bool(pd.notna(row.structure_m))
        lon, lat = to_wgs84.transform(float(row.easting), float(row.northing))
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(lon, 7), round(lat, 7)],
                },
                "properties": {
                    "stranded_watercourse": row.mine,
                    "draining_watercourse": row.theirs,
                    "corroborated": corroborated,
                    "structure": row.structure if corroborated else None,
                    "structure_m": round(float(row.structure_m), 1) if corroborated else None,
                    "refused_by": "D-016",
                    # The National Grid position is kept as a property, because the
                    # rest of this project works in EPSG:27700 and a reader joining
                    # this file to anything else will want it.
                    "easting": round(float(row.easting), 2),
                    "northing": round(float(row.northing), 2),
                    "in_trust_country": bool(row.in_trust_country),
                    "note": (
                        "A Canal & River Trust aqueduct or culvert is recorded nearby, "
                        "which corroborates the refusal."
                        if corroborated
                        else (
                            "No Canal & River Trust structure is recorded within "
                            "150 m, and this crossing IS in country the Trust covers "
                            "— the register could have recorded a structure here and "
                            "did not, so the refusal is genuinely unsupported and "
                            "wants looking at."
                            if row.in_trust_country
                            else "No Canal & River Trust structure is recorded within "
                            "150 m, and this crossing is OUTSIDE the country the Trust "
                            "covers — the register was never going to speak about it, "
                            "so this is absence of evidence rather than a doubtful "
                            "refusal."
                        )
                    ),
                },
            }
        )
    doc = {
        "type": "FeatureCollection",
        "name": "refused_crossings",
        "features": features,
    }
    out = paths.PUBLISHED / "audit" / "refused_crossings.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(doc, indent=1, sort_keys=True, allow_nan=False), encoding="utf-8")
    log.detail(f"    all {len(features):,} written to {paths.rel(out)}, uncapped")


def _refused_crossings() -> pd.DataFrame:
    """Where a stranded line touches draining water at exactly 0 m (D-016)."""
    frame = db.df(
        """
        WITH un AS (
            SELECT e.link_id, l.geom, l.name
            FROM edge e JOIN link_reach r USING (link_id)
            JOIN link l ON l.link_id = e.link_id
            JOIN link_scope s ON s.link_id = e.link_id
            WHERE NOT r.reaches_tidal AND s.in_scope
        ),
        re AS (
            SELECT l.link_id, l.geom, l.name
            FROM link l JOIN link_reach r USING (link_id)
            WHERE r.reaches_tidal
        )
        SELECT un.name AS mine, re.name AS theirs,
               ST_X(ST_Centroid(ST_Intersection(un.geom, re.geom))) AS easting,
               ST_Y(ST_Centroid(ST_Intersection(un.geom, re.geom))) AS northing
        FROM un JOIN re ON ST_Intersects(un.geom, re.geom)
        """
    ).dropna(subset=["easting", "northing"]).drop_duplicates(
        subset=["easting", "northing"]
    )
    if frame.empty or not db.table_exists("structure"):
        frame["structure"] = None
        frame["structure_m"] = None
        return frame
    with db.registered("_cross_in", frame[["easting", "northing"]]):
        near = db.df(
            """
            SELECT c.easting, c.northing,
                   (SELECT s.description FROM structure s
                    WHERE s.kind IN ('aqueducts', 'culverts')
                      AND s.easting BETWEEN c.easting - 150 AND c.easting + 150
                      AND s.northing BETWEEN c.northing - 150 AND c.northing + 150
                    ORDER BY sqrt(pow(s.easting - c.easting, 2)
                                + pow(s.northing - c.northing, 2)) LIMIT 1) AS structure,
                   (SELECT min(sqrt(pow(s.easting - c.easting, 2)
                                  + pow(s.northing - c.northing, 2)))
                    FROM structure s
                    WHERE s.kind IN ('aqueducts', 'culverts')
                      AND s.easting BETWEEN c.easting - 150 AND c.easting + 150
                      AND s.northing BETWEEN c.northing - 150 AND c.northing + 150)
                   AS structure_m
            FROM _cross_in c
            """
        )
    frame = frame.merge(near, on=["easting", "northing"], how="left")

    # Is this crossing in country the Trust covers AT ALL? Without that, the
    # corroboration flag is substantially a map of the register's extent rather than
    # of whether a refusal is sound: the 232 corroborated cluster in the canal
    # Midlands and North West, and the uncorroborated scatter across Devon, Cornwall,
    # west Wales and the south coast, largely outside the canal network. The sharp
    # list is the crossings the register COULD have spoken about and did not.
    with db.registered("_cov_in", frame[["easting", "northing"]]):
        cover = db.df(
            """
            SELECT c.easting, c.northing,
                   EXISTS (SELECT 1 FROM structure s
                           WHERE s.easting BETWEEN c.easting - 2000 AND c.easting + 2000
                             AND s.northing BETWEEN c.northing - 2000 AND c.northing + 2000)
                   AS in_trust_country
            FROM _cov_in c
            """
        )
    return frame.merge(cover, on=["easting", "northing"], how="left")


def _share(value) -> str:
    """Format a reached share so that only a complete basin can read as complete.

    A basin at 0.99794 with 6.57 km of river still stranded printed as "100% reached"
    under a plain round, in a section headed "Every basin short of 100%". Seventeen
    basins did, holding about 34 km between them. **A reader quotes the number and not
    the clause after it**, and §9 is the one place this project may not be loose: *every
    basin either reaches 100% reachable, or its shortfall is named with a reason.* So
    the format floors instead of rounding, and 100% is reserved for exactly 1.0.
    """
    if value is None or pd.isna(value):
        return "—"
    if value >= 1.0:
        return "100%"
    import math

    return f"{math.floor(float(value) * 1000) / 10:.1f}%"


def _stranded_components(g, labels) -> pd.DataFrame:
    """In-scope components from which the sea cannot be reached at all."""
    reach = db.df("SELECT link_id, reaches_tidal FROM link_reach")
    reached = set(reach.loc[reach["reaches_tidal"], "link_id"])
    scope = db.df("SELECT link_id, in_scope FROM link_scope")
    in_scope = set(scope.loc[scope["in_scope"], "link_id"])

    frame = pd.DataFrame(
        {
            "link_id": g.link_ids,
            "component": labels[g.u].astype(int),
            "km": g.length / 1000.0,
            "form": g.form,
            "node": [str(g.nodes[i]) for i in g.u],
            "reached": [lid in reached for lid in g.link_ids],
            "in_scope": [lid in in_scope for lid in g.link_ids],
        }
    )
    per = frame.groupby("component").agg(
        km=("km", "sum"), any_reached=("reached", "any"), any_scope=("in_scope", "any")
    )
    keep = per[(~per["any_reached"]) & per["any_scope"]].sort_values(
        "km", ascending=False
    )
    if keep.empty:
        return pd.DataFrame(columns=["label", "km", "forms", "easting", "northing"])

    rows = []
    members = frame[frame["component"].isin(keep.index)]
    names = db.df("SELECT link_id, name FROM link WHERE name IS NOT NULL")
    name_of = dict(zip(names["link_id"], names["name"]))
    places = db.df("SELECT node_id, easting, northing FROM node")
    place_of = {r.node_id: (r.easting, r.northing) for r in places.itertuples()}
    for component, group in members.groupby("component"):
        named = [name_of.get(lid) for lid in group["link_id"] if lid in name_of]
        label = (
            pd.Series(named).value_counts().index[0]
            if named
            else f"component {int(component)}"
        )
        e, n = place_of.get(group["node"].iloc[0], (None, None))
        rows.append(
            {
                "label": label,
                "km": float(keep.loc[component, "km"]),
                "forms": "/".join(sorted(set(group["form"].dropna()))),
                "easting": e,
                "northing": n,
            }
        )
    return pd.DataFrame(rows).sort_values("km", ascending=False).reset_index(drop=True)


def _name_the_shortfalls(basin_rows: pd.DataFrame) -> pd.DataFrame:
    """Give every basin that is short of 100% a reason, in words.

    PLAN.md §9: *Every basin either reaches 100% reachable, or its shortfall is named
    with a reason. "Improved a lot" is not a reason, and neither is "it is only a
    canal" — canals are inside the requirement (D-011).*

    So the reason has to say what is actually still wrong there, and the honest answer
    for most of what remains is that the evidence does not reach a conclusion — which
    is a reason, and a different one from "a canal, therefore excused".
    """
    from .. import candidates as cand

    frame = basin_rows.copy()
    frame["shortfall_reason"] = ""
    short = frame["km"] > frame["reached_km"] + 1e-9
    if not short.any():
        frame.loc[~short, "shortfall_reason"] = "reaches tidal water in full"
        return frame
    frame.loc[~short, "shortfall_reason"] = "reaches tidal water in full"

    evidence = cand.build()
    if evidence.empty:
        frame.loc[short, "shortfall_reason"] = (
            "unreached length remains, and the candidate generator offers no evidence "
            "about it — look at the place"
        )
        return frame

    per_basin = {}
    for basin_id, group in evidence.groupby("basin_id"):
        biggest = group.sort_values("upstream_km", ascending=False).iloc[0]
        forms = group.groupby("form")["upstream_km"].sum().sort_values(ascending=False)
        dominant = forms.index[0] if len(forms) else "watercourse"
        shapes = group["suggests"].value_counts()
        top_shape = shapes.index[0] if len(shapes) else "none"
        n = int(group["sink_node"].nunique())

        if top_shape.startswith("none"):
            why = (
                f"{n} dead end(s) remain, mostly {dominant}, and none has a "
                f"watercourse that already drains within 2 km. These are stranded "
                f"regions rather than gaps: nothing near them can carry the water "
                f"out, so closing them needs a judgement at the place and not a rule."
            )
        elif dominant == "canal":
            why = (
                f"{n} dead end(s) remain, mostly canal. Canals are inside the "
                f"reachability requirement (D-011) and this is not an excuse: it "
                f"records that the receiving structure — a lock, a weir, a feeder — "
                f"is not drawn by the survey and is not within the {top_shape} "
                f"evidence this build acts on."
            )
        else:
            why = (
                f"{n} dead end(s) remain, mostly {dominant}. The evidence points to "
                f"{top_shape}, but each was refused by the rules that were applied — "
                f"the names conflict, the reach is too long, or the line would cross "
                f"another watercourse. The largest holds {biggest.upstream_km:,.1f} km "
                f"above it at {biggest.sink_e:,.0f} E {biggest.sink_n:,.0f} N."
            )
        per_basin[basin_id] = why

    frame.loc[short, "shortfall_reason"] = (
        frame.loc[short, "basin_id"]
        .map(per_basin)
        .fillna(
            "unreached length remains but no dead end inside this basin is in scope; "
            "the water leaves it by a link whose downstream end is elsewhere"
        )
    )
    return frame


def _write_human_report(report: Report, ranked, by_form, worst) -> None:
    """The audit, human-readable as well as machine-readable (§7)."""
    lines = [
        "# Stage 1 audit",
        "",
        "Machine-readable alongside this at `audit.json`. Every finding carries a",
        "coordinate, because every serious defect in the predecessor was invisible in",
        "the national figures and obvious at the place.",
        "",
        "## Reachability",
        "",
    ]
    reach = report.sections["reachability"]
    lines += [
        f"- Great Britain: **{reach['gb_share']:.2%}** — "
        f"{reach['reached_gb_km']:,.0f} km reaches tidal water "
        f"of {reach['total_gb_km']:,.0f} km",
        f"- In scope: **{reach['in_scope_share']:.2%}** — "
        f"{reach['reached_in_scope_km']:,.0f} km reaches tidal water "
        f"of {reach['total_in_scope_km']:,.0f} km",
        "",
        "## Dead ends",
        "",
    ]
    d = report.sections["dead_ends"]
    lines += [
        f"- {d['national']:,} nodes nationally have inflows and no outflow",
        f"- {d['in_scope']:,} of them are in scope; {d['at_tidal_water']:,} stand at "
        "tidal water and are correct",
        f"- **{d['defects']:,} do not, and are the work**",
        f"- {d['over_nominal']:,} carry more than a nominal catchment draining into nowhere",
        "",
        "### By the form of the water arriving",
        "",
        "| form | links | km | nodes |",
        "|---|---:|---:|---:|",
    ]
    for r in by_form.itertuples():
        lines.append(f"| {r.form} | {int(r.links):,} | {r.km:,.1f} | {int(r.nodes):,} |")
    lines += [
        "",
        "## In-scope basins, ranked by unreached length",
        "",
        "A national figure hides a basin at a much lower share, and that basin is the",
        "entire finding. This is the list to work down.",
        "",
        "| basin | km | reached km | unreached km | share |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in ranked.head(40).itertuples():
        share = _share(r.share)
        lines.append(
            f"| {r.label or r.basin_id} | {r.km:,.1f} | {r.reached_km:,.1f} | "
            f"{r.unreached_km:,.1f} | {share} |"
        )
    lines += [
        "",
        "## Every basin short of 100%, and why (§9)",
        "",
        "*\"Improved a lot\" is not a reason, and neither is \"it is only a canal\" —",
        "canals are inside the requirement (D-011).*",
        "",
    ]
    for r in ranked.head(60).itertuples():
        reason = getattr(r, "shortfall_reason", "")
        if not reason or reason == "reaches tidal water in full":
            continue
        share = _share(r.share)
        lines.append(f"- **{r.label or r.basin_id}** ({share} reached) — {reason}")
    lines += [
        "",
        "## The largest dead ends, by the length actually stranded above them",
        "",
        "**Ranked on `stranded km`, not `upstream km`, and the difference matters.**",
        "A dead end can sit on water that leaves by another route: Stanlow Pool, on the",
        "Manchester Ship Canal, stood at the top of the Cheshire list with 1,514.5 km",
        "above it and *nothing stranded at all*, because the node above it also drains",
        "west to Eastham. It is a cul-de-sac off a working drain. Ranking by catchment",
        "put a non-defect first in the list this section asks someone to work down,",
        "which is the most expensive place to be wrong — the reader spends their",
        "attention where there is nothing to find.",
        "",
        "| name | form | stranded km | upstream km | easting | northing |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in worst.head(40).itertuples():
        lines.append(
            f"| {r.name or '—'} | {r.form or '—'} | {r.stranded_km:,.1f} | "
            f"{r.upstream_km:,.1f} | {r.easting:,.0f} | {r.northing:,.0f} |"
        )
    from ..report import write_text

    write_text(paths.PUBLISHED / "audit" / "audit.md", "\n".join(lines) + "\n")


def _generalisation() -> dict:
    """Measure the generalisation OS Open Rivers has already applied.

    §10: *the survey has already generalised, and the audit should record what that
    generalisation actually is, because it is measurable at Stage 1 and nowhere else.*
    Once a later stage puts its own vertices on a line, the survey's own vertex
    spacing is gone and cannot be recovered from the result.

    Two quantities, both from the geometry as delivered:

    **Vertex spacing** — the distance between consecutive vertices. This is the
    sampling interval: the survey says nothing about the course between two
    vertices, so a bend shorter than this spacing is not absent from the river, it
    is absent from the *record* of the river.

    **Sagitta** — how far each interior vertex sits off the straight line joining
    its two neighbours. This is the amplitude of detail that survived: a vertex
    kept a bend, and the sagitta is how big that bend was. Together the pair say
    that OS retained detail down to about this size at about this spacing, and a
    later stage proposing to move a line by less than that is arguing with noise.

    Measured on `link`, which holds the survey as delivered and nothing else —
    everything this project split or added lives in `repair_link`. Retired links are
    kept in the measurement deliberately: a link we later split was still surveyed by
    OS at OS's own spacing, and dropping it would bias the result toward the
    geometry we happened not to touch.
    """
    import shapely

    con = db.get()
    rows = con.execute(
        """
        SELECT ST_AsWKB(l.geom) AS wkb FROM link l WHERE l.origin = 'survey'
        """
    ).fetchall()
    if not rows:
        raise StageError("no as-surveyed links to measure generalisation on")

    spacing: list[np.ndarray] = []
    sagitta: list[np.ndarray] = []
    vertices = 0
    for (wkb,) in rows:
        xy = shapely.get_coordinates(shapely.from_wkb(bytes(wkb)))
        if len(xy) < 2:
            continue
        vertices += len(xy)
        seg = np.hypot(*(xy[1:] - xy[:-1]).T)
        spacing.append(seg[seg > 0])
        if len(xy) < 3:
            continue
        a, b, c = xy[:-2], xy[1:-1], xy[2:]
        chord = c - a
        chord_len = np.hypot(*chord.T)
        ok = chord_len > 0
        # perpendicular distance from b to the line a->c
        h = np.abs(np.cross(chord[ok], b[ok] - a[ok])) / chord_len[ok]
        sagitta.append(h)

    spacing_all = np.concatenate(spacing)
    sagitta_all = np.concatenate(sagitta)
    pct = [5, 25, 50, 75, 95, 99]
    return {
        "links_measured": len(rows),
        "vertices": vertices,
        "spacing_m": dict(zip(pct, np.percentile(spacing_all, pct).round(1))),
        "spacing_min_m": float(spacing_all.min().round(2)),
        "sagitta_m": dict(zip(pct, np.percentile(sagitta_all, pct).round(2))),
        "sagitta_max_m": float(sagitta_all.max().round(1)),
    }


# How close a basin must lie to Mean High Water, or to a tidal terminus, before its
# having no outlet is the expected coastal case rather than a hole in the network.
# 500 m is the survey's own order of generalisation, not a tuned number.
COASTAL_M = 500.0


def _sweep_the_outletless_basins(report: Report, findings: list[Finding]) -> None:
    """Check EVERY basin with no outlet, not a sample of them.

    This was a caveat before it was a check: the release said the ones examined were
    coastal catchments and that they had not all been swept. That is two claims, and the
    second undoes the first — the member of such a set worth finding is exactly the one
    a sample does not reach. Sweeping all of them costs seconds.

    A basin is explained when it touches Mean High Water OR stands beside a tidal
    terminus. **Both tests are needed and neither alone is enough.** An estuary is wide:
    a basin on the inner shore of the Ribble sits 2.3 km from the outer coast and 48 m
    from tidal water, and against the coastline alone it reads as an inland hole.
    """
    frame = _outletless_against_the_coast()
    if frame.empty:
        report.add("outletless_basins", {"total": 0, "in_scope": 0, "unexplained": 0})
        return

    scoped = frame[frame["in_scope"]]
    explained = scoped[(scoped.coast_m <= COASTAL_M) | (scoped.tidal_m <= COASTAL_M)]
    unexplained = scoped[(scoped.coast_m > COASTAL_M) & (scoped.tidal_m > COASTAL_M)]

    report.add("outletless_basins", {
        "total": int(len(frame)),
        "in_scope": int(len(scoped)),
        "explained_as_coastal_or_tidal": int(len(explained)),
        "unexplained": int(len(unexplained)),
        "threshold_m": COASTAL_M,
        "in_scope_km2": round(float(scoped.area_km2.sum()), 1),
    })
    log.detail(
        f"basins with no outlet: {len(frame):,} ({len(scoped):,} in scope, "
        f"{scoped.area_km2.sum():,.0f} km2). Swept against Mean High Water and the "
        f"tidal termini: {len(explained):,} are coastal or estuarine, "
        f"{len(unexplained):,} are not explained by either"
    )
    for row in unexplained.itertuples():
        findings.append(
            Finding(
                kind="outletless_basin_inland",
                subject=row.basin_id,
                detail=(
                    f"{row.area_km2:,.1f} km2 basin with no outlet node stands "
                    f"{row.coast_m / 1000:,.1f} km from Mean High Water and "
                    f"{row.tidal_m / 1000:,.1f} km from the nearest tidal terminus — "
                    "so it is neither a coastal nor an estuarine catchment, and its "
                    "water has nowhere in this network to go"
                ),
                metrics={"area_km2": round(float(row.area_km2), 2),
                         "coast_m": round(float(row.coast_m), 1),
                         "tidal_m": round(float(row.tidal_m), 1)},
            )
        )


def _outletless_against_the_coast() -> pd.DataFrame:
    """Every basin with no outlet node, and how far it lies from Mean High Water.

    **The question this settles.** A basin the network never drains out of is either the
    expected coastal case — a cliff or ria catchment whose water reaches the sea without
    a mapped watercourse — or a genuine hole, a catchment with nowhere for its water to
    go that nobody has noticed. Those are opposite findings and they had been reported as
    one: *"the ones examined are coastal, and they have not all been checked."* A sample
    is not a sweep, and the interesting member of a set like this is precisely the one a
    sample misses.

    **Measured against Boundary-Line's `high_water`, which is Mean High Water itself**
    rather than against a country polygon. The country polygons stop AT Mean High Water,
    so testing containment in them answers a different question and answers it the same
    way for every coastal basin.

    **Distance is evidence, not a verdict.** An estuary is wide, and a basin on its inner
    shore can stand kilometres from the outer coast while sitting beside tidal water — so
    the distance to the nearest tidal terminus is carried alongside, and it is that pair
    which distinguishes an estuarine basin from an inland one.
    """
    import geopandas as gpd

    con = db.get()
    basins = gpd.GeoDataFrame(
        con.execute(
            "SELECT basin_id, label, area_km2, in_scope, ST_AsWKB(geom) AS wkb "
            "FROM basin WHERE outlet_node IS NULL"
        ).df().assign(geometry=lambda d: gpd.GeoSeries.from_wkb(
            [bytes(v) for v in d.pop("wkb")])),
        geometry="geometry", crs=config.param("crs.working"),
    )
    if basins.empty:
        return basins

    gpkg = acquire.one("os_boundary_line", "bdline_gb.gpkg")
    coast = gpd.read_file(gpkg, layer="high_water").to_crs(basins.crs)
    near_coast = gpd.sjoin_nearest(
        basins[["basin_id", "geometry"]], coast[["geometry"]],
        how="left", distance_col="coast_m",
    ).groupby("basin_id", as_index=False).coast_m.min()

    termini = gpd.GeoDataFrame(
        con.execute(
            "SELECT node_id, ST_AsWKB(geom) AS wkb FROM node WHERE terminus = 'tidal'"
        ).df().assign(geometry=lambda d: gpd.GeoSeries.from_wkb(
            [bytes(v) for v in d.pop("wkb")])),
        geometry="geometry", crs=basins.crs,
    )
    near_tidal = gpd.sjoin_nearest(
        basins[["basin_id", "geometry"]], termini[["geometry"]],
        how="left", distance_col="tidal_m",
    ).groupby("basin_id", as_index=False).tidal_m.min()

    out = (basins.drop(columns="geometry")
           .merge(near_coast, on="basin_id").merge(near_tidal, on="basin_id"))
    return out.sort_values(["coast_m", "basin_id"], ascending=[False, True])
