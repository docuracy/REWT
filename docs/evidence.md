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

**The archaeological registers were checked and cannot date a leat either.** The National
Heritage List for England is open, national and updated daily, but its published form carries
**no monument-type field at all** — only a free-text name — so a watercourse has to be
selected by string exactly as in GB1900, and the only structured date it holds is the date of
*listing*, not of the asset. A few hundred names containing *mill*, and a few dozen containing
*leat*, against some four thousand labelled mill channels. The Welsh equivalent is more
promising and is not yet measured: the National Monuments Record of Wales does publish a
monument-type classification, which is a structured field where England offers only prose.

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

**The statutory registers are the better instrument, and only one country publishes one.**
Every reservoir holding water above the level of the surrounding ground is registered under
the Reservoirs Act — over 25,000 m³ in England, over 10,000 m³ in Wales — which is a *raised
water* test, far closer to "this drowned a valley" than a storage threshold is, and which
reaches well below the hydrological inventory. **Natural Resources Wales publishes the Welsh
register as open data** under the Open Government Licence, with a year built for most
entries. **The Environment Agency does not publish the English one**: it must be requested by
letter, email or telephone. Treat a registered year as what it is — a declaration made by the
undertaker on a regulatory form, with no source recorded — and not as the same kind of
evidence as the inventory's flagged and referenced dates.

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

### Maps that show the valley before the dam

The six-inch is the base case and its limit is now measured rather than assumed: two in five
of the impounding reservoirs in England and Wales need the first edition or earlier, and in
Wales, where the county first editions were surveyed late — mostly 1873–1888 — a large
minority of reservoirs predate **both** editions. So the question "what shows the valley
before the dam" has to be answered below the six-inch, and this is what is on the shelf.

| source | what it shows | state |
|---|---|---|
| **[OS six-inch County Series](https://maps.nls.uk/os/6inch-england-and-wales/){:target="_blank"}**, 1st and 2nd editions | the channel itself, 1:10,560 | georeferenced, national — the base case, and too late for a large minority |
| **[OS one-inch Old Series](https://maps.nls.uk/os/one-inch-england-wales/){:target="_blank"}**, 1801–1869 | the valley; rarely the channel, at 1:63,360 | georeferenced, 746 sheets — earlier than the six-inch over much of the country, and **untested for this purpose** |
| **Pre-Ordnance-Survey county maps**, c.1729–1836 | valley and settlement at county-map scale | scattered across a dozen libraries; georeferencing is the tracer's problem |
| **Tithe maps**, 1836–1852 | the best large-scale coverage before the six-inch | **Wales: 1,224 maps, over 95% of the country, georeferenced by volunteers.** England: no national equivalent |
| **Enclosure maps and awards** | large scale, patchy by construction | county record offices; unassessed |
| **Deposited plans for the waterworks Acts** | the works *and the ground taken* — the channel, not only the valley | indexed nationally and item by item; **nothing digitised** |

**The deposited plans are the best-evidenced route on that list, and water schemes are what
the series was created for.** From **1793**, Standing Orders required an application for a
local Act to be accompanied by a detailed plan deposited with the Clerk of the Peace of every
county affected — and the requirement covered **canals and waterworks**, railways only being
added in 1803. Each plan came with a *book of reference* naming the owner and occupier of
every parcel of land the scheme would take. That is the argument this page already makes
about navigation legislation, in its strongest form: a compulsory purchase is a legal act
over specific ground, drawn at large scale by someone who had to be accurate about it. It is
the only source here that would show a **channel** rather than a valley.

**The index exists, it is national, and it is one catalogue.** The obvious fear — that
finding a plan means working through county record offices one at a time — is wrong. The
National Archives' [Discovery](https://discovery.nationalarchives.gov.uk/){:target="_blank"} catalogue aggregates the county record offices
alongside its own holdings, so a single search reaches Bolton, Derbyshire, Leicestershire and
Kew together. The parliamentary series is catalogued item by item: the House of Lords
deposited plans of 1794–1841, formerly listed only by box, were re-catalogued in December
2022 to give every plan its own reference on the scheme already used for 1842 onwards.

**Searched against the fifteen reservoirs with no Ordnance Survey edition behind them**,
eleven return a catalogued record naming the place — the deposited plan and reference book
for the 1843 Belmont Reservoir extension is at Bolton, and *Belmont Reservoirs* of the same
session is at Kew. Two of the four misses close when the search is the *undertaking* instead
of the reservoir: Tittesworth returns nothing under its own name and the Staffordshire
Potteries Waterworks deposits of 1847 and 1849 are there under the company's. **That is the
practical lesson — a nineteenth-century plan is titled for the company and the Act, because
the reservoir frequently had no name yet.**

**Four things temper it.** A catalogue hit is a *mention*, not a confirmed plan for that
scheme. Catalogue depth is very uneven, and a good many entries are titled no more than
"Plan" or "Book of reference", so the index makes a holding findable without saying what is
on the sheet. **Nothing is digitised**: establishing that a plan exists is an hour at a
keyboard, and reading one is a visit to a record office, per reservoir. And access is in
flux — the Parliamentary Archives has closed and its collections are moving to The National
Archives, which is why these references now carry a `Y` prefix, so the reference form should
not be assumed stable.

**Two of the strands meet on the same shelf.** The pre-Ordnance-Survey county maps are the
only cartographic evidence for the Welsh reservoirs that predate both OS editions, and they
are the same corpus the [mill mapping](https://maps.nls.uk/projects/mills-of-britain/){:target="_blank"} was compiled from. A project that
digitises or georeferences that material serves the drowned valleys and the mill channels at
once, which is worth knowing before either is costed separately.

**The licences here are per image, not per site.** The National Library of Scotland offers
much of its map imagery under CC-BY with the acknowledgement "Reproduced with the permission
of the National Library of Scotland", but is explicit that terms vary by collection, with
some under CC-BY-NC-SA and third-party content carved out entirely. That is the same lesson
as the GB1900 gazetteers and the mill layers: **an item's licence is not its collection's
licence**, and this project checks the item.

### What has been looked for and not yet found

Named so that nobody repeats the search, and so that anyone who can close one of these knows
it is wanted:

- **An open source enumerating the English large raised reservoirs with locations.** The
  statutory register is not published; the flood-extent dataset implies the list without
  naming it.
- **Licence and bulk access for the Welsh tithe maps**, which are digitised and georeferenced
  but whose reuse terms are not established here.
- **Whether the one-inch Old Series shows enough**, at 1:63,360, to be worth a tracer's time.
  Testable on a single reservoir.
- **Whether a catalogued deposited plan is the plan for the scheme** — the index finds
  records naming a place; only the document says what it draws.
- **An open, place-located version of the Domesday mills**, which is the one source that
  could date a mill channel rather than merely attest it earlier.

**And one deliberately deferred.** The *Victoria County History* will often date a mill or a
reservoir where the maps only locate one, and it is noted here as a fallback rather than
investigated. Two reasons, and the second is the one that generalises. Its coverage is
England only and partial, so it cannot answer at national scale. And **being able to read a
source is not the same as being able to republish it**: a text can support a curated
judgement — a `reason` in words with an `evidence` string naming a volume and a page — while
its own words may not travel into an export. Nothing on this page yet occupies that category,
the terms have not been established for the VCH, and describing it as available would imply
an answer to a question nobody has asked yet.

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
