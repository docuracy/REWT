"""Turning the audit's defects into candidates a person can adjudicate.

PLAN.md §5 is the whole of this module:

> **Almost every fault is one of three shapes, and one question separates them: *which
> end of the stranded link touches the network?***
>
> | finding | what it is | remedy |
> |---|---|---|
> | downstream end is a node with inflows and **no outflow** | a real gap | a **connector** |
> | **upstream** end touches a draining line at ~0 m | drawn backwards | a **reversal** |
> | the end sits *on* another channel with no node | no gap at all | a **junction** |
> | a reach two basins need in **opposite** directions | neither | `mode: both` |
>
> Ask it **of every inflow separately**, not of the first that answers. Three channels
> arrive at a sink; reversing the wrong one gives the node an outflow pointing deeper
> into the same stranded region, and the total improves while the place stays broken.

So this module asks the question once per *inflow*, never once per node, and it records
what it found rather than what it concluded. **It proposes; it does not decide.** A
candidate becomes a correction only when a person writes it into `data/curated/` with a
reason and evidence — and the evidence a candidate carries is what makes that cheap.

The ordering is by the catchment standing above the defect, because that is the ranking
§6 asks for: *work down the list.*
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, db, graph
from .report import log


def _reached_nodes(g: graph.Graph) -> set[str]:
    """Nodes the crawl reached — the network the water can already leave from."""
    reach = db.df("SELECT link_id, reaches_tidal FROM link_reach")
    reached = set(reach.loc[reach["reaches_tidal"], "link_id"])
    out: set[str] = set()
    for link_id, u, v in zip(g.link_ids, g.u, g.v):
        if link_id in reached:
            out.add(str(g.nodes[u]))
            out.add(str(g.nodes[v]))
    return out


def _defect_inflows() -> pd.DataFrame:
    """Every link arriving at an in-scope dead end that is not at tidal water.

    One row per *inflow*, not per node. A node with three inflows appears three times,
    which is the point: reversing the wrong one of them improves the total and leaves
    the place broken.
    """
    return db.df(
        """
        WITH sink AS (
            SELECT e.to_node AS node_id
            FROM edge e
            GROUP BY 1
            HAVING count(*) > 0
        ),
        has_out AS (SELECT DISTINCT from_node AS node_id FROM edge),
        defect AS (
            SELECT s.node_id
            FROM sink s
            LEFT JOIN has_out h ON h.node_id = s.node_id
            JOIN node n ON n.node_id = s.node_id
            WHERE h.node_id IS NULL AND n.terminus <> 'tidal'
        )
        SELECT d.node_id                AS sink_node,
               e.link_id,
               e.from_node              AS upstream_node,
               e.length_m,
               e.form,
               l.publisher_id,
               l.name,
               n.easting                AS sink_e,
               n.northing               AS sink_n,
               un.easting               AS up_e,
               un.northing              AS up_n,
               nb.basin_id,
               coalesce(sc.in_scope, false) AS in_scope
        FROM defect d
        JOIN edge e   ON e.to_node = d.node_id
        JOIN link l   ON l.link_id = e.link_id
        JOIN node n   ON n.node_id = d.node_id
        JOIN node un  ON un.node_id = e.from_node
        LEFT JOIN node_basin nb ON nb.node_id = d.node_id
        LEFT JOIN link_scope sc ON sc.link_id = e.link_id
        WHERE coalesce(sc.in_scope, false)
        ORDER BY d.node_id, e.link_id
        """
    )


def _junction_evidence(node_ids: list[str], tolerance_m: float) -> pd.DataFrame:
    """Sink nodes sitting *on* a channel they are not an endpoint of.

    §5's third shape: no gap at all. The remedy is a junction, which adds no geometry —
    the target is cut and the node merged.
    """
    from . import topology

    renames = {
        "link_id": "junction_target",
        "distance_m": "junction_gap_m",
        "publisher_id": "junction_target_publisher",
    }
    hits = topology.nodes_on_other_links(node_ids, tolerance_m)
    # The empty case is renamed too. An empty result that carries different column
    # names from a non-empty one is a bug waiting for the day the answer is "none":
    # here it collided `link_id` against the caller's own and the merge silently
    # produced `link_id_x`. Once the junctions had been applied there were none left
    # to find, so the failure appeared only after the code had been working.
    if hits.empty:
        return hits.rename(columns=renames)
    return (
        hits.sort_values(["node_id", "distance_m", "link_id"])
        .groupby("node_id", as_index=False)
        .first()
        .rename(columns=renames)
    )


def _reversal_evidence(inflows: pd.DataFrame, reached: set[str]) -> pd.Series:
    """Does the inflow's *upstream* end touch a line that already drains?

    §5's second shape: the link is drawn backwards. The tell is that the end which is
    NOT at the dead end is attached to a part of the network the water can leave from —
    so turning this one link round gives the stranded reach an exit, rather than
    pointing it deeper into the same stranded region.
    """
    return inflows["upstream_node"].isin(reached)


def _nearest_draining_link(inflows: pd.DataFrame, radius_m: float) -> pd.DataFrame:
    """The nearest link that ALREADY reaches tidal water, and whether it shares a name.

    This is the strongest evidence there is for §5's first shape. The largest defect in
    the country is a *River Great Ouse* link ending at a node OS itself classifies as
    an `outlet`, 56 m from another *River Great Ouse* link that drains to the sea. A
    watercourse that stops and resumes under the same name, with the far side draining,
    is a gap in the survey's topology and not a feature of the river.

    The name is what raises it above proximity. Something is within 2 km of almost
    every dead end in the country; the same *river* is not.
    """
    if inflows.empty:
        return pd.DataFrame(
            columns=["sink_node", "drain_link", "drain_publisher", "drain_name",
                     "drain_form", "drain_gap_m", "drain_same_name"]
        )
    sinks = inflows[["sink_node", "sink_e", "sink_n"]].drop_duplicates()
    with db.registered("_dsink_in", sinks):
        frame = db.df(
            f"""
            WITH cand AS (
                SELECT s.sink_node, l.link_id, l.publisher_id, l.name, l.form,
                       ST_Distance(l.geom, ST_Point(s.sink_e, s.sink_n)) AS gap_m
                FROM _dsink_in s
                JOIN link l
                  ON  ST_XMax(l.geom) >= s.sink_e  - {radius_m}
                  AND ST_XMin(l.geom) <= s.sink_e  + {radius_m}
                  AND ST_YMax(l.geom) >= s.sink_n - {radius_m}
                  AND ST_YMin(l.geom) <= s.sink_n + {radius_m}
                JOIN link_reach r ON r.link_id = l.link_id
                WHERE r.reaches_tidal
                  AND l.to_node <> s.sink_node AND l.from_node <> s.sink_node
                  AND ST_Distance(l.geom, ST_Point(s.sink_e, s.sink_n)) <= {radius_m}
            )
            SELECT * FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY sink_node ORDER BY gap_m, link_id
                ) AS rn FROM cand
            ) WHERE rn = 1
            """
        )
    if frame.empty:
        return pd.DataFrame(
            columns=["sink_node", "drain_link", "drain_publisher", "drain_name",
                     "drain_form", "drain_gap_m", "drain_same_name"]
        )
    return frame.rename(
        columns={"link_id": "drain_link", "publisher_id": "drain_publisher",
                 "name": "drain_name", "form": "drain_form", "gap_m": "drain_gap_m"}
    )[["sink_node", "drain_link", "drain_publisher", "drain_name", "drain_form",
       "drain_gap_m"]]


def _connector_evidence(inflows: pd.DataFrame, reached: set[str], radius_m: float) -> pd.DataFrame:
    """How far is the nearest node the water can already leave from?

    §5's first shape: a real gap, closed by a connector. **A connector is defined by
    its geometry, not by any link id**, so what a candidate carries is the two places,
    not two identifiers.
    """
    if inflows.empty or not reached:
        return pd.DataFrame(columns=["sink_node", "connector_to", "connector_gap_m",
                                     "connector_to_e", "connector_to_n"])
    sinks = inflows[["sink_node", "sink_e", "sink_n"]].drop_duplicates()
    with db.registered("_sinks_in", sinks), db.registered(
        "_reached_in", pd.DataFrame({"node_id": sorted(reached)})
    ):
        frame = db.df(
            f"""
            WITH cand AS (
                SELECT s.sink_node, s.sink_e, s.sink_n,
                       n.node_id AS other, n.easting, n.northing,
                       sqrt(pow(n.easting - s.sink_e, 2)
                          + pow(n.northing - s.sink_n, 2)) AS gap_m
                FROM _sinks_in s
                JOIN node n
                  ON n.easting  BETWEEN s.sink_e - {radius_m} AND s.sink_e + {radius_m}
                 AND n.northing BETWEEN s.sink_n - {radius_m} AND s.sink_n + {radius_m}
                JOIN _reached_in r ON r.node_id = n.node_id
                WHERE n.node_id <> s.sink_node
            )
            SELECT * FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY sink_node ORDER BY gap_m, other
                ) AS rn FROM cand
                WHERE gap_m <= {radius_m}
            ) WHERE rn = 1
            """
        )
    if frame.empty:
        return pd.DataFrame(columns=["sink_node", "connector_to", "connector_gap_m",
                                     "connector_to_e", "connector_to_n"])
    return frame.rename(
        columns={"other": "connector_to", "gap_m": "connector_gap_m",
                 "easting": "connector_to_e", "northing": "connector_to_n"}
    )[["sink_node", "connector_to", "connector_gap_m", "connector_to_e", "connector_to_n"]]


def build(radius_m: float | None = None) -> pd.DataFrame:
    """The candidate list: one row per inflow to an in-scope, non-tidal dead end.

    Every row carries the evidence for each of §5's shapes, side by side, so that the
    adjudication is a reading rather than a search. Where two shapes both have
    evidence, that is a finding and not a problem: it is exactly the case the plan
    warns about, and the row says so.
    """
    p = config.params()
    radius = radius_m if radius_m is not None else 2000.0
    tolerance = float(p("topology.coincidence_tolerance_m"))

    inflows = _defect_inflows()
    if inflows.empty:
        return inflows
    g = graph.load("edge")
    reached = _reached_nodes(g)

    # How much water stands above each dead end — the ranking §6 asks for.
    sink_nodes = inflows["sink_node"].drop_duplicates().tolist()
    idx = g.indices_of(sink_nodes)
    upstream_km = pd.Series(
        g.upstream_length(idx) / 1000.0, index=[str(g.nodes[i]) for i in idx]
    )
    inflows["upstream_km"] = inflows["sink_node"].map(upstream_km)

    inflows["upstream_end_drains"] = _reversal_evidence(inflows, reached)
    inflows = inflows.merge(
        _junction_evidence(sink_nodes, tolerance), left_on="sink_node",
        right_on="node_id", how="left",
    ).drop(columns=["node_id", "easting", "northing", "form_y"], errors="ignore")
    inflows = inflows.rename(columns={"form_x": "form"})
    inflows = inflows.merge(
        _connector_evidence(inflows, reached, radius), on="sink_node", how="left"
    )
    inflows = inflows.merge(
        _nearest_draining_link(inflows, radius), on="sink_node", how="left"
    )
    # The name comparison is on the inflow's own name against the draining link's:
    # "does this river stop and resume?", not "is there any river nearby?".
    inflows["drain_same_name"] = (
        inflows["name"].notna()
        & inflows["drain_name"].notna()
        & (inflows["name"].astype(str).str.strip().str.lower()
           == inflows["drain_name"].astype(str).str.strip().str.lower())
    )

    # The shape each row's evidence points to. Recorded as a reading of the evidence,
    # never as a decision: the column is called `suggests`.
    def suggest(row) -> str:
        shapes = []
        if pd.notna(row.get("junction_gap_m")):
            shapes.append("junction")
        if row.get("upstream_end_drains"):
            shapes.append("reversal")
        if pd.notna(row.get("connector_gap_m")):
            shapes.append("connector")
        if not shapes:
            return "none — nothing within reach; look at the place"
        return "+".join(shapes)

    inflows["suggests"] = inflows.apply(suggest, axis=1)
    inflows["ambiguous"] = inflows["suggests"].str.contains(r"\+", regex=True)

    return inflows.sort_values(
        ["upstream_km", "sink_node", "link_id"], ascending=[False, True, True]
    ).reset_index(drop=True)


def summarise(frame: pd.DataFrame) -> None:
    if frame.empty:
        log.info("  no defects to adjudicate")
        return
    by_shape = (
        frame.groupby("suggests")
        .agg(inflows=("link_id", "size"), km_above=("upstream_km", "sum"))
        .sort_values("inflows", ascending=False)
        .reset_index()
    )
    log.table(
        "what the evidence suggests, per inflow (§5's table, asked of every inflow)",
        ["the evidence points to", "inflows", "km standing above them"],
        [(r.suggests, int(r.inflows), round(float(r.km_above), 0)) for r in by_shape.itertuples()],
    )
    log.detail(
        f"    {int(frame['ambiguous'].sum()):,} inflows have evidence for more than one "
        "shape. That is the case §5 warns about — reversing the wrong inflow of a "
        "three-inflow sink improves the total and leaves the place broken — and each "
        "needs adjudicating at the place rather than by rule."
    )


def inspect(sink_publisher_id: str, radius_m: float = 1500.0) -> dict:
    """Everything needed to adjudicate one defect, at the place.

    AGENTS.md: *looking beats measuring*. This is the closest a terminal gets to
    looking — what arrives, what is nearby, whether it drains, how far, and which way
    the ground falls. It reports; the judgement is the reader's.
    """
    node_id = f"os:node:{sink_publisher_id}"
    place = db.query(
        "SELECT easting, northing, terminus, category FROM node WHERE node_id = ?",
        [node_id],
    )
    if not place:
        raise KeyError(f"no node with publisher id {sink_publisher_id}")
    e, n, terminus, category = place[0]

    inflows = db.df(
        """
        SELECT l.publisher_id, l.name, l.form, e.length_m,
               coalesce(r.reaches_tidal, false) AS reaches_tidal,
               un.easting AS up_e, un.northing AS up_n
        FROM edge e JOIN link l USING (link_id)
        LEFT JOIN link_reach r ON r.link_id = e.link_id
        JOIN node un ON un.node_id = e.from_node
        WHERE e.to_node = ? ORDER BY e.length_m DESC
        """,
        [node_id],
    )
    nearby_links = db.df(
        f"""
        SELECT l.publisher_id, l.name, l.form,
               ST_Distance(l.geom, ST_Point({e}, {n})) AS distance_m,
               coalesce(r.reaches_tidal, false) AS reaches_tidal,
               coalesce(s.in_scope, false) AS in_scope
        FROM link l
        LEFT JOIN link_reach r ON r.link_id = l.link_id
        LEFT JOIN link_scope s ON s.link_id = l.link_id
        WHERE ST_XMax(l.geom) >= {e - radius_m} AND ST_XMin(l.geom) <= {e + radius_m}
          AND ST_YMax(l.geom) >= {n - radius_m} AND ST_YMin(l.geom) <= {n + radius_m}
          AND l.to_node <> ? AND l.from_node <> ?
          AND ST_Distance(l.geom, ST_Point({e}, {n})) <= {radius_m}
        ORDER BY distance_m LIMIT 12
        """,
        [node_id, node_id],
    )
    nearby_nodes = db.df(
        f"""
        SELECT n2.publisher_id, n2.terminus,
               sqrt(pow(n2.easting - {e}, 2) + pow(n2.northing - {n}, 2)) AS distance_m,
               (SELECT count(*) FROM edge x WHERE x.from_node = n2.node_id) AS outflows,
               (SELECT count(*) FROM edge x WHERE x.to_node   = n2.node_id) AS inflows
        FROM node n2
        WHERE n2.node_id <> ?
          AND n2.easting  BETWEEN {e - radius_m} AND {e + radius_m}
          AND n2.northing BETWEEN {n - radius_m} AND {n + radius_m}
        ORDER BY distance_m LIMIT 12
        """,
        [node_id],
    )

    from . import raster

    elevation = None
    try:
        with raster.open_unconditioned() as ds:
            s = raster.sample_window(ds, e, n, window_m=200.0)
            elevation = s.value
    except Exception:
        pass

    log.rule(f"defect at {sink_publisher_id}")
    log.info(f"  place {e:,.0f} E {n:,.0f} N — terminus {terminus}, "
             f"OS category {category}, Terrain 50 {elevation if elevation is None else round(elevation,1)} m")
    log.frame("what arrives here", inflows)
    log.frame("nearest other links", nearby_links)
    log.frame("nearest other nodes", nearby_nodes)
    return {
        "node_id": node_id, "easting": e, "northing": n, "elevation_m": elevation,
        "inflows": inflows, "nearby_links": nearby_links, "nearby_nodes": nearby_nodes,
    }


def propose_connectors(
    max_gap_m: float = 100.0,
    name_rule: str = "same",
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Draft connectors for the strongest evidence class, and say why each is drawn.

    The rule, and it is deliberately narrow:

    * the defect is an in-scope dead end that is not at tidal water;
    * the nearest link that **already reaches tidal water** is within `max_gap_m`;
    * the names satisfy `name_rule`. Under **`same`** the far link must carry the
      **same watercourse name** as the water arriving, so this is one river stopping
      and resuming rather than two rivers near each other. Under **`compatible`** it
      must merely not carry a *different* one — two named watercourses with different
      names are evidence of two watercourses, but only a third of links are named at
      all, and refusing every unnamed pair would refuse most of the network. Use
      `compatible` only at a short reach, where the geometry is doing the arguing;
    * and the line drawn between them **crosses no other watercourse**, because a
      connector that cuts across a third river is not a gap in the survey, it is an
      invention.

    Every draft carries its measurements, so the rule is inspectable and so is each
    application of it. **These are judgements made by rule, and they say so in their
    own evidence** — that is a different thing from a person having looked at each
    place, and a reader is entitled to know which they are holding.

    Returns the drafts, and the rejections with the reason each was rejected.
    """
    import shapely

    frame = build()
    if frame.empty:
        return [], []
    wanted = frame[frame["drain_gap_m"].notna() & (frame["drain_gap_m"] <= max_gap_m)]
    if name_rule == "same":
        wanted = wanted[wanted["drain_same_name"]]
    elif name_rule == "compatible":
        conflicting = (
            wanted["name"].notna()
            & wanted["drain_name"].notna()
            & ~wanted["drain_same_name"]
        )
        wanted = wanted[~conflicting]
    else:
        raise ValueError(f"no name rule {name_rule!r}; use 'same' or 'compatible'")
    wanted = wanted.sort_values("upstream_km", ascending=False).drop_duplicates("sink_node")

    drafts: list[dict] = []
    rejected: list[tuple[str, str]] = []
    for row in wanted.itertuples():
        target = db.query(
            "SELECT ST_AsWKB(geom), publisher_id, name FROM link WHERE link_id = ?",
            [row.drain_link],
        )
        if not target:
            rejected.append((str(row.sink_node), "the draining link vanished from the database"))
            continue
        line = shapely.from_wkb(bytes(target[0][0]))
        here = shapely.Point(float(row.sink_e), float(row.sink_n))
        landing = shapely.ops.nearest_points(line, here)[0] if hasattr(shapely, "ops") else None
        from shapely.ops import nearest_points

        landing = nearest_points(line, here)[0]
        connector = shapely.LineString([(here.x, here.y), (landing.x, landing.y)])
        if shapely.length(connector) <= 0:
            rejected.append((str(row.sink_node), "the two ends coincide — this is a junction, not a connector"))
            continue

        # Does the line cross a third watercourse? A connector that does is not
        # closing a gap in the survey; it is inventing a channel across a river.
        crossed = db.query(
            """
            SELECT l.publisher_id, l.name FROM link l
            WHERE l.link_id <> ?
              AND ST_Intersects(l.geom, ST_GeomFromWKB(?))
              AND ST_XMax(l.geom) >= ? AND ST_XMin(l.geom) <= ?
              AND ST_YMax(l.geom) >= ? AND ST_YMin(l.geom) <= ?
            LIMIT 4
            """,
            [
                row.drain_link,
                shapely.to_wkb(connector),
                min(here.x, landing.x) - 1, max(here.x, landing.x) + 1,
                min(here.y, landing.y) - 1, max(here.y, landing.y) + 1,
            ],
        )
        # The inflow itself touches the connector at the dead end, which is expected.
        crossed = [c for c in crossed if c[0] != row.publisher_id]
        if crossed:
            names = ", ".join(f"{c[1] or 'unnamed'} ({c[0]})" for c in crossed)
            rejected.append(
                (str(row.sink_node),
                 f"the line would cross {len(crossed)} other watercourse(s): {names}")
            )
            continue

        gap = float(row.drain_gap_m)
        name = row.name if isinstance(row.name, str) else "an unnamed watercourse"
        drafts.append(
            {
                "geometry": connector,
                "name": f"{name} at {row.sink_e:,.0f} {row.sink_n:,.0f}",
                "reason": (
                    (
                        f"{name} arrives at a node with no outflow and stops. "
                        f"{gap:,.1f} m away the same watercourse resumes and does "
                        f"reach tidal water. One river drawn in two pieces is a gap "
                        f"in the survey's topology, not a feature of the river, so "
                        f"the two pieces are joined where they come closest."
                    )
                    if row.drain_same_name
                    else (
                        f"{name} arrives at a node with no outflow and stops "
                        f"{gap:,.1f} m short of a watercourse that does reach tidal "
                        f"water, and nothing lies between them. At this distance, on "
                        f"a network generalised from larger-scale data, that is a gap "
                        f"in the survey's topology rather than a gap on the ground. "
                        f"Neither end carries a name that contradicts the other."
                    )
                ),
                "evidence": (
                    f"Measured on OS Open Rivers issue {_issue()}: the dead end is at "
                    f"{row.sink_e:,.1f} E {row.sink_n:,.1f} N with "
                    f"{row.upstream_km:,.1f} km of catchment above it and no outflow; "
                    f"the nearest link that reaches tidal water is {row.drain_publisher} "
                    f"({row.drain_name}), {gap:,.1f} m away, "
                    + (
                        "carrying the same watercourse name"
                        if row.drain_same_name
                        else "carrying no name that contradicts it"
                    )
                    + "; the line between them crosses no other watercourse. "
                    "JUDGED BY RULE, not by a person looking at the place: see "
                    "rewt/candidates.py propose_connectors."
                ),
                "author": "rewt candidates (rule), reviewed by Claude",
                "dated": "2026-08-31",
                "upstream_km": round(float(row.upstream_km), 3),
                "gap_m": round(gap, 3),
                "sink_publisher_id": _node_publisher(str(row.sink_node)),
                "resumes_as": row.drain_publisher,
            }
        )
    return drafts, rejected


