"""The routing edges as a GeoJSON layer, for the viewer's toggle from the sea cells.

Stephen asked to see the travelling surface itself rather than the cells that carry it.
An edge here is a link between two cell CENTRES — the surface eRutter uses, and the one
`edges.py` builds. What is drawn is an ADJACENCY, not a route: a vessel did not sail the
straight line between two hex centres, and a chain of these is only the shape a route
would follow at the lattice's resolution. That sentence rides in the layer's own
properties rather than in the legend, so it cannot be separated from the geometry.

Cross-resolution edges are the interesting ones and carry `crosses_band`. A grid built
from `grid_disk` alone would be one disconnected sheet per resolution, each locally
perfect; those edges are the seams, and a picture shows what a count cannot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402

CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "summary": "docs/router/data/edge_summary.json",
    "out": "docs/router/data/edges.geojson",
    "check_dir": "docs/router/check",
    "areas": "docs/router/check/areas.json",
    "cells": "docs/router/data/sightline2_r6.geojson",
    "publish_resolution": 6,   # see the note in main(): 415,520 res-7 edges is 80 MB
    "coord_dp": 4,             # 11 m, against a median edge of 2,290 m
}


def main(cfg: dict = CONFIG) -> None:
    """Two layers, because the true graph will not fit down a browser.

    THE PUBLISHED ONE IS AGGREGATED, and this is the whole of the compromise. The
    routing grid is res 7: 143,196 cells and 415,520 edges, which is 80 MB of GeoJSON
    and about a gigabyte once a browser has parsed it. The published SEA CELLS are res
    6 — that is the layer a toggle switches away from — so the published edges are the
    res-7 graph aggregated to res 6: two res-6 cells are linked when any res-7 edge
    joins a child of one to a child of the other. Every such link is backed by a real
    routing edge and none is invented, but a drawn line runs centre-to-centre between
    res-6 cells and no vessel and no route uses those centres.

    THE TRUE EDGES GO OUT PER CHECK AREA, unaggregated, into the gitignored check
    directory, where the areas are small enough to hold them. That is where to look at
    the lattice itself.
    """
    g = np.load(cfg["grid"], allow_pickle=True)
    res = g["resolution"]
    lat, lon = np.round(g["lat"], cfg["coord_dp"]), np.round(g["lon"], cfg["coord_dp"])
    cell = g["cell"].tolist()
    P, D = cfg["publish_resolution"], cfg["coord_dp"]
    z = np.load(cfg["edges"])
    e, length = z["edge"], z["length_m"]
    ra, rb = res[e[:, 0]].astype(int), res[e[:, 1]].astype(int)
    cross = ra != rb
    print(f"{len(e):,} edges, {cross.sum():,} crossing a resolution band "
          f"({100*cross.mean():.2f}%)")

    par = {}
    for k, (i, j) in enumerate(e):
        pa = h3.cell_to_parent(cell[i], P)
        pb = h3.cell_to_parent(cell[j], P)
        if pa == pb:
            continue                       # inside one published cell; nothing to draw
        key = (pa, pb) if pa < pb else (pb, pa)
        r = par.setdefault(key, {"n": 0, "cross": 0, "len": 0.0})
        r["n"] += 1
        r["cross"] += int(cross[k])
        r["len"] += float(length[k])
    print(f"  aggregated to res {P}: {len(par):,} links (from {len(e):,} routing edges)")

    # CLIP TO THE CELLS THAT ARE ACTUALLY PUBLISHED. A res-6 parent appears as soon as
    # ONE of its seven res-7 children is in the routing grid, so aggregation spills a
    # ring of cells past the edge of the published layer — 4,504 of them, all perimeter.
    # A toggle whose two layers do not cover the same ground is a bug the eye finds
    # immediately, so links with an endpoint outside the published set come out here,
    # and the count goes into the layer's properties rather than being silently lost.
    pub = {f["properties"]["h3"]
           for f in json.loads(Path(cfg["cells"]).read_text())["features"]}
    spill = [k for k in par if not (k[0] in pub and k[1] in pub)]
    for k in spill:
        del par[k]
    print(f"  dropped {len(spill):,} links reaching a cell the layer does not publish; "
          f"{len(par):,} remain")

    feats = []
    for (pa, pb), r in sorted(par.items()):
        la, lo = h3.cell_to_latlng(pa)
        lb, ob = h3.cell_to_latlng(pb)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [
                [round(lo, D), round(la, D)], [round(ob, D), round(lb, D)]]},
            "properties": {
                "h3_a": pa, "h3_b": pb,
                "routing_edges": r["n"],
                "crosses_band": bool(r["cross"]),
                "mean_edge_m": int(round(r["len"] / r["n"])),
            },
        })

    # --- the true lattice, unaggregated, for the named check areas ------------------
    areas = json.loads(Path(cfg["areas"]).read_text()) if Path(cfg["areas"]).exists() else {}
    for name, box in areas.items():
        if name.startswith("_"):
            continue
        w, so, ea, no = box
        inside = ((lon[e[:, 0]] >= w) & (lon[e[:, 0]] <= ea) &
                  (lat[e[:, 0]] >= so) & (lat[e[:, 0]] <= no))
        sub = np.nonzero(inside)[0]
        af = [{"type": "Feature",
               "geometry": {"type": "LineString", "coordinates": [
                   [float(lon[e[k, 0]]), float(lat[e[k, 0]])],
                   [float(lon[e[k, 1]]), float(lat[e[k, 1]])]]},
               "properties": {"res_a": int(min(ra[k], rb[k])),
                              "res_b": int(max(ra[k], rb[k])),
                              "res_pair": f"{min(ra[k], rb[k])}-{max(ra[k], rb[k])}",
                              "crosses_band": bool(cross[k]),
                              "length_m": int(round(float(length[k])))}}
              for k in sub]
        Path(cfg["check_dir"], f"edges-{name}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection",
             "properties": {"generation": generation(), "aggregated": False,
                            "what": "the routing lattice itself, res 7-9, unaggregated"},
             "features": af}, separators=(",", ":")))
        print(f"  edges-{name}.geojson  {len(af):,} true edges")

    s = json.loads(Path(cfg["summary"]).read_text())
    fc = {
        "type": "FeatureCollection",
        "properties": {
            "generation": generation(),
            "what": "Links between the centres of adjacent sea cells: the surface a "
                    "route is measured on.",
            "an_edge_is_not_a_route":
                "A drawn edge is an ADJACENCY, not a track. No vessel sailed the straight "
                "line between two hexagon centres; the line says only that a route may "
                "pass from one cell to the next. A chain of them approximates a course to "
                "within the lattice's resolution and no better.",
            "lattice": s.get("lattice_note"),
            "links": len(feats),
            "links_outside_published_cells": len(spill),
            "clip_note":
                "Aggregation lifts a res-6 cell into view as soon as one of its seven "
                "res-7 children is in the routing grid, so it spills a ring past the "
                "published layer. Those links are real edges; they are dropped here only "
                "so the two layers of the toggle cover the same ground.",
            "routing_edges_behind_them": int(len(e)),
            "aggregated_to_resolution": P,
            "aggregation":
                "The routing graph is res 7. These links are it aggregated to the res 6 "
                "of the published sea cells: two cells are linked where any res-7 edge "
                "joins a child of one to a child of the other. `routing_edges` counts "
                "how many. Nothing is invented, but the drawn centres are not the "
                "centres a route uses — for the lattice itself see the check export.",
            "cells": int(s.get("cells", len(res))),
            "crossing_a_band": sum(1 for f in feats if f["properties"]["crosses_band"]),
            "crossing_a_band_before_aggregation": int(cross.sum()),
            "band_counts_differ":
                "crossing_a_band counts features IN THIS LAYER. The res-7 graph behind "
                "it has more, because several routing edges collapse into one drawn "
                "link and the link is marked if any of them crosses. Take the count "
                "from this layer; the other figure is here to be compared, not drawn.",
            "crosses_band_meaning":
                "True where the two cells sit at different resolutions. These are the "
                "seams of the banding: with none of them the graph would be one "
                "disconnected sheet per resolution, each looking locally correct.",
            "links_rejected_crossing_land": s.get("links_rejected_crossing_land"),
            "rejection_rule":
                "A link whose straight line passes over land at 232 m is not an edge, "
                "even where both cells hold water — a spit or a peninsula between two "
                "cell centres. The same test decides which cells the grid keeps.",
            "length_is_not_a_weight":
                "length_m is geometry. Weights — wind, tide, season — are deferred.",
            "components": s.get("components"),
            "largest_component": s.get("largest_component"),
            "attribution": s.get("attribution"),
            "use_constraint": "DO NOT USE FOR NAVIGATION",
        },
        "features": feats,
    }
    Path(cfg["out"]).write_text(json.dumps(fc, separators=(",", ":")))
    mb = Path(cfg["out"]).stat().st_size / 1e6
    print(f"wrote {cfg['out']} ({mb:.1f} MB, {len(feats):,} edges)")


if __name__ == "__main__":
    main()
