# DECISIONS

Append-only. One entry per design decision, dated, with the reasoning and not just the
outcome. **Never silently reverse one** — if you disagree with an entry, write a new one
saying so and why.

These first ten were taken while planning, before any code existed. They are recorded so
that an agent picking the work up knows which choices were made deliberately, and can tell
them from choices nobody has yet made.

---

**D-001 — Start from a clean sheet; carry across no code and no data.** *2026-08-30*

A scoping exercise (*Premodern Rivers*) established the approach and, more usefully, what
goes wrong. Its curated corrections were made against that build's own graph, and
importing them would seed this one with another pipeline's assumptions — including the
ones the rebuild exists to leave behind. More importantly, Stage 1 must build an audit
that finds such defects on its own: **an audit handed its answers is not an audit.** They
remain a validation set, to be consulted after the audit works.

**D-002 — Stage 1 makes no historical claim at all.** *2026-08-30*

Dates, old courses, attestation and flow are later stages. The separation is not
fastidiousness: the predecessor's flow figures had to be withdrawn because they were
computed over a network the water could not leave, and the network's problems were
invisible underneath the historical ones. Get the water to the sea first, with nothing
else in the way.

**D-003 — Scope is decided on basins, not on the border, and not on network components.**
*2026-08-31*

A basin is in scope if any part of it lies in England or Wales; the whole of it then is.
Clipping to the political line strands the Tweed, four fifths of whose basin is in
Scotland, and the Border Esk, which rises in Cumbria and reaches the Solway in
Dumfriesshire. The cheap alternative — weakly connected components — fails differently and
instructively: OS models the Solway Firth as connected tidal water, so the Annan, Esk and
Eden land in one component and the test would drag Dumfriesshire into an England-and-Wales
project. **A shared estuary is not a shared catchment**, and only a topographic delineation
tells them apart.

**D-004 — Six sources, all Ordnance Survey or OGL, all open and redistributable.**
*2026-08-31*

OS Open Rivers, Terrain 50, Boundary-Line, OpenMap – Local, and the two 1 m LiDAR products
for England and Wales. The constraint is deliberate and worth defending: the repository is
intended to become public, and a single encumbered source would mean a licence review
before it could. Adding a seventh is a decision to be recorded here, not a convenience.

**D-005 — Build the network by crawling upstream from the sea, not by patching holes.**
*2026-08-31*

Seed at tidal termini and admit a link only when the node at its downstream end is already
in the network. Patching asks *is this hole closed?* and answers yes for a hole whose
closure leads somewhere else broken — a link-by-link check once reported every gap bridged
while 3,440 km of river still drained into nowhere. The crawl cannot answer yes for a
reach the water cannot leave, and what it fails to reach *is* the defect report.

**D-006 — Terrain 50 nationally; 1 m LiDAR per section only.** *2026-08-31*

The elevation range inside a river component is a median 115 m, so Terrain 50's ~4 m error
is irrelevant for basin delineation and for identifying a component's outlet. LiDAR earns
its place only where the differences are decimetres — adjudicating a single link. A
national LiDAR pass would be a large expense for no gain.

**D-007 — A DEM screens flow direction; it never decides it.** *2026-08-31*

Measured against OS's stated direction, Terrain 50 clearly disagrees on 0.6% of links —
757 nationally, a workable list. But it sits inside its own error bar on 82% of canal
links, 89% of tidal and 92% of lake, against 47% of inland river: **it screens the uplands,
where you least need it, and is silent on the levels, where you most do.** No link is
flipped on terrain evidence alone, and no correction is reported as terrain-evidenced when
the fall was inside the error bar. Sample the unconditioned surface, never one the network
has been burned into.

**D-008 — Route through standing water, and flag the route for what it is.** *2026-08-31*

Where OS Open Rivers draws a schematic straight line across a lake (~2,300 km of the
network) that line is a routing device, not a course; where it draws nothing, the medial
axis of an OpenMap – Local polygon supplies one. Stage 1 makes no historical claim so
either is admissible, but both are flagged, because a reservoir crossing is a modern
artefact with a valley underneath it and a later stage must not mistake it for a channel.

**D-009 — The productive audit signal is sinks per component, not the lowest point.**
*2026-08-31*

