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

    width = int(round((right - left) / cell))
    height = int(round((top - bottom) / cell))
    nodata = float(config.param("terrain.nodata"))
    log.detail(
        f"    national grid {width:,} x {height:,} cells at {cell:g} m, "
        f"{left:,.0f}-{right:,.0f} E, {bottom:,.0f}-{top:,.0f} N"
    )

    grid = np.full((height, width), nodata, dtype=np.float32)
    for z, m, l, b, r, t in bounds:
        with rasterio.open(f"/vsizip/{z}/{m}") as ds:
            tile = ds.read(1)
            tile_nodata = ds.nodata
        row0 = int(round((top - t) / cell))
        col0 = int(round((l - left) / cell))
        if tile_nodata is not None:
            tile = np.where(np.isclose(tile, tile_nodata), nodata, tile)
        grid[row0 : row0 + tile.shape[0], col0 : col0 + tile.shape[1]] = tile

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
        "predictor": 2,
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
        "tiles": len(members),
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
    """
    import geopandas as gpd

    frame = db.df(
        "SELECT link_id, ST_AsWKB(geom) AS wkb FROM link ORDER BY link_id"
    )
    import shapely

    gdf = gpd.GeoDataFrame(
        {"link_id": frame["link_id"]},
        geometry=[shapely.from_wkb(bytes(w)) for w in frame["wkb"]],
        crs=config.param("crs.working"),
    )
    out = paths.INTERIM / "network_streams.shp"
    gdf.to_file(out)
    log.detail(f"    {len(gdf):,} links written for burning")
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

    # Check the conditioning rather than assume it. A cell with no downslope
    # neighbour is a place the water cannot leave, and a surface still full of them
    # will delineate basins that are an artefact of the conditioning rather than of
    # the terrain. Fail loudly is the rule; this is what there is to fail on.
    log.info("  checking the conditioned surface for cells water cannot leave")
    no_flow = paths.INTERIM / "terrain50_no_flow_cells.tif"
    rc = wbt.find_no_flow_cells(dem=raster.CONDITIONED.name, output=no_flow.name)
    if rc != 0:
        raise StageError(f"WhiteboxTools find_no_flow_cells returned {rc}")
    with rasterio.open(no_flow) as ds:
        band = ds.read(1)
        nd = ds.nodata
        stuck = int(np.count_nonzero((band != (nd if nd is not None else -32768)) & (band > 0)))
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

    with rasterio.open(raster.BASINS) as ds:
        band = ds.read(1)
        ids = np.unique(band[band != (ds.nodata if ds.nodata is not None else -32768)])
    log.done(f"{len(ids):,} basins delineated to the coast")

    detail["basins_delineated"] = int(len(ids))
    detail["whitebox"] = WBT_VERSION
    return detail
