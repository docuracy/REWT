"""Does the straight line between two cell centres cross land?

ONE definition, imported by both `grid2.py` and `edges.py`. They used to disagree:
grid2 decided what was connected with bare `grid_disk`, edges then removed the links
that cross land, and the 220 cells whose every link crossed land survived the first
and were isolated by the second. A cell with no usable link is not a routing cell, so
the two passes have to ask the same question.

The mask is `fine_sea` at 232 m from the sightline run — the same surface the traces
walk, so a link is rejected on the same evidence a path is refused.
"""
from __future__ import annotations

import math

import numpy as np
from pyproj import Transformer

# NEVER SAMPLE COARSER THAN THE MASK. This took a fixed 12 samples along every link,
# which is 517 m apart on a 6.2 km res-6 chord while the mask pixel is 232 m — so the test
# stepped clean over any island narrower than its own stride. Stephen found three such
# links crossing the Uists, and there was nothing wrong with the rule, only with how often
# it looked. The sample count is now derived from the line's own length: one sample every
# HALF pixel, which cannot miss a feature the mask is able to represent at all.
# WALK PIXELS, NOT DISTANCE. First this took a fixed 12 samples per link — 517 m apart on
# a 6.2 km chord against a 232 m pixel — so it stepped clean over any island narrower than
# its own stride, and Stephen found three such links crossing the Uists. Sampling every
# half pixel along the LINE fixed those and still left 78 links grazing a land pixel,
# because half a pixel along a diagonal is less than half a pixel along either axis.
# The count is now taken from the DOMINANT AXIS in pixel units, three samples per pixel,
# which cannot skip a pixel the segment passes through. There was never anything wrong
# with the rule, only with how often it looked.
#
# EIGHT, NOT THREE, and the last step is asymptotic rather than exact. Three per pixel left
# 7 links of 47,378 grazing a single 232 m pixel at a corner — real, visible on the map, and
# the tail of a class that no finite sampling closes: a line can always clip a corner
# between two samples. Eight per pixel costs about a minute on a full run and takes the
# residual below the mask's own fidelity, which is one 232 m pixel. Anything still missed
# is smaller than the coastline this mask is able to describe.
SAMPLES_PER_PIXEL = 8.0
MIN_SAMPLES = 8


def land_crossing_test(masks_npz: str, samples_per_pixel: float = SAMPLES_PER_PIXEL):
    """Return `crosses(a, b)` for (lat, lon) pairs. Off-mask counts as land."""
    mk = np.load(masks_npz, allow_pickle=True)
    fine, ftr = mk["fine_sea"], mk["fine_transform"]
    fwd = Transformer.from_crs(4326, str(mk["crs"][0]), always_xy=True)
    fh, fw = fine.shape
    x0, y0, sx, sy = float(ftr[2]), float(ftr[5]), float(ftr[0]), float(ftr[4])

    def crosses(a, b) -> bool:
        (px1, py1), (px2, py2) = fwd.transform(a[1], a[0]), fwd.transform(b[1], b[0])
        c1, r1 = (px1 - x0) / sx, (py1 - y0) / sy
        c2, r2 = (px2 - x0) / sx, (py2 - y0) / sy
        n = max(MIN_SAMPLES,
                int(max(abs(c2 - c1), abs(r2 - r1)) * samples_per_pixel) + 2)
        t = np.linspace(0.0, 1.0, n)
        c = np.floor(c1 + (c2 - c1) * t).astype(int)
        r = np.floor(r1 + (r2 - r1) * t).astype(int)
        ok = (r >= 0) & (r < fh) & (c >= 0) & (c < fw)
        return bool((~fine[np.clip(r, 0, fh - 1), np.clip(c, 0, fw - 1)] | ~ok).any())

    return crosses