Testing whether each component's flow direction drains to its lowest node was measured and
does not pay: the outlet is already within 2 m of the minimum in over 90% of components,
and only 37 nationally are more than 5 m out. The reason is structural — **reversing one
link mid-tree does not move the component's outlet**, it creates a new sink partway up — so
the test is blind to the common fault. Counting sinks per component finds it instead, and
needs no elevation at all. The 90% is not wasted: it establishes that a component's lowest
node is a **trustworthy root**, which is what licenses orienting a spanning tree toward it
to give level canals a direction that no gradient can.

**D-010 — Python, DuckDB with its spatial extension, stages under one entry point.**
*2026-08-31*

Recorded as **defaults, not commandments**. DuckDB proved a good fit in the predecessor and
one module owning the connection keeps a move to PostGIS cheap. Language, layout and the
runner are the implementing agent's call; overturn any of this with a reason recorded here.
Nothing in `PLAN.md` §1–§6 depends on the choice.

**D-011 — Canals are inside the reachability requirement.** *2026-08-31*

Stephen's call, and the plan previously left it open. Excluding canals would have been
easier and is wrong on three counts.

**Many links OS types as `canal` are canalised rivers.** The Aire and Calder, the Calder
and Hebble, the Wey, the Itchen, the Fossdyke, the Sheffield and South Yorkshire. Those
*are* the drainage; setting them aside leaves a hole where a river should be, and the
`form` attribute is not a reliable way to tell a canalised river from an artificial cut.

**Canals cross watersheds and join basins**, so a network that omits them cannot be
reconciled where a canal is the only continuous line between two river sections. This was
Stephen's stated reason and it is the decisive one.

**And it is a bounded piece of work.** Measured: 2,706 km of canal in 538 components, of
which 1,932 km already sits in a component holding river, lake or tidal water and needs no
new geometry. The remaining 774 km is in 289 canal-only components, and **every one has a
non-canal watercourse within 2 km** — 163 within 10 m (junctions, not connectors: a node
is merged, nothing is invented), 65 within 50 m, and only 28 beyond 200 m. Roughly 290
adjudications, most of them trivial.

Two consequences to carry. A canal reaches the sea **through a structure** — lock,
overflow weir, feeder — that the survey does not draw, so it is attached to the receiving
watercourse where the structure actually is, as a curated judgement, and never by reversing
canal links until the total improves. And **a canal may legitimately have two outlets**:
water leaves a summit pound in both directions, so the one-sink-per-component expectation
does not apply to it. That is what the `mode: both` case exists for.

*Forward note for a later stage, recorded here so it is not rediscovered:* including canals
in the modern network is not a licence to route historical water down them. A 1790s cut
must not carry 1348 water. The predecessor made exactly this mistake with post-medieval Fen
drains, and the fix belongs in the dating stage, not here.

---

*The entries below were taken while implementing Stage 1.*

**D-012 — Python 3.10, DuckDB, a pinned virtualenv, and stages as a registry rather
than a list.** *2026-08-31*

D-010 recorded Python and DuckDB as defaults; both are kept, and nothing was found that
argues against either. Three things it left open are settled here.

**Dependencies are pinned in `requirements.txt` and installed into `.venv`.** "One
command from an empty checkout, producing the same result every time" is not satisfied
by whatever happens to be on the machine.

**Stages declare what they read and what they write** (`rewt/pipeline.py`), and the run
order is derived from those declarations. PLAN.md §2 asks for this because one stage
once rebuilt a table another had written columns into. Declaring it is not enough on
its own, so the registry additionally **refuses to let two stages write the same
artefact** — that is the shape the failure actually took.

**A stage is skipped only when its fingerprint matches and its outputs exist.** The
fingerprint covers the stage's own source code, the parameters it declares it reads,
the source declarations it reads, and the fingerprints of everything upstream. This is
the answer to the corrected setting that sat unused for a month behind a cached raster.

**D-013 — Two identifier schemes: the publisher's, and a digest of our own geometry.**
*2026-08-31*

PLAN.md §10 requires that a stretch present in two published editions carries the same
id in both, which rules out anything derived from row order. A feature that came from
Ordnance Survey keeps its identity as `os:link:<uuid>`. A feature this project creates
is identified by *what it is* — `rewt:link:<digest of its own geometry>` — so rebuilding
the database gives a connector between the same two places the same id again, and a
reader can tell survey from correction without reading the code (§7).

The line digest is direction-independent, because a reversal moves no geometry.

**D-014 — No stage adds a column to another stage's table, and there is exactly one
routing graph.** *2026-08-31*

