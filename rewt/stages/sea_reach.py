"""Stage: can the water get to the SEA NETWORK, not merely to tidal water?

**Two readings, and the difference is the whole point.** `crawl` asks whether a link
can reach tidal water — water the survey itself draws as tidal, which is where §1's
traversability test has always stopped. This asks whether it can reach the routes §10
builds across open water between every mouth. The second question is strictly harder,
and a mouth can fail it: 693 were recorded `blocked`, meaning the sea could not take
them, and a river arriving at one has reached tidal water and still cannot get out.

**It exists because the sea network was invisible to reachability.** §10 built 4,183
routes, the exporter published them, the viewer drew them — and **not one of them was in
`edge`**, so no reading could traverse them. 2,751 nodes had a sea route attached and no
figure anywhere reflected it. The network was correct, the map was correct, and the two
had never been connected; a coastal dead end was reported as a defect while the route
that drains it sat in the same GeoPackage.

**Nothing is invented here.** No geometry is added and no correction is applied: this
admits routes that already exist into a reading that could not see them. That ordering
matters for what comes next — a connector proposed to drain a region the sea already
drains is geometry invented to solve a problem that was never there, and until now the
proposer had no way to know the difference.

**The seeds are the sea network's own endpoints**, not the tidal termini. A node is on
the sea network when a sea link touches it, which is the same relation §10 used to
decide which mouths it could serve; the walk upstream from there is the crawl's, run
against the same routing graph, so the two readings differ in their seeds and in nothing
else.
"""

from __future__ import annotations

import pandas as pd

from .. import config, db, graph, paths, schema, sea
from ..pipeline import PIPELINE
from ..report import Report, log


