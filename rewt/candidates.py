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

from . import config, db, graph, ids
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
               l.name_alt,
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
                SELECT s.sink_node, l.link_id, l.publisher_id, l.name, l.name_alt,
                       l.form,
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
                 "name": "drain_name", "name_alt": "drain_name_alt",
                 "form": "drain_form", "gap_m": "drain_gap_m"}
    )[["sink_node", "drain_link", "drain_publisher", "drain_name", "drain_name_alt",
       "drain_form", "drain_gap_m"]]


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
    #
    # BOTH name fields on BOTH sides. OS Open Rivers' specification says that where a
    # watercourse has a name in more than one language, `watercourseName` carries the
    # Welsh or Gaelic and `watercourseNameAlternative` the English — the opposite of
    # the natural reading. Comparing primary names alone would fail to match `Afon
    # Tawe` against `River Tawe`, systematically under-finding Welsh watercourses in a
    # project whose scope is England AND Wales. 5,335 links carry an alternative name
    # and every one differs from its primary; 4,311 of them are in scope. The pairs
    # are not all bilingual either — `Waterbarn Channel` / `River Frome` is a local
    # name beside a river name — so matching on either field is right for more reasons
    # than the specification gives.
    def _names(frame, primary: str, alternative: str):
        a = frame[primary].astype("string").str.strip().str.lower()
        b = frame[alternative].astype("string").str.strip().str.lower()
        return a, b

    mine_a, mine_b = _names(inflows, "name", "name_alt")
    theirs_a, theirs_b = _names(inflows, "drain_name", "drain_name_alt")
    inflows["drain_same_name"] = (
        (mine_a.notna() & theirs_a.notna() & (mine_a == theirs_a))
        | (mine_a.notna() & theirs_b.notna() & (mine_a == theirs_b))
        | (mine_b.notna() & theirs_a.notna() & (mine_b == theirs_a))
        | (mine_b.notna() & theirs_b.notna() & (mine_b == theirs_b))
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
    node_id = ids.publisher("node", sink_publisher_id)
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
    only_forms: tuple[str, ...] | None = None,
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
    elif name_rule == "any":
        # Permitted for canals alone, and D-011 is the reason: **a canal reaches the
        # sea through a structure — a lock, an overflow weir, a feeder — that the
        # survey does not draw**, and that structure discharges into a watercourse
        # with a different name by definition. Requiring the names to match would
        # refuse the whole class on the strength of the very fact that defines it.
        pass
    elif name_rule == "compatible":
        conflicting = (
            wanted["name"].notna()
            & wanted["drain_name"].notna()
            & ~wanted["drain_same_name"]
        )
        wanted = wanted[~conflicting]
    else:
        raise ValueError(f"no name rule {name_rule!r}; use 'same' or 'compatible'")
    if only_forms:
        wanted = wanted[wanted["form"].isin(only_forms)]
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
        corroboration = (
            structure_near(float(row.sink_e), float(row.sink_n))
            if row.form == "canal"
            else None
        )
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
                        f"{name} is a canal, and it arrives at a node with no outflow "
                        f"and stops. {gap:,.1f} m away is "
                        f"{row.drain_name or 'a watercourse'} ({row.drain_form}), "
                        f"which does reach tidal "
                        f"water. D-011: a canal does not reach the sea down its own "
                        f"channel — it reaches it through a lock, an overflow weir or "
                        f"a feeder that the survey does not draw — so it is attached "
                        f"to the receiving watercourse rather than being reversed "
                        f"until the total improves."
                    )
                    if row.form == "canal"
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
                    + (
                        (
                            "D-011 asks for the connection where the lock or weir "
                            "actually is: " + corroboration + ". The POSITION is still "
                            "the nearest approach between the two waters, because a "
                            "located structure sits a median 11.5 m and up to 298 m "
                            "from the survey's own line and is evidence rather than a "
                            "coordinate (D-030). "
                            if corroboration
                            else "THE POSITION IS THE NEAREST APPROACH, NOT A SURVEYED "
                            "STRUCTURE, and no lock, weir or boat lift is recorded "
                            "within 150 m of it. The Canal & River Trust covers its "
                            "own 101 waterways only, so that is not evidence there is "
                            "no structure — but it is not evidence there is one. This "
                            "is the weakest class in this file and should be checked "
                            "at the place. "
                        )
                        if row.form == "canal" else ""
                    )
                    + "JUDGED BY RULE, not by a person looking at the place: see "
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


