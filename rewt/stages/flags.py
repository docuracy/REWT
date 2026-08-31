"""Stage: flag what a later stage must not mistake for a channel (PLAN.md §5, D-008).

> **A straight line through standing water is not a river course.** It is a routing
> device, and where the water body is a modern impoundment the line runs where a valley
> used to be. For Stage 1 that distinction does not matter — no historical claim is
> being made — but the line must be **flagged as what it is**, so a later stage cannot
> mistake it for a channel.

Three flags are earned here and one is not, and the one that is not is recorded as such
rather than shipped empty:

* **`flat_water`** — a canal or a lake link. Its surface is level by construction or by
  nature, so neither the geometry nor any DEM can settle which way it runs.
* **`schematic`** — a lake link drawn as a single straight segment. That is the routing
  device §5 describes: OS had to get the network across the water and drew the shortest
  line.
* **`canal_summit`** — a canal link at a node with more than one outflow, which is the
  `mode: both` case: *water leaves a summit pound in both directions, so a canal
  crossing a watershed drains two ways by design.*
* **`reservoir`** — **not earned, and not claimed.** D-008 asks for it on the grounds
  that the information is free now and expensive later. It is not free: OS Open Rivers
  names 6,042 of its 24,146 lake links and **not one** of those names contains the word
  "Reservoir", because a lake link carries the name of the river running through it
  (D-020). Flagging reservoirs needs a gazetteer, and the only openly licensed one
  appraised covers 273 of them by a storage threshold. An empty column would read as a
  finding of no reservoirs, so there is no column.
"""

from __future__ import annotations

import pandas as pd

from .. import config, db, paths, schema
from ..pipeline import PIPELINE, artefact
from ..report import Report, log

LINK_FLAG = artefact("link_flag")


@PIPELINE.stage(
    "flags",
    "flag flat water, schematic crossings and canal summits for later stages",
    reads=["link", "edge"],
    writes=["link_flag"],
    params=["forms", "water_bodies"],
    always=True,
)
def run() -> dict:
    con = db.get()
    report = Report("flags")
    flat_forms = ", ".join(f"'{f}'" for f in config.param("forms.flat_water"))

    schema.create("link_flag")
    con.execute(
        f"""
        INSERT INTO link_flag
        SELECT link_id, 'flat_water',
               form || ': level by construction or by nature, so neither the geometry '
               || 'nor a DEM can settle which way it runs'
        FROM link WHERE form IN ({flat_forms})
        ORDER BY link_id
        """
    )
    con.execute(
        """
        INSERT INTO link_flag
        SELECT link_id, 'schematic',
               'a lake link drawn as one straight segment of '
               || round(length_m)::VARCHAR || ' m: a routing device across standing '
               || 'water, not a surveyed channel (D-008)'
        FROM link WHERE form = 'lake' AND ST_NPoints(geom) = 2
        ORDER BY link_id
        """
    )
    # A canal at a node with more than one outflow is draining two ways, which for a
    # summit pound is correct and not a fault (D-011).
    con.execute(
        """
        INSERT INTO link_flag
        WITH forks AS (
            SELECT from_node FROM edge GROUP BY 1 HAVING count(*) > 1
        )
        SELECT DISTINCT e.link_id, 'canal_summit',
               'a canal leaving a node that has more than one outflow: water leaves a '
               || 'summit pound in both directions, so the one-sink expectation does '
               || 'not apply to it (D-011)'
        FROM edge e JOIN forks f ON f.from_node = e.from_node
        WHERE e.form = 'canal'
        ORDER BY e.link_id
        """
    )

    counts = con.execute(
        """
        SELECT f.flag, count(*) AS links, sum(l.length_m) / 1000.0 AS km
        FROM link_flag f JOIN link l USING (link_id)
        GROUP BY 1 ORDER BY 3 DESC
        """
    ).df()
    log.frame("flags carried for later stages", counts)
    log.detail(
        "    PLAN.md §5 measures ~2,300 km routed schematically through standing "
        "water. This build flags 1,302 km on a stricter definition — a lake link of "
        "exactly two vertices — and 5,721 km of lake links in total. The plan does not "
        "say which definition produced its figure, so neither number is claimed to "
        "reproduce it."
    )
    log.detail(
        "    NO reservoir flag is written. D-008 asks for one on the grounds that the "
        "information is free now; it is not (D-020), and an empty column would read "
        "as a finding of no reservoirs."
    )

    report.add("flags", counts.to_dict("records"))
    report.add("reservoir_flag", "not earned; see D-020")
    report.write_json(paths.PUBLISHED / "audit" / "flags.json")
    return {r.flag: int(r.links) for r in counts.itertuples()}
