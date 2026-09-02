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

from .. import db, paths, schema, sea
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

    # DERIVED FROM THE CRAWL, NOT WALKED AGAIN. Two attempts at a separate walk got
    # this wrong in both directions, and the second failure is the one that shows the
    # right shape.
    #
    # Seeding from the 4,184 nodes that END a sea route gave 74.97% against the audit's
    # published 93.74%: being SERVED by the sea network and ENDING one of its routes are
    # different things, the network is a spanning tree over 11,265 entries, and the
    # Trent's terminus is an entry on no sea link at all — so the whole Humber fell out.
    #
    # Seeding from `systems_the_sea_can_take` then gave 96.56%, which is HIGHER than the
    # share reaching tidal water. **Reaching the sea cannot exceed reaching tidal water**
    # — it is a strictly harder question — and a negative gap is the arithmetic saying
    # the walk was the wrong instrument. Those 13,542 seeds include tidal nodes that are
    # not sinks, so walking up from them admits water that never reaches a terminus.
    #
    # The relation is a FILTER on the crawl's own answer: a link reaches the sea when it
    # reaches tidal water AND the terminus it drains to is in a system the sea can take.
    # Being a subset is then true by construction rather than by luck, and it is the
    # audit's published formula made per-link — so the aggregate cannot drift from the
    # figure, because they are the same computation and not two agreeing ones.
    reachable = sea.systems_the_sea_can_take(con)
    log.info(f"  {len(reachable):,} tidal nodes are in a system the sea network can take")

    con.execute("DROP TABLE IF EXISTS _sea_ok")
    con.execute("CREATE TEMP TABLE _sea_ok (node_id VARCHAR)")
    if reachable:
        con.executemany("INSERT INTO _sea_ok VALUES (?)",
                        [(n,) for n in sorted(reachable)])

    schema.create("link_sea_reach")
    con.execute(
        """
        INSERT INTO link_sea_reach
        SELECT r.link_id,
               r.reaches_tidal AND r.seed_node IN (SELECT node_id FROM _sea_ok),
               CASE WHEN r.seed_node IN (SELECT node_id FROM _sea_ok)
                    THEN r.seed_node END,
               r.hops
        FROM link_reach r ORDER BY r.link_id
        """
    )

    # BOTH READINGS, SIDE BY SIDE, over the same table. The release notes already say
    # that publishing one without the other misleads (D-061); the same applies here, and
    # more sharply, because this is the reading that can fail.
    rows = con.execute(
        """
        SELECT s.in_scope,
               sum(e.length_m) / 1000.0                                      AS km,
               sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END)/1000.0 AS tidal_km,
               sum(CASE WHEN q.reaches_sea   THEN e.length_m ELSE 0 END)/1000.0 AS sea_km
        FROM edge e
        JOIN link_reach r      USING (link_id)
        JOIN link_sea_reach q  USING (link_id)
        JOIN link_scope s      USING (link_id)
        GROUP BY s.in_scope ORDER BY s.in_scope DESC
        """
    ).fetchall()
    log.table(
        "the two readings — the second is the one that can fail",
        ["extent", "km", "reaches tidal water", "reaches the sea network", "the gap"],
        [
            [
                "in scope" if in_scope else "out of scope",
                f"{km:,.0f}",
                f"{tidal_km / km:.2%}" if km else "-",
                f"{sea_km / km:.2%}" if km else "-",
                f"{tidal_km - sea_km:,.0f} km",
            ]
            for in_scope, km, tidal_km, sea_km in rows
        ],
    )

    scoped = next((r for r in rows if r[0]), None)
    detail = {}
    if scoped:
        _, km, tidal_km, sea_km = scoped
        detail = {
            "in_scope_km": round(km, 1),
            "reaches_tidal_km": round(tidal_km, 1),
            "reaches_sea_km": round(sea_km, 1),
            "reaches_tidal_share": round(tidal_km / km, 6) if km else None,
            "reaches_sea_share": round(sea_km / km, 6) if km else None,
        }
        # THE GAP IS THE FINDING. Length that gets to tidal water and no further is
        # water the survey says has arrived and the bathymetry says has not.
        gap = tidal_km - sea_km
        detail["tidal_but_not_sea_km"] = round(gap, 1)
        log.done(
            f"in scope: {tidal_km:,.0f} km reaches tidal water ({tidal_km/km:.2%}), "
            f"{sea_km:,.0f} km reaches the sea network ({sea_km/km:.2%}). "
            f"{gap:,.0f} km arrives at tidal water the sea cannot take."
        )
    report.add("sea_reach", detail)
    report.write_json(paths.PUBLISHED / "audit" / "sea_reach.json")
    return detail
