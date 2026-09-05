"""An inverted sub-sea stream network: drainage run over the seabed instead of the land.

STEPHEN'S IDEA, and it is a genuinely different way of getting a sea route network. Instead
of tiling the sea with hexagons and asking which pairs are adjacent, treat the SEABED AS A
TERRAIN and run the same drainage analysis a hydrologist runs on land. Water on the seabed
flows to the deepest place, so flow accumulation traces the submarine valleys — and many of
those valleys ARE drowned river channels, so the network it finds is the one a vessel with a
draught would care about.

"Inverted" because the sense is upside down relative to a land network: a land stream network
converges toward the sea, and this one converges AWAY from the coast, out into deep water.
Its headwaters are at the shore.

BOUNDED ON BOTH SIDES, as Stephen specified.
  landward   the OS high_water line (its polygons over GB), so the network stops where the
             administrative coast says it does rather than where a 930 m bathymetry pixel
             changes sign
  seaward    the land-visibility cells from the sightline stage — the network exists only
             where a navigator could see land, which is the same bound the hex grid uses

WHAT IT IS NOT, yet. This is a picture, not a router. No depth threshold for draught, no
weights, no connection to the river network, and it has not been compared against the hex
mesh for coverage. It is here so Stephen can look at the shape and say whether the idea is
worth building out.
"""
from __future__ import annotations

import heapq
import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation                      # noqa: E402
from landtest import os_land_polygons                  # noqa: E402

CONFIG = {
    "masks": "tools/router/cache/sightline_masks.npz",
    "vrt": "tools/router/cache/emodnet.vrt",
    "out": "docs/router/data/seabed_channels.geojson",
    "summary": "docs/router/data/seabed_summary.json",
    "min_drainage_km2": 250.0,   # chosen from the distribution, see main()
    "coord_dp": 5,
    # --- FINE MODE, for the estuaries -------------------------------------------
    # At 930 m an estuary is two or three pixels wide and the network cannot enter it.
    # Fine mode re-runs the whole analysis at the mask's own 232 m over a COASTAL BAND:
    # the offshore trunks are already had from the coarse run, and this is where the
    # resolution actually buys something.
    # THE FINE LAYER GOES IN THE GITIGNORED CHECK DIRECTORY, not in data/. It is an
    # exploration Stephen asked to look at, not a published artefact, and at the
    # threshold the estuaries need it is 20 MB. Committing that before the approach has
    # been judged would put the cost of an idea into the repository ahead of the decision
    # about whether to keep it. It moves to data/ if and when the method is adopted.
    "fine_out": "docs/router/check/seabed_channels_fine.geojson",
    "fine_summary": "docs/router/check/seabed_fine_summary.json",
    "fine_band_km": 30.0,        # how far out the fine run goes
    "fine_always_km": 8.0,       # within this, include water the coarse mask calls unseen,
                                 # because an estuary can be land at 930 m
    "fine_min_drainage_km2": 20.0,
    "fine_cache": "tools/router/cache/seabed_fine.npz",
    "fine_inshore_km": 10.0,
    "fine_min_inshore_km2": 3.0,
}


def fine_inputs(cfg: dict):
    """Elevations and domain at the mask's own 232 m, over a coastal band."""
    import rasterio
    from rasterio.warp import Resampling, reproject
    from rasterio.transform import Affine
    from scipy import ndimage
    m = np.load(cfg["masks"], allow_pickle=True)
    ftr, crs = m["fine_transform"], str(m["crs"][0])
    fine_sea = m["fine_sea"]
    fh, fw = fine_sea.shape
    fpx = float(m["fine_px"][0])

    src = rasterio.open(cfg["vrt"])
    z = np.full((fh, fw), np.nan, "float32")
    reproject(source=rasterio.band(src, 1), destination=z,
              dst_transform=Affine(*[float(v) for v in ftr[:6]]), dst_crs=crs,
              resampling=Resampling.bilinear, src_nodata=-9999.0, dst_nodata=np.nan)
    print(f"  reprojected bathymetry to {z.shape} at {fpx:.0f} m")

    # distance to land, measured on the COARSE grid because a 30 km band does not need
    # 232 m to be decided, and the fine distance transform is 74M px
    tr = m["transform"]
    cpx = float(m["px"][0])
    dl = ndimage.distance_transform_edt(~m["land"], sampling=(cpx, cpx)) / 1000.0
    ys, xs = np.mgrid[0:fh, 0:fw]
    X = ftr[2] + (xs + 0.5) * ftr[0]
    Y = ftr[5] + (ys + 0.5) * ftr[4]
    col = np.clip(((X - tr[2]) / tr[0]).astype(np.int32), 0, m["land"].shape[1] - 1)
    row = np.clip(((Y - tr[5]) / tr[4]).astype(np.int32), 0, m["land"].shape[0] - 1)
    del X, Y, xs, ys
    band = dl[row, col]
    vis = m["visible"][row, col]
    del row, col
    dom = fine_sea & np.isfinite(z) & (band <= cfg["fine_band_km"]) \
        & (vis | (band <= cfg["fine_always_km"]))
    print(f"  fine domain: {int(dom.sum()):,} px within {cfg['fine_band_km']:.0f} km of "
          f"land ({100*dom.sum()/fine_sea.sum():.1f}% of all sea px)")
    return z, dom, ftr, crs, fpx, band


