"""If the sea were drained, which of the foreshore mini-networks would empty last?

STEPHEN'S QUESTION, about the OS links seaward of high water that section 54 put on /check.
They form disconnected MINI-NETWORKS — sets of links sharing nodes — and the question is
which of them holds water longest as the sea goes down.

TWO THINGS DECIDE IT, and they are different.

  **The bed.** A network is dry once the sea falls below its lowest bed. So the network with
  the LOWEST BED empties last, all else equal — that is the plain reading of the question.

  **The sill.** Water only leaves if it has a downhill path out. A priority flood seeded at
  the open boundary gives, for every cell, the lowest level at which water there can still
  escape — its spill level. Where that sill stands ABOVE the bed, the difference is water
  that never drains at all: the network becomes a lake and the answer to "when does it
  empty" is never.

So each mini-network carries `min_bed_m`, `sill_m`, `trapped_m = sill - bed`, and
`empties_at_m` — the sea level at which it finally goes dry, or null where it does not.
Ranked, `rank` 1 is the last to empty.

WHAT IT IS NOT. The bed comes from EMODnet at 930 m, which is coarse for a creek: a channel
narrower than a pixel takes its neighbour's depth. The ORDER is more trustworthy than any
single figure, and a network of one short link should be read with that in mind.
"""
from __future__ import annotations

import heapq
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402

CONFIG = {
    "masks": "tools/router/cache/sightline_masks.npz",
    "rivers": "data/raw/os_open_rivers/extracted/Data/oprvrs_gb.gpkg",
    "links": "docs/router/check/foreshore_links.geojson",
    "out": "docs/router/check/foreshore_networks.geojson",
    "out_links": "docs/router/check/foreshore_network_links.geojson",
    "summary": "docs/router/check/foreshore_networks_summary.json",
    "coord_dp": 6,
}


