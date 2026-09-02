# AGENTS.md

Working conventions for this repository. **`PLAN.md` is the specification — what to build
and why.** This file is the shorter, duller thing: how to work here, and what is easy to
get wrong. Read `PLAN.md` first, then this, then start.

## The one rule that matters most

**Stage 1 and nothing else.** The deliverable is a modern river network in which water can
get from any stretch to the sea. It makes no historical claim whatever. Dates, old
courses, attestation, navigability, flow modelling, tiles, maps and releases all belong to
later stages.

The failure mode is not refusing this outright; it is drifting into it a little at a time
because a field looked easy to add. **If a task requires knowing what year it is, it is
not Stage 1.** Say so and stop.

## How to work

- **Run everything from the repository root.** Paths in code are relative — `Path("data/raw")`.
  Never `cd` into a subdirectory to make a script work.
- **Stages are subcommands of one entry point**, and the whole build is one command. If a
  step only runs when a person remembers to run it, it is not part of the build.
- **Declare every input in `conf/sources.yml`. No URL is ever hard-coded in code.**
  Thresholds and parameters live in configuration too, not as literals in a function.
- **The four Ordnance Survey products are open and need no API key.** Do not build an
  authentication path you will not use.
- **The database is a build artefact, not a source of truth.** Gitignored, rebuilt from
  scratch, never hand-edited. Never write code that assumes state survives a rebuild. The
  sources of truth are `data/raw/` (immutable, checksummed) and `data/curated/`
  (hand-authored, committed).
- **One module owns the database connection.** Everything else asks it for one. This is
  what keeps a move to PostGIS cheap, and it is why there is one module and not six.
- **A read-only DuckDB connection blocks writers.** Anything long-running that holds one —
  a viewer, a served map, a notebook — must be stopped before a build.

## Conventions that are easy to get wrong

- **EPSG:27700 throughout; EPSG:4326 only at export.** This project does metric work —
  buffers, distances, gradients — which needs a projected CRS. Reproject once, at the
  boundary, in the loader or the exporter, and nowhere else.
- **Store nodes already oriented**, so `from_node` is upstream and `to_node` downstream on
  every row. OS encodes direction relative to the digitised line; resolve it once at load
  or four separate places will have to remember to flip it.
- **Never delete a geometry to correct it.** Retire it with a reason and keep it. This is a
  research dataset and the audit trail is part of the product — a retired link is how a
  reader tells a correction from an omission.
- **A human judgement belongs in `data/curated/`**, as a diffable file, with a `reason` in
  words and `evidence` — a place, a source, or a person and the date they looked. If you
  are about to hard-code a decision about a particular river in Python, stop.
- **Every identifier in `data/curated/` is validated against the database by a test that
  runs in the build.** A mistyped id does nothing while the stage reports success. This
  happened twice in the predecessor, once through a column nothing read, so the error was
  invisible. Do not rely on care.
- **Fail loudly.** Topology errors, unresolved identifiers, corrections whose targets do
  not exist, sources that cannot be fetched — all reported, never silently skipped. The
  interesting findings of this project live in exactly those reports.
- **Name every skip.** A correction that finds no target must say so by identifier. Eleven
  of twenty-five once did nothing silently, including the largest single defect in the
  country.

## Reporting findings

- **Report at the place, not only in the total.** Emit a coordinate with every finding.
  Every serious defect in the predecessor was invisible in national figures — 481 km of
  new holes once arrived alongside a network that had grown in both count and length.
- **Report per basin as well as nationally.** A national 97% hides a basin at 40%, and the
  basin at 40% is the entire finding.
- **Looking beats measuring.** When you have fixed something, go and look at the place on
  a map. Aggregates have repeatedly agreed that a broken thing was fixed.
- **Do not quote the predecessor's results as this repository's.** The calibration figures
  in `PLAN.md` §6 are measurements of *OS Open Rivers as shipped* and are legitimate to
  check against. Findings about the reconstructed network are not, and must be re-earned.

## Decisions

**Append to `DECISIONS.md`**: dated, numbered, one entry per design decision, with the
reasoning and not just the outcome. Never silently reverse one that is recorded there — if
you disagree with an earlier decision, write a new entry saying so and why.

`PLAN.md` names its own assumed defaults — Python, DuckDB with its spatial extension,
stages under one entry point. They are defaults, not commandments. Overturn any of them if
there is a better way, and record the reason.

## Licensing, which is not a formality

**This repository is private and is intended to become public.** Everything in it must
stay open and redistributable.

- Every source carries `access` and `redistribution` in `conf/sources.yml`. The exporter
  refuses to write a feature whose source is not openly licensed. Keep that check; do not
  work around it.
- **Never commit licence-encumbered data**, and never add a source without recording its
  licence and required attribution first.
- **Provenance travels as a pointer.** Wherever a short attribution appears, it may never
  attribute less than `conf/sources.yml` does.

## The predecessor

`Premodern Rivers` is a private repository whose public write-up is at
<https://docuracy.github.io/premodern-rivers/guide/>. `PLAN.md` §8 summarises what it
learned. **Do not import code or data from it.** Read it for reasoning; the point of
starting again is to leave its accumulated assumptions behind.

Its curated corrections are a **validation set**, to be consulted after your own audit
works and never as an input to it. An audit handed its answers is not an audit.

## Two performance findings, each of which cost a day

- **Spatial self-joins over ~120,000 links are prohibitively slow.** Join on rounded
  endpoint coordinates instead; a ten-minute query becomes seconds.
- **Per-row inserts that parse geometry per row are pathological** — ten minutes for
  122,000 rows where a single bulk insert took moments.

## Working as a team

Six agents worked this repository in parallel, with hard directory ownership and a standing
duty to check each other's artefacts. **[TEAM.md](TEAM.md) is how to start them** — the six
scopes, the startup order, what to tell each session, and the standing orders that made the
arrangement catch what the build could not. Read it if you are the only session running.
