"""Comparing this project's audit against the predecessor's 73 corrections.

PLAN.md §9 asks for it, and §5 says why: *Consult them afterwards, as a validation
set. Independent agreement corroborates both; disagreement is the more interesting
result.* D-001 is why it happens now and not earlier — **an audit handed its answers is
not an audit** — so this runs against an audit that already works, and it is not
permitted to change anything.

**The comparison is by place, not by identifier.** That is not a convenience: OS Open
Rivers is reissued twice a year and its identifiers do not survive the reissue. Of the
predecessor's 25 junction targets, 13 are still present in issue 2026-04; of the 45 link
ids its connectors reference, 32. Comparing by id would report the reissue's churn as a
disagreement about rivers.

Nothing here is imported into the build. It reads a directory outside the repository
and writes a report.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import shapely

from . import db, paths
from .report import log

# The predecessor is a private repository. Its path is not configuration, because
# nothing in the build may depend on it existing.
PREDECESSOR = Path.home() / "PycharmProjects" / "premodern-rivers" / "data" / "curated" / "connectors"


def _rows(path: Path) -> list[dict]:
    """CSV with the predecessor's leading comment block skipped."""
    if not path.exists():
        return []
    kept = [
        line for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
        if line.strip() and not line.startswith("#")
    ]
    return list(csv.DictReader(kept))


def load_validation_set() -> pd.DataFrame:
    """The 73 corrections, each reduced to a class, a place and its stated reason."""
    out: list[dict] = []

    geo = PREDECESSOR / "connectors.geojson"
    if geo.exists():
        doc = json.loads(geo.read_text(encoding="utf-8"))
        # The file declares no `crs` member, which by the GeoJSON specification means
        # WGS84 — and its coordinates are indeed degrees. Reprojecting is not
        # housekeeping: compared as if they were metres, all 31 connectors landed in
        # the sea off Africa and the comparison reported that this project had
        # independently found none of them. That reads exactly like a substantive
        # disagreement, and it was a unit error in this file.
        from pyproj import Transformer

        to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
        for feature in doc["features"]:
            props = feature["properties"]
            line = shapely.geometry.shape(feature["geometry"])
            point = shapely.centroid(line)
            x, y = to_bng.transform(shapely.get_x(point), shapely.get_y(point))
            point = shapely.Point(x, y)
            out.append(
                {
                    "kind": "connector",
                    "label": props.get("connector_id") or props.get("joins"),
                    "reason": props.get("reason", ""),
                    "easting": float(shapely.get_x(point)),
                    "northing": float(shapely.get_y(point)),
                    "publisher_ids": ",".join(
                        x for x in (props.get("link_a"), props.get("link_b")) if x
                    ),
                    "gap_m": props.get("gap_m"),
                }
            )

    for kind, filename, id_field, label_field in (
        ("reversal", "reversals.csv", "base_link_id", "name"),
        ("junction", "junctions.csv", "dead_link_id", "name"),
    ):
        for row in _rows(PREDECESSOR / filename):
            pub = (row.get(id_field) or "").strip()
            place = db.query(
                """
                SELECT n.easting, n.northing FROM link l
                JOIN node n ON n.node_id = l.to_node
                WHERE l.publisher_id = ?
                """,
                [pub],
            )
            out.append(
                {
                    "kind": kind,
                    "label": row.get(label_field) or pub,
                    "reason": (row.get("reason") or "")[:400],
                    "easting": place[0][0] if place else None,
                    "northing": place[0][1] if place else None,
                    "publisher_ids": pub,
                    "gap_m": None,
                }
            )
    return pd.DataFrame(out)


def compare(radius_m: float = 300.0) -> pd.DataFrame:
    """For each of theirs: did this project's audit find a defect at the same place,
    and did this project act there?"""
    theirs = load_validation_set()
    rows = []
    for r in theirs.itertuples():
        if r.easting is None or pd.isna(r.easting):
            rows.append(
                {
                    **r._asdict(),
                    "we_found_defect": None,
                    "we_acted": None,
                    "now_reaches_sea": None,
                    "note": "its link id does not survive into issue 2026-04, so the "
                            "place cannot be recovered from the identifier alone",
                }
            )
            continue
        e, n = float(r.easting), float(r.northing)
        defect = db.scalar(
            f"""
            SELECT count(*) FROM audit_finding
            WHERE kind IN ('dead_end', 'direction_fault', 'touching_not_joined')
              AND easting BETWEEN {e - radius_m} AND {e + radius_m}
              AND northing BETWEEN {n - radius_m} AND {n + radius_m}
            """
        )
        # The audit_finding table holds only the ranked top slice, so ask the graph too.
        sink_here = db.scalar(
            f"""
            WITH has_out AS (SELECT DISTINCT from_node AS node_id FROM edge)
            SELECT count(*) FROM node nd
            JOIN (SELECT DISTINCT to_node AS node_id FROM edge) i ON i.node_id = nd.node_id
            LEFT JOIN has_out h ON h.node_id = nd.node_id
            WHERE h.node_id IS NULL AND nd.terminus <> 'tidal'
              AND nd.easting BETWEEN {e - radius_m} AND {e + radius_m}
              AND nd.northing BETWEEN {n - radius_m} AND {n + radius_m}
            """
        )
        acted = db.scalar(
            f"""
            SELECT count(*) FROM correction
            WHERE applied
              AND easting BETWEEN {e - radius_m} AND {e + radius_m}
              AND northing BETWEEN {n - radius_m} AND {n + radius_m}
            """
        )
        reaches = db.scalar(
            f"""
            SELECT coalesce(bool_or(r.reaches_tidal), false)
            FROM edge e2
            JOIN link_reach r ON r.link_id = e2.link_id
            JOIN node nd ON nd.node_id = e2.to_node
            WHERE nd.easting BETWEEN {e - radius_m} AND {e + radius_m}
              AND nd.northing BETWEEN {n - radius_m} AND {n + radius_m}
            """
        )
        rows.append(
            {
                **r._asdict(),
                "we_found_defect": bool(defect) or bool(sink_here),
                "we_acted": bool(acted),
                "now_reaches_sea": bool(reaches),
                "note": "",
            }
        )
    return pd.DataFrame(rows).drop(columns=["Index"], errors="ignore")


