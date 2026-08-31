# The scale of the work

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
| links in [OS Open Rivers](https://www.ordnancesurvey.co.uk/products/os-open-rivers){:target="_blank"} (GB) | 192,865 |
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

> These six figures are measurements of *OS Open Rivers as shipped*, carried over from the
> scoping exercise. They are legitimate to check a rebuild against and are not results of
> this repository; the issue they were taken from is not the issue now being built from.

### Old courses the Victorian surveyors labelled

Volunteers have already transcribed **2.6 million labels** ([GB1900](http://www.gb1900.org/){:target="_blank"}) from the
[six-inch County Series second edition](https://maps.nls.uk/os/6inch-england-and-wales/){:target="_blank"}. Within them, in England and
Wales:

| label | labels | distinct places | what it is |
|---|---|---|---|
| **Old Course** | 139 | **126** | the surveyor stating which of two channels is superseded |
| **New Cut** | 224 | **209** | the same statement from the other side |
| Towing path | 2,169 | 1,724 | the navigable channel c.1900; ambiguous alone |
| Mill channels — *Mill Race*, *Mill Leat*, *Mill Pond* | 4,996 | **4,068** | frequently medieval, and belonging *in* the reconstruction |

**Two columns, because a caption is not a channel.** The Ordnance Survey repeated a name
along the feature it named, so one stretch of abandoned river can carry *Old Course* three
or four times and a transcription of the labels counts the type, not the river. The second
column collapses labels reading the same thing into one place where they are within a
kilometre of each other.

**The correction turns out to be small**, and that is worth stating because the opposite
was expected. Repeated captions are set far apart: no two *Old Course* labels in England
and Wales are within 300 m of each other, and the median distance from one to the nearest
other label reading the same thing is 1.7 km. Collapsing at a kilometre takes 139 labels to
126 places — nine per cent, not a factor. **What the labels count and what the work counts
are nearly the same number.**

**361 labels at some 274 distinct places** for *Old Course* and *New Cut* together, taking
the two classes as one and clustering on position alone — the two captions describe the
same event from either side, and often sit on the same reach. Each is a statement by
someone who was there, not an inference from the modern line. At ten minutes to find the
sheet and trace the channel, that is **about six working days**.

**Verdict: in house, comfortably.** This is the second edition's core, and it is finishable.

> **How these were counted.** From the **CC0 raw dump** of the GB1900 transcriptions, never
> from the published gazetteers, which are CC-BY-SA: share-alike would propagate into this
> project's own exports, and the abridgement drops every string occurring 300 or more times
> nationally, which is exactly the mill and towing-path vocabulary. A pin's text is the
> reading most volunteers gave it. Extent is England and Wales by OS Boundary-Line, which
> matters more than it sounds: **1,888 of the 6,884 mill-channel labels in Great Britain are
> in Scotland** and outside this project's scope — *lade* and *lead* are Scots, and they are
> two of the four commonest terms. Earlier drafts of this page gave 161, 219, 2,214 and
> 10,738 for the four classes. Two of those reproduce exactly; the mill-channel figure does
> not reproduce at all from the source, at any extent, and has been replaced by the measured
> one.

### Valleys drowned by reservoirs

A drowned channel has not ceased to exist; it is under water, and its course is recoverable
from a map made before the dam. Much of Victorian water supply predates the second series,
so a good share of these need the **first** series — county by county rather than a single
national mosaic, and so slower.

**How many there are is not yet a figure this project can quote.** The scoping exercise
reported 606 reservoirs marking 1,834 links, and did it by joining a *gazetteer* to the
network. The network alone cannot do it: OS Open Rivers names 6,042 of its 24,146
standing-water links, and **not one of those names contains the word "Reservoir"** — the
name carried by a lake link is the river running through it, *River Darent*, *Mill Beck*.
Identifying the drowned valleys therefore needs a named-places source declared alongside
the rest, and until it is, the count is inherited rather than earned.

**Nor can the dates be looked up.** Wikidata was tested for exactly this: of 1,125 items
typed as reservoirs in the United Kingdom, **24 carry a construction date** — two per cent —
and not one of Kielder Water, Rutland Water, Ladybower, Haweswater, Lake Vyrnwy or Derwent
does. The dam records are no better: 101 items, 5 dated. Anything relying on that lookup
would be dating a handful of reservoirs and guessing at the rest.

**The map series dates them instead, and more cheaply.** A valley shown as a river on the
first edition and as water on the second was flooded between the two surveys, which brackets
it to a couple of decades — and the same comparison is what tells the tracer which sheet to
work from. The date falls out of the work rather than having to be fetched before it.

**Verdict: in house, but the largest bounded item.** Several hundred hours. A candidate for
the first thing volunteers are invited to help with, because each unit of work is
self-contained: one reservoir, one pre-dam sheet, one traced valley.

---

## What is not bounded

### The mill channels

**Some 4,068 places in England and Wales.** Still an order of magnitude larger than
everything above it, and each requires a judgement rather than a trace: a mill leat may be
medieval, Victorian, or a nineteenth-century rebuild on a medieval line, and the map does
not say which.

**Verdict: not in house.** This needs either volunteer adjudication at scale or a
defensible sampling strategy — and the honest answer may be to publish them as *a class
identified but not dated*, which is a real contribution on its own.

### The documentary and regional research

The [rebuilt landscapes](regions/) — the Fens, the Humber, the Somerset Levels and the
rest — are where the modern channel is worthless and the answer is local. **A tenth of
England lies inside an [Internal Drainage District](https://www.ada.org.uk/){:target="_blank"}: 12,779 km, 13.3% of the mapped
network.** That is the measurable extent.

Each region has its own literature, its own archives, and its own specialists. Nobody can
work through all of them, and the material is of a kind — cartularies, drainage awards,
deposited plans, county archives — where a person who already knows the region will be
faster by an order of magnitude than a person learning it.

**Verdict: collaborators, region by region, indefinitely.** This is the third edition and
after, and it is why the third edition is defined as *never complete*.

### Courses recoverable only from another synthesis

[Oksanen's *Inland Navigation in England and Wales before 1348*](https://doi.org/10.5284/1057497){:target="_blank"} holds **652 records**, with a median
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
| *Old Course* / *New Cut* traces | ~274 places | in house, ~6 days |
| reservoir valleys | count not yet earned; several hundred | in house or volunteers, months |
| mill channels | ~4,068 places | volunteers, or publish undated |
| regional documentary research | 12,779 km of rebuilt landscape | collaborators, indefinitely |

**The first two rows are a publishable dataset.** That is the argument for releasing in
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

**[GB1900](http://www.gb1900.org/){:target="_blank"} is the proof that this scale of volunteer work succeeds**: 2.6 million labels,
transcribed by the public, and the reason the assertions this project most needs are
already findable. The same constituency exists for river courses.
