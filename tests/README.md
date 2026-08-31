# tests

The build's own tests. `rewt check` runs them; so does `python -m pytest tests`.

They are not unit tests of the code's internals. Each one is here because something
specific went wrong, or because `PLAN.md` §9 says the deliverable is not done without
it. Where a test exists for a recorded reason, the docstring says which.

## What is checked, and where the requirement comes from

| file | what it holds the line on |
|---|---|
| `test_curated_identifiers.py` | **Every identifier in `data/curated/` resolves against the database.** PLAN.md §9, AGENTS.md. *A mistyped id does nothing while the stage reports success.* Also: no correction is skipped without a reason, and the validation really is part of the build. |
| `test_curated_files.py` | The curated files themselves: a `reason` in words and `evidence` on every row, no two judgements acting on one subject, connectors that are lines with length in EPSG:27700. |
| `test_licence.py` | **Licensing, which is not a formality.** Every source declares its licence and attribution; the exporter's gate refuses an encumbered source when handed one; no URL is a string literal in code; every `source_id` in the database is declared and open. |
| `test_determinism.py` | The identifier scheme survives a rebuild, the configuration fingerprint moves when the configuration does, stage fingerprints are stable and cover their upstream, ordering is declared. |
| `test_pipeline.py` | Order is enforced, not remembered: one producer per artefact, no undeclared reads, a valid topological order, a cycle is an error, every declared parameter and source exists. |
| `test_rasters.py` | **A derived raster holds at least one finite, in-range value.** WhiteboxTools' `FillBurn` returns 0 and writes an entirely NaN/3.3e38 grid when the streams it is given extend beyond the DEM. Nothing in the return code says so. |
| `test_stage1_scope.py` | **Stage 1 and nothing else.** No network table declares a date, an old course, an attestation or a flow. The one legitimate date is on a `correction`: the day a person looked, which is evidence. |
| `test_config.py` | The registry and the parameter file refuse what they are supposed to refuse — an undeclared source, a parameter with no value. |

## Markers

- `db` — needs the build database. Run `pytest -m "not db"` to skip them all.
- `interim` — reads a derived raster under `data/interim/`, read-only.

## Skips

**A test that cannot run says what is missing and why.** A silent skip is the failure
mode this repository has been bitten by twice, so there are none: an absent database,
an unbuilt raster and an unauthored curated file each skip by name.

One skip is a warning rather than a state: if the database cannot be opened because a
writer holds the lock, that is reported as a skip and not a failure. **A read-only
DuckDB connection blocks writers**, so a suite that failed the build in order to
report on it would be worse than useless. The `con` fixture prefers a connection the
process already holds — which is what `rewt check` gives it after a build — and opens
its own only when there is none.
