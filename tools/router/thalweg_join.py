"""Join the thalweg chains into one connected network.

THE PROBLEM. `thalweg.py` finds where the seabed is locally deepest, and that is a set of
CHAINS with no connectivity at all — 31,752 of them. Drainage gives a tree for free because
every cell flows somewhere; a thalweg detector gives disconnected evidence. A route cannot
use it until the gaps are bridged.

THE APPROACH. Treat each chain as a node and each possible bridge between two chain ENDS as
a candidate edge, then take a minimum spanning forest — the cheapest set of bridges that
connects everything it can reach. Cheapest is measured, not assumed:

  a bridge is REFUSED if it crosses land, using the same 232 m mask and the same Shapely
  test as every other link in this project;
  its WEIGHT is its length penalised by how shallow it gets, because a short bridge over a
  bank is worse than a longer one that stays in the channel — a vessel would take the
  longer one and so should the network.

WHAT THIS IS AND IS NOT. It is a connected graph over the thalwegs. It is NOT a claim that
the bridges are real channels: a bridge is an inference that two deep threads are usable
together, and every one is flagged so it can be told apart from a detected thalweg. The
distinction is the same as rule 1 against rule 3 in the river joins — observation against
inference, kept visible rather than blended.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, minimum_spanning_tree
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402

CONFIG = {
    "chains": "docs/router/check/thalwegs.geojson",
    "masks": "tools/router/cache/sightline_masks.npz",
    "cache": "tools/router/cache/seabed_fine.npz",
    "out": "docs/router/check/thalweg_network.geojson",
    "summary": "docs/router/check/thalweg_network_summary.json",
    "max_bridge_km": 15.0,   # candidates; the sweep below picks what is used     # a gap longer than this is not a gap, it is open water
    # A VERTEX'S NEAREST NEIGHBOURS ARE ITS OWN CHAIN. At 232 m spacing a vertex has
    # some 35 of its own within 4 km, so asking for 10 finds no other chain at all and
    # the candidate graph fell to 2,717 components. It has to be large enough to see
    # past the chain the vertex is on.
    "neighbours": 64,
    "shallow_penalty_m": 5.0, # depth at which a bridge starts costing extra
    "coord_dp": 5,
}


def main(cfg: dict = CONFIG) -> None:
    fc = json.loads(Path(cfg["chains"]).read_text())
    chains = fc["features"]
    m = np.load(cfg["masks"], allow_pickle=True)
    c = np.load(cfg["cache"])
    z, dom = c["z"], c["dom"]
    ftr, crs = m["fine_transform"], str(m["crs"][0])
    px = float(m["fine_px"][0])
    fh, fw = z.shape
    fwd = Transformer.from_crs(4326, crs, always_xy=True)
    back = Transformer.from_crs(crs, 4326, always_xy=True)
    print(f"{len(chains):,} thalweg chains")

    # --- EVERY VERTEX, NOT JUST THE ENDS ------------------------------------------
    # The first version offered bridges only between chain ENDS. Two channels running
    # 300 m apart could then only be joined by a hop from one end to the other, so the
    # median bridge came out at 4.89 km against a 6 km cap — the tree was reaching across
    # open water because the short connection was not on the menu. It left 525 components
    # and a largest holding 42% of the chains. A bridge may land anywhere on a chain.
    pts, owner = [], []
    for i, f in enumerate(chains):
        for lo, la in f["geometry"]["coordinates"]:
            pts.append(fwd.transform(lo, la))
            owner.append(i)
    ends = np.array(pts)
    owner = np.array(owner)
    print(f"  {len(ends):,} chain vertices (any of them may take a bridge)")

    def sample(a, b):
        """Depths along a bridge, at half-pixel steps. None if it leaves the water."""
        n = max(4, int(np.hypot(b[0] - a[0], b[1] - a[1]) / (px / 2)) + 1)
        t = np.linspace(0, 1, n)
        X = a[0] + (b[0] - a[0]) * t
        Y = a[1] + (b[1] - a[1]) * t
        col = ((X - ftr[2]) / ftr[0]).astype(int)
        row = ((Y - ftr[5]) / ftr[4]).astype(int)
        ok = (row >= 0) & (row < fh) & (col >= 0) & (col < fw)
        if not ok.all():
            return None
        if not dom[row, col].all():
            return None                      # leaves the sea, or the coastal band
        return -z[row, col].astype(float)    # positive metres of water

    # --- candidate bridges: the shortest link between each pair of chains ----------
    tree = cKDTree(ends)
    K = cfg["neighbours"]
    dd, ii = tree.query(ends, k=K + 1, distance_upper_bound=cfg["max_bridge_km"] * 1000.0)
    best: dict = {}
    for a in range(len(ends)):
        for t in range(1, K + 1):
            b = int(ii[a, t])
            if b >= len(ends):
                continue
            if owner[a] == owner[b]:
                continue
            key = (min(owner[a], owner[b]), max(owner[a], owner[b]))
            L = float(dd[a, t])
            if key not in best or L < best[key][0]:
                best[key] = (L, a, b)
    print(f"  {len(best):,} chain pairs with a candidate link")

    rows, cols, wts, keep = [], [], [], []
    refused_land = 0
    for key, (L, a, b) in best.items():
        d = sample(ends[a], ends[b])
        if d is None:
            refused_land += 1
            continue
        shallow = max(0.0, cfg["shallow_penalty_m"] - float(d.min()))
        rows.append(key[0]); cols.append(key[1])
        wts.append(L * (1.0 + shallow))
        keep.append((a, b, L, float(d.min())))
    print(f"  {len(wts):,} usable bridges; {refused_land:,} refused for leaving the water")

    n = len(chains)
    # HOW FAR MUST A BRIDGE REACH TO CONNECT THIS? Sweep the cap over the candidates
    # already validated, so the answer is a curve rather than a guess. A thalweg exists
    # only where the seabed has a cross-section; between them are stretches of flat with
    # no thalweg at all, and the curve says how long those stretches are.
    Lk = np.array([k[2] for k in keep]) / 1000.0
    print(f"  {'cap km':>7} {'bridges':>9} {'components':>11} {'largest %':>10}")
    for cap in (2, 4, 6, 8, 10, 12, 15):
        sel = Lk <= cap
        gg = coo_matrix((np.ones(int(sel.sum())),
                         (np.array(rows)[sel], np.array(cols)[sel])), shape=(n, n))
        nc, lb = connected_components(gg + gg.T, directed=False)
        print(f"  {cap:>7} {int(sel.sum()):>9,} {nc:>11,} "
              f"{100*np.bincount(lb).max()/n:>9.1f}%")
    g = coo_matrix((wts, (rows, cols)), shape=(n, n))
    ncomp0, _ = connected_components(g + g.T, directed=False)
    mst = minimum_spanning_tree(g + g.T).tocoo()
    chosen = {(min(a, b), max(a, b)) for a, b in zip(mst.row, mst.col)}
    print(f"  chain graph: {ncomp0:,} components before the tree, "
          f"{len(chosen):,} bridges chosen")

    # --- emit: chains as found, plus the bridges that connect them -----------------
    D = cfg["coord_dp"]
    feats = []
    for f in chains:
        p = dict(f["properties"]); p["kind"] = "thalweg"
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": p})
    used = set()
    for (i, j, L, dmin) in keep:
        k = (min(owner[i], owner[j]), max(owner[i], owner[j]))
        if k not in chosen or k in used:
            continue
        used.add(k)
        a, b = back.transform(*ends[i]), back.transform(*ends[j])
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": [
                          [round(a[0], D), round(a[1], D)],
                          [round(b[0], D), round(b[1], D)]]},
                      "properties": {"kind": "bridge", "km": round(L / 1000, 2),
                                     "min_depth_m": round(dmin, 1)}})
    nb = sum(1 for f in feats if f["properties"]["kind"] == "bridge")

    # what did it achieve?
    r2 = [owner[i] for (i, j, L, d) in keep if (min(owner[i], owner[j]),
                                                max(owner[i], owner[j])) in used]
    c2 = [owner[j] for (i, j, L, d) in keep if (min(owner[i], owner[j]),
                                                max(owner[i], owner[j])) in used]
    g2 = coo_matrix((np.ones(len(r2)), (r2, c2)), shape=(n, n))
    ncomp, lab = connected_components(g2 + g2.T, directed=False)
    sz = np.bincount(lab)
    bl = np.array([f["properties"]["km"] for f in feats
                   if f["properties"]["kind"] == "bridge"])
    print(f"  after joining: {ncomp:,} components, largest holds {sz.max():,} of {n:,} "
          f"chains ({100*sz.max()/n:.1f}%)")
    print(f"  bridges: {nb:,}, median {np.median(bl):.2f} km, "
          f"90th {np.percentile(bl, 90):.2f} km, max {bl.max():.2f} km")

    props = {
        "generation": generation(),
        "what": "The thalweg chains plus the bridges that connect them. `kind` is 'thalweg' "
                "where the deepest line was DETECTED and 'bridge' where a connection was "
                "INFERRED between two chain ends.",
        "how": "Each chain is a node, each short gap between two chain ends a candidate "
               "edge; a minimum spanning forest picks the cheapest set that connects what "
               "it can. A bridge crossing land is refused on the 232 m mask. Weight is "
               "length penalised by shallowness, so a short bridge over a bank loses to a "
               "longer one that stays in the channel.",
        "chains": len(chains), "bridges": nb,
        "components_before": int(ncomp0), "components_after": int(ncomp),
        "largest_component_chains": int(sz.max()),
        "largest_component_pct": round(100 * float(sz.max()) / n, 1),
        "bridge_km": {"median": round(float(np.median(bl)), 2),
                      "p90": round(float(np.percentile(bl, 90)), 2),
                      "max": round(float(bl.max()), 2)},
        "max_bridge_km": cfg["max_bridge_km"],
        "a_bridge_is_an_inference":
            "A bridge is not a detected channel. It says two deep threads are usable "
            "together, which is a claim about navigability that nothing here has tested. "
            "It is flagged so it can be told from a thalweg rather than blended with one — "
            "the same distinction the river joins draw between observation and inference.",
        "not_a_router": "No draught test, nothing joined to the river network or the hex "
                        "grid, and no comparison against either.",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }
    Path(cfg["out"]).write_text(json.dumps(
        {"type": "FeatureCollection", "properties": props, "features": feats},
        separators=(",", ":")))
    Path(cfg["summary"]).write_text(json.dumps(props, indent=1))
    print(f"wrote {cfg['out']} ({Path(cfg['out']).stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
