# GB1900 measurements

`measure.py` re-derives every GB1900 figure published on the documentation site. It exists
because [D-019](../../DECISIONS.md) says do not publish a number you cannot re-run, and for
a while these numbers lived only in a session scratchpad.

```
.venv/bin/python tools/gb1900/measure.py                       # the published figures
.venv/bin/python tools/gb1900/measure.py --places out/     # and the work queues
```

**It is not a build stage.** `gb1900_raw_dump` is registered `stage: 2, used_by: docs`, and
`rewt/pipeline.py` refuses any stage that declares it. Nothing here touches the database.

## What it produces

| figure | where it is published |
|---|---|
| *Old Course* — 139 labels, 126 places (England and Wales) | `docs/scale.md`, `docs/evidence.md` |
| *New Cut* — 224 labels, 209 places | the same |
| *Towing path* — 2,169 labels, 1,724 places | the same |
| Mill channels — 4,996 labels, 4,068 places | the same |
| 1,888 of 6,884 mill-channel labels are Scottish | `docs/scale.md` |
| *Old Course* + *New Cut* together — 361 labels at 274 places | `docs/scale.md` |
| one CSV per class, a row per distinct place | the work queues for tracing |

## Input, and the two traps

The input is the **CC0 raw dump**, cached at `data/raw/gb1900/` per `conf/sources.yml`.

**Never the gazetteers.** The abridged and complete GB1900 *gazetteers* are CC-BY-SA, whose
share-alike would reach this project's own exports — and the abridgement drops every string
occurring 300 or more times nationally, which is exactly the *Mill Race* / *Mill Pond* /
*Towing Path* vocabulary these counts rest on. A copy of the abridged file sits in
`~/Downloads` and is the obvious file to reach for. It is wrong twice over. See D-018.

**Never the predecessor's copy.** `AGENTS.md` forbids importing data from *Premodern
Rivers*; acquire the dump from the publisher and check it against the registered checksum.

## Method

Every volunteer transcription is scanned rather than only the reading made when the pin was
dropped, so a pin whose first reading was blank is still found; each pin's text is then the
reading most of its matching transcriptions gave. Pins are split to England and Wales by OS
Boundary-Line country polygon — a **proxy** for the basin scope rule of `PLAN.md` §4.1,
which is why the counts undercount slightly in the Scottish parts of the Tweed and the
Border Esk. Labels sharing a normalised caption are collapsed into one *place* by single
linkage at 1 km, because the Ordnance Survey repeated a name along the feature it named, so
a count of labels is a count of type and not of rivers.

The class patterns are declared at the top of the script rather than described here, so
that what was counted is readable in one place.

## Outputs are not committed

`--places DIR` writes `mill_channel_places.csv`, `old_course_places.csv`,
`new_cut_places.csv`, `towing_path_places.csv` and `assertion_places.csv`, each with
`place_id,text,captions,labels,easting,northing` in EPSG:27700.

**Test against `captions`, not `text`.** A place is a *cluster*, so it can carry more than
one caption, and `text` joins them for display. Asking a joined string whether it matches
something answers *does any caption match*, when the question is usually *does no caption
describe a channel* — and that difference has produced a wrong answer for two people
independently. `captions` is a JSON array so the distinction is a visible choice at the
point of writing the test rather than one you have to know to draw.

**Use `assertion_places.csv` as the tracing queue, not the two class files.** *Old Course*
and *New Cut* describe one event from either side and frequently sit on the same reach, so
the assertion file clusters them **together on position** — 274 places, the published
figure. The per-class files cluster by caption and total 335; unioning them would send two
contributors to opposite ends of the same channel, and accidental duplication is worse than
useless to anyone trying to measure whether two tracings of the same reach agree. They are derived and regenerable;
only the script is kept. Write them where you like — not into the repository.
