# The scale of the work

[← REWT](index)

**How much of this can be done in house, and where volunteer or collaborator effort
becomes unavoidable.** The counts below are measured, not estimated; the hours are
illustrative and meant only to separate *bounded* work from *open-ended* work.

The distinction matters because it decides the [release plan](epochs). Work that can be
counted can be scheduled and finished. Work that cannot must be released incrementally, or
it will hold up everything behind it.

---

## What is bounded

### Repairing the modern network

| | |
|---|---|
| links in OS Open Rivers (GB) | 192,865 |
| mapped length | ~152,000 km |
| separate connected components | 5,617 |
| nodes where water arrives and cannot leave | **2,516** |
| isolated canal systems needing attachment | 289 |
| links where terrain contradicts the stated flow direction | 757 |

**2,516 sounds like a research programme and is not**, because the defects cluster: one
misdrawn junction strands everything above it. The scoping exercise cleared the bulk of
them with **73 hand-authored corrections** — roughly one judgement per thirty defects —
each checked at the place by one person in a few minutes.

**Verdict: in house.** Days of adjudication, not months, and the crawl-from-the-sea method
generates the queue automatically and ranks it by how much water is at stake.

### Old courses the Victorian surveyors labelled

Volunteers have already transcribed **2.6 million labels** from the six-inch County Series
second edition. Within them:

| label | count | what it is |
|---|---|---|
| **Old Course** | **161** | the surveyor stating which of two channels is superseded |
| **New Cut** | **219** | the same statement from the other side |
| Towing path | 2,214 | the navigable channel c.1900; ambiguous alone |
| Mill channels — *Mill Race, Mill Lade, Mill Leat* | **10,738** | frequently medieval, and belonging *in* the reconstruction |

**380 assertions** for *Old Course* and *New Cut* together. Each is a statement by someone
who was there, not an inference from the modern line. At ten minutes to find the sheet and
trace the channel, that is **under two working weeks**.

**Verdict: in house, comfortably.** This is the second edition's core, and it is finishable.

### Valleys drowned by reservoirs

| | |
|---|---|
| named reservoirs matched against the network | **606** |
| network links marked as standing water that was once a valley | 1,834 |

A drowned channel has not ceased to exist; it is under water, and its course is recoverable
from a map made before the dam. Much of Victorian water supply predates the second series,
so a good share of these need the **first** series — county by county rather than a single
national mosaic, and so slower.

**Verdict: in house, but the largest bounded item.** Several hundred hours. A candidate for
the first thing volunteers are invited to help with, because each unit of work is
self-contained: one reservoir, one pre-dam sheet, one traced valley.

---

## What is not bounded

### The mill channels

**10,738.** An order of magnitude larger than everything above it combined, and each
requires a judgement rather than a trace: a mill leat may be medieval, Victorian, or a
nineteenth-century rebuild on a medieval line, and the map does not say which.

**Verdict: not in house.** This needs either volunteer adjudication at scale or a
defensible sampling strategy — and the honest answer may be to publish them as *a class
identified but not dated*, which is a real contribution on its own.

### The documentary and regional research

The [rebuilt landscapes](regions/) — the Fens, the Humber, the Somerset Levels and the
rest — are where the modern channel is worthless and the answer is local. **A tenth of
England lies inside an Internal Drainage District: 12,779 km, 13.3% of the mapped
network.** That is the measurable extent.

Each region has its own literature, its own archives, and its own specialists. Nobody can
work through all of them, and the material is of a kind — cartularies, drainage awards,
deposited plans, county archives — where a person who already knows the region will be
faster by an order of magnitude than a person learning it.

**Verdict: collaborators, region by region, indefinitely.** This is the third edition and
after, and it is why the third edition is defined as *never complete*.

### Courses recoverable only from another synthesis

Existing scholarly GIS of pre-1348 inland navigation holds **652 records**, with a median
continuous part of 3.6 km — and where a course is derived from a parish boundary it sits a
median **236 m** from the modern channel.

**That 236 m is not error.** It is the historical signal: the boundary remembers where the
river was. But it means the synthesis cannot be merged into a traced network without
reconciling two orders of accuracy at every junction, silently. The route to a better
course is **the material behind it, retraced**, not the line resampled — which puts it in
the open-ended category with everything else documentary.

A further 19,434 boundary-fossil candidates exist but rest on a licence-encumbered
boundary set, and cannot be published from.

---

## What this adds up to

| strand | count | who |
|---|---|---|
| network repair | ~73 judgements over 2,516 defects | in house, days |
| *Old Course* / *New Cut* traces | 380 | in house, ~2 weeks |
| reservoir valleys | 606 | in house or volunteers, months |
| mill channels | 10,738 | volunteers, or publish undated |
| regional documentary research | 12,779 km of rebuilt landscape | collaborators, indefinitely |

**The first two columns are a publishable dataset.** That is the argument for releasing in
editions rather than waiting: the bounded work produces something useful and complete on
its own terms, and the unbounded work is added to it a course at a time without disturbing
what is already there.

## Designing for contribution

If volunteers are to help, the tooling has to exist before they are asked — and the
scoping exercise built the parts of it that were hardest:

- **A correction-request tool.** A reader selects the stretch that is wrong, says what is
  wrong with it, and the report carries the identifiers needed to act on it. Feedback
  against a *specific line* is worth far more than feedback about a map.
- **A snap-to-ink tracer.** A traced segment is fitted to the printed ink of a historic
  sheet rather than clicked freehand, so two people tracing the same channel produce
  substantially the same line. It records which vertices were placed by hand and which by
  the algorithm, and on which sheet — so a contributed trace carries its own provenance.

**GB1900 is the proof that this scale of volunteer work succeeds**: 2.6 million labels,
transcribed by the public, and the reason 380 of the assertions this project most needs are
already findable. The same constituency exists for river courses.
