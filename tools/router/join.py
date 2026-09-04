"""Join the river network's tidal termini to the sea grid.

    python3 tools/router/join.py

Run from the repository root; paths are relative (AGENTS.md).

THREE RULES, IN ORDER, STOPPING AT THE FIRST THAT SUCCEEDS (PLAN.md 7):

  1. the terminus already lies in a grid cell        -> an observation
  2. a grid cell lies within one cell edge           -> a short inference
  3. neither                                          -> needs a traced path

Every join records WHICH RULE FIRED, because a join made by rule 3 is an inference and one
made by rule 1 is an observation, and a reader must be able to tell them apart. A terminus
that cannot be joined is reported with its coordinate and kept, never dropped: AGENTS.md
says fail loudly and name every skip.

THE TERMINUS SET IS NOT FROZEN. R-01 is unbuilt; it will change which watercourses have
termini. It will not move them far (median 48 m from the high water line), so the algorithm
is stable under it and the population is not. Re-run when R-01 lands.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

import h3
from generation import generation

CONFIG = {
    "grid": "tools/router/cache/grid2.npz",
    "network": "published/rewt_stage1_network.gpkg",
    "scope_max_m_from_ew": 1000.0,   # see the scope note in main()
    "out": "docs/router/data/joins.geojson",
    "summary": "docs/router/data/join_summary.json",
    "earth_radius_m": 6371000.0,
    "start_resolution": 3,
    "coastal_sea_resolution": 9,
}


def to_xyz(lat, lon, r):
    la, lo = np.radians(lat), np.radians(lon)
    return np.column_stack([r*np.cos(la)*np.cos(lo), r*np.cos(la)*np.sin(lo), r*np.sin(la)])


def main(cfg: dict = CONFIG) -> None:
    g = np.load(cfg["grid"], allow_pickle=True)
    cells, cres = g["cell"], g["resolution"]
    glat, glon, gdep = g["lat"], g["lon"], g["depth_m"]
    cellset = set(cells.tolist())
    grid_res = sorted({int(r) for r in cres}, reverse=True)   # ask the grid, do not assume
    print(f"grid: {len(cells):,} cells, res {cres.min()}-{cres.max()}")

    node = gpd.read_file(cfg["network"], layer="node", ignore_geometry=True,
                         columns=["node_id", "terminus", "in_scope", "easting", "northing"])
    link = gpd.read_file(cfg["network"], layer="link", ignore_geometry=True,
                         columns=["from_node", "to_node", "retired"])
    live = link[~link.retired.astype(bool)]
    sinks = set(live.to_node.dropna()) - set(live.from_node.dropna())
    t = node[node.node_id.isin(sinks) & (node.terminus == "tidal")].copy()

    # SCOPE: basins that intersect England or Wales, which is what this project is about
    # (D-024, and Stephen 4 Sep 2026 — traces were being computed into northern Scotland).
    # `in_scope` is the audit's own derivation; `basin_in_scope` is only half the rule and
    # gives a different answer, so the implementer's instruction is to use `in_scope`.

    # SCOPE, AND WHY IT IS NOT JUST `in_scope` (Stephen, 4 September 2026)
    #
    # D-024 puts a basin in scope ENTIRE if any part of it lies in England or Wales, and
    # that rule is right: a river system should not be cut at a border. But two basins
    # are not catchments. `River Earn` runs from Northumberland to Montrose and `River
    # Nith` holds the Duddon Channel and the Isle of Bute — rewt-46's D-080 — and 4.0%
    # and 8.2% of them respectively lie in England, which puts the whole of both in
    # scope. Traces were being computed into northern Scotland.
    #
    # THE TEST IS GEOMETRIC AND IT IS NOT POINT-IN-POLYGON. A tidal terminus sits
    # SEAWARD of the high water line by definition, and the country polygon is bounded by
    # that line, so a plain containment test rejects the very features it should keep:
    # 194 of 474 fall outside England and Wales, and most are in basins 99-100% English.
    #
    # DISTANCE, and the threshold barely matters. Measured over the 474: median 0 m,
    # 75th percentile 10 m, then a JUMP to 95.75 km at the 90th. Nothing lies between
    # 10 m and 96 km. Everything beyond 20 km is the Nith (61) or the Earn (19) and
    # nothing else. Any cut from 1 km to 90 km gives the same answer, which is what a
    # real boundary looks like as against a tuned one. 1 km is a hundred times the
    # observed offset of a legitimate terminus.
    #
    # THIS DOES NOT FIX THE BASINS, and must not be mistaken for it. The delineation is
    # the implementer's and D-080 is still open; this is a geometric guard so the router
    # does not publish traces up the Tay while that stands.
    before = len(t)
    t = t[t.in_scope.astype(bool)].copy()
    _bl = "data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg"
    _cr = gpd.read_file(_bl, layer="country_region")
    from shapely.ops import unary_union as _uu
    from shapely.geometry import Point as _P
    _ew = _uu(_cr[_cr.Name.isin(["England", "Wales"])].geometry.values)
    _d = np.array([_P(x, y).distance(_ew) for x, y in zip(t.easting, t.northing)])
    t = t[_d <= cfg["scope_max_m_from_ew"]].copy()
    print(f"  scope: {len(t):,} of {before:,} tidal termini — in an England/Wales basin "
          f"AND within {cfg['scope_max_m_from_ew']/1000:.0f} km of England or Wales")
    tr = Transformer.from_crs(27700, 4326, always_xy=True)
    t["lon"], t["lat"] = tr.transform(t.easting.values, t.northing.values)
    print(f"termini: {len(t):,} tidal sinks, {int(t.in_scope.astype(bool).sum()):,} in scope")

    R = cfg["earth_radius_m"]
    tree = cKDTree(to_xyz(glat, glon, R))
    tx = to_xyz(t.lat.values, t.lon.values, R)
    nd, ni = tree.query(tx)

    edge = {r: h3.average_hexagon_edge_length(r, unit="m")
            for r in range(cfg["start_resolution"], cfg["coastal_sea_resolution"] + 1)}

    rule = np.zeros(len(t), int)
    cell_of = np.array([None] * len(t), object)
    res_of = np.zeros(len(t), int)
    dist_of = np.full(len(t), np.nan)

    for i, (la, lo) in enumerate(zip(t.lat.values, t.lon.values)):
        hit = None
        for r in range(cfg["coastal_sea_resolution"], cfg["start_resolution"] - 1, -1):
            c = h3.latlng_to_cell(float(la), float(lo), r)
            if c in cellset:
                hit = (c, r); break
        if hit:                                     # rule 1: already inside a cell
            rule[i] = 1; cell_of[i], res_of[i] = hit
            dist_of[i] = float(nd[i]) if cells[ni[i]] == hit[0] else 0.0
            continue
        # Rule 2 is ADJACENCY, and H3 states it exactly — no distance threshold at all.
        # "Within one cell edge" was the first version and it is not the same thing: it
        # is roughly "inside the cell", so it fired only where rule 1 had just missed,
        # and every rule-2 distance piled up against the 201 m edge like a wall. The
        # question rule 2 asks is whether the terminus sits in a cell NEXT DOOR to the
        # grid, which is a property of the tiling, not of a tuned radius.
        # ADJACENCY AT WHATEVER RESOLUTIONS THE GRID ACTUALLY USES. This asked at res 9
        # because the old distance-banded grid ended there; the state-banded one is
        # mostly res 7, so every lookup missed and rule 2 collapsed into rule 3 — 724
        # "needs a traced path" where there should have been about 140.
        nb, own_res = [], None
        for rr in grid_res:
            own = h3.latlng_to_cell(float(la), float(lo), rr)
            found = [c for c in h3.grid_disk(own, 1) if c in cellset]
            if found:
                nb, own_res = found, rr
                break
        j = int(ni[i]); r = int(cres[j])
        if nb:                                      # rule 2: a grid cell is adjacent
            # the NEAREST adjacent cell, not whichever grid_disk happened to list first.
            # The arbitrary pick also made the drawn line disagree with the recorded
            # attachment on 115 joins — the map said one thing and the data another.
            nb.sort(key=lambda c: (lambda p: (p[0] - la) ** 2
                                   + ((p[1] - lo) * np.cos(np.radians(la))) ** 2)
                    (h3.cell_to_latlng(c)))
            rule[i] = 2; cell_of[i] = nb[0]
            res_of[i] = own_res; dist_of[i] = float(nd[i])
        else:                                       # rule 3: needs a traced path
            rule[i] = 3; cell_of[i], res_of[i] = cells[j], r; dist_of[i] = float(nd[i])

    t["rule"], t["cell"], t["cell_res"], t["dist_m"] = rule, cell_of, res_of, dist_of
    dep = gdep[ni]
    t["attach_depth_m"] = np.where(rule < 3, dep, np.nan)

    print("\nJOINS BY RULE")
    for label, sub in (("all", t), ("in scope", t[t.in_scope.astype(bool)])):
        n = len(sub)
        print(f"  {label} (n={n:,})")
        for k, what in ((1, "already in a cell   (observation)"),
                        (2, "adjacent to a cell  (short inference)"),
                        (3, "needs a traced path (inference)")):
            m = int((sub.rule == k).sum())
            print(f"    rule {k}: {m:>6,} ({100*m/n:5.1f}%)  {what}")
        d = sub[sub.rule == 2].dist_m
        if len(d):
            print(f"      rule-2 distances: median {d.median():.0f} m, max {d.max():.0f} m")

    r3 = t[t.rule == 3].sort_values("dist_m", ascending=False)
    print(f"\nRULE 3 — every one named, with its coordinate (never truncated: this answers "
          f"'is there anything else')")
    for _, row in r3.iterrows():
        print(f"    {row.node_id}  {row.dist_m/1000:6.2f} km to res-{row.cell_res} cell  "
              f"at {row.lat:.4f} N {row.lon:.4f} E  "
              f"{'in scope' if row.in_scope else 'out of scope'}")
    if r3.empty:
        print("    none — and that is itself a finding, so check rule 2's threshold")

    Path(cfg["summary"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["summary"]).write_text(json.dumps({
        "generation": generation(), "termini": len(t), "in_scope": int(t.in_scope.astype(bool).sum()),
        "by_rule": {str(k): int((t.rule == k).sum()) for k in (1, 2, 3)},
        "by_rule_in_scope": {str(k): int(((t.rule == k) & t.in_scope.astype(bool)).sum())
                             for k in (1, 2, 3)},
        "rule3": [{"node_id": r.node_id, "lat": round(r.lat, 5), "lon": round(r.lon, 5),
                   "dist_m": round(r.dist_m), "in_scope": bool(r.in_scope)}
                  for _, r in r3.iterrows()],
        "note": "R-01 unbuilt: the terminus SET will change, the positions will not move far",
    }, indent=1))
    print(f"\nwrote {cfg['summary']}")

    # DRAW THE ATTACHMENT THAT WAS RECORDED, and only where one exists. A rule-3
    # terminus has no attachment yet: drawing a straight line to the nearest cell
    # asserted a connection across 50 km of London, and it looked like a route. Those
    # are points now, and the actual path is stage 4's business.
    def geom(r, k):
        p = h3.cell_to_latlng(str(r.cell))
        here = [round(r.lon, 6), round(r.lat, 6)]
        if r.rule == 3:
            return {"type": "Point", "coordinates": here}
        return {"type": "LineString",
                "coordinates": [here, [round(p[1], 6), round(p[0], 6)]]}

    feats = [{"type": "Feature",
              "geometry": geom(r, k),
              "properties": {"node_id": r.node_id, "rule": int(r.rule),
                             "cell": str(r.cell), "cell_res": int(r.cell_res),
                             "dist_m": round(float(r.dist_m)),
                             "in_scope": bool(r.in_scope),
                             "attach_depth_m": None if np.isnan(r.attach_depth_m)
                             else round(float(r.attach_depth_m), 1)}}
             for k, (_, r) in enumerate(t.iterrows())]
    Path(cfg["out"]).write_text(json.dumps({
        "type": "FeatureCollection",
        "properties": {"what": "river terminus -> sea grid joins, one line each",
                       "attribution": [
                           "Contains EMODnet Bathymetry data. EMODnet Bathymetry "
                           "Consortium (2024): EMODnet Digital Bathymetry (DTM 2024), "
                           "licensed CC BY 4.0.",
                           "Contains OS data (c) Crown copyright and database right, "
                           "via published/rewt_stage1_network.gpkg — see "
                           "published/ATTRIBUTION.md, which this may never attribute "
                           "less fully than."],
                       "derived_from": ["emodnet_bathymetry (the sea grid)",
                                        "published/rewt_stage1_network.gpkg (the termini)"],
                       "rules": {"1": "terminus already inside a grid cell",
                                 "2": "grid cell within one cell edge",
                                 "3": "needs a traced path — NOT YET TRACED"},
                       "use_constraint": "DO NOT USE FOR NAVIGATION"},
        "features": feats}))
    p = Path(cfg["out"])
    print(f"wrote {p} ({p.stat().st_size/1e6:.1f} MB, {len(feats):,} features)")


if __name__ == "__main__":
    main()
