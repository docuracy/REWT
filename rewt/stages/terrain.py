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

    forms = config.param("terrain.burn_forms")
    placeholders = ", ".join(f"'{f}'" for f in forms)
    frame = db.df(
        f"SELECT link_id, form, ST_AsWKB(geom) AS wkb FROM link "
        f"WHERE form IN ({placeholders}) ORDER BY link_id"
    )
    excluded = db.scalar(
        f"SELECT count(*) FROM link WHERE form NOT IN ({placeholders})"
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
        f"    {len(gdf):,} links written for burning ({', '.join(forms)}); "
        f"{excluded:,} excluded by form and {dropped:,} more lie wholly outside the "
        "terrain extent"
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


def _sea_as_outlet() -> None:
    """Give the sea an elevation, so that water can leave the land.

    Terrain 50 masks the sea out, and a masked cell is a **wall**: WhiteboxTools will
    not route flow into nodata. Left that way, water cannot leave England and Wales at
    all, and the conditioning pools the entire country into whatever its lowest land
    cell happens to be. Measured: 72 million cells — 88% of the land — draining to one
    node at -3.2 m in the Somerset Levels behind Bridgwater Bay, which is genuinely the
    lowest ground in the country and therefore a completely plausible-looking answer.

    So the sea is written in below every land cell. It is not terrain and is never
    sampled as terrain: this raster exists only to delineate, it is named for what it
    is, and `rewt.raster` refuses it for any question about elevation.
    """
    with rasterio.open(raster.UNCONDITIONED) as src:
        profile = src.profile
        dem = src.read(1)
        nodata = src.nodata

    from scipy import ndimage

    sea = np.isclose(dem, nodata)
    land_min = float(dem[~sea].min())
    sea_level = land_min - float(config.param("terrain.sea_depth_below_land_m"))

    # Only a MARGIN of sea is written in, not the whole of it. The sea has to be an
    # outlet at the coast and nowhere else, and giving all 102 million of its cells a
    # value more than doubles the conditioning's work for no gain -- breaching went
    # from seven minutes to over thirty. Beyond the margin the raster stays nodata, so
    # the margin's outer rim is the edge of the data, which is what an outlet is.
    margin_cells = int(config.param("terrain.sea_margin_cells"))
    near_land = ndimage.binary_dilation(~sea, iterations=margin_cells)
    margin = sea & near_land
    dem[margin] = sea_level
    profile.update(BIGTIFF="YES")
    with rasterio.open(raster.HYDRO, "w", **profile) as dst:
        dst.write(dem, 1)
    log.detail(
        f"    a {margin_cells * 50:,.0f} m sea margin -- {int(margin.sum()):,} cells "
        f"of {int(sea.sum()):,} -- set to {sea_level:,.1f} m, below the lowest land at "
        f"{land_min:,.1f} m, so that coastal water has somewhere to go"
    )


def _pour_points() -> Path:
    """River mouths, taken from the survey's own tidal termini.

    A basin has one outlet, which is what makes "what share of this basin can reach its
    own sea?" a complete question (PLAN.md §6). Delineating to the edge of the data
    cannot give that, because a connected sea is one edge and would return one basin
    for the country. Delineating to *these* points gives a catchment per river mouth,
    anchored to a node the network actually contains.

    They come from `form = tidalRiver`, never from a coastline (§5), and they are taken
    from anywhere — including Scotland, because the Border Esk's mouth is in
    Dumfriesshire and a basin seeded only inside England and Wales would strand it.
    """
    import geopandas as gpd

    frame = db.df(
        """
        WITH outflow AS (SELECT DISTINCT from_node AS node_id FROM link),
             inflow  AS (SELECT DISTINCT to_node   AS node_id FROM link)
        SELECT n.node_id, n.easting, n.northing
        FROM node n
        JOIN inflow i ON i.node_id = n.node_id
        LEFT JOIN outflow o ON o.node_id = n.node_id
        WHERE o.node_id IS NULL AND n.terminus = 'tidal'
        ORDER BY n.node_id
        """
    )
    if frame.empty:
        raise StageError(
            "no tidal termini to delineate from. A basin is the catchment of an outlet; "
            "without outlets there is nothing to delineate to."
        )
    gdf = gpd.GeoDataFrame(
        {"node_id": frame["node_id"]},
        geometry=gpd.points_from_xy(frame["easting"], frame["northing"]),
        crs=config.param("crs.working"),
    )
    out = paths.INTERIM / "pour_points.shp"
    for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        out.with_suffix(suffix).unlink(missing_ok=True)
    gdf.to_file(out)
    log.detail(f"    {len(gdf):,} river mouths to delineate to")
    return out


def _whitebox():
    import whitebox

    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(paths.INTERIM.resolve()))
    # ONE PROCESS, AND THIS IS A CORRECTNESS SETTING RATHER THAN A TUNING ONE.
    # `breach_depressions_least_cost` is not deterministic when it threads: measured on
    # the burned national surface, two runs over a byte-identical input produced
    # different rasters (sha 3b40f5b3… and 7b54eef1…), and a third, single-threaded,
    # produced a third. Two single-threaded runs then agreed exactly (12bec237…).
    #
    # The cost is nothing. 452 s single-threaded against 451 s threaded — the tool was
    # buying non-determinism for no speed whatever.
    #
    # It matters because the conditioning decides the delineation. One threaded run
    # merged the Midlands and the Scottish border into a single 18,148 km² "basin",
    # caught only because §1's northern-edge invariant refused it. And PLAN.md §9 asks
    # for the same output from the same inputs twice, which nothing in a threaded run
    # can promise.
    wbt.set_max_procs(1)
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

    _sea_as_outlet()

    wbt = _whitebox()
    log.info("  breaching depressions — breach, do not fill (PLAN.md §5)")
    max_dist = int(config.param("terrain.breach_max_dist_cells"))
    rc = wbt.breach_depressions_least_cost(
        dem=raster.HYDRO.name,
        output=raster.CONDITIONED.name,
        dist=max_dist,
        fill=True,
    )
    if rc != 0:
        raise StageError(f"WhiteboxTools breach_depressions_least_cost returned {rc}")
    raster.assert_usable(
        raster.CONDITIONED,
        "WhiteboxTools breach_depressions_least_cost",
        (-600.0, 1400.0),
    )

    # Check the conditioning rather than assume it. A cell with no downslope neighbour
    # is a place the water cannot leave; a surface still full of them will delineate
    # basins that are an artefact of the conditioning rather than of the terrain.
    log.info("  checking the conditioned surface for cells water cannot leave")
    no_flow = paths.INTERIM / "terrain50_no_flow_cells.tif"
    rc = wbt.find_no_flow_cells(dem=raster.CONDITIONED.name, output=no_flow.name)
    if rc != 0:
        raise StageError(f"WhiteboxTools find_no_flow_cells returned {rc}")
    with rasterio.open(no_flow) as ds:
        flags = ds.read(1)
    with rasterio.open(raster.UNCONDITIONED) as ds:
        land = ds.read(1) != ds.nodata
    stuck = int(np.count_nonzero(np.isfinite(flags) & (flags > 0) & land))
    land_cells = detail["land_cells"]
    log.detail(
        f"    {stuck:,} land cells have no downslope neighbour after breaching "
        f"({stuck / land_cells:.4%} of land)"
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

    # Delineate to the network's own river mouths, not to the edge of the data.
    # `Basins` delineates everything draining to the data edge, and with the sea
    # written in as an outlet that edge is one connected surface — so it returns the
    # country as a single basin. A catchment per river mouth is both what §4.1 needs
    # and what makes `basin.outlet_node` mean something.
    log.info("  delineating a catchment for each river mouth")
    pour = _pour_points()
    snapped = paths.INTERIM / "pour_points_snapped.shp"
    rc = wbt.snap_pour_points(
        pour_pts=pour.name,
        flow_accum=raster.FLOW_ACC.name,
        output=snapped.name,
        snap_dist=float(config.param("basins.pour_point_snap_m")),
    )
    if rc != 0:
        raise StageError(f"WhiteboxTools snap_pour_points returned {rc}")

    rc = wbt.watershed(
        d8_pntr=raster.D8_POINTER.name,
        pour_pts=snapped.name,
        output=raster.BASINS.name,
    )
    if rc != 0:
        raise StageError(f"WhiteboxTools watershed returned {rc}")
    raster.assert_usable(raster.BASINS, "WhiteboxTools watershed", (1.0, 5e6))

    # The sea is in the conditioned surface as an outlet; it is not land and is not in
    # any basin. Mask it back out, so a basin's area is an area of ground.
    with rasterio.open(raster.BASINS) as ds:
        band = ds.read(1)
        profile = ds.profile
        bnd = ds.nodata if ds.nodata is not None else -32768.0
    band = np.where(land, band, bnd)
    profile.update(BIGTIFF="YES")
    with rasterio.open(raster.BASINS, "w", **profile) as dst:
        dst.write(band, 1)

    ids, counts = np.unique(band[band != bnd], return_counts=True)
    km2 = counts * (detail["cell_m"] ** 2) / 1e6
    log.done(f"{len(ids):,} basins delineated to river mouths")
    if len(ids):
        # Report the shape, not the count. A plausible number of basins with one of
        # them holding most of the country is the failure this stage has already had
        # twice, and it is invisible in any total.
        log.detail(
            f"    largest {km2.max():,.0f} km2 ({km2.max() / km2.sum():.1%} of the "
            f"delineated area), median {np.median(km2):,.1f} km2, "
            f"{int((km2 >= 100).sum()):,} over 100 km2"
        )
        detail["largest_basin_km2"] = round(float(km2.max()), 1)
        detail["largest_basin_share"] = round(float(km2.max() / km2.sum()), 4)

    detail["basins_delineated"] = int(len(ids))
    detail["whitebox"] = WBT_VERSION
    return detail
