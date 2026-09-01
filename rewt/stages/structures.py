"""Stage: the works that connect the network but are not drawn in it (D-011, D-030).

> **Do not require a canal to reach the sea down its own channel.** It reaches it
> through a structure — a lock, an overflow weir, a feeder — that the survey does not
> draw. Connect it to the receiving watercourse **where the structure actually is**.

Until now "where the structure actually is" had to be guessed at as the nearest approach
between two waters, and the canal connectors say so in their own evidence: *the position
is the nearest approach, not a surveyed structure.* This stage loads 6,225 located
structures so that the guess can at least be corroborated.

**They are evidence, not coordinates.** Measured against OS Open Rivers issue 2026-04,
a Canal & River Trust lock sits a median 11.5 m from the nearest OS watercourse, but the
90th percentile is 108 m and the maximum 298 m, and for 28% of locks the nearest OS link
is not even a canal. Two independent products do not coincide. So a structure here says
*something was built near this place*, which is exactly what D-011 asks for, and it is
never used to move a connector's geometry — that keeps coming from the network, where it
is precise.

**Absence is not evidence of absence.** The Trust manages 101 named waterways, not all
navigable water in England and Wales; the Environment Agency, the Broads Authority and
several independent trusts hold the rest.
"""

from __future__ import annotations

import json

import pandas as pd
from pyproj import Transformer

from .. import acquire, config, db, paths
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Report, log

RAW_CRT = artefact("raw_crt_structures", "dir", "data/raw/crt_structures/extracted")
STRUCTURE = artefact("structure")


@PIPELINE.stage(
    "acquire_structures",
    "fetch the Canal & River Trust's navigation structures",
    writes=["raw_crt_structures"],
    sources=["crt_navigation_structures"],
)
def acquire_run() -> dict:
    acq = acquire.fetch("crt_navigation_structures")
    return {"issue": acq.issue, "sha256": acq.sha256, "layers": acq.members}


@PIPELINE.stage(
    "structures",
    "load the located locks, weirs, aqueducts and culverts",
    reads=["raw_crt_structures"],
    writes=["structure"],
    params=["crs"],
    sources=["crt_navigation_structures"],
)
def run() -> dict:
    src = config.source("crt_navigation_structures")
    working = config.param("crs.working")
    declared = src.get("crs", default="EPSG:4326")
    to_working = Transformer.from_crs(declared, working, always_xy=True)

    rows: list[dict] = []
    for name in src.require("arcgis", "layers"):
        path = src.dir / "extracted" / f"{name}.geojson"
        if not path.exists():
            raise StageError(f"{paths.rel(path)} is missing; re-acquire the source")
        doc = json.loads(path.read_text(encoding="utf-8"))
        for feature in doc.get("features", []):
            geom = feature.get("geometry")
            if not geom or geom.get("type") != "Point":
                continue
            x, y = geom["coordinates"]
            easting, northing = to_working.transform(x, y)
            props = feature.get("properties", {})
            rows.append(
                {
                    "kind": name,
                    "reference": props.get("sap_func_loc"),
                    "description": props.get("sap_description"),
                    "waterway": props.get("waterway_name"),
                    "easting": easting,
                    "northing": northing,
                }
            )
    if not rows:
        raise StageError("the structures source yielded no point features")

    frame = pd.DataFrame(rows).sort_values(
        ["kind", "reference", "easting"], kind="stable"
    ).reset_index(drop=True)

    con = db.get()
    con.execute("DROP TABLE IF EXISTS structure")
    with db.registered("_struct_in", frame):
        con.execute(
            """
            CREATE TABLE structure AS
            SELECT kind, reference, description, waterway, easting, northing,
                   ST_Point(easting, northing) AS geom,
                   'crt_navigation_structures' AS source_id
            FROM _struct_in ORDER BY kind, reference
            """
        )

    counts = con.execute(
        "SELECT kind, count(*) FROM structure GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    log.table("located structures", ["kind", "features"], counts)

    # How far are they from the survey's own lines? Reported every build, because the
    # answer is what licenses using them as evidence rather than as coordinates.
    offset = con.execute(
        """
        WITH nearest AS (
            SELECT s.reference,
                   min(ST_Distance(l.geom, s.geom)) AS gap_m
            FROM structure s JOIN link l
              ON ST_XMax(l.geom) >= s.easting - 300 AND ST_XMin(l.geom) <= s.easting + 300
             AND ST_YMax(l.geom) >= s.northing - 300 AND ST_YMin(l.geom) <= s.northing + 300
            WHERE s.kind = 'locks'
              AND ST_Distance(l.geom, s.geom) <= 300
            GROUP BY 1
        )
        SELECT count(*), median(gap_m), quantile_cont(gap_m, 0.9), max(gap_m)
        FROM nearest
        """
    ).fetchone()
    log.detail(
        f"    of {counts[0][1] if counts else 0:,} structures, locks sit a median "
        f"{offset[1]:.1f} m from the nearest OS watercourse, 90th percentile "
        f"{offset[2]:.1f} m, max {offset[3]:.1f} m ({offset[0]:,} within 300 m). "
        "That is why they are evidence and not coordinates (D-030)."
    )

    report = Report("structures")
    report.add("counts", {k: int(v) for k, v in counts})
    report.add("lock_offset_m", {
        "measured": int(offset[0]), "median": round(float(offset[1]), 2),
        "p90": round(float(offset[2]), 2), "max": round(float(offset[3]), 2),
    })
    report.write_json(paths.PUBLISHED / "audit" / "structures.json")
    return {k: int(v) for k, v in counts}
