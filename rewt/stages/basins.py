"""Stage: delineate basins, and decide scope on them (PLAN.md §4.1).

Delineation and the scope decision are one stage because §4.1 makes them one
operation: **basins must be delineated before scope is decided**, and the reason the
DEM is acquired at all is that without a topographic delineation there is no way to
tell a shared estuary from a shared catchment.

**This runs AFTER repair**, which is what §4.1 asks for: *basins are recomputed after
repair, not before. Repair changes connectivity, so an early delineation is
provisional.* The plan expects two passes, a provisional one and a final one. There is
one here, and the reason is measured rather than assumed: the raster delineation
depends on the network only through the burn, and the repaired geometry adds **644
cells to a 2,673,201-cell burn footprint — 0.024%, 1.61 km² of 6,683 km²** — every one
of them lying between two channels that were already burned. A connector closes a gap;
it does not carve a path across a watershed. So a second conditioning pass would return
the same basins for ten minutes of work, and the parts that genuinely do change with
repair — which node is a basin's outlet, and which links are in scope — are graph
questions, computed here from the repaired graph. See D-028.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import rasterio
import shapely

from .. import basins as basin_logic
from .. import config, db, graph, ids, paths, raster, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Finding, Report, log

BASIN = artefact("basin")
NODE_BASIN = artefact("node_basin")
LINK_SCOPE = artefact("link_scope")


def _outlets(node_basin: pd.DataFrame) -> pd.DataFrame:
    """One outlet node per basin: the tidal terminus with the most water above it.

    A basin has one outlet, which is what makes "what share of this basin can reach
    its own sea?" a complete question with a number for an answer (§6). Where a basin
    holds no tidal terminus at all, that is recorded rather than invented — an
    unanchored basin is a finding, and its identifier says so (D-013).
    """
    # The REPAIRED graph, not the survey's: a basin's outlet is a property of the
    # network as it now stands, and a reversal or a connector can move it.
    g = graph.load("edge")
    sinks = g.sinks()
    upstream = g.upstream_length(sinks)
    sink_frame = pd.DataFrame(
        {
            "node_id": [str(g.nodes[i]) for i in sinks],
            "upstream_m": upstream,
        }
    )
    candidates = node_basin.merge(sink_frame, on="node_id", how="inner")
    candidates = candidates[candidates["terminus"] == "tidal"]
    candidates = candidates[candidates["raster_id"] > basin_logic.NO_BASIN]
    if candidates.empty:
        return pd.DataFrame(columns=["raster_id", "outlet_node", "outlet_upstream_km"])
    best = (
        candidates.sort_values(
            ["raster_id", "upstream_m", "node_id"], ascending=[True, False, True]
        )
        .groupby("raster_id", as_index=False)
        .first()
    )
    return best.rename(columns={"node_id": "outlet_node"}).assign(
        outlet_upstream_km=lambda d: d["upstream_m"] / 1000.0
    )[["raster_id", "outlet_node", "outlet_upstream_km"]]


@PIPELINE.stage(
    "basins",
    "delineate basins from the terrain, and decide scope on them",
    reads=["terrain50_basins", "raw_os_boundary_line", "link", "node", "edge",
           "repair_node", "repair_link"],
    writes=["basin", "node_basin", "link_scope"],
    params=["basins", "scope", "crs", "terrain"],
    sources=["os_terrain_50", "os_boundary_line"],
)
def run() -> dict:
    p = config.params()
    con = db.get()
    report = Report("basins")

    with rasterio.open(raster.BASINS) as ds:
        band = ds.read(1)
        nodata = ds.nodata
        if nodata is not None:
            band = np.where(np.isclose(band, nodata), basin_logic.NO_BASIN, band)
        band = band.astype(np.int64)
        transform = ds.transform
        cell_m = abs(transform.a)
        measured = basin_logic.measure(band, transform, cell_m)
        node_basin = basin_logic.sample_basin_at_nodes(band, ds)

    log.info(f"  {len(measured):,} basins delineated to the coast")

    # ----------------------------------------------------------- the scope rule
    measured = basin_logic.decide_scope(measured)
    _check_northern_edge(band, measured)
    outlets = _outlets(node_basin)
    measured = measured.merge(outlets, on="raster_id", how="left")

    in_scope = measured[measured["in_scope"]]
    log.table(
        "scope, decided on basins and not on the border (§4.1, D-003)",
        ["measure", "value"],
        [
            ("basins delineated", len(measured)),
            ("in scope (some part in England or Wales)", len(in_scope)),
            ("in-scope area, km2", round(float(in_scope["area_km2"].sum()), 0)),
            (
                "of which in Scotland, km2 (in scope: the basin is)",
                round(float(in_scope["scotland_area_km2"].sum()), 0),
            ),
            (
                "of which tidal or offshore, in no country polygon",
                round(
                    float(
                        (
                            in_scope["area_km2"]
                            - in_scope["england_wales_area_km2"]
                            - in_scope["scotland_area_km2"]
                        ).clip(lower=0).sum()
                    ),
                    0,
                ),
            ),
            ("basins with no outlet node in the network", int(in_scope["outlet_node"].isna().sum())),
        ],
    )

    # The cross-border cases §9 asks to be named individually.
    crossing = basin_logic.cross_border(measured).head(25)
    named = []
    for row in crossing.itertuples():
        label = _label_for(row.raster_id, node_basin)
        named.append(
            (
                label or f"basin {int(row.raster_id)}",
                round(float(row.area_km2), 1),
                round(float(row.england_wales_area_km2), 1),
                round(float(row.scotland_area_km2), 1),
                f"{row.scotland_area_km2 / row.area_km2:.0%}",
                round(float(row.tidal_or_offshore_km2), 1),
            )
        )
    log.table(
        "in-scope basins with ground in SCOTLAND — the cross-border cases, named (§9)",
        ["basin", "area km2", "in E&W", "in Scotland", "share Scottish", "tidal/offshore"],
        named,
    )
    log.detail(
        "    the last column is ground in no country polygon at all — Boundary-Line "
        "stops at Mean High Water, so a coastal basin's estuary and foreshore lie "
        "outside every country and are not a border crossing"
    )

    # ------------------------------------------------------------ persist basins
    keep = measured.loc[
        (measured["in_scope"])
        | (measured["area_km2"] >= float(p("basins.min_basin_area_km2"))),
        "raster_id",
    ].to_numpy()
    log.info(f"  polygonising {len(keep):,} basins")
    polys = basin_logic.polygonise(band, transform, keep)
    measured = measured.merge(polys, on="raster_id", how="left")

    labels = {
        int(r): _label_for(int(r), node_basin) for r in measured["raster_id"].tolist()
    }
    measured["label"] = measured["raster_id"].map(labels)
    measured["basin_id"] = [
        basin_logic.basin_identity(int(r), o if isinstance(o, str) else None)
        for r, o in zip(measured["raster_id"], measured["outlet_node"])
    ]
    # Not provisional: this IS the post-repair delineation (§4.1, D-028).
    measured["provisional"] = False

    out = measured.dropna(subset=["geometry"]).copy()
    out["wkb"] = [shapely.to_wkb(g) for g in out["geometry"]]
    schema.create("basin")
    with db.registered(
        "_basin_in",
        out[
            [
                "basin_id", "label", "outlet_node", "area_km2", "in_scope",
                "scope_reason", "england_wales_area_km2", "provisional", "wkb",
                "raster_id",
            ]
        ],
    ):
        con.execute(
            """
            INSERT INTO basin
            SELECT basin_id, label, outlet_node, area_km2, in_scope, scope_reason,
                   england_wales_area_km2, provisional, ST_GeomFromWKB(wkb)
            FROM _basin_in ORDER BY basin_id
            """
        )

    # node -> basin, kept as its own table so the exporter and the audit can join it
    # without either of them recomputing a delineation.
    node_basin = node_basin.merge(
        measured[["raster_id", "basin_id", "in_scope"]], on="raster_id", how="left"
    )
    with db.registered("_nb_in", node_basin[["node_id", "raster_id", "basin_id", "in_scope"]]):
        con.execute("DROP TABLE IF EXISTS node_basin")
        con.execute(
            "CREATE TABLE node_basin AS SELECT node_id, raster_id, basin_id, "
            "coalesce(in_scope, false) AS basin_in_scope FROM _nb_in ORDER BY node_id"
        )

    # ------------------------------------------------------------- link scope
    # Rule one: the downstream end falls in an in-scope basin.
    # Rule two: the downstream end falls in England or Wales. Needed because tidal
    # water is masked out of a DEM and sits on no basin at all; without it the scope
    # silently drops the tidal Thames, the Humber, and the navigable head of every
    # major estuary in the country.
    ew = basin_logic.england_and_wales()
    nodes = db.df("SELECT node_id, easting, northing FROM node ORDER BY node_id")
    points = shapely.points(nodes["easting"].to_numpy(), nodes["northing"].to_numpy())
    tree = shapely.STRtree(points)
    inside_idx = tree.query(ew, predicate="intersects")
    nodes["in_country"] = False
    nodes.loc[nodes.index[inside_idx], "in_country"] = True

    schema.create("link_scope")
    with db.registered("_ew_in", nodes[["node_id", "in_country"]]):
        con.execute(
            """
            INSERT INTO link_scope
            -- The link's DOWNSTREAM node decides its basin and its scope. That has
            -- to be the *oriented* downstream node, not the digitised one: a reversed
            -- link's water leaves by the end it was drawn entering, and 335 links are
            -- reversed. `basins` runs after `repair` (D-028) precisely so that `edge`
            -- exists here and the oriented sense is available.
            --
            -- It used to key on the digitised `to_node`, which put 64 links (94.3 km,
            -- 56 of them reversed) in a different basin from the one the audit counts
            -- them in — the audit joins on `edge.to_node`. Small, systematic, and
            -- exactly the kind of disagreement between the audit and the published
            -- file that makes a reader distrust both. Found by rewt-fc comparing the
            -- two from outside.
            --
            -- `coalesce` because a retired link has no edge and still needs a basin.
            WITH every_link AS (
                SELECT l.link_id, coalesce(e.to_node, l.to_node) AS to_node
                FROM (
                    SELECT link_id, to_node FROM link
                    UNION ALL
                    SELECT link_id, to_node FROM repair_link
                ) l
                LEFT JOIN edge e ON e.link_id = l.link_id
            )
            SELECT l.link_id,
                   nb.basin_id,
                   coalesce(nb.basin_in_scope, false) OR coalesce(ew.in_country, false)
                       AS in_scope,
                   CASE
                     WHEN coalesce(nb.basin_in_scope, false) THEN 'basin'
                     WHEN coalesce(ew.in_country, false)     THEN 'country'
                     ELSE 'neither'
                   END AS scope_rule
            FROM every_link l
            LEFT JOIN node_basin nb ON nb.node_id = l.to_node
            LEFT JOIN _ew_in ew      ON ew.node_id = l.to_node
            ORDER BY l.link_id
            """
        )

    stats = con.execute(
        """
        SELECT s.in_scope, s.scope_rule, count(*) AS links,
               sum(l.length_m) / 1000.0 AS km
        FROM link_scope s JOIN link l USING (link_id)
        GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC
        """
    ).df()
    log.frame("links by scope rule", stats)

    kept = con.execute(
        "SELECT count(*), sum(l.length_m)/1000.0 FROM link_scope s JOIN link l "
        "USING (link_id) WHERE s.in_scope"
    ).fetchone()
    dropped = con.execute(
        "SELECT count(*), sum(l.length_m)/1000.0 FROM link_scope s JOIN link l "
        "USING (link_id) WHERE NOT s.in_scope"
    ).fetchone()
    cal = p("basins.calibration")
    log.table(
        "scope against PLAN.md §4.1's calibration (the predecessor's own delineation)",
        ["measure", "this build", "PLAN.md §4.1"],
        [
            ("links in scope", kept[0], cal["links_in_scope"]),
            ("km in scope", round(kept[1] or 0, 0), cal["length_in_scope_km"]),
            ("links out of scope", dropped[0], cal["links_out_of_scope"]),
            ("km out of scope", round(dropped[1] or 0, 0), cal["length_out_of_scope_km"]),
        ],
    )
    log.detail(
        "    §4.1 says the in-scope figures depend on your own basin delineation, so "
        "a few per cent of difference is expected; more than that is a reason to "
        "question the delineation before questioning the network."
    )

    for row in crossing.head(15).itertuples():
        place = node_basin[node_basin["raster_id"] == row.raster_id].head(1)
        report.finding(
            Finding(
                kind="cross_border_basin",
                subject=labels.get(int(row.raster_id)) or f"basin {int(row.raster_id)}",
                detail=(
                    f"{row.scotland_area_km2:,.0f} km2 of {row.area_km2:,.0f} km2 lies "
                    "in Scotland, and is in scope because the basin is"
                ),
                easting=float(place["easting"].iloc[0]) if len(place) else None,
                northing=float(place["northing"].iloc[0]) if len(place) else None,
                metrics={
                    "area_km2": round(float(row.area_km2), 1),
                    "scotland_km2": round(float(row.scotland_area_km2), 1),
                },
            )
        )
    report.add("basins", {
        "delineated": len(measured),
        "in_scope": int(measured["in_scope"].sum()),
        "unanchored": int(measured.loc[measured["in_scope"], "outlet_node"].isna().sum()),
    })
    report.add("links", {
        "in_scope": kept[0], "in_scope_km": round(kept[1] or 0, 1),
        "out_of_scope": dropped[0], "out_of_scope_km": round(dropped[1] or 0, 1),
    })
    report.write_json(paths.PUBLISHED / "audit" / "basins.json")

    return {
        "basins": len(measured),
        "in_scope": int(measured["in_scope"].sum()),
        "links_in_scope": kept[0],
        "km_in_scope": round(kept[1] or 0, 1),
    }


def _label_for(raster_id: int, node_basin: pd.DataFrame) -> str | None:
    """A name for reading, taken from the largest named river draining the basin.

    Purely for legibility in a report. Nothing is decided on it.
    """
    members = node_basin.loc[node_basin["raster_id"] == raster_id, "node_id"]
    if members.empty:
        return None
    with db.registered("_lbl_in", pd.DataFrame({"node_id": members.tolist()})):
        row = db.query(
            """
            SELECT l.name, sum(l.length_m) AS m
            FROM link l JOIN _lbl_in n ON n.node_id = l.to_node
            WHERE l.name IS NOT NULL
            GROUP BY 1 ORDER BY m DESC, 1 LIMIT 1
            """
        )
    return row[0][0] if row else None


def _check_northern_edge(band, measured) -> None:
    """No in-scope basin may touch the clipped edge of the grid.

    PLAN.md §1: *because scope is whole basins and every basin drains to a coast, an
    exit at the edge of the study area is not a legitimate terminus — it is a defect.
    Anything that appears to leave sideways means the scope was drawn wrong, not that
    the water went somewhere unmodelled.*

    The grid is clipped in the north (conf/params.yml `terrain.northing_max_m`), which
    draws exactly such an edge. A clip drawn by hand is an assumption; this turns it
    into an invariant the build enforces. If an in-scope basin reaches the edge, the
    clip is wrong and the answer is to move it north, not to accept the basin.
    """
    top_row = band[0, :]
    touching = set(int(v) for v in np.unique(top_row) if v > basin_logic.NO_BASIN)
    if not touching:
        log.detail("    no basin at all reaches the clipped northern edge")
        return
    in_scope_ids = set(
        int(r) for r in measured.loc[measured["in_scope"], "raster_id"].tolist()
    )
    offenders = sorted(touching & in_scope_ids)
    # Worded as a test result, not as a rule. "None of them may be in scope" reads as
    # a finding that none are, which is how a failing run got misread as a passing one.
    log.detail(
        f"    {len(touching):,} basins touch the clipped northern edge, of which "
        f"{len(offenders):,} are in scope (the rule allows none)"
    )
    if offenders:
        detail = measured[measured["raster_id"].isin(offenders)]
        rows = "\n  ".join(
            f"basin {int(r.raster_id)}: {r.area_km2:,.0f} km2, "
            f"{r.england_wales_area_km2:,.0f} km2 of it in England or Wales"
            for r in detail.itertuples()
        )
        raise StageError(
            f"{len(offenders)} in-scope basin(s) reach the northern edge of the "
            "clipped grid, which means the clip was drawn wrong. PLAN.md §1: an exit "
            "at the edge of the study area is not a terminus but a defect. Raise "
            "conf/params.yml terrain.northing_max_m until this passes; do not accept "
            f"the basins.\n  {rows}"
        )
