"""The routing graph: components, sinks, cycles, and the crawl uphill from the sea.

**Do not patch the network where it looks broken. Grow it from the sea, and let
whatever fails to arrive be the report** (PLAN.md §5, D-005). The two framings sound
equivalent and are not: patching asks *is this hole closed?* and answers yes for a
hole whose closure leads somewhere else broken. The crawl asks *can the water get
out?* and cannot answer yes for a reach that cannot.

Everything here works on integer node indices and numpy arrays. A hundred and ninety
thousand edges is small for scipy and large for a Python loop, and the difference
between the two is the difference between seconds and an afternoon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components

from . import config, db


@dataclass
class Graph:
    """A directed graph over the network, with its node vocabulary.

    `u` is upstream and `v` downstream on every row, because the loader stored the
    nodes already oriented and the repair stage is the only thing that reverses one.
    """

    edge_ids: np.ndarray          # identifiers, aligned with u/v
    link_ids: np.ndarray
    u: np.ndarray                 # upstream node index
    v: np.ndarray                 # downstream node index
    length: np.ndarray
    form: np.ndarray
    mode: np.ndarray              # "downstream" | "both"
    nodes: np.ndarray             # node index -> node id
    node_index: dict[str, int]

    # -- shape ------------------------------------------------------------
    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_edges(self) -> int:
        return len(self.u)

    def index_of(self, node_id: str) -> int:
        return self.node_index[node_id]

    def indices_of(self, node_ids: Iterable[str]) -> np.ndarray:
        idx = [self.node_index[n] for n in node_ids if n in self.node_index]
        return np.asarray(idx, dtype=np.int64)

    # -- degrees ----------------------------------------------------------
    def outdegree(self) -> np.ndarray:
        return np.bincount(self.u, minlength=self.n_nodes)

    def indegree(self) -> np.ndarray:
        return np.bincount(self.v, minlength=self.n_nodes)

    def sinks(self) -> np.ndarray:
        """Nodes with inflows and no outflow — the symptom PLAN.md §5 anatomises.

        A symptom with several causes: a real gap, a line drawn backwards, or an end
        sitting on another channel with no node between them.
        """
        return np.flatnonzero((self.indegree() > 0) & (self.outdegree() == 0))

    def headwaters(self) -> np.ndarray:
        return np.flatnonzero((self.outdegree() > 0) & (self.indegree() == 0))

    def bifurcations(self) -> np.ndarray:
        """Nodes with more than one outflow.

        PLAN.md §6: only 1,324 nodes in ~198,000 have more than one, so components are
        overwhelmingly tree-like and rooting is well defined. Treat these as the
        exceptions they are.
        """
        return np.flatnonzero(self.outdegree() > 1)

    def one_in_two_out(self) -> np.ndarray:
        """One inflow and two outflows: the signature of a tributary drawn flowing
        away from its parent (§6). A single earlier pass found 245 of them."""
        return np.flatnonzero((self.indegree() == 1) & (self.outdegree() >= 2))

    # -- components -------------------------------------------------------
    def weak_components(self) -> np.ndarray:
        """Sets of links connected regardless of direction (§6's census)."""
        m = coo_matrix(
            (np.ones(self.n_edges, dtype=np.int8), (self.u, self.v)),
            shape=(self.n_nodes, self.n_nodes),
        )
        _, labels = connected_components(m, directed=True, connection="weak")
        return labels

    def strong_components(self) -> np.ndarray:
        m = coo_matrix(
            (np.ones(self.n_edges, dtype=np.int8), (self.u, self.v)),
            shape=(self.n_nodes, self.n_nodes),
        )
        _, labels = connected_components(m, directed=True, connection="strong")
        return labels

    def cycles(self) -> list[np.ndarray]:
        """Closed loops with no exit. A cycle strands everything above it and is
        invisible in any total (§6).

        As shipped, OS Open Rivers has none of 10 km or more, so any that appear later
        were introduced by your own repairs.
        """
        labels = self.strong_components()
        counts = np.bincount(labels)
        big = np.flatnonzero(counts > 1)
        out = []
        for label in big:
            out.append(np.flatnonzero(labels == label))
        # A self-loop is a cycle of one node and is missed by the size test above.
        for e in np.flatnonzero(self.u == self.v):
            out.append(np.asarray([self.u[e]]))
        return out

    # -- the crawl --------------------------------------------------------
    def reachable_from_sea(self, seeds: Sequence[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Grow the network upstream from tidal termini.

        Admit a link only when the node at its downstream end is already in the
        network; repeat until nothing more is admitted. Returns, per edge, whether it
        was admitted; per edge, the seed it drains to; and per edge, its hop count.

        A `mode: both` edge — the summit pound of a canal, which drains two ways by
        design — is admitted from either end, because either end may be its outlet.
        """
        n_nodes, n_edges = self.n_nodes, self.n_edges
        admitted = np.zeros(n_edges, dtype=bool)
        edge_seed = np.full(n_edges, -1, dtype=np.int64)
        edge_hops = np.full(n_edges, -1, dtype=np.int32)
        node_seed = np.full(n_nodes, -1, dtype=np.int64)

        in_network = np.zeros(n_nodes, dtype=bool)
        seed_idx = np.asarray(list(seeds), dtype=np.int64)
        in_network[seed_idx] = True
        node_seed[seed_idx] = seed_idx

        # Edges indexed by their downstream node, so "which links arrive here?" is a
        # slice and not a scan. A `both` edge is additionally indexed by its upstream
        # node, so arriving at either end admits it.
        by_down = _csr_by_key(self.v, n_nodes)
        both = self.mode == "both"
        by_up_both = _csr_by_key(np.where(both, self.u, -1), n_nodes)

        frontier = seed_idx
        hops = 0
        while frontier.size:
            hops += 1
            new_nodes: list[np.ndarray] = []
            for keys, other in ((by_down, self.u), (by_up_both, self.v)):
                cand = keys.gather(frontier)
                if cand.size == 0:
                    continue
                cand = cand[~admitted[cand]]
                if cand.size == 0:
                    continue
                admitted[cand] = True
                edge_hops[cand] = hops
                anchor = self.v[cand] if keys is by_down else self.u[cand]
                edge_seed[cand] = node_seed[anchor]
                upstream = other[cand]
                fresh = upstream[~in_network[upstream]]
                if fresh.size:
                    fresh = np.unique(fresh)
                    # Deterministic: a node reached by two seeds in one wave takes the
                    # lowest seed index, not whichever the iteration happened to hit.
                    order = np.argsort(edge_seed[cand], kind="stable")
                    src = np.full(n_nodes, -1, dtype=np.int64)
                    src[upstream[order]] = edge_seed[cand][order]
                    in_network[fresh] = True
                    node_seed[fresh] = src[fresh]
                    new_nodes.append(fresh)
            frontier = np.unique(np.concatenate(new_nodes)) if new_nodes else np.empty(0, np.int64)

        return admitted, edge_seed, edge_hops

    # -- upstream accounting ---------------------------------------------
    def upstream_length(self, start_nodes: Sequence[int], mask: np.ndarray | None = None) -> np.ndarray:
        """Length of network standing above each node, following flow upstream.

        This is what ranks the defect list: *how much water stands above this entry?*
        Computed independently per start node, because two dead ends may share the
        reach above them and each is answerable for it.
        """
        by_down = _csr_by_key(self.v, self.n_nodes)
        out = np.zeros(len(start_nodes), dtype=float)
        for i, start in enumerate(start_nodes):
            seen_edges: set[int] = set()
            stack = [int(start)]
            seen_nodes = {int(start)}
            total = 0.0
            while stack:
                node = stack.pop()
                for e in by_down.gather(np.asarray([node], dtype=np.int64)):
                    e = int(e)
                    if e in seen_edges or (mask is not None and not mask[e]):
                        continue
                    seen_edges.add(e)
                    total += float(self.length[e])
                    up = int(self.u[e])
                    if up not in seen_nodes:
                        seen_nodes.add(up)
                        stack.append(up)
            out[i] = total
        return out


class _Index:
    """A CSR-style index from key to the rows carrying it. Built once, sliced often."""

    def __init__(self, indptr: np.ndarray, order: np.ndarray):
        self.indptr = indptr
        self.order = order

    def gather(self, keys: np.ndarray) -> np.ndarray:
        if keys.size == 0:
            return np.empty(0, dtype=np.int64)
        starts = self.indptr[keys]
        ends = self.indptr[keys + 1]
        counts = ends - starts
        total = int(counts.sum())
        if total == 0:
            return np.empty(0, dtype=np.int64)
        # Expand each [start, end) range without a Python loop.
        idx = np.repeat(starts, counts) + (
            np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
        )
        return self.order[idx]


def _csr_by_key(keys: np.ndarray, n_keys: int) -> _Index:
    valid = keys >= 0
    k = keys[valid]
    rows = np.flatnonzero(valid)
    order = np.argsort(k, kind="stable")
    counts = np.bincount(k[order], minlength=n_keys)
    indptr = np.zeros(n_keys + 1, dtype=np.int64)
    np.cumsum(counts, out=indptr[1:])
    return _Index(indptr, rows[order])


# --------------------------------------------------------------------------
# Building a graph from the database
# --------------------------------------------------------------------------

_LINK_SQL = """
SELECT link_id AS edge_id, link_id, from_node, to_node, length_m, form,
       'downstream' AS mode
FROM link
{where}
ORDER BY link_id
"""

_SEA_SQL = """
-- §10's routes, as edges of the one graph. `mode: both` because open water has no
-- downstream; `form: sea` so a reader can tell a route from a river at a glance. An
-- entry with no mouth of its own gets a `rewt:sea-node/` id so the network is
-- connected rather than a scatter of pairs.
-- A BLOCKED MOUTH ATTACHES ONLY IF IT IS AT THE COAST. `sea_entry.coast_m` is its
-- distance to Mean High Water. A channel ending at the sea wall discharges through it;
-- one ending well inland is drained by the network, and attaching it to a route would
-- show the water leaving where it does not — Stephen's four cases separate at 4 m, 43 m
-- and 4 m attaching against 210 m not.
--
-- The ROUTE IS NEVER REMOVED, only the attachment withheld: the sea network stays whole
-- and connected, and the mouth simply is not a way into it. Dropping the link instead
-- would tear the network apart at exactly the places §10 found hardest to serve.
--
-- A mouth the sea took (`kind = 'terminus'`) attaches whatever its distance: it reached
-- tidal water, which is the survey's own statement that the sea is already there.
SELECT s.link_id AS edge_id, s.link_id,
       coalesce(
         CASE WHEN ef.is_terminus = 1 OR ef.coast_m <= {max_coast_m}
              THEN s.from_node END,
         'rewt:sea-node/' || CAST(s.from_entry AS VARCHAR)) AS from_node,
       coalesce(
         CASE WHEN et.is_terminus = 1 OR et.coast_m <= {max_coast_m}
              THEN s.to_node END,
         'rewt:sea-node/' || CAST(s.to_entry AS VARCHAR)) AS to_node,
       s.length_m, 'sea' AS form, 'both' AS mode
FROM sea_link s
-- JOINED ON THE MOUTH, AND PRE-AGGREGATED. `entry_id` is not unique in `sea_entry`:
-- several mouths can snap to one cell of open water, so joining on it multiplied 4,183
-- routes into 35,707 and every count downstream with them. A node is the thing that
-- either attaches or does not, so it is the thing to join on — and the aggregate makes
-- that one row even where a node was offered more than one entry.
LEFT JOIN (SELECT node_id,
                  min(coast_m) AS coast_m,
                  max(CASE WHEN kind = 'terminus' THEN 1 ELSE 0 END) AS is_terminus
           FROM sea_entry WHERE node_id IS NOT NULL GROUP BY node_id) ef
       ON ef.node_id = s.from_node
LEFT JOIN (SELECT node_id,
                  min(coast_m) AS coast_m,
                  max(CASE WHEN kind = 'terminus' THEN 1 ELSE 0 END) AS is_terminus
           FROM sea_entry WHERE node_id IS NOT NULL GROUP BY node_id) et
       ON et.node_id = s.to_node
ORDER BY s.link_id
"""

_EDGE_SQL = """
SELECT edge_id, link_id, from_node, to_node, length_m, form, mode
FROM edge
{where}
ORDER BY edge_id
"""


def load(table: str = "edge", where: str = "") -> Graph:
    """Read a graph out of `edge`, `link`, or `edge+sea` — the completed routing graph.

    `link` is the right table for the census, which runs before any repair. `edge` is
    the right table for everything after it. There is no third graph, because two graphs
    over one geometry cannot be reconciled after the fact (§8).

    **`edge+sea` is not a third graph. It is the one graph with the half that was built
    and never attached.** `schema.py` has always said a sea route must be a link in one
    network rather than a second graph — and `sea_link` had 4,183 rows of which none were
    in `edge`, so the network's seaward half existed, was published, was drawn, and could
    not be traversed. 541 of the 693 coastal mouths the sea could not take already carry
    a sea route on their own node id, so what was missing was admission and not geometry.
    The union happens here because `edge` is written by `repair`, which runs long before
    the sea network exists: `sea` reads `edge`, so `edge` cannot wait for it without a
    cycle. Composing at read time is the only place both halves are available.

    A sea route runs `mode: both`: open water has no downstream, and a mouth may be
    reached from either side of it. An entry that is not a mouth gets a node of its own
    (`rewt.ids.sea_node`) so the sea network is internally connected rather than a set of
    disjoint pairs.
    """
    if table not in ("edge", "link", "edge+sea"):
        raise ValueError(f"no graph over {table!r}")
    if table == "edge+sea":
        # One query, so the two halves cannot be read from different states of the
        # database, and so the node index below covers both without special-casing.
        sql = (
            "SELECT * FROM (" + _EDGE_SQL.format(where=f"WHERE {where}" if where else "")
            .replace("ORDER BY edge_id", "") + ") "
            "UNION ALL SELECT * FROM ("
            + _SEA_SQL.format(max_coast_m=float(config.param("sea.max_coast_m")))
              .replace("ORDER BY s.link_id", "") + ") "
            "ORDER BY edge_id"
        )
    else:
        sql = (_EDGE_SQL if table == "edge" else _LINK_SQL).format(
            where=f"WHERE {where}" if where else ""
        )
    frame = db.df(sql)
    node_ids = db.df("SELECT node_id FROM node ORDER BY node_id")["node_id"].tolist()

    # A repair may have created nodes; take the union so no edge dangles. Set
    # arithmetic, not numpy's: numpy sorts an object array element by element in
    # Python, and on 400,000 identifier strings that is minutes, not milliseconds.
    known = set(node_ids)
    extra = sorted((set(frame["from_node"]) | set(frame["to_node"])) - known)
    node_ids = np.asarray(node_ids + extra, dtype=object)
    node_index = {nid: i for i, nid in enumerate(node_ids)}

    return Graph(
        edge_ids=frame["edge_id"].to_numpy(),
        link_ids=frame["link_id"].to_numpy(),
        u=frame["from_node"].map(node_index).to_numpy(dtype=np.int64),
        v=frame["to_node"].map(node_index).to_numpy(dtype=np.int64),
        length=frame["length_m"].to_numpy(dtype=float),
        form=frame["form"].to_numpy(),
        mode=frame["mode"].to_numpy(),
        nodes=node_ids,
        node_index=node_index,
    )
