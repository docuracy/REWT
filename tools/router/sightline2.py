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
from rasterio.windows import Window, from_bounds as _fb
from scipy import ndimage

import h3
from pyproj import Transformer
from sightline import build_vrt, nodata_to_nan

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
    # THE BLIND-SAILING BUFFER, and it is a routing decision rather than a horizon.
    # Measured against real crossings inside the cache: Holyhead-Dublin, Orkney-Shetland,
    # Mull of Kintyre-Antrim and Fair Isle-Shetland never leave sight of land at all
    # (0.0 km blind), Scilly-Brittany goes 12.1 km blind, and the deepest that lies
    # wholly within the British Isles is Land's End to Cork at 56.4 km. 60 km covers
    # that with a little margin and is chosen for that reason, not rounded to it.
    # WHAT IT EXCLUDES, deliberately and worth a ruling: the open North Sea. A crossing
    # to Norway or the Low Countries runs 175 km+ out of sight and is trimmed away. That
    # matches rules/H3.md's scope -- the coastal waters of the British Isles -- but it
    # is a scope decision showing up as a rendering one.
    "buffer_km": 60.0,
    # THE EXTENT IS A DECLARED PARAMETER, not the mosaic's bounds. Geometry does not
    # bound this area: the continental shore is continuous, so a sight-plus-buffer
    # surface keeps connecting coastwise for as long as land is in the extent — it would
    # run to the Baltic and round Iberia. Where to stop must be SAID.
    #
    # Faroe was admitted on a bad rule and is now out: two buffers overlapping is two
    # blind zones touching, which is not a route. The test is whether a landmass's buffer
    # reaches water that is IN SIGHT of the existing area. Shetland-Faroe is 290 km with
    # 113 and 80 km of sight, leaving 97 km blind against a 60 km buffer. It fails.
    "aoi": (-13.24, 44.5, 9.5, 62.12),
    "crs": "EPSG:32630",
    "metres_per_pixel": 930.0,
    "min_land_height_m": 1.0,
    "islet_max_px": 40,              # below this, test whether it stands on anything
    "islet_min_seabed_m": -500.0,    # Rockall stands on a bank at about -200 m
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
    aw = _fb(*cfg["aoi"], src.transform)
    off_r, off_c = int(aw.row_off), int(aw.col_off)
    ah, aw_ = int(aw.height), int(aw.width)
    h, w = ah // dec, aw_ // dec
    print(f"working grid {w} x {h} at 1/{dec}")

    # Two reductions from one read. MAX for land, because peaks must survive it; and a
    # separate "does this block hold any water" at FOUR TIMES the resolution, because
    # the sea mask needs connectivity and a coarse block closes narrow channels.
    fine = 2
    fh, fw = (h * dec) // fine, (w * dec) // fine   # the AOI, not the whole mosaic
    elev = np.full((h, w), np.nan, "float32")
    wet = np.zeros((fh, fw), bool)
    for r0 in range(0, h, 256):
        r1 = min(r0 + 256, h)
        raw = nodata_to_nan(src.read(1, window=Window(
            off_c, off_r + r0 * dec, w * dec, (r1 - r0) * dec)))
        c = raw.reshape(r1 - r0, dec, w, dec)
        with np.errstate(invalid="ignore"):
            elev[r0:r1] = np.nanmax(c, axis=(1, 3))     # peaks must survive the reduction
        k = dec // fine
        f = raw.reshape((r1 - r0) * k, fine, fw, fine)
        wet[r0 * k:r1 * k] = np.any(np.isfinite(f) & (f < 0), axis=(1, 3))

    # THE SEA IS WATER THAT REACHES THE SEA — the same test as grid.py, which this
    # script did not have. `elevation < 0` admits the Fens, which lie below the datum
    # and are dry land, and Stephen saw them still drawn in the sightline layer after
    # the grid had been fixed. A defect fixed in one place is not fixed.
    lab, _ = ndimage.label(wet, structure=ndimage.generate_binary_structure(2, 2))
    border = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    border.discard(0)
    ocean = np.isin(lab, list(border))
    dropped = int((wet & ~ocean).sum())
    print(f"  sea connectivity at 1/{fine}: dropped {dropped:,} inland below-datum "
          f"blocks ({100*dropped/max(wet.sum(),1):.2f}%)")
    k = dec // fine
    reaches = np.any(ocean.reshape(h, k, w, k), axis=(1, 3))   # back to the working grid

    b = rasterio.coords.BoundingBox(*rasterio.windows.bounds(
        Window(off_c, off_r, w * dec, h * dec), src.transform))
    print(f"  extent (declared) {[round(v, 2) for v in b]}")
    # into a projected CRS with SQUARE pixels, so one `sampling` is true everywhere
    dst_tr, dw, dh = calculate_default_transform(
        src.crs, cfg["crs"], w, h, *b, resolution=cfg["metres_per_pixel"])
    proj = np.full((dh, dw), np.nan, "float32")
    rea = np.zeros((dh, dw), "float32")
    reproject(source=reaches.astype("float32"), destination=rea,
              src_transform=rasterio.transform.from_bounds(*b, w, h), src_crs=src.crs,
              dst_transform=dst_tr, dst_crs=cfg["crs"], resampling=Resampling.max,
              src_nodata=None, dst_nodata=0.0)
    reproject(source=elev, destination=proj,
              src_transform=rasterio.transform.from_bounds(*b, w, h), src_crs=src.crs,
              dst_transform=dst_tr, dst_crs=cfg["crs"],
              resampling=Resampling.max, src_nodata=np.nan, dst_nodata=np.nan)
    elev = proj
    px = py = cfg["metres_per_pixel"]
    print(f"  reprojected to {cfg['crs']}: {dw} x {dh} at {px:.0f} m square")
    land = np.isfinite(elev) & (elev >= cfg["min_land_height_m"])

    # A REAL ISLAND SHOALS TOWARDS IT. Six pixels reading +126 m sit in the Faroe-Shetland
    # Channel at 61.696 N, 2.049 W, with a median seabed of -1,429 m for 50 km around and
    # no shoaling at all — a 1,555 m spike out of deep water, and an artefact. It was
    # casting 40 km of sightline over 150 cells, and nothing but the picture showed it.
    # AREA CANNOT SEPARATE THESE: Rockall is a real navigational mark of 0.001 km2. What
    # separates them is that Rockall stands on a bank at about -200 m and this stands on
    # nothing.
    llab, ln = ndimage.label(land, structure=ndimage.generate_binary_structure(2, 2))
    lsz = np.bincount(llab.ravel())
    dropped_spikes = 0
    for i in range(1, ln + 1):
        if lsz[i] > cfg["islet_max_px"]:
            continue                              # big enough to be obviously real
        rs, cs = np.nonzero(llab == i)
        r0, r1 = max(rs.min() - 20, 0), min(rs.max() + 21, land.shape[0])
        c0, c1 = max(cs.min() - 20, 0), min(cs.max() + 21, land.shape[1])
        near = elev[r0:r1, c0:c1]
        wet = near[np.isfinite(near) & (near < 0)]
        if wet.size and float(np.median(wet)) < cfg["islet_min_seabed_m"]:
            land[llab == i] = False
            dropped_spikes += 1
    if dropped_spikes:
        print(f"  dropped {dropped_spikes} land specks standing in water deeper than "
              f"{-cfg['islet_min_seabed_m']:.0f} m with no shoaling — spikes, not islands")
    sea = np.isfinite(elev) & (elev < 0) & (rea > 0.5)
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

    # --- ADMISSION: A BUFFER MUST REACH WATER THAT IS IN SIGHT ---------------------
    # Stephen's correction, and it is a rule about LANDMASSES, not about the extent. Two
    # buffers overlapping is two blind zones touching, which is not a route. So: take the
    # connected components of the VISIBLE zone, start from Great Britain, and admit
    # another component only when the gap to an already-admitted one is within the
    # buffer. Clipping the extent instead left Faroe's southern islands inside the
    # rectangle, casting a sliced-off zone — the rule has to act on the land, not the box.
    vlab, vn = ndimage.label(visible, structure=ndimage.generate_binary_structure(2, 2))
    seed_lat, seed_lon = 53.60, -3.60                     # Liverpool Bay: sea, and in sight
    sx, sy = Transformer.from_crs(4326, cfg["crs"], always_xy=True).transform(seed_lon, seed_lat)
    sr, sc = rasterio.transform.rowcol(dst_tr, sx, sy)
    seed = int(vlab[sr, sc])
    if seed == 0:
        raise SystemExit(f"seed {seed_lat} N {seed_lon} E is not in the visible zone — it "
                         f"must be a point of SEA that can see land, not a point on land")
    admitted = {seed}
    while True:
        mask = np.isin(vlab, list(admitted))
        d = ndimage.distance_transform_edt(
            ~mask, sampling=(cfg["metres_per_pixel"],) * 2) / 1000.0
        gained = set()
        for i in range(1, vn + 1):
            if i in admitted:
                continue
            m = vlab == i
            if m.any() and float(d[m].min()) <= cfg["buffer_km"]:
                gained.add(i)
        if not gained:
            break
        admitted |= gained
    sizes = np.bincount(vlab.ravel())
    rejected = [(int(sizes[i]), i) for i in range(1, vn + 1) if i not in admitted]
    rejected.sort(reverse=True)
    print(f"  visible zone has {vn} components; {len(admitted)} admitted, "
          f"{len(rejected)} rejected as unreachable within the {cfg['buffer_km']:.0f} km buffer")
    for n_, i in rejected[:4]:
        rs, cs = np.nonzero(vlab == i)
        x, y = rasterio.transform.xy(dst_tr, int(rs.mean()), int(cs.mean()))
        blo, bla = Transformer.from_crs(cfg["crs"], 4326, always_xy=True).transform(x, y)
        print(f"    {n_:>7,} px of sight around {bla:.2f} N {blo:.2f} E — "
              f"{float(d[vlab == i].min()):.0f} km from anything in sight")
    visible &= np.isin(vlab, list(admitted))

    # --- TRIM (H3-002 item 3) -----------------------------------------------------
    dblind = ndimage.distance_transform_edt(
        ~visible, sampling=(cfg["metres_per_pixel"],) * 2) / 1000.0
    keep_px = sea & (visible | (dblind <= cfg["buffer_km"]))
    print(f"  buffer {cfg['buffer_km']:.0f} km -> keep {int(keep_px.sum()):,} of "
          f"{int(sea.sum()):,} sea px ({100*keep_px.sum()/sea.sum():.1f}%)")

    # WHETHER THE ANSWER IS KNOWABLE, which the trim does NOT by itself settle. A cell
    # near the edge of the cached data may be governed by land that lies outside it.
    # Once the cache covers everything that can reach in, every kept cell is answered
    # and this flag becomes universally true and can be dropped -- rewt-46's layer
    # already reads an absent `known` as answered.
    edge = ndimage.distance_transform_edt(
        np.pad(np.ones(np.array(elev.shape) - 2, bool), 1),
        sampling=(cfg["metres_per_pixel"],) * 2) / 1000.0
    known_px = visible | (edge >= rmax)

    # per-cell governing height: the tallest land that reaches this cell. This is the
    # thing the inversion makes visible and the per-sea-cell method never had — it says
    # WHICH land does the work, so a reader can see that Snowdon carries water a Norfolk
    # hill cannot.
    gv = gov[sea]; gvs = gv[order]
    gov_cell = np.maximum.reduceat(gvs, starts)
    kp = keep_px[sea][order]; keep_cell = np.maximum.reduceat(kp.astype(np.int8), starts).astype(bool)
    kn = known_px[sea][order]; known_cell = np.minimum.reduceat(kn.astype(np.int8), starts).astype(bool)
    feats = []
    for c, v, gh, kp_, kn_ in zip(uniq, any_vis, gov_cell, keep_cell, known_cell):
        if not kp_:
            continue                      # trimmed: outside sight plus the buffer
        bnd = h3.cell_to_boundary(c)
        ring = [[round(x, 5), round(y, 5)] for y, x in bnd]
        ring.append(ring[0])
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"h3": c, "visible": bool(v),
                                     **({} if kn_ else {"known": False}),
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
            "blind_sailing_buffer_km": cfg["buffer_km"],
            "buffer_basis": "the deepest a crossing wholly within the British Isles goes "
                            "out of sight: Land's End to Cork, 56.4 km. It is a ROUTING "
                            "decision, not a horizon and not a coast -- the trimmed edge "
                            "means nothing else.",
            "trimmed": "cells beyond sight plus the buffer are absent, not coloured "
                       "(H3-002 item 3). `known: false` appears only where the answer "
                       "still depends on land outside the cached data; absent means "
                       "answered.",
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
        "kept_after_trim": int(keep_cell.sum()),
        "blind_sailing_buffer_km": cfg["buffer_km"],
        "still_unknown": int((keep_cell & ~known_cell).sum()),
        "reach_bound_evidence": {
            "Ben Nevis GB": 139.2, "Kerry IRL": 120.9, "Brittany FRA": 73.9,
            "W Norway (does NOT reach, 430 km away)": 146.2,
            "Iceland (does NOT reach, 700 km away)": 143.8},
        "attribution": ATTRIBUTION, "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"wrote {cfg['summary']}")


if __name__ == "__main__":
    main()
