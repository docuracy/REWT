"""Basin delineation, and the scope rule that is decided on it (PLAN.md §4.1).

**A basin is in scope if any part of it lies in England or Wales; the whole of that
basin then is, Scottish headwaters included.** Everything draining only to Scotland —
Forth, Tay, Clyde, Spey — leaves the project.

Two things this must not do, both of which look right and are not:

* **Clip to the political line.** The Tweed reaches the sea at Berwick with four fifths
  of its basin in Scotland; the Border Esk rises in Cumbria and reaches the Solway in
  Dumfriesshire. Cut either at the border and everything below the cut has lost most of
  the water that made it.
* **Use the network's connected components as basins.** OS Open Rivers models the
  Solway Firth as connected tidal water, so the Annan, the Border Esk and the Eden all
  land in a single component — and the test drags Dumfriesshire into an
  England-and-Wales project. **A shared estuary is not a shared catchment.**

**Two rules, and the second is not a fudge.** A link is in scope if its downstream end
falls in an in-scope basin, **or** if it falls in England or Wales. The second is needed
because tidal water is masked out of a DEM and so sits on no basin at all; without it
the scope silently drops the tidal Thames, the Humber, and the navigable head of every
major estuary in the country.

**Nothing is deleted.** Out-of-scope links are flagged, not dropped.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import rasterio
import shapely
from rasterio.features import rasterize, shapes

from . import acquire, config, db, ids, raster
from .report import log

NO_BASIN = 0        # a cell on no basin at all: sea, or outside the data


def country_polygon(names: list[str]) -> shapely.Geometry:
    """The union of Boundary-Line country polygons for the named countries.

    Country boundaries only, and never used to clip the network — only to ask which
    ground a basin covers.
    """
    import pyogrio

    gpkg = acquire.one("os_boundary_line", "bdline_gb.gpkg")
    frame = pyogrio.read_dataframe(
        gpkg,
        layer="country_region",
        where=" OR ".join(f"\"Name\" = '{c}'" for c in names),
    )
    if frame.empty:
        raise RuntimeError(
            f"Boundary-Line country_region holds no polygon named any of {names}"
        )
    working = config.param("crs.working")
    if str(frame.crs) != working:
        frame = frame.to_crs(working)
    return shapely.union_all(list(frame.geometry.values))


def england_and_wales() -> shapely.Geometry:
    """The England-and-Wales polygon the scope rule tests against.

    Boundary-Line's `country_region` layer, and country boundaries only. It is never
    used to clip the network — only to ask whether a basin touches the two countries.
    """
    return country_polygon(config.param("scope.countries_in_scope"))


def measure(basin_band: np.ndarray, transform, cell_m: float) -> pd.DataFrame:
    """Per basin: how many cells it holds, and how many lie in England or Wales.

    Done on the raster rather than on polygons. Polygonising 324 million cells to ask
    an area question would be an afternoon's computation in exchange for the same
    number.
    """
    def mask_for(geom) -> np.ndarray:
        return rasterize(
            [(geom, 1)],
            out_shape=basin_band.shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)

    ew_mask = mask_for(england_and_wales())
    # Scotland is measured, not inferred as "everything that is not England or Wales".
    # Boundary-Line's country polygons stop at Mean High Water, so a coastal basin's
    # estuary and foreshore lie outside *every* country — and taking the complement as
    # Scottish reported the Nedd, the Hull, the Great Ouse and the Ystwyth as
    # cross-border cases, which is nonsense. Ground in no country polygon is a real
    # third category and is reported as one.
    scotland_mask = mask_for(country_polygon(["Scotland"]))

    flat = basin_band.ravel()
    valid = flat > NO_BASIN
    cell_km2 = (cell_m * cell_m) / 1e6

    total = np.bincount(flat[valid])
    in_ew = np.bincount(flat[valid & ew_mask.ravel()], minlength=len(total))
    in_scot = np.bincount(flat[valid & scotland_mask.ravel()], minlength=len(total))

    basin_ids = np.flatnonzero(total)
    return pd.DataFrame(
        {
            "raster_id": basin_ids.astype(np.int64),
            "area_km2": total[basin_ids] * cell_km2,
            "england_wales_area_km2": in_ew[basin_ids] * cell_km2,
            "scotland_area_km2": in_scot[basin_ids] * cell_km2,
        }
    )


def decide_scope(frame: pd.DataFrame) -> pd.DataFrame:
    """A basin is in scope if any part of it lies in England or Wales.

    "Any part" is qualified by a minimum, because a boundary generalised at
    Boundary-Line's scale overlaps its neighbours by slivers, and a sliver is not a
    catchment. The threshold is in conf/params.yml so that changing it is a recorded
    change and not an edit to a function.
    """
    minimum = float(config.param("scope.min_overlap_area_km2"))
    frame = frame.copy()
    frame["in_scope"] = frame["england_wales_area_km2"] >= minimum
    frame["scope_reason"] = np.where(
        frame["in_scope"],
        (
            frame["england_wales_area_km2"].round(1).astype(str)
            + " km2 of "
            + frame["area_km2"].round(1).astype(str)
            + " km2 lies in England or Wales"
        ),
        np.where(
            frame["england_wales_area_km2"] > 0,
            (
                "only "
                + frame["england_wales_area_km2"].round(3).astype(str)
                + " km2 in England or Wales, below the "
                + str(minimum)
                + " km2 a generalised boundary can produce as a sliver"
            ),
            "no part in England or Wales",
        ),
    )
    return frame


def cross_border(frame: pd.DataFrame) -> pd.DataFrame:
    """In-scope basins with land outside England and Wales — the cases §9 asks to name.

    The Tweed and the Border Esk are the ones the plan names. Anything else appearing
    here is worth a look: it means the delineation put a catchment across the border
    that nobody expected to be there.
    """
    out = frame[frame["in_scope"]].copy()
    # Cross-border means ground in ANOTHER COUNTRY, not ground outside a country
    # polygon. The difference is the whole width of an estuary.
    out["outside_km2"] = out["area_km2"] - out["england_wales_area_km2"]
    out["tidal_or_offshore_km2"] = (
        out["outside_km2"] - out["scotland_area_km2"]
    ).clip(lower=0.0)
    out = out[out["scotland_area_km2"] > 1.0]
    return out.sort_values("scotland_area_km2", ascending=False)


def polygonise(basin_band: np.ndarray, transform, keep: np.ndarray) -> pd.DataFrame:
    """Polygons for the basins named in `keep`, and for no others.

    Geometry is wanted for the published deliverable, not for the arithmetic above, so
    only what is published is polygonised.
    """
    mask = np.isin(basin_band, keep)
    # rasterio's polygoniser will not take int64; a basin id is a small positive
    # integer, so int32 is ample and the cast is exact.
    band = basin_band.astype(np.int32)
    rows = []
    for geom, value in shapes(
        band, mask=mask, transform=transform, connectivity=4
    ):
        rows.append((int(value), shapely.geometry.shape(geom)))
    if not rows:
        return pd.DataFrame(columns=["raster_id", "geometry"])
    frame = pd.DataFrame(rows, columns=["raster_id", "geometry"])
    # A basin can arrive as several polygons where the coast interrupts it; keep it as
    # one feature rather than as several rows that no longer mean "a basin".
    merged = (
        frame.groupby("raster_id")["geometry"]
        .apply(lambda parts: shapely.union_all(list(parts)))
        .reset_index()
    )
    return merged


def sample_basin_at_nodes(basin_band: np.ndarray, dataset) -> pd.DataFrame:
    """Which basin each node stands in, or none where it stands on tidal water."""
    nodes = db.df("SELECT node_id, easting, northing, terminus FROM node ORDER BY node_id")
    rows, cols = raster.grid_indices(
        dataset, nodes["easting"].to_numpy(), nodes["northing"].to_numpy()
    )
    inside = (rows >= 0) & (rows < dataset.height) & (cols >= 0) & (cols < dataset.width)
    value = np.zeros(len(nodes), dtype=np.int64)
    value[inside] = basin_band[rows[inside], cols[inside]]
    nodes["raster_id"] = value
    return nodes


def basin_identity(raster_id: int, outlet_node: str | None) -> str:
    """A stable basin id.

    A basin is identified by its outlet, which is the thing that defines it (D-013).
    Where no outlet node could be found the raster id is used, prefixed so that nobody
    mistakes it for something stable across a re-delineation — and that case is a
    finding in its own right.
    """
    if outlet_node:
        return ids.basin(outlet_node)
    return f"rewt:basin-unanchored:{raster_id}"
