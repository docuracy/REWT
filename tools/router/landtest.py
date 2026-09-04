"""Does the straight line between two cell centres cross land?

ONE definition, imported by `grid2.py`, `edges.py`, `export_edges.py` and
`export_coarse.py`. They used to disagree: grid2 decided what was connected with bare
`grid_disk`, edges then removed the links that cross land, and the 220 cells whose every
link crossed land survived the first and were isolated by the second.

EXACT, VIA SHAPELY. This sampled points along the line against the raster mask instead,
and the sampling rate was a parameter I kept having to raise: 12 points per link stepped
over islands narrower than its own 517 m stride and drew three links through the Uists;
half a pixel along the line still let 78 links graze a land pixel; eight per pixel still
let SIX REAL CROSSINGS through, which I had written up as an asymptotic residual "below
the mask's own fidelity". It was not. Stephen asked why this was not simply a geometric
intersection test, and the answer was that the land definition lives in a raster and I had
stayed in raster space out of habit. That is a reason to polygonise the mask ONCE, not a
reason to sample it a million times.

The mask is still the authority — these polygons ARE `fine_sea` at 232 m, so the link test
agrees with the traces, the node-in-water rule and the sea-connectivity fill, all of which
read the same surface. Substituting a vector coastline from another source would have made
this test disagree with everything else in the pipeline.

SUBDIVISION IS WHAT MAKES IT FAST. Whole-polygon `intersects` against the European mainland
took 133 s for 47,372 links, because a handful of rings hold most of the 192,120 vertices.
Clipped to a 50 km grid the largest piece has 1,468 vertices and the same query takes
0.14 s — 950x faster, and 14x faster than the sampler it replaces, while being exact.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import rasterio.features
import rasterio.transform
import shapely
from pyproj import Transformer
from shapely import LineString, STRtree
from shapely.geometry import box, shape

TILE_M = 50_000.0        # subdivision grid; see the note above
SPLIT_ABOVE = 200        # vertices, beyond which a polygon is worth clipping


def land_polygons(masks_npz: str):
    """The land side of the mask, as polygons clipped small enough to query quickly."""
    mk = np.load(masks_npz, allow_pickle=True)
    fine, ftr = mk["fine_sea"], mk["fine_transform"]
    tr = rasterio.transform.Affine(*[float(v) for v in ftr[:6]])
    land = (~fine).astype(np.uint8)
    polys = [shape(g) for g, v in
             rasterio.features.shapes(land, mask=land.astype(bool), transform=tr) if v == 1]

    xmin, ymin, xmax, ymax = shapely.total_bounds(polys)
    tiles = [box(x, y, x + TILE_M, y + TILE_M)
             for x in np.arange(xmin, xmax, TILE_M)
             for y in np.arange(ymin, ymax, TILE_M)]
    ttree = STRtree(tiles)
    pieces = []
    for p in polys:
        if shapely.get_num_coordinates(p) < SPLIT_ABOVE:
            pieces.append(p)
            continue
        for i in ttree.query(p):
            q = shapely.intersection(p, tiles[i])
            if not q.is_empty:
                pieces.append(q)
    return pieces, str(mk["crs"][0])


def land_crossing_test(masks_npz: str):
    """Return `crosses(a, b)` for (lat, lon) pairs. Off the mask counts as land."""
    pieces, crs = land_polygons(masks_npz)
    tree = STRtree(pieces)
    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    hull = shapely.box(*shapely.total_bounds(pieces))

    # cells repeat about six times each across the adjacency walk, so projecting once per
    # DISTINCT centre rather than once per link is most of the per-call cost removed
    @lru_cache(maxsize=1 << 20)
    def proj(la: float, lo: float):
        return fwd.transform(lo, la)

    def crosses(a, b) -> bool:
        p, q = proj(float(a[0]), float(a[1])), proj(float(b[0]), float(b[1]))
        ln = LineString([p, q])
        if not hull.contains(ln):
            return True                      # off the mask: not known to be water
        return len(tree.query(ln, predicate="intersects")) > 0

    return crosses
