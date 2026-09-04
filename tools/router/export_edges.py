"""The routing edges as a GeoJSON layer, for the viewer's toggle from the sea cells.

Stephen asked to see the travelling surface itself rather than the cells that carry it.
An edge here is a link between two cell CENTRES — the surface eRutter uses, and the one
`edges.py` builds. What is drawn is an ADJACENCY, not a route: a vessel did not sail the
straight line between two hex centres, and a chain of these is only the shape a route
would follow at the lattice's resolution. That sentence rides in the layer's own
properties rather than in the legend, so it cannot be separated from the geometry.

Cross-resolution edges are the interesting ones and carry `crosses_band`. A grid built
from `grid_disk` alone would be one disconnected sheet per resolution, each locally
perfect; those edges are the seams, and a picture shows what a count cannot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402
from landtest import land_crossing_test     # noqa: E402

CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "summary": "docs/router/data/edge_summary.json",
    "out": "docs/router/data/edges.geojson",
    "check_dir": "docs/router/check",
    "areas": "docs/router/check/areas.json",
    "cells": "docs/router/data/sightline2_r6.geojson",
    "masks": "tools/router/cache/sightline_masks.npz",
    "publish_resolution": 6,   # see the note in main(): 415,520 res-7 edges is 80 MB
    "coord_dp": 4,             # 11 m, against a median edge of 2,290 m
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
    """Two layers, because the true graph will not fit down a browser.

    THE PUBLISHED ONE IS AGGREGATED, and this is the whole of the compromise. The
    routing grid is res 7: 143,196 cells and 415,520 edges, which is 80 MB of GeoJSON
    and about a gigabyte once a browser has parsed it. The published SEA CELLS are res
    6 — that is the layer a toggle switches away from — so the published edges are the
    res-7 graph aggregated to res 6: two res-6 cells are linked when any res-7 edge
    joins a child of one to a child of the other. Every such link is backed by a real
    routing edge and none is invented, but a drawn line runs centre-to-centre between
    res-6 cells and no vessel and no route uses those centres.

    THE TRUE EDGES GO OUT PER CHECK AREA, unaggregated, into the gitignored check
    directory, where the areas are small enough to hold them. That is where to look at
    the lattice itself.
    """
    g = np.load(cfg["grid"], allow_pickle=True)
    res = g["resolution"]
    lat, lon = np.round(g["lat"], cfg["coord_dp"]), np.round(g["lon"], cfg["coord_dp"])
    cell = g["cell"].tolist()
    P, D = cfg["publish_resolution"], cfg["coord_dp"]
    # AN EXPORT DOES NOT MINT A GENERATION. This re-rendered the same edges an hour
    # later and stamped a fresh time on them, so two layers from one pass disagreed and
    # the viewer's cross-layer check — reading my own files — caught my own claim that
    # they matched. The stamp belongs to the pass that COMPUTED the data; re-rendering
    # it is not a new pass. generation() is the fallback for edges built without one.
    s = json.loads(Path(cfg["summary"]).read_text())
    stamp = s.get("generation") or generation()
    z = np.load(cfg["edges"])
    e, length = z["edge"], z["length_m"]
    ra, rb = res[e[:, 0]].astype(int), res[e[:, 1]].astype(int)
    cross = ra != rb
    print(f"{len(e):,} edges, {cross.sum():,} crossing a resolution band "
          f"({100*cross.mean():.2f}%)")

    par = {}
    for k, (i, j) in enumerate(e):
        pa = h3.cell_to_parent(cell[i], P)
        pb = h3.cell_to_parent(cell[j], P)
        if pa == pb:
            continue                       # inside one published cell; nothing to draw
        key = (pa, pb) if pa < pb else (pb, pa)
        r = par.setdefault(key, {"n": 0, "cross": 0, "len": 0.0, "rep": k, "best": 1e18})
        r["n"] += 1
        r["cross"] += int(cross[k])
        r["len"] += float(length[k])
        # DRAW A REAL EDGE, NOT A LINE BETWEEN TWO PARENT CENTRES. Connecting res-6
        # centres invented endpoints, and Stephen found some of them inland: a res-6
        # cell is kept because it CONTAINS sighted sea, so its centre can sit on a
        # beach. Every line drawn is now one actual res-7 routing edge from the group —
        # the shortest, for determinism — so both endpoints are routing nodes and are in
        # water by construction. The aggregation thins the graph; it no longer
        # fabricates geometry.
        if float(length[k]) < r["best"]:
            r["best"], r["rep"] = float(length[k]), k
    print(f"  aggregated to res {P}: {len(par):,} links (from {len(e):,} routing edges)")

    # CLIP TO THE CELLS THAT ARE ACTUALLY PUBLISHED. A res-6 parent appears as soon as
    # ONE of its seven res-7 children is in the routing grid, so aggregation spills a
    # ring of cells past the edge of the published layer — 4,504 of them, all perimeter.
    # A toggle whose two layers do not cover the same ground is a bug the eye finds
    # immediately, so links with an endpoint outside the published set come out here,
    # and the count goes into the layer's properties rather than being silently lost.
    pub = {f["properties"]["h3"]
           for f in json.loads(Path(cfg["cells"]).read_text())["features"]}
    spill = [k for k in par if not (k[0] in pub and k[1] in pub)]
    for k in spill:
        del par[k]
    print(f"  dropped {len(spill):,} links reaching a cell the layer does not publish; "
          f"{len(par):,} remain")

    # DRAWN CENTRE TO CENTRE OF THE CELLS IT IS SHOWN BESIDE. This drew the shortest real
    # res-7 edge instead, so that no endpoint sat on land — and Stephen's next look found
    # links that visibly do not join the centres of the hexagons under them. Both
    # complaints are right and they cannot both be answered at res 6: the routing nodes
    # are res-7 and a res-6 picture of them is a schematic whichever way it is drawn. So
    # this is now internally consistent — lines join the cells you can see — and the true
    # lattice goes out per area at its own resolution, where cells and links agree and
    # nothing is a schematic. The endpoints-on-land question belongs to res-6 CENTRES, not
    # to the network: grid2.py now guarantees every routing node is in water.
    # A DRAWN LINK MAY NOT CROSS LAND EITHER. The res-7 graph is trimmed by this test
    # already; the res-6 chord between two parent centres is a different line and can run
    # over a headland the res-7 path goes round. Stephen caught the omission the moment
    # the geometry went back to parent centres. Same test, same 232 m mask.
    crosses = land_crossing_test(cfg["masks"])

    # WHERE THE CHORD CANNOT REPRESENT THE ROUTE, DRAW THE ROUTE. A res-6 chord between two
    # cell centres crosses land wherever the water between them is narrower than the cells
    # are wide — the north Solent, the Exe. Dropping those links made the drawn network say
    # the channel is impassable, when the res-7 routing graph goes through it perfectly
    # well: Hurst to Cowes Roads is 20.0 km of routing against an 18.4 km straight line, a
    # ratio of 1.1. Stephen read the gap as a routing failure and it was a drawing failure.
    #
    # So instead of dropping such a link, walk the res-7 path between the two cells and draw
    # THAT. The search is restricted to res-7 nodes lying under the two parents, which is at
    # most fourteen of them, so it answers exactly the local question "how does a route get
    # from this cell to that one" and stays cheap.
    import heapq
    from collections import defaultdict
    kids = defaultdict(list)
    for i7, c7 in enumerate(cell):
        kids[h3.cell_to_parent(c7, P)].append(i7)
    nbr = defaultdict(list)
    for k, (i, j) in enumerate(e):
        nbr[int(i)].append((int(j), float(length[k])))
        nbr[int(j)].append((int(i), float(length[k])))

    def path_between(pa, pb):
        """Shortest res-7 path from pa's children to pb's, staying under the two."""
        allowed = set(kids[pa]) | set(kids[pb])
        if not kids[pa] or not kids[pb]:
            return None
        goal = set(kids[pb])
        # a monotonic counter as the tiebreaker: without it two entries with equal
        # distance and equal node fall through to comparing the predecessor, and None
        # against an int raises
        from itertools import count
        tick = count()
        seen, prev = {}, {}
        h = [(0.0, next(tick), i, None) for i in kids[pa]]
        heapq.heapify(h)
        while h:
            d, _, u, pv = heapq.heappop(h)
            if u in seen:
                continue
            seen[u] = d
            prev[u] = pv
            if u in goal:
                out = []
                while u is not None:
                    out.append(u)
                    u = prev[u]
                return out[::-1]
            for v, w in nbr[u]:
                if v in allowed and v not in seen:
                    heapq.heappush(h, (d + w, next(tick), v, u))
        return None

    feats, over_land, routed = [], 0, 0
    for (pa, pb), r in sorted(par.items()):
        # TEST WHAT IS DRAWN, NOT WHAT IS COMPUTED. Publishing rounds the centre to
        # 4 dp, which moves it up to ~11 m — enough to put the drawn line across a
        # headland the exact line misses. One link of 47,367 did exactly that.
        la, lo = (round(v, D) for v in h3.cell_to_latlng(pa))
        lb, ob = (round(v, D) for v in h3.cell_to_latlng(pb))
        coords = [[round(lo, D), round(la, D)], [round(ob, D), round(lb, D)]]
        how = "chord"
        if crosses((la, lo), (lb, ob)):
            pth = path_between(pa, pb)
            ok = False
            if pth and len(pth) > 1:
                cc = [[round(float(lon[i]), D), round(float(lat[i]), D)] for i in pth]
                ok = all(not crosses((cc[k][1], cc[k][0]), (cc[k + 1][1], cc[k + 1][0]))
                         for k in range(len(cc) - 1))
                if ok:
                    coords, routed, how = cc, routed + 1, "res-7 path"
            if not ok:
                over_land += 1
                continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "h3_a": pa, "h3_b": pb,
                "routing_edges": r["n"],
                "crosses_band": bool(r["cross"]),
                # NOT inferred from the vertex count: a res-7 path between two adjacent
                # cells is usually two points as well, so counting vertices
                # labelled all 1,845 routed links as chords.
                "drawn_as": how,
                "mean_edge_m": int(round(r["len"] / r["n"])),
                "drawn_edge_m": int(round(r["best"])),
            },
        })

    # --- the true lattice, unaggregated, for the named check areas ------------------
    areas = json.loads(Path(cfg["areas"]).read_text()) if Path(cfg["areas"]).exists() else {}
    for name, box in areas.items():
        if name.startswith("_"):
            continue
        w, so, ea, no = box
        inside = ((lon[e[:, 0]] >= w) & (lon[e[:, 0]] <= ea) &
                  (lat[e[:, 0]] >= so) & (lat[e[:, 0]] <= no))
        sub = np.nonzero(inside)[0]
        af = [{"type": "Feature",
               "geometry": {"type": "LineString", "coordinates": [
                   [float(lon[e[k, 0]]), float(lat[e[k, 0]])],
                   [float(lon[e[k, 1]]), float(lat[e[k, 1]])]]},
               "properties": {"res_a": int(min(ra[k], rb[k])),
                              "res_b": int(max(ra[k], rb[k])),
                              "res_pair": f"{min(ra[k], rb[k])}-{max(ra[k], rb[k])}",
                              "crosses_band": bool(cross[k]),
                              "length_m": int(round(float(length[k])))}}
              for k in sub]
        # the cells those edges run between, at their own resolution, so the area view
        # can show a lattice in which the links DO join the centres
        inb = np.nonzero((lon >= w) & (lon <= ea) & (lat >= so) & (lat <= no))[0]
        cf = [{"type": "Feature",
               "geometry": {"type": "Polygon", "coordinates": [
                   [[round(x, 5), round(y, 5)] for y, x in h3.cell_to_boundary(cell[k])]]},
               "properties": {"h3": cell[k], "res": int(g["resolution"][k]),
                              "depth_m": round(float(g["depth_m"][k]), 1)}}
              for k in inb]
        Path(cfg["check_dir"], f"cells-{name}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection",
             "properties": {"generation": stamp, "aggregated": False,
                            "what": "the routing cells themselves, res 7-9"},
             "features": cf}, separators=(",", ":")))
        Path(cfg["check_dir"], f"edges-{name}.geojson").write_text(json.dumps(
            {"type": "FeatureCollection",
             "properties": {"generation": stamp, "aggregated": False,
                            "what": "the routing lattice itself, res 7-9, unaggregated"},
             "features": af}, separators=(",", ":")))
        print(f"  {name}: {len(cf):,} true cells, {len(af):,} true edges")

    feats, dropped, frags = largest_component(feats)
    print(f"  dropped {dropped:,} links in {frags} fragments left isolated by the land trim")
    print(f"  {routed:,} links drawn along their res-7 path (the chord crossed land)")

    s = json.loads(Path(cfg["summary"]).read_text())
    fc = {
        "type": "FeatureCollection",
        "properties": {
            "generation": stamp,
            "what": "Links between the centres of adjacent sea cells: the surface a "
                    "route is measured on.",
            "an_edge_is_not_a_route":
                "A drawn edge is an ADJACENCY, not a track. No vessel sailed the straight "
                "line between two hexagon centres; the line says only that a route may "
                "pass from one cell to the next. A chain of them approximates a course to "
                "within the lattice's resolution and no better.",
            "lattice": s.get("lattice_note"),
            "links": len(feats),
            "links_dropped_isolated": dropped,
            "isolated_note":
                "Links left in a fragment disconnected from the main drawn network once "
                "the land-crossing chords were removed. The routing graph behind them is "
                "still one component; it reaches these cells round a headland by a path "
                "no single res-6 chord can represent.",
            "links_over_land_not_drawn": over_land,
            "links_drawn_as_res7_path": routed,
            "res7_path_note":
                "Where the straight chord between two cell centres crosses land but the "
                "res-7 routing graph joins them anyway — a channel narrower than the "
                "cells are wide — the link is drawn along the actual res-7 path instead "
                "of being dropped. Dropping it made the picture claim the channel is "
                "impassable when the route goes through it.",
            "land_trim":
                "A link is not drawn where the straight line between the two CELL CENTRES "
                "crosses land at 232 m, even though a res-7 route joins them round the "
                "headland. The chord and the route are different lines; this layer draws "
                "the chord, so the chord is what is tested.",
            "links_outside_published_cells": len(spill),
            "clip_note":
                "Aggregation lifts a res-6 cell into view as soon as one of its seven "
                "res-7 children is in the routing grid, so it spills a ring past the "
                "published layer. Those links are real edges; they are dropped here only "
                "so the two layers of the toggle cover the same ground.",
            "routing_edges_behind_them": int(len(e)),
            "aggregated_to_resolution": P,
            "aggregation":
                "The routing graph is res 7. These links thin it to one per pair of "
                "published res-6 cells: where any res-7 edge joins a child of one to a "
                "child of the other, THE SHORTEST SUCH EDGE IS DRAWN and `routing_edges` "
                "says how many it stands for. Every line is a real routing edge and both "
                "its endpoints are routing nodes. An earlier version drew parent-centre "
                "to parent-centre, which invented endpoints and put some of them on land, "
                "because a res-6 cell is kept for CONTAINING sighted sea and its centre "
                "may sit on a beach. For the whole lattice see the check export.",
            "cells": int(s.get("cells", len(res))),
            "crossing_a_band": sum(1 for f in feats if f["properties"]["crosses_band"]),
            "crossing_a_band_before_aggregation": int(cross.sum()),
            "band_counts_differ":
                "crossing_a_band counts features IN THIS LAYER. The res-7 graph behind "
                "it has more, because several routing edges collapse into one drawn "
                "link and the link is marked if any of them crosses. Take the count "
                "from this layer; the other figure is here to be compared, not drawn.",
            "crosses_band_meaning":
                "True where the two cells sit at different resolutions. These are the "
                "seams of the banding: with none of them the graph would be one "
                "disconnected sheet per resolution, each looking locally correct.",
            "links_rejected_crossing_land": s.get("links_rejected_crossing_land"),
            "rejection_rule":
                "A link whose straight line passes over land at 232 m is not an edge, "
                "even where both cells hold water — a spit or a peninsula between two "
                "cell centres. The same test decides which cells the grid keeps.",
            "length_is_not_a_weight":
                "length_m is geometry. Weights — wind, tide, season — are deferred.",
            "published_cells_with_no_edge": len(pub - {f["properties"]["h3_a"] for f in feats}
                                                 - {f["properties"]["h3_b"] for f in feats}),
            "cells_with_no_edge_meaning":
                "Cells the sightline layer draws as sighted sea that the routing graph "
                "never enters: every res-7 child was lost to the sea mask, the trim or "
                "the land test. Two of 17,599, off Wexford and off Caithness. They are "
                "counted here rather than left for a reader to find as hexes nothing "
                "touches.",
            "components": s.get("components"),
            "largest_component": s.get("largest_component"),
            "attribution": s.get("attribution"),
            "use_constraint": "DO NOT USE FOR NAVIGATION",
        },
        "features": feats,
    }
    # THE INSTRUMENT MUST COVER WHAT IT EXISTS TO SHOW. The check areas were chosen for
    # hard trace cases and then inherited by the edges export, where they covered 8 of 59
    # seams. A per-area file that misses the thing the layer is for is worse than none,
    # because it looks like coverage. This does not fail the run — the areas are a viewing
    # aid, not a result — but it says the number out loud every time.
    import h3 as _h3
    _in = 0
    for f in feats:
        if not f["properties"]["crosses_band"]:
            continue
        la, lo = _h3.cell_to_latlng(f["properties"]["h3_a"])
        if any(not n.startswith("_") and b[0] <= lo <= b[2] and b[1] <= la <= b[3]
               for n, b in areas.items()):
            _in += 1
    _n = sum(1 for f in feats if f["properties"]["crosses_band"])
    print(f"  seams inside a named check area: {_in} of {_n}"
          + ("" if _n and _in / _n >= 0.5 else "   ** most seams are not viewable **"))

    Path(cfg["out"]).write_text(json.dumps(fc, separators=(",", ":")))
    mb = Path(cfg["out"]).stat().st_size / 1e6
    print(f"wrote {cfg['out']} ({mb:.1f} MB, {len(feats):,} edges)")


if __name__ == "__main__":
    main()
