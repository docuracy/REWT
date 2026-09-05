"""The open-water mesh: one resolution, cells whose centres are in open water.

SUPERSEDES `grid2.py`. Stephen's ruling after the skeleton proved out: the multi-resolution
banding is no longer buying anything, and the mesh should cover OPEN WATER ONLY, with the
skeleton taking the enclosed water it was built for.

**The banding was already vestigial.** grid2 produced 143,879 cells of which 142,115 — 98.8%
— were res 7. The rest was 315 res-6 blind hops and 1,449 res-8/9 cells refined for
estuaries, which is precisely the work the medial axis now does better.

**WHERE OPEN WATER STARTS IS THE SKELETON'S NUMBER, NOT A GUESS.** PLAN.md 51 measured the
medial-axis clearance: a median 290 m at Plymouth and 338 m at Sheppey against 1,633 m on the
open coast at Kimmeridge, with a 1 km threshold keeping ~76% of the enclosed cases and 44% of
the open one. So 1 km is where the skeleton stops being about a channel — and it is where the
mesh starts. Measured on the old grid, cutting there keeps 96.9% of cells and leaves the
largest component at 99.8%.

**ONE CONSEQUENCE, STATED.** The skeleton is GB-only, because OS is the source that exists.
Cutting at 1 km everywhere therefore leaves the near-shore strip of Ireland, France and
Norway served by neither. Those coasts are outside the England-and-Wales basins this project
routes for, the mesh still runs along them a kilometre out, and the alternative — a mesh that
reaches the shore in some countries and not others — would be a worse thing to explain.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import numpy as np
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely import STRtree, points

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adjacency import build_pairs                      # noqa: E402
from generation import generation                      # noqa: E402
from landtest import land_crossing_test, land_polygons, os_coastline   # noqa: E402

CONFIG = {
    "masks": "tools/router/cache/sightline_masks.npz",
    "out": "tools/router/cache/mesh.npz",
    "summary": "docs/router/data/mesh_summary.json",
    "resolution": 7,          # single band; 2.44 km between cell centres
    "min_clearance_km": 1.0,  # where the skeleton stops being about a channel
}


def main(cfg: dict = CONFIG) -> None:
    m = np.load(cfg["masks"], allow_pickle=True)
    crs = str(m["crs"][0])
    tr = m["fine_transform"]
    fine_sea = m["fine_sea"]
    keep_px, cvis, ctr = m["keep"], m["visible"], m["transform"]
    fh, fw = fine_sea.shape
    R = cfg["resolution"]

    # kept sea at its own resolution, mapped up to the 930 m trim decision
    ys, xs = np.nonzero(fine_sea)
    X = tr[2] + (xs + 0.5) * tr[0]
    Y = tr[5] + (ys + 0.5) * tr[4]
    col = np.clip(((X - ctr[2]) / ctr[0]).astype(np.int32), 0, keep_px.shape[1] - 1)
    row = np.clip(((Y - ctr[5]) / ctr[4]).astype(np.int32), 0, keep_px.shape[0] - 1)
    sel = keep_px[row, col]
    print(f"kept sea: {int(sel.sum()):,} px of {len(ys):,} at "
          f"{abs(float(tr[0])):.0f} m")

    back = Transformer.from_crs(crs, 4326, always_xy=True)
    lon, lat = back.transform(X[sel], Y[sel])
    cells = np.array([h3.latlng_to_cell(float(a), float(b), R) for a, b in zip(lat, lon)])
    uniq = np.unique(cells)
    print(f"  {len(uniq):,} res-{R} cells hold kept sea")

    # --- CENTRES: in water, and out in open water ---------------------------------
    ll = np.array([h3.cell_to_latlng(c) for c in uniq])
    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    CX, CY = fwd.transform(ll[:, 1], ll[:, 0])
    c_ = ((CX - tr[2]) / tr[0]).astype(int)
    r_ = ((CY - tr[5]) / tr[4]).astype(int)
    ok = (r_ >= 0) & (r_ < fh) & (c_ >= 0) & (c_ < fw)
    in_water = np.zeros(len(uniq), bool)
    in_water[ok] = fine_sea[r_[ok], c_[ok]]
    print(f"  centre in water: {int(in_water.sum()):,} "
          f"({int((~in_water).sum()):,} dropped — the cell held sea, the node did not)")

    tree = STRtree(land_polygons(cfg["masks"])[0] + os_coastline(crs))
    pts = points(np.column_stack([CX, CY]))
    d = np.array([tree.geometries[tree.nearest(p)].distance(p) for p in pts]) / 1000.0
    open_water = in_water & (d >= cfg["min_clearance_km"])
    print(f"  centre >= {cfg['min_clearance_km']:.1f} km from land: "
          f"{int(open_water.sum()):,} ({int((in_water & ~open_water).sum()):,} inshore "
          f"cells left to the skeleton)")
    cells_keep = uniq[open_water]

    # --- adjacency, one definition, and drop what it cannot reach -----------------
    crosses = land_crossing_test(cfg["masks"])
    res_map = {c: R for c in cells_keep}
    pair_ids, _cr, blocked = build_pairs(res_map, crosses, R, R)
    pos = {c: i for i, c in enumerate(cells_keep)}
    e = np.array(sorted({(pos[a], pos[b]) for a, b in pair_ids}), dtype=np.int32)
    print(f"  {len(e):,} links; {blocked:,} directed refused for crossing land")
    mat = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(cells_keep),) * 2)
    n, lab = connected_components(mat + mat.T, directed=False)
    sizes = np.bincount(lab)
    main_c = int(np.argmax(sizes))
    keep2 = lab == main_c
    print(f"  {n} components; dropping {int((~keep2).sum()):,} cells outside the largest "
          f"({100*sizes[main_c]/len(cells_keep):.2f}%)")
    final = cells_keep[keep2]
    remap = {c: i for i, c in enumerate(final)}
    e2 = np.array([[remap[cells_keep[a]], remap[cells_keep[b]]] for a, b in e
                   if keep2[a] and keep2[b]], dtype=np.int32)
    fll = np.array([h3.cell_to_latlng(c) for c in final])

    R_E = 6371000.0
    la, lo = np.radians(fll[:, 0]), np.radians(fll[:, 1])
    xyz = np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    length = np.linalg.norm(xyz[e2[:, 0]] - xyz[e2[:, 1]], axis=1) * R_E

    np.savez_compressed(cfg["out"], cell=final, lat=fll[:, 0], lon=fll[:, 1],
                        edge=e2, length_m=length.astype("float32"),
                        clearance_km=d[open_water][keep2].astype("float32"))
    m2 = coo_matrix((np.ones(len(e2)), (e2[:, 0], e2[:, 1])), shape=(len(final),) * 2)
    ncomp2 = connected_components(m2 + m2.T, directed=False)[0]
    deg = np.bincount(e2.ravel(), minlength=len(final))
    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(),
        "what": "The open-water mesh: one resolution, cells whose centres are in open water.",
        "supersedes": "grid2.py's multi-resolution banding, which was 98.8% res 7 already. "
                      "Estuaries are the skeleton's work now.",
        "h3_resolution": R,
        "centre_to_centre_km": round(h3.average_hexagon_edge_length(R, unit="km") * 3 ** .5, 2),
        "min_clearance_km": cfg["min_clearance_km"],
        "clearance_basis": "PLAN.md 51: medial-axis clearance is a median 290 m at Plymouth "
                           "and 338 m at Sheppey against 1,633 m on the open coast, so 1 km "
                           "is where the skeleton stops being about a channel.",
        "cells": len(final), "links": int(len(e2)),
        "components": int(ncomp2), "isolated": int((deg == 0).sum()),
        "links_refused_crossing_land": int(blocked),
        "gb_only_skeleton_note": "The skeleton is GB-only, so cutting at 1 km everywhere "
                                 "leaves the near-shore strip of Ireland, France and Norway "
                                 "served by neither. Those coasts are outside the basins "
                                 "this project routes for.",
        "attribution": "Contains EMODnet Bathymetry data, CC BY 4.0. Contains OS data "
                       "(c) Crown copyright and database right, OGL v3.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"\nMESH {len(final):,} cells, {len(e2):,} links, {ncomp2} component(s), "
          f"{int((deg == 0).sum())} isolated")
    print(f"wrote {cfg['out']} and {cfg['summary']}")


if __name__ == "__main__":
    main()
