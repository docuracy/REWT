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
from landtest import land_polygons, os_land_polygons   # noqa: E402

CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "masks": "tools/router/cache/sightline_masks.npz",
    "summary": "docs/router/data/edge_summary.json",
    "out_cells": "docs/router/data/cells_r7_coast.geojson",
    "out_edges": "docs/router/data/edges_r7_coast.geojson",
    "fringe_km": 5.0,
    "coord_dp": 5,
}


def main(cfg: dict = CONFIG) -> None:
    g = np.load(cfg["grid"], allow_pickle=True)
    cell, res = g["cell"].tolist(), g["resolution"]
    lat, lon, depth = g["lat"], g["lon"], g["depth_m"]
    stamp = json.loads(Path(cfg["summary"]).read_text()).get("generation") or generation()

    mask, crs = land_polygons(cfg["masks"])
    tree = STRtree(mask + os_land_polygons(crs))
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

    D = cfg["coord_dp"]
    props = {
        "generation": stamp,
        "what": "The routing cells themselves, at res 7 (and 6, 8, 9 where the grid bands), "
                "for the coastal band within %.0f km of land." % cfg["fringe_km"],
        "extent_deliberately_differs":
            "This layer does NOT cover the same ground as sightline2_r6.geojson and is not "
            "meant to. The main edges layer is clipped to the sightline cells so a viewer "
            "toggle lines up; that clip removes 4,504 perimeter cells and hides coastal "
            "surface that the routing graph has. Draw the mismatch rather than clipping it "
            "away: a visible difference that is explained beats a tidy picture that has "
            "lost the estuaries.",
        "coverage_measured":
            "Against the 4,184 sea entries of the release: 32.6% fall in a routing cell, "
            "39.6% one ring away, 10.8% two rings, and 17.0% are ABSENT — 710 entries with "
            "2,360 river mouths behind them, in creek heads and narrow estuaries the res-7 "
            "lattice cannot represent. That last figure is a real limit of the surface and "
            "no finer rendering changes it.",
        "band_chosen_by": "what it covers, not by generosity: 5 km captures exactly as many "
                          "sea entries as publishing all 143,879 cells would. 3 km loses "
                          "ten; 8 km adds none.",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0. "
                       "Contains OS data (c) Crown copyright and database right, OGL v3.",
        "this_layer_is_a_band_not_a_surface":
            "It has 32 connected components and the largest holds 38% of it. That is NOT a "
            "defect and must not be repaired by dropping the small ones: a 5 km coastal "
            "band around separate landmasses IS separate, and the water between them is "
            "simply further from land than the band is wide. The ROUTING GRAPH these cells "
            "belong to is one component of 143,879 cells; this layer is a window onto it, "
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
