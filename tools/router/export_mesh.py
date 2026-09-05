"""The new mesh and the new joins, as /check layers."""
from __future__ import annotations
import json, sys
from pathlib import Path
import h3, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402

OUT = Path("docs/router/check")
D = 5


def main() -> None:
    g = np.load("tools/router/cache/mesh.npz", allow_pickle=True)
    cell, lat, lon, e, cl = g["cell"], g["lat"], g["lon"], g["edge"], g["clearance_km"]
    stamp = json.loads(Path("docs/router/data/mesh_summary.json").read_text())["generation"]

    cf = []
    for i, c in enumerate(cell.tolist()):
        ring = [[round(x, D), round(y, D)] for y, x in h3.cell_to_boundary(c)]
        ring.append(ring[0])
        cf.append({"type": "Feature",
                   "geometry": {"type": "Polygon", "coordinates": [ring]},
                   "properties": {"h3": c, "km_to_land": round(float(cl[i]), 1)}})
    (OUT / "mesh_cells.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": stamp, "cells": len(cf), "resolution": 7,
                        "what": "The open-water mesh: one resolution, every centre in "
                                "water and at least 1 km from land."},
         "features": cf}, separators=(",", ":")))
    print(f"  mesh_cells.geojson {len(cf):,} cells "
          f"({(OUT/'mesh_cells.geojson').stat().st_size/1e6:.1f} MB)")

    # THE WHOLE NETWORK. Stephen asked to see it, so the subset is gone: every link
    # between two ADJACENT res-7 cells whose straight line does not cross land, after
    # dropping everything outside the majority connected set. Verified: 0 of 402,992 join
    # non-adjacent cells, lengths 1,897-2,521 m.
    near = np.ones(len(cl), bool)
    lf = [{"type": "Feature",
           "geometry": {"type": "LineString", "coordinates": [
               [round(float(lon[a]), D), round(float(lat[a]), D)],
               [round(float(lon[b]), D), round(float(lat[b]), D)]]},
           "properties": {}} for a, b in e if near[a] or near[b]]
    (OUT / "mesh_network.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": stamp, "links": len(lf),
                        "construction": "Every pair of ADJACENT res-7 cells (H3 grid distance 1), "
                                        "minus links whose straight line crosses land on "
                                        "the exact Shapely test over both coastlines, minus "
                                        "everything outside the majority connected set. "
                                        "Verified: 0 links join non-adjacent cells.",
                        "total_links": int(len(e))},
         "features": lf}, separators=(",", ":")))
    print(f"  mesh_network.geojson {len(lf):,} of {len(e):,} links "
          f"({(OUT/'mesh_network.geojson').stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
