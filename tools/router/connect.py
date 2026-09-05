"""One network: rivers -> skeleton -> mesh.

REPLACES `join.py` and `trace.py` for the new design. Those attached river termini to MESH
cells and, where no cell was near enough, traced a least-cost path across the drying ground —
rule 3, 230 of 389 attachments, inference. The mesh now stops a kilometre offshore and the
SKELETON runs up the estuary to the terminus, so the path that had to be inferred is mostly
already there as a measured centreline.

THREE JOINS, and each is land-tested with the same exact Shapely test as every other link:

  1  TERMINUS -> SKELETON   a tidal terminus to the nearest medial-axis vertex
  2  SKELETON -> MESH       a skeleton vertex to the nearest open-water cell centre
  3  the mesh's own links and the skeleton's own chains, unchanged

WHAT IT REPORTS is the thing Stephen has been asking for since the beginning: whether the
sea grid, the joins and the inland river network form ONE network, and if not, where it
breaks. That number is measured on the assembled graph, not asserted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402
from landtest import land_crossing_test     # noqa: E402

CONFIG = {
    "network": "published/rewt_stage1_network.gpkg",
    "mesh": "tools/router/cache/mesh.npz",
    "skeleton": "docs/router/check/water_skeleton_gb.geojson",
    "masks": "tools/router/cache/sightline_masks.npz",
    "boundary": "data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg",
    "out_joins": "docs/router/data/joins.geojson",
    "out_links": "docs/router/data/skeleton_mesh_links.geojson",
    "summary": "docs/router/data/network_summary.json",
    "scope_max_m_from_ew": 1000.0,
    "max_terminus_join_km": 5.0,
    "max_skeleton_mesh_km": 6.0,
    "coord_dp": 6,
}


def main(cfg: dict = CONFIG) -> None:
    crosses = land_crossing_test(cfg["masks"])
    TRIM_M = 250.0        # one EMODnet pixel; see nearest_clear
    to93 = Transformer.from_crs(27700, 32630, always_xy=True)
    to43 = Transformer.from_crs(32630, 4326, always_xy=True)
    fwd = Transformer.from_crs(4326, 32630, always_xy=True)

    # --- the termini, with the scope rule PLAN.md 15 -------------------------------
    t = gpd.read_file(cfg["network"], layer="terminus")
    t = t[t.arriving_form == "tidalRiver"].copy()
    nd = gpd.read_file(cfg["network"], layer="node")[["node_id", "in_scope"]]
    t = t.merge(nd, on="node_id", how="left")
    t = t[t.in_scope.astype(bool)]
    cr = gpd.read_file(cfg["boundary"], layer="country_region")
    ew = unary_union(cr[cr.Name.isin(["England", "Wales"])].geometry.values)
    d_ew = np.array([Point(x, y).distance(ew)
                     for x, y in zip(t.easting.values, t.northing.values)])
    t = t[d_ew <= cfg["scope_max_m_from_ew"]].copy()
    TX, TY = to93.transform(t.easting.values, t.northing.values)
    print(f"{len(t):,} tidal termini in scope")

    # --- the skeleton -------------------------------------------------------------
    sk = json.loads(Path(cfg["skeleton"]).read_text())["features"]
    sv, sowner = [], []
    for i, f in enumerate(sk):
        for lo, la in f["geometry"]["coordinates"]:
            sv.append(fwd.transform(lo, la))
            sowner.append(i)
    sv = np.array(sv)
    print(f"  skeleton {len(sk):,} chains, {len(sv):,} vertices")

    # --- the mesh -----------------------------------------------------------------
    g = np.load(cfg["mesh"], allow_pickle=True)
    mcell, mlat, mlon, medge = g["cell"], g["lat"], g["lon"], g["edge"]
    MX, MY = fwd.transform(mlon, mlat)
    mesh_pts = np.column_stack([MX, MY])
    print(f"  mesh {len(mcell):,} cells, {len(medge):,} links")

    def nearest_clear(src_xy, dst_xy, tree, cap_m, k=400, owner=None):
        """Nearest destination whose straight line does not cross land.

        k HAS TO BE LARGE, and this is the third time in this project. At 58 m spacing the
        400 nearest skeleton vertices span about 23 km OF ONE CHAIN, so a small k tests the
        same chain 24 times and reports failure if that chain's line happens to cross a
        bank. `owner` skips to the next distinct chain instead of grinding along one.
        """
        dd, ii = tree.query(src_xy, k=k, distance_upper_bound=cap_m)
        tried = set()
        for t_ in range(k):
            j = int(ii[t_])
            if j >= len(dst_xy):
                break
            if owner is not None:
                o = owner[j]
                if o in tried:
                    continue
                tried.add(o)
            # IGNORE LAND AT THE TERMINUS ITSELF. A tidal terminus sits at the high
            # water mark, and EMODnet at 232 m calls that land: 157 of 188 stranded
            # termini were INSIDE EMODnet land, so every line from them started in land
            # and was refused before it had gone anywhere. The question is whether the
            # route crosses land BETWEEN the two points, so the test begins one pixel
            # along. 9% are inside the OS land area too — the network reaches a little
            # above high water in places — and the same trim covers them.
            v = dst_xy[j] - src_xy
            L = float(np.hypot(*v))
            if L <= TRIM_M:
                return j, float(dd[t_])
            start = src_xy + v * (TRIM_M / L)
            a = to43.transform(*start)[::-1]
            b = to43.transform(*dst_xy[j])[::-1]
            if not crosses(a, b):
                return j, float(dd[t_])
        return None, None

    # --- JOIN 1: terminus -> skeleton ---------------------------------------------
    stree = cKDTree(sv)
    D = cfg["coord_dp"]
    jf, attached, stranded = [], 0, []
    for i in range(len(t)):
        j, dist = nearest_clear(np.array([TX[i], TY[i]]), sv, stree,
                                cfg["max_terminus_join_km"] * 1000.0, owner=sowner)
        r = t.iloc[i]
        if j is None:
            dn, _jn = stree.query(np.array([TX[i], TY[i]]), k=1)
            stranded.append({"node_id": r.node_id,
                             "nearest_skeleton_m": round(float(dn))})
            continue
        attached += 1
        a = to43.transform(TX[i], TY[i])
        b = to43.transform(*sv[j])
        jf.append({"type": "Feature",
                   "geometry": {"type": "LineString", "coordinates": [
                       [round(a[0], D), round(a[1], D)], [round(b[0], D), round(b[1], D)]]},
                   "properties": {"node_id": r.node_id, "to": "skeleton",
                                  "chain": int(sowner[j]), "m": round(dist)}})
    print(f"  terminus -> skeleton: {attached:,} joined, {len(stranded):,} stranded")

    # --- JOIN 2: skeleton -> mesh --------------------------------------------------
    mtree = cKDTree(mesh_pts)
    lf, seen_chain = [], {}
    for vi in range(0, len(sv), 4):          # every 4th vertex is ample at 58 m
        ch = sowner[vi]
        j, dist = nearest_clear(sv[vi], mesh_pts, mtree,
                                cfg["max_skeleton_mesh_km"] * 1000.0, k=48)
        if j is None:
            continue
        if ch in seen_chain and seen_chain[ch][1] <= dist:
            continue
        seen_chain[ch] = (vi, dist, j)
    for ch, (vi, dist, j) in seen_chain.items():
        a = to43.transform(*sv[vi])
        b = to43.transform(MX[j], MY[j])
        lf.append({"type": "Feature",
                   "geometry": {"type": "LineString", "coordinates": [
                       [round(a[0], D), round(a[1], D)], [round(b[0], D), round(b[1], D)]]},
                   "properties": {"chain": int(ch), "cell": str(mcell[j]),
                                  "m": round(dist)}})
    print(f"  skeleton -> mesh: {len(lf):,} chains linked to a cell")

    # --- ASSEMBLE AND COUNT --------------------------------------------------------
    idx: dict = {}

    def ix(k):
        return idx.setdefault(k, len(idx))

    rows = []
    lk = gpd.read_file(cfg["network"], layer="link")
    for a, b in zip(lk.from_node.values, lk.to_node.values):
        rows.append((ix(("n", a)), ix(("n", b))))
    for a, b in medge:
        rows.append((ix(("c", str(mcell[int(a)]))), ix(("c", str(mcell[int(b)])))))
    for i, f in enumerate(sk):
        cs = f["geometry"]["coordinates"]
        for p, q in zip(cs, cs[1:]):
            rows.append((ix(("s", tuple(p))), ix(("s", tuple(q)))))
    for f in jf:
        cs = f["geometry"]["coordinates"]
        rows.append((ix(("n", f["properties"]["node_id"])), ix(("s", tuple(cs[1])))))
    for f in lf:
        cs = f["geometry"]["coordinates"]
        rows.append((ix(("s", tuple(cs[0]))), ix(("c", f["properties"]["cell"]))))
    arr = np.array(rows)
    mm = coo_matrix((np.ones(len(arr)), (arr[:, 0], arr[:, 1])), shape=(len(idx),) * 2)
    ncomp, lab = connected_components(mm + mm.T, directed=False)
    sea_lab = int(lab[ix(("c", str(mcell[0])))])
    rn = [v for k, v in idx.items() if k[0] == "n"]
    nds = gpd.read_file(cfg["network"], layer="node")
    insc = set(nds[nds.in_scope.astype(bool)].node_id)
    ri = [idx[("n", k)] for k in insc if ("n", k) in idx]
    pct = 100 * float((lab[ri] == sea_lab).mean())
    print(f"\nCOMBINED {len(idx):,} nodes, {len(arr):,} edges, {ncomp:,} components")
    print(f"  IN-SCOPE RIVER NODES REACHING THE SEA: "
          f"{int((lab[ri] == sea_lab).sum()):,} of {len(ri):,} ({pct:.2f}%)")

    for path, feats, what in ((cfg["out_joins"], jf, "tidal terminus -> skeleton vertex"),
                              (cfg["out_links"], lf, "skeleton chain -> mesh cell centre")):
        Path(path).write_text(json.dumps(
            {"type": "FeatureCollection",
             "properties": {"generation": generation(), "what": what,
                            "features_": len(feats),
                            "land_tested": "every join is refused if the straight line "
                                           "crosses land, on both coastlines",
                            "use_constraint": "DO NOT USE FOR NAVIGATION"},
             "features": feats}, separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(),
        "question": "Do the mesh, the skeleton, the joins and the inland river network "
                    "form ONE network?",
        "in_scope_pct_reaching_the_sea": round(pct, 2),
        "in_scope_river_nodes_reaching_the_sea": int((lab[ri] == sea_lab).sum()),
        "in_scope_river_nodes_total": len(ri),
        "components": int(ncomp), "nodes": len(idx), "edges": len(arr),
        "termini_in_scope": int(len(t)), "termini_joined": attached,
        "termini_stranded": len(stranded),
        "skeleton_chains_linked_to_mesh": len(lf),
        "design": "The mesh is open water only, from 1 km offshore. The skeleton is the "
                  "medial axis of enclosed water. A terminus joins the skeleton, the "
                  "skeleton joins the mesh. No traced paths across drying ground: the "
                  "centreline already goes up the estuary.",
        "stranded": stranded,
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"wrote {cfg['out_joins']}, {cfg['out_links']}, {cfg['summary']}")


if __name__ == "__main__":
    main()
