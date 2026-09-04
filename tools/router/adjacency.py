"""Which cells are neighbours: ONE definition, imported by `grid2.py` and `edges.py`.

The land test was factored out first, after 220 cells survived grid2's connectivity pass
and were isolated by edges.py. That fixed half the divergence. This is the other half:
the two also BUILT the neighbour set differently — same idea, two hand-written walks over
`grid_disk`, ancestors and descendants — so "connected" still meant two things and the
disagreement reappeared as 7 isolated cells and 14 components the moment the sightline
moved. Two copies of a predicate is two chances to disagree, and the disagreement is
invisible while both copies are internally consistent.
"""
from __future__ import annotations

from collections import Counter

import h3


def build_pairs(res: dict[str, int], crosses_land, r_min: int, r_max: int):
    """Return (pairs, crossings, rejected) over the cells of `res` (cell -> resolution).

    `pairs` holds index-free cell-id tuples, sorted within each pair. A link is refused
    when the straight line between the two centres crosses land.
    """
    idx = set(res)
    ll = {c: h3.cell_to_latlng(c) for c in idx}
    pairs: set[tuple[str, str]] = set()
    crossings: Counter = Counter()
    rejected = 0

    def link(a: str, b: str) -> bool:
        nonlocal rejected
        if crosses_land(ll[a], ll[b]):
            rejected += 1
            return False
        pairs.add((a, b) if a < b else (b, a))
        crossings[tuple(sorted((res[a], res[b])))] += 1
        return True

    def touches(child: str, c: str, r: int) -> bool:
        return any(h3.cell_to_parent(y, r) == c for y in h3.grid_disk(child, 1))

    for c in idx:
        r = res[c]
        for n in h3.grid_disk(c, 1):
            if n == c:
                continue
            if n in idx:                                    # same resolution
                link(c, n)
                continue
            up = None                                       # inside a coarser cell?
            for rr in range(r - 1, r_min - 1, -1):
                p = h3.cell_to_parent(n, rr)
                if p in idx:
                    up = p
                    break
            if up is not None:
                link(c, up)
                continue
            frontier = [n]                                  # or it was subdivided
            for rr in range(r + 1, r_max + 1):
                nxt = []
                for x in frontier:
                    for ch in h3.cell_to_children(x, rr):
                        if not touches(ch, c, r):
                            continue
                        if ch in idx:
                            link(c, ch)
                        else:
                            nxt.append(ch)
                frontier = nxt
                if not frontier:
                    break
    return pairs, crossings, rejected
