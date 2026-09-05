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
    "out": "docs/router/data/seabed_channels.geojson",
    "summary": "docs/router/data/seabed_summary.json",
    "min_drainage_km2": 250.0,   # chosen from the distribution, see main()
    "coord_dp": 5,
}


def main(cfg: dict = CONFIG) -> None:
    m = np.load(cfg["masks"], allow_pickle=True)
    z = m["elev"].astype("float32")
    sea, visible = m["sea"], m["visible"]
    tr, crs = m["transform"], str(m["crs"][0])
    px = float(m["px"][0])
    h, w = z.shape

    dom = sea & visible
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
    thr = cfg["min_drainage_km2"]
    net = dom & (area >= thr)
    print(f"  drainage area: median {np.median(area[dom]):.2f} km2, "
          f"max {area[dom].max():,.0f} km2")
    for t in (100, 250, 500, 1000, 2500):
        print(f"    >= {t:>5} km2: {int((dom & (area >= t)).sum()):>7,} px")
    print(f"  network at {thr:.0f} km2: {int(net.sum()):,} px")

    # --- one segment per network cell, to its downstream neighbour -----------------
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    D = cfg["coord_dp"]

    def lonlat(y, x):
        return back.transform(tr[2] + (x + 0.5) * tr[0], tr[5] + (y + 0.5) * tr[4])

    feats = []
    for y, x in zip(*np.nonzero(net)):
        k = int(steep[y, x])
        if k < 0:
            continue
        ny, nx = int(y) + dy_[k], int(x) + dx_[k]
        if not dom[ny, nx]:
            continue
        a, b = lonlat(int(y), int(x)), lonlat(ny, nx)
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": [
                          [round(a[0], D), round(a[1], D)],
                          [round(b[0], D), round(b[1], D)]]},
                      "properties": {"km2": round(float(area[y, x]), 1),
                                     "depth_m": round(float(-z[y, x]), 1),
                                     "rank": int(np.log10(max(area[y, x], 1)))}})
    props = {
        "generation": generation(),
        "what": "An INVERTED sub-sea stream network: D8 drainage run over the seabed. Flow "
                "goes to the deepest place, so these are the submarine valleys, and the "
                "network converges AWAY from the coast rather than toward it.",
        "bounds": "Landward, the OS high_water polygons over GB. Seaward, the "
                  "land-visibility cells of the sightline stage. Nothing outside both.",
        "min_drainage_km2": thr,
        "segments": len(feats),
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
    Path(cfg["out"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": feats},
        separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps(props, indent=1))
    print(f"wrote {cfg['out']} "
          f"({Path(cfg['out']).stat().st_size/1e6:.1f} MB, {len(feats):,} segments)")


if __name__ == "__main__":
    main()