@PIPELINE.stage(
    "sea_reach",
    "the second reading: can the water reach the sea network, not just tidal water",
    reads=["edge", "sea_link", "sea_entry", "link_scope", "link_reach"],
    writes=["link_sea_reach"],
    always=True,
)
def run() -> dict:
    con = db.get()
    report = Report("sea_reach")

    # WALKED ON THE COMPLETED GRAPH — `edge` WITH §10'S ROUTES IN IT.
    #
    # Two earlier attempts got this wrong and both were instructive. Seeding a walk over
    # `edge` alone from the nodes that END a sea route gave 74.97% against a published
    # 93.74%: the routes were not traversable, so the walk could only reach what already
    # drained. Deriving it as a filter on the crawl — reaches tidal water AND the
    # terminus is in a system the sea can take — gave the published figure back exactly,
    # which was correct and could never help a mouth the crawl does not reach.
    #
    # **A blocked mouth is precisely a mouth the crawl does not reach.** 541 of the 693
    # already carry a sea route on their own node id, so nothing needed inventing; the
    # routes simply were not in the graph. Walking `edge+sea` from the sea makes them
    # drain, which is what §10 was for and what `schema.py` has always said should be
    # true of a sea route.
    g = graph.load("edge+sea")
    is_sea = g.form == "sea"
    sea_nodes = sorted(set(g.nodes[g.u[is_sea]]) | set(g.nodes[g.v[is_sea]]))
    log.info(f"  {int(is_sea.sum()):,} sea routes are in the graph, touching "
             f"{len(sea_nodes):,} nodes")

    # TWO SEEDS, BECAUSE THERE ARE TWO WAYS TO THE SEA AND NEITHER SUBSUMES THE OTHER.
    #
    # Walking from the sea network alone gave 74.97%, and the Humber shows why: the
    # Trent's terminus is a SINK with no outflow, and no §10 route reached it, so a
    # direction-respecting walk stops there. But tidal water is physically continuous —
    # if an estuary meets the sea anywhere, all of it drains — which is the relation
    # `systems_the_sea_can_take` already captures and a graph walk cannot see, because
    # the survey draws no edge along the width of an estuary.
    #
    # Filtering the crawl by that relation alone gave the published 93.53% and could
    # never help a blocked mouth, since a blocked mouth is by definition one the crawl
    # does not reach. So the seeds are the union: every node the sea network touches,
    # and every tidal node whose system the sea can take. The first admits the 541
    # coastal mouths that already carry a route; the second admits the estuaries.
    tidal_ok = sea.systems_the_sea_can_take(con)

    # A MOUTH THE GATE WITHHELD MUST NOT BE A WAY TO THE SEA BY ANY OTHER ROUTE.
    #
    # The graph already refuses to attach a blocked mouth more than `sea.max_coast_m`
    # from Mean High Water — but `systems_the_sea_can_take` is a second relation and did
    # not know about it, so F28D09AC at 210 m was withheld from the sea network and
    # admitted by the tidal systems anyway. The gate is a decision about the mouth, not
    # about one of the two ways of reaching it, so it is applied to the union.
    withheld = {r[0] for r in con.execute(
        "SELECT node_id FROM sea_entry WHERE kind = 'blocked' AND coast_m > ? "
        "AND node_id IS NOT NULL",
        [float(config.param("sea.max_coast_m"))],
    ).fetchall()}
    seeds = sorted((set(sea_nodes) | set(tidal_ok)) - withheld)
    log.detail(f"{len(withheld):,} blocked mouths are withheld as too far inland "
               f"(> {config.param('sea.max_coast_m'):g} m from Mean High Water)")
    log.info(f"  seeds: {len(sea_nodes):,} on the sea network, {len(tidal_ok):,} in a "
             f"tidal system it can take — {len(seeds):,} together")

    admitted, edge_seed, hops = g.reachable_from_sea(g.indices_of(seeds))

    # The sea's own routes are not part of the answer: asking whether a sea route
    # reaches the sea is asking whether a thing reaches itself.
    frame = pd.DataFrame({
        "link_id": g.link_ids,
        "reaches_sea": admitted,
        "entry_node": [str(g.nodes[s]) if s >= 0 else None for s in edge_seed],
        "hops": hops,
        "_sea": is_sea,
    })
    frame = frame[~frame["_sea"]].drop(columns="_sea")

    schema.create("link_sea_reach")
    with db.registered("_sea_reach_in", frame):
        con.execute(
            "INSERT INTO link_sea_reach SELECT link_id, reaches_sea, entry_node, "
            "CASE WHEN hops < 0 THEN NULL ELSE hops END FROM _sea_reach_in "
            "ORDER BY link_id"
        )

    # THE TWO READINGS ARE NO LONGER NESTED, AND THAT IS THE POINT.
    #
    # Before the sea network was in the graph, reaching the sea was strictly harder than
    # reaching tidal water: the only way out was through a tidal link. Now a coastal
    # mouth can discharge through a sea wall and reach the sea without touching a
    # `tidalRiver` at all — which is exactly the drainage §10 was built to represent and
    # the survey does not draw. So a cross-tabulation is the honest presentation and a
    # single "share reaching the sea" is not: the interesting cell is the one that only
    # the second reading admits, and a subtraction would hide it.
    rows = con.execute(
        """
        SELECT r.reaches_tidal, q.reaches_sea, sum(e.length_m)/1000.0 AS km, count(*) AS n
        FROM edge e
        JOIN link_reach r      USING (link_id)
        JOIN link_sea_reach q  USING (link_id)
        JOIN link_scope s      USING (link_id)
        WHERE s.in_scope
        GROUP BY 1, 2 ORDER BY 1 DESC, 2 DESC
        """
    ).fetchall()
    total = sum(r[2] for r in rows) or 1.0
    labels = {
        (True, True): "reaches tidal water, and the sea",
        (True, False): "reaches tidal water only — the sea cannot take it",
        (False, True): "reaches the SEA only — coastal drainage, no tidal link",
        (False, False): "reaches neither — the defect",
    }
    log.table(
        "in-scope network, by which reading admits it",
        ["km", "share", "links", "reading"],
        [[f"{km:,.0f}", f"{km / total:.1%}", f"{n:,}", labels[(bool(t), bool(sea))]]
         for t, sea, km, n in rows],
    )
    cell = {(bool(t), bool(sea)): (km, n) for t, sea, km, n in rows}
    sea_only = cell.get((False, True), (0.0, 0))
    defect = cell.get((False, False), (0.0, 0))
    detail = {
        "in_scope_km": round(total, 1),
        "reaches_tidal_km": round(sum(k for (t, _), (k, _n) in cell.items() if t), 1),
        "reaches_sea_km": round(sum(k for (_t, s), (k, _n) in cell.items() if s), 1),
        "sea_only_km": round(sea_only[0], 1),
        "sea_only_links": sea_only[1],
        "reaches_neither_km": round(defect[0], 1),
        "reaches_neither_links": defect[1],
    }
    log.done(
        f"{sea_only[0]:,.0f} km ({sea_only[1]:,} links) reaches the sea WITHOUT reaching "
        f"tidal water — coastal drainage the survey does not draw, and stranded until "
        f"§10's routes entered the graph. {defect[0]:,.0f} km reaches neither, and that "
        "is the defect list."
    )

    report.add("sea_reach", detail)
    report.write_json(paths.PUBLISHED / "audit" / "sea_reach.json")
    return detail
