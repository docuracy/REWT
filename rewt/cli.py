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