def main(cfg: dict = CONFIG, fine: bool = False) -> None:
    if fine and Path(cfg["fine_cache"]).exists() and "--rethreshold" in sys.argv:
        m = np.load(cfg["masks"], allow_pickle=True)
        c = np.load(cfg["fine_cache"])
        area, dom, band, steep, z = (c["area"], c["dom"], c["band"], c["steep"], c["z"])
        tr, crs, px = m["fine_transform"], str(m["crs"][0]), float(m["fine_px"][0])
        h, w = z.shape
        print(f"re-thresholding from cache: {int(dom.sum()):,} px at {px:.0f} m")
        return _emit(cfg, True, area, dom, band, steep, z, tr, crs, px)
    if fine:
        z, dom, tr, crs, px, band = fine_inputs(cfg)
        h, w = z.shape
        thr_default = cfg["fine_min_drainage_km2"]
        out, summ = cfg["fine_out"], cfg["fine_summary"]
    else:
        m = np.load(cfg["masks"], allow_pickle=True)
        z = m["elev"].astype("float32")
        tr, crs = m["transform"], str(m["crs"][0])
        px = float(m["px"][0])
        h, w = z.shape
        dom = m["sea"] & m["visible"]
        thr_default = cfg["min_drainage_km2"]
        out, summ = cfg["out"], cfg["summary"]
        print(f"domain: {int(dom.sum()):,} px of sighted sea at {px:.0f} m")

    # --- LANDWARD BOUND: the OS high water line, not the bathymetry sign change ----
    ys, xs = np.nonzero(dom)
    X = tr[2] + (xs + 0.5) * tr[0]
    Y = tr[5] + (ys + 0.5) * tr[4]
    from shapely import STRtree, points
    tree = STRtree(os_land_polygons(crs))
    inside = tree.query(points(np.column_stack([X, Y])), predicate="intersects")[0]
    if len(inside):
        dom[ys[inside], xs[inside]] = False
        print(f"  dropped {len(set(inside.tolist())):,} px landward of OS high_water")

    # --- FILL THE PITS, draining to the edge of the domain -------------------------
    # Without this, flow stops in every closed hollow on the seabed and accumulation
    # never reaches the deep. Priority flood: seed with the domain's own boundary — the
    # coast AND the seaward visibility limit are both outlets, and because the seabed
    # deepens outward the flow finds the seaward one on its own rather than being told to.
    # PRIORITY FLOOD + EPSILON. Plain pit filling makes each hollow a FLAT, and D8 cannot
    # leave a flat — the first run left 99,989 px (14% of the domain) with nowhere lower to
    # go and a maximum drainage of 1,819 km2, because flow stalled in every filled hollow.
    # Adding a tiny increment as the flood advances makes the filled surface strictly
    # descending toward the outlet, so every cell has exactly one way out and the flats
    # resolve in the direction the water actually came from.
    EPS = 1e-3            # metres; far below the vertical precision of the source
    filled = np.where(dom, z, np.inf).astype("float64")
    seen = ~dom
    heap: list = []
    nb = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))
    edge = np.zeros_like(dom)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        edge |= dom & ~np.roll(dom, (dy, dx), (0, 1))
    for y, x in zip(*np.nonzero(dom & edge)):
        heapq.heappush(heap, (float(z[y, x]), int(y), int(x)))
        seen[y, x] = True
    n_out = len(heap)
    while heap:
        e, y, x = heapq.heappop(heap)
        filled[y, x] = e
        for dy, dx in nb:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                seen[ny, nx] = True
                heapq.heappush(heap, (max(e + EPS, float(z[ny, nx])), ny, nx))
    print(f"  pit-filled from {n_out:,} outlet px; "
          f"raised {int((filled[dom] > z[dom]).sum()):,} px "
          f"({100*(filled[dom] > z[dom]).mean():.1f}% of the domain)")

    # --- D8 ON THE FILLED SURFACE --------------------------------------------------
    np.seterr(invalid="ignore")          # inf - inf outside the domain; the mask drops it
    steep = np.full((h, w), -1, np.int8)
    best = np.zeros((h, w), "float64")
    for k, (dy, dx) in enumerate(nb):
        nz = np.full((h, w), np.inf, "float64")
        sl = (slice(max(0, -dy), h - max(0, dy)), slice(max(0, -dx), w - max(0, dx)))
        ds = (slice(max(0, dy), h - max(0, -dy)), slice(max(0, dx), w - max(0, -dx)))
        nz[sl] = filled[ds]
        drop = (filled - nz) / (px * (2 ** 0.5 if dy and dx else 1))
        take = dom & (drop > best)
        best[take] = drop[take]
        steep[take] = k
    print(f"  D8: {int((steep[dom] < 0).sum()):,} px with nowhere lower to go")

    # --- ACCUMULATION, by processing highest first ---------------------------------
    acc = np.where(dom, 1.0, 0.0).astype("float64")
    order = np.argsort(-filled[dom])
    dy_, dx_ = zip(*nb)
    dy_, dx_ = np.array(dy_), np.array(dx_)
    yy, xx = np.nonzero(dom)
    for i in order:
        y, x, k = int(yy[i]), int(xx[i]), int(steep[yy[i], xx[i]])
        if k < 0:
            continue
        acc[y + dy_[k], x + dx_[k]] += acc[y, x]
    area = acc * (px / 1000.0) ** 2
    if fine:
        # CACHE THE EXPENSIVE HALF. The flood, the D8 and the accumulation take about a
        # quarter of an hour; choosing a threshold is a judgement that wants several
        # tries. Saving them means a threshold can be re-tried in seconds, which is the
        # difference between choosing one from evidence and choosing the first that runs.
        np.savez_compressed(cfg["fine_cache"], area=area.astype("float32"),
                            dom=dom, band=band.astype("float32"),
                            steep=steep, z=z.astype("float32"))
        print(f"  cached accumulation -> {cfg['fine_cache']}")
    return _emit(cfg, fine, area, dom, band, steep, z, tr, crs, px)


