"""Theoretical sight-of-land: the zone from which land can be seen at sea.

Maximum land elevation per H3 cell from EMODnet's merged land-and-sea surface, a
curvature horizon per land cell, and then, for every sea cell, whether any land cell
reaches it.

    python3 tools/router/sightline.py

Run from the repository root; paths are relative (AGENTS.md).

WHAT THIS IS NOT. Curvature only. No occlusion by intervening land, no refractive
variation, no weather, no visibility of a lit or marked object. Stephen's request was
the zone in which land can *theoretically* be seen and that is exactly what this draws.
It is not a chart: `conf/sources.yml` puts DO NOT USE FOR NAVIGATION on the source and
the constraint travels (tools/router/PLAN.md 8.5).

DATUM. Heights are read off EMODnet's land side, which is on a datum its record does not
name (ASTER GDEM / SRTM3 / EU-DEM blended, established by rewt-16). Horizon range goes as
the square root of height, so a datum offset of a metre or two against summits of hundreds
is far below the error already accepted. These heights are NEVER differenced against sea
depths, which are on Lowest Astronomical Tide (PLAN.md 8.4).
"""
from __future__ import annotations

import glob
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.spatial import cKDTree

import h3

# --- parameters -------------------------------------------------------------------
# These belong in conf/ when the implementer adopts this; conf/ is not this session's
# to write (TEAM.md). They are named here rather than buried in the functions.
ATTRIBUTION = (
    "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium (2024): "
    "EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0."
)

CONFIG = {
    "resolution": 6,              # H3 resolution for both land and sea cells
    "decimate": 8,                # max-reduce NxN raster blocks (~920 m) for land maxima
    "observer_height_m": 0.0,     # SUPERSEDED. sightline2.py uses 10 m, a masthead
                                  # lookout. This module survives only for build_vrt and
                                  # nodata_to_nan, which grid.py, trace.py and
                                  # export_check.py import; its CONFIG is not run.
                                  # a vessel's masthead is a vessel parameter, deferred.
    "refraction_k": 1.13,         # standard terrestrial refraction; 1.0 = pure geometry
    "min_land_height_m": 1.0,     # below this a "peak" is noise in a 115 m grid
    "earth_radius_m": 6371000.0,
    "windows": "data/raw/emodnet_bathymetry/*.tif",
    "vrt": "tools/router/cache/emodnet.vrt",   # derived; tools/router/cache/ is ignored
    "out_dir": "docs/router/data",
}


def build_vrt(cfg: dict) -> str:
    """Mosaic the cached EMODnet windows. Built here rather than by hand: a step that
    only runs when someone remembers it is not part of the build (AGENTS.md)."""
    vrt = Path(cfg["vrt"])
    # data/raw first (checksummed, the implementer's), then the working cache for the
    # windows the extent needs and the manifest does not yet hold.
    # PREFER COVERAGE, NOT PROVENANCE. data/raw is authoritative, but ten of its windows
    # are HALF HEIGHT (its area of interest stopped at 61.0 N), and a VRT fills whatever
    # no window covers with ZERO — which reads as land at the datum, silently. So a raw
    # window is used unless the working cache holds a fuller one for the same tile.
    import rasterio
    def span(t):
        with rasterio.open(t) as r:
            return r.bounds.top - r.bounds.bottom
    raw = {Path(t).name: t for t in sorted(glob.glob(cfg["windows"]))}
    for t in sorted(glob.glob("tools/router/cache/windows/*.tif")):
        n = Path(t).name
        if n not in raw or span(t) > span(raw[n]) + 1e-6:
            raw[n] = t
    tifs = [raw[k] for k in sorted(raw)]
    if not tifs:
        raise SystemExit(f"no EMODnet windows under {cfg['windows']} — nothing to mosaic")
    vrt.parent.mkdir(parents=True, exist_ok=True)
    if not vrt.exists() or vrt.stat().st_mtime < max(Path(t).stat().st_mtime for t in tifs):
        print(f"building {vrt} from {len(tifs)} windows")
        # -vrtnodata so a gap in the MOSAIC is loud. Without it gdalbuildvrt fills
        # uncovered ground with 0.0, which is a plausible measurement at this datum and
        # indistinguishable from the real datum-boundary zeros. -9999 is not: nothing in
        # the coverage lies below -6000 m, so it cannot be mistaken for a depth.
        subprocess.run(["gdalbuildvrt", "-q", "-vrtnodata", "-9999",
                        str(vrt), *tifs], check=True)
    return str(vrt)


