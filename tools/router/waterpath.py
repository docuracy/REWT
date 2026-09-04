"""Shortest path between two points THROUGH WATER, on the 232 m sea mask.

One definition, imported by `detour.py`, which measures what a refused link costs, and by
`grid2.py`, which refines the grid where that cost is worth removing. The two must agree
about what "the water goes straight past it" means, or the refinement will not be aimed at
the pairs the measurement selected — the same reason `landtest.py` and `adjacency.py` exist.

The search runs in a WINDOW around the two points. That bounds the cost, and it bounds the
claim: a pair whose way round is longer than the window returns infinity and is reported as
separated, so the separated count is an upper bound rather than a fact.
"""
from __future__ import annotations

import math

import numpy as np
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

PAD_PX = 90          # ~21 km of margin at 232 m
EARTH_R = 6371000.0


def great_circle_m(a, b) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    return EARTH_R * math.acos(min(1.0, math.sin(p1) * math.sin(p2)
                                   + math.cos(p1) * math.cos(p2) * math.cos(dl)))


def water_path_test(sea, transform, crs, pad_px: int = PAD_PX):
    """Return `path(a, b)` -> (distance_m, [(row, col), ...]) for (lat, lon) pairs.

    The pixel list is the corridor the water actually uses, which is what a refinement
    has to follow: subdividing only the two end cells does not help if the channel runs
    through a third.
    """
    ftr = transform
    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    fh, fw = sea.shape
    px = abs(float(ftr[0]))

    def rc(la, lo):
        x, y = fwd.transform(lo, la)
        return int((y - ftr[5]) / ftr[4]), int((x - ftr[2]) / ftr[0])

    def path(a, b):
        r1, c1 = rc(*a)
        r2, c2 = rc(*b)
        r0, rN = max(0, min(r1, r2) - pad_px), min(fh, max(r1, r2) + pad_px + 1)
        c0, cN = max(0, min(c1, c2) - pad_px), min(fw, max(c1, c2) + pad_px + 1)
        w = sea[r0:rN, c0:cN]
        h, wd = w.shape
        ys, xs = np.nonzero(w)
        if len(ys) == 0:
            return math.inf, []
        ids = -np.ones((h, wd), np.int32)
        ids[ys, xs] = np.arange(len(ys))
        rows, cols, vals = [], [], []
        for dy, dx, cost in ((0, 1, px), (1, 0, px),
                             (1, 1, px * 2 ** .5), (1, -1, px * 2 ** .5)):
            y2, x2 = ys + dy, xs + dx
            ok = (y2 >= 0) & (y2 < h) & (x2 >= 0) & (x2 < wd)
            ok &= w[np.clip(y2, 0, h - 1), np.clip(x2, 0, wd - 1)]
            rows += ids[ys[ok], xs[ok]].tolist()
            cols += ids[y2[ok], x2[ok]].tolist()
            vals += [cost] * int(ok.sum())
        n = len(ys)
        gm = coo_matrix((vals, (rows, cols)), shape=(n, n))
        gm = gm + gm.T
        s = ids[np.clip(r1 - r0, 0, h - 1), np.clip(c1 - c0, 0, wd - 1)]
        t = ids[np.clip(r2 - r0, 0, h - 1), np.clip(c2 - c0, 0, wd - 1)]
        if s < 0 or t < 0:
            return math.inf, []
        d, pred = dijkstra(gm, indices=int(s), return_predecessors=True)
        if not np.isfinite(d[int(t)]):
            return math.inf, []
        out, u = [], int(t)
        while u >= 0:
            out.append((int(ys[u]) + r0, int(xs[u]) + c0))
            u = int(pred[u])
        return float(d[int(t)]), out[::-1]

    return path
