"""Stage: the water bodies the survey routes through, or does not route through at all.

PLAN.md §5's fourth case, and the one that needs a second source:

> Where a watercourse meets a lake, reservoir or broad, OS Open Rivers either draws a
> **schematic straight line** across it — some 2,300 km of the network is routed this
> way — or draws nothing, and the network is severed.

This stage loads the polygons so the second case can be found. **It earns its place
here on a measurement, not on the plan's say-so**: of the 26 largest stranded components
whose nearest approach to draining water is greater than zero, **16 — holding 603 km of
1,006 — have a mapped water body lying between them and it.** Sixty per cent of the
residue is this case.

Three cautions from §5, all of them enforced:

* **It is not a base network and must not be made one.** Its water has no topology
  whatever — 1.36 million lines in 892,000 components, 0.7% of its length in a
  component that reaches tidal water. It supplies polygons; OS Open Rivers keeps
  supplying topology.
* **Width can measure the sea.** At estuary scale a "channel" is a bay. Polygons
  meeting OS OpenMap – Local's own tidal water are excluded rather than discovered in
  the output.
* **Only where it earns its place.** A minimum area keeps the table to the bodies big
  enough to sever a network; below that a polygon is a pond beside a stream.
"""

from __future__ import annotations

import geopandas as gpd
import shapely

from .. import acquire, config, db, paths
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Report, log

WATER_BODY = artefact("water_body")


@PIPELINE.stage(
    "water_bodies",
    "load the water bodies a network can be severed by",
    reads=["raw_os_open_map_local"],
    writes=["water_body"],
    params=["water_bodies", "crs"],
    sources=["os_open_map_local"],
)
def run() -> dict:
    src = config.source("os_open_map_local")
    src.require_redistributable()
    gpkg = acquire.one("os_open_map_local", "opmplc_gb.gpkg")
    working = config.param("crs.working")
    min_area = float(config.param("water_bodies.min_polygon_area_m2"))

    log.info(f"  reading surface water areas of {min_area:,.0f} m2 or more")
    water = gpd.read_file(gpkg, layer="surface_water_area")
    if str(water.crs) != working:
        water = water.to_crs(working)
    before = len(water)
    water = water[water.geometry.area >= min_area].copy()
    log.detail(f"    {len(water):,} of {before:,} polygons are large enough to sever a network")

    if config.param("water_bodies.exclude_tidal"):
        # Width can measure the sea: at estuary scale a "channel" is a bay, and a route
        # through one means nothing. Excluded here rather than discovered in the output.
        tidal = gpd.read_file(gpkg, layer="tidal_water")
        if str(tidal.crs) != working:
            tidal = tidal.to_crs(working)
        joined = gpd.sjoin(water, tidal[["geometry"]], predicate="intersects", how="left")
        tidal_hit = joined[joined["index_right"].notna()].index.unique()
        log.detail(
            f"    {len(tidal_hit):,} of them meet OS OpenMap - Local's own tidal water "
            "and are excluded: a medial axis through a bay is meaningless (§5)"
        )
        water = water.loc[~water.index.isin(tidal_hit)].copy()

    water = water.sort_values("id", kind="stable").reset_index(drop=True)
    frame = water[["id"]].copy()
    frame["area_m2"] = water.geometry.area.values
    frame["wkb"] = [shapely.to_wkb(g) for g in water.geometry]

    con = db.get()
    con.execute("DROP TABLE IF EXISTS water_body")
    with db.registered("_water_in", frame):
        con.execute(
            """
            CREATE TABLE water_body AS
            SELECT id AS publisher_id, area_m2,
                   'os_open_map_local' AS source_id,
                   ST_GeomFromWKB(wkb) AS geom
            FROM _water_in ORDER BY publisher_id
            """
        )
    total = db.count("water_body")
    if not total:
        raise StageError("no water bodies survived the filters; check the thresholds")
    log.done(f"{total:,} water bodies, {frame['area_m2'].sum() / 1e6:,.0f} km2")

    report = Report("water_bodies")
    report.add("polygons", {"read": before, "kept": total,
                            "km2": round(float(frame["area_m2"].sum()) / 1e6, 1)})
    report.write_json(paths.PUBLISHED / "audit" / "water_bodies.json")
    return {"water_bodies": total}
