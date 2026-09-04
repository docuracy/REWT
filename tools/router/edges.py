"""Adjacency for the banded sea grid: what touches what, across resolutions.

    python3 tools/router/edges.py

Run from the repository root; paths are relative (AGENTS.md).

THE PROBLEM IS THE BAND BOUNDARIES. Within a band every cell has six neighbours at its
own resolution and `h3.grid_disk` gives them directly. At a boundary a coarse cell abuts
several finer ones, and neither cell appears in the other's disk at all — so a graph built
from `grid_disk` alone is SEVEN DISCONNECTED SHEETS, one per resolution, and every one of
them looks locally correct.

For a neighbour position not in the grid, exactly one of two things is true, because the
grid covers each place once: an ANCESTOR of it is in the grid (the neighbour is inside a
coarser cell), or DESCENDANTS of it are (the neighbour was subdivided). Walk up first,
then descend, keeping only descendants that actually touch the cell we started from.

EDGE LENGTH IS NOT AN EDGE WEIGHT. The distance between two cell centres is geometry and
is measured here. What it costs a vessel to cross is a weight, and weights are deferred
(PLAN.md 1).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

import h3

CONFIG = {
    "grid": "tools/router/cache/grid_r9.npz",
    "out": "tools/router/cache/edges_r9.npz",
    "summary": "docs/router/data/edge_summary.json",
    "start_resolution": 3,
    "coastal_sea_resolution": 9,
    "earth_radius_m": 6371000.0,
}


def main(cfg: dict = CONFIG) -> None:
    g = np.load(cfg["grid"], allow_pickle=True)
    cells = g["cell"].tolist()
    res = {c: int(r) for c, r in zip(cells, g["resolution"])}
    idx = {c: i for i, c in enumerate(cells)}
    lat, lon = g["lat"], g["lon"]
    R, R0 = cfg["coastal_sea_resolution"], cfg["start_resolution"]
    print(f"grid: {len(cells):,} cells, res {min(res.values())}-{max(res.values())}")

    def touches(child: str, c: str, r: int) -> bool:
        """Does `child` share a boundary with `c`, which is at resolution r?"""
        return any(h3.cell_to_parent(y, r) == c for y in h3.grid_disk(child, 1))

    pairs: set[tuple[int, int]] = set()
    crossings = Counter()
    for c in cells:
        r = res[c]
        for n in h3.grid_disk(c, 1):
            if n == c:
                continue
            if n in idx:                                    # same resolution
                a, b = idx[c], idx[n]
                pairs.add((a, b) if a < b else (b, a))
                crossings[(r, r)] += 1
                continue
            up = None                                       # inside a coarser cell?
            for rr in range(r - 1, R0 - 1, -1):
                p = h3.cell_to_parent(n, rr)
                if p in idx:
                    up = p
                    break
            if up is not None:
                a, b = idx[c], idx[up]
                pairs.add((a, b) if a < b else (b, a))
                crossings[tuple(sorted((r, res[up])))] += 1
                continue
            frontier = [n]                                  # or it was subdivided
            for rr in range(r + 1, R + 1):
                nxt = []
                for x in frontier:
                    for ch in h3.cell_to_children(x, rr):
                        if not touches(ch, c, r):
                            continue
                        if ch in idx:
                            a, b = idx[c], idx[ch]
                            pairs.add((a, b) if a < b else (b, a))
                            crossings[tuple(sorted((r, rr)))] += 1
                        else:
                            nxt.append(ch)
                frontier = nxt
                if not frontier:
                    break

    e = np.array(sorted(pairs), dtype=np.int32)
    print(f"edges: {len(e):,} undirected")

    la, lo = np.radians(lat), np.radians(lon)
    xyz = np.column_stack([np.cos(la)*np.cos(lo), np.cos(la)*np.sin(lo), np.sin(la)])
    length = np.linalg.norm(xyz[e[:, 0]] - xyz[e[:, 1]], axis=1) * cfg["earth_radius_m"]

    # --- checks (PLAN.md 9) -------------------------------------------------------
    print("\nCHECKS")
    deg = np.bincount(e.ravel(), minlength=len(cells))
    print(f"  degree: min {deg.min()}, median {int(np.median(deg))}, max {deg.max()}")
    iso = int((deg == 0).sum())
    print(f"  isolated cells (must be 0): {iso}")

    m = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(cells),)*2)
    ncomp, lab = connected_components(m, directed=False)
    sizes = np.bincount(lab)
    big = int(sizes.max())
    print(f"  connected components: {ncomp}  (largest holds {big:,} of {len(cells):,}, "
          f"{100*big/len(cells):.2f}%)")
    if ncomp > 1:
        print(f"  ** {ncomp-1} fragments. Sizes of the largest few: "
              f"{sorted(sizes.tolist(), reverse=True)[1:6]} **")
        for k in np.argsort(-sizes)[1:4]:
            j = int(np.nonzero(lab == k)[0][0])
            print(f"     fragment of {sizes[k]:,} at {lat[j]:.3f} N {lon[j]:.3f} E "
                  f"({cells[j]}, res {res[cells[j]]})")

    print("  edges by resolution pair — a graph with none across resolutions would be")
    print("  seven disconnected sheets, so this is the check that the banding is joined:")
    for (a, b), n in sorted(crossings.items()):
        tag = "same" if a == b else "**crosses**"
        print(f"    res {a} <-> res {b}: {n:>9,}  {tag}")
    cross = sum(n for (a, b), n in crossings.items() if a != b)
    print(f"  cross-resolution edges: {cross:,} of {2*len(e):,} directed "
          f"({100*cross/(2*len(e)):.2f}%)")
    if cross == 0:
        print("  ** none cross a band boundary — the graph is one sheet per resolution **")
    print(f"  edge length: median {np.median(length):.0f} m, "
          f"min {length.min():.0f} m, max {length.max():.0f} m")

    np.savez_compressed(cfg["out"], edge=e, length_m=length.astype("float32"))
    Path(cfg["summary"]).write_text(json.dumps({
        "cells": len(cells), "edges": int(len(e)),
        "components": int(ncomp), "largest_component": big,
        "isolated": iso,
        "degree": {"min": int(deg.min()), "median": int(np.median(deg)),
                   "max": int(deg.max())},
        "edges_by_resolution_pair": {f"{a}-{b}": n for (a, b), n in sorted(crossings.items())},
        "cross_resolution_directed": cross,
        "note": "Edge length is geometry, not a weight. Weights are deferred (PLAN.md 1).",
        "attribution": "Contains EMODnet Bathymetry data. EMODnet Bathymetry Consortium "
                       "(2024): EMODnet Digital Bathymetry (DTM 2024), licensed CC BY 4.0.",
        "use_constraint": "DO NOT USE FOR NAVIGATION",
    }, indent=1))
    print(f"\nwrote {cfg['out']} and {cfg['summary']}")


if __name__ == "__main__":
    main()
