"""The one entry point. Every stage is a subcommand of it, and the whole build is one
command (AGENTS.md).

    rewt build            # empty checkout to finished network
    rewt run <stage>      # one stage, with its dependencies
    rewt plan             # what would run, in order
    rewt status           # what has run, and whether it is still current

If a step only runs when a person remembers to run it, it is not part of the build.
That is why there is no separate audit script: `audit` is a stage, and `build` runs it.
"""

from __future__ import annotations

import sys
from typing import Optional

import typer

from . import config, db, paths, pipeline
from .report import log

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="REWT Stage 1 — a traversable modern river network for England and Wales.",
)


def _import_stages() -> None:
    from . import stages  # noqa: F401  (registers every stage)


@app.callback()
def main(quiet: bool = typer.Option(False, "--quiet", "-q", help="suppress progress")) -> None:
    log.quiet = quiet
    paths.check_root()
    _import_stages()


@app.command()
def build(
    force: bool = typer.Option(False, "--force", help="re-run every stage, cache or no"),
) -> None:
    """One command, empty checkout to finished network."""
    pipeline.run(force_all=force)
    _final_word()


@app.command()
def run(
    stage: list[str] = typer.Argument(..., help="stage name(s)"),
    force: bool = typer.Option(False, "--force", help="re-run the named stages"),
) -> None:
    """Run one or more stages, with whatever they depend on."""
    unknown = [s for s in stage if s not in pipeline.PIPELINE]
    if unknown:
        raise typer.BadParameter(
            f"unknown stage(s) {', '.join(unknown)}. "
            f"Known: {', '.join(pipeline.PIPELINE.names)}"
        )
    pipeline.run(stage, force=force)


@app.command("plan")
def plan_cmd(stage: Optional[list[str]] = typer.Argument(None)) -> None:
    """What would run, in order, and what each reads and writes."""
    pipeline.run(stage or None, dry_run=True)


@app.command()
def status() -> None:
    """What has run, whether it is still current, and what is in the database."""
    pipeline.ensure_ledger()
    rows = []
    upstream: dict[str, str] = {}
    for name in pipeline.PIPELINE.names:
        st = pipeline.PIPELINE[name]
        deps = {
            d: upstream[d]
            for d in pipeline.PIPELINE.dependencies(name)
            if d != name and d in upstream
        }
        want = st.fingerprint(deps)
        upstream[name] = want
        have = pipeline.recorded_fingerprint(name)
        if have is None:
            state = "not run"
        elif have != want:
            state = "stale"
        else:
            state = "current"
        rows.append((name, state, st.summary))
    log.table("stages", ["stage", "state", "summary"], rows)
    log.table("tables", ["table", "rows"], db.summarise())


@app.command()
def sources() -> None:
    """The declared inputs, with their licences and required attribution."""
    from . import acquire

    rows = []
    for src in config.sources():
        acq = acquire.acquisition(src.id)
        rows.append(
            (
                src.id,
                src.publisher,
                src.licence.split("—")[0].strip(),
                "yes" if src.is_redistributable else "no",
                acq.issue if acq else "not acquired",
            )
        )
    log.table("conf/sources.yml", ["id", "publisher", "licence", "redistributable", "issue"], rows)
    typer.echo(config.sources().attribution_block())


@app.command()
def acquire(
    source: Optional[list[str]] = typer.Argument(None, help="source id(s); default all national"),
    force: bool = typer.Option(False, "--force", help="re-fetch even if the digest matches"),
) -> None:
    """Fetch declared sources. No URL is hard-coded; every one comes from the file."""
    from . import acquire as acq_mod

    for source_id in source or acq_mod.national_sources():
        acq_mod.fetch(source_id, force=force)


@app.command()
def candidates(
    top: int = typer.Option(60, help="how many to write out"),
    radius: float = typer.Option(2000.0, help="how far to look for a reachable node, m"),
) -> None:
    """Propose adjudications for the audit's defects. It proposes; it does not decide.

    Writes a ranked candidate list with the evidence for each of PLAN.md §5's shapes
    side by side, so that authoring a curated judgement is a reading rather than a
    search. Nothing here is a correction until a person writes it into data/curated/
    with a reason and evidence of their own.
    """
    from . import candidates as cand

    frame = cand.build(radius_m=radius)
    cand.summarise(frame)
    if frame.empty:
        return
    out = paths.PUBLISHED / "audit" / "candidates.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    log.info(f"  {len(frame):,} candidates written to {paths.rel(out)}")
    log.frame(
        "the largest defects, by the catchment standing above them",
        frame.head(top)[
            ["name", "form", "upstream_km", "suggests", "junction_gap_m",
             "connector_gap_m", "sink_e", "sink_n"]
        ],
        top,
    )


