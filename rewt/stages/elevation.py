"""Stage: a 1 m elevation at every node, from the three registered LiDAR services.

**D-085**, and the reason it is a stage rather than the script it began as. A step that
only runs when a person remembers to run it is not part of the build (AGENTS.md), and
the sweep spent a day as exactly that — which is what
`test_every_stage_1_source_is_read_by_a_stage_or_says_why_not` was saying when it named
`scottish_gov_lidar_dtm` as declared for Stage 1 and read by nothing. The test was right
and the answer was never a declaration.

**What it is for.** PLAN.md §5 measures Terrain 50 as saying nothing at all about 24.3%
of links, 82.3% of canals and 91.8% of lakes: it screens the uplands, where the network
is least broken, and is silent on the levels, where it is most. A 1 m surface with
±0.15 m error against Terrain 50's ~4 m should move most of that mute band into a band
that answers. **That is the claim to test, as a distribution against the Terrain 50 one,
and not to assert** — and if the mute share barely moves, the honest reading is that the
levels are genuinely flat rather than that the instrument failed.

**The node is the unit.** 197,734 nodes against 195,568 links with two ends each, so a
node value discriminates every link incident on it: 197,734 samples rather than 391,136.

**Three services, three fetch units, and that is a property of the services** (D-086).
England is a per-node 80 m window over a WCS — 25.4 KB and 0.45 s, against 9.44 MB and
2.16 s for the kilometre square containing it, because the median square holds two
nodes. Wales has no such choice: the NRW catalogue serves whole kilometre tiles, so a
tile is fetched and every node in it is sampled before it is discarded. Scotland has no
WCS at all, so it is a per-node WMS point query, one layer at a time.

**Nothing is cached as raster.** 380 GB of tiles to extract 197,734 numbers is not a
defensible use of the disk, and the durable artefact is the elevation. `data/raw/` keeps
the readings themselves and a per-tile manifest — source, request, digest, the
publisher's own survey date where it gives one — so any reading can be re-derived and
verified against what was actually sampled.

**Every service lies about absence, and each lies differently.** The English WCS asked
for Welsh ground returns HTTP 200 and a structurally valid GeoTIFF of 0.0 m with no
nodata declared — measured at a node where the Welsh tile reads 498.10 m. EMODnet, for
the router's purposes, returns 100% exact 0.0 outside its coverage. The Scottish WMS has
two shapes, an empty feature list outside a layer's extent and `-9999` inside it with no
data, and a single-layer probe shows only the first. So **coverage is decided by country
and then confirmed by the reading**, never inferred from nodata, and a refusal is a null
with a reason rather than a zero.
"""

from __future__ import annotations

import json

from .. import config, db, elevation, paths, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Report, log

NODE_ELEVATION = artefact("node_elevation")
READINGS = paths.RAW / "node_elevation.jsonl"


@PIPELINE.stage(
    "elevation",
    "a 1 m elevation at every node, as a direction discriminator (D-085)",
    reads=["node", "node_basin"],
    writes=["node_elevation"],
    params=["terrain"],
    sources=["ea_lidar_composite_dtm_1m", "nrw_lidar_dtm_1m", "scottish_gov_lidar_dtm"],
)
def run() -> dict:
    con = db.get()
    if not READINGS.exists():
        raise StageError(
            f"{paths.rel(READINGS)} does not exist. The sweep is an acquisition: it "
            "makes about 105,000 requests to three public services and takes hours, so "
            "it is not re-run by every build. Run `rewt sweep` to acquire it."
        )

    rows, seen = [], set()
    for line in READINGS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["node_id"] in seen:      # the file is append-only and resumable
            continue
        seen.add(r["node_id"])
        rows.append({
            "node_id": r["node_id"],
            "elevation_m": r.get("elev"),
            "source_id": r.get("src"),
            "layer": r.get("layer"),
            "country": r.get("country"),
            "why_not": (r.get("why") or None) if r.get("elev") is None else None,
        })
    if not rows:
        raise StageError(f"{paths.rel(READINGS)} holds no readings")

    import pandas as pd

    schema.create("node_elevation")
    with db.registered("_elev_in", pd.DataFrame(rows)):
        con.execute(
            "INSERT INTO node_elevation "
            "SELECT node_id, elevation_m, source_id, layer, country, why_not "
            "FROM _elev_in ORDER BY node_id"
        )

    # WHAT THE SWEEP DOES NOT COVER IS PART OF THE RESULT, not a footnote. Reported
    # against the node population rather than as a share of what was attempted, because
    # a share of what was attempted cannot see what was never attempted.
    total, with_value = con.execute(
        "SELECT count(*), count(elevation_m) FROM node_elevation"
    ).fetchone()
    in_scope = con.execute(
        "SELECT count(*) FROM node_basin WHERE basin_in_scope"
    ).fetchone()[0]
    covered = con.execute(
        "SELECT count(*) FROM node_basin nb JOIN node_elevation e USING (node_id) "
        "WHERE nb.basin_in_scope AND e.elevation_m IS NOT NULL"
    ).fetchone()[0]

    by_country = con.execute(
        "SELECT country, count(*), count(elevation_m) FROM node_elevation "
        "GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    log.table(
        "readings held, by country",
        ["country", "attempted", "with a value"],
        [(c or "—", f"{a:,}", f"{v:,}") for c, a, v in by_country],
    )
    log.detail(
        f"    {covered:,} of {in_scope:,} in-scope nodes carry a 1 m elevation "
        f"({100 * covered / max(in_scope, 1):.1f}%); the remainder are outside England "
        "and Wales, or on ground no service holds"
    )

    refused = con.execute(
        "SELECT why_not, count(*) FROM node_elevation WHERE elevation_m IS NULL "
        "AND why_not IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
    ).fetchall()
    for why, n in refused:
        log.detail(f"    {n:,} refused: {why}")

    report = Report("elevation")
    report.add("nodes", {"with_reading": total, "with_value": with_value,
                         "in_scope": in_scope, "in_scope_with_value": covered})
    report.add("by_country", {c or "unknown": {"attempted": a, "with_value": v}
                              for c, a, v in by_country})
    report.write_json(paths.PUBLISHED / "audit" / "elevation.json")

    log.done(f"{with_value:,} nodes carry a 1 m elevation of {total:,} attempted")
    return {"node_elevation": total}