def structure_near(easting: float, northing: float, radius_m: float = 150.0) -> str | None:
    """A located lock, weir or feeder near a place — D-011's corroboration.

    Returns a phrase naming the nearest one, or None. **Never a coordinate.** A Canal &
    River Trust structure sits a median 11.5 m from the nearest OS watercourse but a
    90th percentile of 108 m, so it says *something was built near here* and not *the
    connection belongs at this point* (D-030).
    """
    if not db.table_exists("structure"):
        return None
    row = db.query(
        f"""
        SELECT kind, description, waterway,
               sqrt(pow(easting - {easting}, 2) + pow(northing - {northing}, 2)) AS d
        FROM structure
        WHERE easting BETWEEN {easting - radius_m} AND {easting + radius_m}
          AND northing BETWEEN {northing - radius_m} AND {northing + radius_m}
          AND kind IN ('locks', 'weirs', 'boat_lifts')
        ORDER BY d, reference LIMIT 1
        """
    )
    if not row:
        return None
    kind, description, waterway, d = row[0]
    return (
        f"a {kind.rstrip('s')} is recorded {d:,.0f} m away — "
        f"{description or 'unnamed'} on the {waterway or 'unnamed waterway'} "
        f"(Canal & River Trust)"
    )


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


def propose_component_outlets(
    max_gap_m: float = 250.0,
    min_component_km: float = 1.0,
    limit: int = 400,
    max_rise_m: float | None = None,
    candidates: int | None = None,
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Connect a stranded COMPONENT to draining water at their closest approach.

    Every other rule in this module proposes at a **dead end**, and that is the wrong
    anchor for the case D-011 actually describes. *A canal reaches the sea through a
    structure — a lock, an overflow weir, a feeder — that the survey does not draw.
    Connect it to the receiving watercourse **where the structure actually is**.* The
    structure is where the two waters come closest, which is generally nowhere near
    the end of the line.

    The Manchester Ship Canal is the case that found this. Its dead end is at
    350,068 E 379,927 N; Runcorn locks, where it meets the tidal Mersey 43 m away,
    are four kilometres from there. No rule anchored on a dead end could ever reach
    it, and with it missing the Irwell reached tidal water over 9% of its 1,957 km.

    **A zero-metre approach is refused, and that is D-016.** Where two lines cross at
    exactly 0 m with both their ends elsewhere, the crossing is very probably an
    aqueduct or a culvert — a structure built to keep the two waters apart — and
    joining them would route the river down the canal. The Ship Canal crosses the
    tidal Gowy at exactly 0.0 m near Stanlow, where the Gowy is culverted beneath it.
    Those are reported for adjudication and never drafted.
    """
    import shapely
    from shapely.ops import nearest_points

    from . import graph

    max_rise_m = config.param("connectors.max_rise_m") if max_rise_m is None else max_rise_m
    candidates = config.param("connectors.candidates") if candidates is None else candidates

    g = graph.load("edge")
    reach = db.df("SELECT link_id, reaches_tidal FROM link_reach")
    reached = set(reach.loc[reach["reaches_tidal"], "link_id"])

    # Components of the UNREACHED SUBGRAPH, not of the whole graph. A stranded region
    # does not have to be a whole component: the Manchester Ship Canal's 1,141 km sits
    # inside a component of 16,787 km of which 16,348 links do reach the sea, because
    # the survey draws the canal in three pieces and one of them shares a node with
    # tidal water. Grouping by whole components made that region invisible to this
    # rule, and its dead end is 14 km from the join it needs, so the dead-end rules
    # could not see it either. The unreached subgraph is the right unit: it is exactly
    # "the water that cannot get out", which is what the crawl reports and what §5 says
    # to work from.
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components as _cc

    unreached = np.array([lid not in reached for lid in g.link_ids])
    if not unreached.any():
        return [], []
    m = coo_matrix(
        (np.ones(int(unreached.sum()), dtype=np.int8),
         (g.u[unreached], g.v[unreached])),
        shape=(g.n_nodes, g.n_nodes),
    )
    _, labels = _cc(m, directed=True, connection="weak")
    edge_component = np.where(unreached, labels[g.u], -1)

    frame = pd.DataFrame(
        {
            "link_id": g.link_ids,
            "component": edge_component.astype(int),
            "length_m": g.length,
            "reached": [lid in reached for lid in g.link_ids],
        }
    )
    frame = frame[frame["component"] >= 0]
    # Only components holding in-scope water. Out of scope means out of scope: a
    # correction there would add geometry to the published network for ground the
    # project does not claim, and nothing is deleted to correct it afterwards.
    scope = db.df("SELECT link_id, in_scope FROM link_scope")
    in_scope_links = set(scope.loc[scope["in_scope"], "link_id"])
    frame["in_scope"] = [lid in in_scope_links for lid in frame["link_id"]]

    per_component = frame.groupby("component").agg(
        km=("length_m", lambda x: x.sum() / 1000.0),
        any_reached=("reached", "any"),
        any_in_scope=("in_scope", "any"),
    )
    # Every group here is unreached by construction, so `any_reached` is always false;
    # it is kept as an assertion rather than a filter.
    assert not per_component["any_reached"].any(), "a reached link entered the subgraph"
    stranded = per_component[
        per_component["any_in_scope"] & (per_component["km"] >= min_component_km)
    ].sort_values("km", ascending=False).head(limit)

    log.info(
        f"  {len(stranded):,} stranded REGIONS of {min_component_km:g} km or more "
        f"(connected runs of unreached water, not whole components), holding "
        f"{stranded['km'].sum():,.0f} km with no way to the sea"
    )

    drafts: list[dict] = []
    rejected: list[tuple[str, str]] = []
    for component, row in stranded.iterrows():
        members = frame.loc[frame["component"] == component, "link_id"].tolist()
        with db.registered("_comp", pd.DataFrame({"link_id": members})), db.registered(
            "_wc0", pd.DataFrame({"link_id": members})
        ):
            near = db.query(
                f"""
                WITH mine AS (SELECT l.link_id, l.geom, l.name, l.form
                              FROM link l JOIN _comp USING (link_id)
                              UNION ALL
                              SELECT rl.link_id, rl.geom, rl.name, rl.form
                              FROM repair_link rl JOIN _comp USING (link_id)),
                     box AS (SELECT min(ST_XMin(geom)) AS x0, max(ST_XMax(geom)) AS x1,
                                    min(ST_YMin(geom)) AS y0, max(ST_YMax(geom)) AS y1
                             FROM mine),
                     theirs AS (
                        SELECT l.link_id, l.geom, l.name, l.form, l.publisher_id
                        FROM link l JOIN link_reach r USING (link_id), box
                        WHERE r.reaches_tidal
                          AND ST_XMax(l.geom) >= box.x0 - {max_gap_m}
                          AND ST_XMin(l.geom) <= box.x1 + {max_gap_m}
                          AND ST_YMax(l.geom) >= box.y0 - {max_gap_m}
                          AND ST_YMin(l.geom) <= box.y1 + {max_gap_m})
                SELECT m.name, m.form, t.publisher_id, t.name, t.form,
                       ST_Distance(m.geom, t.geom) AS gap_m,
                       ST_AsWKB(m.geom), ST_AsWKB(t.geom)
                FROM mine m JOIN theirs t
                  ON ST_Distance(m.geom, t.geom) <= {max_gap_m}
                 AND ST_Distance(m.geom, t.geom) > 0
                ORDER BY gap_m LIMIT {candidates}
                """
            )
            # The zero-metre touches are asked for SEPARATELY rather than filtered out
            # of a limited result. Taking the closest twelve and discarding the zeros
            # worked until a region had more than twelve of them: the Manchester Ship
            # Canal's stranded 32 km touches reached water at exactly 0 m in at least
            # five places — Rivacre Brook, Hoolpool Gutter, the Gowy, an unnamed
            # channel and another Ship Canal link — so the list never reached the
            # 184 m gap at Eastham that is the actual join. A LIMIT is not a filter.
            zero = db.query(
                f"""
                WITH mine AS (SELECT l.link_id, l.geom, l.name, l.form
                              FROM link l JOIN _wc0 USING (link_id)
                              UNION ALL
                              SELECT rl.link_id, rl.geom, rl.name, rl.form
                              FROM repair_link rl JOIN _wc0 USING (link_id)),
                     box AS (SELECT min(ST_XMin(geom)) AS x0, max(ST_XMax(geom)) AS x1,
                                    min(ST_YMin(geom)) AS y0, max(ST_YMax(geom)) AS y1
                             FROM mine)
                SELECT m.name, t.name FROM mine m
                JOIN link t ON ST_Intersects(m.geom, t.geom)
                JOIN link_reach r ON r.link_id = t.link_id
                WHERE r.reaches_tidal LIMIT 1
                """
            )
        # A 0 m crossing is refused (D-016) but it must not MASK the real join behind
        # it. Taking the component's minimum distance and rejecting on it meant that a
        # canal culverted under a river somewhere along its length was never offered
        # the genuine gap at its end: the Manchester Ship Canal crosses the tidal Gowy
        # at 0 m near Stanlow, and that hid a 184.5 m hole at Eastham where OS has
        # drawn a tidal stub and simply not joined it. So a zero is stepped over, and
        # recorded, rather than ending the search.
        if zero:
            rejected.append(
                (
                    f"component {component}",
                    f"{zero[0][0] or 'an unnamed watercourse'} and "
                    f"{zero[0][1] or 'a watercourse'} cross at exactly 0 m with their "
                    f"ends elsewhere — an aqueduct or a culvert far more often than a "
                    f"confluence (D-016), so not joined"
                    + (
                        f"; the search continued and found a {near[0][5]:,.1f} m gap "
                        "instead" if near else " and nothing else is within reach"
                    ),
                )
            )
        if not near:
            continue

        chosen = _downhill_approach(near, max_rise_m, rejected, component, row["km"])
        if chosen is None:
            continue
        my_name, my_form, their_pub, their_name, their_form, gap, a, b, fall = chosen
        connector = shapely.LineString([(a.x, a.y), (b.x, b.y)])
        drafts.append(
            {
                "geometry": connector,
                "name": f"{my_name or 'a stranded watercourse'} to "
                        f"{their_name or 'draining water'} at {a.x:,.0f} {a.y:,.0f}",
                "reason": (
                    f"A component holding {row['km']:,.1f} km has no way to tidal "
                    f"water at all. Its closest approach to water that does drain is "
                    f"{gap:,.1f} m, between {my_name or 'an unnamed watercourse'} "
                    f"({my_form}) and {their_name or 'an unnamed watercourse'} "
                    f"({their_form}). D-011: a canal reaches the sea through a "
                    f"structure the survey does not draw, and the structure is where "
                    f"the two waters come closest — which is not, in general, at the "
                    f"end of either line."
                ),
                "evidence": (
                    f"Measured on OS Open Rivers issue {_issue()}: the component holds "
                    f"{row['km']:,.1f} km and not one of its links reaches tidal "
                    f"water; the closest approach to a link that does is {gap:,.1f} m, "
                    f"at {a.x:,.1f} E {a.y:,.1f} N, to {their_pub}. The approach is "
                    f"greater than zero, so this is a gap rather than a crossing — a "
                    f"0 m crossing with both ends elsewhere is an aqueduct or culvert "
                    f"and is refused (D-016). The unconditioned Terrain 50 surface falls "
                    f"{fall:+,.1f} m from the stranded side to the draining side, so the "
                    f"water this connector invents runs downhill. THE POSITION IS THE "
                    f"CLOSEST APPROACH, "
                    f"NOT A SURVEYED STRUCTURE, and should be checked at the place. "
                    f"JUDGED BY RULE: see rewt/candidates.py propose_component_outlets."
                ),
                "author": "rewt candidates (rule), reviewed by Claude",
                "dated": "2026-08-31",
                "upstream_km": round(float(row["km"]), 3),
                "gap_m": round(float(gap), 3),
                "sink_publisher_id": None,
                "resumes_as": their_pub,
            }
        )
    return drafts, rejected


def propose_water_crossings(
    max_gap_m: float = 2000.0,
    min_component_km: float = 0.5,
    limit: int = 400,
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Cross a water body that the survey routes through with nothing (PLAN.md §5).

    > Where a watercourse meets a lake, reservoir or broad, OS Open Rivers either draws
    > a **schematic straight line** across it — some 2,300 km of the network is routed
    > this way — or **draws nothing, and the network is severed**.

    This is the second case. A stranded component and draining water, with a mapped
    water body lying between them, is a network severed by a lake — and the fact that
    OS routes *through* other water bodies with a straight line is what says a straight
    line is admissible here: it is the survey's own convention, not an invention of
    this project's.

    **The line is flagged `schematic` because it is a routing device and not a
    channel** (D-008). Stage 1 makes no historical claim so either is admissible, but a
    later stage must not mistake this for a surveyed course — and where the water body
    is a modern impoundment, the line runs where a valley used to be.

    A longer reach is allowed than for a connector on dry land, and the water body is
    what licenses it: the gap is not open ground the water would have to cross, it is
    water. The line must lie **inside** the polygon for its whole length, so a 2 km
    crossing of a broad is admissible and a 2 km line over fields is not.
    """
    import shapely
    from shapely.ops import nearest_points

    from . import graph

    if not db.table_exists("water_body"):
        return [], [("water_body", "the water_bodies stage has not run")]

    g = graph.load("edge")
    labels = g.weak_components()
    reach = db.df("SELECT link_id, reaches_tidal FROM link_reach")
    reached = set(reach.loc[reach["reaches_tidal"], "link_id"])
    scope = db.df("SELECT link_id, in_scope FROM link_scope")
    in_scope_links = set(scope.loc[scope["in_scope"], "link_id"])

    frame = pd.DataFrame(
        {
            "link_id": g.link_ids,
            "component": labels[g.u].astype(int),
            "length_m": g.length,
            "reached": [lid in reached for lid in g.link_ids],
            "in_scope": [lid in in_scope_links for lid in g.link_ids],
        }
    )
    per = frame.groupby("component").agg(
        km=("length_m", lambda x: x.sum() / 1000.0),
        any_reached=("reached", "any"),
        any_scope=("in_scope", "any"),
    )
    stranded = per[
        (~per["any_reached"]) & per["any_scope"] & (per["km"] >= min_component_km)
    ].sort_values("km", ascending=False).head(limit)

    drafts: list[dict] = []
    rejected: list[tuple[str, str]] = []
    for component, row in stranded.iterrows():
        members = frame.loc[frame["component"] == component, "link_id"].tolist()
        with db.registered("_wc", pd.DataFrame({"link_id": members})):
            near = db.query(
                f"""
                WITH mine AS (SELECT l.link_id, l.geom, l.name FROM link l JOIN _wc USING (link_id)
                              UNION ALL
                              SELECT rl.link_id, rl.geom, rl.name FROM repair_link rl JOIN _wc USING (link_id)),
                     box AS (SELECT min(ST_XMin(geom)) x0, max(ST_XMax(geom)) x1,
                                    min(ST_YMin(geom)) y0, max(ST_YMax(geom)) y1 FROM mine)
                SELECT m.name, t.name, t.publisher_id,
                       ST_Distance(m.geom, t.geom) AS gap_m,
                       ST_AsWKB(m.geom), ST_AsWKB(t.geom)
                FROM mine m, link t JOIN link_reach r USING (link_id), box
                WHERE r.reaches_tidal
                  AND ST_XMax(t.geom) >= box.x0 - {max_gap_m}
                  AND ST_XMin(t.geom) <= box.x1 + {max_gap_m}
                  AND ST_YMax(t.geom) >= box.y0 - {max_gap_m}
                  AND ST_YMin(t.geom) <= box.y1 + {max_gap_m}
                  AND ST_Distance(m.geom, t.geom) BETWEEN 0.001 AND {max_gap_m}
                ORDER BY gap_m LIMIT 1
                """
            )
        if not near:
            continue
        my_name, their_name, their_pub, gap, mw, tw = near[0]
        a, b = nearest_points(
            shapely.from_wkb(bytes(mw)), shapely.from_wkb(bytes(tw))
        )
        line = shapely.LineString([(a.x, a.y), (b.x, b.y)])

        # The whole line must lie in ONE water body. A line that merely clips a corner
        # is crossing land, and this rule has nothing to say about land.
        # Bounding boxes before geometry, as everywhere else in this project: a bare
        # ST_Contains over 34,848 polygons is a full scan per candidate.
        x0, y0, x1, y1 = shapely.bounds(line)
        body = db.query(
            f"""
            SELECT publisher_id, area_m2
            FROM water_body
            WHERE ST_XMax(geom) >= {x0} AND ST_XMin(geom) <= {x1}
              AND ST_YMax(geom) >= {y0} AND ST_YMin(geom) <= {y1}
              AND ST_Contains(geom, ST_GeomFromWKB(?))
            ORDER BY area_m2 DESC LIMIT 1
            """,
            [shapely.to_wkb(line)],
        )
        if not body:
            rejected.append(
                (
                    f"component {component}",
                    f"the {gap:,.0f} m approach does not lie inside a mapped water "
                    "body, so this is a gap over land and not a severed crossing",
                )
            )
            continue

        drafts.append(
            {
                "geometry": line,
                "name": f"{my_name or 'a stranded watercourse'} across water at "
                        f"{a.x:,.0f} {a.y:,.0f}",
                "reason": (
                    f"A component holding {row['km']:,.1f} km has no way to tidal "
                    f"water, and the {gap:,.0f} m between it and water that does drain "
                    f"lies wholly inside a mapped water body of "
                    f"{body[0][1] / 10000:,.1f} ha. The survey has routed through this "
                    f"one with nothing at all. §5: where OS draws no route across a "
                    f"lake, broad or reservoir the network is severed there, and a "
                    f"straight line across standing water is the survey's OWN "
                    f"convention — it uses one for some 2,300 km elsewhere."
                ),
                "evidence": (
                    f"Measured on OS Open Rivers issue {_issue()} against OS OpenMap - "
                    f"Local: the component holds {row['km']:,.1f} km and not one of its "
                    f"links reaches tidal water; the nearest link that does is "
                    f"{their_pub} ({their_name}) at {gap:,.0f} m; and the line between "
                    f"them is CONTAINED by surface water polygon {body[0][0]}. "
                    f"THIS LINE IS A ROUTING DEVICE AND NOT A CHANNEL and is flagged "
                    f"`schematic` (D-008): where the water body is a modern "
                    f"impoundment it runs where a valley used to be, and a later stage "
                    f"must not read it as a surveyed course. JUDGED BY RULE: see "
                    f"rewt/candidates.py propose_water_crossings."
                ),
                "author": "rewt candidates (rule), reviewed by Claude",
                "dated": "2026-09-01",
                "upstream_km": round(float(row["km"]), 3),
                "gap_m": round(float(gap), 3),
                "sink_publisher_id": None,
                "resumes_as": their_pub,
                "schematic": True,
            }
        )
    return drafts, rejected


def _downhill_approach(near, max_rise_m: float, rejected: list, component, km: float):
    """The nearest approach whose water would actually run downhill.

    **Distance alone was the whole rule, and it joined channels across banks.** The
    proposer took the single closest approach between a stranded region and water that
    drains, which is right in the large — but two channels can be close in plan and
    separated by an embankment, a road or a watershed, and the rule could not tell.
    Measured against v0.1.0-alpha: 104 of 1,204 connectors rose more than a metre end to
    end, 23 rose more than five, and the worst climbed 27.4 m in 462 m.

    So several approaches are considered and the nearest one that does not climb is
    taken. A longer connector is accepted ONLY to avoid running uphill, never to find a
    tidier target — the ordering is still by distance, and terrain is a veto rather than
    a preference.

    **The surface is the unconditioned one (D-007).** The conditioned DEM has this very
    network burned into it, so asking it whether a connector runs downhill would be
    asking whether the answer we assumed is the answer we get.

    **A region with no downhill approach is refused and named**, not drafted with the
    least-bad candidate. The rule cannot tell an embankment from a survey gap, and a
    connector nobody can justify is worse than a dead end somebody can see: the dead end
    is already reported, with the length stranded behind it.
    """
    import shapely
    from shapely.ops import nearest_points

    from . import raster

    raster.assert_unconditioned(raster.UNCONDITIONED)
    tried: list[str] = []
    with raster.open_unconditioned() as ds:
        for my_name, my_form, their_pub, their_name, their_form, gap, mw, tw in near:
            a, b = nearest_points(shapely.from_wkb(bytes(mw)), shapely.from_wkb(bytes(tw)))
            za, zb = raster.sample_points(
                ds, np.array([a.x, b.x]), np.array([a.y, b.y]))
            if not (np.isfinite(za) and np.isfinite(zb)):
                # No elevation at one end — offshore, or outside the clipped grid. The
                # terrain cannot answer, so it does not get a vote, and the approach is
                # taken on distance as before.
                return my_name, my_form, their_pub, their_name, their_form, gap, a, b, 0.0
            fall = float(za - zb)
            if fall >= -max_rise_m:
                return (my_name, my_form, their_pub, their_name, their_form, gap,
                        a, b, fall)
            tried.append(f"{gap:,.0f} m rising {-fall:,.1f} m")

    rejected.append((
        f"component {component}",
        f"a region holding {km:,.1f} km has no approach to draining water that runs "
        f"downhill: the {len(tried)} nearest all climb more than {max_rise_m:g} m on the "
        f"unconditioned Terrain 50 surface ({'; '.join(tried[:4])}"
        + (", …" if len(tried) > 4 else "")
        + "). Two channels close in plan and separated by a bank are not a survey gap, "
        "and joining them would route water uphill. Left as a dead end, which is "
        "reported with the length stranded behind it."
    ))
    return None
