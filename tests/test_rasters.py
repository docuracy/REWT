"""Derived rasters must contain data.

This exists because of a specific silent failure, found while the terrain stage was
being written: **WhiteboxTools' `FillBurn` returns 0 and writes an output that is
entirely NaN and 3.3e38** when the stream vector it is handed extends beyond the
raster's extent. 185 million cells, not one valid value, and nothing in the return
code or on stderr said so. A stage that checks only the return code reports success
and every basin downstream of it is garbage.

So the check is on the artefact and not on the tool: **at least one finite value, in
a range the surface could plausibly hold.** It would have caught that failure in a
second, and it will catch the next tool that fails this way.

Nothing here writes to `data/interim/`. A raster that has not been produced yet is a
named skip.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rewt import paths, raster


pytestmark = pytest.mark.interim

# Great Britain's terrain, generously: Ben Nevis is 1,345 m and the lowest land is
# about -4 m in the Fens. A surface conditioned for hydrology may sit a little below
# that where depressions have been breached.
ELEVATION_MIN = -200.0
ELEVATION_MAX = 2_000.0

# (name, path, plausible range) — a d8 pointer and a basin grid are codes and labels,
# not metres, so each says what it should hold.
SURFACES = [
    ("unconditioned", raster.UNCONDITIONED, (ELEVATION_MIN, ELEVATION_MAX)),
    ("burned and filled", raster.BURNED, (ELEVATION_MIN, ELEVATION_MAX)),
    ("conditioned (breached)", raster.CONDITIONED, (ELEVATION_MIN, ELEVATION_MAX)),
    ("d8 pointer", raster.D8_POINTER, (0.0, 255.0)),
    ("flow accumulation", raster.FLOW_ACC, (0.0, float("inf"))),
    ("basins", raster.BASINS, (0.0, float("inf"))),
]


def _sample(path: Path, max_cells: int = 4_000_000):
    """A decimated read of the whole grid, and the dataset's own nodata value.

    Decimated rather than windowed on purpose: the FillBurn failure was uniform
    across the raster, but a failure that ruins only part of one would hide from a
    single window in the middle.
    """
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(path) as ds:
        scale = max(1, int((ds.width * ds.height / max_cells) ** 0.5))
        out_shape = (1, max(1, ds.height // scale), max(1, ds.width // scale))
        arr = ds.read(
            out_shape=out_shape, resampling=Resampling.nearest, masked=False
        ).astype("float64")[0]
        return arr, ds.nodata, ds.crs, ds.width, ds.height


# A burn incises the surface, and it does so wherever the stream vector runs —
# including over cells that hold nodata, which come out a little above or below the
# declared value rather than equal to it. Measured on the burned surface: every
# out-of-range cell sat within 5% of -9999, offset by -15 m to +224 m. Those are
# nodata that has been nudged, not elevations, so the tolerance is wide on purpose.
#
# It is worth knowing that these cells exist: a stream burnt over nodata is a length
# of watercourse with no terrain under it, which is itself a finding.
_NODATA_RTOL = 0.05


def _valid(arr: np.ndarray, nodata) -> np.ndarray:
    keep = np.isfinite(arr)
    if nodata is not None:
        keep &= ~np.isclose(arr, nodata, rtol=_NODATA_RTOL)
    # WhiteboxTools writes this sentinel where it has nothing, whatever the header
    # declares — which is the whole point of this module.
    keep &= np.abs(arr) < 1e38
    return arr[keep]


@pytest.mark.parametrize(
    "label,path,bounds", SURFACES, ids=[s[1].name for s in SURFACES]
)
def test_a_derived_raster_holds_at_least_one_valid_value(label, path, bounds):
    """The test that would have caught FillBurn returning success over nothing."""
    if not path.exists():
        pytest.skip(
            f"{paths.rel(path)} has not been produced yet — run the terrain stage. "
            f"({label})"
        )
    arr, nodata, _, width, height = _sample(path)
    valid = _valid(arr, nodata)
    assert valid.size, (
        f"{paths.rel(path)} ({label}) contains no valid value at all: "
        f"{width:,}x{height:,} cells, every one of them nodata, NaN or a "
        "±3.4e38 sentinel. A hydrology tool can return success and write exactly "
        "this — check the extent of what was handed to it before the algorithm."
    )
    low, high = bounds
    out_of_range = valid[(valid < low) | (valid > high)]
    share = 1.0 - out_of_range.size / valid.size
    # Not zero tolerance: a hydrology tool leaves a scatter of cells at the edges of
    # its own nodata, and failing a national build on fourteen of them would teach
    # everyone to stop reading this test. A corrupt surface does not scrape past
    # here — the ones this file was written for scored 0.0%.
    assert share > 0.99, (
        f"{paths.rel(path)} ({label}) holds only {share:.2%} of its {valid.size:,} "
        f"valid cells inside [{low}, {high}]. {out_of_range.size:,} are outside it, "
        f"running from {out_of_range.min():.4g} to {out_of_range.max():.4g}. "
        "A surface that is finite everywhere and meaningless everywhere is what a "
        "hydrology tool writes when it returns success over an input it could not "
        "decode."
    )


@pytest.mark.parametrize(
    "label,path,bounds", SURFACES, ids=[s[1].name for s in SURFACES]
)
def test_a_derived_raster_is_mostly_not_nodata(label, path, bounds):
    """One valid cell is not enough to call a national surface built.

    Great Britain is roughly a third of its own bounding box, so a national grid
    that is more than about 90% empty is not a coastline — it is a failure that
    happened to leave a corner behind.
    """
    if not path.exists():
        pytest.skip(f"{paths.rel(path)} has not been produced yet ({label})")
    arr, nodata, _, _, _ = _sample(path)
    share = _valid(arr, nodata).size / arr.size
    assert share > 0.10, (
        f"{paths.rel(path)} ({label}) is {1 - share:.1%} nodata. A national surface "
        "this empty is a failed write, not a coastline."
    )


@pytest.mark.parametrize(
    "label,path,bounds", SURFACES, ids=[s[1].name for s in SURFACES]
)
def test_a_derived_raster_is_in_the_working_crs(label, path, bounds):
    """EPSG:27700 throughout (AGENTS.md)."""
    if not path.exists():
        pytest.skip(f"{paths.rel(path)} has not been produced yet ({label})")
    _, _, crs, _, _ = _sample(path)
    assert crs is not None, f"{paths.rel(path)} declares no CRS"
    assert crs.to_epsg() == 27700, (
        f"{paths.rel(path)} is EPSG:{crs.to_epsg()}, not 27700"
    )


def test_the_conditioned_and_unconditioned_surfaces_are_distinct_files():
    """*Keep the two rasters distinct and distinctly named* (§5, D-007).

    A burned DEM has the network's own direction stamped into it, so checking
    direction against it proves nothing.
    """
    names = {raster.UNCONDITIONED, raster.BURNED, raster.CONDITIONED}
    assert len(names) == 3, "the terrain surfaces are not distinct files"


def test_a_conditioned_surface_is_refused_for_a_direction_check():
    """The guard, exercised — not merely present."""
    for path in (raster.BURNED, raster.CONDITIONED):
        with pytest.raises(raster.ConditioningError):
            raster.assert_unconditioned(path)
    raster.assert_unconditioned(raster.UNCONDITIONED)      # must not raise