@app.command()
def propose(
    max_gap: float = typer.Option(100.0, help="furthest a connector may reach, m"),
    name_rule: str = typer.Option(
        "same", help="'same' watercourse name, 'compatible' names, or 'any' (canals)"
    ),
    forms: str = typer.Option("", help="restrict to these forms, comma-separated"),
    write: bool = typer.Option(False, "--write", help="append to data/curated/"),
) -> None:
    """Draft connectors for the strongest evidence class and, with --write, author them.

    The rule is narrow and is stated in `rewt.candidates.propose_connectors`: a river
    that stops at a dead end and resumes under the same name within `max_gap`, where
    the far side already reaches tidal water and the line between them crosses no other
    watercourse.

    It is worth running more than once. **The crawl is what makes it iterate**: closing
    a gap at the bottom of a stranded region admits everything above it, so links that
    had no draining neighbour on one pass have one on the next. That is D-005's whole
    argument, and it is why this proposes from the repaired graph rather than from the
    survey.
    """
    import json

    from . import candidates as cand

    drafts, rejected = cand.propose_connectors(
        max_gap_m=max_gap,
        name_rule=name_rule,
        only_forms=tuple(f.strip() for f in forms.split(",") if f.strip()) or None,
    )
    path = paths.CURATED / "connectors.geojson"

    existing_ends: set[tuple] = set()
    existing: list = []
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        existing = doc.get("features", [])
        for feature in existing:
            coords = feature["geometry"]["coordinates"]
            existing_ends.add((round(coords[0][0], 2), round(coords[0][1], 2)))

    import shapely

    fresh = [
        d for d in drafts
        if (round(float(shapely.get_coordinates(d["geometry"])[0][0]), 2),
            round(float(shapely.get_coordinates(d["geometry"])[0][1]), 2)) not in existing_ends
    ]
    log.info(
        f"  {len(drafts):,} drafts, {len(fresh):,} of them new, "
        f"{len(rejected):,} rejected by the crossing check"
    )
    if fresh:
        log.frame(
            "new drafts, largest catchment first",
            __import__("pandas").DataFrame(
                [
                    {"river": d["name"], "km above": round(d["upstream_km"], 1),
                     "gap m": round(d["gap_m"], 1)}
                    for d in sorted(fresh, key=lambda x: -x["upstream_km"])
                ]
            ),
            15,
        )
    for node, why in rejected[:10]:
        log.detail(f"    rejected {node}: {why}")

    if not write:
        log.info("  nothing written; pass --write to author these into data/curated/")
        return
    if not fresh:
        log.info("  nothing new to author")
        return

    merged = existing + [
        {
            "type": "Feature",
            "geometry": json.loads(shapely.to_geojson(d["geometry"])),
            "properties": {k: v for k, v in d.items() if k != "geometry"},
        }
        for d in fresh
    ]
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "name": "connectors",
                "crs": {"type": "name",
                        "properties": {"name": "urn:ogc:def:crs:EPSG::27700"}},
                "features": merged,
            },
            indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )
    log.done(f"{len(merged):,} connectors in {paths.rel(path)} ({len(fresh):,} new)")


@app.command()
def validate() -> None:
    """Compare the audit against the predecessor's 73 corrections (PLAN.md §9).

    A validation set, consulted after the audit works and never as an input to it
    (D-001). It reads a directory outside this repository, changes nothing, and writes
    up the agreements and the disagreements.
    """
    from . import validate as val

    if not val.PREDECESSOR.exists():
        log.warn(
            f"{val.PREDECESSOR} is not present. The predecessor is a private "
            "repository; the comparison is skipped rather than faked."
        )
        raise typer.Exit(0)
    frame = val.compare()
    out = val.write_report(frame, paths.PUBLISHED / "audit" / "validation.md")
    recoverable = frame[frame["we_found_defect"].notna()]
    agreed = int(recoverable["we_found_defect"].astype(bool).sum())
    log.table(
        "the predecessor's 73 corrections, compared by place",
        ["measure", "value"],
        [
            ("corrections in the validation set", len(frame)),
            ("places recoverable in issue 2026-04", len(recoverable)),
            ("places whose link id no longer exists", len(frame) - len(recoverable)),
            ("defects this audit found independently", agreed),
            ("agreement on the recoverable places", f"{agreed / max(len(recoverable), 1):.0%}"),
        ],
    )
    log.done(f"written up in {paths.rel(out)}")


