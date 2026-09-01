"""Stage: the deliverable (PLAN.md §7).

**Stage 1 is finished not when the network is good but when someone else can pick it
up.** A published directory, rebuilt from scratch by the same one command:

* **the network**, GeoPackage, EPSG:27700, links and nodes as separate layers. Every
  link carries the publisher id, the oriented `from_node`/`to_node`, name, length,
  form, its basin, whether it reaches tidal water, and an `origin` saying whether it is
  survey, connector or skeleton. **A consumer must be able to tell what came from
  Ordnance Survey and what this project added, without reading the code.**
* **the corrections**, as their own layer or file, so the difference between the survey
  and the published network is a thing you can open.
* **the audit**, machine-readable and human-readable, per basin and national.
* **the attribution**, carrying every source's required statement in full.

And the licence gate, which is not a formality: **the exporter refuses to write a
feature whose source is not openly licensed.** Keep that check; do not work around it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
import shapely

from .. import acquire, config, db, paths
from ..pipeline import PIPELINE, StageError, artefact
from ..report import log, write_text

PUBLISHED = artefact("published", "dir", "published")

NETWORK_GPKG = paths.PUBLISHED / "rewt_stage1_network.gpkg"
CORRECTIONS_GPKG = paths.PUBLISHED / "rewt_stage1_corrections.gpkg"


def _licence_gate(source_ids) -> None:
    """Refuse to write a feature whose source is not openly licensed."""
    for source_id in sorted({s for s in source_ids if s and s != "rewt"}):
        config.source(source_id).require_redistributable()


@PIPELINE.stage(
    "export",
    "write the published network, the corrections, the audit and the attribution",
    reads=["edge", "link", "node", "basin", "link_scope", "link_reach", "correction"],
    writes=["published"],
    params=["crs"],
    always=True,
)
def run() -> dict:
    con = db.get()
    working = config.param("crs.working")
    export_crs = config.param("crs.export")
    paths.PUBLISHED.mkdir(parents=True, exist_ok=True)

    # GDAL stamps a GeoPackage with the time it was written, which makes two builds
    # from one set of inputs differ by eighteen bytes. Pin it to the newest input's
    # acquisition, so the stamp still says something true — this is the edition the
    # file describes — while being a function of the inputs rather than of the clock.
    os.environ["OGR_CURRENT_DATE"] = _input_date()

    # ---------------------------------------------------------------- links
    links = con.execute(
        """
        WITH all_links AS (
            SELECT link_id, publisher_id, source_id, origin, form, name, name_alt,
                   from_node, to_node, length_m, geom, NULL AS parent_link_id
            FROM link
            UNION ALL
            SELECT link_id, publisher_id, source_id, origin, form, name, name_alt,
                   from_node, to_node, length_m, geom, parent_link_id
            FROM repair_link
        )
        SELECT a.link_id,
               a.publisher_id,
               a.source_id,
               a.origin,
               a.form,
               a.name,
               a.name_alt,
               -- the ORIENTED routing graph's sense, which is what a consumer wants
               coalesce(e.from_node, a.from_node) AS from_node,
               coalesce(e.to_node,   a.to_node)   AS to_node,
               a.length_m,
               s.basin_id,
               coalesce(s.in_scope, false)        AS in_scope,
               s.scope_rule,
               coalesce(r.reaches_tidal, false)   AS reaches_tidal,
               r.seed_node,
               coalesce(e.reversed, false)        AS routing_reversed,
               e.reversed_by                      AS reversed_by_correction,
               coalesce(e.mode, 'downstream')     AS routing_mode,
               ret.link_id IS NOT NULL            AS retired,
               ret.reason                         AS retired_reason,
               ret.superseded_by,
               a.parent_link_id,
               ST_AsWKB(a.geom)                   AS wkb
        FROM all_links a
        LEFT JOIN edge e        ON e.link_id  = a.link_id
        LEFT JOIN link_scope s  ON s.link_id  = a.link_id
        LEFT JOIN link_reach r  ON r.link_id  = a.link_id
        LEFT JOIN retirement ret ON ret.link_id = a.link_id
        ORDER BY a.link_id
        """
    ).df()
    _licence_gate(links["source_id"].unique())

    link_gdf = gpd.GeoDataFrame(
        links.drop(columns=["wkb"]),
        geometry=[shapely.from_wkb(bytes(w)) for w in links["wkb"]],
        crs=working,
    )
    if export_crs != working:
        link_gdf = link_gdf.to_crs(export_crs)

    # ---------------------------------------------------------------- nodes
    nodes = con.execute(
        """
        WITH all_nodes AS (
            SELECT node_id, publisher_id, source_id, origin, category, terminus,
                   easting, northing, geom FROM node
            UNION ALL
            SELECT node_id, publisher_id, source_id, origin, category, terminus,
                   easting, northing, geom FROM repair_node
        )
        SELECT n.node_id, n.publisher_id, n.source_id, n.origin, n.category,
               n.terminus, n.easting, n.northing, nb.basin_id,
               coalesce(nb.basin_in_scope, false) AS basin_in_scope,
               sd.node_id IS NOT NULL AS is_seed,
               ST_AsWKB(n.geom) AS wkb
        FROM all_nodes n
        LEFT JOIN node_basin nb ON nb.node_id = n.node_id
        LEFT JOIN seed sd ON sd.node_id = n.node_id
        ORDER BY n.node_id
        """
    ).df()
    _licence_gate(nodes["source_id"].unique())
    node_gdf = gpd.GeoDataFrame(
        nodes.drop(columns=["wkb"]),
        geometry=[shapely.from_wkb(bytes(w)) for w in nodes["wkb"]],
        crs=working,
    )
    if export_crs != working:
        node_gdf = node_gdf.to_crs(export_crs)

    # --------------------------------------------------------------- basins
    basins = con.execute(
        "SELECT basin_id, label, outlet_node, area_km2, in_scope, scope_reason, "
        "england_wales_area_km2, provisional, ST_AsWKB(geom) AS wkb FROM basin "
        "ORDER BY basin_id"
    ).df()
    basin_gdf = gpd.GeoDataFrame(
        basins.drop(columns=["wkb"]),
        geometry=[shapely.from_wkb(bytes(w)) for w in basins["wkb"]],
        crs=working,
    )
    if export_crs != working:
        basin_gdf = basin_gdf.to_crs(export_crs)

    NETWORK_GPKG.unlink(missing_ok=True)
    link_gdf.to_file(NETWORK_GPKG, layer="link", driver="GPKG")
    node_gdf.to_file(NETWORK_GPKG, layer="node", driver="GPKG")
    basin_gdf.to_file(NETWORK_GPKG, layer="basin", driver="GPKG")

    # ---------------------------------------------------------- corrections
    # Their own file, so the difference between the survey and the published network
    # is a thing you can open.
    # A junction, a reversal, an exclusion and a mode act on a feature that already
    # exists, so they carry no geometry of their own — and were therefore published
    # with no position at all, which put 332 of 1,246 judgements nowhere on a map.
    # AGENTS.md asks for a coordinate with EVERY finding. The midpoint of the link a
    # judgement acts on is that coordinate, and it is marked as derived so it is never
    # read as a surveyed position.
    con.execute(
        """
        UPDATE correction SET
            easting = coalesce(easting, (
                SELECT ST_X(ST_Centroid(l.geom)) FROM link l
                WHERE l.link_id = correction.resolved_to
                   OR l.publisher_id = correction.subject LIMIT 1)),
            northing = coalesce(northing, (
                SELECT ST_Y(ST_Centroid(l.geom)) FROM link l
                WHERE l.link_id = correction.resolved_to
                   OR l.publisher_id = correction.subject LIMIT 1))
        WHERE easting IS NULL OR northing IS NULL
        """
    )
    # A junction acts on a NODE, so its subject is a node's publisher id and the link
    # lookup above finds nothing for it. Ten judgements were left unplaced by that.
    con.execute(
        """
        UPDATE correction SET
            easting = coalesce(easting, (
                SELECT n.easting FROM node n
                WHERE n.node_id = correction.resolved_to
                   OR n.publisher_id = correction.subject LIMIT 1)),
            northing = coalesce(northing, (
                SELECT n.northing FROM node n
                WHERE n.node_id = correction.resolved_to
                   OR n.publisher_id = correction.subject LIMIT 1))
        WHERE easting IS NULL OR northing IS NULL
        """
    )
    placed = con.execute(
        "SELECT count(*) FILTER (WHERE easting IS NOT NULL), count(*) FROM correction"
    ).fetchone()
    log.detail(f"    {placed[0]:,} of {placed[1]:,} judgements carry a position")

    corrections = con.execute(
        "SELECT correction_id, kind, subject, resolved_to, applied, skip_reason, "
        "reason, evidence, detail, author, dated, source_file, source_row, "
        "easting, northing, "
        "CASE WHEN geom IS NULL THEN NULL ELSE ST_AsWKB(geom) END AS wkb "
        "FROM correction ORDER BY kind, source_file, source_row"
    ).df()
    CORRECTIONS_GPKG.unlink(missing_ok=True)
    # An empty CSV left behind by an earlier build is worse than no file: it says
    # there are no corrections while the GeoPackage beside it holds 1,246.
    (paths.PUBLISHED / "corrections.csv").unlink(missing_ok=True)
    if len(corrections):
        # A junction, a reversal and an exclusion have no geometry of their own — they
        # act on features that already exist — so they are published at the place they
        # act on. `pd.isna` rather than `is None`: DuckDB returns pandas NA here, which
        # is not None and does not convert to bytes.
        geoms = [
            shapely.from_wkb(bytes(w)) if not pd.isna(w)
            else (shapely.Point(e, n) if pd.notna(e) else None)
            for w, e, n in zip(corrections["wkb"], corrections["easting"], corrections["northing"])
        ]
        corr_gdf = gpd.GeoDataFrame(
            corrections.drop(columns=["wkb"]), geometry=geoms, crs=working
        )
        if export_crs != working:
            corr_gdf = corr_gdf.to_crs(export_crs)
        corr_gdf.to_file(CORRECTIONS_GPKG, layer="correction", driver="GPKG")
    else:
        # An empty correction set is a state worth publishing explicitly rather than
        # by the absence of a file: it says the audit has not yet been adjudicated.
        corrections.to_csv(paths.PUBLISHED / "corrections.csv", index=False)

    # --------------------------------------------------------- attribution
    _write_provenance()
    _write_attribution()
    _write_readme(link_gdf, node_gdf, basin_gdf, len(corrections))

    survey_km = float(links.loc[links["origin"] == "survey", "length_m"].sum()) / 1000.0
    ours_km = float(links.loc[links["origin"] != "survey", "length_m"].sum()) / 1000.0
    log.table(
        "published — what came from Ordnance Survey and what this project added",
        ["origin", "links", "km"],
        [
            (origin, int((links["origin"] == origin).sum()),
             round(float(links.loc[links["origin"] == origin, "length_m"].sum()) / 1000.0, 1))
            for origin in sorted(links["origin"].dropna().unique())
        ],
    )
    log.done(f"{paths.rel(NETWORK_GPKG)}  ({len(link_gdf):,} links, {len(node_gdf):,} nodes)")

    return {
        "links": len(link_gdf),
        "nodes": len(node_gdf),
        "basins": len(basin_gdf),
        "corrections": len(corrections),
        "survey_km": round(survey_km, 1),
        "added_km": round(ours_km, 1),
    }


def _input_date() -> str:
    """The newest acquisition date among the inputs, as GDAL wants it."""
    stamps = [
        acquire.acquisition(src.id).acquired_at
        for src in config.sources()
        if acquire.acquisition(src.id)
    ]
    when = max(stamps) if stamps else "2026-01-01T00:00:00+00:00"
    return datetime.fromisoformat(when).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _write_provenance() -> None:
    """When this build ran, and from what.

    Everything else published is a function of the inputs, so that two builds from
    one set of inputs are byte-identical (§9). The one thing that cannot be is when
    the build happened, so it lives here alone and nowhere else.
    """
    doc = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_fingerprint": config.config_fingerprint(),
        "sources": {},
    }
    # The publisher's own recorded date for the network, which is more precise than
    # the API's month and is what conf/sources.yml means by "record which issue".
    issued = db.query(
        "SELECT detail FROM stage_run WHERE stage = 'load' AND status = 'ok'"
    )
    issued = issued[0] if issued else None
    if issued and issued[0]:
        try:
            doc["os_open_rivers_written"] = json.loads(issued[0]).get("issued_on")
        except (ValueError, TypeError):
            pass
    for src in sorted(config.sources(), key=lambda s: s.id):
        acq = acquire.acquisition(src.id)
        if acq:
            doc["sources"][src.id] = {
                "issue": acq.issue, "sha256": acq.sha256,
                "acquired_at": acq.acquired_at, "file": acq.file_name,
            }
    (paths.PUBLISHED / "provenance.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_attribution() -> None:
    """Every source's required statement, in full.

    **Provenance travels as a pointer.** Wherever a short attribution appears, it may
    never attribute less than `conf/sources.yml` does — so this file is generated from
    that file and from nothing else.
    """
    lines = [
        "# Attribution",
        "",
        "Generated from `conf/sources.yml`. A short attribution appearing anywhere else",
        "may never attribute less than this does.",
        "",
    ]
    for src in sorted(config.sources(), key=lambda s: s.id):
        acq = acquire.acquisition(src.id)
        lines += [
            f"## {src.title}",
            "",
            f"- Publisher: {src.publisher}",
            f"- Licence: {src.licence}",
            f"- Required attribution: **{src.attribution}**",
            f"- Access: {src.access}; redistribution: {src.redistribution}",
        ]
        if acq:
            lines.append(f"- Issue used: **{acq.issue}** (sha256 `{acq.sha256[:32]}…`)")
        else:
            lines.append("- Not acquired in this build")
        lines.append("")
    write_text(paths.PUBLISHED / "ATTRIBUTION.md", "\n".join(lines))


def _write_readme(links, nodes, basins, corrections: int) -> None:
    """What a stranger needs in order to tell survey from correction (§7, §9)."""
    con = db.get()
    reach = con.execute(
        """
        SELECT sum(CASE WHEN r.reaches_tidal THEN e.length_m ELSE 0 END) / 1000.0,
               sum(e.length_m) / 1000.0
        FROM edge e JOIN link_reach r USING (link_id)
        JOIN link_scope s USING (link_id) WHERE s.in_scope
        """
    ).fetchone()
    issues = {
        s.id: (acquire.acquisition(s.id).issue if acquire.acquisition(s.id) else None)
        for s in config.sources()
    }
    text = f"""# REWT Stage 1 — a traversable modern network

