"""Trace a path from a stranded river terminus to the sea grid, across the drying zone.

    python3 tools/router/trace.py

Run from the repository root; paths are relative (AGENTS.md).

WHAT THIS IS FOR. PLAN.md 7 rule 3: 414 tidal termini are neither inside a grid cell nor
adjacent to one. They sit up estuaries, behind ground that is sea at high water and dry at
low. Reaching them needs a path chosen by BATHYMETRY rather than a straight line, which is
what rules/H3.md asks for.

THIS COST SURFACE IS NOT A WEIGHT, and the distinction is the same one PLAN.md 8 draws for
the sightline. Where the water lies, and how deep, is geometry and measurement — as true in
1450 as in 2026. How much a master would pay to avoid a shoal is a claim about a vessel and
a period, and it is deferred. This finds the deepest available channel; it does not price it.

NOT A CHART. conf/sources.yml carries DO NOT USE FOR NAVIGATION and it travels.
"""
from __future__ import annotations

import heapq
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds
from scipy.spatial import cKDTree

import h3
from generation import generation
from sightline import build_vrt, nodata_to_nan

ATTRIBUTION = ("Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium (2024): "
               "EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.")

CONFIG = {
    "windows": "data/raw/emodnet_bathymetry/*.tif",
    "vrt": "tools/router/cache/emodnet.vrt",
    "grid": "tools/router/cache/grid2.npz",
    "network": "published/rewt_stage1_network.gpkg",
    "joins": "docs/router/data/join_summary.json",
    "out": "docs/router/data/traces.geojson",
    "summary": "docs/router/data/trace_summary.json",
    # THE COST SURFACE. Deliberately crude and deliberately untuned: one parameter with a
    # reason, not a fitted model. Water costs 1 per pixel whatever its depth, because
    # preferring depth is a vessel judgement and this is not making one. Ground above the
    # lowest tide costs 1 + its height in metres, so a trace crosses a drying bank only
    # when there is no wet route, and prefers the lowest saddle when it must.
    "impassable_above_m": 5.0,   # above this it is land, not a drying bank
    # A CEILING ON DRYING GROUND, because 5 m of permitted height silently licenses a
    # river valley. The Thames terminus in central London traced 43 km, of which 35.6 km
    # was "drying" — which in a valley means low land, not tidal flat. Section 6 measured
    # the population these traces exist to cross: the gap from a terminus to water that
    # exists at the lowest tide is a median 143 m, a 95th of 624 m and a MAXIMUM of
    # 9,605 m anywhere in the country. A path crossing more drying ground than the widest
    # intertidal zone that exists is not crossing an intertidal zone.
    "max_drying_m": None,        # DERIVED at run time — see derive_drying_ceiling()
    "margin_px": 40,             # window padding around the straight line
    "earth_radius_m": 6371000.0,
}


def derive_drying_ceiling(src, t, cfg) -> float:
    """The widest intertidal gap that actually exists, measured now.

    This was a typed 9,605 — correct, and correct only because the number had not moved.
    rewt-46 found three frozen figures of mine in their own file within twenty minutes
    and the remedy each time was the same, and it is not care: compute it, print it from
    the file, or do not state it. So it is computed. If the terminus set changes — and
    R-01 will change it — the ceiling follows instead of quietly describing a population
    that no longer exists.
    """
    R = cfg["earth_radius_m"]
    worst = 0.0
    for la, lo in zip(t.lat.values, t.lon.values):
        for half in (0.03, 0.08, 0.20, 0.50):
            w = from_bounds(lo - half, la - half, lo + half, la + half, src.transform)
            a = nodata_to_nan(src.read(1, window=w, boundless=True,
                                       fill_value=np.nan)).astype("float64")
            wet = a < 0
            if not wet.any():
                continue
            rr, cc = np.nonzero(wet)
            x0, y0 = src.xy(int(w.row_off), int(w.col_off))
            plon = x0 + cc * src.res[0]
            plat = y0 - rr * src.res[1]
            d = R * np.hypot(np.radians(plat - la),
                             np.radians(plon - lo) * np.cos(np.radians(la)))
            worst = max(worst, float(d.min()))
            break
    return worst


def dijkstra(cost: np.ndarray, start: tuple[int, int], goal: np.ndarray):
    """Least-cost path to ANY pixel in the goal mask. NaN cost = impassable.

    THE GOAL IS THE GRID, NOT A CHOSEN CELL. The first version aimed at the nearest
    grid cell centre by straight-line distance, which is a different question: 34 of
    85 failures could reach open water perfectly well and simply could not reach THAT
    cell. Aiming at a point when the requirement is "reach the network" invents an
    obstacle out of the choice of target.
    """
    h, w = cost.shape
    dist = np.full((h, w), np.inf)
    prev = np.full((h, w, 2), -1, np.int32)
    dist[start] = 0.0
    pq = [(0.0, start)]
    reached = None
    steps = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
             (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
    while pq:
        d, (r, c) = heapq.heappop(pq)
        if goal[r, c]:
            reached = (r, c)
            break
        if d > dist[r, c]:
            continue
        for dr, dc, k in steps:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w):
                continue
            cc = cost[nr, nc]
            if not np.isfinite(cc):
                continue
            nd = d + k * cc
            if nd < dist[nr, nc]:
                dist[nr, nc] = nd
                prev[nr, nc] = (r, c)
                heapq.heappush(pq, (nd, (nr, nc)))
    if reached is None:
        return None, np.inf
    path = [reached]
    while path[-1] != start:
        r, c = path[-1]
        p = tuple(prev[r, c])
        if p == (-1, -1):
            return None, np.inf
        path.append(p)
    return path[::-1], float(dist[reached])