def _emit(cfg, fine, area, dom, band, steep, z, tr, crs, px):
    import numpy as np
    from pathlib import Path
    nb = ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1))
    dy_, dx_ = np.array([d[0] for d in nb]), np.array([d[1] for d in nb])
    h, w = z.shape
    thr_default = cfg['fine_min_drainage_km2'] if fine else cfg['min_drainage_km2']
    out = cfg['fine_out'] if fine else cfg['out']
    summ = cfg['fine_summary'] if fine else cfg['summary']
    # A THRESHOLD ON DRAINAGE AREA CUTS THE ESTUARIES FIRST, and that is structural
    # rather than a tuning problem. This network's headwaters are AT THE COAST — flow
    # runs seaward — so accumulation is smallest exactly where Stephen wants the detail.
    # A single threshold that keeps the offshore trunks legible empties the Thames.
    # So the threshold is lower inshore, stated as the display choice it is: one cell is
    # 0.054 km2 at 232 m, so 1 km2 is about eighteen cells upstream, which is a channel
    # rather than a pixel.
    thr = thr_default
    if fine:
        near = band <= cfg["fine_inshore_km"]
        thr_map = np.where(near, cfg["fine_min_inshore_km2"], thr_default)
        net = dom & (area >= thr_map)
        print(f"  inshore (<= {cfg['fine_inshore_km']:.0f} km) threshold "
              f"{cfg['fine_min_inshore_km2']:.0f} km2, offshore {thr_default:.0f} km2")
        print(f"    inshore px {int((net & near).sum()):,}, "
              f"offshore px {int((net & ~near).sum()):,}")
    net = dom & (area >= thr) if not fine else net
    print(f"  drainage area: median {np.median(area[dom]):.2f} km2, "
          f"max {area[dom].max():,.0f} km2")
    for t in (100, 250, 500, 1000, 2500):
        print(f"    >= {t:>5} km2: {int((dom & (area >= t)).sum()):>7,} px")
    print(f"  network at {thr:.0f} km2: {int(net.sum()):,} px")

    # --- vectorise -----------------------------------------------------------------
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    D = cfg["coord_dp"]

    def lonlat(y, x):
        return back.transform(tr[2] + (x + 0.5) * tr[0], tr[5] + (y + 0.5) * tr[4])

    # ONE POLYLINE PER CHANNEL, not one segment per cell. A channel of 400 cells was
    # 400 two-point features sharing 399 duplicated coordinates — 348,256 features and
    # 55 MB at the threshold the estuaries need. Walking each channel from its head to
    # the next confluence stores every coordinate once and lets a reader select a whole
    # channel rather than a pixel of one.
    nxt = {}
    for y, x in zip(*np.nonzero(net)):
        k = int(steep[y, x])
        if k < 0:
            continue
        ny, nx = int(y) + dy_[k], int(x) + dx_[k]
        if net[ny, nx]:
            nxt[(int(y), int(x))] = (ny, nx)
    upstream: dict = {}
    for a_, b_ in nxt.items():
        upstream.setdefault(b_, []).append(a_)
    heads = [c for c in zip(*[v.tolist() for v in np.nonzero(net)])
             if len(upstream.get(c, ())) != 1]
    feats, drawn = [], set()
    for hcell in heads:
        for start in (upstream.get(hcell) or [None]):
            cur = start if start is not None else hcell
            if cur is None or cur in drawn:
                continue
            chain = [hcell] if start is not None else []
            chain = ([cur] + chain) if start is not None else [cur]
            # walk downstream from `cur` until a confluence or the end
            path = [cur]
            drawn.add(cur)
            while cur in nxt:
                nx_ = nxt[cur]
                path.append(nx_)
                if len(upstream.get(nx_, ())) > 1 or nx_ in drawn:
                    break
                drawn.add(nx_)
                cur = nx_
            if len(path) < 2:
                continue
            coords = []
            for (yy_, xx_) in path:
                lo, la = lonlat(yy_, xx_)
                coords.append([round(lo, D), round(la, D)])
            km2 = float(area[path[-1][0], path[-1][1]])
            feats.append({"type": "Feature",
                          "geometry": {"type": "LineString", "coordinates": coords},
                          "properties": {"km2": round(km2, 1),
                                         "cells": len(path),
                                         "depth_m": round(float(-z[path[-1]]), 1)}})

    props = {
        "generation": generation(),
        "what": "An INVERTED sub-sea stream network: D8 drainage run over the seabed. Flow "
                "goes to the deepest place, so these are the submarine valleys, and the "
                "network converges AWAY from the coast rather than toward it.",
        "bounds": "Landward, the OS high_water polygons over GB. Seaward, the "
                  "land-visibility cells of the sightline stage. Nothing outside both.",
        "min_drainage_km2": thr,
        "resolution": "fine (232 m, coastal band)" if fine else "coarse (930 m, whole sighted sea)",
        "channels": len(feats),
        "cells_in_network": int(net.sum()),
        "resolution_m": px,
        "not_a_router": "This is a PICTURE, not a routing surface. No draught threshold, no "
                        "weights, no connection to the river network, and no coverage "
                        "comparison against the hex mesh. It exists so the shape can be "
                        "judged before anything is built on it.",
        "pits_note": "The seabed is full of closed hollows; without filling them flow stops "
                     "in each one. Filling drains to the domain's own boundary — coast and "
                     "seaward limit both — and the flow finds the seaward outlet by itself "
                     "because the seabed deepens outward.",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0. "
                       "Contains OS data (c) Crown copyright and database right, OGL v3.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(out).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": feats},
        separators=(",", ":")))
    Path(summ).write_text(json.dumps(props, indent=1))
    print(f"wrote {out} "
          f"({Path(out).stat().st_size/1e6:.1f} MB, {len(feats):,} channels, "
          f"{int(net.sum()):,} cells)")


if __name__ == "__main__":
    main(fine="--fine" in sys.argv)
