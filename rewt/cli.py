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

import os
import sys
from typing import Optional

import typer

from . import config, db, paths, pipeline
from .report import log

app = typer.Typer(
    add_completion=False,
    # NOT typer's own help. This project runs typer 0.15 against click 8.5, whose
    # `Parameter.make_metavar()` gained a required argument, so typer's rich renderer
    # raises a TypeError: **`rewt` with no arguments gave a traceback rather than a
    # reminder.** That is the first thing a person types and the moment they most need
    # an answer. Rendered below instead of moving a dependency under a working build —
    # the listing is a few lines and cannot break on a version.
    no_args_is_help=False,
    help="REWT Stage 1 — a traversable modern river network for England and Wales.",
)


def _import_stages() -> None:
    from . import stages  # noqa: F401  (registers every stage)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    quiet: bool = typer.Option(False, "--quiet", "-q", help="suppress progress"),
) -> None:
    log.quiet = quiet
    paths.check_root()
    # ONLY WHERE THEY ARE NEEDED. This imported every stage — and with them rasterio,
    # geopandas, scipy and duckdb — before running ANY command, including `rewt team`,
    # which reads a small JSON file and needs none of it. Warm, that is a second and
    # four CPU-seconds; cold, on a machine that has not touched the geospatial stack, it
    # is long enough to look like a hang, which is what it looked like.
    #
    # The stage registry is needed by the commands that plan, run or check a build.
    # Nothing else touches it.
    if ctx.invoked_subcommand in {
        "build", "run", "plan", "status", "check", "validate", "acquire", "sources",
        "candidates", "propose", "propose-outlets", "propose-reversals",
        "release-check", "viewer-data",
    }:
        _import_stages()
    if ctx.invoked_subcommand is not None:
        return
    log.rule("REWT — Stage 1")
    log.table(
        "what you are most likely to want",
        ["command", "what it does"],
        [
            ["rewt team", "who holds which role, and the other team commands"],
            ["rewt team claim", "take a role, and name this terminal tab"],
            ["rewt team shutdown", "clear the board when stopping the team"],
            ["rewt build", "run the pipeline — only the implementer does this"],
            ["rewt viewer-data", "build the map's tiles and layers from published/"],
            ["rewt release-check TAG", "refuse a release that is not clean, current, green"],
            ["rewt release-notes TAG", "the notes, generated from the build"],
            ["rewt status", "what the last build did"],
        ],
    )
    names = sorted(c.name for c in typer.main.get_command(app).commands.values() if c.name)
    log.detail("all commands: " + ", ".join(names))
    log.detail("this is bin/rewt — to type `rewt` anywhere: "
               "ln -s $PWD/bin/rewt ~/.local/bin/rewt")
    log.info("TEAM.md starts the other agents. AGENTS.md is how to work here. "
             "PLAN.md is what is being built.")


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
def sources(
    verify: bool = typer.Option(
        False, "--verify", help="digest the cached bytes and check them against the file"
    ),
) -> None:
    """The declared inputs, with their licences and required attribution.

    With `--verify`, computes what this repository can actually say about each source's
    bytes rather than repeating the `status:` field, which nothing writes.
    """
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

    if verify:
        checks = []
        for src in config.sources():
            v = acquire.verification(src.id)
            checks.append((src.id, v["status"], v["why"] or "—",
                           src.get("status", default="—")))
        log.table(
            "what this repository can actually say about each source's bytes",
            ["id", "computed", "why", "the file claims"],
            checks,
        )
        wrong = [c for c in checks if c[1] == "MISMATCH"]
        drifted = [
            c for c in checks
            if c[3] == "verified" and c[1] != "verified"
        ]
        if wrong:
            log.error(
                f"{len(wrong)} source(s) do not match their declared checksum: "
                + ", ".join(c[0] for c in wrong)
            )
        if drifted:
            log.warn(
                f"{len(drifted)} source(s) are recorded as 'verified' in the file but "
                "this repository cannot confirm it: "
                + ", ".join(c[0] for c in drifted)
                + ". The field is a claim, not evidence."
            )
        if wrong or drifted:
            raise typer.Exit(1)
        return
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


