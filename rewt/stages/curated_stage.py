"""Stage: read the curated judgements and validate every identifier against the database.

AGENTS.md: **a mistyped id does nothing while the stage reports success. This happened
twice in the predecessor, once through a column nothing read, so the error was
invisible. Do not rely on care.** So this stage resolves every authored identifier and
raises on any that does not resolve, naming it.

It is separate from the stage that applies the corrections, because §8's architectural
warning is to keep the trace, the curated inputs and the reporting as three separable
things — the predecessor's routing module reached ~1,600 lines and was rewritten in
place five times.
"""

from __future__ import annotations

import json

import pandas as pd
import shapely

from .. import config, curated, db, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import log

CORRECTION = artefact("correction")


@PIPELINE.stage(
    "curated",
    "read data/curated/, validate every identifier, and record the judgements",
    reads=["link", "node"],
    writes=["correction"],
    params=["repair"],
    always=True,     # the files are hand-edited; never serve a cached answer about them
)
def run() -> dict:
    judgements = curated.read_all()
    resolved = curated.resolve(judgements)

    unresolved = [(j, why) for j, r, why in resolved if why]
    if unresolved and config.param("repair.fail_on_unresolved"):
        lines = "\n  ".join(f"{j.kind} {j.subject}: {why}" for j, why in unresolved)
        raise StageError(
            f"{len(unresolved)} curated identifier(s) do not resolve against the "
            f"database. Named, because a skip is never silent:\n  {lines}"
        )

    rows = []
    for j, resolved_id, why in resolved:
        e, n = j.place()
        rows.append(
            {
                "correction_id": j.correction_id,
                "kind": j.kind,
                "subject": j.subject,
                "resolved_to": resolved_id,
                "applied": False,          # the repair stage decides this
                "skip_reason": why,
                "reason": j.reason,
                "evidence": j.evidence,
                # The row's remaining fields, carried verbatim so that a later stage
                # reads what was authored rather than a re-derivation of it. This is
                # where a junction's target link travels.
                "detail": json.dumps(j.fields, sort_keys=True, default=str),
                "author": j.author,
                "dated": j.dated,
                "source_file": j.source_file,
                "source_row": j.source_row,
                "easting": e,
                "northing": n,
                "wkb": shapely.to_wkb(j.geometry) if j.geometry is not None else None,
            }
        )

    frame = pd.DataFrame(
        rows,
        columns=[
            "correction_id", "kind", "subject", "resolved_to", "applied",
            "skip_reason", "reason", "evidence", "detail", "author", "dated",
            "source_file", "source_row", "easting", "northing", "wkb",
        ],
    )
    schema.create("correction")
    con = db.get()
    with db.registered("_corr_in", frame):
        con.execute(
            """
            INSERT INTO correction
            SELECT correction_id, kind, subject, resolved_to, applied, skip_reason,
                   reason, evidence, detail, author, dated, source_file, source_row,
                   easting, northing,
                   CASE WHEN wkb IS NULL THEN NULL ELSE ST_GeomFromWKB(wkb) END
            FROM _corr_in ORDER BY kind, source_file, source_row
            """
        )

    by_kind = con.execute(
        "SELECT kind, count(*) FROM correction GROUP BY 1 ORDER BY 1"
    ).fetchall()
    if by_kind:
        log.table("curated judgements read", ["class", "rows"], by_kind)
    else:
        log.info(
            "  data/curated/ holds no judgements yet. That is the correct state before "
            "the audit has run: the predecessor's 73 corrections are a validation set, "
            "not an input, and an audit handed its answers is not an audit (D-001)."
        )
    if unresolved:
        for j, why in unresolved:
            log.warn(f"unresolved {j.kind} {j.subject}: {why}")

    return {"judgements": len(rows), "unresolved": len(unresolved)}
