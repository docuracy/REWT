# Evidence

[← REWT](index.md)

What each source can say, what it cannot, and whether it can be published.

## The modern network

**OS Open Rivers** (Ordnance Survey, Open Government Licence) is the spine: a national
watercourse network with names and topology. It is a *cartographic* product and does not
claim to be hydrologically routable — which is the whole of the first phase's work.

It says nothing whatever about premodern courses, and is treated as the least reliable
evidence in the places where most has changed.

## The map record

**Victorian six-inch sheets** (National Library of Scotland, georeferenced) are the base
for tracing. The surveyors sometimes state which of two channels is superseded —
*Old Course*, *New Cut* — and **GB1900**, a volunteer transcription of every label on
those sheets, makes those statements findable. A label is an assertion by someone who
was there, which is worth more than an inference from the modern line.

The **first series** matters where the second is too late: much of Victorian water supply
predates 1888, so for a valley drowned in the 1870s the second series shows the lake and
not the river.

## The documentary record

**Drainage and navigation legislation** records works authorised, undertakers, and land
taken — but authorisation is not execution, and several such powers were never
exercised. Nothing here may be read as *the river was navigable from this year*.

Their under-used value is different: a compulsory purchase is a legal act over **specific
ground**, and the plans and awards behind it commonly show the river *before* the work.

**Regional studies** — the Fenland Survey, the Humber Wetlands Project, the Somerset
Levels literature — answer locally what no national rule can: which channels are older
than they look, and which are engineering.

## Attested navigation

Existing scholarly GIS of pre-1348 inland navigation is used as an **index and a check**
— where to look, and whether a trace is corroborated — and **not** as geometry. Merging a
national synthesis with a traced line means reconciling two orders of accuracy at every
junction, silently, in exactly the places nobody is looking.

## Terrain

A terrain model can say whether water *can* get from one place to another, and cannot say
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
