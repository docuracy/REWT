# Temporality: which dates get published

[← REWT](index)

A reconstruction "between Domesday and 1900" has to say which years it actually draws, and
why not all of them. This page is that decision and its reasoning.

## Why a continuum is not publishable

**Flow is modelled *on* the network.** The water balance is resolved over the network
itself, so changing which channels exist changes where the water goes — not merely which
lines are drawn. An epoch is therefore **a complete run of the pipeline, not a query over a
built one.**

Be precise about what that does and does not promise. The reference year *is* a parameter,
and the pipeline can be run at any year — that capability is real. What does not exist, and
should not be implied, is slicing an already-built network to an arbitrary date without
rebuilding it. Promising "a model at any date" should mean the first of those, and say so.

The cost per epoch, measured: roughly half an hour of pipeline, **29 MB of vector tiles**
and an **89 MB dataset**. Seven epochs is around 200 MB of tiles in a repository served as
static pages. That is the constraint, and it is why the answer is **a curated set of dates,
not a slider**.

## The phases of change

The published dates are chosen to sit **between** phases, so that each is a stable state
rather than a moment mid-transformation.

| phase | roughly | what changes |
|---|---|---|
| medieval mills, fisheries, monastic drainage | 11th–15th c. | leats, diversions, embankment; the Broads dug and flooded |
| late-medieval retreat | 14th–15th c. | works decay; some channels revert |
| statutory river improvement begins | 1539–1620s | the legislative record starts; navigation works |
| **the great drainage schemes** | **1626–1660s** | Vermuyden; the Great Level and Hatfield Chase rebuilt |
| river navigations | 1660–1760 | locks, cuts, made rivers |
| **the canal age** | **1760–1830** | wholly new channels on new lines |
| parliamentary enclosure and land drainage | 1760–1850 | field drainage; warping |
| Victorian water supply | 1850–1900 | reservoirs drown valleys |
| modern | 20th c. | pumping, flood relief channels |

## The proposed set

| epoch | why this date | brackets |
|---|---|---|
| **1086** | Domesday — corroborated by independent evidence the project can hold: the coastline, and the mills | before almost all drainage |
| **1300** | the high medieval maximum, before plague and the late-medieval retreat | monastic drainage; the Broads |
| **1540** | the Dissolution; the legislative record begins in 1539 | after decay, before statutory improvement |
| **1600** | the eve of the great drainage | **the last state before the Level is rebuilt** |
| **1700** | after Vermuyden and Hatfield, before the canals | the great drainage schemes |
| **1830** | after canal mania and enclosure drainage, before the railways displace both | the canal age |
| **1900** | the survey datum — the map the courses are traced *from* | Victorian reservoirs |

**If fewer are wanted, 1540 goes first.** It is the least distinct: little changed
hydrographically between 1500 and 1600 outside the navigations.

**1600 must never be dropped.** It is the last state before the Fens and Humberhead were
rebuilt, and the single most useful cross-section in the series.

## Why the datum is not 1348

An earlier reference year of 1348 was not a historical judgement. It was the terminus of
the navigation synthesis the work leaned on, which carries **no start date on any of its
652 records** — so 1348 was the one year at which every course it attests is attested *by*
the date being drawn. The datum was fixed by the weakest constraint in the evidence.

Once courses are traced from dated sources, each carries its own bounds and that constraint
disappears. 1348 keeps a role as a continuity date, but stops being the year the project is
organised around.

## What the map does with this

**A stepped selector, not a slider.** A continuous control implies a precision the data does
not have. A control that moves between *published epochs* claims exactly what is true:
these are the dates that were built, and there is nothing in between.

**And flow cannot be interpolated across epochs.** Each epoch's figures are modelled on its
own network, so the selector switches datasets rather than animating one. That should be
visible in the interface rather than buried in a note: a reader moving between two epochs
is looking at two separate models, and the difference between them is a **finding**, not a
transition.

## Editions and epochs are different axes

*Editions* are how complete the evidence is. *Epochs* are which date is drawn. They are
independent, and confusing them means either waiting for the research before publishing any
date, or publishing seven dates of a network that is not yet sound.

**The first edition publishes one epoch. Later editions add both evidence and dates.**

| edition | what it adds | epochs it supports |
|---|---|---|
| **First** | the modern survey repaired into a working drainage network. No historical claim. | 1900 |
| **Second** | old courses from map evidence: the labelled channels, the drowned valleys. [Bounded and countable](scale). | + 1830, 1700 |
| **Third and after** | documentary and cartographic research, released a course at a time. **Never completes.** | + 1600, then 1300 and 1086 |

**An epoch is published when its evidence supports it and not before.** An empty medieval
map is worse than no medieval map, because it looks like a finding.

**1900 rather than a medieval date for the first edition**, because that edition makes no
historical claim and should not appear to. It is the modern survey repaired, and the honest
year for it is the one the survey describes.

## What varies between epochs, and what must not

**Varying:** which channels exist; the flow modelled on them; the coastline, for which
transcribed Holocene sea-level curves exist; and which attestations are in force.

**Not varying: identity.** A stretch present in 1600 and in 1700 must carry the same
identifier in both. Epochs are cross-sections of *one* network, not seven networks —
anything else makes change between them impossible to measure, which is the main reason to
publish a series at all.

This is also what makes incremental release safe, and it has to be designed in at the first
edition rather than discovered later:

- **Stable identifiers.** A course added in the fourth edition must not renumber the
  network. Identifier churn is what makes a dataset painful to track across versions.
- **Every line carries its status**, so a reader can take the first edition and ask which
  parts later editions have superseded. Additions are marked as such, never substituted
  silently.
- **The audit is published with the data** — dead ends, unreached length, flow anomalies —
  in the release notes of every edition, so improvement is visible and regression is caught
  by the reader as well as by the pipeline.

## One consequence worth accepting

The first edition will be a **modern** network, and some readers will take it for a
historical one whatever the documentation says. The defence is the same as everywhere else
here: every stretch carries what it is and what it rests on, and the map draws the
difference rather than describing it in a paragraph nobody reads.
