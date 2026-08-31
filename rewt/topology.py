"""Topology questions asked of the geometry rather than of the graph.

Two of PLAN.md §6's findings live here, and one of §5's three shapes:

* **Touching but not joined** — links whose endpoints coincide within a metre while
  sharing no node.
* **The end sits *on* another channel with no node** — no gap at all, a junction.

Both are spatial questions over ~193,000 links, and AGENTS.md is explicit about how
not to ask them: **spatial self-joins over ~120,000 links are prohibitively slow —
join on rounded endpoint coordinates instead, and a ten-minute query becomes seconds.**
So the node-to-node test is a grid join, and the node-to-line test is confined to the
candidate nodes that the graph has already identified as interesting.
"""

from __future__ import annotations

import pandas as pd

from . import config, db

_CELL_M = 1.0     # the grid the rounded join uses; must be >= the tolerance


def unjoined_pairs(tolerance_m: float | None = None) -> pd.DataFrame:
    """Distinct nodes standing within a metre of one another.

    Every link endpoint is a node, so two nodes this close is exactly "two links touch
    and share no node". The join is on a floor-divided grid cell and its eight
    neighbours, which is O(n) where the spatial self-join is not.
    """
    tol = tolerance_m if tolerance_m is not None else config.param(
        "topology.coincidence_tolerance_m"
    )
    cell = max(_CELL_M, tol)
    con = db.get()
    con.execute("DROP TABLE IF EXISTS _node_cell")
    con.execute(
        f"""
        CREATE TEMP TABLE _node_cell AS
        SELECT node_id, easting, northing,
               CAST(floor(easting / {cell}) AS BIGINT) AS cx,
               CAST(floor(northing / {cell}) AS BIGINT) AS cy
        FROM node
        """
    )
    # Expand each node into the nine cells it could have a neighbour in, so the join
    # is a plain equijoin on one integer key. Expressing the neighbourhood as a join
    # condition instead makes DuckDB fall back to a nested loop over 197,000 rows,
    # which is the ten-minute query AGENTS.md warns about wearing a different hat.
    offsets = " UNION ALL ".join(
        f"SELECT node_id, (cx + {dx}) * 1000000000 + (cy + {dy}) AS key "
        f"FROM _node_cell"
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    )
    con.execute("DROP TABLE IF EXISTS _node_near")
    con.execute(f"CREATE TEMP TABLE _node_near AS {offsets}")
    con.execute(
        "CREATE TEMP TABLE _node_key AS "
        "SELECT node_id, cx * 1000000000 + cy AS key FROM _node_cell"
    )
    frame = con.execute(
        f"""
        SELECT a.node_id AS node_a, b.node_id AS node_b,
               na.easting, na.northing,
               sqrt(pow(na.easting - nb.easting, 2)
                  + pow(na.northing - nb.northing, 2)) AS gap_m
        FROM _node_near a
        JOIN _node_key b ON b.key = a.key
        JOIN _node_cell na ON na.node_id = a.node_id
        JOIN _node_cell nb ON nb.node_id = b.node_id
        WHERE a.node_id < b.node_id
          AND pow(na.easting - nb.easting, 2)
            + pow(na.northing - nb.northing, 2) <= {tol * tol}
        ORDER BY gap_m, node_a, node_b
        """
    ).df()
    con.execute("DROP TABLE IF EXISTS _node_near")
    con.execute("DROP TABLE IF EXISTS _node_key")
    con.execute("DROP TABLE IF EXISTS _node_cell")
    return frame.drop_duplicates(subset=["node_a", "node_b"]).reset_index(drop=True)


def nodes_on_other_links(node_ids: list[str], tolerance_m: float | None = None) -> pd.DataFrame:
    """Candidate nodes sitting *on* a channel they are not an endpoint of.

    This is §5's third shape — no gap at all — and the remedy is a junction, not a
    connector: **a junction adds nothing at all**, no geometry, no feature, no output
    row; the target is cut and the node merged. A connector cannot express that,
    because its two ends would coincide, and a zero-length connector once reached a
    published dataset as a row with no country.

    Confined to the nodes handed in, because that population is the defect list and is
    thousands rather than two hundred thousand.
    """
    tol = tolerance_m if tolerance_m is not None else config.param(
        "topology.coincidence_tolerance_m"
    )
    if not node_ids:
        return pd.DataFrame(
            columns=["node_id", "link_id", "publisher_id", "form", "distance_m",
                     "easting", "northing", "measure"]
        )
    con = db.get()
    candidates = pd.DataFrame({"node_id": node_ids})
    with db.registered("_cand", candidates):
        con.execute("DROP TABLE IF EXISTS _cand_node")
        con.execute(
            """
            CREATE TEMP TABLE _cand_node AS
            SELECT n.node_id, n.easting, n.northing, n.geom
            FROM node n JOIN _cand c ON c.node_id = n.node_id
            """
        )
    # Bound the search by a bounding-box test before measuring distance: DuckDB will
    # not build an index for a one-off, and the box test is what makes it cheap.
    frame = con.execute(
        f"""
        SELECT c.node_id,
               l.link_id,
               l.publisher_id,
               l.form,
               ST_Distance(c.geom, l.geom) AS distance_m,
               c.easting, c.northing
        FROM _cand_node c
        JOIN link l
          ON l.from_node <> c.node_id AND l.to_node <> c.node_id
         AND ST_XMax(l.geom) >= c.easting - {tol}
         AND ST_XMin(l.geom) <= c.easting + {tol}
         AND ST_YMax(l.geom) >= c.northing - {tol}
         AND ST_YMin(l.geom) <= c.northing + {tol}
        WHERE ST_Distance(c.geom, l.geom) <= {tol}
        ORDER BY c.node_id, distance_m, l.link_id
        """
    ).df()
    con.execute("DROP TABLE IF EXISTS _cand_node")
    return frame