Scope, reachability and flags are narrow tables keyed on `link_id` (`link_scope`,
`link_reach`, `link_flag`) rather than columns on `link`. `link` is written once, by the
loader, and never altered. This is a direct answer to §2's stale-values failure: a stage
cannot leave another stage's column behind if it has no column there.

The routing graph is the table `edge`, and it is the only one. §8 records that two
graphs over one geometry could not be reconciled after the fact, and that this is where
the predecessor stopped. A reversal exists in `edge` and nowhere else; `link` keeps the
geometry and the published attributes untouched, exactly as §5 requires.

**D-015 — The loader's calibration tolerance is 3%, and the check is a gate.**
*2026-08-31*

PLAN.md §6 gives figures for OS Open Rivers *as shipped*, and says that if the loader
does not match closely, nothing downstream is worth looking at. The issue in hand is
2026-04; the plan's figures were measured on an earlier one, and the product is
reissued twice a year.

Measured: total links -0.1%, inlandRiver -0.7% / -0.0%, canal -0.5% / -0.0%, tidalRiver
-0.4% / +0.0%, lake -1.4% / **-2.4%**, nodes 197,734 against ~198,000, and **exactly
three** links recorded against the digitised line. Lake links are the most heavily
generalised and move most between issues. A loader bug is structural — wrong units,
dropped rows, misparsed forms — and would show as tens of per cent, so 3% separates the
two cases. The check raises and stops the build; it is not a warning.

**D-016 — D-011's canal band table reproduces exactly; its reading of the nearest band
does not.** *2026-08-31*

The census independently reproduces D-011's measurements on issue 2026-04: 2,721 km of
canal against 2,706, 1,947 km already sharing a component with river, lake or tidal
water against 1,932, **288 canal-only components against 289**, 774 km against 774, and
the distance bands **163 / 67 / 30 / 28** against D-011's **163 / 65 / 33 / 28**. Two
independent measurements agreeing this closely is worth having.

**The interpretation is where they part.** D-011 reads the nearest band as "163 within
10 m — touching, merely unjoined", and concludes that those are "**junctions, not
connectors** — no geometry is invented, a node is merged". Measured on this issue, that
does not hold. Of the 663 endpoints belonging to canal-only components, **five** lie
within a metre of a non-canal watercourse, and fourteen within ten metres. The 151
components sitting at exactly 0 m are therefore, in the main, canal lines **crossing**
river lines with both their own ends elsewhere.

A canal crossing a river mid-line is the signature of an aqueduct or a culvert — a
structure built to keep the two waters apart. Merging a node there would route the river
down the canal, which is the opposite of the intended repair. So the nearest band is not
163 cheap junctions; it is 163 adjudications, most of which will conclude *do not join*.

This does not disturb D-011's decision, which is that canals are inside the
reachability requirement, and it does not make the work unbounded — it is still ~290
places. It disturbs the estimate of how much of it is trivial, and it is recorded so
that the estimate is not quoted again unexamined. **Each is still to be adjudicated at
the place**, per D-011.

**D-017 — Write no raster a downstream tool cannot read, and check the artefact rather
than the return code.** *2026-08-31*

The interim Terrain 50 mosaic is written as DEFLATE **without a predictor**, and every
raster this project derives is checked for a plausible value before anything reads it.

WhiteboxTools reads GeoTIFF with its own decoder rather than GDAL's, and it cannot
decode DEFLATE with a horizontal predictor. Handed such a file, `FillBurn` **returns
success and writes a raster of NaN and 3.3e38**, with one 512-column stripe of
plausible values at the left edge. `BreachDepressionsLeastCost` then consumed that and
produced a surface which was **finite everywhere and meaningless everywhere** — so a
guard testing only for NaN would have passed it. Forty-one million "basins" were
delineated from the result, and every stage reported success.

Three builds and two wrong diagnoses went into finding this, and both wrong turns are
worth recording because they are the general lesson.

**The first wrong diagnosis was a size limit.** A windowed test of the same size
succeeded, so the difference looked like grid extent, and a clip was written into
`conf/params.yml` as if it were the fix. **The second was stream geometry outside the
raster** — plausible, and also wrong. Both survived because the test that "passed" had
read its raster window and its streams through the same bounding box, which quietly
removed the variable actually under test. *A control that changes two things at once
proves nothing, and reads exactly like a control that changed one.*