def _issue() -> str:
    from . import acquire

    try:
        return acquire.issue_of("os_open_rivers")
    except Exception:
        return "unknown"


def _node_publisher(node_id: str) -> str | None:
    return db.scalar("SELECT publisher_id FROM node WHERE node_id = ?", [node_id])


def write_connectors(drafts: list[dict], path) -> int:
    """Write the drafts as GeoJSON. Connectors are defined by their geometry (§5)."""
    import json

    import shapely

    features = []
    for d in drafts:
        props = {k: v for k, v in d.items() if k != "geometry"}
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(shapely.to_geojson(d["geometry"])),
                "properties": props,
            }
        )
    doc = {
        "type": "FeatureCollection",
        "name": "connectors",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::27700"}},
        "features": features,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return len(features)


def propose_reversals(
    allow_flat_water: bool = False,
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Draft reversals, under the strictest rule in this module.

    §5 is emphatic about the danger, and the rule is built around it:

    > Ask it **of every inflow separately**, not of the first that answers. Three
    > channels arrive at a sink; reversing the wrong one gives the node an outflow
    > pointing deeper into the same stranded region, and the total improves while the
    > place stays broken.

    So the test is not "does this link look backwards" but **"does its other end
    already drain to the sea?"** A link whose upstream end is a node the crawl has
    reached is a link that, turned round, carries the stranded water out. A link whose
    upstream end is *also* stranded is the trap, and it fails this test by
    construction — which is why the crawl has to run before this can be asked at all.

    Three further guards:

    * **The terrain may corroborate and may never decide** (D-007). A reversal is
      refused if Terrain 50 clearly contradicts it, recorded as corroborated if the
      DEM clearly agrees, and recorded as *unsupported by terrain* where the fall is
      inside the error bar — which it will be, often, and saying so is the point. No
      link is flipped on terrain evidence alone and none is reported as
      terrain-evidenced when the evidence was inside the error bar.
    * **Flat water is excluded by default.** *Do not trust a direction fault on flat
      water at face value*: on level ground both directions are defensible from the
      geometry and neither from the terrain. Canals and lakes need the rooting
      argument of §6 or a person, not this rule.
    * **A reversal moves no geometry and changes no published attribute.** It is a row
      in `edge` and nothing else, so it is the cheapest correction to withdraw if it
      turns out to be wrong.
    """
    import numpy as np

    frame = build()
    if frame.empty:
        return [], []
    wanted = frame[frame["upstream_end_drains"]].copy()
    drafts: list[dict] = []
    rejected: list[tuple[str, str]] = []

    flat = set(config.param("forms.flat_water"))
    weak = float(config.param("terrain.screen_bands_m.weak"))
    clear = float(config.param("terrain.screen_bands_m.clear_agree"))

    gradient = db.df(
        "SELECT link_id, fall_m, verdict FROM link_gradient"
    ).set_index("link_id")

    for row in wanted.sort_values("upstream_km", ascending=False).itertuples():
        if row.form in flat and not allow_flat_water:
            rejected.append(
                (row.publisher_id,
                 f"{row.form} is flat water: on level ground both directions are "
                 "defensible from the geometry and neither from the terrain, so this "
                 "rule does not apply to it (§5)")
            )
            continue

        # `fall_m` is upstream minus downstream AS THE SURVEY HAS IT. Reversing is
        # right if the ground falls the OTHER way, so a NEGATIVE fall corroborates.
        fall = gradient["fall_m"].get(row.link_id, np.nan)
        if pd.notna(fall) and fall > clear:
            rejected.append(
                (row.publisher_id,
                 f"Terrain 50 says the ground falls {fall:,.1f} m in the direction the "
                 "survey states, well outside its error bar. The topology says the "
                 "other end drains; the terrain says this one does. Adjudicate at the "
                 "place — do not reverse on the topology alone")
            )
            continue
        if pd.isna(fall):
            terrain = ("Terrain 50 gives no reading here — the sea is masked out of "
                       "it — so the terrain neither supports nor contradicts this")
        elif fall < -clear:
            terrain = (f"Terrain 50 corroborates: the ground falls {-fall:,.1f} m "
                       f"towards the end this reversal drains to, outside the ~4 m "
                       f"error bar")
        elif fall < -weak:
            terrain = (f"Terrain 50 weakly corroborates: {-fall:,.1f} m towards the "
                       f"end this drains to, inside the ~4 m error bar and therefore "
                       f"not evidence on its own")
        else:
            terrain = (f"Terrain 50 says nothing: {fall:,.1f} m over "
                       f"{row.length_m:,.0f} m is inside its own error bar. This "
                       f"reversal rests on topology alone")

        name = row.name if isinstance(row.name, str) else "an unnamed watercourse"
        drafts.append(
            {
                "publisher_id": row.publisher_id,
                "reason": (
                    f"{name} arrives at a node with no outflow, so the water stops. "
                    f"Its OTHER end is at a node the crawl has already reached, which "
                    f"means that end drains to the sea. A link drawn from a place the "
                    f"water can leave towards a place it cannot is drawn backwards; "
                    f"turned round, it carries {row.upstream_km:,.1f} km of stranded "
                    f"catchment out."
                ),
                "evidence": (
                    f"Measured on OS Open Rivers issue {_issue()}: the dead end is at "
                    f"{row.sink_e:,.1f} E {row.sink_n:,.1f} N with {row.upstream_km:,.1f} "
                    f"km above it and no outflow; the link's upstream node at "
                    f"{row.up_e:,.1f} E {row.up_n:,.1f} N is in the set the crawl "
                    f"reaches, so it drains. {terrain}. Asked of THIS inflow and not of "
                    f"the node, so that reversing one of several inflows cannot point "
                    f"the water deeper into the same stranded region (§5). JUDGED BY "
                    f"RULE, not by a person looking at the place: see "
                    f"rewt/candidates.py propose_reversals."
                ),
                "author": "rewt candidates (rule), reviewed by Claude",
                "dated": "2026-08-31",
                "upstream_km": round(float(row.upstream_km), 3),
                "form": row.form,
                "name": name,
            }
        )
    return drafts, rejected