def nearest_links(
    node_ids: list[str], max_distance_m: float, exclude_forms: list[str] | None = None
) -> pd.DataFrame:
    """For each node, the nearest link within a radius, optionally excluding forms.

    This answers §5's canal question — *how far is the nearest non-canal watercourse?*
    — and the same question for any stranded end. The radius keeps the box join small.
    """
    if not node_ids:
        return pd.DataFrame(
            columns=["node_id", "link_id", "publisher_id", "form", "name", "distance_m"]
        )
    con = db.get()
    exclude = exclude_forms or []
    exclusion = (
        "AND l.form NOT IN (" + ", ".join(f"'{f}'" for f in exclude) + ")" if exclude else ""
    )
    with db.registered("_cand", pd.DataFrame({"node_id": node_ids})):
        frame = con.execute(
            f"""
            WITH c AS (
                SELECT n.node_id, n.easting, n.northing, n.geom
                FROM node n JOIN _cand USING (node_id)
            ),
            pairs AS (
                SELECT c.node_id, l.link_id, l.publisher_id, l.form, l.name,
                       ST_Distance(c.geom, l.geom) AS distance_m,
                       c.easting, c.northing
                FROM c JOIN link l
                  ON  ST_XMax(l.geom) >= c.easting  - {max_distance_m}
                  AND ST_XMin(l.geom) <= c.easting  + {max_distance_m}
                  AND ST_YMax(l.geom) >= c.northing - {max_distance_m}
                  AND ST_YMin(l.geom) <= c.northing + {max_distance_m}
                  {exclusion}
                WHERE ST_Distance(c.geom, l.geom) <= {max_distance_m}
            )
            SELECT * FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY node_id ORDER BY distance_m, link_id
                ) AS rn
                FROM pairs
            ) WHERE rn = 1
            ORDER BY distance_m, node_id
            """
        ).df()
    return frame.drop(columns=["rn"], errors="ignore")


def nearest_link_to_links(
    link_ids: list[str], max_distance_m: float, exclude_forms: list[str] | None = None
) -> pd.DataFrame:
    """For each link, the nearest *other* link within a radius, by geometry.

    Distinct from `nearest_links`, which measures from a node. The difference matters:
    a canal that touches a river at an endpoint is a **junction** — a node is merged
    and no geometry is invented — while a canal whose line crosses a river with both
    endpoints far away is very likely an aqueduct, and joining them would route water
    through a structure built to keep it apart. Measuring only one of the two and
    calling the answer "touching" conflates them.
    """
    if not link_ids:
        return pd.DataFrame(columns=["link_id", "other_link_id", "form", "distance_m"])
    con = db.get()
    exclude = exclude_forms or []
    exclusion = (
        "AND o.form NOT IN (" + ", ".join(f"'{f}'" for f in exclude) + ")" if exclude else ""
    )
    with db.registered("_cand_link", pd.DataFrame({"link_id": link_ids})):
        frame = con.execute(
            f"""
            WITH c AS (
                SELECT l.link_id, l.geom,
                       ST_XMin(l.geom) AS xmin, ST_XMax(l.geom) AS xmax,
                       ST_YMin(l.geom) AS ymin, ST_YMax(l.geom) AS ymax
                FROM link l JOIN _cand_link USING (link_id)
            ),
            pairs AS (
                SELECT c.link_id, o.link_id AS other_link_id, o.form,
                       ST_Distance(c.geom, o.geom) AS distance_m
                FROM c JOIN link o
                  ON  o.link_id <> c.link_id
                  AND ST_XMax(o.geom) >= c.xmin - {max_distance_m}
                  AND ST_XMin(o.geom) <= c.xmax + {max_distance_m}
                  AND ST_YMax(o.geom) >= c.ymin - {max_distance_m}
                  AND ST_YMin(o.geom) <= c.ymax + {max_distance_m}
                  {exclusion}
                WHERE ST_Distance(c.geom, o.geom) <= {max_distance_m}
            )
            SELECT * FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY link_id ORDER BY distance_m, other_link_id
                ) AS rn FROM pairs
            ) WHERE rn = 1
            ORDER BY distance_m, link_id
            """
        ).df()
    return frame.drop(columns=["rn"], errors="ignore")
