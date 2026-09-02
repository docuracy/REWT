"""Stage: apply the curated judgements, producing the one routing graph.

**Order matters and is not obvious.** In the earlier work, corrections applied before
the features they referenced existed reported "no such edge" and did nothing — silently
except for a log line, and including the single largest defect in the country. So each
class is applied where its targets exist, and **every skip is named**.

The three properties of these corrections, each learned expensively (PLAN.md §5):

* **A connector is defined by its geometry, not by any link id.** Each end is resolved
  onto the network, cutting a link where there is no node, because snapping to the
  nearest node left connectors attached to nothing 280 m and 377 m away and the stage
  counted them as successes.
* **A reversal moves no geometry and changes no published attribute** — only the
  routing graph. So a reversal is a row in `edge` and nothing else changes.
* **A junction adds nothing at all**: no geometry, no feature, no output row; the
  target is cut and the node merged. A connector cannot express that, because its two
  ends would coincide.

**Never delete a link to correct it.** A link cut in two is retired with a reason and
kept; the two children carry ids derived from the parent and from their own geometry.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import shapely

from .. import config, db, ids, paths, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Finding, Report, log

EDGE = artefact("edge")
REPAIR_LINK = artefact("repair_link")
REPAIR_NODE = artefact("repair_node")
RETIREMENT = artefact("retirement")


def _resolve_end(point: shapely.Geometry, snap_node_m: float, split_link_m: float) -> dict:
    """Put one end of a connector onto the network.

    Three outcomes, in this order of preference: it lands on an existing node; it lands
    on a link, which is then cut and a node created; or it lands on nothing, which is
    an error and not a silently accepted 280 m snap.
    """
    e, n = float(shapely.get_x(point)), float(shapely.get_y(point))
    node = db.query(
        f"""
        SELECT node_id, sqrt(pow(easting - {e}, 2) + pow(northing - {n}, 2)) AS d
        FROM node
        WHERE easting BETWEEN {e - snap_node_m} AND {e + snap_node_m}
          AND northing BETWEEN {n - snap_node_m} AND {n + snap_node_m}
        ORDER BY d, node_id LIMIT 1
        """
    )
    if node and node[0][1] <= snap_node_m:
        return {"kind": "node", "node_id": node[0][0], "distance_m": node[0][1]}

    link = db.query(
        f"""
        SELECT link_id, ST_Distance(geom, ST_Point({e}, {n})) AS d
        FROM link
        WHERE ST_XMax(geom) >= {e - split_link_m} AND ST_XMin(geom) <= {e + split_link_m}
          AND ST_YMax(geom) >= {n - split_link_m} AND ST_YMin(geom) <= {n + split_link_m}
        ORDER BY d, link_id LIMIT 1
        """
    )
    if link and link[0][1] <= split_link_m:
        return {"kind": "split", "link_id": link[0][0], "distance_m": link[0][1],
                "easting": e, "northing": n}
    return {
        "kind": "unresolved",
        "distance_m": link[0][1] if link else None,
        "easting": e,
        "northing": n,
    }


def _split_link(link_id: str, easting: float, northing: float) -> tuple[str, list[dict], list[dict]]:
    """Cut a link at a place, retiring the parent and creating two children.

    Returns the new node's id, the child link rows, and the retirement row. The parent
    is kept: **a retired link is how a reader tells a correction from an omission.**
    """
    row = db.query(
        "SELECT publisher_id, source_id, origin, form, name, name_alt, from_node, "
        "to_node, ST_AsWKB(geom) FROM link WHERE link_id = ?",
        [link_id],
    )
    if not row:
        raise StageError(f"cannot split {link_id}: it is not in the database")
    pub, source_id, origin, form, name, name_alt, from_node, to_node, wkb = row[0]
    line = shapely.from_wkb(bytes(wkb))
    point = shapely.Point(easting, northing)
    measure = shapely.line_locate_point(line, point)
    if measure <= 0 or measure >= shapely.length(line):
        raise StageError(
            f"cannot split {link_id} at its own end; that end is already a node"
        )
    snapped = shapely.line_interpolate_point(line, measure)
    upper = shapely.ops.substring(line, 0.0, measure) if hasattr(shapely, "ops") else None
    from shapely.ops import substring

    upper = substring(line, 0.0, measure)
    lower = substring(line, measure, shapely.length(line))

    node_id = ids.point(float(shapely.get_x(snapped)), float(shapely.get_y(snapped)))
    children = []
    for part, a, b in ((upper, from_node, node_id), (lower, node_id, to_node)):
        child_id = ids.derived(link_id, "link", shapely.to_wkt(part, rounding_precision=3))
        children.append(
            {
                "link_id": child_id,
                "publisher_id": pub,
                "source_id": source_id,
                "origin": origin,
                "form": form,
                "name": name,
                "name_alt": name_alt,
                "from_node": a,
                "to_node": b,
                "length_m": float(shapely.length(part)),
                "wkb": shapely.to_wkb(part),
                "parent_link_id": link_id,
            }
        )
    retirement = {
        "link_id": link_id,
        "reason": f"cut at {easting:.1f}, {northing:.1f} so a correction could attach there",
        "superseded_by": ",".join(c["link_id"] for c in children),
    }
    new_node = {
        "node_id": node_id,
        "publisher_id": None,
        "source_id": source_id,
        "origin": "split",
        "category": None,
        "terminus": "inland",
        "easting": float(shapely.get_x(snapped)),
        "northing": float(shapely.get_y(snapped)),
        "wkb": shapely.to_wkb(snapped),
    }
    return node_id, children, [retirement, new_node]


@PIPELINE.stage(
    "repair",
    "apply the curated judgements and build the one routing graph",
    reads=["link", "node", "correction", "terrain50_unconditioned", "structure"],
    writes=["edge", "repair_link", "repair_node", "retirement"],
    params=["repair", "forms", "connectors"],
    always=True,
)
def run() -> dict:
    p = config.params()
    con = db.get()
    report = Report("repair")

    snap_node_m = float(p("repair.connector_snap_node_m"))
    split_link_m = float(p("repair.connector_split_link_m"))
    max_rise_m = float(p("connectors.max_rise_m"))
    corroborate_m = float(p("connectors.structure_corroboration_m"))

    new_links: list[dict] = []
    new_nodes: list[dict] = []
    retirements: list[dict] = []
    applied: dict[str, bool] = {}
    skipped: dict[str, str] = {}
    reversed_by: dict[str, str] = {}
    mode_by: dict[str, str] = {}
    merged_nodes: dict[str, str] = {}

    corrections = db.df(
        """
        SELECT correction_id, kind, subject, resolved_to, reason, evidence, detail,
               source_file, source_row, easting, northing,
               CASE WHEN geom IS NULL THEN NULL ELSE ST_AsWKB(geom) END AS wkb
        FROM correction ORDER BY kind, source_file, source_row
        """
    )

    # ---------------------------------------------------------- reversals first
    # A reversal changes only the routing graph, so it can be resolved before any
    # geometry exists that a connector might attach to. Applying it first also means
    # a connector authored against the corrected direction sees it.
    for row in corrections[corrections["kind"] == "reversal"].itertuples():
        if row.resolved_to is None:
            skipped[row.correction_id] = "identifier did not resolve"
            continue
        reversed_by[row.resolved_to] = row.correction_id
        applied[row.correction_id] = True

    # ------------------------------------------------------------------- modes
    for row in corrections[corrections["kind"] == "mode"].itertuples():
        if row.resolved_to is None:
            skipped[row.correction_id] = "identifier did not resolve"
            continue
        mode_by[row.resolved_to] = "both"
        applied[row.correction_id] = True

    # --------------------------------------------------------------- junctions
    # A junction adds nothing at all: the target is cut and the node merged.
    for row in corrections[corrections["kind"] == "junction"].itertuples():
        if row.resolved_to is None:
            skipped[row.correction_id] = "identifier did not resolve"
            continue
        place = db.query(
            "SELECT easting, northing FROM node WHERE node_id = ?", [row.resolved_to]
        )
        target_publisher_id = _target_of(row.detail)
        target = (
            db.scalar(
                "SELECT link_id FROM link WHERE publisher_id = ?", [target_publisher_id]
            )
            if target_publisher_id
            else None
        )
        if target is None:
            skipped[row.correction_id] = (
                f"junction target link is not in the database "
                f"({row.source_file} row {row.source_row})"
            )
            continue
        e, n = place[0]
        # A junction whose target is nearest at one of its own ENDS is not a cut at
        # all: the two channels already share a place and the survey records two nodes
        # for it. That is §6's "touching but not joined", and the remedy is to merge
        # the two nodes rather than to split anything. Handling it here rather than
        # skipping keeps the class from needing a fourth kind of curated file.
        endpoint = db.query(
            """
            SELECT n.node_id,
                   sqrt(pow(n.easting - ?, 2) + pow(n.northing - ?, 2)) AS d
            FROM link l JOIN node n
              ON n.node_id IN (l.from_node, l.to_node)
            WHERE l.link_id = ?
            ORDER BY d LIMIT 1
            """,
            [e, n, target],
        )
        if endpoint and endpoint[0][1] <= float(p("repair.junction_max_offset_m")):
            merged_nodes[row.resolved_to] = endpoint[0][0]
            applied[row.correction_id] = True
            log.detail(
                f"    {row.subject}: merged onto the target's own end "
                f"{endpoint[0][1]:.2f} m away — touching but not joined, so no "
                "geometry is cut and none is invented"
            )
            continue
        try:
            node_id, children, extra = _split_link(target, e, n)
        except StageError as exc:
            skipped[row.correction_id] = str(exc)
            continue
        new_links.extend(children)
        retirements.append(extra[0] | {"correction_id": row.correction_id})
        new_nodes.append(extra[1])
        # The merge: the existing node and the new one are the same place.
        merged_nodes[node_id] = row.resolved_to
        applied[row.correction_id] = True

    # -------------------------------------------------------------- connectors
    # SAMPLED ONCE FOR ALL OF THEM, and that is not a micro-optimisation.
    # `raster.sample_points` reads the whole band on every call, so asking it per
    # connector would read a 128 MB raster 1,200 times and turn an 18-second stage
    # into a long one. The batched form reads it twice.
    rises = _rises_by_correction(corrections)

    for row in corrections[corrections["kind"] == "connector"].itertuples():
        if row.wkb is None:
            skipped[row.correction_id] = "a connector with no geometry"
            continue
        line = shapely.from_wkb(bytes(row.wkb))
        coords = list(shapely.get_coordinates(line))
        ends = [shapely.Point(coords[0]), shapely.Point(coords[-1])]

        # A CONNECTOR THAT RISES IS WATER RUNNING UPHILL, AND IT IS REFUSED HERE.
        #
        # The rule that proposes these joins a stranded region to the nearest water
        # that drains, and until v0.1.0-alpha it weighed only distance. Two channels
        # can be close in plan and separated by an embankment, a road or a watershed:
        # 104 of that release's 1,204 connectors rose more than a metre end to end, 23
        # rose more than five, and the worst climbed 27.4 m in 462 m. Stephen found two
        # of them on the map; the rest were found by measuring the class.
        #
        # THE VETO IS HERE AND NOT ONLY IN THE PROPOSER because the proposals are
        # already authored — `data/curated/connectors.geojson` holds 1,205 of them, and
        # fixing the proposer alone would leave every existing one applied. It also
        # catches a connector authored by hand, which the proposer never sees.
        #
        # It works at this point in the pipeline only because `terrain` runs BEFORE
        # `repair` and leaves the unconditioned mosaic on disk. That ordering is load
        # bearing for this check: move `repair` earlier and the DEM would be absent,
        # the veto would quietly pass everything, and a clean build would disagree with
        # a rebuild. The stage declares `terrain50_unconditioned` as a read so the
        # dependency is stated rather than assumed.
        #
        # NOT DELETED — REFUSED, WITH A REASON. The row stays in the curated file and
        # the correction table records `applied = false` and why, which is the
        # mechanism every other skip already uses.
        #
        # A PERSON OUTRANKS A 50 m TERRAIN MODEL. Where the evidence does not say
        # JUDGED BY RULE, somebody has looked at the place, and Terrain 50 cannot
        # resolve a lock, a culvert or a pumped outfall — which is what these joins
        # usually are. Those are applied, and the rise is reported rather than hidden.
        rise = rises.get(row.correction_id)
        if rise is not None and rise > max_rise_m:
            # A SURVEYED STRUCTURE OUTRANKS THE MODEL. If the Trust records a lock, an
            # aqueduct, a culvert or a weir within `corroborate_m`, something was built
            # at this place to move water across it — which is the very thing D-011 says
            # the survey does not draw, and better evidence than a 50 m grid. Measured
            # against v0.1.0-alpha this reinstates 15 of 62 refusals, and those 15 are
            # anomalous twice over: the terrain says uphill AND something is there.
            near_structure = _structure_within(coords, corroborate_m)
            if near_structure is not None:
                log.detail(
                    f"    {row.subject}: climbs {rise:,.1f} m, applied anyway — "
                    f"{near_structure} within {corroborate_m:g} m. A surveyed structure "
                    "outranks a 50 m terrain model"
                )
            elif "JUDGED BY RULE" in (row.evidence or "").upper():
                skipped[row.correction_id] = (
                    f"the connector climbs {rise:,.1f} m end to end on the "
                    f"unconditioned Terrain 50 surface, more than the {max_rise_m:g} m "
                    "that model can be trusted for. Two channels close in plan and "
                    "separated by a bank are not a survey gap, and joining them would "
                    "route water uphill. Judged by rule, so nobody has looked: left as "
                    "a dead end, which the audit reports with the length behind it"
                )
                continue
            log.detail(
                f"    {row.subject}: climbs {rise:,.1f} m, applied anyway — the "
                "evidence names a person, and a 50 m model cannot see a lock or a "
                "pumped outfall"
            )

        resolved_ends = []
        failed = None
        for end in ends:
            r = _resolve_end(end, snap_node_m, split_link_m)
            if r["kind"] == "unresolved":
                failed = (
                    f"an end at {r['easting']:.0f}, {r['northing']:.0f} resolves onto "
                    f"nothing within {split_link_m:g} m"
                    + (f" (nearest link {r['distance_m']:.1f} m)" if r["distance_m"] else "")
                )
                break
            resolved_ends.append(r)
        if failed:
            skipped[row.correction_id] = failed
            continue

        end_nodes = []
        for r in resolved_ends:
            if r["kind"] == "node":
                end_nodes.append(r["node_id"])
            else:
                try:
                    node_id, children, extra = _split_link(
                        r["link_id"], r["easting"], r["northing"]
                    )
                except StageError as exc:
                    failed = str(exc)
                    break
                new_links.extend(children)
                retirements.append(extra[0] | {"correction_id": row.correction_id})
                new_nodes.append(extra[1])
                end_nodes.append(node_id)
        if failed:
            skipped[row.correction_id] = failed
            continue
        if end_nodes[0] == end_nodes[1]:
            skipped[row.correction_id] = (
                "both ends resolve to the same node — what is wanted here is a "
                "junction, which adds nothing at all; a zero-length connector once "
                "reached a published dataset as a row with no country (§5)"
            )
            continue

        link_id = ids.line(coords, "link")
        new_links.append(
            {
                "link_id": link_id,
                "publisher_id": None,
                "source_id": "rewt",
                "origin": "connector",
                "form": None,
                "name": row.subject,
                "name_alt": None,
                "from_node": end_nodes[0],
                "to_node": end_nodes[1],
                "length_m": float(shapely.length(line)),
                "wkb": shapely.to_wkb(line),
                "parent_link_id": None,
            }
        )
        applied[row.correction_id] = True

    # -------------------------------------------------------------- exclusions
    excluded: set[str] = set()
    for row in corrections[corrections["kind"] == "exclusion"].itertuples():
        if row.resolved_to is None:
            skipped[row.correction_id] = "identifier did not resolve"
            continue
        excluded.add(row.resolved_to)
        applied[row.correction_id] = True

    # ------------------------------------------------------------ persist them
    _write_repairs(new_links, new_nodes, retirements)
    _build_edge(reversed_by, mode_by, merged_nodes, excluded, new_links)

    # Record what was applied and what was skipped, by identifier. Never silently.
    # Declared dtypes again, for the same reason: with no corrections yet there is
    # nothing for pandas to infer from, and an untyped empty column reaches DuckDB as
    # DOUBLE.
    applied_frame = pd.DataFrame(
        {
            "correction_id": pd.Series(list(applied) + list(skipped), dtype="string"),
            "was_applied": pd.Series(
                [True] * len(applied) + [False] * len(skipped), dtype="boolean"
            ),
            "why": pd.Series(
                [None] * len(applied) + list(skipped.values()), dtype="string"
            ),
        }
    )
    with db.registered("_applied_in", applied_frame):
        con.execute(
            """
            UPDATE correction SET
                applied = COALESCE((SELECT was_applied FROM _applied_in a
                                    WHERE a.correction_id = correction.correction_id), false),
                skip_reason = COALESCE(skip_reason,
                                       (SELECT why FROM _applied_in a
                                        WHERE a.correction_id = correction.correction_id))
            """
        )

    if skipped:
        log.warn(f"{len(skipped)} curated judgement(s) were not applied. Named:")
        for cid, why in skipped.items():
            row = db.query(
                "SELECT kind, subject, easting, northing FROM correction WHERE correction_id = ?",
                [cid],
            )
            kind, subject, e, n = row[0] if row else ("?", cid, None, None)
            log.finding(f"{kind} {subject}: {why}", e, n)
            report.finding(
                Finding(kind="correction_skipped", subject=str(subject), detail=why,
                        easting=e, northing=n)
            )

    counts = con.execute(
        "SELECT kind, sum(CASE WHEN applied THEN 1 ELSE 0 END), count(*) "
        "FROM correction GROUP BY 1 ORDER BY 1"
    ).fetchall()
    if counts:
        log.table("judgements applied", ["class", "applied", "authored"], counts)

    # Every applied correction must be VISIBLE in the graph it claims to have changed.
    # A stage that reports success while the artefact is unchanged is the failure this
    # project has met more often than any other (§8, D-017, D-031).
    unseen = db.query(
        """
        SELECT c.correction_id, c.kind, c.subject
        FROM correction c
        WHERE c.applied AND c.kind = 'reversal'
          AND c.correction_id NOT IN (
              SELECT reversed_by FROM edge WHERE reversed_by IS NOT NULL
          )
        ORDER BY c.subject
        """
    )
    if unseen:
        raise StageError(
            f"{len(unseen)} reversal(s) are recorded as applied but do not appear in "
            "the routing graph. A correction that reports success while changing "
            "nothing is the failure PLAN.md §8 names twice. Named:\n  "
            + "\n  ".join(f"{k} {subj} ({cid})" for cid, k, subj in unseen[:20])
        )

    edges = db.count("edge")
    log.done(
        f"routing graph: {edges:,} edges "
        f"({db.count('repair_link')} added, {db.count('retirement')} retired, "
        f"{len(reversed_by)} reversed)"
    )
    report.add("applied", {k: int(a or 0) for k, a, _ in counts})
    report.add("skipped", len(skipped))
    report.write_json(paths.PUBLISHED / "audit" / "repair.json")

    return {
        "edges": edges,
        "added": db.count("repair_link"),
        "retired": db.count("retirement"),
        "reversed": len(reversed_by),
        "skipped": len(skipped),
    }


def _target_of(detail: str | None) -> str | None:
    """A junction names the link it merges onto; that travels in the row's `detail`.

    Read back from what was authored, not re-derived: a correction that references a
    feature by id does nothing, silently, when the id is wrong, while the stage
    reports it applied (§8). The id is checked in the curated stage and used here.
    """
    if not detail:
        return None
    fields = json.loads(detail)
    value = fields.get("target_publisher_id") or fields.get("target")
    return str(value).strip() or None if value else None


def _write_repairs(new_links, new_nodes, retirements) -> None:
    con = db.get()
    con.execute("DROP TABLE IF EXISTS repair_link")
    con.execute(
        """
        CREATE TABLE repair_link (
            link_id VARCHAR, publisher_id VARCHAR, source_id VARCHAR, origin VARCHAR,
            form VARCHAR, name VARCHAR, name_alt VARCHAR, from_node VARCHAR,
            to_node VARCHAR, length_m DOUBLE, parent_link_id VARCHAR, geom GEOMETRY
        )
        """
    )
    con.execute("DROP TABLE IF EXISTS repair_node")
    con.execute(
        """
        CREATE TABLE repair_node (
            node_id VARCHAR, publisher_id VARCHAR, source_id VARCHAR, origin VARCHAR,
            category VARCHAR, terminus VARCHAR, easting DOUBLE, northing DOUBLE,
            geom GEOMETRY
        )
        """
    )
    schema.create("retirement")

    if new_links:
        frame = pd.DataFrame(new_links).drop_duplicates(subset=["link_id"])
        with db.registered("_rl_in", frame):
            con.execute(
                """
                INSERT INTO repair_link
                SELECT link_id, publisher_id, source_id, origin, form, name, name_alt,
                       from_node, to_node, length_m, parent_link_id,
                       ST_GeomFromWKB(wkb)
                FROM _rl_in ORDER BY link_id
                """
            )
    if new_nodes:
        frame = pd.DataFrame(new_nodes).drop_duplicates(subset=["node_id"])
        with db.registered("_rn_in", frame):
            con.execute(
                """
                INSERT INTO repair_node
                SELECT node_id, publisher_id, source_id, origin, category, terminus,
                       easting, northing, ST_GeomFromWKB(wkb)
                FROM _rn_in ORDER BY node_id
                """
            )
    if retirements:
        frame = pd.DataFrame(retirements).drop_duplicates(subset=["link_id"])
        if "correction_id" not in frame.columns:
            frame["correction_id"] = None
        with db.registered("_ret_in", frame[["link_id", "reason", "superseded_by", "correction_id"]]):
            con.execute("INSERT INTO retirement SELECT * FROM _ret_in ORDER BY link_id")


def _build_edge(reversed_by, mode_by, merged_nodes, excluded, new_links) -> None:
    """Build the one routing graph, from `link` plus the repairs.

    Two graphs over one geometry cannot be reconciled after the fact (§8). This is the
    only edge table there is, and a reversal exists here and nowhere else — the
    published geometry and attributes are untouched by it.
    """
    con = db.get()
    schema.create("edge")

    # Every column is declared as a string, including when it is empty. An empty
    # pandas column has no dtype to infer, DuckDB reads it as DOUBLE, and joining it
    # to a VARCHAR key fails with a type error that says nothing about the real
    # situation — which is that there are no corrections yet, the correct state before
    # the audit has been adjudicated.
    def strings(**columns) -> pd.DataFrame:
        return pd.DataFrame(
            {k: pd.Series(v, dtype="string") for k, v in columns.items()}
        )

    frames = {
        "_rev_in": strings(
            link_id=list(reversed_by), correction_id=list(reversed_by.values())
        ),
        "_mode_in": strings(link_id=list(mode_by), mode=list(mode_by.values())),
        "_merge_in": strings(
            from_node_id=list(merged_nodes), to_node_id=list(merged_nodes.values())
        ),
        "_excl_in": strings(link_id=sorted(excluded)),
    }
    for name, frame in frames.items():
        db.register(name, frame)
    try:
        con.execute(
            """
            INSERT INTO edge
            WITH all_links AS (
                SELECT link_id, from_node, to_node, length_m, form, origin,
                       NULL AS parent_link_id
                FROM link
                WHERE link_id NOT IN (SELECT link_id FROM retirement)
                UNION ALL
                SELECT link_id, from_node, to_node, length_m, form, origin,
                       parent_link_id
                FROM repair_link
            ),
            merged AS (
                SELECT a.link_id,
                       coalesce(mf.to_node_id, a.from_node) AS from_node,
                       coalesce(mt.to_node_id, a.to_node)   AS to_node,
                       a.length_m, a.form, a.origin,
                       -- A link that was reversed and LATER SPLIT by a connector or a
                       -- junction becomes two children with new identifiers, and a
                       -- reversal keyed on the parent then matches neither. Eleven
                       -- reversals were silently lost that way: `correction.applied`
                       -- said true, `edge.reversed` said false, and the published
                       -- network carried no trace of them. That is precisely §8's
                       -- "a correction that references a feature by id does nothing,
                       -- silently, while the stage reports it applied". The parent's
                       -- identity is carried here so a reversal reaches its children.
                       coalesce(a.parent_link_id, a.link_id) AS reversal_key
                FROM all_links a
                LEFT JOIN _merge_in mf ON mf.from_node_id = a.from_node
                LEFT JOIN _merge_in mt ON mt.from_node_id = a.to_node
            )
            SELECT m.link_id AS edge_id,
                   m.link_id,
                   CASE WHEN r.link_id IS NOT NULL THEN m.to_node   ELSE m.from_node END,
                   CASE WHEN r.link_id IS NOT NULL THEN m.from_node ELSE m.to_node   END,
                   coalesce(md.mode, 'downstream'),
                   m.length_m, m.form, m.origin,
                   r.link_id IS NOT NULL,
                   r.correction_id
            FROM merged m
            LEFT JOIN _rev_in  r  ON r.link_id  = m.reversal_key
            LEFT JOIN _mode_in md ON md.link_id = m.link_id
            WHERE m.link_id NOT IN (SELECT link_id FROM _excl_in)
            ORDER BY m.link_id
            """
        )
    finally:
        for name in frames:
            db.unregister(name)


def _rises_by_correction(corrections) -> dict[str, float]:
    """How far each connector climbs end to end, for all of them in one raster pass.

    Positive is uphill: the water the connector invents would have to run up. A
    correction is absent from the result where the terrain cannot answer — an end
    offshore, or outside the clipped grid — because a question the model cannot answer
    gets no vote.

    **The unconditioned surface, and the distinction is D-007's.** The conditioned DEM
    has this network burned into it, so asking it whether a connector runs downhill
    would be asking whether the answer we assumed is the answer we get.
    """
    import numpy as np
    import shapely

    from .. import raster

    rows = corrections[(corrections["kind"] == "connector")
                       & corrections["wkb"].notna()]
    if rows.empty:
        return {}
    raster.assert_unconditioned(raster.UNCONDITIONED)

    ids, ax, ay, bx, by = [], [], [], [], []
    for r in rows.itertuples():
        cs = shapely.get_coordinates(shapely.from_wkb(bytes(r.wkb)))
        ids.append(r.correction_id)
        ax.append(cs[0][0]); ay.append(cs[0][1])
        bx.append(cs[-1][0]); by.append(cs[-1][1])

    with raster.open_unconditioned() as ds:
        za = raster.sample_points(ds, np.array(ax, float), np.array(ay, float))
        zb = raster.sample_points(ds, np.array(bx, float), np.array(by, float))

    good = np.isfinite(za) & np.isfinite(zb)
    return {cid: float(z2 - z1)
            for cid, z1, z2, ok in zip(ids, za, zb, good) if ok}


def _structure_within(coords, radius_m: float) -> str | None:
    """The nearest Canal & River Trust structure to either end, if one is close enough.

    Returns a description for the log, or `None` where nothing is near. **Either end,
    not the midpoint**: a lock or an aqueduct sits where the two waters meet, which is
    one of the connector's ends, and a short connector's midpoint is a place where
    nothing was ever built.

    The structure register is loaded once per build and cached on the function, because
    this is asked of every climbing connector and the table is small.
    """
    cache = getattr(_structure_within, "_cache", None)
    if cache is None:
        rows = db.get().execute(
            "SELECT kind, easting, northing FROM structure"
        ).fetchall()
        cache = [(k, float(e), float(n)) for k, e, n in rows]
        _structure_within._cache = cache
    if not cache:
        return None
    for x, y in (coords[0], coords[-1]):
        best, kind = None, None
        for k, e, n in cache:
            d = ((e - x) ** 2 + (n - y) ** 2) ** 0.5
            if best is None or d < best:
                best, kind = d, k
        if best is not None and best <= radius_m:
            return f"a {kind} {best:,.0f} m away"
    return None
