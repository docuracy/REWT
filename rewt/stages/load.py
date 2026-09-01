"""Stage: load OS Open Rivers into `link` and `node`, already oriented.

Two things this stage must get right, because everything downstream assumes them.

**Store the nodes already oriented**, so `from_node` is upstream and `to_node`
downstream for every row whatever the source (PLAN.md §3). OS encodes direction
*relative to the digitised line*, and in the earlier work four separate places had to
remember to flip it. It is resolved once, here, and the digitised sense is kept
alongside so the flip stays inspectable.

**Bulk insert.** Per-row inserts that parse geometry per row took ten minutes for
122,000 rows where a single bulk insert took moments (AGENTS.md).

The stage ends by checking itself against PLAN.md §6's calibration figures for OS Open
Rivers *as shipped*. Those are measurements of the publisher's product and are
legitimate to check against; if they do not match closely the loader is wrong and
nothing downstream is worth looking at.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyogrio

from .. import acquire, config, db, ids, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import log

LINK = artefact("link")
NODE = artefact("node")

# The calibration table of PLAN.md §6, for Great Britain, before any repair. These are
# the publisher's figures for an earlier issue; the product is reissued twice a year, so
# a small drift is expected and a large one is a bug in this loader.
CALIBRATION = {
    "inlandRiver": (156808, 138402),
    "lake": (24490, 5864),
    "tidalRiver": (11589, 5738),
    "canal": (1584, 2722),
}
CALIBRATION_TOTAL_LINKS = 192865
CALIBRATION_NODES = 198000
CALIBRATION_AGAINST_LINE = 3
# The tolerance is a judgement and is recorded as D-012. A loader bug is structural —
# wrong units, dropped rows, misparsed forms — and shows as tens of per cent or more.
# Drift between two issues of a twice-yearly product is a per cent or two, and lake
# links are the ones that move most, being the most heavily re-generalised.
TOLERANCE = 0.03


def _geopackage_date(path) -> str | None:
    """The date the GeoPackage itself records, from `gpkg_contents.last_change`."""
    import sqlite3

    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
            row = con.execute(
                "SELECT max(last_change) FROM gpkg_contents"
            ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0])[:10] if row and row[0] else None


def _resolve_direction(flow: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Which rows are digitised against the flow, and which said nothing at all.

    PLAN.md §5: the attribute carries almost no signal — three links in 194,471 are
    recorded as flowing against the digitised line. Direction *is* digitised order.
    That is a reason to distrust the attribute downstream, not a reason to skip it here.
    """
    p = config.params()
    with_line = {str(v).lower() for v in p("load.direction_with_line")}
    against_line = {str(v).lower() for v in p("load.direction_against_line")}

    norm = flow.fillna("").astype(str).str.strip().str.lower()
    is_with = norm.isin(with_line)
    is_against = norm.isin(against_line)
    unknown = norm == ""

    unrecognised = ~(is_with | is_against | unknown)
    if unrecognised.any():
        values = sorted(set(norm[unrecognised]))
        raise StageError(
            f"OS Open Rivers carries flow_direction values this loader does not "
            f"recognise: {values}. Add them to conf/params.yml load.direction_* — "
            "guessing which way the water goes is not an option."
        )
    return is_against, unknown