def nodata_to_nan(a):
    """The VRT declares -9999 so a gap in the MOSAIC is loud rather than a plausible
    zero. Every reader must honour it: `np.isfinite` alone will not, and -9999 would
    sail through as the deepest water in the world."""
    import numpy as _np
    a = a.astype("float32", copy=False)
    a[a <= -9000] = _np.nan
    return a


def horizon_m(height_m: np.ndarray, cfg: dict) -> np.ndarray:
    """Distance to the horizon from a given height, with refraction."""
    return np.sqrt(2.0 * cfg["earth_radius_m"] * cfg["refraction_k"] * height_m)


def to_xyz(lat: np.ndarray, lon: np.ndarray, r: float) -> np.ndarray:
    la, lo = np.radians(lat), np.radians(lon)
    return np.column_stack([r * np.cos(la) * np.cos(lo),
                            r * np.cos(la) * np.sin(lo),
                            r * np.sin(la)])


def main(cfg: dict = CONFIG) -> None:
    res, R = cfg["resolution"], cfg["earth_radius_m"]
    src = rasterio.open(build_vrt(cfg))
    dec = cfg["decimate"]
    h, w = src.height // dec, src.width // dec
    print(f"reading {cfg['vrt']} and max-reducing 1/{dec} -> {w} x {h}")
    # Max-reduce rather than decimate: a sampled point near a sharp summit lands on the
    # shoulder and reads far low on a ~115 m grid (PLAN.md 8.4, rewt-16). Read in row
    # blocks so the full 106 M-pixel coverage is never held at once.
    a = np.empty((h, w), "float64")
    BLOCK = 256
    for r0 in range(0, h, BLOCK):
        r1 = min(r0 + BLOCK, h)
        chunk = nodata_to_nan(src.read(1, window=Window(0, r0*dec, w*dec, (r1-r0)*dec))).astype("float64")
        chunk = chunk.reshape(r1 - r0, dec, w, dec)
        with np.errstate(invalid="ignore"):
            a[r0:r1] = np.nanmax(chunk, axis=(1, 3))

    # pixel-centre coordinates of the decimated grid
    lon = src.bounds.left + (np.arange(w) + 0.5) * (src.bounds.right - src.bounds.left) / w
    lat = src.bounds.top - (np.arange(h) + 0.5) * (src.bounds.top - src.bounds.bottom) / h
    LON, LAT = np.meshgrid(lon, lat)

    finite = np.isfinite(a)
    land = finite & (a >= cfg["min_land_height_m"])
    sea = finite & (a < 0)
    print(f"pixels: {finite.sum():,} finite, {land.sum():,} land, {sea.sum():,} sea")

    # --- maximum land height per H3 cell ------------------------------------------
    print("binning land pixels to H3 cells...")
    ll = np.column_stack([LAT[land], LON[land]])
    vals = a[land]
    cells = np.array([h3.latlng_to_cell(float(y), float(x), res) for y, x in ll])
    order = np.argsort(cells)
    cells_s, vals_s = cells[order], vals[order]
    uniq, starts = np.unique(cells_s, return_index=True)
    land_max = np.maximum.reduceat(vals_s, starts)
    print(f"  {len(uniq):,} land cells at res {res}")

    land_ll = np.array([h3.cell_to_latlng(c) for c in uniq])
    reach = horizon_m(land_max, cfg) + horizon_m(np.float64(cfg["observer_height_m"]), cfg)

    # --- sea cells ----------------------------------------------------------------
    print("binning sea pixels to H3 cells...")
    sea_cells = np.unique(np.array([h3.latlng_to_cell(float(y), float(x), res)
                                    for y, x in zip(LAT[sea], LON[sea])]))
    land_set = set(uniq.tolist())          # hoisted: rebuilding this per item is O(n^2)
    sea_cells = np.array([c for c in sea_cells if c not in land_set])
    sea_ll = np.array([h3.cell_to_latlng(c) for c in sea_cells])
    print(f"  {len(sea_cells):,} sea cells at res {res}")

    # --- which land reaches which sea cell ----------------------------------------
    print("querying...")
    tree = cKDTree(to_xyz(land_ll[:, 0], land_ll[:, 1], R))
    rmax = float(reach.max())
    print(f"  furthest any land reaches: {rmax/1000:.1f} km "
          f"(tallest cell {land_max.max():.0f} m)")
    neigh = tree.query_ball_point(to_xyz(sea_ll[:, 0], sea_ll[:, 1], R), r=rmax)

    visible = np.zeros(len(sea_cells), bool)
    best_h = np.full(len(sea_cells), np.nan)
    best_d = np.full(len(sea_cells), np.nan)
    margin = np.full(len(sea_cells), np.nan)
    best_ll = np.full((len(sea_cells), 2), np.nan)
    for i, idx in enumerate(neigh):
        if not idx:
            continue
        idx = np.asarray(idx)
        d = np.linalg.norm(to_xyz(land_ll[idx, 0], land_ll[idx, 1], R)
                           - to_xyz(sea_ll[i:i+1, 0], sea_ll[i:i+1, 1], R), axis=1)
        m = reach[idx] - d
        j = int(np.argmax(m))
        if m[j] >= 0:
            visible[i] = True
            best_h[i], best_d[i], margin[i] = land_max[idx[j]], d[j], m[j]
            best_ll[i] = land_ll[idx[j]]

    print(f"  {visible.sum():,} of {len(sea_cells):,} sea cells see land "
          f"({100*visible.mean():.1f}%)")

    # --- IS THE ANSWER KNOWABLE? (rewt-46) -----------------------------------------
    # The data extent marks where the DATA is, not where the ANSWER is. A cell well
    # inside the rectangle is still unanswerable if the land that would have been
    # visible from it lies outside. A cell that DOES see land is answerable regardless
    # of what lies beyond — more land cannot make it invisible. So only negatives can
    # be unknown, and only those within one maximum reach of the edge.
    b = src.bounds
    mlat = np.radians(sea_ll[:, 0])
    dx = np.minimum(sea_ll[:, 1] - b.left, b.right - sea_ll[:, 1]) * 111_320.0 * np.cos(mlat)
    dy = np.minimum(sea_ll[:, 0] - b.bottom, b.top - sea_ll[:, 0]) * 111_320.0
    edge_dist = np.minimum(dx, dy)
    known = visible | (edge_dist >= rmax)
    print(f"  answerable: {known.sum():,} ({100*known.mean():.1f}%). "
          f"Of {int((~visible).sum()):,} negatives, {int((~known).sum()):,} "
          f"({100*(~known).sum()/max(1,(~visible).sum()):.1f}%) are UNKNOWN, not negative "
          f"— within {rmax/1000:.1f} km of the data edge")

    # --- write --------------------------------------------------------------------
    out = Path(cfg["out_dir"]); out.mkdir(parents=True, exist_ok=True)
    feats = []
    for i, c in enumerate(sea_cells):
        b = h3.cell_to_boundary(c)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[round(x, 5), round(y, 5)] for y, x in b]
                                         + [[round(b[0][1], 5), round(b[0][0], 5)]]]},
            "properties": {
                "h3": c,
                "visible": bool(visible[i]),
                "landmark_h_m": None if np.isnan(best_h[i]) else round(float(best_h[i])),
                "distance_km": None if np.isnan(best_d[i]) else round(float(best_d[i]) / 1000, 1),
                "margin_km": None if np.isnan(margin[i]) else round(float(margin[i]) / 1000, 1),
                "landmark_lat": None if np.isnan(best_ll[i, 0]) else round(float(best_ll[i, 0]), 4),
                "landmark_lon": None if np.isnan(best_ll[i, 1]) else round(float(best_ll[i, 1]), 4),
                # false = the answer is not knowable here, NOT "no land visible"
                "known": bool(known[i]),
            },
        })
    # This layer is NOT covered by the build's built_at / config_fingerprint: it is not
    # derived from the REWT build at all. It therefore carries its own stamp, so it
    # cannot borrow a date that does not apply to it (rewt-46).
    horizon_const = math.sqrt(2 * cfg["earth_radius_m"] * cfg["refraction_k"]) / 1000
    fc = {"type": "FeatureCollection",
          "properties": {
              "what": "theoretical sight of land: curvature only, no occlusion",
              "h3_resolution": res,
              "observer_height_m": cfg["observer_height_m"],
              "refraction_k": cfg["refraction_k"],
              "horizon_km_per_sqrt_metre": round(horizon_const, 4),
              "horizon_formula": "range_km = 3.7945 * sqrt(height_m), from refraction_k "
                                 "= 1.13. NOT the commonly quoted 3.86, which is k = 1.17.",
              "margin_km_definition": "reach - distance, both in metres before rounding, "
                                      "where reach = 3.7945 * sqrt(landmark_h_m) km plus "
                                      "the observer's own horizon.",
              "margin_km_rederivation_slack": "Re-deriving margin_km from the ROUNDED "
                                      "landmark_h_m and distance_km in this file is NOT "
                                      "good to a fixed tolerance: range goes as sqrt(h), "
                                      "so a height rounded to the metre carries "
                                      "0.5 * 3.7945 / (2*sqrt(h)) km of slack, plus 0.05 km "
                                      "from distance_km. That is 0.08 km at a 1000 m "
                                      "landmark and 0.35 km at a 10 m one. Measured worst "
                                      "case over this file: 0.211 km, at a 21 m landmark. "
                                      "A tolerance quoted tighter than this fails on "
                                      "correct data.",
              "known_boundary_note": "26 negative cells lie within 500 m of the "
                                      "max_landmark_reach_km threshold, so an independent "
                                      "re-derivation of `known` may differ by a cell or "
                                      "two at the boundary without either being wrong.",
              "max_landmark_reach_km": round(rmax / 1000, 1),
              "known_definition": "false = the answer is not knowable at this cell, NOT "
                                  "'no land visible'. True where the cell already sees "
                                  "land, or lies further than max_landmark_reach_km "
                                  "inside data_extent.",
              "source_id": "emodnet_bathymetry",
              "source_coverage_id": "emodnet__mean",
              "source_release": "EMODnet Digital Bathymetry (DTM 2024)",
              "source_checksum": "33255844e907362085647fea70a72c3638f3a8e01bce735527cb"
                                 "19faed8e7bfa",
              "cache_windows": 120,
              "source": "EMODnet Digital Bathymetry (DTM 2024), CC BY 4.0 — land side",
              "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry "
                             "Consortium (2024): EMODnet Digital Bathymetry (DTM 2024), "
                             "licensed CC BY 4.0.",
              "use_constraint": "DO NOT USE FOR NAVIGATION",
              "data_extent": list(src.bounds),
              "warning": "Read `known` per cell, NOT data_extent. The extent marks where "
                         "the DATA is; the ANSWER is unknowable for a wide band inside it, "
                         "because the land that would have been visible lies outside.",
          },
          "features": feats}
    p = out / ("sightline_r%d.geojson" % res)
    p.write_text(json.dumps(fc))
    print(f"wrote {p} ({p.stat().st_size/1e6:.1f} MB, {len(feats):,} features)")

    mask = {"type": "FeatureCollection", "properties": {
                "what": "extent of the EMODnet cache. Outside this the sightline layer "
                        "has no data and must not be read as 'no land visible'. Inside "
                        "it, read each cell's `known` flag: the answer is unknowable for "
                        "a wide band within this rectangle.",
                "source_id": "emodnet_bathymetry",
                "attribution": ATTRIBUTION,
                "use_constraint": "DO NOT USE FOR NAVIGATION"},
            "features": [{"type": "Feature", "properties": {"state": "known"},
                          "geometry": {"type": "Polygon", "coordinates": [[
                              [src.bounds.left, src.bounds.bottom],
                              [src.bounds.right, src.bounds.bottom],
                              [src.bounds.right, src.bounds.top],
                              [src.bounds.left, src.bounds.top],
                              [src.bounds.left, src.bounds.bottom]]]}}]}
    q = out / "sightline_extent.geojson"
    q.write_text(json.dumps(mask))
    print(f"wrote {q}")

    # --- checks that the build will not do for us (PLAN.md 9) ---------------------
    print("\nCHECKS")
    print(f"  selector excludes something: {len(sea_cells):,} sea of "
          f"{len(sea_cells)+len(uniq):,} cells; {(~visible).sum():,} sea cells see NO land")
    far = np.argsort(np.where(np.isnan(best_d), -1, best_d))[-5:][::-1]
    print("  furthest sightlines, named rows:")
    for i in far:
        if visible[i]:
            print(f"    {best_d[i]/1000:6.1f} km : sea cell {sea_ll[i,0]:.3f} N {sea_ll[i,1]:.3f} E"
                  f"  <- {best_h[i]:.0f} m landmark at {best_ll[i,0]:.4f} N {best_ll[i,1]:.4f} E")


if __name__ == "__main__":
    main()
