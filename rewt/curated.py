"""Curated files: the human judgements, which are the product (PLAN.md §7).

One diffable file per correction class under `data/curated/`, one row per judgement.
Every row carries a stable identifier for what it acts on, a `reason` in words, and
**evidence** — a place, a source, or a person and the date they looked. *A correction
without evidence is indistinguishable from a guess a year later.*

Connectors are defined by their geometry so they are GeoJSON; reversals, junctions,
exclusions and modes are CSV keyed on publisher ids.

**Every identifier in every one of them is validated against the database by a test
that runs in the build, not by hand.** A mistyped id does nothing while the stage
reports the correction as loaded. This has happened twice, and once through a column
that nothing reads — so the wrong value was invisible.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import shapely

from . import db, ids, paths

# The classes, the file each lives in, and what identifies the thing it acts on.
CLASSES = {
    "connector": "connectors.geojson",
    "reversal": "reversals.csv",
    "junction": "junctions.csv",
    "exclusion": "exclusions.csv",
    "mode": "modes.csv",
}

REQUIRED = ("reason", "evidence")


class CuratedError(ValueError):
    """A curated file is malformed, or a judgement in it lacks its evidence."""


@dataclass
class Judgement:
    """One curated row: what it acts on, what it does, why, and on what evidence."""

    kind: str
    subject: str                  # the identifier as authored
    reason: str
    evidence: str
    source_file: str
    source_row: int
    author: str | None = None
    dated: str | None = None
    fields: dict = field(default_factory=dict)
    geometry: object | None = None

    @property
    def correction_id(self) -> str:
        detail = self.fields.get("target") or self.fields.get("mode") or ""
        return ids.correction(self.kind, self.subject, str(detail))

    def place(self) -> tuple[float | None, float | None]:
        if self.geometry is not None:
            c = shapely.centroid(self.geometry)
            return float(shapely.get_x(c)), float(shapely.get_y(c))
        e, n = self.fields.get("easting"), self.fields.get("northing")
        return (float(e) if e else None, float(n) if n else None)


def _require(row: dict, kind: str, path: Path, index: int) -> None:
    for key in REQUIRED:
        value = (row.get(key) or "").strip()
        if not value:
            raise CuratedError(
                f"{paths.rel(path)} row {index}: a {kind} with no {key}. "
                "A correction without evidence is indistinguishable from a guess a "
                "year later (PLAN.md §7). Every row carries a reason in words and "
                "evidence — a place, a source, or a person and the date they looked."
            )


def read_csv(kind: str, path: Path) -> list[Judgement]:
    if not path.exists():
        return []
    out: list[Judgement] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return []
        subject_field = _subject_field(kind, reader.fieldnames, path)
        for i, row in enumerate(reader, start=2):   # row 1 is the header
            if not any((v or "").strip() for v in row.values()):
                continue
            _require(row, kind, path, i)
            subject = (row.get(subject_field) or "").strip()
            if not subject:
                raise CuratedError(
                    f"{paths.rel(path)} row {i}: no {subject_field}. A judgement that "
                    "does not say what it acts on cannot be applied or checked."
                )
            out.append(
                Judgement(
                    kind=kind,
                    subject=subject,
                    reason=row["reason"].strip(),
                    evidence=row["evidence"].strip(),
                    author=(row.get("author") or "").strip() or None,
                    dated=(row.get("dated") or "").strip() or None,
                    source_file=paths.rel(path),
                    source_row=i,
                    fields={
                        k: (v or "").strip()
                        for k, v in row.items()
                        if k not in {"reason", "evidence", "author", "dated", subject_field}
                    },
                )
            )
    return out


def _subject_field(kind: str, fieldnames: Iterable[str], path: Path) -> str:
    names = list(fieldnames)
    for candidate in ("publisher_id", "node_publisher_id", "subject"):
        if candidate in names:
            return candidate
    raise CuratedError(
        f"{paths.rel(path)}: a {kind} file must key its rows on publisher_id, "
        f"node_publisher_id or subject; it has {names}"
    )


# The National Grid origin is out at sea southwest of the Scillies, so no real feature
# in this project sits within a kilometre of it. Degrees, by contrast, are all within
# about 60 of it. That asymmetry is the test: an outer bound alone does not work,
# because degrees fall comfortably INSIDE any generous National Grid box.
_BNG_OUTER = (-100_000.0, -100_000.0, 800_000.0, 1_400_000.0)
_DEGREES_LIKE = 1_000.0


def _assert_national_grid(path: Path, feature_index: int, geom) -> None:
    """Refuse a curated geometry that is not in EPSG:27700.

    **GeoJSON is WGS84 by definition** — RFC 7946 fixes it at CRS84 and deprecates the
    `crs` member. The curated connectors deviate from that knowingly (D-035): they are
    an input to this build rather than a published artefact, their identifiers are
    digests of their own projected coordinates, and reprojecting them would rewrite
    every id. **The deviation is only safe if it is checked**, and this is the check.

    It is not hypothetical. The predecessor's connectors are GeoJSON with no `crs`
    member and are therefore degrees; compared against this project's metres they all
    landed in the ocean, and the comparison reported that this build had independently
    found none of them — which reads exactly like a substantive disagreement about
    method and was a unit error. That was caught by a result being too clean to
    believe. This catches it by arithmetic instead.
    """
    x0, y0, x1, y1 = shapely.bounds(geom)
    lo_x, lo_y, hi_x, hi_y = _BNG_OUTER
    outside = not (lo_x <= x0 and lo_y <= y0 and x1 <= hi_x and y1 <= hi_y)
    degrees_like = (
        abs(x0) < _DEGREES_LIKE and abs(x1) < _DEGREES_LIKE
        and abs(y0) < _DEGREES_LIKE and abs(y1) < _DEGREES_LIKE
    )
    if outside or degrees_like:
        raise CuratedError(
            f"{paths.rel(path)} feature {feature_index} has coordinates "
            f"({x0:,.3f}, {y0:,.3f}) - ({x1:,.3f}, {y1:,.3f}), which are not British "
            "National Grid metres. GeoJSON is WGS84 by definition (RFC 7946), so a "
            "file of degrees is what a conforming producer writes and what this "
            "project's curated files deliberately are NOT (D-035). Reproject to "
            "EPSG:27700 before authoring; do not let a degree reach the graph."
        )


def read_geojson(kind: str, path: Path) -> list[Judgement]:
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    features = doc.get("features", [])
    out: list[Judgement] = []
    for i, feature in enumerate(features, start=1):
        props = {k: v for k, v in (feature.get("properties") or {}).items()}
        _require({k: str(v) for k, v in props.items()}, kind, path, i)
        geom = shapely.geometry.shape(feature["geometry"])
        if geom.geom_type != "LineString":
            raise CuratedError(
                f"{paths.rel(path)} feature {i} is a {geom.geom_type}. A connector is "
                "defined by its geometry — a line from one place to another (§5)."
            )
        _assert_national_grid(path, i, geom)
        if shapely.length(geom) <= 0:
            raise CuratedError(
                f"{paths.rel(path)} feature {i} has zero length. A zero-length "
                "connector once reached a published dataset as a row with no country; "
                "what you want there is a junction, which adds nothing at all (§5)."
            )
        subject = str(props.get("name") or f"connector {i}")
        out.append(
            Judgement(
                kind=kind,
                subject=subject,
                reason=str(props["reason"]).strip(),
                evidence=str(props["evidence"]).strip(),
                author=(str(props.get("author") or "").strip() or None),
                dated=(str(props.get("dated") or "").strip() or None),
                source_file=paths.rel(path),
                source_row=i,
                fields={k: v for k, v in props.items()
                        if k not in {"reason", "evidence", "author", "dated"}},
                geometry=geom,
            )
        )
    return out


def read_all() -> list[Judgement]:
    """Every curated judgement, in a deterministic order."""
    out: list[Judgement] = []
    for kind, filename in CLASSES.items():
        path = paths.CURATED / filename
        if filename.endswith(".geojson"):
            out.extend(read_geojson(kind, path))
        else:
            out.extend(read_csv(kind, path))
    return sorted(out, key=lambda j: (j.kind, j.source_file, j.source_row))


# --------------------------------------------------------------------------
# Validation against the database — the test that runs in the build
# --------------------------------------------------------------------------


def resolve(judgements: Iterable[Judgement]) -> list[tuple[Judgement, str | None, str | None]]:
    """Resolve every authored identifier against the database.

    Returns (judgement, resolved_id, failure_reason). A connector resolves to nothing
    by id, because **a connector is defined by its geometry, not by any link id** —
    each end is resolved onto the network at apply time, cutting a link where there is
    no node. Snapping to the nearest node once left connectors attached to nothing
    280 m and 377 m away and the stage counted them as successes.
    """
    out = []
    known_links = {
        r[0]: r[1]
        for r in db.query("SELECT publisher_id, link_id FROM link WHERE publisher_id IS NOT NULL")
    }
    known_nodes = {
        r[0]: r[1]
        for r in db.query("SELECT publisher_id, node_id FROM node WHERE publisher_id IS NOT NULL")
    }
    for j in judgements:
        if j.kind == "connector":
            out.append((j, None, None))
            continue
        table = known_nodes if j.kind == "junction" else known_links
        what = "node" if j.kind == "junction" else "link"
        resolved = table.get(j.subject)
        if resolved is None:
            out.append(
                (
                    j,
                    None,
                    f"no {what} in the database has publisher id {j.subject!r} "
                    f"({j.source_file} row {j.source_row})",
                )
            )
            continue
        # A junction also names the link it is to be merged onto.
        target = j.fields.get("target_publisher_id") or j.fields.get("target")
        if j.kind == "junction":
            if not target:
                out.append((j, None, "a junction must name the link it merges onto"))
                continue
            if target not in known_links:
                out.append(
                    (
                        j,
                        None,
                        f"junction target link {target!r} is not in the database "
                        f"({j.source_file} row {j.source_row})",
                    )
                )
                continue
        out.append((j, resolved, None))
    return out
