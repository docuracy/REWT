"""The medial axis of navigable water: skeletonise the non-land below high water.

STEPHEN'S BRIEF. The mesh is for open water; the first step is a RELIABLE method for
drawing routes out from the estuaries to meet it. Thalwegs were filed as not reliable
enough (PLAN.md 47) — a detector that fires on land, and no connectivity guarantee.

WHY THIS SHOULD BE RELIABLE WHERE THAT WAS NOT. It asks nothing of the bathymetry. The
subject is a SHAPE — the water area seaward of the high water line — and its skeleton is
the set of points equidistant from two or more banks: the middle of the channel, by
construction. Three properties fall out that the thalweg method could not offer:

  it CANNOT leave the water, because it is a subset of the water mask rather than a line
  fitted through it;
  it is CONNECTED wherever the water is connected, because thinning preserves topology;
  it runs UP an estuary to its head, because an estuary is a long thin shape and that is
  exactly what a medial axis describes well.

THE LAND IS OS high_water, NOT THE BATHYMETRY. `fine_sea` is EMODnet's sign change at
232 m and it does not resolve the Knapdale peninsulas or the Uists; using it as the bank
is what put thalwegs across dry land. Over GB the banks are the OS polygons, which is the
better source where we have it, and EMODnet elsewhere — the same asymmetry as the link
test, and stated for the same reason.

WHAT THIS IS NOT, yet: not joined to the mesh, not pruned to a route, no draught test.
It is the centreline, which is the thing that has to be reliable before anything is built
on it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio.features
import rasterio.transform
from pyproj import Transformer
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation                      # noqa: E402
from landtest import os_coastline, os_land_area    # noqa: E402

CONFIG = {
    "masks": "tools/router/cache/sightline_masks.npz",
    "cache": "tools/router/cache/seabed_fine.npz",
    "out": "docs/router/check/water_skeleton.geojson",
    "summary": "docs/router/check/water_skeleton_summary.json",
    "band_km": 30.0,        # the coastal band; open water is the mesh's job
    "min_spur_cells": 12,   # ~2.8 km; shorter twigs are shape noise, not channels
    "coord_dp": 5,
    # --- GB FINE MODE -------------------------------------------------------------
    # At 232 m, rasterising the OS banks CLOSES narrow estuaries: a cell whose centre
    # falls on land is land, and in the Tamar above the Narrows every centre does. In one
    # Plymouth window the water is ONE component without the OS cut and SEVENTEEN with
    # it. The banks are vector, so nothing forces 232 m — this rasterises them at 58 m
    # over GB, where a 200 m channel is three cells wide instead of sub-pixel.
    #
    # It needs no bathymetry at all: the subject is a shape, and the shape is the OS
    # coastline. That is also why it is GB-only — it is the source that exists.
    "gb_px": 58.0,
    "gb_band_km": 15.0,
    "gb_out": "docs/router/check/water_skeleton_gb.geojson",
    "gb_summary": "docs/router/check/water_skeleton_gb_summary.json",
    "gb_min_spur_cells": 40,     # ~2.3 km, the same twig length at four times the detail
}


def _vectorise(cfg, s_, tr, crs, px, out, summ, ncomp, water_px, gb=False, z=None):
    """Chains from a one-cell-wide skeleton. Shared by both modes so they cannot drift."""
    from pyproj import Transformer
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    D = cfg["coord_dp"]
    idx = {(int(y), int(x)) for y, x in zip(*np.nonzero(s_))}
    nbrs = {p: [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and (p[0] + dy, p[1] + dx) in idx] for p in idx}
    ends = [p for p, v in nbrs.items() if len(v) != 2]
    seen: set = set()
    feats = []
    a, bb, c_, d_, e_, f_ = tr.a, tr.b, tr.c, tr.d, tr.e, tr.f

    def emit(path):
        if len(path) < 3:
            return
        coords = []
        for (y, x) in path:
            X = c_ + (x + .5) * a + (y + .5) * bb
            Y = f_ + (x + .5) * d_ + (y + .5) * e_
            lo, la = back.transform(X, Y)
            coords.append([round(lo, D), round(la, D)])
        pr = {"cells": len(path), "km": round(len(path) * px / 1000, 2)}
        if z is not None:
            dep = [float(-z[p]) for p in path]
            pr["depth_min_m"] = round(min(dep), 1)
            pr["depth_median_m"] = round(float(np.median(dep)), 1)
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": coords},
                      "properties": pr})

    for e in ends:
        for nb0 in nbrs[e]:
            if (e, nb0) in seen:
                continue
            prev, cur, path = e, nb0, [e]
            seen.add((e, nb0))
            while True:
                path.append(cur)
                seen.add((prev, cur)); seen.add((cur, prev))
                nxt = [q for q in nbrs[cur] if q != prev]
                if len(nxt) != 1:
                    break
                prev, cur = cur, nxt[0]
            emit(path)
    print(f"  {len(feats):,} centreline chains")
    props = {
        "generation": generation(),
        "what": "The MEDIAL AXIS of navigable water — points equidistant from two or more "
                "banks, which is the middle of the channel by construction.",
        "banks": ("OS high_water alone, rasterised at %.0f m. No bathymetry is involved: "
                  "the subject is a shape." % px) if gb else
                 "OS high_water over GB, EMODnet's sea mask elsewhere.",
        "resolution_m": px, "components": int(ncomp), "chains": len(feats),
        "water_px": int(water_px),
        "gb_only": bool(gb),
        "why_this_resolution":
            "At 232 m, rasterising the OS banks CLOSES narrow estuaries — a cell whose "
            "centre falls on land is land, and above the Tamar Narrows every centre does. "
            "One Plymouth window is ONE water component without the OS cut and SEVENTEEN "
            "with it. The banks are vector, so the resolution is a choice rather than a "
            "constraint." if gb else "",
        "not_yet": "Not joined to the hex mesh, not pruned to a route, no draught test.",
        "attribution": "Contains OS data (c) Crown copyright and database right, OGL v3." +
                       ("" if gb else " Contains EMODnet Bathymetry data, CC BY 4.0."),
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(out).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": feats},
        separators=(",", ":")))
    Path(summ).write_text(json.dumps(props, indent=1))
    print(f"wrote {out} ({Path(out).stat().st_size/1e6:.1f} MB)")


def gb_fine(cfg: dict) -> None:
    """GB only, banks from OS alone, at 58 m."""
    from skimage.morphology import skeletonize
    import geopandas as gpd
    import shapely
    px = cfg["gb_px"]
    polys = os_land_area("EPSG:32630")   # polygonised rings, not the coastline
    b = shapely.total_bounds(polys)
    pad = cfg["gb_band_km"] * 1000.0 + 2000.0
    x0, y0, x1, y1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    w = int((x1 - x0) / px); h = int((y1 - y0) / px)
    tr = rasterio.transform.from_origin(x0, y1, px, px)
    print(f"GB grid {w:,} x {h:,} at {px:.0f} m = {w*h/1e6:,.0f}M cells")

    land = rasterio.features.rasterize(((p, 1) for p in polys), out_shape=(h, w),
                                       transform=tr, fill=0, dtype="uint8").astype(bool)
    print(f"  land {int(land.sum()):,} px ({100*land.mean():.1f}%)")

    # the band, decided at 232 m and upsampled: 15 km does not need 58 m to be decided
    k = int(round(232.0 / px))
    hh, ww = h // k * k, w // k * k
    coarse = land[:hh, :ww].reshape(hh // k, k, ww // k, k).any(axis=(1, 3))
    d = ndimage.distance_transform_edt(~coarse, sampling=(232.0, 232.0)) / 1000.0
    band = np.kron(d <= cfg["gb_band_km"], np.ones((k, k), bool))
    water = np.zeros((h, w), bool)
    water[:hh, :ww] = ~land[:hh, :ww] & band
    print(f"  water within {cfg['gb_band_km']:.0f} km of land: {int(water.sum()):,} px")

    skel = skeletonize(water)
    print(f"  skeleton {int(skel.sum()):,} px ({100*skel.sum()/water.sum():.2f}% of water)")
    s_ = skel.copy()
    nbr8 = np.ones((3, 3), np.uint8)
    for _ in range(cfg["gb_min_spur_cells"]):
        deg = ndimage.convolve(s_.astype(np.uint8), nbr8, mode="constant") - s_
        s_ &= ~(s_ & (deg <= 1))
    lab, _n = ndimage.label(s_, structure=np.ones((3, 3), int))
    sizes = np.bincount(lab.ravel())
    s_ &= ~np.isin(lab, np.nonzero(sizes < cfg["gb_min_spur_cells"])[0])
    ncomp = ndimage.label(s_, structure=np.ones((3, 3), int))[1]
    print(f"  after pruning: {int(s_.sum()):,} px, {ncomp:,} components")
    _vectorise(cfg, s_, tr, "EPSG:32630", px, cfg["gb_out"], cfg["gb_summary"],
               ncomp, int(water.sum()), gb=True)


def main(cfg: dict = CONFIG) -> None:
    from skimage.morphology import skeletonize
    m = np.load(cfg["masks"], allow_pickle=True)
    c = np.load(cfg["cache"])
    z, band = c["z"], c["band"]
    fine_sea = m["fine_sea"]
    ftr, crs = m["fine_transform"], str(m["crs"][0])
    px = float(m["fine_px"][0])
    fh, fw = fine_sea.shape
    tr = rasterio.transform.Affine(*[float(v) for v in ftr[:6]])

    # --- THE BANKS: OS high_water over GB, EMODnet elsewhere -----------------------
    polys = os_land_area(crs)          # AREA, not the coastline: see landtest.py
    os_land = rasterio.features.rasterize(
        ((p, 1) for p in polys), out_shape=(fh, fw), transform=tr,
        fill=0, dtype="uint8", all_touched=False).astype(bool)
    print(f"  rasterised {len(polys):,} OS land pieces: {int(os_land.sum()):,} px")

    water = fine_sea & ~os_land & (band <= cfg["band_km"])
    print(f"  water within {cfg['band_km']:.0f} km of land: {int(water.sum()):,} px "
          f"at {px:.0f} m")
    print(f"    of which EMODnet called sea but OS calls land: "
          f"{int((fine_sea & os_land & (band <= cfg['band_km'])).sum()):,} px removed")

    # --- THE MEDIAL AXIS -----------------------------------------------------------
    skel = skeletonize(water)
    print(f"  skeleton: {int(skel.sum()):,} px "
          f"({100*skel.sum()/water.sum():.2f}% of the water)")

    # prune twigs: iteratively remove endpoints, `min_spur_cells` times over
    nbr8 = np.ones((3, 3), np.uint8)
    s = skel.copy()
    for _ in range(cfg["min_spur_cells"]):
        deg = ndimage.convolve(s.astype(np.uint8), nbr8, mode="constant") - s
        s &= ~(s & (deg <= 1))
    lab, n = ndimage.label(s, structure=np.ones((3, 3), int))
    sizes = np.bincount(lab.ravel())
    s &= ~np.isin(lab, np.nonzero(sizes < cfg["min_spur_cells"])[0])
    print(f"  after pruning {cfg['min_spur_cells']}-cell twigs: {int(s.sum()):,} px, "
          f"{int(ndimage.label(s, structure=np.ones((3,3),int))[1]):,} components")

    # --- vectorise into chains ------------------------------------------------------
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    D = cfg["coord_dp"]
    idx = {(int(y), int(x)) for y, x in zip(*np.nonzero(s))}
    nbrs = {p: [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and (p[0] + dy, p[1] + dx) in idx] for p in idx}
    ends = [p for p, v in nbrs.items() if len(v) != 2]
    seen: set = set()
    feats = []

    def emit(path):
        if len(path) < 3:
            return
        coords, dep = [], []
        for (y, x) in path:
            X, Y = ftr[2] + (x + .5) * ftr[0], ftr[5] + (y + .5) * ftr[4]
            lo, la = back.transform(X, Y)
            coords.append([round(lo, D), round(la, D)])
            dep.append(float(-z[y, x]))
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": coords},
                      "properties": {"cells": len(path),
                                     "km": round(len(path) * px / 1000, 2),
                                     "depth_min_m": round(min(dep), 1),
                                     "depth_median_m": round(float(np.median(dep)), 1)}})

    for e in ends:
        for nb0 in nbrs[e]:
            if (e, nb0) in seen:
                continue
            prev, cur, path = e, nb0, [e]
            seen.add((e, nb0))
            while True:
                path.append(cur)
                seen.add((prev, cur)); seen.add((cur, prev))
                nxt = [q for q in nbrs[cur] if q != prev]
                if len(nxt) != 1:
                    break
                prev, cur = cur, nxt[0]
            emit(path)
    print(f"  {len(feats):,} centreline chains")

    props = {
        "generation": generation(),
        "what": "The MEDIAL AXIS of navigable water — the set of points equidistant from "
                "two or more banks, which is the middle of the channel by construction.",
        "banks": "OS high_water polygons over GB, EMODnet's sea mask elsewhere. Not the "
                 "bathymetry: EMODnet at 232 m does not resolve the Knapdale peninsulas or "
                 "the Uists, and using it as the bank is what put the thalweg method across "
                 "dry land.",
        "why_reliable": "It cannot leave the water, because it is a SUBSET of the water mask "
                        "rather than a line fitted through it. It is connected wherever the "
                        "water is connected, because thinning preserves topology. And it "
                        "runs up an estuary to its head, because an estuary is a long thin "
                        "shape and that is what a medial axis describes well.",
        "band_km": cfg["band_km"],
        "min_spur_cells": cfg["min_spur_cells"],
        "resolution_m": px,
        "chains": len(feats),
        "not_yet": "Not joined to the hex mesh, not pruned to a route, no draught test. "
                   "This is the centreline, which has to be reliable before anything is "
                   "built on it.",
        "attribution": "Contains OS data (c) Crown copyright and database right, OGL v3. "
                       "Contains EMODnet Bathymetry data, CC BY 4.0.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(cfg["out"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": feats},
        separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps(props, indent=1))
    print(f"wrote {cfg['out']} ({Path(cfg['out']).stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    if "--gb" in sys.argv:
        gb_fine(CONFIG)
    else:
        main()