@PIPELINE.stage(
    "load",
    "OS Open Rivers into link and node, oriented once and for all",
    reads=["raw_os_open_rivers"],
    writes=["link", "node"],
    params=["load", "forms", "crs", "seeds"],
    sources=["os_open_rivers"],
)
def run() -> dict:
    p = config.params()
    src = config.source("os_open_rivers")
    acq = acquire.require_acquisition("os_open_rivers")
    gpkg = acquire.one("os_open_rivers", "*.gpkg")
    # conf/sources.yml: "Reissued twice a year. Record which issue was fetched: the
    # network changes between them, and a result that cannot name its input cannot be
    # reproduced." The API gives a month; the GeoPackage's own `gpkg_contents` gives
    # the day the product was written, which is the more precise statement of what is
    # in the file, so both are recorded.
    issued_on = _geopackage_date(gpkg)
    log.info(
        f"{src.title}, issue {acq.issue}"
        + (f" (written {issued_on})" if issued_on else "")
        + f" — {gpkg.name}"
    )

    # ------------------------------------------------------------------ the pin
    # D-053. The project takes OS's identifiers and freezes the issue rather than
    # minting its own. That is only a guarantee if the freeze is enforced: OS says
    # its GUIDs are not persistent between product versions, so accepting a reissue
    # silently would renumber 195,689 links and 198,457 nodes, and every judgement in
    # data/curated/ keys on those numbers.
    #
    # Fail rather than warn. A warning on a twice-yearly event is a warning nobody is
    # present for — the reissue lands, the build goes green, and the first sign of
    # trouble is a curated correction that no longer matches anything.
    frozen = src.get("frozen_issue", default=None)
    if frozen and issued_on and issued_on != frozen:
        raise StageError(
            f"OS Open Rivers is pinned to the {frozen} issue (conf/sources.yml, "
            f"D-053) and the file on disk was written {issued_on}. This is the "
            "reissue the pin exists to catch.\n\n"
            "A reissue renumbers every link and node, and data/curated/ keys on "
            "those identifiers, so this is a decision and not a refresh. Either "
            "restore the pinned issue, or take the decision to move the pin — which "
            "means re-validating every curated judgement against the new numbering "
            "and recording it in DECISIONS.md."
        )
    if frozen and not issued_on:
        raise StageError(
            f"OS Open Rivers is pinned to the {frozen} issue but the GeoPackage "
            "records no write date in gpkg_contents, so the pin cannot be checked. "
            "Refusing to build against an input that cannot identify itself."
        )

    working_crs = p("crs.working")

    # ---------------------------------------------------------------- links
    links = pyogrio.read_dataframe(gpkg, layer="watercourse_link", use_arrow=False)
    if str(links.crs) != working_crs:
        raise StageError(
            f"OS Open Rivers arrived as {links.crs}, not {working_crs}. "
            "Reproject once, at the boundary, and nowhere else (AGENTS.md)."
        )

    is_against, unknown = _resolve_direction(links["flow_direction"])

    # Orientation. from_node upstream, to_node downstream, on every row.
    from_node = np.where(is_against, links["end_node"], links["start_node"])
    to_node = np.where(is_against, links["start_node"], links["end_node"])

    frame = pd.DataFrame(
        {
            "link_id": [ids.publisher("link", x) for x in links["id"]],
            "publisher_id": links["id"].to_numpy(),
            "source_id": "os_open_rivers",
            "origin": "survey",
            "form": links["form"].to_numpy(),
            "name": links["watercourse_name"].to_numpy(),
            "name_alt": links["watercourse_name_alternative"].to_numpy(),
            "from_node": [ids.publisher("node", x) for x in from_node],
            "to_node": [ids.publisher("node", x) for x in to_node],
            "digitised_from": [ids.publisher("node", x) for x in links["start_node"]],
            "digitised_to": [ids.publisher("node", x) for x in links["end_node"]],
            "flow_direction": links["flow_direction"].to_numpy(),
            "oriented_flip": is_against.to_numpy(),
            "direction_known": (~unknown).to_numpy(),
            "published_length_m": links["length"].astype(float).to_numpy(),
            "wkb": [g.wkb if g is not None else None for g in links.geometry],
        }
    )
    if frame["wkb"].isna().any():
        raise StageError(f"{int(frame['wkb'].isna().sum())} links arrived with no geometry")

    # Deterministic ordering (§2): the publisher's id, which does not move between runs.
    frame = frame.sort_values("publisher_id", kind="stable").reset_index(drop=True)

    schema.create("link", "node")
    con = db.get()
    with db.registered("_link_in", frame):
        con.execute(
            """
            INSERT INTO link
            SELECT link_id, publisher_id, source_id, origin, form, name, name_alt,
                   from_node, to_node, digitised_from, digitised_to, flow_direction,
                   oriented_flip, direction_known,
                   ST_Length(ST_GeomFromWKB(wkb)) AS length_m,
                   published_length_m,
                   ST_GeomFromWKB(wkb) AS geom
            FROM _link_in
            """
        )

    # ---------------------------------------------------------------- nodes
    nodes = pyogrio.read_dataframe(gpkg, layer="hydro_node", use_arrow=False)
    if str(nodes.crs) != working_crs:
        raise StageError(f"hydro_node arrived as {nodes.crs}, not {working_crs}")

    # Terminus classification, from the survey's own form and never from a coastline.
    tidal_forms = set(p("seeds.tidal_forms"))
    tidal_links = links.loc[links["form"].isin(tidal_forms)]
    tidal_node_ids = set(tidal_links["start_node"]) | set(tidal_links["end_node"])

    node_frame = pd.DataFrame(
        {
            "node_id": [ids.publisher("node", x) for x in nodes["id"]],
            "publisher_id": nodes["id"].to_numpy(),
            "source_id": "os_open_rivers",
            "origin": "survey",
            "category": nodes["hydro_node_category"].to_numpy(),
            "terminus": np.where(nodes["id"].isin(tidal_node_ids), "tidal", "inland"),
            "easting": nodes.geometry.x.to_numpy(),
            "northing": nodes.geometry.y.to_numpy(),
            "wkb": [g.wkb for g in nodes.geometry],
        }
    ).sort_values("publisher_id", kind="stable").reset_index(drop=True)

    with db.registered("_node_in", node_frame):
        con.execute(
            """
            INSERT INTO node
            SELECT node_id, publisher_id, source_id, origin, category, terminus,
                   easting, northing, ST_GeomFromWKB(wkb) AS geom
            FROM _node_in
            """
        )

    schema.index(
        ("link", "link_id"),
        ("link", "from_node"),
        ("link", "to_node"),
        ("link", "form"),
        ("node", "node_id"),
    )

    detail = _integrity_and_calibration(acq.issue)
    detail["issued_on"] = issued_on
    return detail


