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

    # links only where the handover happens; the open-sea interior is a uniform lattice
    near = cl <= 25.0
    lf = [{"type": "Feature",
           "geometry": {"type": "LineString", "coordinates": [
               [round(float(lon[a]), D), round(float(lat[a]), D)],
               [round(float(lon[b]), D), round(float(lat[b]), D)]]},
           "properties": {}} for a, b in e if near[a] or near[b]]
    (OUT / "mesh_links.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": stamp, "links": len(lf),
                        "subset": "links with an end within 25 km of land — the handover "
                                  "zone. The open-sea interior is a uniform lattice and "
                                  "drawing all 402,992 of it says nothing extra.",
                        "total_links": int(len(e))},
         "features": lf}, separators=(",", ":")))
    print(f"  mesh_links.geojson {len(lf):,} of {len(e):,} links "
          f"({(OUT/'mesh_links.geojson').stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
