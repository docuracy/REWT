"""The banded H3 sea grid: fine near the coast, coarse offshore.

    python3 tools/router/grid.py [resolution]

Run from the repository root; paths are relative (AGENTS.md).

THE BANDING IS EMERGENT, NOT SPECIFIED (PLAN.md 5.1). At resolution r a cell is kept as
sea if its centroid is further from land than `2 x edge_length(r)`; a cell entirely inside
land is dropped; anything else is replaced by its seven children at r+1 and tested again.
Because the threshold is the cell's OWN size, the bands scale themselves and cannot
disagree with the geometry they describe.

WHY THE DISTANCE TEST SUBSUMES THE INTERSECTION TEST. An H3 cell's circumradius is about
its edge length, so a centroid further than `2 x edge` from land cannot lie in a cell that
touches land. The predecessor tests both because it intersects polygons; working from a
distance transform, one test does.

THE COAST HERE IS LOWEST ASTRONOMICAL TIDE, from EMODnet's sign change, and that is
deliberate (PLAN.md 4): a ship cannot cross a bank that dries, so a low-water land mask
makes drying ground impassable by construction. Boundary-Line's high water line is the
coast for the RIVER end of the join, in PLAN.md 7, not for this.

NOT A CHART. conf/sources.yml carries DO NOT USE FOR NAVIGATION and it travels.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds as _fb
from scipy import ndimage

import h3

from extent import EXTENT
from sightline import build_vrt, nodata_to_nan

CONFIG = {
    "coastal_sea_resolution": 9,   # PLAN.md 5.2: the floor, set by the bathymetry
    "aoi": EXTENT,
    "start_resolution": 3,
    "decimate": 2,                 # ~230 m working grid for the distance transforms
    "windows": "data/raw/emodnet_bathymetry/*.tif",
    "vrt": "tools/router/cache/emodnet.vrt",
    "out_dir": "tools/router/cache",
    "summary": "docs/router/data/grid_summary.json",
    # A COVERAGE GAP ARRIVES AS EXACT ZERO, NOT AS NaN. Established against the live
    # service: asked for Greenland's interior, inside its declared envelope but outside
    # its coverage, EMODnet returns HTTP 200 and a valid GeoTIFF of 100% exact 0.0 with
    # no nodata declared. The same shape is already recorded on ea_lidar_composite_dtm_1m,
    # which answers 0.00 m for Welsh ground it does not hold. Absence is rendered as a
    # plausible measurement AT THE DATUM, so `>= 0` would class it as land and drop it
    # silently. Measured over the 120 cached windows, genuine datum-boundary zeros are a
    # thin coastal scatter: 0.092% overall, worst window 0.711%, largest contiguous blob
    # 4,047 pixels. A gap is three orders of magnitude away from that, so the separation
    # is wide and these thresholds are not finely tuned.
    "max_zero_fraction": 0.05,        # 5% of the grid exactly 0.0 -> refuse
    "max_zero_blob_px": 50_000,       # one contiguous zero region this big is a gap
}


def load_masks(cfg: dict):
    """Land/sea masks and the two distance transforms, in metres."""
    src = rasterio.open(build_vrt(cfg))
    dec = cfg["decimate"]
    # clip to the DECLARED extent, not the mosaic's bounds — two of its four edges are
    # declared rather than derived, and the mosaic may hold more than the extent claims
    aw = _fb(*cfg["aoi"], src.transform)
    off_r, off_c = int(aw.row_off), int(aw.col_off)
    h, w = int(aw.height) // dec, int(aw.width) // dec
    b = rasterio.coords.BoundingBox(*rasterio.windows.bounds(
        Window(off_c, off_r, w * dec, h * dec), src.transform))
    print(f"  extent (declared) {[round(v, 2) for v in b]}")
    print(f"reading and max-reducing 1/{dec} -> {w} x {h}")
    # THREE REDUCTIONS, NOT ONE. A single max-reduce was the first version and it is
    # wrong here: max over a block containing any land is land, so land DILATES and the
    # sea is eroded by up to a pixel all along the coast. That is fine for elevation
    # (sightline.py wants peaks preserved) and quietly destructive for a land/sea mask,
    # which is what it was copied across to do. A block can legitimately be BOTH — that
    # is what a coastline is — so the two masks are reduced independently.
    has_land = np.empty((h, w), bool)
    has_sea = np.empty((h, w), bool)
    all_zero = np.empty((h, w), bool)
    depth = np.full((h, w), np.nan, "float32")
    for r0 in range(0, h, 256):
        r1 = min(r0 + 256, h)
        c = nodata_to_nan(src.read(1, window=Window(
            off_c, off_r + r0 * dec, w * dec, (r1 - r0) * dec)))
        c = c.reshape(r1 - r0, dec, w, dec)
        fin = np.isfinite(c)
        has_land[r0:r1] = np.any(fin & (c >= 0), axis=(1, 3))
        has_sea[r0:r1] = np.any(fin & (c < 0), axis=(1, 3))
        all_zero[r0:r1] = np.all(fin & (c == 0.0), axis=(1, 3))
        with np.errstate(invalid="ignore"):
            # all-land blocks have no sea pixel and yield NaN here, which is correct
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                depth[r0:r1] = np.nanmin(np.where(fin & (c < 0), c, np.nan), axis=(1, 3))
    a = depth

    # --- coverage gaps, which arrive as exact zero (see CONFIG) --------------------
    # a solid gap reduces to an all-zero block; scattered datum zeros do not
    zero = all_zero
    zf = zero.sum() / zero.size
    gap = np.zeros_like(zero)
    biggest = 0
    if zero.any():
        lab, _ = ndimage.label(zero)
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        biggest = int(sizes.max())
        big_ids = np.nonzero(sizes >= cfg["max_zero_blob_px"])[0]
        if big_ids.size:
            gap = np.isin(lab, big_ids)
    print(f"  exact zeros {zero.sum():,} ({100*zf:.4f}%), largest contiguous "
          f"{biggest:,} px, treated as gap {gap.sum():,}")
    if zf > cfg["max_zero_fraction"]:
        raise SystemExit(
            f"REFUSING: {100*zf:.2f}% of the surface is exactly 0.0, against 0.092% "
            f"measured over the cached windows. That is what a coverage gap looks like "
            f"here, not a datum boundary. Go and look before building on it.")
    if gap.any():
        print(f"  ** {gap.sum():,} pixels are a contiguous zero region and are being "
              f"treated as NO DATA, not as land. Holes are fatal here **")

    # max-reduction helps rather than hurts here: a max over a block containing any
    # non-zero is non-zero, so scattered datum zeros shrink while a solid gap survives.
    land = has_land & ~gap
    sea = has_sea & ~gap

    # --- THE SEA IS WATER THAT REACHES THE SEA ------------------------------------
    # `elevation < 0` is not the same test. The Fens lie below the datum and are dry
    # land: EMODnet reads -2.3 m at Downham Market. Admitting them made 3,028 inland
    # water bodies, 3,904 graph components and 2,303 cells with no edge at all — a
    # routing surface with pockets of unreachable "sea" in Cambridgeshire.
    #
    # This is PLAN.md's own question turned seaward. The river network asks whether
    # water can get to the sea; the grid must ask the same of itself, or it asserts
    # navigable water where a ship could never be.
    # 8-connectivity: a channel that steps diagonally is still a channel. It drops
    # 57,880 blocks where the 4-connected default drops 71,192.
    lab, _ = ndimage.label(sea, structure=ndimage.generate_binary_structure(2, 2))
    border = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    border.discard(0)
    ocean = np.isin(lab, list(border))
    orphan = sea & ~ocean
    if orphan.any():
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        orphan_ids = [i for i in np.unique(lab[orphan]) if i]
        print(f"  dropped {orphan.sum():,} sea blocks ({100*orphan.sum()/sea.sum():.2f}%) "
              f"in {len(orphan_ids):,} bodies that do not reach the sea")
        # NAME THEM, AND SORT THE TWO POPULATIONS APART. Most are genuine: ground below
        # the datum that is dry land — the Fens read -2.3 m at Downham Market. But a real
        # sea loch whose entrance EMODnet cannot resolve is dropped identically, and
        # Loch Etive is one: the Connel narrows read +6.8 m and the Falls of Lora +0.4 m,
        # so a 200 m channel has been averaged into land by a 115 m grid. DEPTH separates
        # them without judgement — drained fen is shallow, a sea loch is not.
        # One labelled pass, not one boolean mask per body: 11,564 masks over a 26 M
        # array is quadratic and does not finish.
        filled = np.where(np.isfinite(depth), depth, 0.0)
        dmins = np.array(ndimage.minimum(filled, labels=lab, index=orphan_ids))
        boxes = ndimage.find_objects(lab)

        def ll(r, c):
            return (b.top - (r + 0.5) * (b.top - b.bottom) / sea.shape[0],
                    b.left + (c + 0.5) * (b.right - b.left) / sea.shape[1])

        deep = [(int(sizes[i]), float(d), i)
                for i, d in zip(orphan_ids, dmins) if d < -10.0]
        print(f"    of {len(orphan_ids):,} bodies, {len(deep):,} reach deeper than 10 m "
              f"and are the suspicious ones — shallow ground below the datum is not a loch")
        for n, dmin, i in sorted(deep, key=lambda t: -t[0])[:6]:
            sl = boxes[i - 1]
            la0, lo0 = ll(sl[0].stop - 1, sl[1].start)
            la1, lo1 = ll(sl[0].start, sl[1].stop - 1)
            print(f"    {n:>7,} blocks, to {dmin:7.1f} m, within "
                  f"{la0:.3f}-{la1:.3f} N  {lo0:.3f}-{lo1:.3f} E")
        # PUBLISHED, not merely printed. AGENTS.md: never delete a geometry to correct
        # it — retire it with a reason and keep it. These are water this bathymetry
        # severs from the sea, and a reader must be able to see what was lost.
        cfg["_severed"] = [
            {"blocks": n, "min_depth_m": round(d, 1),
             "lat": [round(ll(boxes[i-1][0].stop - 1, boxes[i-1][1].start)[0], 4),
                     round(ll(boxes[i-1][0].start, boxes[i-1][1].stop - 1)[0], 4)],
             "lon": [round(ll(boxes[i-1][0].stop - 1, boxes[i-1][1].start)[1], 4),
                     round(ll(boxes[i-1][0].start, boxes[i-1][1].stop - 1)[1], 4)]}
            for n, d, i in sorted(deep, key=lambda t: -t[0])]
        orphan_deep = sum(n for n, _, _ in deep)
        print(f"    blocks in deep orphans: {orphan_deep:,} of {orphan.sum():,} "
              f"({100*orphan_deep/orphan.sum():.1f}%) — the rest is ground below the datum")
    sea = ocean
    both = land & sea
    print(f"  {land.sum():,} blocks hold land, {sea.sum():,} hold sea, "
          f"{both.sum():,} hold both (the coastline itself)")

    # metres per pixel: north-south is constant, east-west shrinks with latitude. Use the
    # north-south pitch for both and correct the east-west axis by cos(lat) via sampling,
    # which is what `sampling=` is for.
    lat0, lat1 = b.bottom, b.top
    midlat = (lat0 + lat1) / 2
    m_per_deg = 111_320.0
    py = (lat1 - lat0) / h * m_per_deg
    px = (b.right - b.left) / w * m_per_deg * np.cos(np.radians(midlat))
    print(f"  pixel {px:.0f} m east-west at {midlat:.1f}N, {py:.0f} m north-south")

    print("  distance transforms...")
    d_land = ndimage.distance_transform_edt(~land, sampling=(py, px)).astype("float32")
    d_sea = ndimage.distance_transform_edt(~sea, sampling=(py, px)).astype("float32")
    return src, b, a, d_land, d_sea


def sampler(bounds, arr):
    """Sample a clipped, decimated array at lon/lat, returning nan off-grid.

    It takes BOUNDS rather than the dataset: the arrays are clipped to the declared
    extent, so mapping through the mosaic's bounds would place every sample wrongly —
    and silently, because the result is still a number.
    """
    b = bounds
    h, w = arr.shape

    def f(lat, lon):
        col = ((lon - b.left) / (b.right - b.left) * w).astype(int)
        row = ((b.top - lat) / (b.top - b.bottom) * h).astype(int)
        ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
        out = np.full(len(lat), np.nan, "float32")
        out[ok] = arr[row[ok], col[ok]]
        return out, ok

    return f


def main(cfg: dict = CONFIG) -> None:
    R = cfg["coastal_sea_resolution"]
    src, b, depth, d_land, d_sea = load_masks(cfg)
    s_land = sampler(b, d_land)
    s_sea = sampler(b, d_sea)
    s_depth = sampler(b, depth)

    aoi = {"type": "Polygon", "coordinates": [[
        [b.left, b.bottom], [b.right, b.bottom], [b.right, b.top],
        [b.left, b.top], [b.left, b.bottom]]]}

    r = cfg["start_resolution"]
    cells = list(h3.h3shape_to_cells(h3.geo_to_h3shape(aoi), r))
    print(f"\nstart: {len(cells):,} cells at res {r}")

    kept: dict[str, int] = {}
    bands: list[dict] = []
    while cells and r <= R:
        ll = np.array([h3.cell_to_latlng(c) for c in cells])
        dl, ok = s_land(ll[:, 0], ll[:, 1])
        ds, _ = s_sea(ll[:, 0], ll[:, 1])
        edge = h3.average_hexagon_edge_length(r, unit="m")
        # PLAN.md 5.1: the penultimate band is widened to soften the last step
        thresh = edge * (1.5 if r == R - 1 else 2.0)

        # A cell is admitted only if its centre is a MEASURED sea pixel (ds <= 0).
        # "not land" is not the same test: a nodata pixel is not land either, and would
        # be admitted as sea while carrying no measurement at all. EMODnet's provenance
        # layers do not cover land and its nil value is NaN with no declared nodata on
        # the dataset, so absence is indistinguishable from measurement on sign alone.
        # An unmeasured cell is therefore DROPPED and COUNTED, never quietly kept: a hole
        # in the grid stops a route visibly, where a confident path through nothing does
        # not (D-077).
        measured_sea = ok & (ds <= 0)
        nodata = ok & (ds > 0) & (dl > 0)              # neither land nor measured sea
        if r == R:
            # A coastal block holds BOTH land and sea, so these must be made mutually
            # exclusive or the outcome ledger double-counts it — which is exactly how
            # this was caught: the SUM stopped balancing the moment the masks were
            # allowed to overlap.
            keep = measured_sea
            # ...and NOT the unmeasured ones, which have their own category. Making
            # `drop` the complement of `keep` for exclusivity put every nodata cell in
            # BOTH buckets, and the ledger came out 171 over — exactly the res-9 nodata
            # count. Two fixes to the same line in one day, each caught by the sum.
            drop = ok & ~keep & ~nodata
            split = np.zeros(len(cells), bool)
        else:
            keep = measured_sea & (dl > thresh)        # far enough offshore: stop here
            drop = ok & (ds > thresh) & ~nodata        # wholly inland: discard
            split = ok & ~keep & ~drop & ~nodata

        for i in np.nonzero(keep)[0]:
            kept[cells[i]] = r
        bands.append({"resolution": r, "tested": len(cells), "kept": int(keep.sum()),
                      "dropped_land": int(drop.sum()), "subdivided": int(split.sum()),
                      "off_grid": int((~ok).sum()),
                      "nodata_centre": int(nodata.sum()),
                      # at the terminal resolution every remaining sea cell is kept, so
                      # no threshold is applied; recording one would describe work not done
                      "threshold_m": None if r == R else round(thresh),
                      "edge_m": round(edge)})
        print(f"  res {r:>2}: tested {len(cells):>9,}  kept {int(keep.sum()):>8,}  "
              f"land {int(drop.sum()):>8,}  split {int(split.sum()):>8,}  "
              f"off-grid {int((~ok).sum()):>7,}  nodata {int(nodata.sum()):>6,}  "
              + ("threshold none (terminal: all sea kept)" if r == R
                 else f"threshold {thresh/1000:6.2f} km"))

        if r == R:
            break
        nxt: list[str] = []
        for i in np.nonzero(split)[0]:
            nxt.extend(h3.cell_to_children(cells[i], r + 1))
        cells = nxt
        r += 1

    print(f"\nTOTAL {len(kept):,} cells")
    by_res: dict[int, int] = {}
    for v in kept.values():
        by_res[v] = by_res.get(v, 0) + 1
    for k in sorted(by_res):
        print(f"  res {k:>2}: {by_res[k]:>9,}")

    # depth at each kept cell's centre
    ids = list(kept)
    ll = np.array([h3.cell_to_latlng(c) for c in ids])
    dep, _ = s_depth(ll[:, 0], ll[:, 1])

    out = Path(cfg["out_dir"]); out.mkdir(parents=True, exist_ok=True)
    Path(cfg["summary"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["summary"]).write_text(json.dumps({
        "coastal_sea_resolution": R, "total_cells": len(kept),
        "by_resolution": {str(k): v for k, v in sorted(by_res.items())},
        "bands": bands, "extent": list(b),
        "coast": "EMODnet sign change = Lowest Astronomical Tide (PLAN.md 4)",
        "sea_must_reach_the_sea": "A cell is admitted only if its water connects to the "
                                  "open sea. `elevation < 0` alone admits the Fens, which "
                                  "lie below the datum and are dry land.",
        "severed_deep_water": cfg.get("_severed", []),
        "severed_note": "Water deeper than 10 m that this bathymetry cuts off from the "
                        "sea. NOT reconnected — that would assert a channel the data "
                        "does not contain. These are real losses: Loch Etive is here "
                        "because EMODnet reads +6.8 m at the Connel narrows, averaging a "
                        "200 m channel into land on a 115 m grid.",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"wrote {cfg['summary']}")

    np.savez_compressed(out / f"grid_r{R}.npz", cell=np.array(ids),
                        resolution=np.array([kept[c] for c in ids], "int8"),
                        lat=ll[:, 0], lon=ll[:, 1], depth_m=dep)
    p = out / f"grid_r{R}.npz"
    print(f"wrote {p} ({p.stat().st_size/1e6:.1f} MB)")

    # --- checks (PLAN.md 9) ---
    # NONE OF THESE MAY BE THE SELECTOR RESTATING ITSELF. "No kept cell reads as land"
    # was the first version and it is exactly D-070: kept cells are chosen BY that test,
    # so it returns zero whether the surface is right, wrong or absent. rewt-16 caught it.
    print("\nCHECKS")
    tested = sum(x["tested"] for x in bands)
    as_land = sum(x["dropped_land"] for x in bands)
    nod = sum(x["nodata_centre"] for x in bands)
    split_n = sum(x["subdivided"] for x in bands)
    offg = sum(x["off_grid"] for x in bands)
    print(f"  every tested cell, by outcome — these must sum to the total tested:")
    print(f"    kept          {len(kept):>9,}")
    print(f"    dropped: land {as_land:>9,}")
    print(f"    subdivided    {split_n:>9,}   (re-counted as seven children at r+1)")
    print(f"    off the grid  {offg:>9,}")
    print(f"    unmeasured    {nod:>9,}")
    acc = len(kept) + as_land + split_n + offg + nod
    print(f"    {'SUM':<13} {acc:>9,}  against {tested:,} tested"
          f"{'  — BALANCES' if acc == tested else '  ** DOES NOT BALANCE **'}")
    print(f"  NB 'tested' is not a population: a subdivided cell is counted again as its "
          f"children, so {split_n:,} of the {tested:,} are parents. Percentages against it "
          f"are meaningless; the grid holds {len(kept):,} cells.")
    if as_land == 0 or len(kept) == 0:
        print("  ** the selector excluded nothing in one direction — that is a finding **")
    if nod:
        print(f"  ** {nod:,} cells had no measurement at their centre and were DROPPED. "
              f"Holes are fatal here (conf/sources.yml); go and look before trusting it **")

    # Named rows in BOTH directions, against places chosen from a map, not from the output
    probes = [("Rannoch Moor", 56.620, -4.720, "land"),
              ("Salisbury Plain", 51.200, -1.900, "land"),
              ("Dogger Bank, southern edge", 54.500, 1.500, "sea"),
              ("The Minch", 58.000, -6.000, "sea"),
              ("Irish Sea, off Anglesey", 53.400, -4.800, "sea")]
    print("  named rows, both directions:")
    for name, la, lo, expect in probes:
        hit = None
        for rr in range(cfg["start_resolution"], R + 1):
            c = h3.latlng_to_cell(la, lo, rr)
            if c in kept:
                hit = (c, rr); break
        got = "sea" if hit else "land"
        flag = "ok " if got == expect else "** MISMATCH **"
        extra = f"kept at res {hit[1]} ({hit[0]})" if hit else "not in the grid"
        print(f"    {flag} {name:<28} expected {expect:<4} {extra}")

    deep = np.argsort(np.where(np.isnan(dep), 1e9, dep))[:3]
    print("  deepest kept cells:")
    for i in deep:
        print(f"    {ids[i]}  res {kept[ids[i]]}  {dep[i]:.0f} m  "
              f"at {ll[i,0]:.3f} N {ll[i,1]:.3f} E")
    unmeasured = int(np.isnan(dep).sum())
    print(f"  kept cells with no depth at their centre (must be 0): {unmeasured}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        CONFIG["coastal_sea_resolution"] = int(sys.argv[1])
    main()