@app.command("propose-outlets")
def propose_outlets_cmd(
    max_gap: float = typer.Option(250.0, help="furthest a connector may reach, m"),
    min_km: float = typer.Option(1.0, help="smallest component to bother with"),
    write: bool = typer.Option(False, "--write", help="append to data/curated/"),
) -> None:
    """Connect a stranded COMPONENT to draining water at their closest approach.

    Every other rule proposes at a dead end, which is the wrong anchor for the case
    D-011 describes: a canal reaches the sea through a structure, and the structure is
    where the two waters come closest, not where the line ends.
    """
    import json

    import shapely

    from . import candidates as cand

    drafts, rejected = cand.propose_component_outlets(
        max_gap_m=max_gap, min_component_km=min_km
    )
    path = paths.CURATED / "connectors.geojson"
    doc = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"type": "FeatureCollection", "name": "connectors",
              "crs": {"type": "name",
                      "properties": {"name": "urn:ogc:def:crs:EPSG::27700"}},
              "features": []}
    )
    seen = {
        (round(f["geometry"]["coordinates"][0][0], 2),
         round(f["geometry"]["coordinates"][0][1], 2))
        for f in doc["features"]
    }
    fresh = [
        d for d in drafts
        if (round(float(shapely.get_coordinates(d["geometry"])[0][0]), 2),
            round(float(shapely.get_coordinates(d["geometry"])[0][1]), 2)) not in seen
    ]
    log.info(
        f"  {len(drafts):,} drafts, {len(fresh):,} new, "
        f"{len(rejected):,} refused as 0 m crossings (D-016)"
    )
    for _, why in rejected[:5]:
        log.detail(f"    {why[:150]}")
    if not write or not fresh:
        if not write:
            log.info("  nothing written; pass --write to author these")
        return
    doc["features"].extend(
        {
            "type": "Feature",
            "geometry": json.loads(shapely.to_geojson(d["geometry"])),
            "properties": {k: v for k, v in d.items() if k != "geometry"},
        }
        for d in fresh
    )
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    log.done(f"{len(doc['features']):,} connectors ({len(fresh):,} new)")


@app.command("propose-reversals")
def propose_reversals_cmd(
    write: bool = typer.Option(False, "--write", help="append to data/curated/"),
    flat_water: bool = typer.Option(
        False, "--flat-water", help="also propose canals and lakes (§5 says do not)"
    ),
) -> None:
    """Draft reversals: links whose OTHER end already drains to the sea.

    Like `propose`, this is worth running again after a repair, because the set of
    ends that already drain grows every time a gap is closed.
    """
    import csv

    from . import candidates as cand

    drafts, rejected = cand.propose_reversals(allow_flat_water=flat_water)
    path = paths.CURATED / "reversals.csv"
    fields = ["publisher_id", "reason", "evidence", "author", "dated"]

    existing: list[dict] = []
    seen: set[str] = set()
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = [r for r in csv.DictReader(fh) if r.get("publisher_id")]
        seen = {r["publisher_id"] for r in existing}

    fresh = [d for d in drafts if d["publisher_id"] not in seen]
    log.info(
        f"  {len(drafts):,} drafts, {len(fresh):,} of them new, "
        f"{len(rejected):,} refused"
    )
    for pub, why in rejected[:6]:
        log.detail(f"    refused {pub}: {why}")
    if not write:
        log.info("  nothing written; pass --write to author these")
        return
    if not fresh:
        log.info("  nothing new to author")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in existing:
            w.writerow({k: row.get(k, "") for k in fields})
        for d in sorted(fresh, key=lambda x: -x["upstream_km"]):
            w.writerow({k: d[k] for k in fields})
    log.done(f"{len(existing) + len(fresh):,} reversals in {paths.rel(path)} "
             f"({len(fresh):,} new)")


@app.command()
def check() -> None:
    """Run the build's own tests: curated identifiers, licences, determinism."""
    import pytest

    code = pytest.main(["-q", str(paths.ROOT / "tests")])
    raise typer.Exit(code)


def _final_word() -> None:
    from . import acquire as acq_mod

    log.rule("built")
    for src in config.sources():
        a = acq_mod.acquisition(src.id)
        if a:
            log.detail(f"  {src.id}: issue {a.issue}")
    log.info(f"  published to {paths.rel(paths.PUBLISHED)}")


def entry() -> None:
    try:
        app()
    except pipeline.StageError as exc:
        log.error(str(exc))
        sys.exit(2)


if __name__ == "__main__":
    entry()
