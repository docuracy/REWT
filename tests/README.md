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
| `test_published_output.py` | **The deliverable as a reader finds it.** PLAN.md §7. Reads `published/` only, so it holds no lock: every correction visible in the network, the audit's headline figures re-derived from the artefact that published them, and **every in-scope total published anywhere under `published/audit/` the same number** (D-079). |
| `test_basins_and_the_sea.py` | **A catchment may not contain the sea.** The tidal surface is not removed before delineation, so a shared estuary accumulates to one sink and the firth falls inside the basin. Threshold-free, because the enclosure distribution is continuous from one 50 m cell upward and any km cut would be a preference. |
| `test_derived_distributions.py` | The **shape** of what was derived, not merely its validity: no single basin holds most of the country, the median basin is not a sliver, this project introduced no self-loop. |
| `test_docs_sources.py` | The public citations page, which must not drift from the manifest — and every count on it derived rather than typed. |
| `test_release_assets.py` | The release's own artefacts, including that each drift check **can actually fail**. A gate that has never been seen to fail is not known to be a gate. |
| `test_repository_is_publishable.py` | **This repository is intended to become public.** No credential in a tracked file, no build artefact tracked, the curated judgements tracked. |
| `test_team.py` | The role board: a claim is recorded with who and when, a held role is refused, and exactly one process wins a contested one. |
| `test_tracer.py` | The tracer mints no identifier in the browser, composes none outside its own module, and draws and names every vertex origin it emits. |

## Failures that are expected, and what clears them

**A suite with a standing red test trains people to read a failure count as weather**,
and the difference between *red because the work is not done* and *red because something
broke* is invisible from the summary line. Raised by rewt-46, who nearly triaged one of
these before reading its docstring. So the standing ones are named here, and **a failure
not on this list is new**.

They are not marked `xfail`. The defects are real, they are in the published output, and
an expected-failure marker turns a red line into a green run with a footnote — which is
the same trade this repository refused when it chose to deselect rather than skip in CI.
The cost of a visible failure is that somebody asks about it; that is the point.

| test | why it is red | what clears it |
|---|---|---|
| `test_stage1_scope.py::test_the_model_stays_small` and `::test_every_derived_table_says_why_it_exists` | `high_water_side` arrived with R-01 (`54571e3`) and §3 does not account for it; and `link_scope`, `link_reach` and `link_flag` have been in the model without a line in `rewt/schema.py`'s docstring since before either test could see it. | One line each in schema.py's docstring saying what the table holds and what asked for it — rewt-e8's — and `high_water_side` added to the derived set here. The two halves are meant to move together and now have to. |
| `test_basins_and_the_sea.py::test_no_in_scope_basin_holds_more_sea_than_river` | D-080. Twelve in-scope basins enclose more sea network than river network, because the tidal surface is not removed before delineation. rewt-46's finding. | The delineation, not a rebuild. R-01 (OS Mean High Water as the coast) is the change most likely to move it. |
| `test_config.py::test_every_stage_1_source_is_read_by_a_stage_or_says_why_not` | `scottish_gov_lidar_dtm` is read by the elevation sweep, and a sweep is not a stage — *a script somebody remembers to run is not part of the build* (AGENTS.md). Left red **deliberately**, with the reasoning in `conf/sources.yml` beside the entry: rewt-e8's judgement, and mine, that this is a defect to fix rather than a category to declare around. | The sweep becoming a stage. Not a `read_by:` declaration — that category is for a source nothing should read, and something does read this one. |

Anything else red is transient or new. At the time of writing four others were failing
because two sources had been registered without the rebuild and conf work that follows;
those are not listed, because they clear themselves and a list that includes them would
be stale within the hour.

## Markers

- `db` — needs the build database. Run `pytest -m "not db"` to skip them all.
- `interim` — reads a derived raster under `data/interim/`, read-only.
- `published` — reads `published/` only, so it holds no database lock and can run while a build is in progress. Any session may run these; the `db` ones belong to whoever holds the database.

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
