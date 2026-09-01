"""The sea as a test rather than a definition (PLAN.md §10).

§1's traversability test ends at tidal water, so "reaches the sea" is true by
definition and cannot fail. This module builds the thing that makes it a test: a
network over the water itself, on which a mouth can be shown to connect — or shown
not to.

**The route is measured, not drawn.** An earlier version of §10 specified a contour at
a stated depth. A contour is a stipulation and the sea does not oblige it: at 10 m
below Lowest Astronomical Tide the line hugs the shore in the Minch and stands 80 km
out in the southern North Sea. What is stipulated here instead is a *cost surface* —
one parameter, `sea.clearance_m` — and the network is whatever least cost produces on
it.

**Paths run between mouths, not seaward.** This is the point the construction turns
on, and the first draft had it wrong. A path to open water takes each mouth to the
nearest edge of the survey: east-coast mouths run east, west-coast mouths run west,
and nothing converges. A coastal route exists only as a *relation between* the mouths,
so the mouths are what the paths connect.
"""

from __future__ import annotations

import numpy as np

# WhiteboxTools' D8 pointer, which its cost_distance writes as a backlink. A wrong
# convention here sends every walk off the grid rather than into a source, so the
# tracer's "unterminated" count is also the test of this table.
D8 = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0),
      16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}

# Every edge must survive into the sparse matrix's *structure*. 510 of 6,191 crossings
# cost exactly zero — two territories meeting at the cell a source sits on — and an
# explicit zero is not stored, so scipy drops them and connected_components walks a
# graph missing its cheapest links. It reported a fragmented coastal sea, which §10
# had pre-authorised as a finding about the bathymetry (D-056).
EDGE_EPSILON = 1e-6


def cost_surface(depth_m: np.ndarray, clearance_m: float, deep_reference_m: float):
    """Impassable above the clearance; cheaper as it deepens.

    `depth_m` is positive downward, so land and nodata fall out for free — the source
    is a merged land-and-sea surface with land positive, and "shallower than the
    clearance" excludes it without a separate land mask.

    A cell at exactly the clearance costs `deep_reference_m / clearance_m` times one of
    open water, so a path trades distance against depth rather than hugging the deepest
    line at any length. That trade is what "deepest *available* channel" means.
    """
    passable = np.isfinite(depth_m) & (depth_m >= clearance_m)
    cost = np.full(depth_m.shape, -9999.0, dtype="float32")
    cost[passable] = np.clip(
        deep_reference_m / np.maximum(depth_m[passable], clearance_m),
        1.0, deep_reference_m / clearance_m,
    )
    return cost, passable


def open_sea(passable: np.ndarray) -> np.ndarray:
    """The largest connected body of passable water.

    Mouths snap to this and to nothing else. The nearest qualifying cell to a mouth on
    a ria coast can be an isolated pocket up an estuary, and a route starting there is
    a route to nowhere that looks like a working path.
    """
    from scipy import ndimage

    lab, _ = ndimage.label(passable)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == int(sizes.argmax())


def snap(rows, cols, ocean: np.ndarray, max_cells: int, cell_m: float):
    """Move each mouth to the nearest open-sea cell, or record that it could not.

    Returns the distance moved, negative where no open sea lies within `max_cells`.
    Those are findings and §10 requires them named rather than dropped.
    """
    H, W = ocean.shape
    moved = np.full(len(rows), -1.0)
    sr = np.zeros(len(rows), int)
    sc = np.zeros(len(rows), int)
    for i in range(len(rows)):
        r, c = int(rows[i]), int(cols[i])
        for rad in range(0, max_cells + 1):
            r0, r1 = max(0, r - rad), min(H, r + rad + 1)
            c0, c1 = max(0, c - rad), min(W, c + rad + 1)
            win = ocean[r0:r1, c0:c1]
            if not win.any():
                continue
            rr, cc = np.nonzero(win)
            d = (rr + r0 - r) ** 2 + (cc + c0 - c) ** 2
            k = int(np.argmin(d))
            sr[i], sc[i] = rr[k] + r0, cc[k] + c0
            moved[i] = float(np.sqrt(d[k]) * cell_m)
            break
    return moved, sr, sc


def crossings(alloc: np.ndarray, accum: np.ndarray, water: np.ndarray, n: int) -> dict:
    """The cheapest crossing between every pair of adjacent territories.

    Eight-connected: territories that touch only at a corner are still neighbours, and
    on a cell grid a diagonal contact is as real as an orthogonal one.
    """
    H, W = alloc.shape
    best: dict[int, tuple] = {}
    for da, db in ((0, 1), (1, 0), (1, 1), (1, -1)):
        if db >= 0:
            sa = (slice(0, H - da), slice(0, W - db))
            sb = (slice(da, H), slice(db, W))
        else:
            sa = (slice(0, H - da), slice(-db, W))
            sb = (slice(da, H), slice(0, W + db))
        A, B = alloc[sa], alloc[sb]
        m = water[sa] & water[sb] & (A > 0) & (B > 0) & (A != B)
        if not m.any():
            continue
        rr, cc = np.nonzero(m)
        tot = accum[sa][m] + accum[sb][m]
        lo = np.minimum(A[m], B[m]).astype(np.int64)
        hi = np.maximum(A[m], B[m]).astype(np.int64)
        key = lo * (n + 1) + hi
        for idx in np.argsort(tot):
            k = int(key[idx])
            if k in best:
                continue
            best[k] = (int(rr[idx] + sa[0].start), int(cc[idx] + sa[1].start),
                       int(rr[idx] + sb[0].start), int(cc[idx] + sb[1].start),
                       float(tot[idx]))
    return best


def spanning_tree(best: dict, n: int):
    """The minimum spanning tree over territories, and the component count.

    A tree, not a cycle. For "can every mouth reach the sea and every other mouth" a
    tree is sufficient; a cycle is a second way round, which is navigation.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components, minimum_spanning_tree

    keys = np.array(sorted(best), dtype=np.int64)
    cost = np.array([best[int(k)][4] for k in keys], dtype="float64")
    lo = (keys // (n + 1)) - 1
    hi = (keys % (n + 1)) - 1
    g = coo_matrix((cost + EDGE_EPSILON, (lo, hi)), shape=(n, n))
    g = g.maximum(g.T)
    ncomp, labels = connected_components(g, directed=False)
    mst = minimum_spanning_tree(g).tocoo()
    return mst, ncomp, labels


def walk(back: np.ndarray, r: int, c: int, max_steps: int):
    """Follow the backlink to the source it belongs to.

    Returns the cells and whether it terminated. A walk that does not terminate is
    refused rather than drawn: §10 requires a path longer than `sea.max_path_km` to be
    a finding, because a least-cost path across an unsurveyed hole produces a
    confident track through water nobody has measured.
    """
    H, W = back.shape
    out = [(r, c)]
    for _ in range(max_steps):
        d = back[r, c]
        if d == 0:
            return out, True
        if d not in D8:
            return out, False
        dr, dc = D8[int(d)]
        r, c = r + dr, c + dc
        if not (0 <= r < H and 0 <= c < W):
            return out, False
        out.append((r, c))
    return out, False