What found it was neither theory but a difference nobody had thought to look at: two
DEMs identical cell for cell, of different file sizes, one of which worked.

Hence the rule, which generalises past this tool: **a return code is not evidence that
a tool did anything.** `rewt/raster.py:assert_usable` takes a plausible range rather
than testing finiteness, and is called after burning, after breaching and after
delineation. The clip at `terrain.northing_max_m` is kept, but on its own merits — D-003
puts Scotland outside the project — and its note now says so instead of claiming a fix
it never made.

**D-018 — GB1900 is registered from the CC0 raw dump, never from the gazetteers.**
*2026-08-31*

*Recorded from the documentation work (rewt-1d); the reasoning is theirs.*

Vision of Britain publishes the GB1900 transcriptions three ways. The abridged and
complete *gazetteers* are CC-BY-SA; the *raw dump* is CC0. Share-alike on an input would
reach every export this project makes, which is the one thing D-004 exists to prevent,
so the gazetteers are excluded on licence grounds alone. They are also the wrong file:
the abridgement drops every string occurring 300 or more times nationally, and *Mill
Race*, *Mill Pond* and *Towing Path* are all well above that cut. The cost of the raw
dump is that it holds individual volunteer readings rather than an agreed text, so a
consensus step is ours — the reading most volunteers gave each pin. Copies of the
abridged file exist elsewhere on the development machine and must not be substituted.

**It is registered as a stage 2 source, and the build cannot read it.** A dated
historical source in Stage 1's own input registry is exactly what CLAUDE.md's first
override exists to catch, and marking it `used_by: docs` in a comment would rely on
care. So `conf/sources.yml` carries `stage: 2`, and `rewt/pipeline.py` **refuses to
register a stage that declares a source whose stage is not 1**. The drift AGENTS.md
warns about — "not refusing this outright, but drifting into it a little at a time
because a field looked easy to add" — now fails at import.

**D-019 — GB1900 label counts are published per place, and for England and Wales only.**
*2026-08-31*

*Recorded from the documentation work (rewt-1d); the reasoning is theirs.*

The Ordnance Survey repeated a name along the feature it named, so a count of labels is
a count of type rather than of rivers. Published counts therefore collapse labels
reading the same thing within a kilometre of each other. The correction proves small —
139 *Old Course* labels become 126 places, and no two are within 300 m of each other —
and it is reported anyway, because the reader cannot tell which was meant otherwise.
The extent correction is the large one: 1,888 of 6,884 mill-channel labels in Great
Britain are Scottish, *lade* and *lead* being Scots, and D-003 puts Scotland outside the
project. The predecessor's figure of 10,738 mill channels does not reproduce from the
source at any extent and is superseded by 4,996 labels at some 4,068 places in England
and Wales.

**D-020 — Reservoir construction dates come from the map series, not from Wikidata.**
*2026-08-31*

*Recorded from the documentation work (rewt-1d); the reasoning is theirs.*

Wikidata was tested for this directly and fails: of 1,125 items typed as reservoirs in
the United Kingdom, 24 carry a construction date, and Kielder, Rutland, Ladybower,
Haweswater, Vyrnwy and Derwent are all among those that do not. The dam records are no
better — 101 items, 5 dated. A valley drawn as a river on the OS first edition and as
water on the second was flooded between the two surveys, which brackets it to a couple
of decades and falls out of work the project has to do anyway.

Related and separate, and it bears on Stage 1's own reservoir flag (§5, D-008): **the
network cannot find the reservoirs by itself.** OS Open Rivers names 6,042 of its 24,146
`lake` links and not one of those names contains the word "Reservoir" — a lake link
carries the name of the river running through it. So the reservoir flag D-008 asks for
cannot come from the network's own attributes, and a gazetteer would have to be declared
before it can be earned. It is not earned in this build, and is not claimed.

**D-021 — The EIDC reservoir inventory is registered, and it is what tells a tracer
which OS edition to open.** *2026-08-31*

*Researched by rewt-86; measurements are reproducible from the script named below.*

D-020 established that reservoir construction dates cannot be looked up on Wikidata
(24 dated of 1,125) and that the map series must date them instead: a valley drawn as a
river on the first edition and as water on the second was flooded between the two
surveys. That remains true and is not reversed here. What D-020 missed is that the
comparison is only cheap once you know which two sheets to compare. Choosing the
edition is the expensive part, and a construction date chooses it in advance.

