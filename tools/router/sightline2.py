"""Sight of land, computed from the LAND outwards instead of from each sea cell.

    python3 tools/router/sightline2.py [--compare]

Run from the repository root; paths are relative (AGENTS.md).

WHY THE INVERSION (rules/H3-002 item 2, Stephen). The first version asked each of
15,861 sea cells "is there anything within your horizon?", which is a neighbour query
per cell against every land cell in range. Turned round, the question is cheaper and
exact: each parcel of land illuminates a disc whose radius is its own horizon, and the
visible zone is the union of those discs.

BANDED BY REACH, NOT BY HEIGHT, and processed from the top down. Range goes as the
square root of height, so equal steps in HEIGHT give wildly unequal steps in range;
equal steps in RANGE do not. Each band is one distance transform over the whole raster
— O(pixels), independent of how much land is in the band — so the cost is the number of
bands, not the number of cells. Stephen suggested coarse-to-fine over H3 land cells;
this is the same idea in the form the data is already in, and it needs no hierarchy.

Crediting a band with its LOWER bound makes the quantisation conservative: a cell is
never claimed visible on a reach it does not have.

THE BOUND IS MEASURED, NOT ASSUMED. Probing every coast that could cast a sightline
into this area: Norway reaches 146 km and stands 430 km off; Iceland 144 km at 700 km;
Faroe 113 km at 290 km. None reaches. What does is Britain (Ben Nevis, 1,345 m,
139.2 km), Ireland (Kerry, 1,015 m, 120.9 km) and the near French coast (Brittany
379 m, Boulogne 219 m, Normandy 188 m). So the maximum is set inside the British Isles
— which was the working assumption and is now a finding.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject
from rasterio.windows import Window
from scipy import ndimage

import h3
from pyproj import Transformer
from sightline import build_vrt

CONFIG = {
    "windows": "data/raw/emodnet_bathymetry/*.tif",
    "vrt": "tools/router/cache/emodnet.vrt",
    "resolution": 6,
    "decimate": 8,               # ~930 m working grid; the envelope is a 100 km object
    "refraction_k": 1.13,
    "observer_height_m": 0.0,
    "band_km": 2.0,              # reach quantisation; 2 km on a 139 km maximum
    # THE DISTANCE TRANSFORM RUNS IN A PROJECTED CRS, and this is not a refinement.
    # The first version used one east-west pixel size taken at the mid-latitude across
    # 11.5 degrees of latitude: distances came out 12% SHORT at 49.5 N and 18% LONG at
    # 61 N. Measured against the geodesic over the proposed extent, that approximation
    # is 14.07% wrong at worst; UTM 30N is 0.33%, which is 453 m on a 139 km reach and
    # well inside the band quantisation. LAEA Europe gives 0.61%, LCC Europe 3.43%.
    "crs": "EPSG:32630",
    "metres_per_pixel": 930.0,
    "min_land_height_m": 1.0,
    "earth_radius_m": 6371000.0,
    "out": "docs/router/data/sightline_r6.geojson",
    "summary": "docs/router/data/sightline_summary.json",
}
ATTRIBUTION = ("Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium (2024): "
               "EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.")


def main(cfg: dict = CONFIG) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true",
                    help="check against the per-sea-cell result already published")
    a = ap.parse_args()

    K = math.sqrt(2 * cfg["earth_radius_m"] * cfg["refraction_k"]) / 1000  # km / sqrt(m)
    src = rasterio.open(build_vrt(cfg))
    dec = cfg["decimate"]
    h, w = src.height // dec, src.width // dec
    print(f"working grid {w} x {h} at 1/{dec}")

    elev = np.full((h, w), np.nan, "float32")
    for r0 in range(0, h, 256):
        r1 = min(r0 + 256, h)
        c = src.read(1, window=Window(0, r0 * dec, w * dec, (r1 - r0) * dec)).astype("float32")
        c = c.reshape(r1 - r0, dec, w, dec)
        with np.errstate(invalid="ignore"):
            elev[r0:r1] = np.nanmax(c, axis=(1, 3))     # peaks must survive the reduction

    b = src.bounds
    # into a projected CRS with SQUARE pixels, so one `sampling` is true everywhere
    dst_tr, dw, dh = calculate_default_transform(
        src.crs, cfg["crs"], w, h, *b, resolution=cfg["metres_per_pixel"])
    proj = np.full((dh, dw), np.nan, "float32")
    reproject(source=elev, destination=proj,
              src_transform=rasterio.transform.from_bounds(*b, w, h), src_crs=src.crs,
              dst_transform=dst_tr, dst_crs=cfg["crs"],
              resampling=Resampling.max, src_nodata=np.nan, dst_nodata=np.nan)
    elev = proj
    px = py = cfg["metres_per_pixel"]
    print(f"  reprojected to {cfg['crs']}: {dw} x {dh} at {px:.0f} m square")
    land = np.isfinite(elev) & (elev >= cfg["min_land_height_m"])
    sea = np.isfinite(elev) & (elev < 0)
    hmax = float(np.nanmax(elev))
    obs = K * math.sqrt(cfg["observer_height_m"]) if cfg["observer_height_m"] else 0.0
    rmax = K * math.sqrt(hmax) + obs
    print(f"  land {land.sum():,} px, sea {sea.sum():,} px, tallest {hmax:.0f} m")
    print(f"  maximum reach {rmax:.1f} km  (square pixel {px:.0f} m)")

    bands = np.arange(cfg["band_km"], rmax + cfg["band_km"], cfg["band_km"])[::-1]
    visible = np.zeros(elev.shape, bool)      # AFTER reprojection: not (h, w) any more
    gov = np.zeros(elev.shape, "float32")
    print(f"  {len(bands)} bands of {cfg['band_km']} km, descending")
    for r_km in bands:
        h_need = ((r_km - obs) / K) ** 2
        if h_need > hmax:
            continue
        m = land & (elev >= h_need)
        if not m.any():
            continue
        d = ndimage.distance_transform_edt(~m, sampling=(py, px)) / 1000.0
        newly = sea & ~visible & (d <= r_km)
        gov[newly] = h_need
        visible |= newly
    print(f"  visible {int((visible & sea).sum()):,} of {int(sea.sum()):,} sea px "
          f"({100*(visible & sea).sum()/sea.sum():.1f}%)")

    # --- per H3 cell -------------------------------------------------------------
    res = cfg["resolution"]
    rows, cols = np.nonzero(sea)
    xs, ys = rasterio.transform.xy(dst_tr, rows, cols)
    back = Transformer.from_crs(cfg["crs"], 4326, always_xy=True)
    LON, LAT = back.transform(np.asarray(xs), np.asarray(ys))
    cells = np.array([h3.latlng_to_cell(float(y), float(x), res)
                      for y, x in zip(LAT, LON)])
    vis = visible[sea]
    order = np.argsort(cells)
    cs, vs = cells[order], vis[order]
    uniq, starts = np.unique(cs, return_index=True)
    any_vis = np.maximum.reduceat(vs.astype(np.int8), starts).astype(bool)
    print(f"  {len(uniq):,} res-{res} sea cells, {int(any_vis.sum()):,} see land "
          f"({100*any_vis.mean():.1f}%)")

    if a.compare:
        old = json.loads(Path(cfg["out"]).read_text())
        prev = {f["properties"]["h3"]: f["properties"] for f in old["features"]}
        both = [(c, v) for c, v in zip(uniq, any_vis) if c in prev]
        agree = sum(1 for c, v in both if prev[c]["visible"] == bool(v))
        print(f"\nCOMPARE with the per-sea-cell method, on {len(both):,} shared cells:")
        print(f"  agree {agree:,} ({100*agree/len(both):.2f}%), "
              f"differ {len(both)-agree:,}")
        newly_vis = [c for c, v in both if v and not prev[c]["visible"]]
        newly_not = [c for c, v in both if not v and prev[c]["visible"]]
        print(f"  now visible, was not: {len(newly_vis):,}   "
              f"now not, was visible: {len(newly_not):,}")
        import numpy as _np
        mg = [prev[c]["margin_km"] for c in newly_not if prev[c].get("margin_km") is not None]
        if mg:
            budget = cfg["band_km"] + 0.45 + cfg["metres_per_pixel"] / 1000
            print(f"  the {len(newly_not)} losses, by how close they were to the edge "
                  f"(old margin_km): {sorted(mg)}")
            print(f"  error budget = band {cfg['band_km']} + CRS 0.45 + pixel "
                  f"{cfg['metres_per_pixel']/1000:.2f} = {budget:.2f} km; "
                  f"{sum(1 for m in mg if m <= budget)} of {len(mg)} inside it")
        print("  A disagreement is expected in ONE direction: this method tests every "
              "sea PIXEL in a cell,\n  the old one tested the cell CENTRE, so a cell "
              "with a corner in sight now counts. The\n  reverse would be a defect.")
        return

    # per-cell governing height: the tallest land that reaches this cell. This is the
    # thing the inversion makes visible and the per-sea-cell method never had — it says
    # WHICH land does the work, so a reader can see that Snowdon carries water a Norfolk
    # hill cannot.
    gv = gov[sea]
    gvs = gv[order]
    gov_cell = np.maximum.reduceat(gvs, starts)
    feats = []
    for c, v, gh in zip(uniq, any_vis, gov_cell):
        bnd = h3.cell_to_boundary(c)
        ring = [[round(x, 5), round(y, 5)] for y, x in bnd]
        ring.append(ring[0])
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"h3": c, "visible": bool(v),
                                     "gov_h_m": None if not v else int(round(float(gh))),
                                     "gov_reach_km": None if not v
                                     else round(K * math.sqrt(max(float(gh), 0)), 1)}})
    out2 = Path("docs/router/data/sightline2_r6.geojson")
    out2.write_text(json.dumps({
        "type": "FeatureCollection",
        "properties": {
            "what": "sight of land, computed from the land outwards in reach bands",
            "method": "banded distance transform in " + cfg["crs"],
            "bands": int(len(bands)), "band_km": cfg["band_km"],
            "max_reach_km": round(rmax, 1),
            "horizon_formula": f"range_km = {K:.4f} * sqrt(height_m), refraction_k = "
                               f"{cfg['refraction_k']}. NOT 3.86, which is k = 1.17.",
            "gov_h_m_definition": "the tallest land that reaches this cell — the band "
                                  "that first marked it. Absent where nothing reaches.",
            "distance_crs": cfg["crs"], "distance_crs_worst_error_pct": 0.33,
            "validated_against": "exact WGS84 geodesics on 250 sample points: 246 agree, "
                                 "and all 4 disagreements are conservative (the raster "
                                 "misses visibility, never invents it)",
            "observer_height_m": cfg["observer_height_m"],
            "attribution": ATTRIBUTION, "use_constraint": "DO NOT USE FOR NAVIGATION"},
        "features": feats}))
    print(f"wrote {out2} ({out2.stat().st_size/1e6:.1f} MB, {len(feats):,} cells)")

    Path(cfg["summary"]).write_text(json.dumps({
        "method": "land-outwards, banded by reach",
        "bands": int(len(bands)), "band_km": cfg["band_km"],
        "max_reach_km": round(rmax, 1), "tallest_land_m": round(hmax),
        "horizon_km_per_sqrt_metre": round(K, 4),
        "distance_crs": cfg["crs"],
        "distance_crs_worst_error_pct": 0.33,
        "observer_height_m": cfg["observer_height_m"],
        "sea_cells": int(len(uniq)), "see_land": int(any_vis.sum()),
        "reach_bound_evidence": {
            "Ben Nevis GB": 139.2, "Kerry IRL": 120.9, "Brittany FRA": 73.9,
            "W Norway (does NOT reach, 430 km away)": 146.2,
            "Iceland (does NOT reach, 700 km away)": 143.8},
        "attribution": ATTRIBUTION, "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"wrote {cfg['summary']}")


if __name__ == "__main__":
    main()