def main(cfg: dict = CONFIG) -> None:
    src = rasterio.open(build_vrt(cfg))
    g = np.load(cfg["grid"], allow_pickle=True)
    glat, glon = g["lat"], g["lon"]
    R = cfg["earth_radius_m"]

    def xyz(la, lo):
        la, lo = np.radians(la), np.radians(lo)
        return np.column_stack([R*np.cos(la)*np.cos(lo), R*np.cos(la)*np.sin(lo), R*np.sin(la)])

    tree = cKDTree(xyz(glat, glon))
    cellset = set(g["cell"].tolist())
    grid_res = sorted({int(r) for r in g["resolution"]}, reverse=True)
    js = json.loads(Path(cfg["joins"]).read_text())
    todo = js["rule3"]
    if cfg["max_drying_m"] is None:
        import geopandas as _gpd
        _n = _gpd.read_file(cfg["network"], layer="node", ignore_geometry=True,
                            columns=["node_id", "terminus", "in_scope",
                                     "easting", "northing"])
        _l = _gpd.read_file(cfg["network"], layer="link", ignore_geometry=True,
                            columns=["from_node", "to_node", "retired"])
        _live = _l[~_l.retired.astype(bool)]
        _sinks = set(_live.to_node.dropna()) - set(_live.from_node.dropna())
        _t = _n[_n.node_id.isin(_sinks) & (_n.terminus == "tidal")
                & _n.in_scope.astype(bool)].copy()
        _tr = Transformer.from_crs(27700, 4326, always_xy=True)
        _t["lon"], _t["lat"] = _tr.transform(_t.easting.values, _t.northing.values)
        cfg["max_drying_m"] = derive_drying_ceiling(src, _t, cfg)
        print(f"  drying ceiling derived from the current in-scope termini: "
              f"{cfg['max_drying_m']:.0f} m (the widest intertidal gap that exists)")
    # NEAREST THE GRID FIRST, so the trunk of an estuary is traced before its branches
    # and the branches have something to join. Traced in arbitrary order, several termini
    # up one channel each cut their own path to the sea and the result is a bundle of
    # near-parallel threads down the same water — which is what the Severn looked like.
    todo.sort(key=lambda r: r["dist_m"])
    reached: set[tuple[int, int]] = set()      # path pixels already traced, in RASTER coords
    print(f"{len(todo):,} rule-3 termini to trace (in-scope only: the join "
          f"stage applies the scope rule and this reads its output) "
          f"({sum(t['in_scope'] for t in todo):,} in scope)")

    feats, rows = [], []
    for k, t in enumerate(todo):
        la, lo = t["lat"], t["lon"]
        _, j = tree.query(xyz(np.array([la]), np.array([lo])))
        j = int(j[0])
        tla, tlo = float(glat[j]), float(glon[j])
        pad = cfg["margin_px"] * max(abs(src.transform.a), abs(src.transform.e))
        w = from_bounds(min(lo, tlo) - pad, min(la, tla) - pad,
                        max(lo, tlo) + pad, max(la, tla) + pad, src.transform)
        a = nodata_to_nan(src.read(1, window=w, boundless=True, fill_value=np.nan)).astype("float64")
        tw = rasterio.windows.transform(w, src.transform)

        cost = np.where(a < 0, 1.0, 1.0 + np.maximum(a, 0.0))
        cost[~np.isfinite(a)] = np.nan
        cost[a >= cfg["impassable_above_m"]] = np.nan

        def rc(lat, lon):
            c, r = ~tw * (lon, lat)
            return (int(np.clip(r, 0, a.shape[0]-1)), int(np.clip(c, 0, a.shape[1]-1)))

        # the goal is the network: the grid, PLUS everything already traced. A later
        # trace stops the moment it meets an earlier one, so an estuary comes out as a
        # tree with one trunk rather than as a bundle of parallel threads.
        goal = np.zeros(a.shape, bool)
        wet = np.isfinite(a) & (a < 0)
        for rr, cc in zip(*np.nonzero(wet)):
            x, y = tw * (cc + 0.5, rr + 0.5)
            if any(h3.latlng_to_cell(float(y), float(x), rr) in cellset
                   for rr in grid_res):
                goal[rr, cc] = True
        r_off, c_off = int(w.row_off), int(w.col_off)
        for gr, gc in reached:
            rr, cc = gr - r_off, gc - c_off
            if 0 <= rr < a.shape[0] and 0 <= cc < a.shape[1]:
                goal[rr, cc] = True
        s = rc(la, lo)
        if not np.isfinite(cost[s]):
            cost[s] = 1.0 + max(0.0, float(a[s]) if np.isfinite(a[s]) else 0.0)
        if not goal.any():
            rows.append({**t, "traced": False, "reason": "no grid cell in the window"})
            continue
        path, total = dijkstra(cost, s, goal)
        if path is None:
            rows.append({**t, "traced": False, "reason": "no passable route"})
            continue

        for r_, c_ in path:
            reached.add((r_ + r_off, c_ + c_off))
        pts = [(tw * (c + 0.5, r + 0.5)) for r, c in path]
        elev = np.array([a[r, c] for r, c in path])
        seg = np.array([np.hypot((pts[i+1][0]-pts[i][0]) * 111320 * np.cos(np.radians(la)),
                                 (pts[i+1][1]-pts[i][1]) * 111320) for i in range(len(pts)-1)])
        dry = int((elev >= 0).sum())
        drying_m = float(seg.sum()) * dry / len(path)
        if drying_m > cfg["max_drying_m"]:
            rows.append({**t, "traced": False,
                         "reason": f"crosses {drying_m:.0f} m of drying ground, more than "
                                   f"the widest intertidal zone measured "
                                   f"({cfg['max_drying_m']:.0f} m) — a river valley, "
                                   f"not a tidal flat",
                         "drying_m": round(drying_m), "path_m": round(float(seg.sum()))})
            continue
        rows.append({**t, "traced": True,
                     "path_m": round(float(seg.sum())),
                     "straight_m": t["dist_m"],
                     "detour": round(float(seg.sum()) / max(t["dist_m"], 1), 2),
                     "max_elev_crossed_m": round(float(np.nanmax(elev)), 1),
                     "min_depth_m": round(float(np.nanmin(elev)), 1),
                     "drying_px": dry, "drying_m": round(drying_m),
                     "drying_frac": round(dry / len(path), 3)})
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": [[round(x, 6), round(y, 6)] for x, y in pts]},
                      "properties": {k2: v for k2, v in rows[-1].items()}})

    print(f"  {len(reached):,} distinct path pixels in the traced network "
          f"(a bundle of independent threads would hold many more)")
    ok = [r for r in rows if r["traced"]]
    bad = [r for r in rows if not r["traced"]]
    print(f"\ntraced {len(ok):,}, failed {len(bad):,}")
    if ok:
        det = np.array([r["detour"] for r in ok])
        dfr = np.array([r["drying_frac"] for r in ok])
        mx = np.array([r["max_elev_crossed_m"] for r in ok])
        print(f"  detour vs straight line: median {np.median(det):.2f}x, "
              f"90th {np.quantile(det,.9):.2f}x, max {det.max():.2f}x")
        print(f"  fraction of path on drying ground: median {np.median(dfr):.2f}, "
              f"max {dfr.max():.2f}")
        print(f"  highest ground crossed: median {np.median(mx):.1f} m, max {mx.max():.1f} m")
        print(f"  traces staying entirely below the lowest tide: "
              f"{int((dfr == 0).sum()):,} of {len(ok):,}")
    print(f"\nFAILURES — every one named (this answers 'is there anything else')")
    for r in bad:
        print(f"    {r['node_id']}  {r['dist_m']/1000:.2f} km  "
              f"at {r['lat']:.4f} N {r['lon']:.4f} E  "
              f"{'in scope' if r['in_scope'] else 'out of scope'}  — {r['reason']}")
    if not bad:
        print("    none — so check that impassable_above_m excludes something")

    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(), "attempted": len(rows), "traced": len(ok), "failed": len(bad),
        "impassable_above_m": cfg["impassable_above_m"],
        "provisional": "R-01 is unbuilt. The implementer will land it in TWO passes — "
                       "retirement of wholly-seaward links, then truncation of crossers "
                       "at the high water line. This population moves under both. "
                       "Re-derive after the second, not the first.",
        "rows": rows}, indent=1))
    Path(cfg["out"]).write_text(json.dumps({
        "type": "FeatureCollection",
        "properties": {"what": "traced paths from stranded river termini to the sea grid",
                       "cost": "1 per pixel in water; 1 + height in metres on ground above "
                               "the lowest tide; impassable above "
                               f"{cfg['impassable_above_m']} m. NOT a weight — see module "
                               "docstring.",
                       "attribution": ATTRIBUTION,
                       "provisional": "R-01 unbuilt; this population will move twice.",
                       "use_constraint": "DO NOT USE FOR NAVIGATION"},
        "features": feats}))
    print(f"\nwrote {cfg['summary']} and {cfg['out']}")


if __name__ == "__main__":
    main()