def _integrity_and_calibration(issue: str) -> dict:
    """Fail loudly on integrity; report loudly on calibration."""
    con = db.get()

    dangling = con.execute(
        """
        SELECT count(*) FROM (
            SELECT from_node AS n FROM link UNION ALL SELECT to_node FROM link
        ) e LEFT JOIN node ON node.node_id = e.n WHERE node.node_id IS NULL
        """
    ).fetchone()[0]
    if dangling:
        raise StageError(
            f"{dangling:,} link endpoints reference a node that is not in hydro_node. "
            "The survey's topology is the one thing this stage is entitled to trust."
        )

    duplicates = con.execute(
        "SELECT count(*) FROM (SELECT link_id FROM link GROUP BY 1 HAVING count(*) > 1)"
    ).fetchone()[0]
    if duplicates:
        raise StageError(f"{duplicates:,} duplicate link ids after load")

    # A link whose two ends are the same node contributes nothing to drainage and is a
    # finding, not an error. Report it at the place.
    loops = con.execute(
        """
        SELECT l.publisher_id, l.form, l.length_m, n.easting, n.northing
        FROM link l JOIN node n ON n.node_id = l.from_node
        WHERE l.from_node = l.to_node ORDER BY l.length_m DESC
        """
    ).fetchall()
    if loops:
        log.warn(f"{len(loops)} links begin and end at the same node — reported, not repaired")
        for pub, form, length, e, n in loops[:10]:
            log.finding(f"self-loop {pub} {form} {length:,.0f} m", e, n)

    unknown_dir = con.execute(
        "SELECT count(*), coalesce(sum(length_m), 0) FROM link WHERE NOT direction_known"
    ).fetchone()
    if unknown_dir[0]:
        log.warn(
            f"{unknown_dir[0]:,} links ({unknown_dir[1] / 1000:,.1f} km) carry no "
            "flow_direction at all; they are loaded in digitised order and flagged. "
            "The audit must not read their direction as the survey's claim."
        )

    # -------------------------------------------------------- calibration
    rows = con.execute(
        """
        SELECT form, count(*) AS links, sum(length_m) / 1000.0 AS km
        FROM link GROUP BY form ORDER BY form
        """
    ).fetchall()
    total_links = con.execute("SELECT count(*) FROM link").fetchone()[0]
    total_nodes = con.execute("SELECT count(*) FROM node").fetchone()[0]
    against = con.execute("SELECT count(*) FROM link WHERE oriented_flip").fetchone()[0]

    table, drifted = [], []
    for form, n, km in rows:
        expect = CALIBRATION.get(form)
        if expect is None:
            drifted.append(f"form {form!r} is not one of PLAN.md §6's four")
            table.append((form, n, round(km, 1), "—", "—", "unexpected form"))
            continue
        dn = (n - expect[0]) / expect[0]
        dk = (km - expect[1]) / expect[1]
        verdict = "ok" if abs(dn) <= TOLERANCE and abs(dk) <= TOLERANCE else "DRIFT"
        if verdict == "DRIFT":
            drifted.append(f"{form}: {n:,} links / {km:,.0f} km against {expect}")
        table.append((form, n, round(km, 1), expect[0], expect[1], f"{verdict} {dn:+.1%}/{dk:+.1%}"))

    log.table(
        f"loader calibration against PLAN.md §6 (OS Open Rivers as shipped, issue {issue})",
        ["form", "links", "km", "plan links", "plan km", "verdict"],
        table,
    )
    log.info(
        f"  total {total_links:,} links (plan {CALIBRATION_TOTAL_LINKS:,}), "
        f"{total_nodes:,} nodes (plan ~{CALIBRATION_NODES:,}), "
        f"{against} against the digitised line (plan {CALIBRATION_AGAINST_LINE})"
    )

    if abs(total_links - CALIBRATION_TOTAL_LINKS) / CALIBRATION_TOTAL_LINKS > TOLERANCE:
        drifted.append(f"total links {total_links:,} against {CALIBRATION_TOTAL_LINKS:,}")
    if drifted:
        raise StageError(
            "the loader does not reproduce PLAN.md §6's calibration within "
            f"{TOLERANCE:.0%}, so nothing downstream is worth looking at:\n  "
            + "\n  ".join(drifted)
        )

    # Measured length against the length the survey states. A systematic difference
    # would mean the geometry is not what the attribute describes.
    worst = con.execute(
        """
        SELECT publisher_id, length_m, published_length_m,
               abs(length_m - published_length_m) AS d
        FROM link WHERE published_length_m IS NOT NULL
        ORDER BY d DESC LIMIT 1
        """
    ).fetchone()
    if worst and worst[3] > 1.0:
        log.detail(
            f"    largest measured-vs-published length difference: {worst[3]:,.1f} m "
            f"on {worst[0]} — the survey rounds to the metre"
        )

    return {
        "issue": issue,
        "links": total_links,
        "nodes": total_nodes,
        "against_digitised_line": against,
        "direction_unknown": unknown_dir[0],
        "self_loops": len(loops),
        "by_form": {form: {"links": n, "km": round(km, 1)} for form, n, km in rows},
    }
