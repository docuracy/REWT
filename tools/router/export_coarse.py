"""Cells and network at a choice of coarser resolutions, for /check's selector.

Stephen asked what "crosses a resolution band" means and whether there are other
resolutions to see. There are: the routing grid is res 7 almost everywhere, res 8-9 where
an estuary was refined, and RES 6 WHERE SIGHT IS LOST — the closed blind hops of PLAN.md 22
are binned coarse, so the seams are the boundary of the water you cannot see across. That
is the thing the legend entry was failing to say.

This writes a matched pair per resolution — cells and the network aggregated the same way —
so the selector changes both together and they always agree. Res 7 and finer is not offered
for the whole extent: it is 415,520 edges and 80 MB. Use the per-area detail toggle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation             # noqa: E402
from landtest import land_crossing_test       # noqa: E402

CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "cells": "docs/router/data/sightline2_r6.geojson",
    "masks": "tools/router/cache/sightline_masks.npz",
    "summary": "docs/router/data/edge_summary.json",
    "out": "docs/router/check",
    "resolutions": [4, 5, 6],
    "coord_dp": 4,
}



def largest_component(feats, a="h3_a", b="h3_b"):
    """Drop links outside the biggest connected set. Stephen: 'deleting a link has left
    part of the sea network isolated'.

    The ROUTING graph is guaranteed one component — grid2 drops what its own adjacency
    cannot reach. The DRAWN layer is a different graph: its chords are land-trimmed
    separately, and trimming one can strand a pocket that the res-7 routing graph still
    reaches round the headland. So the drawn graph needs its own connectivity pass, and
    it must run AFTER the land trim, not before. Yes, this is Stephen's suggested drop of
    everything but the biggest connected set; there is no need for anything cleverer,
    because the routing graph beneath has already answered the hard version.
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    if not feats:
        return feats, 0, 0
    ids = {}
    e = []
    for f in feats:
        p = f["properties"]
        u = ids.setdefault(p[a], len(ids))
        v = ids.setdefault(p[b], len(ids))
        e.append((u, v))
    e = np.array(e)
    m = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(ids),) * 2)
    n, lab = connected_components(m, directed=False)
    main = int(np.argmax(np.bincount(lab)))
    keep = [f for f, (u, _) in zip(feats, e) if lab[u] == main]
    return keep, len(feats) - len(keep), n - 1

def main(cfg: dict = CONFIG) -> None:
    g = np.load(cfg["grid"], allow_pickle=True)
    cell, gres = g["cell"].tolist(), g["resolution"]
    z = np.load(cfg["edges"])
    e, length = z["edge"], z["length_m"]
    stamp = json.loads(Path(cfg["summary"]).read_text()).get("generation") or generation()
    crosses = land_crossing_test(cfg["masks"])
    D = cfg["coord_dp"]

    src = json.loads(Path(cfg["cells"]).read_text())["features"]
    print(f"{len(src):,} published cells, {len(e):,} routing edges")

    for R in cfg["resolutions"]:
        # --- cells: ANY child visible makes the parent visible, as sightline2 folds it
        agg: dict[str, dict] = {}
        for f in src:
            p = f["properties"]
            k = h3.cell_to_parent(p["h3"], R)
            a = agg.setdefault(k, {"vis": False, "gov": 0, "closed": False, "n": 0})
            a["n"] += 1
            a["vis"] |= bool(p.get("visible"))
            a["closed"] |= bool(p.get("closed_hop"))
            if p.get("gov_h_m"):
                a["gov"] = max(a["gov"], int(p["gov_h_m"]))
        cf = []
        for k, a in sorted(agg.items()):
            ring = [[round(x, 5), round(y, 5)] for y, x in h3.cell_to_boundary(k)]
            ring.append(ring[0])
            cf.append({"type": "Feature",
                       "geometry": {"type": "Polygon", "coordinates": [ring]},
                       "properties": {"h3": k, "res": R, "cells_beneath": a["n"],
                                      "visible": a["vis"],
                                      **({"closed_hop": True}
                                         if a["closed"] and not a["vis"] else {}),
                                      "gov_h_m": a["gov"] or None}})
        Path(cfg["out"], f"cells-r{R}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection",
             "properties": {"generation": stamp, "resolution": R, "cells": len(cf),
                            "aggregated_from": "docs/router/data/sightline2_r6.geojson",
                            "visible_rule": "ANY child cell that sees land makes the "
                                            "parent visible, as sightline2 folds pixels "
                                            "into cells. gov_h_m is the MAXIMUM."},
             "features": cf}, separators=(",", ":")))

        # --- network: the same parents, linked where any routing edge joins them
        pres = {k: R for k in agg}
        par: dict[tuple[str, str], dict] = {}
        for m, (i, j) in enumerate(e):
            pa, pb = h3.cell_to_parent(cell[i], R), h3.cell_to_parent(cell[j], R)
            if pa == pb or pa not in pres or pb not in pres:
                continue
            key = (pa, pb) if pa < pb else (pb, pa)
            r = par.setdefault(key, {"n": 0, "len": 0.0, "cross": 0})
            r["n"] += 1
            r["len"] += float(length[m])
            r["cross"] += int(gres[i] != gres[j])
        ef, over = [], 0
        for (pa, pb), r in sorted(par.items()):
            # test the rounded centres, which are what the file actually draws
            la, lo = (round(v, D) for v in h3.cell_to_latlng(pa))
            lb, ob = (round(v, D) for v in h3.cell_to_latlng(pb))
            if crosses((la, lo), (lb, ob)):
                over += 1
                continue
            ef.append({"type": "Feature",
                       "geometry": {"type": "LineString", "coordinates": [
                           [round(lo, D), round(la, D)], [round(ob, D), round(lb, D)]]},
                       "properties": {"h3_a": pa, "h3_b": pb, "routing_edges": r["n"],
                                      "crosses_band": bool(r["cross"]),
                                      "mean_edge_m": int(round(r["len"] / r["n"]))}})
        ef, dropped, frags = largest_component(ef)
        Path(cfg["out"], f"edges-r{R}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection",
             "properties": {"generation": stamp, "resolution": R, "links": len(ef),
                            "links_over_land_not_drawn": over,
                            "links_dropped_isolated": dropped,
                            "crossing_a_band": sum(1 for f in ef
                                                   if f["properties"]["crosses_band"])},
             "features": ef}, separators=(",", ":")))
        mb = (Path(cfg["out"], f"cells-r{R}.geojson").stat().st_size
              + Path(cfg["out"], f"edges-r{R}.geojson").stat().st_size) / 1e6
        print(f"  res {R}: {len(cf):>6,} cells, {len(ef):>6,} links "
              f"({over:,} over land, {dropped:,} isolated)   {mb:.1f} MB")


if __name__ == "__main__":
    main()