def main(cfg: dict = CONFIG) -> None:
    m = np.load(cfg["masks"], allow_pickle=True)
    z = m["elev"].astype("float64")
    # THE BED IS READ AT 232 m, NOT 930 m. The first run required the 930 m sea mask and
    # got a reading for 9 of 2,118 networks: a foreshore link sits on pixels EMODnet calls
    # LAND at 930 m, which is the same coarseness that put 157 stranded termini inside
    # EMODnet land. The fine surface covers the whole extent and is four times finer, and
    # the bed is sampled from it with no mask at all — an intertidal channel reads a bed
    # near zero, which is the truth about it.
    fine = np.load("tools/router/cache/seabed_fine.npz")["z"].astype("float32")
    ftr = m["fine_transform"]
    fhh, fww = fine.shape
    sea, tr, crs = m["sea"], m["transform"], str(m["crs"][0])
    px = float(m["px"][0])
    h, w = z.shape

    # --- SPILL LEVEL EVERYWHERE: priority flood from the open boundary ------------
    # `filled[p]` is the lowest level at which water at p can still reach the open sea.
    filled = np.where(sea, z, np.inf)
    seen = ~sea
    heap: list = []
    edge = np.zeros_like(sea)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        edge |= sea & ~np.roll(sea, (dy, dx), (0, 1))
    for y, x in zip(*np.nonzero(sea & edge)):
        heapq.heappush(heap, (float(z[y, x]), int(y), int(x)))
        seen[y, x] = True
    nb = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))
    while heap:
        e, y, x = heapq.heappop(heap)
        filled[y, x] = e
        for dy, dx in nb:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx]:
                seen[ny, nx] = True
                heapq.heappush(heap, (max(e, float(z[ny, nx])), ny, nx))
    print(f"  spill levels computed over {int(sea.sum()):,} sea px at {px:.0f} m")

    # --- MINI-NETWORKS: connected components of the seaward links -----------------
    # RE-DERIVE THE SELECTION, do not match it back. The export chose links whose
    # midpoint lies seaward of high water using a rasterised land test; repeating that
    # test is deterministic and takes seconds, where matching 193,040 geometries back by
    # WKB is slow and silently wrong if either side is reprojected.
    import rasterio.features
    import rasterio.transform
    import shapely
    from landtest import os_land_area
    lk = gpd.read_file(cfg["rivers"], layer="watercourse_link")
    land_poly = os_land_area("EPSG:27700")
    lb = shapely.total_bounds(land_poly)
    PX = 100.0
    LW = int((lb[2] - lb[0]) / PX) + 2
    LH = int((lb[3] - lb[1]) / PX) + 2
    ltr = rasterio.transform.from_origin(lb[0], lb[3], PX, PX)
    LAND = rasterio.features.rasterize(((q, 1) for q in land_poly), out_shape=(LH, LW),
                                       transform=ltr, fill=0, dtype="uint8").astype(bool)
    mid = shapely.centroid(lk.geometry.values)
    mx = np.array([q.x for q in mid]); my = np.array([q.y for q in mid])
    cc = ((mx - lb[0]) / PX).astype(int); rr = ((lb[3] - my) / PX).astype(int)
    ok = (rr >= 0) & (rr < LH) & (cc >= 0) & (cc < LW)
    landward = np.zeros(len(lk), bool)
    landward[ok] = LAND[rr[ok], cc[ok]]
    sel = lk[~landward].to_crs(4326)
    print(f"  {len(sel):,} links seaward of high water")

    ids: dict = {}

    def ix(k):
        return ids.setdefault(k, len(ids))

    rows = [(ix(a), ix(b)) for a, b in zip(sel.start_node.values, sel.end_node.values)]
    arr = np.array(rows)
    g = coo_matrix((np.ones(len(arr)), (arr[:, 0], arr[:, 1])), shape=(len(ids),) * 2)
    ncomp, lab = connected_components(g + g.T, directed=False)
    print(f"  {ncomp:,} mini-networks")

    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    comp_of = {}
    for (a, b), i in zip(zip(sel.start_node.values, sel.end_node.values), range(len(sel))):
        comp_of[i] = int(lab[ids[a]])

    stats: dict = {}
    for i, geom in enumerate(sel.geometry.values):
        c = comp_of[i]
        # THE MARKER GOES ON THE LOWEST BED, NOT ON THE CENTROID. A centroid of a
        # sinuous creek system is not on the creek: for the 75 networks of 20 links or
        # more it landed a median 360 m off and up to 2.15 km, over land, and those are
        # drawn largest so they are the ones the eye goes to. The lowest bed is also the
        # meaningful place — it is where the water actually drains last.
        s = stats.setdefault(c, {"bed": [], "sill": [], "links": 0, "km": 0.0,
                                 "low": None, "low_at": None})
        s["links"] += 1
        for lo, la in geom.coords:
            X, Y = fwd.transform(lo, la)
            fc = int((X - ftr[2]) / ftr[0]); fr = int((Y - ftr[5]) / ftr[4])
            if 0 <= fr < fhh and 0 <= fc < fww and np.isfinite(fine[fr, fc]):
                v = float(fine[fr, fc])
                s["bed"].append(v)
                if s["low"] is None or v < s["low"]:
                    s["low"], s["low_at"] = v, (lo, la)
            col = int((X - tr[2]) / tr[0]); row = int((Y - tr[5]) / tr[4])
            if 0 <= row < h and 0 <= col < w and np.isfinite(filled[row, col]):
                s["sill"].append(float(filled[row, col]))


    feats = []
    for c, s in stats.items():
        if not s["bed"]:
            continue
        bed = min(s["bed"])
        sill = min(s["sill"]) if s["sill"] else bed
        trapped = max(0.0, sill - bed)
        feats.append({"comp": c, "links": s["links"],
                      "min_bed_m": round(bed, 1), "sill_m": round(sill, 1),
                      "trapped_m": round(trapped, 1),
                      "empties_at_m": None if trapped > 0 else round(bed, 1),
                      "lon": round(float(s["low_at"][0]), 5),
                      "lat": round(float(s["low_at"][1]), 5)})
    feats.sort(key=lambda f: (f["min_bed_m"]))
    for r, f in enumerate(feats, 1):
        f["rank"] = r
    print(f"  {len(feats):,} mini-networks with a bed reading")
    never = sum(1 for f in feats if f["empties_at_m"] is None)
    print(f"    {never:,} never empty — a sill above the bed traps water in them")
    print("\n  last to empty (lowest bed):")
    for f in feats[:6]:
        print(f"    rank {f['rank']:>3}  bed {f['min_bed_m']:>7.1f} m  sill "
              f"{f['sill_m']:>7.1f} m  trapped {f['trapped_m']:>5.1f} m  "
              f"{f['links']:>3} links at {f['lat']:.3f} N {f['lon']:.3f} E")

    by_comp = {f["comp"]: f for f in feats}
    lf = []
    for i, geom in enumerate(sel.geometry.values):
        f_ = by_comp.get(comp_of[i])
        if f_ is None:
            continue
        lf.append({"type": "Feature",
                   "geometry": {"type": "LineString",
                                "coordinates": [[round(x, 6), round(y, 6)]
                                                for x, y in geom.coords]},
                   "properties": {"comp": f_["comp"], "rank": f_["rank"],
                                  "min_bed_m": f_["min_bed_m"],
                                  "empties_at_m": f_["empties_at_m"]}})
    Path(cfg["out_links"]).write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": generation(),
                        "what": "The seaward links themselves, each carrying its "
                                "mini-network's drain figures, so the ordering can be read "
                                "off the geometry rather than off a marker beside it.",
                        "features_": len(lf)},
         "features": lf}, separators=(",", ":")))
    print(f"  wrote {cfg['out_links']} ({len(lf):,} links carrying their network's rank)")

    gj = [{"type": "Feature",
           "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
           "properties": {k: v for k, v in f.items() if k not in ("lon", "lat")}}
          for f in feats]
    props = {
        "generation": generation(),
        "what": "One point per MINI-NETWORK of OS links seaward of high water, carrying "
                "what decides when it would empty if the sea were drained.",
        "min_bed_m": "lowest seabed elevation under the network; a network is dry once the "
                     "sea falls below it, so the LOWEST bed empties last",
        "sill_m": "the lowest level at which water there can still escape to the open sea, "
                  "from a priority flood seeded at the open boundary",
        "trapped_m": "sill minus bed; where this is positive that much water never drains "
                     "and the network becomes a lake",
        "empties_at_m": "the sea level at which it finally goes dry, or null where it never "
                        "does",
        "rank": "1 is the last to empty",
        "caveat": "The bed is EMODnet at 930 m, coarse for a creek: a channel narrower than "
                  "a pixel takes its neighbour's depth. The ORDER is more trustworthy than "
                  "any single figure.",
        "networks": len(feats), "never_empty": never,
        "attribution": "Contains OS data (c) Crown copyright and database right, OGL v3. "
                       "Contains EMODnet Bathymetry data, CC BY 4.0.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(cfg["out"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": gj},
        separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps(props, indent=1))
    print(f"wrote {cfg['out']}")


if __name__ == "__main__":
    main()