`Inventory of reservoirs amounting to 90% of total UK storage` (Durant and Counsell,
2018, NERC EIDC) carries a completion year for 252 of its 273 reservoirs and a planning
year for 240, each with a data-quality flag, 355 references and a per-reservoir note.
233 of the 273 are in England and Wales.

Compared per reservoir against the National Library of Scotland's County Series survey
dates for the historic county each one sits in, the 233 divide:

| verdict | all | impounding only |
|---|---|---|
| the 2nd edition shows the valley | 130 | 95 |
| 2nd edition, but surveyed while it was being built | 9 | 9 |
| 1st edition only | 15 | 14 |
| 1st edition, but surveyed while it was being built | 36 | 26 |
| earlier than both editions | 23 | 19 |
| no completion date | 20 | 2 |

So for the impounding reservoirs — the ones that actually drowned a valley — **40% need
the first edition or earlier**, and nineteen predate both editions entirely and will
need a pre-Ordnance-Survey county map or nothing. That is knowable before anyone opens
a sheet, per reservoir, by name.

**Two things it is not.** It is not a national gazetteer of reservoirs: coverage is by
storage volume, the stated rule is over 1,600 Ml, and only 25 of the 273 hold less than
1,000 thousand m3. The small Victorian impoundments are absent by design. And it does
not earn the drowned-valley count: 493 of the 24,146 `lake` links in OS Open Rivers lie
within 500 m of an entry, against the 1,834 links over 606 reservoirs the scoping
exercise inherited. It earns about a quarter of that count. The rest stays inherited.

**Its licence had to be established from the DOI, not from the page.** The CEH catalogue
record and the DOI both return HTTP 500, and the download bundle's own `readme.html`
reads "Unable to retrieve citation and licence information for: f5a7d56c-..." — a server
fault, not a statement. data.gov.uk asserts OGL v3.0 in a site-wide footer, which is not
evidence about a particular dataset. The DataCite record for
`10.5285/f5a7d56c-cea0-4f00-b159-c3788a3b2b38` carries `rightsIdentifier: ogl-uk-3.0`
and the required citation, and that is what the entry records.

**Registered `stage: 2`.** Construction dates are the clearest possible case of
CLAUDE.md's first override, and `rewt/pipeline.py` refuses to register a Stage 1 stage
that declares it.

---

**D-022 — Mills of Britain is registered for two layers, and it dates maps, not mills.**
*2026-08-31*

*Researched by rewt-86.*

The question asked of it was whether it records the earliest date at which a mill is
known to have existed at each site. **It does not.** Its `Year` field is documented as
"Final year of survey; or, if not specified, year of final publication" — of the map the
mill was read from. It is a terminus ante quem from cartographic attestation. There is
no documentary, Domesday or archaeological earliest date anywhere in it, and nothing
derived from it may be phrased as "a mill was built in this year".

What it does give is attestation 60 to 170 years earlier than the GB1900 sheets.
`MillsofBritain_17291836_v2` holds 23,621 mill records read from pre-Ordnance-Survey
county maps, estate maps and the Roy Military Survey, dated 1729-1836 with a median of
1818. 17,120 are in England and Wales; 10,371 of those are watermill-class, at some
5,150 places when collapsed at 1 km by the D-019 rule.

**It is genuinely additional to GB1900, and measurably so.** 7,874 of the 10,371 have no
record in the project's own GB1900-derived layer within 100 m, and 4,930 have none
within 250 m. Roughly half the pre-OS watermill sites are not where the Victorian
sheets put a mill.

**It indicates a leat; it does not locate one.** The authors attach `W275?` and `W425?`
flags — whether the mill falls within 275 m or 425 m of a river — which is itself an
admission of positional accuracy, and they warn that locations "may not exactly
coincide" with the Ordnance Survey. Measured against OS Open Rivers, 80.5% of the
England-and-Wales watermill-class records lie within 50 m of an inlandRiver or canal
link and 94.1% within 250 m. The authors also state that drainage mills (47 records),
threshing mills and animal-powered mills are heavily under-recorded. Absence is not
evidence of absence.

