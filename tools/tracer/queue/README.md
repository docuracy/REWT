# The work queue's inputs

Three CSVs, produced by `tools/gb1900/measure.py --places`, clustered from the **CC0 raw
dump** of the GB1900 transcriptions. Committed, which needs justifying twice over.

**They are derived, and `.gitignore` opens by forbidding that.** The rule's reason is that a
committed artefact silently stops matching its inputs. Here the input is a 326 MB archive
that CI cannot fetch on every build, so the choice is between committing these and having
`tools/tracer/gen_tasks.py --check` skip permanently — and a check that never runs is not a
check. Committing the cheap artefact makes the expensive one's product verifiable.

**What guards them, and where the guard stops.** `conf/sources.yml` declares the dump with a
pinned sha256 (`e29eca60…`, corrected on 1 Sep 2026 after the inherited value proved wrong),
and `measure.py` refuses to run unless the archive matches. So *these files came from that
archive* is enforced at the moment they are made. It is **not** re-enforced on every build,
because the archive is not here. Regenerate with:

    .venv/bin/python tools/gb1900/measure.py --places tools/tracer/queue/

and if it prints an `--unverified` banner, **stop**: the figures are almost certainly right
and *almost certainly* is not what a provenance field is for.

## The columns

`place_id,text,captions,labels,easting,northing` — EPSG:27700, one row per place under a
1 km single-linkage clustering. `captions` is a JSON array and `text` is those captions
joined for display. **Test the array, never the joined string**: a merged cluster is a set
of statements, and `NEW CUT; New Cut Bridge` fails a naive structure-word test while being a
perfectly good task. That error was made twice, by two agents independently, before the
column existed.

## What is a task and what is not

`assertion_places.csv` — 274 places where the surveyor lettered *Old Course* or *New Cut*,
the two clustered together on position because they describe one event from either side.
`mill_channel_places.csv` — 4,068, the volunteer strand.
`towing_path_places.csv` — 1,724, **not a queue**: nothing is traced from it. It is the
control that made the mill-channel separation credible (97.8% within 250 m of a navigable
section against 5.5%), and it is the best contextual layer the tracer can carry, because a
towing path is direct evidence that *this* channel carried traffic at the survey date.