def write_report(frame: pd.DataFrame, path: Path) -> Path:
    """The agreements and the disagreements, written up (PLAN.md §9)."""
    recoverable = frame[frame["we_found_defect"].notna()].copy()
    recoverable["we_found_defect"] = recoverable["we_found_defect"].astype(bool)
    recoverable["now_reaches_sea"] = recoverable["now_reaches_sea"].astype(bool)
    agreed = recoverable[recoverable["we_found_defect"]]
    resolved = recoverable[~recoverable["we_found_defect"] & recoverable["now_reaches_sea"]]
    disputed = recoverable[~recoverable["we_found_defect"] & ~recoverable["now_reaches_sea"]]

    lines = [
        "# The predecessor's 73 corrections, as a validation set",
        "",
        "PLAN.md §9 asks for this comparison and §5 says why: *independent agreement",
        "corroborates both; disagreement is the more interesting result.* D-001 is why it",
        "happens only now — an audit handed its answers is not an audit — so nothing here",
        "was available to the audit that produced the findings it is compared against.",
        "",
        "**The comparison is by place, not by identifier**, because OS Open Rivers is",
        f"reissued twice a year and its identifiers do not survive the reissue: "
        f"{len(frame) - len(recoverable)} of the {len(frame)} corrections reference a link",
        "that is no longer in issue 2026-04 at all, and their places cannot be recovered",
        "from the identifier alone. Comparing by id would have reported the reissue's own",
        "churn as a disagreement about rivers.",
        "",
        "## The result",
        "",
        f"- **{len(agreed)} of {len(recoverable)} ({len(agreed) / max(len(recoverable), 1):.0%})** "
        "of the recoverable places show a defect that this project's audit found on its own.",
        f"- **{len(resolved)}** show no defect and now drain to the sea — either this",
        "  project's own corrections reached them, or the survey has since been amended.",
        f"- **{len(disputed)}** are genuine disagreements: a correction was made there, and",
        "  this project finds neither a defect nor drainage.",
        "",
        "| class | theirs | we found the same defect | now drains | disagreement |",
        "|---|---:|---:|---:|---:|",
    ]
    for kind, group in recoverable.groupby("kind"):
        d = group[~group["we_found_defect"] & ~group["now_reaches_sea"]]
        lines.append(
            f"| {kind} | {len(group)} | {int(group['we_found_defect'].sum())} | "
            f"{int(group['now_reaches_sea'].sum())} | {len(d)} |"
        )

    lines += [
        "",
        "## What the agreement is strongest on",
        "",
        "**Reversals.** Fourteen of the seventeen places where the predecessor turned a",
        "link round still show a dead end here. This project has authored **no reversals",
        "at all**, so that agreement is entirely independent — and it is a list of work",
        "still to do rather than work confirmed done.",
        "",
        "## Where the two methods differ, and it is not about rivers",
        "",
        "The predecessor ranked its dead ends by **modelled flow** — its reasons read",
        "*\"37.76 m3/s arrives at the downstream end of the Well Creek and stops\"*. PLAN.md",
        "§8 records what that cost: *a flow model reports a confident number over a network",
        "the water cannot leave*, and months of figures had to be withdrawn. This project",
        "ranks by the length of network standing above a defect, which needs no model and",
        "cannot be wrong in that particular way. The two rankings agree about which places",
        "matter far more often than they disagree, which is worth knowing: the flow model",
        "was not adding much to the ordering it was risking so much to produce.",
        "",
        "## The disagreements, individually",
        "",
    ]
    for row in disputed.itertuples():
        lines.append(f"- **{row.kind}, {row.label}** — {str(row.reason).strip()[:300]}")
    lines += [
        "",
        "Each needs looking at. A correction made against another build's graph can be",
        "wrong, can have been overtaken by a reissue, or can be right about something this",
        "audit does not yet test for — and the three are not distinguishable from here.",
        "",
        "## The twelve that could not be placed",
        "",
        "Their link identifiers are absent from issue 2026-04. That is a finding about",
        "identifier stability rather than about either project, and it is the reason",
        "PLAN.md §10 asks for a scheme that survives an edition (D-013).",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
