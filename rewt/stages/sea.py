"""The sea network: a cost surface, and the routes that emerge from it (§10).

Turns "reaches the sea" from a definition into a test. Every tidal terminus and every
mouth currently blocked at the coast is snapped to open water; cost-allocation
partitions the sea between them; and the minimum spanning tree over those territories
is the network. The loop is not drawn and is not a parameter — it is what remains
where the routes agree.
"""

from __future__ import annotations

import subprocess

import numpy as np
import pandas as pd

from .. import acquire, config, db, ids, paths, schema, sea
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Report, log
from . import terrain

SEA_ENTRY = artefact("sea_entry")
SEA_LINK = artefact("sea_link")

VRT = paths.INTERIM / "emodnet.vrt"
DEPTH = paths.INTERIM / "sea_depth.tif"
COST = paths.INTERIM / "sea_cost.tif"
SOURCES = paths.INTERIM / "sea_sources.tif"


def _mosaic_and_warp(cell_m: float, working_crs: str) -> None:
    """120 WCS windows to one National Grid raster.

    RESAMPLED BY AVERAGE, NOT MAXIMUM, and this is a correctness choice rather than a
    tuning one. Max — the shallowest point in each cell — looks conservative and is
    wrong: a cell holding one rock and 9,900 m2 of deep water is still connected water,
    and taking the rock erodes every channel until the coast is a wall. Measured, the
    Solent closed under max. It is also what `sea.clearance_m`'s justification assumes,
    that being a margin against the cell AVERAGING over its footprint.
    """
    src = config.source("emodnet_bathymetry")
    windows = sorted((paths.ROOT / src.get("cache_path")).glob("*.tif"))
    if not windows:
        raise StageError(
            "no bathymetry windows on disk; run `rewt acquire emodnet_bathymetry`"
        )
    subprocess.run(["gdalbuildvrt", "-q", "-overwrite", str(VRT),
                    *[str(w) for w in windows]], check=True)
    subprocess.run(
        ["gdalwarp", "-q", "-overwrite", "-t_srs", working_crs,
         "-tr", str(cell_m), str(cell_m), "-tap", "-r", "average",
         # nodata must be explicit: the source declares none, so without this every
         # cell outside the fetched window warps to 0.0 and is indistinguishable from
         # water at exactly Lowest Astronomical Tide.
         "-dstnodata", "nan",
         "-of", "GTiff", "-co", "COMPRESS=DEFLATE", "-co", "TILED=YES",
         str(VRT), str(DEPTH)], check=True)
    log.detail(f"{len(windows)} windows mosaicked and warped to {working_crs} at {cell_m:.0f} m")


def _mouths(con) -> pd.DataFrame:
    """Every tidal terminus, and every in-scope dead end that is not at tidal water.

    §10 serves *"every river now reaching the sea and every river now blocked at the
    coast"*. The second are not in the `terminus` layer at all — their terminus is not
    tidal, which is exactly what makes them blocked — so a source set taken from
    termini alone excludes the population the construction exists for.

    **No distance-to-coast threshold decides who is offered.** An earlier definition
    admitted a sink only if it lay within 250 m of mean high water and more than 250 m
    from a tidal link. Both numbers were invented, and rewt-86 — whose definition they
    were — said so. They are unnecessary: a dead end far inland simply finds no open
    sea to snap to and is reported as such. Letting the sea decide who is at the coast
    is better than asserting it with a threshold, and it removes two parameters that
    would have had to be defended.
    """
    return con.execute(
        """
        SELECT n.node_id, 'terminus' AS kind, n.easting, n.northing
        FROM node n WHERE n.terminus = 'tidal'
        UNION ALL
        SELECT n.node_id, 'blocked' AS kind, n.easting, n.northing
        FROM node n
        WHERE n.terminus IS DISTINCT FROM 'tidal'
          AND NOT EXISTS (SELECT 1 FROM edge e WHERE e.from_node = n.node_id)
          -- SCOPE THROUGH THE ARRIVING LINK, NOT THROUGH THE NODE'S BASIN. Scoping
          -- via node_basin excludes exactly the mouths this stage exists for: 27% of
          -- nodes fall outside every delineated basin because the delineation runs
          -- out at the coast (D-050), and a mouth blocked at the coast is the most
          -- likely node in the country to have no basin. Measured: the basin join
          -- gives 967 blocked mouths, the link join 1,970.
          AND EXISTS (
              SELECT 1 FROM edge e JOIN link_scope sc ON sc.link_id = e.link_id
              WHERE e.to_node = n.node_id AND sc.in_scope)
        ORDER BY 1
        """
    ).df()


