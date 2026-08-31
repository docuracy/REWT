"""Stage: the Terrain 50 mosaic, and the surfaces derived from it.

PLAN.md §5 is precise about why this exists and what it is not for.

**Basins: yes, and this is the real reason to acquire it.** Without a topographic
delineation there is no way to tell a shared estuary from a shared catchment, and the
scope rule has nothing to test (§4.1).

**Direction: a screen, never an authority.** Terrain 50 posts every 50 m with an RMSE
of about 4 m, so a fall inside ±4 m is inside its own error bar. It screens the
uplands, where you least need it, and is silent on the levels, where you most do.

And the circularity that has to be avoided: **burning the network into the DEM is the
standard first step in hydrological conditioning, and it is correct for delineating
catchments — but a burned DEM has the network's own direction stamped into it, so
checking direction against it proves nothing.** Two rasters, distinctly named, are
written here, and `rewt.raster` refuses to sample the wrong one for a direction check.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin  # noqa: F401  (grid arithmetic below)

from .. import acquire, config, db, paths, raster
from ..pipeline import PIPELINE, StageError, artefact
from ..report import log

DEM_RAW = artefact("terrain50_unconditioned", "file", str(raster.UNCONDITIONED.relative_to(paths.ROOT)))
DEM_COND = artefact("terrain50_conditioned", "file", str(raster.CONDITIONED.relative_to(paths.ROOT)))
D8 = artefact("terrain50_d8_pointer", "file", str(raster.D8_POINTER.relative_to(paths.ROOT)))
BASIN_RASTER = artefact("terrain50_basins", "file", str(raster.BASINS.relative_to(paths.ROOT)))

# WhiteboxTools fetches its own binary on first use. The version is checked rather than
# assumed, because a hydrology tool that silently changed its breaching algorithm would
# move every basin boundary in the country without anything saying so.
WBT_VERSION = "2.4.0"


def _tile_bounds(path: Path, member: str) -> tuple[float, float, float, float, float]:
    with rasterio.open(f"/vsizip/{path}/{member}") as ds:
        b = ds.bounds
        return b.left, b.bottom, b.right, b.top, ds.transform.a


def _mosaic() -> dict:
    """Place 2,858 ten-kilometre tiles into one national grid.

    Placed by their own affine transform rather than merged pairwise: the tiles are on
    an exact grid, so arithmetic is both faster and exactly reproducible where a
    resampling merge is neither.
    """
    zips = acquire.find("os_terrain_50", "*.zip")
    if not zips:
        raise StageError("OS Terrain 50 holds no tile archives; re-acquire it")

    members: list[tuple[Path, str]] = []
    for z in zips:
        with zipfile.ZipFile(z) as zf:
            asc = [n for n in zf.namelist() if n.lower().endswith(".asc")]
        if len(asc) != 1:
            raise StageError(f"{paths.rel(z)} holds {len(asc)} .asc files; expected one")
        members.append((z, asc[0]))

    log.info(f"  mosaicking {len(members):,} Terrain 50 tiles")
    left = bottom = float("inf")
    right = top = float("-inf")
    cell = None
    bounds = []
    for z, m in members:
        l, b, r, t, res = _tile_bounds(z, m)
        bounds.append((z, m, l, b, r, t))
        left, bottom = min(left, l), min(bottom, b)
        right, top = max(right, r), max(top, t)
        if cell is None:
            cell = res
        elif abs(cell - res) > 1e-9:
            raise StageError(f"{paths.rel(z)} has cell size {res}, not {cell}")

    declared = config.param("terrain.resolution_m")
    if abs(cell - declared) > 1e-6:
        raise StageError(
            f"Terrain 50 arrived at {cell} m, not the {declared} m conf/params.yml "
            "declares. A changed posting changes every figure downstream."
        )

    # Clip the north (see conf/params.yml terrain.northing_max_m for why, and for
    # why the basins stage then checks that nothing in scope touches the edge).
    clip_top = float(config.param("terrain.northing_max_m"))
    if clip_top < top:
        log.detail(
            f"    clipping the grid at {clip_top:,.0f} N: everything above drains "
            "only to Scotland, which is out of scope (D-003), and delineating it "
            "would be work with no consumer"
        )
        top = clip_top

    width = int(round((right - left) / cell))
    height = int(round((top - bottom) / cell))
    nodata = float(config.param("terrain.nodata"))
    log.detail(
        f"    national grid {width:,} x {height:,} cells at {cell:g} m, "
        f"{left:,.0f}-{right:,.0f} E, {bottom:,.0f}-{top:,.0f} N"
    )

    grid = np.full((height, width), nodata, dtype=np.float32)
    placed = 0
    for z, m, l, b, r, t in bounds:
        if b >= top:
            continue          # wholly above the clip
        with rasterio.open(f"/vsizip/{z}/{m}") as ds:
            tile = ds.read(1)
            tile_nodata = ds.nodata
        if tile_nodata is not None:
            tile = np.where(np.isclose(tile, tile_nodata), nodata, tile)
        row0 = int(round((top - t) / cell))
        col0 = int(round((l - left) / cell))
        # A tile straddling the clip contributes only its part below it.
        if row0 < 0:
            tile = tile[-row0:, :]
            row0 = 0
        if row0 >= height:
            continue
        tile = tile[: height - row0, :]
        grid[row0 : row0 + tile.shape[0], col0 : col0 + tile.shape[1]] = tile
        placed += 1

    transform = from_origin(left, top, cell, cell)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": config.param("crs.working"),
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
        # NO PREDICTOR, and this is not a tuning choice. WhiteboxTools reads GeoTIFF
        # with its own decoder rather than GDAL's, and it cannot decode DEFLATE with
        # a horizontal predictor. Handed such a file it does not fail: it returns
        # success and writes an output of NaN and 3.3e38, with one 512-column stripe
        # of plausible values at the left edge. Three builds and two wrong diagnoses
        # went into finding that, because the corruption is deterministic and
        # depends only on how the INPUT was compressed — so it survives changing the
        # streams, the extent and the tool's parameters. `assert_usable` below is the
        # guard that turns the next occurrence of this class into a loud failure.
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "BIGTIFF": "YES",
    }
    raster.UNCONDITIONED.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(raster.UNCONDITIONED, "w", **profile) as dst:
        dst.write(grid, 1)

    covered = int((grid != nodata).sum())
    # The sea is masked out of Terrain 50. That is not a gap: a node standing on
    # nodata is confirmation that it is at tidal water (§6).
    log.detail(
        f"    {covered / grid.size:.1%} of the national grid carries an elevation; "
        "the rest is sea, which the product masks out"
    )
    return {
        "tiles": placed,
        "tiles_available": len(members),
        "clipped_at_northing": top,
        "width": width,
        "height": height,
        "cell_m": cell,
        "bounds": [left, bottom, right, top],
        "land_cells": covered,
    }


def _write_stream_vector() -> Path:
    """The network as a vector file, for WhiteboxTools to burn.

    Shapefile because that is what WhiteboxTools reads; it is an interim artefact and
    never published, so its limitations do not reach anything a consumer sees.

    **Clipped to the raster's own extent, and this is not tidiness.** Handed stream
    geometry that lies outside the DEM, WhiteboxTools' `FillBurn` returns success and
    writes a raster of NaN and 3.3e38 — 185 million cells of it, with not one valid
    value, and nothing in the return code or the log to say so. It cost two builds to
    find, and the give-away was that the same call over a bbox-read subset of the same
    streams was exact. Links outside the extent are counted and named here rather than
    dropped quietly, because a link with no terrain under it is itself a finding.
    """
    import geopandas as gpd
    import shapely

    with rasterio.open(raster.UNCONDITIONED) as ds:
        b = ds.bounds
    box = shapely.box(b.left, b.bottom, b.right, b.top)

    frame = db.df(
        "SELECT link_id, ST_AsWKB(geom) AS wkb FROM link ORDER BY link_id"
    )
    geoms = [shapely.from_wkb(bytes(w)) for w in frame["wkb"]]
    inside = shapely.intersects(box, geoms)
    dropped = int((~inside).sum())

    kept = [g for g, keep in zip(geoms, inside) if keep]
    # A link that straddles the edge is cut at it, so nothing outside reaches the tool.
    clipped = [
        g if shapely.contains(box, g) else shapely.intersection(box, g) for g in kept
    ]
    gdf = gpd.GeoDataFrame(
        {"link_id": frame.loc[inside, "link_id"].to_numpy()},
        geometry=clipped,
        crs=config.param("crs.working"),
    )
    gdf = gdf[~gdf.geometry.is_empty]

    out = paths.INTERIM / "network_streams.shp"
    for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        out.with_suffix(suffix).unlink(missing_ok=True)
    gdf.to_file(out)
    log.detail(
        f"    {len(gdf):,} links written for burning; {dropped:,} lie wholly outside "
        "the terrain extent and are not burned"
    )
    return out


def _burn(streams: Path) -> None:
    """Burn the network into the surface, for delineation only.

    A 50 m surface gives no gradient at all across embanked or levelled ground, so
    without this the delineation wanders. **The tool matters here.** Subtracting a
    fixed depth along the rasterised lines — the obvious thing, and what this stage
    did first — cuts a *flat* trench, and flow direction along a flat trench is
    arbitrary: the delineation then wanders along the channel instead of across it.
    WhiteboxTools' `FillBurn` implements Saunders (1999), which incises the stream so
    that it descends monotonically to its outlet, and that is the property the
    delineation actually needs.

    The result is named `burned` and `filled` so that `rewt.raster` will refuse to
    sample it for a direction check (D-007).
    """
    wbt = _whitebox()
    rc = wbt.fill_burn(
        dem=raster.UNCONDITIONED.name,
        streams=streams.name,
        output=raster.BURNED.name,
    )
    if rc != 0:
        raise StageError(f"WhiteboxTools fill_burn returned {rc}")
    # A burned surface is the terrain minus a burn depth, so the plausible range is
    # the terrain's own, slack at the bottom. Britain's highest ground is 1,345 m.
    raster.assert_usable(raster.BURNED, "WhiteboxTools fill_burn", (-500.0, 1400.0))


def _whitebox():
    import whitebox

    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(paths.INTERIM.resolve()))
    version = wbt.version().splitlines()[0]
    if WBT_VERSION not in version:
        raise StageError(
            f"WhiteboxTools reports {version!r}, not {WBT_VERSION}. A hydrology tool "
            "that changes its breaching algorithm moves every basin boundary in the "
            "country; pin the version or record the change in DECISIONS.md."
        )
    return wbt


@PIPELINE.stage(
    "terrain",
    "Terrain 50 mosaic, and the conditioned surface basins are delineated on",
    reads=["raw_os_terrain_50", "link"],
    writes=[
        "terrain50_unconditioned",
        "terrain50_conditioned",
        "terrain50_d8_pointer",
        "terrain50_basins",
    ],
    params=["terrain", "crs", "basins"],
    sources=["os_terrain_50"],
)
def run() -> dict:
    detail = _mosaic()

    log.info("  burning the network for delineation (never for a direction check)")
    streams = _write_stream_vector()
    _burn(streams)

    wbt = _whitebox()
    log.info("  breaching depressions — breach, do not fill (PLAN.md §5)")
    max_dist = int(config.param("terrain.breach_max_dist_cells"))
    rc = wbt.breach_depressions_least_cost(
        dem=raster.BURNED.name,
        output=raster.CONDITIONED.name,
        dist=max_dist,
        fill=True,
    )
    if rc != 0:
        raise StageError(f"WhiteboxTools breach_depressions_least_cost returned {rc}")
    raster.assert_usable(
        raster.CONDITIONED,
        "WhiteboxTools breach_depressions_least_cost",
        (-500.0, 1400.0),
    )

    # Check the conditioning rather than assume it. A cell with no downslope
    # neighbour is a place the water cannot leave, and a surface still full of them
    # will delineate basins that are an artefact of the conditioning rather than of
    # the terrain. Fail loudly is the rule; this is what there is to fail on.
    log.info("  checking the conditioned surface for cells water cannot leave")
    no_flow = paths.INTERIM / "terrain50_no_flow_cells.tif"
    rc = wbt.find_no_flow_cells(dem=raster.CONDITIONED.name, output=no_flow.name)
    if rc != 0:
        raise StageError(f"WhiteboxTools find_no_flow_cells returned {rc}")
    # Count only over land. The sea is masked out of Terrain 50 and every sea cell
    # trivially has no downslope neighbour; counting those gave 204% of the land
    # area, which is the kind of number that should stop a person rather than be
    # written down.
    with rasterio.open(no_flow) as ds:
        flags = ds.read(1)
    with rasterio.open(raster.UNCONDITIONED) as ds:
        land = ds.read(1) != ds.nodata
    stuck = int(np.count_nonzero(np.isfinite(flags) & (flags > 0) & land))
    land_cells = detail["land_cells"]
    log.detail(
        f"    {stuck:,} cells have no downslope neighbour after breaching "
        f"({stuck / land_cells:.4%} of land). These are the places the delineation "
        "cannot resolve; they are reported, not silently accepted."
    )
    detail["no_flow_cells"] = stuck

    log.info("  D8 flow pointer and flow accumulation")
    for fn, kwargs in (
        (wbt.d8_pointer, {"dem": raster.CONDITIONED.name, "output": raster.D8_POINTER.name}),
        (
            wbt.d8_flow_accumulation,
            {
                "i": raster.CONDITIONED.name,
                "output": raster.FLOW_ACC.name,
                "out_type": "cells",
            },
        ),
    ):
        rc = fn(**kwargs)
        if rc != 0:
            raise StageError(f"WhiteboxTools {fn.__name__} returned {rc}")

    # `Basins` delineates every catchment draining to the edge of the data. Terrain 50
    # masks the sea out, so "the edge of the data" is the coastline — which is exactly
    # the delineation §4.1 needs, and is why a shared estuary does not become a shared
    # catchment here as it does with network components.
    log.info("  delineating basins to the coast")
    rc = wbt.basins(d8_pntr=raster.D8_POINTER.name, output=raster.BASINS.name)
    if rc != 0:
        raise StageError(f"WhiteboxTools basins returned {rc}")
    # A basin id is a small positive integer. Forty million of them means the pointer
    # it was delineated from was noise.
    raster.assert_usable(raster.BASINS, "WhiteboxTools basins", (1.0, 5e6))

    with rasterio.open(raster.BASINS) as ds:
        band = ds.read(1)
        ids = np.unique(band[band != (ds.nodata if ds.nodata is not None else -32768)])
    log.done(f"{len(ids):,} basins delineated to the coast")

    detail["basins_delineated"] = int(len(ids))
    detail["whitebox"] = WBT_VERSION
    return detail
