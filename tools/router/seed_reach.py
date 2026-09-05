"""Can a seed node see open water? Three targets, in Stephen's order of preference.

THE QUESTION. A `seed_node` is the concept that already answered "which river nodes meet the
sea" — a node with no outflow standing at tidal water, from `rewt/stages/crawl.py`. Nothing
better has been found, and the foreshore-network metadata did not help. So: for each seed,
can it be joined by a straight line that does not cross land to

  1  a SEA NETWORK node        the open-water mesh, res 7, 1 km offshore
  2  a WATER SKELETON node     a medial-axis vertex, 58 m spacing
  3  a WATER SKELETON edge     the nearest point ON a chain, not just a vertex

taking the first that works. The land test is the exact Shapely one over both coastlines,
with the first 250 m ignored — a seed sits at the high water mark and EMODnet at 232 m calls
that land, so an untrimmed test refuses every line before it has gone anywhere.

WHY SEEDS AND NOT `sea_entry_node`. Because that column is unsound: of its 12,105 distinct
entry nodes only 2,204 are seeds, and 576 are `terminus = inland` — an inland head marked as
a sea entry. Reported separately; `is_seed` is the flag this uses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely import STRtree, distance, points
from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402
from landtest import land_crossing_test     # noqa: E402

CONFIG = {
    "network": "published/rewt_stage1_network.gpkg",
    "mesh": "tools/router/cache/mesh.npz",
    "skeleton": "docs/router/check/water_skeleton_gb.geojson",
    "masks": "tools/router/cache/sightline_masks.npz",
    "out": "docs/router/check/seed_reach.geojson",
    "summary": "docs/router/check/seed_reach_summary.json",
    "cap_km": 8.0,
    "trim_m": 250.0,
    "k": 400,
    "coord_dp": 6,
}


def main(cfg: dict = CONFIG) -> None:
    crosses = land_crossing_test(cfg["masks"])
    to93 = Transformer.from_crs(27700, 32630, always_xy=True)
    to43 = Transformer.from_crs(32630, 4326, always_xy=True)
    fwd = Transformer.from_crs(4326, 32630, always_xy=True)
    TRIM = cfg["trim_m"]

    nd = gpd.read_file(cfg["network"], layer="node")
    seeds = nd[nd.is_seed.astype(bool)]
    SX, SY = to93.transform(seeds.easting.values, seeds.northing.values)
    insc = seeds.in_scope.astype(bool).values
    print(f"{len(seeds):,} seed nodes, {int(insc.sum()):,} in scope")

    g = np.load(cfg["mesh"], allow_pickle=True)
    MX, MY = fwd.transform(g["lon"], g["lat"])
    mesh = np.column_stack([MX, MY])
    mtree = cKDTree(mesh)

    sk = json.loads(Path(cfg["skeleton"]).read_text())["features"]
    sv, chains = [], []
    for i, f in enumerate(sk):
        cs = [fwd.transform(lo, la) for lo, la in f["geometry"]["coordinates"]]
        chains.append(LineString(cs) if len(cs) > 1 else None)
        for c in cs:
            sv.append(c)
    sv = np.array(sv)
    stree = cKDTree(sv)
    etree = STRtree([c for c in chains if c is not None])
    print(f"  mesh {len(mesh):,} nodes; skeleton {len(sv):,} vertices, "
          f"{sum(c is not None for c in chains):,} chains")

    def clear(a_xy, b_xy):
        v = np.asarray(b_xy) - np.asarray(a_xy)
        L = float(np.hypot(*v))
        if L <= TRIM:
            return True
        st = np.asarray(a_xy) + v * (TRIM / L)
        return not crosses(to43.transform(*st)[::-1], to43.transform(*b_xy)[::-1])

    def try_tree(src, pts, tree, cap):
        dd, ii = tree.query(src, k=cfg["k"], distance_upper_bound=cap)
        for t in range(cfg["k"]):
            j = int(ii[t])
            if j >= len(pts):
                break
            if clear(src, pts[j]):
                return pts[j], float(dd[t])
        return None, None

    cap = cfg["cap_km"] * 1000.0
    out, tally = [], {"mesh": 0, "skeleton node": 0, "skeleton edge": 0, "none": 0}
    D = cfg["coord_dp"]
    for i in range(len(seeds)):
        src = np.array([SX[i], SY[i]])
        tgt, dist, how = None, None, None
        t1, d1 = try_tree(src, mesh, mtree, cap)
        if t1 is not None:
            tgt, dist, how = t1, d1, "mesh"
        else:
            t2, d2 = try_tree(src, sv, stree, cap)
            if t2 is not None:
                tgt, dist, how = t2, d2, "skeleton node"
            else:
                p = Point(*src)
                near = etree.query(p.buffer(cap), predicate="intersects")
                best = None
                for k_ in near:
                    ln = etree.geometries[k_]
                    q = ln.interpolate(ln.project(p))
                    dq = p.distance(q)
                    if best is None or dq < best[0]:
                        if clear(src, (q.x, q.y)):
                            best = (dq, (q.x, q.y))
                if best:
                    tgt, dist, how = best[1], best[0], "skeleton edge"
        tally[how or "none"] += 1
        r = seeds.iloc[i]
        a = to43.transform(*src)
        f = {"type": "Feature",
             "properties": {"node_id": r.node_id, "reached": how or "none",
                            "m": None if dist is None else round(dist),
                            "in_scope": bool(r.in_scope)}}
        if tgt is None:
            f["geometry"] = {"type": "Point", "coordinates": [round(a[0], D), round(a[1], D)]}
        else:
            b = to43.transform(*tgt)
            f["geometry"] = {"type": "LineString", "coordinates": [
                [round(a[0], D), round(a[1], D)], [round(b[0], D), round(b[1], D)]]}
        # EVERY SEED GETS A POINT, not only the failures. Drawing just the sight-line
        # left the seed itself invisible — Stephen could see lines leaving something he
        # could not see. 2,246 seeds is roughly one per river mouth, four in the whole
        # Medway and Swale, so a line with no origin marker is hard to read at any zoom.
        out.append(f)
        if tgt is not None:
            out.append({"type": "Feature",
                        "geometry": {"type": "Point",
                                     "coordinates": [round(a[0], D), round(a[1], D)]},
                        "properties": {**f["properties"], "marker": "seed"}})
        else:
            f["properties"]["marker"] = "seed"
        if i % 250 == 0:
            print(f"    {i:,}/{len(seeds):,}", end="\r")
    print()
    n = len(seeds)
    for k_, v in tally.items():
        print(f"  {k_:>15}: {v:>6,}  ({100*v/n:5.1f}%)")
    ok = n - tally["none"]
    print(f"  REACHED SOMETHING: {ok:,} of {n:,} ({100*ok/n:.1f}%)")
    ins = [f for f in out if f["properties"]["in_scope"]]
    oki = sum(1 for f in ins if f["properties"]["reached"] != "none")
    print(f"  in scope: {oki:,} of {len(ins):,} ({100*oki/max(len(ins),1):.1f}%)")

    props = {
        "generation": generation(),
        "what": "For each seed node, the first of three targets it can reach by a straight "
                "line that does not cross land: a sea-network node, then a skeleton "
                "vertex, then a point on a skeleton edge.",
        "why_seeds": "sea_entry_node is unsound — of 12,105 distinct entry nodes only 2,204 "
                     "are seeds and 576 are terminus=inland. is_seed is the flag used here.",
        "land_test": "exact Shapely over both coastlines, first 250 m ignored because a seed "
                     "sits at high water and EMODnet at 232 m calls that land",
        "cap_km": cfg["cap_km"], "seeds": n, "by_target": tally,
        "reached": ok, "reached_pct": round(100 * ok / n, 1),
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(cfg["out"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": out},
        separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps(props, indent=1))
    print(f"wrote {cfg['out']}")


if __name__ == "__main__":
    main()
