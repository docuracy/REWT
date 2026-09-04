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

import numpy as np
from pyproj import Transformer

SAMPLES = 12          # points tested along each link, endpoints excluded


def land_crossing_test(masks_npz: str, samples: int = SAMPLES):
    """Return `crosses(a, b)` for (lat, lon) pairs. Off-mask counts as land."""
    mk = np.load(masks_npz, allow_pickle=True)
    fine, ftr = mk["fine_sea"], mk["fine_transform"]
    fwd = Transformer.from_crs(4326, str(mk["crs"][0]), always_xy=True)
    fh, fw = fine.shape
    fr = np.arange(1, samples) / samples

    def crosses(a, b) -> bool:
        la = a[0] + (b[0] - a[0]) * fr
        lo = a[1] + (b[1] - a[1]) * fr
        x, y = fwd.transform(lo, la)
        c = ((np.asarray(x) - ftr[2]) / ftr[0]).astype(int)
        r = ((np.asarray(y) - ftr[5]) / ftr[4]).astype(int)
        ok = (r >= 0) & (r < fh) & (c >= 0) & (c < fw)
        return bool((~fine[np.clip(r, 0, fh - 1), np.clip(c, 0, fw - 1)] | ~ok).any())

    return crosses
