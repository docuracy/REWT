# Temporality: which dates get published

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

The cost per epoch, as measured in the [scoping exercise](background) and not yet re-earned
here: roughly half an hour of pipeline, **29 MB of vector tiles** and an **89 MB dataset**.
Seven epochs is around 200 MB of tiles in a repository served as static pages. That is the constraint, and it is why the answer is **a curated set of dates,
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

**And one that is not in the list.** The **modern network** is the datum the whole series is
worked back from, and it is published as the first edition. It is not an epoch in the sense
used here — it draws no historical claim and needs no evidence beyond the survey — but it is
the cross-section every other one is measured against, and it is dated by the issue of the
Ordnance Survey product it repairs rather than by a year in the past.

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
| **First** | the modern survey repaired into a working drainage network. No historical claim. | the modern network itself |
| **Second** | old courses from map evidence: the labelled channels, the drowned valleys. [Bounded and countable](scale). | 1900, then 1830 and 1700 |
| **Third and after** | documentary and cartographic research, released a course at a time. **Never completes.** | + 1600, then 1300 and 1086 |

**An epoch is published when its evidence supports it and not before.** An empty medieval
map is worse than no medieval map, because it looks like a finding.

**The first edition is not a historical epoch at all**, and labelling it as one would be the
first misreading to invite. It is the modern survey repaired, so the honest date for it is the
survey's own issue and not a year in the past. 1900 is the earliest date the *map* record
reaches and the first cross-section that has to be reconstructed — which makes it second-edition
work, not first.

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

## How a date is recorded

An epoch is a year the project *draws*. It is not the same thing as what the project *knows*
about a stretch, and conflating the two is how the old 1348 datum came about. Dates on
evidence are therefore recorded separately from the dates that get built, in the
**[Linked Places Format](https://github.com/LinkedPasts/linked-places-format){:target="_blank"}** `when` object: a set of `timespans`, each with an optional
`start` and an optional `end`, each of those being either `in` a year or bounded by
`earliest` and `latest`, with a `certainty` on the whole.

**Both bounds are optional, and that is the point.** Almost every source this project uses
knows one and not the other:

| what a source actually says | recorded as |
|---|---|
| a mill on a map surveyed in 1824 | `start: {latest: 1824}` |
| a channel labelled on a sheet surveyed in 1899 | `start: {latest: 1899}`, `end: {earliest: 1899}` |
| a reservoir completed in 1869 | `start: {in: 1869}` — and the drowned channel's `end: {in: 1869}` |
| a valley drawn as river on the 1st edition and water on the 2nd | `end: {earliest: 1854, latest: 1894}` |
| a declared year built that is visibly rounded | `start: {earliest: 1870, latest: 1880}`, `certainty: less-certain` |
| a waterway already navigable when a survey window opens in 1600 | `start: {latest: 1600}` |
| navigable at some point, no year given at all | `start: {latest: 1600}` — *the same encoding, honestly* |
| an attestation with no start date at all | `end` only, **`start` absent** |

The last two rows are the argument for the whole scheme. **A model that requires a start date
forces every source to invent the half it does not have** — which is precisely how a datum
can come to be fixed by the weakest constraint in the evidence. An absent `start` says
*nobody knows when this began*, which is true and is a publishable fact. And where a source
records "already open at the start of my window" and "known to have been navigable once, no
year", those two carry **identical information**: a plain year column would make one look like
a date and the other like a hole in the data.

**It also puts a finding into the data instead of a footnote.** The whole point about the
pre-Ordnance-Survey mill mapping is that its year is the *map's* year and not the mill's — a
terminus ante quem. `start: {latest: 1824}` says that structurally. A `date` column says the
opposite and needs a paragraph to undo it.

**Unknown is not the same as unbounded.** A missing `start` because nobody knows is a
different statement from a channel deliberately modelled as having no beginning, and the two
must not be allowed to collapse into the same empty field. Where that distinction has to be
drawn, it is drawn explicitly.

**Two things this must not become.** It is not a licence to interpolate: a bound is a bound,
and a stretch with `start: {latest: 1600}` and nothing else must not be drawn at 1540 because
the arithmetic permits it. And **documentary uncertainty must not be blended with model
uncertainty** — how confident we are that a channel existed in 1700 is a different quantity
from how confident we are in a modelled flow along it, and one "confidence" number over both
is worse than neither.

> **On convergence.** The choice is deliberate rather than convenient. Linked Places is the
> interchange format for historical gazetteer work, and its current draft both relaxes the
> requirement for a `start` and carries `certainty` on the timespan — which is exactly what
> evidence of this kind needs. The [PLATO](https://github.com/docuracy/place-attestation-ontology){:target="_blank"} attestation ontology expresses the same
> information as a four-date model, `startEarliest` / `startLatest` / `endEarliest` /
> `endLatest`, aligned with PeriodO, and adds a precision term and an explicit flag for a
> bound that is *deliberately* open rather than unknown. The two are inter-convertible, and
> this project's aim is to be expressible in either rather than to invent a third thing. That
> matters more here than it might elsewhere, because a river reach carrying its own evidence
> **is** an attestation, and the modelling problem is one other people are already solving.

## How a release is archived

**Editions are published as releases, and a release may carry more than one epoch.** Each
release is deposited to [Zenodo](https://zenodo.org){:target="_blank"} automatically, through its link with GitHub, and
minted a **DOI** — so a reader can cite what they used and a later reader can fetch exactly
that, after this project's own site has changed or gone.

**Two DOIs, and citing the wrong one loses the thing that makes a citation useful.** Zenodo
issues a *concept* DOI that always resolves to the newest version, and a *version* DOI fixed
to a single deposit. A paper about this project cites the concept DOI. **A result computed
from a particular edition must cite that edition's version DOI** — otherwise the reference
silently comes to point at a later network, and a figure that could once be checked no longer
can. Since a release may carry several epochs, the version DOI is the only identifier that
says which network a number came from.

**And an archive of this repository is not an archive of the data.** Nothing acquired,
derived or built is committed here — the inputs are declared and fetched, and the outputs are
reproducible from them — so a deposit made from the repository alone holds the method, the
configuration and the hand-made judgements, and none of the network. That is worth archiving
and it is not what a reader following a DOI expects to find. The built outputs are deposited
with it, or the record says plainly what it contains; the one thing that must not happen is a
DOI that looks like a dataset and is not.

## One consequence worth accepting

The first edition will be a **modern** network, and some readers will take it for a
historical one whatever the documentation says. The defence is the same as everywhere else
here: every stretch carries what it is and what it rests on, and the map draws the
difference rather than describing it in a paragraph nobody reads.
