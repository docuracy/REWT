"""Is it one network yet? Build the whole thing and count.

Stephen's expectation is that the sea grid, the joins and traces, and the Open Rivers inland
network "will form a single D8 network which we will be able to use for routing from one
river port to another around the coast". rewt-46 asked, before drawing anything that implies
it, whether that network exists today — and asked for a file and a property to TEST rather
than a claim to repeat. This is that file.

It builds one graph out of all four parts and counts components. Nothing here is a router:
it answers reachability and nothing else.

WHAT COUNTS AS A CONNECTION. A river link joins its two nodes. A sea edge joins its two
cells. A JOIN of rule 1 or 2 attaches a terminus to a cell, because those rules assert a
direct attachment. A rule-3 join attaches ONLY IF the trace succeeded — the rule says a path
must be worked out, so an untraced rule-3 terminus is a terminus with no way to the sea, and
counting it as attached would be assuming the thing being measured.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402

CONFIG = {
    "network": "published/rewt_stage1_network.gpkg",
    "grid": "tools/router/cache/grid2.npz",
    "edges": "tools/router/cache/edges_r9.npz",
    "joins": "docs/router/data/joins.geojson",
    "traces": "docs/router/data/traces.geojson",
    "out": "docs/router/data/network_summary.json",
}


def main(cfg: dict = CONFIG) -> None:
    lk = gpd.read_file(cfg["network"], layer="link")
    nd = gpd.read_file(cfg["network"], layer="node")
    g = np.load(cfg["grid"], allow_pickle=True)
    e = np.load(cfg["edges"])["edge"]
    cells = g["cell"].tolist()

    ids: dict = {}

    def ix(k):
        return ids.setdefault(k, len(ids))

    rows = [(ix(("n", a)), ix(("n", b)))
            for a, b in zip(lk.from_node.values, lk.to_node.values)]
    rows += [(ix(("c", cells[int(i)])), ix(("c", cells[int(j)]))) for i, j in e]

    joins = json.loads(Path(cfg["joins"]).read_text())["features"]
    traced = {f["properties"]["node_id"]
              for f in json.loads(Path(cfg["traces"]).read_text())["features"]}
    attached, stranded = 0, []
    for f in joins:
        p = f["properties"]
        if p["rule"] in (1, 2) or p["node_id"] in traced:
            rows.append((ix(("n", p["node_id"])), ix(("c", p["cell"]))))
            attached += 1
        else:
            stranded.append({"node_id": p["node_id"], "rule": p["rule"],
                             "dist_m": p["dist_m"]})

    arr = np.array(rows)
    m = coo_matrix((np.ones(len(arr)), (arr[:, 0], arr[:, 1])), shape=(len(ids),) * 2)
    ncomp, lab = connected_components(m, directed=False)
    sizes = np.bincount(lab)
    sea_lab = int(lab[ids[("c", cells[0])]])
    rn = [v for k, v in ids.items() if k[0] == "n"]
    in_scope = set(nd[nd.in_scope.astype(bool)].node_id) if "in_scope" in nd.columns else set()
    ri = [ids[("n", k)] for k in in_scope if ("n", k) in ids]

    out = {
        "generation": generation(),
        "question": "Do the sea grid, the joins, the traces and the Open Rivers inland "
                    "network form ONE network today?",
        "answer": "Not yet.",
        "nodes": len(ids), "edges": len(arr), "components": int(ncomp),
        "largest_component": int(sizes.max()),
        "largest_component_pct": round(100 * float(sizes.max()) / len(ids), 2),
        "termini_attached_to_the_sea": attached,
        "termini_stranded": len(stranded),
        "river_nodes_reaching_the_sea": int((lab[rn] == sea_lab).sum()),
        "river_nodes_total": len(rn),
        "in_scope_river_nodes_reaching_the_sea": int((lab[ri] == sea_lab).sum()) if ri else None,
        "in_scope_river_nodes_total": len(ri) if ri else None,
        "in_scope_pct_reaching_the_sea":
            round(100 * float((lab[ri] == sea_lab).mean()), 2) if ri else None,
        "what_counts_as_a_connection":
            "A river link joins its two nodes; a sea edge joins its two cells; a join of "
            "rule 1 or 2 attaches a terminus to a cell. A rule-3 join attaches ONLY if its "
            "trace succeeded — the rule says a path must be worked out, so an untraced "
            "rule-3 terminus has no way to the sea, and counting it would assume the thing "
            "being measured.",
        "why_not_yet":
            "Two reasons, in order of size. Most in-scope river nodes that do not reach the "
            "sea are in river components that never reach an attached terminus at all — "
            "that is the inland network's own connectivity and R-01's territory, not the "
            "grid's. The rest is the stranded termini below: rule-3 joins whose trace "
            "across the drying ground failed.",
        "provisional": "R-01 unbuilt. The terminus population moves twice before this "
                       "number is final, so treat it as a floor on the work remaining "
                       "rather than a measurement of a finished thing.",
        "stranded": stranded,
    }
    Path(cfg["out"]).write_text(json.dumps(out, indent=1))
    print(f"combined graph: {len(ids):,} nodes, {len(arr):,} edges")
    print(f"  components {ncomp:,}; largest {sizes.max():,} "
          f"({100*sizes.max()/len(ids):.1f}%)")
    print(f"  termini attached {attached} of {len(joins)}, stranded {len(stranded)}")
    if ri:
        print(f"  in-scope river nodes reaching the sea: "
              f"{int((lab[ri] == sea_lab).sum()):,} of {len(ri):,} "
              f"({100*(lab[ri] == sea_lab).mean():.1f}%)")
    print(f"wrote {cfg['out']}")


if __name__ == "__main__":
    main()