@app.command("viewer-data")
def viewer_data_cmd(
    layers_only: bool = typer.Option(False, "--layers-only",
                                     help="skip the tiles, which take minutes"),
) -> None:
    """Build what the map reads: one PMTiles archive and nine small layers.

    **Built here and not in CI.** The workflow that deploys the site cannot make this
    — it would need OS Open Rivers, Terrain 50, EMODnet and the hours the terrain stage
    takes. So it is built from a finished `published/`, attached to the release, and
    fetched by `pages.yml` at deploy time. Nothing derived is committed either way.
    """
    from . import tiles

    tiles.build_layers()
    if not layers_only:
        tiles.build_tiles()
        # Never a flag on its own: the archive is read back and counted. A build that
        # dropped the defects it exists to show is worse than no map.
        tiles.verify()
        # PACKED HERE AND NOWHERE ELSE. The tar is what the release attaches and what
        # pages.yml serves, so building the tiles without repacking leaves the published
        # map a different pass from the GeoPackage beside it — two artefacts, each
        # internally consistent, never compared. rewt-6a found exactly that: a tar
        # ninety minutes older than the tiles on disk, with counts that agreed.
        tiles.pack()


@app.command("team")
def team_cmd(
    # DEFAULTS TO status, NOT claim. It defaulted to claim, so `rewt team` — which reads
    # like a question — took a role. A bare command that looks like a query must not
    # mutate anything, and claiming is a mutation another session can see.
    action: str = typer.Argument("status", help="status | claim | release | shutdown"),
    role: Optional[str] = typer.Option(None, "--role", help="a specific role"),
    name: Optional[str] = typer.Option(None, "--name", help="this session's name"),
    force: bool = typer.Option(False, "--force", help="retake a role whose holder has gone"),
) -> None:
    """Take a role, see who holds what, or give one back.

    Six sessions can see each other's names through `ListAgents` and cannot tell which is
    which — the names are new after every restart and `TEAM.md` names roles, not sessions.
    Claiming joins the two, in a file anybody can read, without a master session handing
    out identities it cannot prove it is entitled to hand out.
    """
    from . import team

    if action == "status":
        held = team.read_all()
        # THE ANSWER ON STDOUT, the presentation on stderr. `log` writes to stderr, so
        # every byte of this went there and `rewt team status > roles.txt` wrote an empty
        # file and exited 0 — for a command whose purpose is to be read by another
        # program. Found by rewt-1d, who redirected it.
        #
        # **Only when stdout is not a terminal.** Printing both gave a person the plain
        # roster AND the table, one above the other, saying the same thing twice. A pipe
        # wants the tab-separated form; a person wants the table; nobody wants both.
        if not sys.stdout.isatty():
            for r, _owns, _task in team.ROLES:
                c = held.get(r)
                print(f"{r}\t{c.session if c else '-'}\t{c.claimed_at if c else '-'}")
        log.detail("rewt team claim [--role R]   take a role, and name this terminal tab")
        log.detail("rewt team release --name S    give one back")
        log.detail("rewt team shutdown           clear the board when stopping the team")
        log.table(
            "roles",
            ["role", "held by", "state", "owns"],
            [[r,
              f"{held[r].session}" if r in held else "—",
              (f"claimed {held[r].age_hours:,.1f} h ago" if r in held else "free"),
              owns]
             for r, owns, _ in team.ROLES],
        )
        return

    if action == "release":
        try:
            freed = team.release(role, name, force)
        except PermissionError as exc:
            log.error(str(exc))
            raise typer.Exit(1) from None
        if not freed:
            held = team.read_all()
            if role:
                log.warn(f"{role} is not on the board. Held: "
                         + (", ".join(f"{r} ({c.session})" for r, c in held.items())
                            or "nothing"))
            else:
                log.warn("nothing released — name the role with --role or the session "
                         "with --name.")
            raise typer.Exit(1)
        log.done(f"released {', '.join(freed)}")
        return

    if action == "shutdown":
        freed = team.shutdown()
        log.done(f"cleared {len(freed)} claim(s): {', '.join(freed) or 'none were held'}")
        log.detail("the board is clean; the next session to claim becomes the implementer")
        return

    if action != "claim":
        log.error(f"unknown action {action!r}; use claim, status, release or shutdown")
        raise typer.Exit(1)

    # A ROLE CLAIMED FROM A BARE TERMINAL IS HELD BY NOBODY, and five other sessions
    # will read it as taken. The board exists to say which agent is doing what; a person
    # typing the command is not an agent, and the honest answer is to refuse rather than
    # record a claim nothing is behind.
    if not team.in_agent_shell() and not name:
        log.error("this is a terminal, not an agent session — a role claimed here would "
                  "be held by nobody, and the other sessions would read it as taken.")
        log.detail("`rewt team` shows the board. If you really mean to hold a role "
                   "yourself, say who you are: rewt team claim --name stephen")
        raise typer.Exit(1)
    if team.in_agent_shell() and not name:
        log.warn("no --name given, so this claim records a session id rather than the "
                 "name your peers address you by. Pass --name with the name ListAgents "
                 "shows for you.")

    # An expected condition is a message and an exit code. Both of these arrived as raw
    # tracebacks — an unknown role as a KeyError, a role already held as a RuntimeError —
    # three lines below a branch that does it correctly for an unknown action. `--role
    # viewer` is the easy slip, because `viewer` is what the directory is called.
    try:
        got, displaced = team.claim(role, name, force)
    except KeyError:
        log.error(f"no such role {role!r}. The roles are: "
                  + ", ".join(r for r, _, _ in team.ROLES))
        raise typer.Exit(1) from None
    except RuntimeError as exc:
        log.error(str(exc))
        raise typer.Exit(1) from None
    _, owns, opening = team.BY_NAME[got]
    # The role on stdout, so `role=$(rewt team claim)` works — but not to a terminal,
    # where it would appear twice: once bare and once inside the message below.
    if not sys.stdout.isatty():
        print(got)
    if displaced is not None:
        # SAY WHAT HAPPENED, not what is comfortable. This claimed the role had been
        # "held by a process that has gone" — a true-looking sentence about something
        # nothing here can know, printed identically whether a dead session was
        # reclaimed or a live colleague evicted.
        log.warn(f"{got} was held by {displaced.session}, claimed "
                 f"{displaced.age_hours:,.1f} h ago, and you have taken it. If that "
                 "session is still running it has just lost its role and has not been "
                 "told — check `ListAgents`.")
    log.done(f"you are the {got} session")
    log.detail(f"you own: {owns}")
    # SUGGESTED, NOT ISSUED. This printed "opening task: …" and the first agent to claim
    # a role read it as an instruction and did it — opening a browser unasked. A claim
    # says who you are; what to do next is the person's call, not the board's.
    log.detail(f"suggested first task, if nobody has told you otherwise: {opening}")
    log.info("Read TEAM.md for the scopes and the standing orders. Other sessions are "
             "found with ListAgents; `rewt team status` says which of them is which.")


