"""The sea grid, banded by what a cell IS rather than by how far it is from something.

    python3 tools/router/grid2.py

Run from the repository root; paths are relative (AGENTS.md).

WHY THIS REPLACES THE DISTANCE BANDING. The recursion in grid.py made the far ocean
cheap by coarsening with distance from the coast. **The trim removed the far field**: no
kept cell lies further from land than the sightline reach plus the blind-sailing buffer,
about 199 km, and 58% of the kept surface is in sight. Built over the option C extent the
old scheme produced 695,855 cells of which 604,606 — 87% — were the single finest band.
That is almost all of the cost, spent on a fringe, to encode a distance that no longer
means anything.

THREE STATES, each of which means something (Stephen, 4 September 2026):

    blind buffer          res 6   out of sight of land; kept so a crossing can be made
    in sight, open water  res 7   the working surface
    coastal and estuarine res 8, then 9

AND THE REFINEMENT IS DRIVEN BY THE REQUIREMENT, not by a radius: a cell is subdivided
only where it is ADJACENT TO LAND *and* REQUIRED BY A JOIN OR A TRACE. "Within one cell
of land" would refine open cliff coast that needs no detail; "within N km" is
distance-banding again in a different hat. Refining only where it buys an attachment is
self-limiting, and it stops on its own when nothing more is bought.

NOT A CHART. conf/sources.yml carries DO NOT USE FOR NAVIGATION and it travels.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy import ndimage

import h3
from generation import generation

from adjacency import build_pairs
from landtest import land_crossing_test

CONFIG = {
    "masks": "tools/router/cache/sightline_masks.npz",
    "network": "published/rewt_stage1_network.gpkg",
    "scope_max_m_from_ew": 1000.0,   # see the scope note in main()
    "out": "tools/router/cache/grid2.npz",
    "summary": "docs/router/data/grid_summary.json",
    "res_blind": 6,
    "res_sight": 7,
    "res_refine": [8, 9],      # in order; the loop stops early if nothing is bought
}
ATTRIBUTION = ("Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium (2024): "
               "EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.")


def cells_for(lat, lon, res):
    return np.array([h3.latlng_to_cell(float(a), float(b), res) for a, b in zip(lat, lon)])


def main(cfg: dict = CONFIG) -> None:
    m = np.load(cfg["masks"], allow_pickle=True)
    crs = str(m["crs"][0])
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    # THE SEA AT ITS OWN RESOLUTION, the sightline's at its. Reading `keep` off the
    # 930 m envelope grid put every unattached terminus 3-67 km from the nearest sea
    # pixel — because at 930 m the estuaries are not there to be near.
    fine_sea = m["fine_sea"]
    tr = m["fine_transform"]
    px = float(m["fine_px"][0])
    ctr, cvis, ckeep = m["transform"], m["visible"], m["keep"]
    fh, fw = fine_sea.shape
    rr, cc = np.mgrid[0:fh, 0:fw]
    x = ctr[2] * 0 + tr[2] + (cc + 0.5) * tr[0] + (rr + 0.5) * tr[1]
    y = tr[5] + (cc + 0.5) * tr[3] + (rr + 0.5) * tr[4]
    ccol = ((x - ctr[2]) / ctr[0]).astype(np.int32)
    crow = ((y - ctr[5]) / ctr[4]).astype(np.int32)
    ok = (crow >= 0) & (crow < cvis.shape[0]) & (ccol >= 0) & (ccol < cvis.shape[1])
    ccol = np.clip(ccol, 0, cvis.shape[1] - 1); crow = np.clip(crow, 0, cvis.shape[0] - 1)
    keep = fine_sea & ok & ckeep[crow, ccol]
    visible = fine_sea & ok & cvis[crow, ccol]
    land = (~fine_sea) & ok
    del rr, cc, x, y, ccol, crow, ok
    print(f"sea {fine_sea.shape} at {px:.0f} m, sight upsampled from "
          f"{cvis.shape} at {float(m['px'][0]):.0f} m")
    print(f"  kept {int(keep.sum()):,} sea px, {int((keep & visible).sum()):,} in sight")

    def lonlat(rows, cols):
        x = tr[2] + (cols + 0.5) * tr[0] + (rows + 0.5) * tr[1]
        y = tr[5] + (cols + 0.5) * tr[3] + (rows + 0.5) * tr[4]
        return back.transform(x, y)

    # --- base: one resolution per state ------------------------------------------
    kr, kc = np.nonzero(keep)
    klon, klat = lonlat(kr, kc)
    kvis = visible[kr, kc]
    # one sea lookup, from the SAME fine mask the link test reads and at the same
    # resolution the estuaries actually exist at
    _fwd = Transformer.from_crs(4326, crs, always_xy=True)
    _fh, _fw = fine_sea.shape

    def sea_at(la, lo) -> bool:
        x, y = _fwd.transform(lo, la)
        c = int((x - tr[2]) / tr[0]); r = int((y - tr[5]) / tr[4])
        return bool(0 <= r < _fh and 0 <= c < _fw and fine_sea[r, c])

    print("binning kept sea to base cells...")
    base = {}
    for res, sel in ((cfg["res_sight"], kvis), (cfg["res_blind"], ~kvis)):
        cs = cells_for(klat[sel], klon[sel], res)
        for c in np.unique(cs):
            base[c] = res
    # A NODE WHOSE CENTRE IS ON LAND IS NOT A NODE. A cell is created because it CONTAINS
    # kept sea, which is right for a cell and wrong for the point that represents it: the
    # routing node is the centre, joins attach to the centre, and eRutter's travelling
    # surface is centre to centre. Stephen found res-7 cells off Portland whose centres sit
    # inland, and the joins reaching them were reaching across a beach. 284 of 142,976.
    # The land test already existed for LINKS; this is the same rule applied to the node
    # the links run between.
    centre_on_land = [c for c in base if not sea_at(*h3.cell_to_latlng(c))]
    for c in centre_on_land:
        del base[c]
    print(f"  dropped {len(centre_on_land):,} base cells whose CENTRE is on land "
          f"(the cell held sea; the node did not)")
    print(f"  base: {len(base):,} cells "
          f"({sum(1 for v in base.values() if v == cfg['res_sight']):,} in sight at res "
          f"{cfg['res_sight']}, {sum(1 for v in base.values() if v == cfg['res_blind']):,} "
          f"blind at res {cfg['res_blind']})")

    # which cells hold land? only land NEAR kept sea can matter, so dilate and mask
    near = ndimage.binary_dilation(keep, iterations=4)   # ~1 km at this pixel
    lr, lc = np.nonzero(land & near)
    llon, llat = lonlat(lr, lc)
    land_at = {r: set(cells_for(llat, llon, r).tolist())
               for r in {cfg["res_blind"], cfg["res_sight"], *cfg["res_refine"]}}
    print(f"  {len(lr):,} land px next to kept sea")

    # --- the termini the refinement serves ---------------------------------------
    node = gpd.read_file(cfg["network"], layer="node", ignore_geometry=True,
                         columns=["node_id", "terminus", "in_scope", "easting", "northing"])
    link = gpd.read_file(cfg["network"], layer="link", ignore_geometry=True,
                         columns=["from_node", "to_node", "retired"])
    live = link[~link.retired.astype(bool)]
    sinks = set(live.to_node.dropna()) - set(live.from_node.dropna())
    t = node[node.node_id.isin(sinks) & (node.terminus == "tidal")].copy()

    # SCOPE: basins that intersect England or Wales, which is what this project is about
    # (D-024, and Stephen 4 Sep 2026 — traces were being computed into northern Scotland).
    # `in_scope` is the audit's own derivation; `basin_in_scope` is only half the rule and
    # gives a different answer, so the implementer's instruction is to use `in_scope`.

    # SCOPE, AND WHY IT IS NOT JUST `in_scope` (Stephen, 4 September 2026)
    #
    # D-024 puts a basin in scope ENTIRE if any part of it lies in England or Wales, and
    # that rule is right: a river system should not be cut at a border. But two basins
    # are not catchments. `River Earn` runs from Northumberland to Montrose and `River
    # Nith` holds the Duddon Channel and the Isle of Bute — rewt-46's D-080 — and 4.0%
    # and 8.2% of them respectively lie in England, which puts the whole of both in
    # scope. Traces were being computed into northern Scotland.
    #
    # THE TEST IS GEOMETRIC AND IT IS NOT POINT-IN-POLYGON. A tidal terminus sits
    # SEAWARD of the high water line by definition, and the country polygon is bounded by
    # that line, so a plain containment test rejects the very features it should keep:
    # 194 of 474 fall outside England and Wales, and most are in basins 99-100% English.
    #
    # DISTANCE, and the threshold barely matters. Measured over the 474: median 0 m,
    # 75th percentile 10 m, then a JUMP to 95.75 km at the 90th. Nothing lies between
    # 10 m and 96 km. Everything beyond 20 km is the Nith (61) or the Earn (19) and
    # nothing else. Any cut from 1 km to 90 km gives the same answer, which is what a
    # real boundary looks like as against a tuned one. 1 km is a hundred times the
    # observed offset of a legitimate terminus.
    #
    # THIS DOES NOT FIX THE BASINS, and must not be mistaken for it. The delineation is
    # the implementer's and D-080 is still open; this is a geometric guard so the router
    # does not publish traces up the Tay while that stands.
    before = len(t)
    t = t[t.in_scope.astype(bool)].copy()
    _bl = "data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg"
    _cr = gpd.read_file(_bl, layer="country_region")
    from shapely.ops import unary_union as _uu
    from shapely.geometry import Point as _P
    _ew = _uu(_cr[_cr.Name.isin(["England", "Wales"])].geometry.values)
    _d = np.array([_P(x, y).distance(_ew) for x, y in zip(t.easting, t.northing)])
    t = t[_d <= cfg["scope_max_m_from_ew"]].copy()
    print(f"  scope: {len(t):,} of {before:,} tidal termini — in an England/Wales basin "
          f"AND within {cfg['scope_max_m_from_ew']/1000:.0f} km of England or Wales")
    f4326 = Transformer.from_crs(27700, 4326, always_xy=True)
    t["lon"], t["lat"] = f4326.transform(t.easting.values, t.northing.values)
    print(f"  {len(t):,} tidal termini to serve")

    def attached(cellset):
        """Which termini sit in, or next to, a cell of the grid?"""
        out = np.zeros(len(t), bool)
        for i, (la, lo) in enumerate(zip(t.lat.values, t.lon.values)):
            for r in sorted({v for v in cellset.values()}, reverse=True):
                own = h3.latlng_to_cell(float(la), float(lo), r)
                if own in cellset or any(c in cellset for c in h3.grid_disk(own, 1)):
                    out[i] = True
                    break
        return out

    grid = dict(base)
    sea_at: dict[int, set] = {}
    att = attached(grid)
    print(f"  base grid attaches {int(att.sum()):,} of {len(t):,} termini "
          f"({100*att.mean():.1f}%)")

    # --- refine where a cell HOLDS LAND and is USED BY A JOIN ----------------------
    # REFINEMENT CANNOT ATTACH A TERMINUS, and the first version of this loop assumed it
    # could. A cell is admitted if it holds any kept sea; its children are admitted on
    # the same test, so their union is a SUBSET of the parent. Subdividing never extends
    # the grid's footprint, only its granularity — so it bought nothing, correctly, and
    # the criterion was aimed at the wrong thing.
    #
    # What it buys is FIDELITY. A 2.8 km cell spanning an estuary mouth and the land
    # beside it lets a route cut across the shore. So: a cell is refined where it HOLDS
    # LAND *and* is the cell a join attaches to — which is where the shore actually has
    # to be right, and nowhere else.
    for r in cfg["res_refine"]:
        want = set()
        for i in range(len(t)):
            la, lo = float(t.lat.values[i]), float(t.lon.values[i])
            for rr in sorted({v for v in grid.values()}, reverse=True):
                own = h3.latlng_to_cell(la, lo, rr)
                for c in [own, *h3.grid_disk(own, 1)]:
                    if grid.get(c) == rr and c in land_at.get(rr, ()):
                        want.add(c)                 # holds land AND a join uses it
        if not want:
            print(f"  res {r}: nothing to refine — the criterion bought nothing, stopping")
            break
        # subdivide, then keep only the children that actually hold kept sea. The
        # membership set is computed once per resolution, not once per parent.
        if r not in sea_at:
            sea_at[r] = set(np.unique(cells_for(klat, klon, r)).tolist())
        for c in want:
            del grid[c]
            for ch in h3.cell_to_children(c, r):
                if ch in sea_at[r]:
                    grid[ch] = r
        att = attached(grid)
        print(f"  res {r}: refined {len(want):,} cells -> {sum(1 for v in grid.values() if v == r):,} "
              f"kept children; attaches {int(att.sum()):,} of {len(t):,} "
              f"({100*att.mean():.1f}%)")

    # --- DROP WHAT IS NOT CONNECTED TO THE SEA NETWORK ----------------------------
    # Stephen saw a scattering of detached cells in the Netherlands. A cell that no route
    # can reach is not part of a routing surface, whatever the mask says — the same
    # question the river network asks of itself, asked of the grid.
    # A LINK THAT CROSSES LAND IS NOT A LINK. This used to ask bare grid_disk, while
    # edges.py asked grid_disk AND the land test — so 220 cells whose every neighbour
    # lay across a spit survived this pass and were isolated by the next. One test,
    # imported, so the two cannot drift again.
    print("building adjacency to find what is detached (links may not cross land)...")
    crosses_land = land_crossing_test(cfg["masks"])
    ids = list(grid)
    pos = {c: i for i, c in enumerate(ids)}
    R0 = min(grid.values())
    pair_ids, _cr, blocked = build_pairs(grid, crosses_land, R0, max(grid.values()))
    pairs = {(pos[a_], pos[b_]) for a_, b_ in pair_ids}
    e = np.array(sorted(pairs), dtype=np.int32) if pairs else np.zeros((0, 2), np.int32)
    print(f"  {blocked:,} directed links refused for crossing land "
          f"({100*blocked/max(blocked+2*len(e),1):.2f}%)")
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    mat = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(ids),) * 2)
    ncomp, lab = connected_components(mat, directed=False)
    csizes = np.bincount(lab)
    main = int(np.argmax(csizes))
    drop = [i for i in range(len(ids)) if lab[i] != main]
    print(f"  {ncomp} components; the largest holds {csizes[main]:,} of {len(ids):,} "
          f"({100*csizes[main]/len(ids):.2f}%)")
    if drop:
        order = np.argsort(-csizes)
        print(f"  dropping {len(drop):,} cells in {ncomp-1} detached pieces. The largest:")
        for k in order[1:6]:
            j = int(np.nonzero(lab == k)[0][0])
            la, lo = h3.cell_to_latlng(ids[j])
            print(f"    {csizes[k]:>6,} cells around {la:.2f} N {lo:.2f} E")
        for i in drop:
            del grid[ids[i]]

    by_res = {}
    for v in grid.values():
        by_res[v] = by_res.get(v, 0) + 1
    print(f"\nTOTAL {len(grid):,} cells")
    for k in sorted(by_res):
        print(f"  res {k:>2}: {by_res[k]:>9,}")
    print(f"  against the distance-banded grid over the same extent: 695,855")

    ids = list(grid)
    ll = np.array([h3.cell_to_latlng(c) for c in ids])
    # DEPTH AT EACH CELL CENTRE. The old grid carried it and join.py reads it; omitting it
    # here made join.py die on its first use — and trace.py then ran on the STALE join
    # summary and reported figures from the previous grid as though they were new. A
    # stage that fails should not be silently absorbed by the next one.
    cel = m["elev"]
    ctr2 = m["transform"]
    fx, fy = Transformer.from_crs(4326, crs, always_xy=True).transform(ll[:, 1], ll[:, 0])
    cc2 = np.clip(((np.asarray(fx) - ctr2[2]) / ctr2[0]).astype(int), 0, cel.shape[1] - 1)
    cr2 = np.clip(((np.asarray(fy) - ctr2[5]) / ctr2[4]).astype(int), 0, cel.shape[0] - 1)
    depth = cel[cr2, cc2]
    np.savez_compressed(cfg["out"], cell=np.array(ids),
                        resolution=np.array([grid[c] for c in ids], "int8"),
                        lat=ll[:, 0], lon=ll[:, 1], depth_m=depth)
    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(), "scheme": "banded by state, not by distance",
        "states": {"blind buffer": cfg["res_blind"], "in sight": cfg["res_sight"],
                   "refined": cfg["res_refine"]},
        "refinement_rule": "a cell is subdivided only where it is adjacent to land AND "
                           "required by a join or a trace — not within N km of anything",
        "total_cells": len(grid),
        "by_resolution": {str(k): v for k, v in sorted(by_res.items())},
        "termini_attached": int(att.sum()), "termini": int(len(t)),
        "detached_cells_dropped": len(drop),
        "components_before_drop": int(ncomp),
        "superseded": "the distance-banded grid gave 695,855 cells over this extent, "
                      "87% of them in the single finest band",
        "attribution": ATTRIBUTION, "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"wrote {cfg['out']} and {cfg['summary']}")


if __name__ == "__main__":
    main()