@PIPELINE.stage(
    "sea",
    "the sea network: a cost surface, and the routes that emerge from it",
    reads=["node", "edge", "basin", "node_basin"],
    writes=["sea_entry", "sea_link"],
    params=["sea", "crs"],
    sources=["emodnet_bathymetry"],
)
def run() -> dict:
    import rasterio
    from rasterio.transform import rowcol, xy
    from shapely.geometry import LineString

    p = config.params()
    con = db.get()
    report = Report("sea")
    cell_m = float(p("sea.cell_m"))
    clearance = float(p("sea.clearance_m"))
    deep = float(p("sea.deep_reference_m"))
    max_km = float(p("sea.max_path_km"))
    working = p("crs.working")

    acquire.require_acquisition("emodnet_bathymetry")
    _mosaic_and_warp(cell_m, working)

    with rasterio.open(DEPTH) as ds:
        elev = ds.read(1)
        T = ds.transform
        prof = ds.profile
    depth = -elev
    cost, passable = sea.cost_surface(depth, clearance, deep)
    ocean = sea.open_sea(passable)
    log.info(
        f"{passable.sum():,} passable cells at {clearance:.1f} m below LAT; "
        f"open sea is {ocean.sum():,} of them"
    )
    prof.update(dtype="float32", nodata=-9999.0, compress="DEFLATE", tiled=True)
    with rasterio.open(COST, "w", **prof) as out:
        out.write(cost, 1)

    mouths = _mouths(con)
    H, W = cost.shape
    rows, cols = rowcol(T, mouths["easting"].to_numpy(), mouths["northing"].to_numpy())
    rows = np.clip(np.asarray(rows), 0, H - 1)
    cols = np.clip(np.asarray(cols), 0, W - 1)
    moved, sr, sc = sea.snap(rows, cols, ocean, int(5000 / cell_m), cell_m)
    got = moved >= 0
    for kind in ("terminus", "blocked"):
        m = (mouths["kind"] == kind).to_numpy()
        if not m.any():
            continue
        log.info(
            f"{kind}: {int((got & m).sum()):,} of {int(m.sum()):,} reach open sea "
            f"({(got & m).sum() / m.sum():.1%})"
        )
        log.skip(
            f"{int((~got & m).sum()):,} {kind} mouths have no open sea within 5 km "
            "and cannot be attached; named, not dropped (§10)"
        )

    entries: dict[tuple[int, int], int] = {}
    for i in np.where(got)[0]:
        entries.setdefault((int(sr[i]), int(sc[i])), len(entries) + 1)
    n = len(entries)
    ids_ras = np.zeros(cost.shape, dtype="int32")
    for (r, c), k in entries.items():
        ids_ras[r, c] = k
    p2 = dict(prof)
    p2.update(dtype="int32", nodata=0)
    with rasterio.open(SOURCES, "w", **p2) as out:
        out.write(ids_ras, 1)
    log.detail(f"{n:,} distinct sea entry cells for {int(got.sum()):,} mouths")

    wbt = terrain._whitebox()
    if wbt.cost_distance(source=SOURCES.name, cost=COST.name,
                         out_accum="sea_accum.tif", out_backlink="sea_backlink.tif") != 0:
        raise StageError("cost_distance failed over the sea surface")
    if wbt.cost_allocation(source=SOURCES.name, backlink="sea_backlink.tif",
                           output="sea_alloc.tif") != 0:
        raise StageError("cost_allocation failed over the sea surface")

    with rasterio.open(paths.INTERIM / "sea_alloc.tif") as ds:
        alloc = ds.read(1).astype("int32")
    with rasterio.open(paths.INTERIM / "sea_accum.tif") as ds:
        accum = ds.read(1)
    with rasterio.open(paths.INTERIM / "sea_backlink.tif") as ds:
        back = ds.read(1)

    best = sea.crossings(alloc, accum, cost > 0, n)
    mst, ncomp, _ = sea.spanning_tree(best, n)
    zero = sum(1 for v in best.values() if v[4] == 0.0)
    log.info(
        f"{len(best):,} adjacent territory pairs ({zero:,} costing exactly zero, kept "
        f"in the graph by an epsilon — D-056); {ncomp} connected component(s); "
        f"spanning tree of {mst.nnz:,} edges"
    )
    if ncomp > 1:
        log.warn(
            f"the sea network is in {ncomp} pieces. §10: this is a finding about the "
            "bathymetry and is reported, not repaired."
        )

    max_steps = int(max_km * 1000 / cell_m)
    recs, refused = [], 0
    cell_of = {v: k for k, v in entries.items()}
    node_at: dict[int, list[str]] = {}
    for i in np.where(got)[0]:
        node_at.setdefault(entries[(int(sr[i]), int(sc[i]))], []).append(str(mouths["node_id"].iloc[i]))
    for a, b in zip(mst.row, mst.col):
        ea, eb = int(a) + 1, int(b) + 1
        k = min(ea, eb) * (n + 1) + max(ea, eb)
        ra, ca, rb, cb, _ = best[k]
        pa, oka = sea.walk(back, ra, ca, max_steps)
        pb, okb = sea.walk(back, rb, cb, max_steps)
        if not (oka and okb):
            refused += 1
            continue
        arr = np.array(pa[::-1] + pb)
        xs, ys = xy(T, arr[:, 0], arr[:, 1])
        line = LineString(list(zip(xs, ys))).simplify(cell_m / 2)
        d = depth[arr[:, 0], arr[:, 1]]
        recs.append({
            "link_id": ids.line(list(line.coords), kind="sea"),
            "from_entry": ea, "to_entry": eb,
            "from_node": (node_at.get(ea) or [None])[0],
            "to_node": (node_at.get(eb) or [None])[0],
            "length_m": round(float(line.length), 1),
            "min_depth_m": round(float(np.nanmin(d)), 1),
            "median_depth_m": round(float(np.nanmedian(d)), 1),
            "wkt": line.wkt,
        })
    if refused:
        log.skip(f"{refused:,} routes refused as longer than {max_km:.0f} km or unterminated (§10)")

    frame = pd.DataFrame(recs)
    schema.create("sea_entry", "sea_link")
    entry_rows = pd.DataFrame({
        "entry_id": [entries[(int(sr[i]), int(sc[i]))] for i in np.where(got)[0]],
        "node_id": mouths["node_id"].to_numpy()[got].astype(str),
        "kind": mouths["kind"].to_numpy()[got].astype(str),
        "snapped_m": moved[got],
        "easting": mouths["easting"].to_numpy()[got],
        "northing": mouths["northing"].to_numpy()[got],
    })
    with db.registered("_se_in", entry_rows):
        con.execute("INSERT INTO sea_entry SELECT * FROM _se_in")
    with db.registered("_sl_in", frame):
        con.execute(
            "INSERT INTO sea_link SELECT link_id, from_entry, to_entry, from_node, "
            "to_node, length_m, min_depth_m, median_depth_m, ST_GeomFromText(wkt) "
            "FROM _sl_in"
        )

    total_km = float(frame["length_m"].sum()) / 1000.0
    shallow = int((frame["min_depth_m"] < clearance - 0.05).sum())
    if shallow:
        raise StageError(
            f"{shallow:,} sea routes pass through water shallower than the "
            f"{clearance:.1f} m clearance they were built to respect"
        )
    log.done(f"{len(frame):,} sea routes, {total_km:,.0f} km, none shallower than "
             f"{clearance:.1f} m")
    report.add("entries", n)
    report.add("mouths_attached", int(got.sum()))
    report.add("mouths_unattached", int((~got).sum()))
    report.add("components", int(ncomp))
    report.add("routes", len(frame))
    report.add("route_km", round(total_km, 1))
    report.write_json(paths.PUBLISHED / "audit" / "sea.json")
    return {"routes": len(frame), "km": round(total_km, 1), "entries": n}