@app.command("citation")
def citation_cmd(tag: str = typer.Argument(..., help="the tag this edition carries")) -> None:
    """Write `CITATION.cff`, at the repository root and beside the published data.

    Two copies of one generated string, and they are for different readers: GitHub
    renders the root one as *Cite this repository*, and the published one travels with
    the release so that someone holding the GeoPackage can find out how to credit it.
    Neither is hand-written — authorship is declared once, in `.zenodo.json`.
    """
    from . import release

    text = release.citation_file(tag)
    for target in (paths.ROOT / "CITATION.cff", paths.PUBLISHED / "CITATION.cff"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    log.done(f"CITATION.cff written for {tag}, at the root and in published/")


@app.command("release-notes")
def release_notes_cmd(
    tag: str = typer.Argument(..., help="the tag this release will carry"),
    out: Optional[str] = typer.Option(None, "--out", help="write here instead of stdout"),
) -> None:
    """Generate the release notes from the build, never from memory.

    Every figure is read out of `published/`. A note that quotes a number by hand is
    right once and wrong at the next edition, and authoritative in both states.
    """
    from . import release

    text = release.notes(tag)
    if out:
        paths.ROOT.joinpath(out).write_text(text, encoding="utf-8")
        log.done(f"release notes for {tag} written to {out}")
    else:
        print(text)


@app.command("release-check")
def release_check_cmd(tag: str = typer.Argument(..., help="the tag to be cut")) -> None:
    """Refuse to release a build that is not current, clean and green.

    **The three ways an alpha embarrasses you**, each checked rather than assumed:
    a working tree with uncommitted changes, so nobody can reconstruct what was
    released; a `published/` older than the code that claims to have made it; and a
    suite that was last green before the last edit.
    """
    import subprocess

    from . import release

    problems: list[str] = []

    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=paths.ROOT
    ).stdout.strip()
    tracked_dirty = [l for l in dirty.splitlines() if not l.startswith("??")]
    if tracked_dirty:
        problems.append(
            f"{len(tracked_dirty)} tracked file(s) are modified. A release nobody can "
            "reconstruct is not a release:\n      " + "\n      ".join(tracked_dirty[:6])
        )

    network = paths.PUBLISHED / "rewt_stage1_network.gpkg"
    if not network.exists():
        problems.append("published/rewt_stage1_network.gpkg does not exist; run `rewt build`")
    else:
        # ASK THE BUILD, NOT THE FILESYSTEM. The first version compared
        # published/'s mtime against the newest rewt/*.py and was wrong for a reason
        # worth keeping: `test_a_stage_fingerprint_covers_the_modules_the_stage_calls`
        # perturbs rewt/ids.py and restores it, which leaves its mtime AFTER the
        # export — so every green build looked stale for ever. A clock is a proxy;
        # the fingerprint is the thing itself (D-049).
        _import_stages()
        stale = pipeline.stale_stages()
        if stale:
            problems.append(
                "the build does not correspond to the code being released — these "
                f"stages would re-run: {', '.join(stale)}. Run `rewt build`."
            )

    # The documentation site states that the audit shipped with the data is the
    # authority for every figure on it. That promise rests on the audit being its own
    # asset rather than a member of an archive, and folding published/ into one file
    # would read as tidiness in a diff. This is the only place the two are connected.
    if not release.audit_is_its_own_asset():
        problems.append(
            f"{release.MACHINE_READABLE_AUDIT} is not attached as its own asset. The "
            "documentation site promises the audit is fetchable with the data; inside "
            "an archive it is machine-readable in principle and unreachable in practice."
        )
    try:
        release.assets()
    except FileNotFoundError as exc:
        problems.append(str(exc))

    # Two renderings of one licence obligation, each checked against the manifest that
    # is the authority for both. A DOI is the point after which a wrong attribution
    # cannot be withdrawn, so it is checked here rather than only on the site.
    problems += release.attribution_drift()
    # The map that ships and the data it was built from must be one pass.
    problems += release.viewer_data_drift()
    # Excluding a file from the DOI must not remove it from the release.
    problems += release.excluded_assets_still_ship()

    # The citation must name the edition being cut, not the last one. It is generated,
    # so a stale copy means someone released without running `rewt citation`.
    want = release.citation_file(tag)
    for where in (paths.ROOT / "CITATION.cff", paths.PUBLISHED / "CITATION.cff"):
        if not where.exists():
            problems.append(f"{where.name} is missing from {where.parent.name}/; "
                            f"run `rewt citation {tag}`")
        elif where.read_text() != want:
            problems.append(f"{where.parent.name}/CITATION.cff does not match {tag}; "
                            f"run `rewt citation {tag}`")

    # RELEASE-CHECK WAS BLOCKING ITS OWN TEST RUN. `stale_stages()` above opens the
    # database read-write and the connection is a module-level singleton, so the pytest
    # subprocess could not take even a read lock — 18 tests skipped themselves, pytest
    # exited 0, and the guard below reported "a build holds its lock" when the holder
    # was this very command. Released before the suite runs, and nothing after this
    # point needs it.
    db.close()
    rc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-rs"],
        capture_output=True, text=True, cwd=paths.ROOT,
    )
    if rc.returncode != 0:
        problems.append("the suite is not green:\n      " + rc.stdout.strip().splitlines()[-1])
    # A SUITE THAT SKIPPED IS NOT A SUITE THAT PASSED. A running build holds the DuckDB
    # write lock, every test that reads the database skips itself with a named reason,
    # and pytest still exits 0 — so `release-check` would have called 25 unrun tests
    # green. The skip is right (a read-only connection would block the writer); treating
    # its exit code as an answer is not.
    locked = [l for l in rc.stdout.splitlines() if "Conflicting lock is held" in l]
    if locked:
        problems.append(
            f"{len(locked)} test(s) could not read the database because something "
            "holds its lock, and pytest still exited 0. A release must not be cut on a "
            "suite that skipped the database. If no build is running, the holder is "
            "another agent's query — wait and re-run."
        )

    if problems:
        log.error(f"{len(problems)} reason(s) not to cut {tag}:")
        for p_ in problems:
            log.error(f"  - {p_}")
        raise typer.Exit(1)

    text = release.notes(tag)
    log.done(f"{tag} is ready: tree clean, build current, suite green")
    log.info(f"notes are {len(text.splitlines())} lines; `rewt release-notes {tag}` to see them")


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
