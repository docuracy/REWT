"""A local, staged visual check of the router's work. Not published.

    python3 tools/router/export_check.py
    python3 tools/viewer/serve.py          # then open http://127.0.0.1:8021/router/check/

Writes everything into `docs/router/check/`, which is gitignored: this is a working
instrument, not an artefact, and it would be 18 MB of GeoJSON on the public site.
Regenerate it whenever a stage changes. It reuses rewt-46's server rather than opening
a second port — TEAM.md: an agent that opens a port owns closing it.

STAGED, because Stephen asked to check the work as it goes rather than at the end. Each
stage is the output of one script and can be looked at on its own:

    1  grid       the banded cells, coloured by resolution
    2  sightline  where land can theoretically be seen
    3  joins      river termini attached to the grid, by rule
    4  traces     the paths across the drying ground

NATIONAL AT COARSE RESOLUTION, DETAILED WHERE IT MATTERS. Emitting all 194,758 cells as
polygons is ~78 MB and no use for looking at an estuary. Res 3-7 goes out whole; res 8
and 9 go out only inside the named areas below, which are the places the hard cases are.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import h3

OUT = Path("docs/router/check")

AREAS = {
    "severn":     (-3.60, 51.20, -2.30, 51.80),
    "thames":     (-0.20, 51.35,  1.00, 51.65),
    "wash":       ( -0.20, 52.70,  0.60, 53.05),
    "solway":     (-3.90, 54.65, -3.00, 55.05),
    "loch-etive": (-5.60, 56.35, -4.95, 56.60),
    "mersey-dee": (-3.30, 53.20, -2.70, 53.50),
}


def cell_feature(c, props):
    b = h3.cell_to_boundary(c)
    ring = [[round(x, 5), round(y, 5)] for y, x in b]
    ring.append(ring[0])
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    g = np.load("tools/router/cache/grid_r9.npz", allow_pickle=True)
    cells, res = g["cell"].tolist(), g["resolution"]
    lat, lon, dep = g["lat"], g["lon"], g["depth_m"]
    print(f"grid {len(cells):,} cells")

    coarse = [cell_feature(c, {"res": int(r), "depth": None if np.isnan(d) else round(float(d))})
              for c, r, d in zip(cells, res, dep) if r <= 7]
    (OUT / "grid-coarse.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": coarse}))
    print(f"  grid-coarse.geojson  {len(coarse):,} cells (res 3-7)")

    for name, (w, s, e, n) in AREAS.items():
        sel = [(c, r, d) for c, r, d, la, lo in zip(cells, res, dep, lat, lon)
               if r >= 8 and w <= lo <= e and s <= la <= n]
        f = [cell_feature(c, {"res": int(r), "depth": None if np.isnan(d) else round(float(d))})
             for c, r, d in sel]
        (OUT / f"grid-{name}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection", "features": f}))
        print(f"  grid-{name}.geojson  {len(f):,} cells (res 8-9)")

    # the other three stages are already browser-readable; link, do not copy
    for src in ("sightline_r6.geojson", "sightline2_r6.geojson",
                "joins.geojson", "traces.geojson"):
        p = Path("docs/router/data") / src
        if p.exists():
            print(f"  (stage reads ../data/{src}, {p.stat().st_size/1e6:.1f} MB)")

    # Geographic context WITHOUT an external basemap: the actual OS coastline, which
    # this project already holds under OGL. A check page that depends on a tile service
    # is a check page that stops working offline and silently changes under you.
    import geopandas as gpd
    cr = gpd.read_file("data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg",
                       layer="country_region").to_crs(4326)
    cr["geometry"] = cr.geometry.simplify(0.002)
    cr = cr[cr.geometry.area > 1e-5]
    (OUT / "coastline.geojson").write_text(cr[["Name", "geometry"]].to_json())
    print(f"  coastline.geojson  {len(cr):,} polygons (OS Boundary-Line, OGL)")

    # Boundary-Line is GREAT BRITAIN ONLY. Ireland, Faroe and the continent would be
    # hexagons around nothing, which reads as sea. Land outside GB comes from EMODnet's
    # own sign change — coarse, but it is context, and it is the same surface the grid
    # is cut from so it cannot disagree with it.
    import rasterio                      # np is already imported at module level;
    from rasterio.features import shapes  # re-importing it here made it function-local
    from rasterio.windows import Window
    from shapely.geometry import shape as shp
    import sys as _sys
    _sys.path.insert(0, "tools/router")
    from sightline import build_vrt, nodata_to_nan
    src = rasterio.open(build_vrt({"windows": "data/raw/emodnet_bathymetry/*.tif",
                                   "vrt": "tools/router/cache/emodnet.vrt"}))
    d = 16
    hh, ww = src.height // d, src.width // d
    a = np.empty((hh, ww), "float32")
    for r0 in range(0, hh, 256):
        r1 = min(r0 + 256, hh)
        c = nodata_to_nan(src.read(1, window=Window(0, r0*d, ww*d, (r1-r0)*d)))
        with np.errstate(invalid="ignore"):
            a[r0:r1] = np.nanmax(c.reshape(r1 - r0, d, ww, d), axis=(1, 3))
    mask = (np.isfinite(a) & (a >= 0)).astype("uint8")
    tr = rasterio.transform.from_bounds(*src.bounds, ww, hh)
    polys = [shp(g).simplify(0.01) for g, v in shapes(mask, mask=mask.astype(bool),
                                                     transform=tr) if v == 1]
    polys = [p_ for p_ in polys if p_.area > 2e-4]
    gdf = gpd.GeoDataFrame(geometry=polys, crs=4326)
    (OUT / "land.geojson").write_text(gdf.to_json())
    print(f"  land.geojson       {len(gdf):,} polygons (EMODnet sign change, context only)")

    # The page is SOURCE and lives in tools/; check/ is gitignored, so an index.html
    # written straight into it would vanish on a clean checkout.
    (OUT / "index.html").write_text(Path("tools/router/check.html").read_text())
    print("  index.html (from tools/router/check.html)")

    summary = {}
    for s in ("grid_summary", "join_summary", "trace_summary", "edge_summary",
              "sightline_summary"):
        p = Path("docs/router/data") / f"{s}.json"
        if p.exists():
            summary[s] = json.loads(p.read_text())
    (OUT / "summaries.json").write_text(json.dumps(summary))
    # "_extent" so the page's "all" button follows the data instead of a box that goes
    # stale the moment the cache grows — which it just did, from 120 windows to 288.
    (OUT / "areas.json").write_text(json.dumps(
        {**AREAS, "_extent": [src.bounds.left, src.bounds.bottom,
                              src.bounds.right, src.bounds.top]}))
    print(f"  summaries.json, areas.json")
    print(f"\nnow: python3 tools/viewer/serve.py   ->   "
          f"http://127.0.0.1:8021/router/check/")


if __name__ == "__main__":
    main()
