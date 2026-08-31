"""Stage: grow the network upstream from the sea (PLAN.md §5, D-005).

**Do not patch the network where it looks broken. Grow it from the sea, and let
whatever fails to arrive be the report.** Seed at tidal termini; admit a link only when
the node at its downstream end is already in the network; repeat until nothing more is
admitted.

The two framings sound equivalent and are not. Patching asks *is this hole closed?*,
and answers yes for a hole whose closure leads somewhere else broken — a link-by-link
check once reported every gap bridged while 3,440 km of river was still draining into
nowhere. The crawl asks the only question that matters, *can the water get out?*, and
cannot answer yes for a reach that cannot.

**Seeds are a finding, not a parameter.** A seed is a node with no outflow standing at
tidal water. They come from the survey's own `form = tidalRiver`, not from a coastline:
a coastline decides the question by distance from a modern shore, and is wrong at
exactly the estuaries where the answer matters. And they are taken from anywhere in an
in-scope basin, **including Scotland** — the Border Esk's mouth is in Dumfriesshire, and
a basin seeded only inside England and Wales would strand the whole of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config, db, graph, paths, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Report, log

LINK_REACH = artefact("link_reach")
SEED = artefact("seed")


def seed_nodes() -> pd.DataFrame:
    """The seed set. Write it out and look at it (§5)."""
    p = config.params()
    forms = ", ".join(f"'{f}'" for f in p("seeds.tidal_forms"))
    restrict = p("seeds.restrict_to_england_and_wales")

    # A seed is a node with no outflow standing at tidal water. "No outflow" is asked
    # of the routing graph, so a reversal that gave a node an outflow removes it from
    # the seed set, which is correct.
    country_clause = ""
    if restrict:
        raise StageError(
            "conf/params.yml sets seeds.restrict_to_england_and_wales, which PLAN.md §5 "
            "forbids: the Border Esk's mouth is in Dumfriesshire, and a basin seeded "
            "only inside England and Wales strands the whole of it."
        )

    return db.df(
        f"""
        WITH outflow AS (SELECT DISTINCT from_node AS node_id FROM edge),
             inflow  AS (SELECT DISTINCT to_node   AS node_id FROM edge),
             tidal   AS (
                SELECT DISTINCT e.to_node AS node_id
                FROM edge e WHERE e.form IN ({forms})
                UNION
                SELECT DISTINCT e.from_node FROM edge e WHERE e.form IN ({forms})
             )
        SELECT n.node_id, n.easting, n.northing,
               coalesce(nb.basin_in_scope, false) AS basin_in_scope,
               (SELECT count(*) FROM edge e WHERE e.to_node = n.node_id) AS inflows,
               (SELECT coalesce(sum(e.length_m), 0) FROM edge e WHERE e.to_node = n.node_id)
                   AS inflow_length_m,
               (SELECT any_value(e.form) FROM edge e WHERE e.to_node = n.node_id) AS form
        FROM node n
        JOIN inflow  i ON i.node_id = n.node_id
        JOIN tidal   t ON t.node_id = n.node_id
        LEFT JOIN outflow o ON o.node_id = n.node_id
        LEFT JOIN node_basin nb ON nb.node_id = n.node_id
        WHERE o.node_id IS NULL
        ORDER BY inflow_length_m DESC, n.node_id
        {country_clause}
        """
    )


@PIPELINE.stage(
    "crawl",
    "grow the network upstream from tidal termini; what it misses is the defect list",
    reads=["edge", "node", "node_basin", "link_scope"],
    writes=["link_reach", "seed"],
    params=["seeds", "forms"],
    always=True,
)
def run() -> dict:
    con = db.get()
    report = Report("crawl")

    seeds = seed_nodes()
    if seeds.empty:
        raise StageError(
            "no seeds at all. A seed is a node with no outflow standing at tidal "
            "water; if there are none, either the orientation is wrong or `form` is "
            "not being read."
        )
    con.execute("DROP TABLE IF EXISTS seed")
    with db.registered("_seed_in", seeds):
        con.execute("CREATE TABLE seed AS SELECT * FROM _seed_in")

    log.info(f"  {len(seeds):,} seeds — nodes with no outflow standing at tidal water")
    log.frame(
        "the seed set, largest first (§5 says to write it out and look at it)",
        seeds.head(12)[["node_id", "easting", "northing", "inflows", "inflow_length_m", "form"]],
        12,
    )

    g = graph.load("edge")
    seed_idx = g.indices_of(seeds["node_id"].tolist())
    admitted, edge_seed, hops = g.reachable_from_sea(seed_idx)

    frame = pd.DataFrame(
        {
            "link_id": g.link_ids,
            "reaches_tidal": admitted,
            "seed_node": [
                str(g.nodes[s]) if s >= 0 else None for s in edge_seed
            ],
            "hops": hops,
        }
    )
    schema.create("link_reach")
    with db.registered("_reach_in", frame):
        con.execute(
            "INSERT INTO link_reach SELECT link_id, reaches_tidal, seed_node, "
            "CASE WHEN hops < 0 THEN NULL ELSE hops END FROM _reach_in ORDER BY link_id"
        )

    total_km = float(g.length.sum()) / 1000.0
    reached_km = float(g.length[admitted].sum()) / 1000.0
    in_scope = con.execute(
        """
        SELECT sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END) / 1000.0,
               sum(e.length_m) / 1000.0
        FROM edge e
        JOIN link_reach r USING (link_id)
        JOIN link_scope s ON s.link_id = e.link_id
        WHERE s.in_scope
        """
    ).fetchone()

    log.table(
        "reachability — the headline number and the one to watch (§6)",
        ["extent", "reached km", "total km", "share"],
        [
            ("Great Britain", round(reached_km, 0), round(total_km, 0),
             f"{reached_km / total_km:.2%}"),
            ("in scope", round(in_scope[0] or 0, 0), round(in_scope[1] or 0, 0),
             f"{(in_scope[0] or 0) / (in_scope[1] or 1):.2%}"),
        ],
    )

    report.add("seeds", len(seeds))
    report.add("reachable", {
        "gb_km": round(reached_km, 1),
        "gb_share": round(reached_km / total_km, 6),
        "in_scope_km": round(in_scope[0] or 0, 1),
        "in_scope_share": round((in_scope[0] or 0) / (in_scope[1] or 1), 6),
    })
    report.write_json(paths.PUBLISHED / "audit" / "crawl.json")

    return {
        "seeds": len(seeds),
        "reached_km": round(reached_km, 1),
        "reachable_share": round(reached_km / total_km, 4),
        "in_scope_share": round((in_scope[0] or 0) / (in_scope[1] or 1), 4),
    }
