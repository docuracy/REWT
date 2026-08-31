# Evidence

What each source can say, what it cannot, and whether it can be published.

## The modern network

**[OS Open Rivers](https://www.ordnancesurvey.co.uk/products/os-open-rivers){:target="_blank"}** (Ordnance Survey, Open Government Licence) is the spine: a national
watercourse network with names and topology. It is a *cartographic* product and does not
claim to be hydrologically routable — which is the whole of the first phase's work.

It says nothing whatever about premodern courses, and is treated as the least reliable
evidence in the places where most has changed.

## The map record

**[Victorian six-inch sheets](https://maps.nls.uk/os/6inch-england-and-wales/){:target="_blank"}** (National Library of Scotland, georeferenced) are the base
for tracing. The surveyors sometimes state which of two channels is superseded —
*Old Course*, *New Cut* — and **[GB1900](http://www.gb1900.org/){:target="_blank"}**, a volunteer transcription of every label on
those sheets, makes those statements findable. A label is an assertion by someone who
was there, which is worth more than an inference from the modern line.

**Pre-Ordnance-Survey mill mapping** — county maps, estate maps and the Roy Military
Survey of 1729–1836, gathered by [Mills of Britain](https://maps.nls.uk/projects/mills-of-britain/){:target="_blank"} (Jonell, Jones, Lucas and
Naylor, CC BY 4.0; its companion layer is derived from GB1900 and carries that dataset's
CC0 terms) — carries 17,120 records in England and Wales, 10,371 of them water-powered. It attests mills
60 to 170 years before the six-inch sheets, and 47% of its water-powered sites have nothing
within 250 m in the mill layer filtered from those sheets, so as a record of *mills* it is
genuinely additional. As a way of finding the labelled mill *channels* it is much weaker —
under a third of them have one of its sites within 250 m, and the two are not the same
population. **It does not date anything either**: its year field is the final survey or publication year of the map the mill
was read from, a terminus ante quem from cartographic attestation with no documentary or
archaeological date behind it. Earlier evidence that a mill stood is earlier evidence that a
leat existed, and that is the whole of what it offers.

The **first series** matters where the second is too late: much of Victorian water supply
predates 1888, so for a valley drowned in the 1870s the second series shows the lake and
not the river. It is county-by-county rather than a single national mosaic, which is why it
is more work — and it is georeferenced less consistently, which is why a trace has to record
*which sheet* each vertex came from.

**What the labels actually offer**, measured against the transcription of 2.6 million of
them, in England and Wales:

| label | labels | distinct places | what it is |
|---|---|---|---|
| **Old Course** | 139 | **126** | the surveyor stating which of two channels is superseded |
| **New Cut** | 224 | **209** | the same statement from the other side |
| Mill channels — *Mill Race*, *Mill Leat*, *Mill Pond* | 4,996 | **4,068** | frequently medieval, and belonging *in* the reconstruction rather than subtracted from it |
| Towing path | 2,169 | 1,724 | the channel carrying traffic c.1900 — ambiguous alone, disambiguated by the two above |

**A label is not a channel.** The Ordnance Survey repeated a name along the feature it
named, so the second column collapses labels reading the same thing within a kilometre of
each other into one place. The correction is smaller than it sounds — repeated captions are
set 1.7 km apart on average, and no two *Old Course* labels lie within 300 m — but the
counts are counts of places, and are labelled as such.

Two figures need saying plainly. The labels come from the **CC0 raw dump**, never from the
published gazetteers, which are CC-BY-SA and would carry share-alike into this project's
exports. And the extent is **England and Wales**: 1,888 of the 6,884 mill-channel labels in
Great Britain are Scottish, *lade* and *lead* being Scots, and Scotland is outside the
scope. [The scale page](scale) gives the method.

**Some 274 outright assertions** where *Old Course* and *New Cut* are taken together and
counted by place, which is a small enough number to work through completely, against some
4,068 judgements, which is not. That difference drives the [release plan](epochs), and
[the scale page](scale) sets out what follows from it.

A **second population is not labelled at all: channels drowned by reservoirs.** A drowned
valley is not a channel that ceased to exist — it is one that is under water, and its course
is recoverable from a map made before the dam. **The network cannot find them by itself**:
OS Open Rivers names 6,042 of its 24,146 standing-water links and not one of those names
contains the word *Reservoir* — a lake link carries the name of the river running through
it. A gazetteer of named places is needed, and has to be declared before any count from it
can be quoted; the scoping exercise's 606 reservoirs over 1,834 links was obtained that way
and is inherited here, not earned.

**Their dates can be looked up, for the large ones.** The [CEH inventory of UK
reservoirs](https://doi.org/10.5285/f5a7d56c-cea0-4f00-b159-c3788a3b2b38){:target="_blank"} (Open Government Licence) holds 273, of which 233 are
in England and Wales and 252 carry a completion year. Its threshold is stated — over
1,600 Ml, plus smaller ones in a group with historic storage information — so the big
reservoirs are dated and the small Victorian impoundments are simply absent. Wikidata is
not a substitute and was tested: 24 of 1,125 items typed as UK reservoirs carry a
construction date, and Kielder, Rutland, Ladybower, Haweswater, Vyrnwy and Derwent are all
among those that do not.

**What the date buys is the edition.** Compared against the County Series survey dates for
the county, a completion year says which map shows the valley before it was flooded — and
two in five of the impounding reservoirs in England and Wales need the first edition or
earlier, with nineteen predating both. [The scale page](scale) gives the breakdown. Where
no date exists the map comparison still answers it, a valley drawn as a river on the first
edition and as water on the second having been flooded between the two surveys; the
inventory only means the tracer knows which sheet to send for.

**Beware the same trap as GB1900 here.** Wikipedia's list of UK reservoirs is the identical
content — the same 273 rows, sourced from the same inventory — under CC-BY-SA. The
share-alike version of an open dataset is not a convenience; it is a licence this project
cannot take. Use the original.

Distinguishing a reservoir from a merely wide river is otherwise tractable: measured channel
width is a good second signal (trunk channels run to a median 34.9 m, so anything an order of
magnitude wider is not a widening), and a reservoir is a *polygon* the network has to be
routed across rather than along.

A third, larger population — **19,434 courses fossilised in parish boundaries** — is
identifiable but rests on a licence-encumbered boundary set, and so cannot be published
from. It is noted here because its absence is a real limit, not an oversight.

## The documentary record

**Drainage and navigation legislation** records works authorised, undertakers, and land
taken — but authorisation is not execution, and several such powers were never exercised.
Nothing here may be read as *the river was navigable from this year*. Compilations of river
legislation and patents covering **1539–1720** exist and record the Act, the undertakers,
the tenure taken and a citation per row.

Their under-used value is different: a compulsory purchase is a legal act over **specific
ground**, and a new cut had to be located relative to the channel it replaced — so the
plans and awards behind it can show the river *before* the work. How reliably is an open
question: survival is uneven, and many plans depict only what was proposed. Worth testing
on a sample before it is relied on.

**Regional studies** — the Fenland Survey, the [Humber Wetlands Project](https://archaeologydataservice.ac.uk/){:target="_blank"}, the Somerset
Levels literature — answer locally what no national rule can: which channels are older than
they look, and which are engineering. National pattern rules that date a channel by its
name — *drain*, *cut*, *sewer* — answer it crudely and should say so: in the Somerset Levels
and Romney Marsh a *sewer* is a drainage channel and many have medieval origins even where
the present cut is later.

**A tenth of England lies inside an Internal Drainage District — 12,779 km, 13.3% of the
mapped network** — and that is the measurable extent of ground where the hydrography was
rebuilt rather than modified. [The rebuilt landscapes](regions/) divides it into the regions
that have to be worked out one at a time, with the schemes that reshaped each, when they
were carried out, and the sources that record what was there before.

## Attested navigation

[Oksanen's *Inland Navigation in England and Wales before 1348*](https://doi.org/10.5284/1057497){:target="_blank"} — the
scholarly GIS of pre-1348 navigation, deposited with the Archaeology Data Service — is used
as an **index and a check**: where to look, and whether a trace is corroborated — and **not** as geometry. Merging a
national synthesis with a traced line means reconciling two orders of accuracy at every
junction, silently, in exactly the places nobody is looking.

The numbers behind that judgement: **652 records**, a median continuous part of **3.6 km**,
and where a course is boundary-derived it sits a median **236 m** from the modern channel.
That 236 m is the historical signal rather than an error — the boundary remembers where the
river was — which is exactly why it should be sharpened by retracing the underlying
material, not resampled from the synthesis.

One further limitation shapes the whole project's temporality: the corpus carries **no start
date on any of its 652 records**. A reconstruction leaning on it can only honestly be drawn
at its terminus, which is how an earlier datum of 1348 came to be fixed by the weakest
constraint in the evidence. [Escaping that is what frees the date](epochs).

## Terrain

A terrain model — [OS Terrain 50](https://www.ordnancesurvey.co.uk/products/os-terrain-50){:target="_blank"} nationally, and the 1 m LiDAR of the
[Environment Agency](https://environment.data.gov.uk/survey){:target="_blank"} and [DataMapWales](https://datamap.gov.wales/maps/lidar-data-download/){:target="_blank"} for a single reach — can say whether water *can*
get from one place to another, and cannot say
by which line. It is admissible for repairing the modern network's connectivity, and is
not evidence of any historical course.

---

## Licensing, and why this repository is structured as it is

Some material this project can read is **not redistributable** — data derived from
licensed terrain products, and safeguarded research datasets available under
end-user agreements. Those can inform a measurement and can never travel in a published
file.

The rule is simple and enforced in code rather than remembered: **a feature whose source
is not openly licensed cannot reach the published site or any exported product.** The
build refuses to write it.

This repository is private while it is assembled, and is being built so that it can be
opened without any such material having to be removed — which is why nothing is carried
across from earlier work except deliberately and after checking.

Every source is declared with its licence and attribution before anything reads it. An
unregistered source is a hard error, not a warning: unattributed provenance is not
provenance.

---

## Related

| | |
|---|---|
| [The rebuilt landscapes](regions/) | region by region: the schemes, their dates, and the records behind them |
| [The scale of the work](scale) | what these counts imply about who can do the work |
| [Temporality](epochs) | which dates the evidence can support |
