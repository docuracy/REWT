#!/usr/bin/env python3
"""Fetch the EMODnet windows the sightline extent needs, into a WORKING cache.

    python3 tools/router/fetch_extent.py [--dry-run]

Run from the repository root; paths are relative (AGENTS.md).

WHY NOT data/raw. That directory is the implementer's, is checksummed, and its manifest
digest is over the sorted name:sha256 of every window — adding files to it is a
deliberate re-pin and rewt-e8's to make. This writes to tools/router/cache/windows/,
which is gitignored, and **skips any window data/raw already holds**, so the
checksummed copies are always the ones read and this cache only ever supplies the
extras. When rewt-e8's fetch lands, the overlap becomes redundant and can be deleted.

It is not a new source: `emodnet_bathymetry` is registered, CC BY 4.0, redistribution
permitted, and this is the same coverage at the same resolution.

THE EXTENT IS DERIVED, not chosen — everything within sight of land plus the 60 km
blind-sailing buffer (PLAN.md 8, tools/router/sightline2.py):

    W  -13.24  Kerry, 1,015 m, reaches 121 km + 60. Derived.
    N   62.12  Shetland's Ronas Hill, 450 m, reaches 80 km + 60. Derived. FAROE IS OUT:
               its buffer reaches another buffer, not water in sight, and two blind
               zones touching is not a route.
    S   44.50  DECLARED, not derived. The Gironde.
    E   11.50  DECLARED. Far enough east to hold Skagen, the northern tip of Denmark,
               which Stephen names as about a week's sailing from London and which is
               therefore a CALIBRATION POINT: the bound cannot be measured against a
               voyage whose destination is outside the data. The week's-sailing rule
               then trims back to what it admits, so the box is generous on purpose.

THE SOUTHERN AND EASTERN EDGES CANNOT BE DERIVED, and pretending otherwise is the
mistake Faroe was. The continental shore is continuous, so a sight-plus-buffer surface
keeps connecting coastwise for as long as land is in the extent — it would run to the
Baltic and round Iberia. The criterion Stephen chose (option C): include coasts where
coastwise sailing is how the voyage was made, and exclude those reached by an open
crossing this surface cannot represent. Biscay is 281 km blind, so northern Spain would
be land the router could only reach by going round the whole French coast — a
confidently wrong answer rather than an absent one.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from extent import EXTENT          # one declaration, asked rather than repeated
RAW = Path("data/raw/emodnet_bathymetry")
OUT = Path("tools/router/cache/windows")
BASE = "https://ows.emodnet-bathymetry.eu/wcs?"


def name(lat: float, lon: float) -> str:
    la = f"p{lat:05.2f}" if lat >= 0 else f"m{abs(lat):05.2f}"
    lo = f"p{lon:06.2f}" if lon >= 0 else f"m{abs(lon):06.2f}"
    return f"emodnet_{la}_{lo}.tif"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pause", type=float, default=0.4, help="seconds between requests")
    a = ap.parse_args()

    w, s, e, n = EXTENT
    lons = list(range(int(w) - 1, int(e) + 1))
    lat0 = int(s) + 0.5
    lats = [lat0 + i for i in range(int((n - lat0) // 1) + 1)]
    want = [(la, lo) for la in lats for lo in lons]
    # SKIP BY COVERAGE, NOT BY NAME. data/raw's top row is HALF HEIGHT — p60.50_* covers
    # 60.5 to 61.0, not 60.5 to 61.5, because the implementer's area of interest stopped
    # at 61.0. Skipping on the filename left 61.0-61.5 covered by nothing, and a VRT
    # fills an uncovered gap with ZERO, which reads as land at the datum. Same trap as a
    # coverage gap from the service, arriving from the mosaic instead.
    import rasterio
    have_raw = set()
    partial = []
    for q in sorted(RAW.glob("*.tif")):
        with rasterio.open(q) as r:
            if r.bounds.top - r.bounds.bottom >= 0.999:
                have_raw.add(q.name)
            else:
                partial.append((q.name, r.bounds.bottom, r.bounds.top))
    if partial:
        print(f"  {len(partial)} windows in data/raw are PARTIAL and do not cover their "
              f"full degree, e.g. {partial[0][0]} covers "
              f"{partial[0][1]:.2f}-{partial[0][2]:.2f}; refetching those")
    OUT.mkdir(parents=True, exist_ok=True)
    have_out = {p.name for p in OUT.glob("*.tif")}

    todo = [(la, lo) for la, lo in want
            if name(la, lo) not in have_raw and name(la, lo) not in have_out]
    print(f"extent {EXTENT}")
    print(f"  {len(want)} windows wanted, {len(have_raw)} already in data/raw "
          f"(authoritative), {len(have_out)} already here, {len(todo)} to fetch")
    if a.dry_run or not todo:
        return 0

    ok = fail = 0
    for i, (la, lo) in enumerate(todo, 1):
        q = {"service": "WCS", "version": "2.0.1", "request": "GetCoverage",
             "coverageId": "emodnet__mean", "format": "image/tiff"}
        url = (BASE + urllib.parse.urlencode(q)
               + f"&subset=Lat({la},{la + 1})&subset=Long({lo},{lo + 1})")
        p = OUT / name(la, lo)
        try:
            urllib.request.urlretrieve(url, p)
            if p.open("rb").read(2) not in (b"II", b"MM"):
                p.unlink(missing_ok=True)
                fail += 1
            else:
                ok += 1
        except Exception as ex:
            p.unlink(missing_ok=True)
            fail += 1
            print(f"    {name(la, lo)} failed: {type(ex).__name__}")
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}  ok {ok}  failed {fail}", flush=True)
        time.sleep(a.pause)
    print(f"done: {ok} fetched, {fail} failed, into {OUT}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
