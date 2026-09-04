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

CONFIG = {
    "grid": "tools/router/cache/grid_r9.npz",
    "network": "published/rewt_stage1_network.gpkg",
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
    print(f"grid: {len(cells):,} cells, res {cres.min()}-{cres.max()}")

    node = gpd.read_file(cfg["network"], layer="node", ignore_geometry=True,
                         columns=["node_id", "terminus", "in_scope", "easting", "northing"])
    link = gpd.read_file(cfg["network"], layer="link", ignore_geometry=True,
                         columns=["from_node", "to_node", "retired"])
    live = link[~link.retired.astype(bool)]
    sinks = set(live.to_node.dropna()) - set(live.from_node.dropna())
    t = node[node.node_id.isin(sinks) & (node.terminus == "tidal")].copy()
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
        own = h3.latlng_to_cell(float(la), float(lo), cfg["coastal_sea_resolution"])
        nb = [c for c in h3.grid_disk(own, 1) if c in cellset]
        j = int(ni[i]); r = int(cres[j])
        if nb:                                      # rule 2: a grid cell is adjacent
            rule[i] = 2; cell_of[i] = nb[0]
            res_of[i] = cfg["coastal_sea_resolution"]; dist_of[i] = float(nd[i])
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
        "termini": len(t), "in_scope": int(t.in_scope.astype(bool).sum()),
        "by_rule": {str(k): int((t.rule == k).sum()) for k in (1, 2, 3)},
        "by_rule_in_scope": {str(k): int(((t.rule == k) & t.in_scope.astype(bool)).sum())
                             for k in (1, 2, 3)},
        "rule3": [{"node_id": r.node_id, "lat": round(r.lat, 5), "lon": round(r.lon, 5),
                   "dist_m": round(r.dist_m), "in_scope": bool(r.in_scope)}
                  for _, r in r3.iterrows()],
        "note": "R-01 unbuilt: the terminus SET will change, the positions will not move far",
    }, indent=1))
    print(f"\nwrote {cfg['summary']}")

    feats = [{"type": "Feature",
              "geometry": {"type": "LineString", "coordinates": [
                  [round(r.lon, 6), round(r.lat, 6)],
                  [round(float(glon[ni[k]]), 6), round(float(glat[ni[k]]), 6)]]},
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