**Only two of the article's layers are registered, and the reason is D-018's reason.**
The figshare article is labelled CC BY 4.0, but the authors' documentation says "This
license does not apply to the founding datasets integral to the production of our
original data", and the collection adds "No claim to datasets from which data in this
study were derived: OS data under (c)Crown Copyright 2007, License number 100017572;
... data under (c)The Canal & River Trust copyright [database right] (2015)".
`GB_Barriers`, `RawPower` and the basin and county power layers rest on those. The two
mill point layers are the authors' own original data. An article-level licence is not a
file-level licence, which is exactly what D-018 records about GB1900.

**`MillsofBritain_18931914_v2` is not independent evidence.** It is 12,860 records
filtered from GB1900 itself, so it overlaps whatever D-019 counts and must not be added
to it. Its authors also require that GB1900-derived records be redistributed under CC0.

**D-023 — A licence is a claim about a specific dataset, and must be traced to a
statement about that dataset.** *2026-08-31*

*Researched by rewt-86; the rule generalises D-018, which rewt-1d recorded.*

AGENTS.md requires a source's licence and required attribution to be recorded before
the source is added. It does not say where to look, and in one afternoon of vetting
three sources the same error appeared in four different disguises. Each one would have
produced a defensible-sounding entry, and two of them would have been wrong.

**A site-wide footer is not a licence.** data.gov.uk carries "All content is available
under the Open Government Licence v3.0, except where otherwise stated" on every page.
That is a statement about the site. It happened to be right for the EIDC reservoir
inventory, and it would have been right for the wrong reason.

**A collection-level label is not a licence for the items in it.** The figshare
collection *Historic Waterpower Britain* adds "No claim to datasets from which data in
this study were derived: OS data under ©Crown Copyright 2007, License number 100017572;
... data under ©The Canal & River Trust copyright [database right] (2015)".

**An article-level label is not a licence for the files in it.** The same project's
figshare article is labelled CC BY 4.0, while its own documentation says "This license
does not apply to the founding datasets integral to the production of our original
data". `GB_Barriers`, `RawPower` and the derived power layers rest on those. Only the
two mill point layers are the authors' to license, and only those are registered.

**A publishing platform is not the publisher.** DataMapWales shows OGL for both of
Natural Resources Wales's Reservoirs Act layers. NRW's own catalogue agrees for
`Registered information` (NRW_DS125216) and contradicts it for `Locations and
undertakers` (NRW_DS125215), which says "NRW may NOT publish or disseminate the data
freely" and re-usable only "in line with the terms of a NRW licence" — it carries named
engineers and their addresses. Two official statements, one wrong.

And **D-018 is the fifth instance one level up**: the GB1900 gazetteers are CC-BY-SA and
the raw dump is CC0, in the same place, from the same publisher.

**The rule.** Trace the licence to a statement about the dataset, layer or file being
registered. Where a source is published at more than one granularity, the narrowest
statement governs, and where two official statements conflict, neither is taken on
preference — the publisher's own catalogue is preferred over a platform hosting the
data, and if that is not decisive the source is registered as unresolved or not at all.

**Two routes for when the publisher's own pages fail**, both used here:

- **DataCite, by DOI.** CEH's catalogue record and the DOI landing page both returned
  HTTP 500 and the download bundle's own `readme.html` read "Unable to retrieve citation
  and licence information for: f5a7d56c-...". `api.datacite.org/dois/<doi>` returned
  `rightsIdentifier: ogl-uk-3.0` and the required citation.
- **A GeoNetwork catalogue's XML formatter.** `metadata.naturalresources.wales`'s HTML
  is JavaScript-rendered and yields nothing to a plain fetch, but
  `/geonetwork/srv/api/records/<id>/formatters/xml` returns ISO 19139 with the licence
  in `gmd:resourceConstraints`.

**This is retrospective.** The six sources registered before this entry were vetted
against the older, looser standard. `nrw_lidar_dtm_1m` has since been traced to
NRW_DS116814 and is confirmed OGL. `ea_lidar_composite_dtm_1m` has NOT been traced to a
per-dataset statement and its OGL v3 claim currently rests on the Environment Agency's
site, which is the first disguise in the list above. The four Ordnance Survey products
are covered by published product licences and are not in doubt. Tracing the Environment
Agency entry is outstanding work, recorded here so it is not forgotten rather than
because it is thought to be wrong.

**D-024 — Burn only inland rivers and lakes into the DEM. Burning tidal water destroys
the delineation the DEM exists to provide.** *2026-08-31*

