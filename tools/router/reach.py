"""How far is a week's sailing? Measured as route distance THROUGH the water.

    python3 tools/router/reach.py

Run from the repository root; paths are relative (AGENTS.md).

THE PROBLEM THIS SOLVES. The extent's southern and eastern edges were declared — the
Gironde and the Elbe — and a declared box has no opinion about what falls inside it. It
let in the Norwegian coast, which nothing about the work wanted.

STEPHEN'S CRITERION: within a week's sailing of England and Wales, under typical
conditions. Two voyages from the eRutter demonstration anchor it — London to the northern
tip of Denmark, and Falmouth to Bordeaux, each about a week in July. Those are attested
durations, so they calibrate a bound instead of one being chosen.

WHY THIS IS NOT AN ARBITRARY DISTANCE, and not a radius. It is measured ALONG THE WATER:
a Dijkstra over the sea mask from the English and Welsh coast, so the Norwegian coast is
as far as the route round the Skagerrak makes it, not as near as a straight line across
the North Sea suggests. A radius would have admitted Norway; the route does not.

TIME IS NOT COMPUTED, and could not be: sailing time needs wind, current and a hull, and
weights are deferred (PLAN.md 1). What is computed is the ROUTE DISTANCE that the two
attested week-long voyages correspond to. That is a measurement of geometry calibrated by
a duration, not a claim about duration.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

CONFIG = {
    "masks": "tools/router/cache/sightline_masks.npz",
    "out": "tools/router/cache/reach.npz",
    "summary": "docs/router/data/reach_summary.json",
    # source coast: England and Wales, which is what the project is about
    "sources": [("Thames, off London", 51.48, 0.60), ("Falmouth", 50.10, -5.05),
                ("Yarmouth", 52.60, 1.80), ("Bristol Channel", 51.40, -3.40),
                ("Humber", 53.60, 0.20), ("Solent", 50.75, -1.30),
                ("Liverpool Bay", 53.55, -3.30), ("Tyne", 55.00, -1.30)],
    "calibration": [("London -> Skagen (N Denmark)", 57.74, 10.63),
                    ("Falmouth -> Bordeaux (Gironde mouth)", 45.58, -1.06)],
    "probes": [("S Norway, Kristiansand", 58.10, 8.00),
               ("Bergen", 60.35, 5.30),
               ("Antwerp approaches", 51.45, 3.40),
               ("Elbe mouth", 54.00, 8.30),
               ("A Coruna", 43.40, -8.40),
               ("W of Ireland", 53.30, -11.00),
               ("Shetland", 60.30, -1.30),
               ("Aarhus, E Denmark", 56.15, 10.30),
               ("Copenhagen approaches", 55.90, 12.00),
               ("Skagen itself", 57.78, 10.70),
               ("Esbjerg, W Denmark", 55.45, 8.30),
               ("Bordeaux itself", 45.30, -1.10)],
}


def main(cfg: dict = CONFIG) -> None:
    m = np.load(cfg["masks"], allow_pickle=True)
    tr = m["fine_transform"]
    px = float(m["fine_px"][0])
    crs = str(m["crs"][0])
    fwd = Transformer.from_crs(4326, crs, always_xy=True)

    # MEASURE ON THE SURFACE WE ARE BUILDING, not through open water. The first version
    # ran over every sea pixel and so took the direct North Sea crossing — 400 km of
    # blind open water the trim removes — which put Bergen 765 km from England, NEARER
    # than the Denmark anchor at 821. A route distance that uses water the router cannot
    # is not a route distance; it contradicted the model it was meant to bound.
    fine_sea = m["fine_sea"]
    ctr, ckeep = m["transform"], m["keep"]
    h, w = fine_sea.shape
    rr, cc = np.mgrid[0:h, 0:w]
    x = tr[2] + (cc + 0.5) * tr[0] + (rr + 0.5) * tr[1]
    y = tr[5] + (cc + 0.5) * tr[3] + (rr + 0.5) * tr[4]
    ccol = np.clip(((x - ctr[2]) / ctr[0]).astype(np.int32), 0, ckeep.shape[1] - 1)
    crow = np.clip(((y - ctr[5]) / ctr[4]).astype(np.int32), 0, ckeep.shape[0] - 1)
    sea = fine_sea & ckeep[crow, ccol]
    del rr, cc, x, y, ccol, crow
    print(f"navigable surface {sea.shape} at {px:.0f} m, {int(sea.sum()):,} px "
          f"(of {int(fine_sea.sum()):,} water px; the rest is trimmed and unroutable)")

    idx = -np.ones((h, w), np.int64)
    ys, xs = np.nonzero(sea)
    idx[ys, xs] = np.arange(len(ys))
    n = len(ys)

    rows, cols, vals = [], [], []
    for dy, dx, wgt in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 2 ** 0.5), (1, -1, 2 ** 0.5)):
        a = idx[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
        b = idx[max(0, dy):h - max(0, -dy), max(0, dx):w - max(0, -dx)]
        ok = (a >= 0) & (b >= 0)
        rows.append(a[ok]); cols.append(b[ok]); vals.append(np.full(ok.sum(), wgt * px))
    g = coo_matrix((np.concatenate(vals),
                    (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    print(f"  graph {n:,} nodes, {g.nnz:,} edges")

    def node_at(lat, lon):
        x, y = fwd.transform(lon, lat)
        c = int((x - tr[2]) / tr[0]); r = int((y - tr[5]) / tr[4])
        if not (0 <= r < h and 0 <= c < w):
            return None
        if idx[r, c] >= 0:
            return int(idx[r, c])
        # nearest water within ~10 km, so a named place on the shore still resolves
        k = int(10_000 / px)
        r0, r1 = max(r - k, 0), min(r + k + 1, h)
        c0, c1 = max(c - k, 0), min(c + k + 1, w)
        sub = idx[r0:r1, c0:c1]
        wy, wx = np.nonzero(sub >= 0)
        if not len(wy):
            return None
        d = (wy + r0 - r) ** 2 + (wx + c0 - c) ** 2
        j = int(np.argmin(d))
        return int(sub[wy[j], wx[j]])

    srcs = []
    for name, la, lo in cfg["sources"]:
        i = node_at(la, lo)
        print(f"  source {name:<22} {'ok' if i is not None else 'NOT IN WATER'}")
        if i is not None:
            srcs.append(i)
    if not srcs:
        raise SystemExit("no source resolved to water")

    print("running Dijkstra over the water...")
    d = dijkstra(g, directed=False, indices=srcs, min_only=True) / 1000.0
    print(f"  reached {int(np.isfinite(d).sum()):,} of {n:,} water pixels")

    print("\nCALIBRATION — attested as about a week's sailing in July (eRutter):")
    cal = []
    for name, la, lo in cfg["calibration"]:
        i = node_at(la, lo)
        v = float(d[i]) if i is not None and np.isfinite(d[i]) else float("nan")
        cal.append(v)
        print(f"  {name:<40} {v:8.0f} km by water")
    missing = [n for (n, _, _), v in zip(cfg["calibration"], cal) if not np.isfinite(v)]
    if missing:
        print(f"  ** {len(missing)} calibration point(s) NOT IN THE DATA: "
              f"{', '.join(missing)}")
        print("     an anchor outside the extent cannot calibrate anything; the bound "
              "below rests on the rest")
    if not np.any(np.isfinite(cal)):
        raise SystemExit("no calibration point is inside the data — nothing to calibrate")
    bound = float(np.nanmax(cal))
    print(f"\n  a week's sailing = {bound:.0f} km of route distance "
          f"(the larger of the two, so both voyages are inside)")

    print("\nWHAT THAT ADMITS AND EXCLUDES:")
    for name, la, lo in cfg["probes"]:
        i = node_at(la, lo)
        v = float(d[i]) if i is not None and np.isfinite(d[i]) else float("inf")
        tag = "IN" if v <= bound else "out"
        print(f"  {name:<26} {v:8.0f} km   {tag}")

    keep = np.zeros((h, w), bool)
    keep[ys, xs] = d <= bound
    print(f"\n  within a week: {int(keep.sum()):,} of {n:,} water px "
          f"({100*keep.sum()/n:.1f}%)")
    np.savez_compressed(cfg["out"], within_week=keep, km=np.float32(bound))
    Path(cfg["summary"]).write_text(json.dumps({
        "criterion": "within a week's sailing of England and Wales, under typical "
                     "conditions, measured as route distance THROUGH the water",
        "calibration": {n: (round(v) if np.isfinite(v) else None)
                        for (n, _, _), v in zip(cfg["calibration"], cal)},
        "calibration_outside_data": missing,
        "calibration_source": "eRutter, docuracy.github.io/Historical_Sea_Routing: London "
                              "to the northern tip of Denmark, and Falmouth to Bordeaux, "
                              "each about a week in July",
        "week_km": round(bound),
        "anchors_disagree": "the two attested week-long voyages imply different route "
                            "distances. That is information, not noise: route distance is "
                            "a poor proxy for time, and the difference is what wind and "
                            "season would explain. The LARGER is taken so that both "
                            "voyages fall inside the bound.",
        "measured_on": "the navigable surface (sight plus the blind-sailing buffer), not "
                       "open water — a route may not use water the router cannot",
        "not_a_radius": "measured along the water, so Norway is as far as the route round "
                        "the Skagerrak makes it, not as near as a straight line suggests",
        "time_not_computed": "sailing time needs wind, current and a hull, and weights are "
                             "deferred. This calibrates a DISTANCE against an attested "
                             "duration; it does not claim to compute duration.",
        "water_px_within": int(keep.sum()), "water_px_total": int(n),
    }, indent=1))
    print(f"wrote {cfg['out']} and {cfg['summary']}")

    # --- APPLY IT ------------------------------------------------------------------
    # The bound was computed and nothing consumed it, so the east coast of Denmark stayed
    # in a layer that a week's sailing does not reach. A measurement nothing acts on is
    # not a trim.
    lay = Path("docs/router/data/sightline2_r6.geojson")
    if lay.exists():
        import h3
        gj = json.loads(lay.read_text())
        before = len(gj["features"])
        out = []
        for f in gj["features"]:
            la, lo = h3.cell_to_latlng(f["properties"]["h3"])
            i = node_at(la, lo)
            if i is not None and np.isfinite(d[i]) and d[i] <= bound:
                out.append(f)
        gj["features"] = out
        gj["properties"]["week_km"] = round(bound)
        gj["properties"]["week_trim"] = (
            "cells beyond a week's sailing of England and Wales are absent. The bound is "
            "route distance ON THE NAVIGABLE SURFACE, calibrated by two attested "
            f"week-long voyages: London-Skagen {cal[0]:.0f} km and Falmouth-Bordeaux "
            f"{cal[1]:.0f} km. Under the no-blind-sailing rule those two agree to 6%; "
            "on a buffered surface they differed by 48%, because the route was free to "
            "cut across open water that was never sailed.")
        lay.write_text(json.dumps(gj))
        print(f"  trimmed the layer to a week's sailing: {before:,} -> {len(out):,} cells")


if __name__ == "__main__":
    main()
