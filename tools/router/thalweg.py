"""Estuary channels by THALWEG, not by drainage.

WHY A SECOND METHOD. `seabed.py` runs drainage over the seabed and it works beautifully
where there is relief — the Channel palaeovalley falls straight out of it. On a flat estuary
floor it fragments, and the reason is structural rather than a tuning problem: after a
depression fill, D8 on a flat routes in the order the flood arrived, so accumulation never
concentrates into the one channel a navigator would use. Lowering the threshold produces more
threads, not a better channel.

So this asks a different question. Not *where does water collect* but **where is the
GROOVE** — the line of locally deepest water, which is what a thalweg is and what a pilot
follows up an estuary.

THE TEST, and it is deliberately simple. A cell is on a thalweg if, along at least one of the
four axes (E-W, N-S, and both diagonals), the seabed rises by more than `sill_m` on BOTH
sides within `k` cells. That is "it sits in a groove of at least this depth at this width".

MULTI-SCALE, because an estuary channel is not one width. A groove is looked for at several
half-widths at once (2, 4, 8 and 16 cells = 460 m to 3.7 km at 232 m), and a cell on any of
them counts. A single scale finds either the pixel noise or the whole basin, never the
channel.

WHAT IT IS NOT. Not a router, not connected to anything, no draught test. It is the second
half of an experiment Stephen asked for, and the point is to see whether it populates the
estuaries where drainage did not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402

CONFIG = {
    "cache": "tools/router/cache/seabed_fine.npz",   # z, dom, band from the fine run
    "masks": "tools/router/cache/sightline_masks.npz",
    "out": "docs/router/check/thalwegs.geojson",
    "summary": "docs/router/check/thalweg_summary.json",
    "band_km": 30.0,          # same coastal band as the fine drainage run
    "scales": [2, 4, 8, 16],  # half-width in cells; 232 m each
    "sill_m": 1.5,            # the flanks must rise this much on BOTH sides
    "min_run": 6,             # drop chains shorter than this many cells
    "coord_dp": 5,
}


def main(cfg: dict = CONFIG) -> None:
    c = np.load(cfg["cache"])
    z, dom, band = c["z"].astype("float32"), c["dom"], c["band"]
    m = np.load(cfg["masks"], allow_pickle=True)
    tr, crs = m["fine_transform"], str(m["crs"][0])
    px = float(m["fine_px"][0])
    h, w = z.shape
    dom = dom & (band <= cfg["band_km"])
    print(f"domain {int(dom.sum()):,} px at {px:.0f} m, within {cfg['band_km']:.0f} km of land")

    # THE TEST HAS TO PICK THE BOTTOM OF THE GROOVE, NOT THE WHOLE GROOVE. The first
    # version marked every cell whose flanks rose by the sill, which is the entire
    # depression: 2,906,848 px, 35% of the domain, a blob that the chain walk could not
    # trace because almost every cell had more than two neighbours. A thalweg is one cell
    # wide by definition, so a cell qualifies only where it is the MINIMUM along the axis
    # within +/- k — the lowest point of its own cross-section — and the flanks rise by
    # the sill on both sides.
    zz = np.where(dom, z, np.float32(1e6))
    groove = np.zeros((h, w), bool)
    axes = ((0, 1), (1, 0), (1, 1), (1, -1))
    for k in cfg["scales"]:
        for dy, dx in axes:
            foot = np.zeros((2 * k + 1, 2 * k + 1), bool)
            for t in range(-k, k + 1):
                foot[k + t * dy, k + t * dx] = True
            lo = ndimage.minimum_filter(zz, footprint=foot, mode="nearest")
            a = np.roll(zz, (k * dy, k * dx), (0, 1))
            b = np.roll(zz, (-k * dy, -k * dx), (0, 1))
            g = (zz <= lo) & (a - zz > cfg["sill_m"]) & (b - zz > cfg["sill_m"])
            groove |= g
        print(f"  scale {k:>2} cells ({k*px:>5.0f} m): cumulative thalweg "
              f"{int((groove & dom).sum()):,} px")
    groove &= dom

    # SKELETONISE, or the chain walk throws most of the network away. The detector marks
    # a band a few cells wide wherever several scales agree, and the walk only follows
    # cells with exactly two neighbours — so it stops at every thickening. Measured: 751,069
    # network cells produced 54,708 cells of output, losing 93%, with a median chain of
    # seven cells. Thinning to one cell wide first is what makes the trace faithful.
    from skimage.morphology import skeletonize
    lab, n = ndimage.label(groove, structure=np.ones((3, 3), int))
    sizes = np.bincount(lab.ravel())
    net = groove & ~np.isin(lab, np.nonzero(sizes < cfg["min_run"])[0])
    before = int(net.sum())
    net = skeletonize(net)
    lab, n2 = ndimage.label(net, structure=np.ones((3, 3), int))
    sizes = np.bincount(lab.ravel())
    net &= ~np.isin(lab, np.nonzero(sizes < cfg["min_run"])[0])
    print(f"  thalweg {int(groove.sum()):,} px -> {before:,} after dropping specks "
          f"-> {int(net.sum()):,} after skeletonising to one cell wide")

    # --- vectorise: walk each chain of adjacent thalweg cells ----------------------
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    D = cfg["coord_dp"]
    idx = {}
    ys, xs = np.nonzero(net)
    for i, (y, x) in enumerate(zip(ys, xs)):
        idx[(int(y), int(x))] = i
    nbrs = {}
    for (y, x) in idx:
        out = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    if (y + dy, x + dx) in idx:
                        out.append((y + dy, x + dx))
        nbrs[(y, x)] = out
    ends = [p for p, v in nbrs.items() if len(v) != 2]
    seen: set = set()
    feats = []

    def emit(path):
        if len(path) < cfg["min_run"]:
            return
        coords = []
        for (y, x) in path:
            X = tr[2] + (x + 0.5) * tr[0]
            Y = tr[5] + (y + 0.5) * tr[4]
            lo, la = back.transform(X, Y)
            coords.append([round(lo, D), round(la, D)])
        d = [float(-z[p]) for p in path]
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": coords},
                      "properties": {"cells": len(path),
                                     "km": round(len(path) * px / 1000, 2),
                                     "depth_min_m": round(min(d), 1),
                                     "depth_max_m": round(max(d), 1)}})

    for e in ends:
        for nb0 in nbrs[e]:
            if (e, nb0) in seen:
                continue
            path, prev, cur = [e], e, nb0
            seen.add((e, nb0))
            while True:
                path.append(cur)
                seen.add((prev, cur)); seen.add((cur, prev))
                nxt = [q for q in nbrs[cur] if q != prev]
                if len(nxt) != 1:
                    break
                prev, cur = cur, nxt[0]
            emit(path)
    print(f"  {len(feats):,} thalweg chains")

    props = {
        "generation": generation(),
        "what": "Estuary channels found as THALWEGS — the line of locally deepest water — "
                "rather than by drainage accumulation. A cell qualifies where the seabed "
                "rises by more than the sill on BOTH sides within k cells, along any of "
                "four axes, at any of four scales.",
        "why_not_drainage": "Drainage works where there is relief and fragments on a flat "
                            "estuary floor: after a depression fill, D8 on a flat routes in "
                            "the order the flood arrived, so accumulation never concentrates "
                            "into the channel a pilot would use. This asks where the groove "
                            "is instead of where water collects.",
        "sill_m": cfg["sill_m"], "scales_cells": cfg["scales"],
        "scales_m": [int(k * px) for k in cfg["scales"]],
        "resolution_m": px, "band_km": cfg["band_km"],
        "chains": len(feats), "cells": int(net.sum()),
        "not_a_router": "No connectivity guarantee, no draught test, nothing joined to the "
                        "river network or the hex grid. A picture, to be judged against the "
                        "drainage version.",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(cfg["out"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": feats},
        separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps(props, indent=1))
    print(f"wrote {cfg['out']} ({Path(cfg['out']).stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