PLAN.md §4.1 warns that OS Open Rivers models the Solway Firth as connected tidal water,
so the Annan, the Border Esk and the Eden fall into a single *network component*, and
that using components as basins would therefore pull in the Annan and the Nith — rivers
that share the Solway **estuary** with the Eden and the Esk while sharing no catchment
with them. **The same trap exists in raster form and the plan does not name it there.**

*To be unambiguous, because the wording here first read as though it were about the
border:* this is an argument about method, not about nationality. **Ground outside
England and Wales that the network needs in order to be coherent is in, and the border
is no bar to it.** A basin with any part in England or Wales is in scope entire,
Scottish headwaters included — the Tweed, four fifths of it Scottish, and the Border
Esk, which rises in Cumbria and reaches the sea in Dumfriesshire. Seeds are taken from
anywhere in such a basin including Scotland, and the crawl stage refuses to run if
configured otherwise. What §4.1 leaves out is only what drains *solely* to Scotland.

Burning the network into the terrain incises a channel wherever a link runs. The 5,738 km
of `tidalRiver` links run up estuaries and along coasts, so burning them carves a
continuous trench that joins one river mouth to the next. Measured, with tidal links in
the burn: **one basin held 181,672 km², 88% of the land area, spanning 110,000–659,950 E
and 10,050–700,000 N** — the whole country — while the median basin was 0.1 km² and only
four exceeded 1,000 km². Every stage reported success.

That is not a delineation with a bug in it. It is the DEM being told, by us, that a
shared estuary *is* a shared catchment — which is precisely the proposition §4.1 acquires
Terrain 50 in order to refute. Burning tidal water spends the one instrument that can
tell the two apart on asserting the thing it was meant to test.

`canal` is excluded for the same reason from the other side. Canals cross watersheds by
design — that is D-011's second and decisive argument for keeping them — so a burned
summit pound joins two basins the terrain separates.

**This narrows the burn and nothing else.** Excluding canals and tidal links from the
burn does not exclude them from the network, from the routing graph, or from the
reachability requirement: D-011 stands unchanged, and canals remain inside it. The
decision says only that the terrain is not carved along an artificial cut, or along
water whose surface is the sea, when asking where water would naturally go.

*How it was found is worth recording too.* The delineation reported 1,123 basins, which
is a plausible number for a coastline, and a conditioned surface that was 44.6% plausible
with a sensible elevation range — every aggregate looked right. It failed on the first
question asked of the distribution rather than the total: a median basin of 0.1 km²
against a largest of 181,672. AGENTS.md's *report at the place, not only in the total*
applies to a project's own intermediate artefacts and not only to its findings.

**D-025 — Where a publisher contradicts itself, the project may choose a reading — but
it records that it chose, and how much rides on it.** *2026-08-31*

*Stephen's ruling on the RCAHMW case; recorded because it is a different act from
D-023's, not an instance of it.*

D-023 is about establishing **what a publisher said**, when the answer is scattered
across a site footer, a collection label, an article label and a hosting platform. Every
one of those cases is resolved by finding the narrowest statement about the actual
dataset. **This is the case that rule does not reach: a publisher saying two
incompatible things at the same level, about the same records.** RCAHMW's Coflein terms
place the digital site data under Open Government Licence v2.0, which permits commercial
re-use without permission, and two sentences later require prior written permission to
compile the same data for commercial or organisational use. There is no narrower
statement to prefer, because both are the owner's, about the same thing.

**The ruling is to take the more permissive statement as governing the site data**, on
three grounds: the permission clause is restated in the same passage with the *archive*
records named explicitly, so it most likely governs those; both named licences are real
and correctly versioned (OGL 2.0 and Non-Commercial Government Licence 1.0) whereas a
"Commercial Government Licence 2.0" the same passage mentions is not a licence that
exists, which tells you how carefully the passage was drafted; and the open statement is
the one attached to the download route.

**Two things this entry must not be read as.**

It is not a general licence to resolve ambiguity in the project's favour. The default
where an owner contradicts itself is still to ask a person, and that is what happened
here — this is a recorded human ruling, not a rule an agent may apply on its own.

And **the exposure here is small precisely because the source was rejected on its
content.** Nothing in the repository reads RCAHMW data, there is no entry for it in
`conf/sources.yml`, and under the ruling that unusable sources are described in prose
rather than registered, there never will be. The reading is not load-bearing. A future
reader should know it was taken cheaply, and should not cite it as a precedent for a
source that anything actually depends on.
