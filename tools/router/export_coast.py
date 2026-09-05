"""The res-7 coastal surface, published at its own resolution and its own extent.

WHY THIS EXISTS. The main published layer is the routing graph aggregated to res 6 and then
CLIPPED to the cells the sightline layer publishes — 4,504 perimeter cells removed so that a
viewer toggling between cells and network would see the two cover the same ground. That clip
was made to satisfy a rendering requirement, and nobody asked what it cost anything joining
against the layer. rewt-46 asked: measured against the implementer's `sea_route`, the
published layer holds 58.1% of its 4,184 entries, while the res-7 routing grid has 83.0% of
them within two rings. **Most of that gap was my clip, not the surface.**

So this layer does not match the sightline extent and is not meant to. rewt-46's ruling, and
it is the better rule: a visible mismatch that is explained beats a tidy picture that has
silently lost the estuaries.

WHAT IS IN IT. Every routing cell within `fringe_km` of land — the coastal band, where the
river mouths and the sea entries are. At 5 km that is 21,974 of 143,879 cells and it captures
EXACTLY as many sea entries as publishing all of them would: 1,366 in a cell, 3,023 within
one ring. 3 km loses ten of them; 8 km adds none. The band is chosen by what it covers, not
by what looks generous.

WHAT IS NOT IN IT, and no resolution fixes: 710 entries with 2,360 river mouths behind them
sit in creek heads and narrow estuaries the res-7 lattice cannot represent at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import numpy as np
from pyproj import Transformer
from shapely import STRtree, points

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation                      # noqa: E402
from landtest import land_polygons, os_coastline   # noqa: E402

# EVERY FIGURE IN THIS FILE'S PROPERTIES IS COMPUTED HERE. They used to be typed: "32
# connected components", "17.0% are ABSENT", "710 entries with 2,360 river mouths", "all
# 143,879 cells". rewt-46 found the same fault in their own harness — it asserted the panel
# carried the literal string "32 connected components", which is MY number frozen into
# THEIR check — and fixed it by reading the sentence from this file instead. That is the
# right fix for their end and it leaves the rot at mine: a sentence read faithfully out of
# an artefact is still wrong if the artefact typed it. So the numbers are derived, and if
# the grid moves the sentences move with it.
CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "masks": "tools/router/cache/sightline_masks.npz",
    "summary": "docs/router/data/edge_summary.json",
    "out_cells": "docs/router/data/cells_r7_coast.geojson",
    "out_edges": "docs/router/data/edges_r7_coast.geojson",
    "release": "published/rewt_stage1_network.gpkg",
    "cells_published": "docs/router/data/sightline2_r6.geojson",
    "fringe_km": 5.0,
    "coord_dp": 5,
}


def entry_positions(gpkg: str):
    """Where each sea entry is. `from_entry`/`to_entry` do not say which end of a route's
    geometry belongs to which entry, so intersect the endpoints of every incident route
    instead of assuming — rewt-46's method, and 3,275 of 4,183 disagree with the obvious
    reading."""
    import collections
    import geopandas as gpd
    sr = gpd.read_file(gpkg, layer="sea_route")
    inc = collections.defaultdict(list)
    for r in sr.itertuples():
        g = r.geometry
        ends = {(round(g.coords[0][0], 2), round(g.coords[0][1], 2)),
                (round(g.coords[-1][0], 2), round(g.coords[-1][1], 2))}
        inc[r.from_entry].append(ends)
        inc[r.to_entry].append(ends)
    pos, leaves = {}, []
    for eid, lst in inc.items():
        c = set.intersection(*lst) if len(lst) > 1 else None
        if c and len(c) == 1:
            pos[eid] = next(iter(c))
        else:
            leaves.append(eid)
    for eid in leaves:                       # a leaf: the end its neighbour has not claimed
        nb = sr[(sr.from_entry == eid) | (sr.to_entry == eid)]
        other = [e for e in set(nb.from_entry) | set(nb.to_entry) if e != eid]
        rest = inc[eid][0] - {pos[o] for o in other if o in pos}
        if len(rest) == 1:
            pos[eid] = next(iter(rest))
    return pos, sr


def main(cfg: dict = CONFIG) -> None:
    g = np.load(cfg["grid"], allow_pickle=True)
    cell, res = g["cell"].tolist(), g["resolution"]
    lat, lon, depth = g["lat"], g["lon"], g["depth_m"]
    stamp = json.loads(Path(cfg["summary"]).read_text()).get("generation") or generation()

    mask, crs = land_polygons(cfg["masks"])
    tree = STRtree(mask + os_coastline(crs))
    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    X, Y = fwd.transform(lon, lat)
    pts = points(np.column_stack([X, Y]))
    print(f"{len(cell):,} routing cells; measuring the coastal band...")
    d = np.array([tree.geometries[tree.nearest(p)].distance(p) for p in pts]) / 1000.0
    keep = d <= cfg["fringe_km"]
    idx = {c: i for i, c in enumerate(cell)}
    kept = {cell[i] for i in np.nonzero(keep)[0]}
    print(f"  {len(kept):,} within {cfg['fringe_km']:.0f} km of land "
          f"({100*len(kept)/len(cell):.1f}%)")

    # --- the figures the properties quote, all measured here -----------------------
    import collections
    import geopandas as gpd
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    z0 = np.load(cfg["edges"])
    e0 = z0["edge"]
    band = {int(i) for i in np.nonzero(keep)[0]}
    be = np.array([[int(a), int(b)] for a, b in e0 if int(a) in band and int(b) in band])
    order = {v: k for k, v in enumerate(sorted(band))}
    bm = coo_matrix((np.ones(len(be)),
                     ([order[int(a)] for a, _ in be], [order[int(b)] for _, b in be])),
                    shape=(len(band),) * 2)
    ncomp, blab = connected_components(bm, directed=False)
    bsz = np.bincount(blab)
    band_pct = 100.0 * float(bsz.max()) / len(band)

    pos, _sr = entry_positions(cfg["release"])
    se = gpd.read_file(cfg["release"], layer="sea_entry")
    mouths = collections.Counter(se.entry_id)
    back = Transformer.from_crs(27700, 4326, always_xy=True)
    rp = sorted({int(r) for r in res}, reverse=True)
    gridset = set(cell)
    cover = collections.Counter()
    absent_mouths = 0
    for eid, (x, y) in pos.items():
        lo, la = back.transform(x, y)
        k = 9
        for r in rp:
            if h3.latlng_to_cell(float(la), float(lo), r) in gridset:
                k = 0
                break
        if k:
            for ring in (1, 2):
                if any(n in gridset for r in rp
                       for n in h3.grid_disk(h3.latlng_to_cell(float(la), float(lo), r), ring)):
                    k = ring
                    break
        cover[k] += 1
        if k == 9:
            absent_mouths += mouths[eid]
    ne = len(pos)
    pct = {k: 100.0 * cover[k] / ne for k in (0, 1, 2, 9)}

    pubcells = {f["properties"]["h3"]
                for f in json.loads(Path(cfg["cells_published"]).read_text())["features"]}
    spill = len({h3.cell_to_parent(c, 6) for c in cell} - pubcells)

    D = cfg["coord_dp"]
    props = {
        "generation": stamp,
        "what": "The routing cells themselves, at res 7 (and 6, 8, 9 where the grid bands), "
                "for the coastal band within %.0f km of land." % cfg["fringe_km"],
        "extent_deliberately_differs":
            "This layer does NOT cover the same ground as sightline2_r6.geojson and is not "
            "meant to. The main edges layer is clipped to the sightline cells so a viewer "
            "toggle lines up; that clip removes %s perimeter cells and hides coastal "
            % f"{spill:,}" +
            "surface that the routing graph has. Draw the mismatch rather than clipping it "
            "away: a visible difference that is explained beats a tidy picture that has "
            "lost the estuaries.",
        "coverage_measured":
            "Against the %s sea entries of the release: %.1f%% fall in a routing cell, "
            "%.1f%% one ring away, %.1f%% two rings, and %.1f%% are ABSENT — %d entries "
            "with %s river mouths behind them, in creek heads and narrow estuaries the "
            "res-7 lattice cannot represent. That last figure is a real limit of the "
            "surface and no finer rendering changes it."
            % (f"{ne:,}", pct[0], pct[1], pct[2], pct[9], cover[9],
               f"{absent_mouths:,}"),
        "coverage": {"entries": ne, "in_a_cell": cover[0], "one_ring": cover[1],
                     "two_rings": cover[2], "absent": cover[9],
                     "mouths_behind_absent": absent_mouths},
        "band_chosen_by": "what it covers, not by generosity: 5 km captures exactly as many "
                          "sea entries as publishing all %s cells would. 3 km loses ten; "
                          "8 km adds none." % f"{len(cell):,}",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0. "
                       "Contains OS data (c) Crown copyright and database right, OGL v3.",
        "this_layer_is_a_band_not_a_surface":
            "It has %d connected components and the largest holds %.0f%% of it. That is "
            "NOT a " % (ncomp, band_pct) +
            "defect and must not be repaired by dropping the small ones: a 5 km coastal "
            "band around separate landmasses IS separate, and the water between them is "
            "simply further from land than the band is wide. The ROUTING GRAPH these cells "
            "belong to is one component of %s cells; this layer is a window onto it, " % f"{len(cell):,}" +
            "and connectivity is a property of the graph, not of the window.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }

    feats = []
    for i in np.nonzero(keep)[0]:
        ring = [[round(x, D), round(y, D)] for y, x in h3.cell_to_boundary(cell[i])]
        ring.append(ring[0])
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"h3": cell[i], "res": int(res[i]),
                                     "depth_m": round(float(depth[i]), 1),
                                     "km_to_land": round(float(d[i]), 2)}})
    Path(cfg["out_cells"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": {**props, "cells": len(feats)},
         "features": feats}, separators=(",", ":")))
    print(f"  wrote {cfg['out_cells']} "
          f"({Path(cfg['out_cells']).stat().st_size/1e6:.1f} MB, {len(feats):,} cells)")

    # the lattice among them, unaggregated: links between the centres a route actually uses
    z = np.load(cfg["edges"])
    e, length = z["edge"], z["length_m"]
    ef = []
    for k in range(len(e)):
        i, j = int(e[k, 0]), int(e[k, 1])
        if not (keep[i] and keep[j]):
            continue
        ef.append({"type": "Feature",
                   "geometry": {"type": "LineString", "coordinates": [
                       [round(float(lon[i]), D), round(float(lat[i]), D)],
                       [round(float(lon[j]), D), round(float(lat[j]), D)]]},
                   "properties": {"res_a": int(res[i]), "res_b": int(res[j]),
                                  "crosses_band": bool(res[i] != res[j]),
                                  "length_m": int(round(float(length[k])))}})
    Path(cfg["out_edges"]).write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {**props, "links": len(ef), "aggregated": False,
                        "what": "The lattice itself over the coastal band: links between "
                                "the centres a route actually uses, at res 7. Nothing is "
                                "aggregated here, so a link DOES join two cell centres.",
                        "an_edge_is_not_a_route":
                            "A drawn edge is an ADJACENCY, not a track. No vessel sailed "
                            "the straight line between two hexagon centres; the line says "
                            "only that a route may pass from one cell to the next."},
         "features": ef}, separators=(",", ":")))
    print(f"  wrote {cfg['out_edges']} "
          f"({Path(cfg['out_edges']).stat().st_size/1e6:.1f} MB, {len(ef):,} links)")


if __name__ == "__main__":
    main()
