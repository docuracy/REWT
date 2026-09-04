"""What does refusing a link actually cost? Measure before refining.

PLAN.md 31 left a question open. The routing grid is res 7, which threads a channel of
about 2.4 km; narrower water is crossed only by luck of alignment, and a link whose chord
crosses land is refused. Stephen asked whether the estuary refinement should be extended to
subdivide wherever that happens. Refinement is always possible, so the only honest reason to
do it is a measured cost.

THE COST IS A DETOUR, NOT A DISCONNECTION. The graph is one component: every refused link
still has a way round. So for each refused pair this compares

    d_graph  the shortest path between the two cells IN THE RES-7 GRAPH
    d_water  the shortest path between the same two points THROUGH WATER, on the 232 m
             mask, which is the finest evidence we have and the bound on what any
             refinement could recover

and reports d_graph / d_water. A ratio near 1 means the grid already routes as well as the
water allows and refining buys nothing. A large ratio means the grid is going round
something the water does not require it to go round — and only THOSE are candidates.

CRUCIALLY IT SEPARATES THE TWO REASONS A LINK IS REFUSED. Two cells either side of a narrow
PENINSULA are correctly refused and no resolution will help; two cells either side of a
narrow CHANNEL are wrongly refused and a finer grid would thread it. `d_water` tells them
apart: the first has no short water path, the second does.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import h3
import numpy as np
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402
from landtest import land_crossing_test     # noqa: E402

CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "masks": "tools/router/cache/sightline_masks.npz",
    "summary": "docs/router/data/detour_summary.json",
    "window_pad_px": 90,      # ~21 km of margin round each pair, at 232 m
    "report_worst": 12,
}


def main(cfg: dict = CONFIG) -> None:
    g = np.load(cfg["grid"], allow_pickle=True)
    cells, lat, lon = g["cell"].tolist(), g["lat"], g["lon"]
    idx = {c: i for i, c in enumerate(cells)}
    crosses = land_crossing_test(cfg["masks"])

    # --- which links were refused, and for what pair of cells ----------------------
    ll = {c: h3.cell_to_latlng(c) for c in cells}
    refused = set()
    for c in cells:
        for n in h3.grid_disk(c, 1):
            if n == c or n not in idx:
                continue
            a, b = (c, n) if c < n else (n, c)
            if (a, b) in refused:
                continue
            if crosses(ll[a], ll[b]):
                refused.add((a, b))
    print(f"{len(refused):,} adjacent res-7 pairs refused for crossing land")

    # --- d_graph: shortest path in the routing graph, one Dijkstra per source -------
    z = np.load(cfg["edges"])
    e, L = z["edge"], z["length_m"]
    m = coo_matrix((L, (e[:, 0], e[:, 1])), shape=(len(cells),) * 2)
    m = m + m.T
    by_src = defaultdict(list)
    for a, b in refused:
        by_src[idx[a]].append(idx[b])
    print(f"  {len(by_src):,} distinct sources to run")
    d_graph = {}
    srcs = sorted(by_src)
    for k in range(0, len(srcs), 256):
        chunk = srcs[k:k + 256]
        dd = dijkstra(m, indices=chunk, limit=120_000.0)
        for r, s in enumerate(chunk):
            for t in by_src[s]:
                d_graph[(s, t)] = float(dd[r, t])
        print(f"    {min(k + 256, len(srcs)):,}/{len(srcs):,}", end="\r")
    print()

    # --- d_water: shortest path through water on the 232 m mask, in a local window --
    mk = np.load(cfg["masks"], allow_pickle=True)
    sea, ftr = mk["fine_sea"], mk["fine_transform"]
    fwd = Transformer.from_crs(4326, str(mk["crs"][0]), always_xy=True)
    fh, fw = sea.shape
    px = abs(float(ftr[0]))
    pad = cfg["window_pad_px"]

    def rc(la, lo):
        x, y = fwd.transform(lo, la)
        return int((y - ftr[5]) / ftr[4]), int((x - ftr[2]) / ftr[0])

    def water_path(a, b):
        r1, c1 = rc(*ll[a])
        r2, c2 = rc(*ll[b])
        r0, rN = max(0, min(r1, r2) - pad), min(fh, max(r1, r2) + pad + 1)
        c0, cN = max(0, min(c1, c2) - pad), min(fw, max(c1, c2) + pad + 1)
        w = sea[r0:rN, c0:cN]
        h, wd = w.shape
        ids = -np.ones((h, wd), np.int32)
        ys, xs = np.nonzero(w)
        ids[ys, xs] = np.arange(len(ys))
        if len(ys) == 0:
            return math.inf
        rows, cols, vals = [], [], []
        for dy, dx, cost in ((0, 1, px), (1, 0, px), (1, 1, px * 2 ** .5), (1, -1, px * 2 ** .5)):
            y2, x2 = ys + dy, xs + dx
            ok = (y2 >= 0) & (y2 < h) & (x2 >= 0) & (x2 < wd)
            ok &= w[np.clip(y2, 0, h - 1), np.clip(x2, 0, wd - 1)]
            u = ids[ys[ok], xs[ok]]
            v = ids[y2[ok], x2[ok]]
            rows += u.tolist(); cols += v.tolist(); vals += [cost] * int(ok.sum())
        n = len(ys)
        gm = coo_matrix((vals, (rows, cols)), shape=(n, n))
        gm = gm + gm.T
        s = ids[np.clip(r1 - r0, 0, h - 1), np.clip(c1 - c0, 0, wd - 1)]
        t = ids[np.clip(r2 - r0, 0, h - 1), np.clip(c2 - c0, 0, wd - 1)]
        if s < 0 or t < 0:
            return math.inf                    # a centre is not on water in this mask
        return float(dijkstra(gm, indices=int(s))[int(t)])

    R = 6371000.0

    def chord_m(a, b):
        (la1, lo1), (la2, lo2) = ll[a], ll[b]
        p1, p2 = math.radians(la1), math.radians(la2)
        dl = math.radians(lo2 - lo1)
        return R * math.acos(min(1.0, math.sin(p1) * math.sin(p2)
                                 + math.cos(p1) * math.cos(p2) * math.cos(dl)))

    # THE DISCRIMINATOR. d_graph/d_water says how far the grid overshoots the water route.
    # It does NOT say whether refining could recover it. d_water/chord does: if the water
    # runs essentially straight between the two centres, the thing in the way is small and
    # a finer grid would thread past it; if the water has to go a long way round, the
    # barrier is real and the grid is right to avoid it.
    rows = []
    for k, (a, b) in enumerate(sorted(refused)):
        dg = d_graph.get((idx[a], idx[b]), math.inf)
        dw = water_path(a, b)
        ch = chord_m(a, b)
        rows.append({"a": a, "b": b, "lat": ll[a][0], "lon": ll[a][1],
                     "d_graph_m": dg, "d_water_m": dw, "chord_m": ch,
                     "water_over_chord": (dw / ch) if np.isfinite(dw) and ch else None,
                     "ratio": (dg / dw) if dw and np.isfinite(dw) and np.isfinite(dg) else None})
        if k % 200 == 0:
            print(f"    water paths {k:,}/{len(refused):,}", end="\r")
    print()

    fin = [r for r in rows if r["ratio"] is not None]
    sep = [r for r in rows if r["ratio"] is None]
    rat = np.array([r["ratio"] for r in fin])
    print(f"\n{len(fin):,} pairs have a water path; {len(sep):,} do not "
          f"(genuinely separated within the window — no resolution helps)")
    for p in (50, 75, 90, 95, 99):
        print(f"  {p}th percentile detour ratio: {np.percentile(rat, p):.2f}x")
    print(f"  worst {rat.max():.1f}x")
    for thr in (1.5, 2.0, 3.0, 5.0):
        n = int((rat > thr).sum())
        print(f"  pairs detouring more than {thr}x: {n:,} ({100*n/len(fin):.2f}%)")

    woc = np.array([r["water_over_chord"] for r in fin if r["water_over_chord"]])
    print(f"\nHOW BIG IS THE THING IN THE WAY?  water path / straight chord:")
    for p_ in (50, 75, 90, 99):
        print(f"  {p_}th percentile: {np.percentile(woc, p_):.2f}x")
    thread = int((woc < 1.15).sum())
    print(f"  within 15% of straight — a small obstruction a finer grid would thread: "
          f"{thread:,} of {len(woc):,} ({100*thread/len(woc):.1f}%)")

    # POSITIVE CONTROL. If d_water/chord were near 1 only because the raster measure is
    # loose, this number would be near 1 for accepted pairs too and the figure above would
    # mean nothing. Sample links that were NOT refused and measure the same thing.
    rng = np.random.default_rng(0)
    acc = []
    seen_pairs = set()
    for c in rng.choice(np.array(cells, dtype=object), size=1200, replace=False):
        for n in h3.grid_disk(str(c), 1):
            if n == c or n not in idx:
                continue
            pr = (str(c), n) if str(c) < n else (n, str(c))
            if pr in refused or pr in seen_pairs:
                continue
            seen_pairs.add(pr)
            acc.append(pr)
            break
        if len(acc) >= 300:
            break
    ctrl = []
    for a, b in acc:
        dw2 = water_path(a, b)
        ch2 = chord_m(a, b)
        if np.isfinite(dw2) and ch2:
            ctrl.append(dw2 / ch2)
    ctrl = np.array(ctrl)
    print(f"  CONTROL, {len(ctrl)} pairs whose link was NOT refused: median "
          f"{np.median(ctrl):.2f}x, 90th {np.percentile(ctrl, 90):.2f}x")

    # REFINED REGION AGAINST UNREFINED, IN ONE RUN. grid2 refines only within 25 km of
    # England and Wales (PLAN.md 33), so the rest of the grid is an untouched control
    # measured by the same method at the same moment. A before/after across two grids
    # would not be comparable — refinement changes which pairs exist at all.
    import geopandas as _gpd
    from shapely.ops import unary_union as _uu
    from shapely.geometry import Point as _P
    _cr = _gpd.read_file("data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg",
                         layer="country_region")
    _ew = _uu(_cr[_cr.Name.isin(["England", "Wales"])].geometry.values)
    _to = Transformer.from_crs(4326, 27700, always_xy=True)
    near = np.array([_P(*_to.transform(r["lon"], r["lat"])).distance(_ew) <= 25_000.0
                     for r in fin])
    rr = np.array([r["ratio"] for r in fin])
    print("\nREFINED (within 25 km of England and Wales) vs UNREFINED control:")
    for lab, m in (("refined  ", near), ("unrefined", ~near)):
        if m.sum():
            print(f"  {lab}  n={int(m.sum()):>4}  median {np.median(rr[m]):.2f}x  "
                  f"90th {np.percentile(rr[m], 90):.2f}x  "
                  f">2x {100*(rr[m] > 2).mean():.1f}%")

    fin.sort(key=lambda r: -r["ratio"])
    print(f"\nworst {cfg['report_worst']}:")
    for r in fin[:cfg["report_worst"]]:
        print(f"  {r['ratio']:>6.1f}x  graph {r['d_graph_m']/1000:>6.1f} km vs water "
              f"{r['d_water_m']/1000:>5.1f} km   at {r['lat']:.3f} N {r['lon']:.3f} E")

    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(),
        "refused_pairs": len(refused),
        "with_water_path": len(fin),
        "separated_no_resolution_helps": len(sep),
        "detour_ratio": {f"p{p}": round(float(np.percentile(rat, p)), 3)
                         for p in (50, 75, 90, 95, 99)},
        "worst_ratio": round(float(rat.max()), 2),
        "refined_vs_control": {
            "refined_median": round(float(np.median(rr[near])), 3) if near.sum() else None,
            "refined_n": int(near.sum()),
            "unrefined_median": round(float(np.median(rr[~near])), 3) if (~near).sum() else None,
            "unrefined_n": int((~near).sum()),
            "note": "grid2 refines only within 25 km of England and Wales, so the rest of "
                    "the grid is an untouched control measured the same way in the same "
                    "run. A before/after across two grids is not comparable, because "
                    "refinement changes which pairs exist at all."},
        "water_over_chord": {f"p{p_}": round(float(np.percentile(woc, p_)), 3)
                             for p_ in (50, 75, 90, 99)},
        "threadable_small_obstruction": int((woc < 1.15).sum()),
        "control_water_over_chord": {"n": int(len(ctrl)),
                                     "median": round(float(np.median(ctrl)), 3),
                                     "p90": round(float(np.percentile(ctrl, 90)), 3)},
        "over": {f"{t}x": int((rat > t).sum()) for t in (1.5, 2.0, 3.0, 5.0)},
        "worst": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
                  for r in fin[:cfg["report_worst"]]],
        "what": "d_graph is the res-7 routing distance between two adjacent cells whose "
                "direct link was refused for crossing land; d_water is the shortest path "
                "between the same points through the 232 m sea mask, which bounds what any "
                "refinement could recover. A ratio near 1 means refining buys nothing.",
        "window_km": round(cfg["window_pad_px"] * 0.2325, 1),
        "caveat": "Truncated by the window: a pair whose real way round is longer than the "
                  "window reports no water path and is counted as separated, so the "
                  "separated count is an UPPER bound on genuine separation.",
    }, indent=1))
    print(f"\nwrote {cfg['summary']}")


if __name__ == "__main__":
    main()
