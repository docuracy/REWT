"""Rasters: the Terrain 50 mosaic, and sampling it without lying about what it says.

Two rules from PLAN.md §5 and D-007 are enforced here rather than remembered:

* **Keep the conditioned and unconditioned surfaces distinct and distinctly named.**
  Burning the network into the DEM is correct for delineating catchments and useless
  for checking direction, because a burned DEM has the network's own direction stamped
  into it. `open_unconditioned()` and `open_conditioned()` are separate functions, and
  the sampler refuses a raster whose name says it was conditioned.
* **Sample a window, not a point.** A single cell lands on a bank, a bridge deck or a
  building. Take a low percentile of a box, and treat a fall of a few centimetres as
  no answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

from . import config, paths

UNCONDITIONED = paths.INTERIM / "terrain50_unconditioned.tif"
BURNED = paths.INTERIM / "terrain50_burned_filled.tif"
CONDITIONED = paths.INTERIM / "terrain50_conditioned_breached.tif"
D8_POINTER = paths.INTERIM / "terrain50_d8_pointer.tif"
FLOW_ACC = paths.INTERIM / "terrain50_flow_accumulation.tif"
BASINS = paths.INTERIM / "terrain50_basins.tif"

_CONDITIONED_MARKERS = ("burned", "conditioned", "breached", "filled")


class ConditioningError(RuntimeError):
    """Asked to read elevation for a direction check from a conditioned surface."""


def open_unconditioned():
    """The raw surface. The only one a direction check may look at."""
    if not UNCONDITIONED.exists():
        raise FileNotFoundError(
            f"{paths.rel(UNCONDITIONED)} does not exist; run the terrain stage."
        )
    return rasterio.open(UNCONDITIONED)


def open_conditioned():
    """The breached surface. For delineating catchments, and for nothing else."""
    if not CONDITIONED.exists():
        raise FileNotFoundError(
            f"{paths.rel(CONDITIONED)} does not exist; run the terrain stage."
        )
    return rasterio.open(CONDITIONED)


def assert_unconditioned(path: Path) -> None:
    """Refuse a raster whose own name says the network has been stamped into it."""
    name = Path(path).name.lower()
    if any(m in name for m in _CONDITIONED_MARKERS):
        raise ConditioningError(
            f"{Path(path).name} is a conditioned surface. Checking flow direction "
            "against it proves nothing: the network's own direction was burned in "
            "(PLAN.md §5, D-007). Sample the unconditioned surface."
        )


@dataclass
class Sample:
    """One elevation reading, and whether it is worth anything."""

    value: float | None
    cells: int
    nodata_cells: int
    source: str

    @property
    def answered(self) -> bool:
        return self.value is not None


def sample_window(
    dataset,
    easting: float,
    northing: float,
    window_m: float | None = None,
    percentile: float | None = None,
    source: str = "os_terrain_50",
) -> Sample:
    """A low percentile of a box around a point, not the cell it lands in.

    Returns a Sample whose `value` is None where the box is entirely nodata — which,
    over the sea, is itself confirmation that the point is at tidal water rather than
    a missing reading (§6). Count that case; do not drop it silently.
    """
    p = config.params()
    win = window_m if window_m is not None else p("lidar.window_m")
    pct = percentile if percentile is not None else p("lidar.percentile")
    half = win / 2.0

    try:
        window = from_bounds(
            easting - half, northing - half, easting + half, northing + half,
            transform=dataset.transform,
        )
        data = dataset.read(1, window=window, boundless=True, fill_value=np.nan)
    except (ValueError, rasterio.errors.RasterioError):
        return Sample(None, 0, 0, source)

    arr = np.asarray(data, dtype=float).ravel()
    nodata = dataset.nodata
    invalid = ~np.isfinite(arr)
    if nodata is not None:
        invalid |= np.isclose(arr, nodata)
    valid = arr[~invalid]
    if valid.size == 0:
        return Sample(None, arr.size, int(invalid.sum()), source)
    return Sample(float(np.percentile(valid, pct)), arr.size, int(invalid.sum()), source)


def sample_points(dataset, eastings: np.ndarray, northings: np.ndarray) -> np.ndarray:
    """Point elevations for many places at once, nodata as NaN.

    Used where the question is national and the answer only has to rank things — the
    §5 screen and the §6 component-root test. Where a single reading has to decide
    something, use `sample_window`.
    """
    rows, cols = rasterio.transform.rowcol(
        dataset.transform, eastings, northings, op=np.floor
    )
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    out = np.full(len(eastings), np.nan)
    inside = (rows >= 0) & (rows < dataset.height) & (cols >= 0) & (cols < dataset.width)
    if not inside.any():
        return out
    band = dataset.read(1)
    values = band[rows[inside], cols[inside]].astype(float)
    nodata = dataset.nodata
    if nodata is not None:
        values[np.isclose(values, nodata)] = np.nan
    out[inside] = values
    return out


def grid_indices(dataset, eastings: np.ndarray, northings: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = rasterio.transform.rowcol(
        dataset.transform, eastings, northings, op=np.floor
    )
    return np.asarray(rows), np.asarray(cols)