Built by `rewt build`, from an empty checkout, from the sources declared in
`conf/sources.yml`. Everything here is a function of those inputs and is byte-identical
between two builds from them; **when** this build ran is in `provenance.json`, which is
the only file that carries a clock.

**This is a modern river network and says nothing whatever about the past.** There are no
dates in it, no superseded channels, no evidence that anything existed when, and no water
moving through it. Everything of that kind belongs to later stages of the project, and a
consumer who needs any of it does not have it here.

## What is here

| file | what it is |
|---|---|
| `rewt_stage1_network.gpkg` | the network: `link`, `node` and `basin` layers, EPSG:27700 |
| `rewt_stage1_corrections.gpkg` | every curated judgement, so the difference from the survey is openable |
| `audit/audit.md`, `audit/audit.json` | the audit, per basin and national |
| `ATTRIBUTION.md` | every source's required statement, in full |

## Telling the survey from this project

Every link carries `origin`:

- **`survey`** — Ordnance Survey's own geometry, unmodified. `publisher_id` is theirs.
- **`connector`** — geometry this project added, where the survey draws no channel.
- **`skeleton`** — geometry derived from a water-body polygon's medial axis.

A link whose `routing_reversed` is true has the survey's geometry and the survey's
attributes exactly as published; only the routing graph runs the other way, and
`reversed_by_correction` names the judgement that did it. **No published attribute is
altered by a correction.**

A `retired` link is one this project superseded; `superseded_by` names what replaced it.
Nothing is deleted to correct it, so a reader can tell a correction from an omission.

## The numbers

- {len(links):,} links, {len(nodes):,} nodes, {len(basins):,} basins
- **{(reach[0] or 0) / (reach[1] or 1):.2%}** of in-scope length can reach tidal water
- {corrections:,} curated judgements

## Provenance

{chr(10).join(f'- {k}: issue {v}' if v else f'- {k}: not used in this build' for k, v in sorted(issues.items()))}

See `ATTRIBUTION.md`. Contains OS data © Crown Copyright and database rights 2026.
"""
    write_text(paths.PUBLISHED / "README.md", text)
