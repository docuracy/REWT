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
from generation import generation
from pyproj import Transformer
from extent import EXTENT
from sightline import build_vrt, nodata_to_nan

CONFIG = {
    "windows": "data/raw/emodnet_bathymetry/*.tif",
    "vrt": "tools/router/cache/emodnet.vrt",
    "resolution": 6,
    "decimate": 8,               # ~930 m working grid; the envelope is a 100 km object
    "refraction_k": 1.13,
    # OBSERVER HEIGHT: 10 m, a lookout at the masthead. Stephen's ruling, 4 Sep 2026,
    # and this was never mine to choose — it is a decision about vessels. I had it at
    # 0.0 and defended that as "the one value that assumes nothing", which is wrong: an
    # eye at sea level assumes something FALSE. Nobody observes from the waterline, and a
    # lookout standing on the deck of the smallest craft is already at 2 m.
    #
    # THE LITERATURE. Litvine, Lewis and Starzec (2024), "A multi-criteria simulation of
    # European coastal shipping routes in the 'age of sail'", Humanities and Social
    # Sciences Communications 11:666, doi:10.1057/s41599-024-02906-9, CC BY 4.0. They
    # report Alvarez-Palau and Dunn (2019) — coastal routing for ENGLAND AND WALES,
    # which is this project's area — as taking h1 = 10 m, located on the ship's mast.
    #
    # AND THE VERSION OF RECORD IS WRONG ON THIS FIGURE. The typeset Nature article reads
    # "1.0 m (located on the ship's mast)"; the accepted manuscript in the Cambridge
    # repository reads "10m". An observer one metre up a mast is nonsense, so 10 m is the
    # figure and the production typesetting corrupted it. The copy that looks most
    # authoritative is the broken one.
    #
    # WHERE WE DIFFER FROM THEM, deliberately. Their relation is sqrt(2*R*h) with no
    # refraction and R = 6378 km, giving 3.5716*sqrt(h); this uses k = 1.13, giving
    # 3.7945*sqrt(h) — about 6% more generous. And they add a flat 20 m landmark to every
    # one of 13,000 coastal points; this takes the land's own height from the DEM, which
    # is the correction Litvine et al. themselves make.
    "observer_height_m": 10.0,
    # SEAMARKS OFF (Stephen, 4 September 2026). They were stamped as sightline sources
    # for about an hour and are now disabled — the data, the fetcher and this code path
    # are kept, because the reasons are worth keeping with them.
    #
    # STEPHEN'S ARGUMENT: a light serves night navigation. By day what a mariner sees is
    # the land. That is the substantive objection and it stands on its own.
    #
    # AND THE MEASUREMENT AGREED, from an angle neither of us expected. Of 4,184 lights
    # inside the extent, 1,383 stand above the local terrain and so add any reach at all;
    # 56% of those are under 20 m, which is where the daylight objection bites hardest.
    # And the ones adding MOST are aviation obstruction lights on broadcast masts —
    # Wenvoe (+257 m), St Hilary (+215 m), Ben-a-chielt (+195 m), which are 20th-century
    # television transmitters. The single largest effect of a navigational dataset on
    # this surface came from TV masts.
    #
    # WHAT IS NOT THE ARGUMENT. I claimed a small mark cannot be resolved at its own
    # horizon and computed an angular size to prove it. That calculation was wrong: it
    # assumed the whole height visible at the horizon, when the horizon is by definition
    # where the TOP becomes tangent and a vanishing sliver is all that shows. The error
    # favoured the conclusion, which is the worst direction for an error to run.
    "use_seamarks": False,
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
    # NO BLIND SAILING (Stephen, 4 Sep 2026, and he said KEEP it). Zero, not 60.
    # I ran the rule as a call-time override and never changed the default, so the very
    # next pipeline run quietly restored the buffer — 14,991 cells back to 27,130, with
    # the out-of-sight and not-knowable states returning to a layer that had been trimmed
    # of them, and rewt-46's viewer re-broken downstream. A decision taken in an
    # experiment and not written into the configuration is not a decision.
    "buffer_km": 0.0,
    # THE EXTENT IS A DECLARED PARAMETER, not the mosaic's bounds. Geometry does not
    # bound this area: the continental shore is continuous, so a sight-plus-buffer
    # surface keeps connecting coastwise for as long as land is in the extent — it would
    # run to the Baltic and round Iberia. Where to stop must be SAID.
    #
    # Faroe was admitted on a bad rule and is now out: two buffers overlapping is two
    # blind zones touching, which is not a route. The test is whether a landmass's buffer
    # reaches water that is IN SIGHT of the existing area. Shetland-Faroe is 290 km with
    # 113 and 80 km of sight, leaving 97 km blind against a 60 km buffer. It fails.
    "close_hop_cells": 3,   # see CLOSE SHORT BLIND HOPS in main()
    "aoi": EXTENT,                   # tools/router/extent.py — one declaration
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
    obs = K * math.sqrt(cfg["observer_height_m"]) if cfg["observer_height_m"] else 0.0

    # THE BOUND COMES FROM LAND THAT CAN ACTUALLY SEE SEA, not from the tallest thing in
    # the box. Extending east put the Alps inside it: 4,792 m reaches 263 km and nearly
    # doubled the band count, for land some 600 km from any water in scope. Solve for it
    # instead — the tallest land within its own reach of the sea — which converges in a
    # couple of rounds because each round can only lower the bound.
    d_sea = ndimage.distance_transform_edt(
        ~sea, sampling=(py, px)) / 1000.0
    hmax = float(np.nanmax(elev))
    for _ in range(6):
        r = K * math.sqrt(hmax) + obs
        near_sea = land & (d_sea <= r)
        h2 = float(np.nanmax(elev[near_sea])) if near_sea.any() else hmax
        if h2 >= hmax - 1e-6:
            break
        hmax = h2
    rmax = K * math.sqrt(hmax) + obs
    print(f"  tallest land that can reach the sea: {hmax:.0f} m "
          f"(the box also holds {float(np.nanmax(elev)):.0f} m, too far inland to matter)")
    print(f"  land {land.sum():,} px, sea {sea.sum():,} px")
    print(f"  maximum reach {rmax:.1f} km  (square pixel {px:.0f} m)")

    # --- SEAMARKS AS SIGHTLINE SOURCES (Stephen, 4 Sep 2026) ----------------------
    # A light stands where mariners needed a mark, at a height somebody measured. It is
    # a far stronger claim about PLACE than Alvarez-Palau and Dunn's flat 20 m at every
    # coastal point, and a far weaker one about DATE — the list has none, and the dating
    # is a queued, deferred work package. See tools/router/lights.py for what that
    # accepts.
    #
    # A light casts sightlines whether or not it stands on land: that is what a
    # lighthouse on a rock is for. So sources are LAND HEIGHT where there is land, and
    # the light's own height at a light, whichever is greater — and the sea/land masks
    # are untouched, because a beacon is not a coastline.
    src_h = np.where(land, np.nan_to_num(elev, nan=0.0), 0.0).astype("float32")
    n_lights = 0
    lp = Path("tools/router/cache/lights/lights.json")
    if cfg["use_seamarks"] and lp.exists():
        lights = json.loads(lp.read_text())
        fwd_l = Transformer.from_crs(4326, cfg["crs"], always_xy=True)
        for L in lights:
            x, y = fwd_l.transform(L["lon"], L["lat"])
            c_ = int((x - dst_tr[2]) / dst_tr[0]); r_ = int((y - dst_tr[5]) / dst_tr[4])
            if 0 <= r_ < src_h.shape[0] and 0 <= c_ < src_h.shape[1]:
                if L["height_m"] > src_h[r_, c_]:
                    src_h[r_, c_] = L["height_m"]
                n_lights += 1
        print(f"  {n_lights:,} seamarks stamped as sightline sources "
              f"(median {sorted(l['height_m'] for l in lights)[len(lights)//2]:.0f} m)")
    # only a SEAMARK may raise the bound. Taking src_h.max() raised it by ALL LAND,
    # undoing the 'land that can reach the sea' reduction and putting the Alps back:
    # 138 bands where 95 were needed, and a summary reporting 4,792 m as the tallest
    # land that matters when the run had just printed 2,464.
    if n_lights:
        hmax = max(hmax, float(src_h.max()))
    rmax = K * math.sqrt(hmax) + obs

    bands = np.arange(cfg["band_km"], rmax + cfg["band_km"], cfg["band_km"])[::-1]
    visible = np.zeros(elev.shape, bool)      # AFTER reprojection: not (h, w) any more
    gov = np.zeros(elev.shape, "float32")
    print(f"  {len(bands)} bands of {cfg['band_km']} km, descending")
    for r_km in bands:
        h_need = ((r_km - obs) / K) ** 2
        if h_need > hmax:
            continue
        m = src_h >= h_need           # land at its own height, or a seamark at its own
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

    # --- CLOSE SHORT BLIND HOPS ---------------------------------------------------
    # Stephen found small pockets of sea just out of sight of land which a navigator
    # would cross without difficulty, the largest of them mid-Channel. The justification
    # is his and it is sound in three parts: the visibility test is approximate, what can
    # actually be seen depends on the weather in any case, and a short blind hop is not
    # the same proposition as a blind passage. It does NOT reopen blind sailing — a
    # uniform buffer grows the frontier outward everywhere, which is what he ruled out.
    # This fills only water that is ENCLOSED: a pocket qualifies when no point in it is
    # more than `close_hop_cells` cell-widths from water that does see land, so the open
    # ocean beyond the sighted zone can never qualify, however large the threshold.
    #
    # THE FILLED CELLS ARE NOT MARKED VISIBLE. They are blind water we accept crossing,
    # and the layer says so with `closed_hop`, because a rule that quietly promoted them
    # would leave the map claiming land is in sight where it is not.
    _c2c = h3.average_hexagon_edge_length(6, unit="km") * math.sqrt(3)
    hop_km = cfg["close_hop_cells"] * _c2c
    dvis = ndimage.distance_transform_edt(
        ~visible, sampling=(cfg["metres_per_pixel"],) * 2) / 1000.0
    _blind = sea & ~visible
    _lab, _n = ndimage.label(_blind, structure=ndimage.generate_binary_structure(2, 2))
    _deep = ndimage.maximum(dvis, _lab, range(1, _n + 1))
    _fill = [i + 1 for i in range(_n) if _deep[i] <= hop_km]
    closed = np.isin(_lab, _fill) if _fill else np.zeros_like(visible)
    print(f"  closing blind pockets within {cfg['close_hop_cells']} cells "
          f"({hop_km:.1f} km) of sighted water:")
    print(f"    {len(_fill):,} of {_n:,} pockets, {int(closed.sum()):,} px "
          f"({closed.sum() * (cfg['metres_per_pixel'] / 1000) ** 2:,.0f} km2)")
    _sz = ndimage.sum(np.ones_like(_lab), _lab, range(1, _n + 1))
    for i in sorted(_fill, key=lambda i: -_sz[i - 1])[:4]:
        _ys, _xs = np.nonzero(_lab == i)
        _lo, _la = back.transform(*rasterio.transform.xy(dst_tr, _ys.mean(), _xs.mean()))
        print(f"      {int(_sz[i-1]):>6,} px  deepest {_deep[i-1]:>5.1f} km  "
              f"{_la:.2f} N {_lo:.2f} E")

    # --- TRIM (H3-002 item 3) -----------------------------------------------------
    dblind = ndimage.distance_transform_edt(
        ~visible, sampling=(cfg["metres_per_pixel"],) * 2) / 1000.0
    keep_px = sea & (visible | closed | (dblind <= cfg["buffer_km"]))
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

    # The grid is built FROM these masks, so they are saved rather than recomputed:
    # two scripts deriving the same sea from the same source is two renderings of one
    # fact, and they would drift the first time one of them changed.
    # THE SIGHTLINE AND THE JOINS ARE DIFFERENT SIZES OF PROBLEM. The envelope is a
    # 100 km object and 930 m serves it; a river mouth is a 100 m object and 930 m
    # erases it. Built on the coarse mask the grid put every unattached terminus 3-67 km
    # from the nearest sea pixel, median 5.95 km, when section 6 measured the median
    # terminus at 143 m from water at the lowest tide. Both figures are right; they are
    # measurements of different rasters.
    #
    # So the SEA is saved at the fine resolution it is derived at, and VISIBLE at the
    # coarse one it is computed at. Still one derivation of each — deriving the sea twice
    # is the fault D-094 records, and this avoids it rather than trading it for another.
    fpx = cfg["metres_per_pixel"] * fine / dec
    ftr, fw2, fh2 = calculate_default_transform(
        src.crs, cfg["crs"], fw, fh, *b, resolution=fpx)
    # only the SEA: grid2 takes land as its complement, and deriving land separately
    # here would be a second rendering of the same fact
    fine_sea = np.zeros((fh2, fw2), "float32")
    reproject(source=ocean.astype("float32"), destination=fine_sea,
              src_transform=rasterio.transform.from_bounds(*b, fw, fh), src_crs=src.crs,
              dst_transform=ftr, dst_crs=cfg["crs"],
              resampling=Resampling.max, src_nodata=None, dst_nodata=0.0)
    np.savez_compressed("tools/router/cache/sightline_masks.npz",
                        visible=visible, keep=keep_px, sea=sea, land=land,
                        elev=elev.astype("float32"),
                        transform=np.array(dst_tr).reshape(-1)[:6],
                        crs=np.array([cfg["crs"]]), px=np.array([cfg["metres_per_pixel"]]),
                        fine_sea=(fine_sea > 0.5), fine_px=np.array([fpx]),
                        fine_transform=np.array(ftr).reshape(-1)[:6])
    print(f"  wrote sightline_masks.npz: visible {visible.shape} at "
          f"{cfg['metres_per_pixel']:.0f} m, sea {fine_sea.shape} at {fpx:.0f} m")

    # per-cell governing height: the tallest land that reaches this cell. This is the
    # thing the inversion makes visible and the per-sea-cell method never had — it says
    # WHICH land does the work, so a reader can see that Snowdon carries water a Norfolk
    # hill cannot.
    gv = gov[sea]; gvs = gv[order]
    gov_cell = np.maximum.reduceat(gvs, starts)
    kp = keep_px[sea][order]; keep_cell = np.maximum.reduceat(kp.astype(np.int8), starts).astype(bool)
    # VISIBLE IS *ANY* PIXEL, KNOWN WAS *ALL* — so a cell part-visible and part-unknowable
    # came out visible AND not-known, contradicting the definition the file itself
    # carries: only a NEGATIVE can be unknowable, because land outside the data cannot
    # make a visible cell invisible. 57 cells did that. At pixel level the invariant
    # holds; it was the aggregation that broke it, and the fix is to preserve it here.
    kn = known_px[sea][order]
    known_cell = np.minimum.reduceat(kn.astype(np.int8), starts).astype(bool)
    known_cell |= any_vis
    # --- DROP CELLS DETACHED FROM THE SEA NETWORK (Stephen) -----------------------
    # The pixel mask already requires water to reach the sea. That is not the same test
    # at CELL level: a pocket of water big enough for one res-6 cell, joined to the rest
    # only through a channel narrower than a cell, becomes an island of cells no route
    # can reach. A surface with unreachable pieces is not a routing surface.
    keptset = {c for c, k in zip(uniq, keep_cell) if k}
    seen, comps = set(), []
    for c in keptset:
        if c in seen:
            continue
        stack, comp = [c], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x)
            stack += [n for n in h3.grid_disk(x, 1) if n in keptset and n not in seen]
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    main = set(comps[0])
    lost = [c for comp in comps[1:] for c in comp]
    if lost:
        print(f"  {len(comps)} cell components; dropping {len(lost):,} cells in "
              f"{len(comps)-1} pieces detached from the network. The largest:")
        for comp in comps[1:6]:
            la_, lo_ = h3.cell_to_latlng(comp[0])
            print(f"    {len(comp):>4} cells around {la_:.2f} N {lo_:.2f} E")
        print(f"    ...and {sum(1 for comp in comps[1:] if len(comp) == 1)} single cells")
    keep_cell = np.array([c in main for c in uniq])

    # a cell is a closed hop where it holds filled water and sees nothing itself.
    # Folded here rather than beside `any_vis`, because the fill is decided after the
    # admission walk and `closed` does not exist yet at that point.
    any_closed = np.maximum.reduceat(
        closed[sea][order].astype(np.int8), starts).astype(bool) & ~any_vis
    print(f"  {int(any_closed.sum()):,} cells are closed short hops "
          f"(blind water we accept crossing, not marked visible)")

    feats = []
    for c, v, gh, kp_, kn_, cl_ in zip(uniq, any_vis, gov_cell, keep_cell,
                                      known_cell, any_closed):
        if not kp_:
            continue                      # trimmed: outside sight plus the buffer
        bnd = h3.cell_to_boundary(c)
        ring = [[round(x, 5), round(y, 5)] for y, x in bnd]
        ring.append(ring[0])
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"h3": c, "visible": bool(v),
                                     **({"closed_hop": True} if cl_ else {}),
                                     **({} if kn_ else {"known": False}),
                                     "gov_h_m": None if not v else int(round(float(gh))),
                                     "gov_reach_km": None if not v
                                     else round(K * math.sqrt(max(float(gh), 0)), 1)}})
    cell_ll = np.array([h3.cell_to_latlng(f["properties"]["h3"]) for f in feats]) \
        if feats else np.zeros((0, 2))
    out2 = Path("docs/router/data/sightline2_r6.geojson")
    out2.write_text(json.dumps({
        "type": "FeatureCollection",
        "properties": {
            "generation": generation(), "what": "sight of land, computed from the land outwards in reach bands",
            "method": "banded distance transform in " + cfg["crs"],
            "bands": int(len(bands)), "band_km": cfg["band_km"],
            "max_reach_km": round(rmax, 1),
            "blind_sailing_buffer_km": cfg["buffer_km"],
            "buffer_basis": ("NO BLIND SAILING (Stephen, 4 Sep 2026): the buffer is zero. "
                             "A cell is in the surface only if land is in sight from it, "
                             "and a landmass joins only when its sighted water TOUCHES "
                             "sighted water already admitted — two blind zones meeting is "
                             "not a route. The trimmed edge is therefore the limit of "
                             "sight itself, not a routing decision and not a coast. "
                             "A crossing that leaves sight of land — Land's End to Cork "
                             "among them — is therefore NOT in this surface. The blind "
                             "span of that crossing was measured on the superseded "
                             "buffered surface and is not restated here, because a figure "
                             "derived from a surface that no longer exists is worse than "
                             "no figure."
                             if not cfg["buffer_km"] else
                             "a ROUTING decision, not a horizon and not a coast — the "
                             "trimmed edge means nothing else."),
            "computation_domain": list(cfg["aoi"]),
            "cell_bounds": ([round(float(cell_ll[:, 1].min()), 3),
                             round(float(cell_ll[:, 0].min()), 3),
                             round(float(cell_ll[:, 1].max()), 3),
                             round(float(cell_ll[:, 0].max()), 3)] if len(cell_ll) else None),
            "computation_domain_note": "where the question was asked. The CELLS are what "
                                       "was found, and after trimming they cover less — "
                                       "about a degree of west Atlantic separates the "
                                       "two. Do not conflate them in a caption (rewt-46).",
            "trimmed": "cells out of sight of land are absent, not coloured (H3-002 "
                       "item 3). There is no unknown state left to render: `known` is "
                       "absent from every feature, and an absent `known` means answered.",
            "horizon_formula": f"range_km = {K:.4f} * sqrt(height_m), refraction_k = "
                               f"{cfg['refraction_k']}. NOT 3.86, which is k = 1.17.",
            "tallest_governing_land_m": (int(max(f["properties"]["gov_h_m"]
                                                 for f in feats
                                                 if f["properties"]["gov_h_m"] is not None))
                                         if any(f["properties"]["gov_h_m"] is not None
                                                for f in feats) else None),
            "tallest_governing_land_note": "if this exceeds 1,345 m — Ben Nevis — then "
                                           "land outside the British Isles is casting "
                                           "sightlines into the surface, and a reader who "
                                           "knows these islands will rightly wonder. "
                                           "rewt-46 caught 221 such cells reaching 1,823 m "
                                           "while a buffer regression was live; under the "
                                           "no-blind-sailing rule there are none.",
            "seamarks": int(n_lights),
            "seamarks_basis": ("OFF. Land only: by day a mariner sees the land, and a "
                               "light serves the night (Stephen, 4 Sep 2026). Of 4,184 "
                               "lights in the extent only 1,383 stood above local "
                               "terrain, 56% of those under 20 m, and the largest "
                               "contributors were aviation obstruction lights on "
                               "20th-century television masts. Kept as a rejected option "
                               "with its reasons, not deleted. Previously: NGA List of "
                               "Lights, public domain, stamped as sightline "
                               "sources at their own stated heights. THE LIST HAS NO "
                               "TEMPORAL INFORMATION — these are the lights standing now, "
                               "mostly 18th and 19th century — and the dating is a queued, "
                               "deferred work package. Until it lands, a reach that depends "
                               "on a light is a reach available at that later date and not "
                               "necessarily to an earlier mariner."),
            "observer_height_basis": ("10 m, a lookout at the masthead. After "
                "Alvarez-Palau and Dunn (2019) as reported by Litvine, Lewis and Starzec "
                "(2024), doi:10.1057/s41599-024-02906-9 (CC BY 4.0), whose coastal "
                "routing model for England and Wales takes the observer at 10 m on the "
                "ship's mast. NOTE the typeset article reads '1.0 m (located on the "
                "ship's mast)' where the accepted manuscript reads '10m' — an observer "
                "one metre up a mast is nonsense, and the version of record is the "
                "corrupted one. Ranges here are therefore NOT floors at sea level: they "
                "assume a masthead lookout, and a deck observer at 2 m would see "
                "an observer term of 5.4 km, which is 6.6 km LESS than the 12.0 km "
                "used here — 5.4 is that observer's own horizon, NOT the difference."),
            "gov_h_m_provenance":
            "gov_h_m is a height off EMODnet's land side, which is ASTER, SRTM3 and "
            "EU-DEM blended with no per-pixel provenance (D-098). It is NOT a "
            "surveyed summit and should not be quoted as one. It is fit for deciding "
            "whether a coast is in sight, where a 3% height error moves the range by "
            "1.49%.",
        "gov_h_m_definition": "the tallest land that reaches this cell — the band "
                                  "that first marked it. Absent where nothing reaches.",
            "gov_reach_km_definition": ("DERIVED FROM gov_h_m, not measured alongside "
                                       f"it: {K:.4f} * sqrt(gov_h_m), exactly. One "
                                       "variable in "
                                       "two units. Shown side by side the pair reads as "
                                       "two measurements agreeing, which is the most "
                                       "persuasive thing a single measurement can "
                                       "pretend to be — rewt-46 found 67 distinct heights "
                                       "and 67 distinct pairs across all cells. Do not "
                                       "cite them as corroborating each other. "
                                       "EXCLUDES THE OBSERVER TERM: admission added "
                                       f"{obs:.1f} km on top of this, so the sighted "
                                       "zone reaches that much further than "
                                       "gov_reach_km says. The per-coast medians "
                                       "exclude it too, which keeps Britain and the "
                                       "Low Countries a like-for-like comparison of "
                                       "the LAND — but neither figure is the distance "
                                       "at which a cell was admitted."),
            "distance_crs": cfg["crs"], "distance_crs_worst_error_pct": 0.33,
            "validated_against": "exact WGS84 geodesics on 250 sample points: 246 agree, "
                                 "and all 4 disagreements are conservative (the raster "
                                 "misses visibility, never invents it)",
            "observer_height_m": cfg["observer_height_m"],
            "attribution": ATTRIBUTION, "use_constraint": "DO NOT USE FOR NAVIGATION"},
        "features": feats}, default=float))
    print(f"wrote {out2} ({out2.stat().st_size/1e6:.1f} MB, {len(feats):,} cells)")

    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(),
        "method": "land-outwards, banded by reach",
        "bands": int(len(bands)), "band_km": cfg["band_km"],
        "max_reach_km": round(rmax, 1), "tallest_land_m": round(hmax),
        "tallest_land_m_note": "the tallest land that can reach the sea, not the tallest in the box — the extent also holds the Alps at 4,792 m, some 600 km from any water in scope, and banding to their horizon costs 43 extra distance transforms for nothing.",
        "horizon_km_per_sqrt_metre": round(K, 4),
        "distance_crs": cfg["crs"],
        "distance_crs_worst_error_pct": 0.33,
        "observer_height_m": cfg["observer_height_m"],
        "cells_considered": int(len(uniq)),
        "cells_in_sight_before_admission": int(any_vis.sum()),
        "cells_after_admission": int(keep_cell.sum()),
        "cells_published": None,
        "counts_note": "`cells_published` is the only count that describes the layer; it is filled by reach.py after the week trim, which happens downstream of this file. The others are earlier populations, and the check panel was showing the largest of them (59,830) as though it were the layer (14,991).",

        "detached_cells_dropped": int(len(lost)) if lost else 0,
        "detached_note": "a pocket of water joined to the rest only through a channel "
                         "narrower than a cell becomes an island of cells no route can "
                         "reach. Dropped, and named in the run output — most are German "
                         "and Norwegian inlets and Irish loughs severed by the 232 m mask, "
                         "which is the Loch Etive limit in another place.",
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
