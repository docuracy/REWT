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

**D-026 — The predecessor's 73 corrections corroborate the audit, and the comparison
must be made by place rather than by identifier.** *2026-08-31*

D-001 held the validation set back until the audit worked on its own. It does, so the
comparison has been made (`published/audit/validation.md`, reproducible as
`rewt validate`).

**Comparing by identifier is not possible, and that is the first finding.** OS Open
Rivers is reissued twice a year, and **12 of the 73 corrections reference a link that
does not exist in issue 2026-04 at all**. Of the 25 junction targets, 13 survive; of the
45 link ids the connectors reference, 32. Compared by id, the reissue's own churn would
have been reported as a disagreement about rivers. This is the concrete cost that
PLAN.md §10's stable-identifier requirement exists to avoid, and D-013's scheme is the
answer to it.

**On the 61 recoverable places, this project's audit independently finds a defect at 30
— 49%.** A further 24 show no defect and now drain, either because this build's own
corrections reached them or because the survey has since been amended. **Seven are
genuine disagreements** and are named individually in the write-up.

**The agreement is strongest exactly where this project has done no work.** Fourteen of
the seventeen places the predecessor reversed a link still show a dead end here, and
**no reversal has been authored in this repository at all** — so that agreement is
entirely independent of anything done here, and it is a list of work outstanding rather
than work confirmed.

**And the two projects rank the same defects by different instruments.** The
predecessor's reasons read *"37.76 m3/s arrives at the downstream end of the Well Creek
and stops"* — it ranked by modelled flow. §8 records what that cost: a flow model
reports a confident number over a network the water cannot leave, and months of figures
were withdrawn. This project ranks by the length of network standing above a defect,
which needs no model and cannot fail in that way. **The two orderings agree about which
places matter far more often than they disagree** — which is itself worth recording,
because it means the flow model was not buying much of the ordering it was risking so
much to produce.

*One methodological note, because it nearly became a false finding.* The predecessor's
connectors are GeoJSON with no `crs` member, which by the specification means WGS84, and
they are indeed in degrees. Compared as though they were National Grid metres, all 31
landed in the ocean and the comparison reported that this project had independently
found none of them — which reads exactly like a substantive disagreement about
connectors, and was a unit error. It was caught only because 0 of 31 was too clean a
result to believe. **An implausibly tidy disagreement deserves the same suspicion as an
implausibly tidy agreement.**

**D-027 — Dates on evidence are recorded in the Linked Places Format `when` object,
with both bounds optional.** *2026-08-31*

*Decided by Stephen; drafted by rewt-86.*

**An epoch is a year the project draws. It is not the same thing as what the project
knows about a stretch**, and conflating the two is how the old 1348 datum came about. So
evidence dates are recorded separately from the dates that get built, as a set of
`timespans`, each with an optional `start` and an optional `end`, each of those either
`in` a year or bounded by `earliest` and `latest`, with a `certainty` on the whole.

**Both bounds are optional, and that is the point.** Almost every source this project has
appraised knows one bound and not the other, and each knows a different one:

| what the source says | recorded as |
|---|---|
| a mill on a map surveyed 1824 | `start: {latest: 1824}` |
| a channel labelled on a sheet surveyed 1899 | `start: {latest: 1899}`, `end: {earliest: 1899}` |
| a reservoir completed 1869 | `start: {in: 1869}`; the drowned channel's `end: {in: 1869}` |
| a valley river on the 1st edition, water on the 2nd | `end: {earliest: 1854, latest: 1894}` |
| a declared year built that is visibly rounded | `start: {earliest: 1870, latest: 1880}`, `certainty: less-certain` |
| a waterway already navigable when a window opens in 1600 | `start: {latest: 1600}` |
| navigable at some point, no year given | `start: {latest: 1600}` — the same encoding |
| an attestation carrying no start date at all | `end` only, **`start` absent** |

**The last two rows are the argument.** A model that requires a start forces every source
to invent the half it does not have, and the invention then reads as a finding — which is
exactly how a datum comes to be fixed by the weakest constraint in the evidence. An absent
`start` says *nobody knows when this began*, which is true and publishable. And a censoring
floor and a bare "navigable once, no year" flag carry **identical information**: a plain
year column makes one look like a date and the other like a hole.

**It moves D-022 out of a footnote and into the data.** That decision exists because the
pre-Ordnance-Survey mill mapping's year is the *map's* year, a terminus ante quem.
`start: {latest: 1824}` says so structurally; a `date` column says the opposite.

**Unknown is not unbounded.** A missing `start` because nobody knows is a different
statement from a channel deliberately modelled as having no beginning, and the two must
not collapse into the same empty field.

**Two guards, part of the decision rather than commentary.** A bound is not a licence to
interpolate — `start: {latest: 1600}` and nothing else must not be drawn at 1540 because
the arithmetic permits it. And documentary uncertainty must never be blended with model
uncertainty; one confidence number over both is worse than neither.

**On convergence, and why this is not a formatting preference.** Linked Places is the
interchange format for historical gazetteer work; its current draft relaxes the
requirement for a `start` and carries `certainty` on the timespan, which is what evidence
of this kind needs. The PLATO attestation ontology expresses the same information as a
four-date model — `startEarliest` / `startLatest` / `endEarliest` / `endLatest`, aligned
with PeriodO — and adds a precision term and an explicit flag for a bound deliberately
left open rather than unknown. The two are inter-convertible. **The aim is to be
expressible in either rather than to invent a third thing**, which matters here because a
river reach carrying its own evidence *is* an attestation, and other people are already
solving that modelling problem.

**Stage 2, and it must not reach Stage 1.** CLAUDE.md's first override applies: if a task
requires knowing what year it is, it is not Stage 1. No Stage 1 table gains a date column
because of this, and `rewt/pipeline.py` never sees it.

**D-028 — One basin delineation, run after repair, because the second pass was measured
and would return the same basins.** *2026-08-31*

PLAN.md §4.1 asks for two passes: *basins are recomputed after repair, not before.
Repair changes connectivity, so an early delineation is provisional. Use a generous
provisional scope to avoid doing national work, and re-derive basins once the network is
closed.* This build runs one, after repair, and the reason is a measurement rather than
a convenience.

**The raster delineation depends on the network only through the burn.** The repaired
geometry — 733 connectors, 32.2 km — adds **644 cells to a 2,673,201-cell burn
footprint: 0.024%, or 1.61 km² of 6,683 km²**. And it is not merely small: every one of
those cells lies *between two channels that were already burned*, because a connector
closes a gap. It does not carve a path across a watershed, which is the only thing that
would move a basin boundary. A second conditioning pass would cost ten minutes and
return the same 877 basins.

**What genuinely changes with repair is not the raster but the graph**, and that is
computed after repair here: which node is a basin's outlet (a reversal or a connector
can move it), and which links are in scope (the connectors are links and must be
scoped). Those are the parts §4.1 is actually protecting, and running the whole stage
after repair gets them right.

So `basin.provisional` is **false** in this build. It would be dishonest to ship a
column saying the delineation is provisional when nothing further is going to be done
to it.

**This is a departure from the plan's stated procedure and not from its reasoning.** If
a later stage adds geometry that *does* cross a watershed — a canal feeder over a summit,
say, or a skeletonised route through a water body that joins two catchments — the
measurement above stops holding and the second pass has to come back. The number to
re-check is the one in the first paragraph.

**D-029 — If a coastline is ever needed, it is Boundary-Line's `high_water`, never
OpenStreetMap. And Stage 1's seeds are not one of the things it may be used for.**
*2026-09-01*

*Found by rewt-86 while checking a licence; verified here.*

**The licence half.** OS Boundary-Line — already declared, already fetched — carries a
`high_water` layer: 32,850 MultiLineString features of High Water Mark, EPSG:27700,
covering Great Britain. So the project already owns a coastline and needs no new source
to have one.

The reason to write that down is what the obvious alternative would cost. The nearest
ready-made coastal graph is built on **OpenStreetMap land polygons, which are ODbL** —
share-alike on derivative databases. A coastal network derived from those would be a
derivative database, and the share-alike would propagate into everything this project
publishes. That is precisely the situation D-004 exists to prevent, and it would be
discovered late, by someone doing a licence review of a finished product. The same
applies to Viabundus Water 1500, which is CC BY-SA. **Two encumbered coastlines are
easy to reach for and one unencumbered one is already in `data/raw`.**

Two properties to carry: `high_water` is the mean-high-water line, so it is a coastline
rather than a navigable-water boundary; and it is British, so it needs the same country
filter §4.1 already applies to everything else.

**The Stage 1 half, which is a prohibition.** Nothing above licenses using it for
seeding, and PLAN.md §5 forbids exactly that:

> **Seeds are a finding, not a parameter.** A seed is a node with no outflow standing at
> tidal water. Take them from the survey's own `form = tidalRiver`, **not from a
> coastline**: a coastline decides the question by distance from a modern shore, and is
> wrong at exactly the estuaries where the answer matters.

A coastline is the most natural wrong tool for the job this project spends most of its
effort on, and now that one is known to be in the acquisition it is *more* likely to be
reached for, not less. This build takes its 2,246 seeds from `form = tidalRiver` and
will go on doing so. `high_water` is registered here as available for a later stage's
coastal work and for nothing in Stage 1.

*Also confirmed, and it changes nothing:* the terrain data behind that same coastal tool
is the Environment Agency's own, attributed *"United Kingdom terrain data © Environment
Agency copyright and/or database right 2015"*, resampled to roughly 20–30 m. It is the
same provenance as `ea_lidar_composite_dtm_1m` at a fortieth of the resolution, so it is
not a substitute for per-section LiDAR (D-006). Its one advantage is that it is seamless
and so has no coverage-boundary trap — no equivalent of the 0.0-m-over-Wales behaviour
that entry warns about. Worth knowing; not worth switching to.

**D-030 — A seventh source the build reads: the Canal & River Trust's navigation
structures. They are evidence of a structure, never a coordinate.** *2026-09-01*

*Found and licence-checked by rewt-86; verified, measured and landed here.*

D-004 fixed the input list at six and said that **adding a seventh is a decision to be
recorded here, not a convenience**. This is the seventh, and it is the first source
since that decision that the Stage 1 build actually reads.

**What licenses it is that PLAN.md asks for it by name.** D-011: *a canal reaches the
sea through a structure — a lock, an overflow weir, a feeder — that the survey does not
draw. Connect it to the receiving watercourse **where the structure actually is**.*
Until now nothing supplied where that was, and the canal connectors in `data/curated/`
admitted it in their own evidence: *the position is the nearest approach, not a surveyed
structure. That is the weakest evidence in this file.* 1,722 locks, 1,108 weirs, 329
aqueducts, 2,962 culverts, 103 tunnel portals and one boat lift now answer it.

**The licence is D-023's shape for the sixth time.** The Trust's portal licenses **per
dataset**: of 30 datasets, 13 are OGL v3, 14 carry a bespoke Canal & River Trust licence
and 2 an INSPIRE end-user licence. The six point-structure layers are the open ones; the
**canal geometry is not** — "Canals By Navigation View", "Canals By KM Length View",
"Canal Reference Map" and "Tunnels View" are all bespoke, Docks and Embankments INSPIRE.
Fortunately the encumbered half is the half we do not need: OS Open Rivers already gives
canal geometry as `form = canal`. The excluded layers are named in the entry so nobody
adds them back.

**The measurement that decides how they may be used, and it is the whole of this
entry.** A Canal & River Trust lock and an OS Open Rivers canal line are two independent
products and they do not coincide. Measured against issue 2026-04: of 1,722 locks, 1,607
have any OS watercourse within 300 m; the median offset is **11.5 m**, the 90th
percentile **108.1 m**, the maximum **297.6 m**, and for **28%** the nearest OS link is
not even a canal.

So a structure here says *something was built near this place* and never *the connection
belongs at this point*. Connector geometry keeps coming from the network, where it is
precise; the structure supplies the corroboration D-011 asks for and nothing else. Every
canal connector now records which of the two it has: a named lock or weir and its
distance, or an explicit statement that none is recorded within 150 m — **and that
second case is not evidence of absence**, because the Trust manages 101 waterways and
not all navigable water in England and Wales.

**It also confirms D-016, which was decided on reasoning alone.** That entry refuses a
connector where two lines touch at exactly 0 m, on the argument that such a crossing is
an aqueduct or a culvert far more often than a confluence. Of the 88 refusals with a
locatable touch point, **68 — 77% — have a recorded aqueduct or culvert within 150 m**.
Three had been checked by hand; sixty-eight is a different quality of answer.

**One trap in the service, and it is silent.** An ArcGIS FeatureServer caps a response
at its own `maxRecordCount` and reports it only in `exceededTransferLimit`. Asked for
the culverts unpaged it returns **2,000 of 2,962 with an HTTP 200 and no error**.
`rewt.acquire.fetch_arcgis` reads the flag and pages; a caller that does not will get a
third of the layer missing and nothing will say so.

**D-031 — An acquisition verifies its own completeness. Success is not completeness.**
*2026-09-01*

*The case is rewt-86's; the guard is the response to it.*

`rewt.acquire.fetch_arcgis` now asks each layer how many features it holds, using
`returnCountOnly=true`, and **fails if the paged fetch returns a different number**.

The case that produced it is nastier than the silent failures already recorded here, and
worth stating precisely. An ArcGIS FeatureServer caps a response at its own
`maxRecordCount` and reports the truncation only in `exceededTransferLimit` — HTTP 200
either way. So an unpaged fetch of the 2,962 culverts returns 2,000 and looks like a
success.

**What made it invisible is that the count was right.** `returnCountOnly` is not subject
to the transfer cap, so a verification that queried the count got 2,962 — the true
figure — while an actual fetch would have delivered 2,000. *The query that told the
truth is a different query from the one that would have lied, and nothing connected
them.* There was no wrong number anywhere to notice: no aggregate looked odd, no
distribution looked skewed, and re-running either query would have reproduced its own
answer exactly. **Re-running is no defence against this shape**, which is what
distinguishes it from most of what this project has caught.

The guard works by pointing the two queries at each other. That is the general form:
where a service will state what it holds as well as hand it over, ask for both and
compare. Where it will not, the acquisition says so rather than assuming.

This joins two others of the same family already recorded: a geoprocessing tool that
returns 0 while writing a raster of NaN (D-017), and a correction that reports itself
applied while resolving to nothing (§8, and the test that now runs in the build). In all
three the operation reports success and the artefact is wrong, and in all three the only
defence is to check the artefact against something that was not produced by the same
call.

**D-032 — Match on both name fields. `watercourseName` is the WELSH name where one
exists.** *2026-09-01*

*The specification finding is rewt-86's; the bug it exposed was in this project's
connector rules.*

OS Open Rivers' specification says of `watercourseName`: *"Where a watercourse has a
name in more than one language, this attribute will be the Welsh or Gaelic version"* —
and of `watercourseNameAlternative`: *"this attribute will be the English version."*

That is the opposite of the natural reading. `watercourseName` is not "the name, with an
alternative beside it"; for a bilingual watercourse it is specifically the Welsh or
Gaelic one. **Any rule matching on `watercourseName` alone under-finds Welsh
watercourses systematically, in a project whose scope is England *and* Wales.**

The same-name connector rule did exactly that. It would not have matched `Afon Tawe`
against `River Tawe`, and the failure would have been invisible: a Welsh river that
stops and resumes would simply not appear among the candidates, and no count would look
wrong. Both name fields on both sides are now compared.

**Measured here, the field is doing more than the specification describes.** 5,335 links
carry an alternative name and **every one differs from its primary**; 4,311 of those are
in scope. The pairs are not all bilingual — `Waterbarn Channel` / `River Frome` and
`Woodbridge Haven` / `River Deben` are a local name beside a river name — so matching on
either field is right for more reasons than the specification gives. Some pairs put the
Welsh first (`Afon Tawe` / `River Tawe`) and others the English (`River Dovey` / `Afon
Dyfi`), so the specification's rule is not even applied consistently, which is a second
reason not to rely on which field is which.

**D-033 — A stranded canal is a severed channel, not a misdirected one, and the unit of
repair is the stranded region rather than the dead end.** *2026-09-01*

*Measured by rewt-86 on OS Open Rivers directly; the rule change is the response.*

Of 569 sinks with canal arriving, **8 — 1% — can reach tidal water even when flow
direction is ignored entirely.** Canals in this product are not pointed the wrong way;
they are *cut off* from the water they lock into. That is one structural fact about how
the survey renders canals — it draws the channel and omits the works — and it is why
D-011's remedy is a connector at a structure and never a reversal.

It also explains a class this project had been solving with the wrong instrument. The
Manchester Ship Canal is drawn in **three disconnected pieces**, and OS *asserts* the
tidal connection at Eastham by drawing a stub that shares a node with the tidal Rivacre
Brook — then leaves a hole between that stub and the canal. **The survey's own geometry
is the evidence for the join**, which is a stronger footing than the structure
corroboration of D-030 and needs no external source at all.

**Two rule changes follow, and both were bugs rather than settings.**

*The unit is the stranded region, not the whole component.* The Ship Canal's stranded
1,141 km sits inside a weakly connected component of 16,787 km of which 16,348 links do
reach the sea — because one of its three pieces shares a node with tidal water. A rule
that grouped by whole components could not see it, and the dead-end rules could not
either, because the join it needs is 14 km from its dead end. The rule now works on
connected runs of *unreached* links, which is exactly "the water that cannot get out" —
the thing the crawl reports and the thing §5 says to work from. That change alone moved
in-scope reachability from 92.60% to 93.44%.

*And a limit is not a filter.* The rule asked for the twelve closest approaches and
discarded those at exactly 0 m (D-016's aqueducts and culverts). The stranded Ship Canal
touches reached water at 0 m in at least five places, so on a bad region the list filled
with zeros and the real gap was never reached. The closest strictly-positive approach is
now asked for in SQL rather than filtered out of a limited result.

**D-034 — Counties are named by the Historic Counties Standard, and the Isle of Man is
carried but out of scope.** *2026-09-01*

*Stephen's convention, arising from the viewer's county mosaics; recorded because it
binds any later stage that attributes a place to a county.*

Wherever this project refers to a county it uses the Historic Counties Standard's names
or its three-letter codes — `BED`, `YRK`, `CMB`. **Not the National Library of
Scotland's tileset filenames**, which differ from the Standard in three places, and not
ad-hoc strings.

The reason it is a decision and not a style note is that county attribution is a join
key. A later stage that attributes a mill, a lock or a map sheet to a county will match
against something, and two spellings of one county silently produce two counties — which
is the same shape as D-032's Welsh name field and D-023's licence granularity: a
mismatch that produces a plausible answer rather than an error.

`IOM` is carried so that a reference to the Isle of Man resolves rather than failing —
the Standard excludes it, the United Kingdom not including the Island. **It is out of
scope**: this project is England and Wales, and nothing draws it. Carrying an identifier
so a lookup succeeds is not the same as including the ground, and the two must not be
confused in a project whose scope rule is as carefully drawn as §4.1's.

**D-035 — A published `.geojson` is WGS84, because the format says so. A curated one is
not, and is checked.** *2026-09-01*

*The defect was found by rewt-fc, whose layer drew nothing.*

**GeoJSON is WGS84 by definition.** RFC 7946 fixes the coordinate reference system at
CRS84 and explicitly *deprecates* the `crs` member that earlier practice used to declare
otherwise. A conforming reader therefore ignores such a declaration: handed
`[203862.05, 198975.63]` with a `crs` member saying EPSG:27700, QGIS, MapLibre,
GitHub's preview and `geopandas.read_file` all read 203862.05 as a longitude and put the
whole of England and Wales a few hundred kilometres off West Africa.

`published/audit/refused_crossings.geojson` did exactly that. It is now WGS84 with no
`crs` member, and carries `easting`/`northing` as ordinary properties so that a reader
joining it to the rest of this project still has the National Grid position.
AGENTS.md's rule already covered this — *EPSG:27700 throughout; EPSG:4326 only at
export* — and a published `.geojson` is an export. A GeoPackage carries a real CRS and
keeps 27700; it is `.geojson` specifically that cannot.

**`data/curated/connectors.geojson` knowingly deviates, and the deviation is now
checked rather than trusted.** It stays in EPSG:27700 for a reason that is not
convenience: **a connector's identifier is a digest of its own coordinates** (D-013), so
reprojecting the file would rewrite every one of the 1,204 ids, and D-013 exists
precisely so that a feature keeps its identity between editions. It is also an input to
this build rather than an artefact anyone else consumes.

That is a defensible deviation and an unsafe one to leave unguarded, so `rewt/curated.py`
now refuses a curated geometry that is not National Grid metres. **An outer bound is not
enough**, and getting that wrong is instructive: degrees fall comfortably *inside* any
generous National Grid box, so the first version of the check passed a file of degrees.
What separates them is that the National Grid origin lies out at sea southwest of the
Scillies, so no real feature here sits within a kilometre of it, while every degree
coordinate in Britain is within about sixty. The guard tests for that, and catches Web
Mercator too.

**This is not hypothetical.** The predecessor's connectors are GeoJSON with no `crs`
member and are therefore degrees. Compared against this project's metres, all 31 landed
in the ocean and the validation reported that this build had independently found none of
them — which reads exactly like a substantive disagreement about method (D-026). That
was caught only because 0 of 31 was too clean a result to believe. It is now caught by
arithmetic.

**D-036 — The Welsh-name hazard is a JOIN hazard, not a filter hazard, and the
difference is measurable.** *2026-09-01*

*The hazard is rewt-86's; the scoping method is rewt-1d's; the measurement is here.*

D-032 recorded that OS Open Rivers puts the Welsh or Gaelic name in `watercourseName`
and the English in `watercourseNameAlternative`, and warned that "any filter reading only
the primary field under-finds Welsh watercourses". **Measured, that warning is wrong in
its stated form and right in a narrower one.**

**No link anywhere is findable only through the alternative field.** Every form returns
zero: inlandRiver 0, tidalRiver 0, lake 0, canal 0. A *filter* over the primary field
therefore loses nothing, and rewt-1d's check that the lake-name figures are unaffected
generalises to the whole product.

**What does fail is a MATCH BETWEEN TWO LINKS**, and that is what this project actually
does. 5,335 links carry both names and **all 5,335 differ**. Worse, the same river takes
different *primary* names on different links: **`Afon Gwy` is the primary name on 157
links and `River Wye` on 32.** So a same-name join on the primary field alone treats the
Welsh Wye and the English Wye as two rivers and declines to connect them — silently,
because nothing is missing, only unmatched. `Afon Hafren` (257 links) and `Afon Wysg`
(138) have no English-primary counterpart at all and would simply never match anything.

The connector rule compares both fields on both sides, which is right for the join case
and harmless for the filter case.

**The transferable part is rewt-1d's, and it is about warnings rather than names: the
scope of a warning is itself measurable.** A correct hazard stated one level too broadly
gets applied where it does not bite, and then either wastes work or — worse — gets
quietly discounted when it is found not to matter somewhere, taking its real
applications with it. Measuring where a hazard is empty is as useful as raising it.

**D-037 — The NLS tilesets are declared for provenance, with re-use recorded as not
established.** *2026-09-01*

*Identifiers and terms traced by rewt-fc and rewt-86.*

Where a curated judgement's evidence says what a historic sheet shows — *"both channels
drawn continuous through the crossing"*, which distinguishes a culvert from a confluence
far more cheaply than a structure register — the sheet is an input to that judgement, and
`conf/sources.yml` now declares it.

**Declaring it is a provenance act, not a rights claim, and the two were conflated in
getting here.** The argument that reading a sheet and citing what it shows is not
reproducing it is sound, and no licence restricts facts or citations. But that settles
whether the method is *permitted*; it does not settle whether a reader of a correction
can find out what was looked at, and AGENTS.md's rule is about both. `redistribution:
not_established` records the uncertainty rather than resolving it, and the exporter
refuses the source outright — verified — so nothing traced from a tile can reach a
published artefact.

Three things the entry carries because each would otherwise be rediscovered:

* **NLS state one condition**, and it is about their infrastructure: *"Re-use of these
  layers is intended within a desktop or local environment... please use our Historic
  Maps API layers, or contact us."* A localhost viewer is inside that and a published
  site is not — **and the Historic Maps API carries no first-edition six-inch at all**,
  so it is not a substitute for the layer the evidence method depends on.
* **No date ranges are recorded.** NLS do not state the date spans of these layers, and
  the figure in circulation comes from a different product's naming. Labelling them with
  years we cannot source would be exactly the error D-023 exists to prevent, pointed at
  a date instead of a licence.
* **The first-edition county filenames are NLS's own** and differ from the Historic
  Counties Standard in three places. D-034 governs: name counties by the Standard and
  map to the filename at the point of use.

**D-038 — Record the day the product was written, not only the month.** *2026-09-01*

`conf/sources.yml` says of OS Open Rivers: *"Reissued twice a year. Record which issue
was fetched: the network changes between them, and a result that cannot name its input
cannot be reproduced."* The build recorded `2026-04` from the download API and stopped
there. The GeoPackage itself records **2026-04-14** in `gpkg_contents.last_change`,
which is a statement about the file in hand rather than about the release it belongs to.
Both are now captured, and the precise one reaches `published/provenance.json`.

The distinction matters for the same reason D-023's does: a month is a statement about a
release, and a release can be re-cut. The file's own date is the narrowest statement
available about the thing actually read, which is the standard this project already
applies to licences.

**D-039 — WhiteboxTools runs single-threaded, because threaded it is not
deterministic.** *2026-09-01*

`wbt.set_max_procs(1)` in `rewt/stages/terrain.py`. This is a correctness setting and
not a tuning one.

**Measured.** `breach_depressions_least_cost` over a byte-identical input produced
`b40f5b39d137acab` on one run and `7b54eef1bb32d30a` on the next. Forced to one process
it produced `12bec2378631fcec` twice.

**The cost is nothing at all**: 452 seconds single-threaded against 451 threaded. The
tool was buying non-determinism for no speed whatever, which is worth stating because
the obvious objection to this change is a performance one and it does not exist.

**What it cost before it was found** is the point. The conditioning decides the
delineation, so an unstable conditioning is an unstable set of basins: one threaded run
merged the Midlands and the Scottish border into a single **18,148 km²** "basin" — larger
than any real British catchment, spanning 297,400–559,900 E and 269,900–700,000 N. It was
caught by the northern-edge invariant of D-024, which refused it because an in-scope
basin reached the clipped edge. Without that guard it would have shipped, and it would
have looked like a delineation rather than an error.

**And it makes a claim in §9 true that was not.** *One command, empty checkout to
finished network, twice, identical output.* That was verified — and the verification was
worthless, because the terrain stage was **cached in both builds compared**, so the one
non-deterministic step in the pipeline never ran. A reproducibility check that skips the
irreproducible stage confirms nothing. The check now has to be run with terrain forced,
and that is the only way it means anything.

**D-040 — `status:` in `conf/sources.yml` is a cached claim, and `rewt sources --verify`
is what checks it.** *2026-09-01*

*Swept by rewt-86, who found the class rather than the instance.*

The field carried its own intent — *"set at first acquisition, then verified on every
use"* — and **nothing implemented it**. It was stale in both directions at once: five
genuinely acquired sources with real digests said `unverified`, and the only two saying
`verified` were the two this repository had never derived.

That is the shape of defect this project keeps finding, in a new place: a populated
field, in the right-looking place, that nobody maintains. It is worse than an absent
field, because it invites exactly the trust it was created to remove.

**`verified` now means one thing: this repository digested the bytes it holds and they
match either the declared checksum or the digest recorded at acquisition.** `rewt sources
--verify` computes that and compares it with what the file claims, failing on a mismatch
in **either** direction — an overstated claim and an understated one are both the field
lying. The file's values have been corrected to the computed truth.

The first thing it found was real: the `gb1900_raw_dump` checksum was wrong.

**D-041 — Report what a difference costs, not that it exists.** *2026-09-01*

*rewt-1d's formulation, from instances belonging to rewt-2b and rewt-86.*

Repeatedly today the useful answer came from naming the **consequence** of a discrepancy
rather than the discrepancy, and in each case the person holding the observation did not
hold the generalisation.

* Asked whether a tracing queue wanted 274 places or 335, rewt-2b did not answer the
  arithmetic. It said that unioning the per-class files would send two contributors to
  opposite ends of the same channel, and that accidental duplication contaminates the
  deliberate overlap sample by which the tool's central claim is to be tested. The
  arithmetic could not have supplied that reason.
* Given a caution that a towing-path label proves traffic at the survey date and nothing
  earlier, rewt-2b found two further mechanisms producing the same failure and made it a
  constraint on its interface — **every historical label carries its date or says it has
  none** — then applied the rule back and caught an undated caption of its author's.
* Finding a tileset whose `attribution` field named the rendering software, rewt-86 did
  not report a missing licence. It reported that **a populated field is not a rights
  statement**: a well-formed value, in the right-looking place, answering a different
  question. That is the same finding as D-040's, reached independently and stated better.

**The practice: when reporting a discrepancy to another worker, say what it would cost to
act on the wrong side of it.** The correction travels either way; the reason is what
generalises. It is also an argument for asking rather than handing over, and a better one
than anybody undertaking to be careful.

**D-042 — Presentation outruns evidence, by at least four mechanisms.** *2026-09-01*

*rewt-1d's family; the sharpest instance is rewt-2b's.*

Distinct from the counting errors already recorded here. In each case the **evidence is
sound** and its **presentation claims more than it holds**.

| mechanism | instance |
|---|---|
| a label read as timeless | a towing path proves traffic in 1899, not navigability |
| a control that invites a guess | asking a contributor to type a year |
| a name read as a date | dating a tileset from the span its series is named for |
| rendered confidence read as evidential weight | a snapped trace looks more authoritative than a hand-drawn one, and is a machine's reading of ink in a corridor a person pointed at |

The last is the one whose remedy is not a caveat. The clicked-or-snapped distinction has
to be **visible while tracing**, not merely recorded in the file, and `snap_mode: hand`
has to be the honest value when snapping is off. **A provenance field that only a later
reader sees does not stop the contributor over-trusting the line in front of them.**

**The rule: anything shown to a person must carry the limit of what it shows, at the
moment they act on it.** That constrains interfaces and captions, not only data models —
which is why it is kept separate from D-041, whose remedy is a habit rather than a
design constraint.

**D-043 — Two readings of the National Library of Scotland's terms, both Stephen's,
both recorded as readings.** *2026-09-01*

*Ruled by Stephen on 2026-09-01, in answer to two questions put to him directly. Neither
is a finding about NLS's terms; each is a decision about how to read them, and D-025's
treatment applies: the project may choose a reading, and it records that it chose.*

**A line traced from an NLS sheet is not a derivative of the scan.** Contributed geometry
therefore reaches `data/curated/` and publishes openly under this project's own terms.
Stephen's words: *"Nothing in the NLS documentation suggests restrictions on derivatives
like this. Assume that they are freely allowed."*

The supporting argument, which is rewt-86's, is that the 1840s–90s survey is out of Crown
copyright, that NLS hold rights over their scans and georeferencing rather than over the
ground, and that a traced line is a new record about the ground rather than a reproduction
of the scan. **That is a good argument and it is still a reading**, and this entry does
not upgrade it to a fact. What makes the reading defensible to act on is that it is
recorded, attributed and reversible: if it is wrong, the remedy is to withdraw geometry
from a repository, which is unpleasant but possible.

**Gating the tracing tool to authorised users satisfies NLS's stated condition.**
Stephen's words: *"My instruction stands: gating satisfies all of the limitations."* The
condition, verbatim from NLS's georeferencing guide, is: *"Re-use of these layers is
intended within a desktop or local environment. If you wish you present these layers
online in a public website, please use our Historic Maps API layers, or contact us at
maps@nls.uk."*

**Three things this entry must not be read as saying**, all of which are true and none of
which the ruling changes.

*The gate does not restrict access to the sheets.* The NLS tile host is keyless and
world-readable; anyone can fetch those tiles without coming near this project. What the
gate restricts is who uses the tool and — the part that matters — where the traces go.
An entry implying we are restricting access to the maps would be false, and rewt-2b
established this rather than letting it pass.

*The sanctioned alternative does not cover the case.* The Historic Maps API, the route
NLS name for public sites, **carries no first-edition six-inch at all** — so it is not a
substitute for the layer the tracing depends on. That is why an assumption is being made
rather than the alternative taken, and it stops "we assumed it was fine" being read later
as "there was no other way".

*One email would settle both.* NLS name the route — `maps@nls.uk` — and neither ruling
should be cited as though the question had been closed rather than decided. D-023's whole
argument is that a licence is a claim about a specific thing traced to a statement about
that thing; these are readings taken in the absence of such a statement, and they remain
readings until someone asks.

A further entry will describe the gate **as built** rather than as intended, once phase 1
of the tracing tool exists. This entry records the rulings; that one will record the
mechanism.

**D-044 — Identifiers use one colon and then slashes, so that a CURIE expands to a URI
that resolves.** *2026-09-01*

*Found by rewt-86 on the day the `rewt` namespace went live, which is the only window in
which this was free to change.*

The build minted `rewt:basin:4385554389`. `rewt` is now a registered w3id prefix bound to
`https://w3id.org/rewt/`, and **a CURIE expands by plain concatenation of namespace and
reference**, so that identifier expands to `https://w3id.org/rewt/basin:4385554389` — a
perfectly legal URI which resolves to nothing, because what w3id routes is
`https://w3id.org/rewt/basin/4385554389`. Both are URIs; only one is the identifier.

Identifiers are now `rewt:basin/4385554389`: the prefix delimiter once, slashes
thereafter. It expands correctly by concatenation, needs no special tooling, and matches
the routes already published. `os:link/{GUID}` follows the same shape.

**The alternative that was rejected is worth recording**, because it is the one already
written into the w3id README: documenting the expansion as a *transformation* — replace
colons with slashes after the prefix. That is not what a CURIE means, and generic tooling
would ignore it, which makes it a rule that works only where someone has read the
documentation. The other alternative, accepting both forms in `.htaccess`, gives one
basin two URIs, which is what an identifier scheme exists to prevent.

**The failure this avoids would have been silent and total.** The moment this data is
serialised as JSON-LD — which D-027 already commits it to, LPF `when` objects being
JSON-LD — a context binding the prefix expands every identifier by concatenation,
produces the unrouted form, and reports no error. Nothing in the pipeline would notice
and every URI would be wrong at once. It is the same family as D-031's silent
truncation: the operation succeeds and the artefact is wrong.

**D-045 — The publisher's identifiers are NOT persistent, so `os:link/{GUID}` cannot
satisfy §10. Recorded as unresolved.** *2026-09-01*

*Raised by rewt-86; the specification checked here; the measurement was already in D-026.*

PLAN.md §10: *a stretch present in two published editions must carry the same id in
both. Design the scheme once, here.* The build mints `os:link/{GUID}` and
`os:node/{GUID}` for 194,658 links and 198,119 nodes, borrowing the Ordnance Survey's
own identifier. **The OS Open Rivers technical specification says, verbatim:**

> The identifier is not persistent between product versions; there is therefore no
> change-history information for features.

So the identifiers for the entire survey-derived network rest on a value the publisher
explicitly declines to keep stable, in a product reissued twice a year. `basin_id`,
`rewt:link/…` and the correction identifiers are minted here and do not have this
problem; the survey's do.

**This is measured, not merely warned about.** D-026 records that of the predecessor's
73 corrections, **12 reference a link that does not exist in issue 2026-04 at all** — of
25 junction targets, 13 survive; of 45 connector link ids, 32. That churn is exactly this
defect, observed eleven months apart, and it is why that comparison had to be made by
place rather than by identifier.

**No scheme is proposed here, and that is deliberate.** Replacing it is a design decision
with consequences that reach outside this file: `data/curated/` keys reversals,
junctions and exclusions on publisher ids, so any new scheme has to say what happens to a
judgement whose subject is re-issued under a different GUID. A geometry digest — the
scheme D-013 already uses for connectors — is the obvious candidate and is not obviously
right, because OS re-generalises geometry between issues too, so a re-drawn reach would
take a new identifier and look like a different river.

Recorded now, unresolved, because §10's own logic applies to fixing it: the window in
which an identifier scheme can be changed for free is the window before anything outside
this repository has resolved one, and that window is open today. **It is on the decision
queue for Stephen.**

---

**D-046 — The survey's own generalisation is measured, because Stage 1 is the only
stage that can measure it.** *2026-09-01*

PLAN.md §10 asks that the audit record what OS Open Rivers' generalisation actually
is. It is now measured on all 193,040 as-surveyed links and 2,137,230 vertices, and
it turns out to be sharper than "generalised" suggests:

| percentile | vertex spacing | sagitta |
|---|---|---|
| 5th | 18.9 m | 8.28 m |
| 50th | 56.7 m | 15.59 m |
| 95th | 204.6 m | 40.64 m |

*Sagitta* is how far a vertex sits off the straight line joining its two neighbours —
the amplitude of the bend that vertex was kept to record.

**The interesting number is the low tail, not the median.** Sagitta at the 0.1st
percentile is 0.18 m and only 0.25% of vertices sit under 1 m, but by the 10th
percentile it is already 8.99 m. That is a knee, not a taper: **the survey retains
bends down to about 9 m of amplitude and almost nothing below it.** A near-empty
low tail is the signature of a tolerance filter, so ~9 m is a reasonable read of the
tolerance OS generalised to, inferred from what survived rather than from a
specification we do not have.

Two consequences worth writing down while they are cheap:

**The survey is finer than the terrain that conditions it.** Median sagitta 15.6 m
and median spacing 56.7 m, against a 50 m DEM. Where §5's terrain evidence and the
survey's own geometry disagree about a course, the survey is the higher-resolution
witness and the DEM is not entitled to overrule it on shape.

**It sets a floor for any later stage.** A stage proposing to move a line by less
than ~9 m is arguing with the tolerance, not with the river. This is measured now
because it cannot be measured later: once anything puts its own vertices on a line,
OS's spacing is gone and is not recoverable from the result.

---

**D-047 — Fall per link is published, and named so it cannot be mistaken for a
measurement.** *2026-09-01*

§10 asks for the fall of every link sampled from the *unconditioned* terrain, on the
grounds that a later stage modelling water power needs head and head is the half
nobody plans for. `link_gradient` already held it — §5 computes it to test flow
direction against the ground — so this costs one join, and the whole cost of not
doing it now is a second national terrain pass later.

**The naming is the actual decision.** The columns ship as
`screening_elevation_upstream_m`, `screening_elevation_downstream_m`,
`screening_fall_m` and `screening_terrain_verdict`. A 50 m DEM does not resolve a
mill's head — a weir and a leat make metres of fall over a few hundred, and the
model will not see either — so a column called `fall_m` in a published GeoPackage
would eventually be read as a site measurement by someone who never saw this file.
The prefix is the only part of the artefact that travels with the number.

---

**D-048 — Tidal termini are published as objects, not inferred from the absence of an
outflow.** *2026-09-01*

§10, on the coastal terminus: *nothing to build now*, but it asks that **every tidal
terminus is identified and kept as a first-class thing rather than implied by the
absence of an outflow, so that attaching them later is a join and not a
re-derivation.*

It was implied. A terminus was a node the crawl happened to start from, and
"is it tidal?" was answered by running the graph. `published/rewt_stage1_network.gpkg`
now carries a **`terminus` layer**: 13,030 nodes with `terminus = 'tidal'`, each with
its basin, the form arriving at it, its inflow count and length, and whether the
crawl actually seeded from it.

**The distinction is not cosmetic, because the two sets are not the same.** A node
can be tidal and not be a seed. Deriving termini from seeds would silently publish
the smaller set, and a later stage joining a depth contour to "the termini" would
attach to whichever ones this build's crawl happened to use — a Stage 2 artefact
shaped by a Stage 1 implementation detail. Recording both, and the flag that
separates them, means the join is a join.

---

**D-049 — A stage's fingerprint now covers every project module it can reach, not
only its own body.** *2026-09-01*

**The bug, because it is worth stating before the fix.** `Stage.source_hash()` hashed
`inspect.getsource(self.fn)` — the stage function's own text and nothing else. But a
stage function is a few lines that call into `ids`, `graph`, `topology`, `curated`,
`schema`. Rewrite any of those and the stage's own text is unchanged, so its
fingerprint is unchanged, so the build serves the artefact the *previous* code
produced and reports success.

**It had already happened.** `ids.publisher` was changed from `os:link:{id}` to
`os:link/{id}` — one character, deliberate, so a CURIE expands by concatenation onto
a URI w3id actually routes. No fingerprint moved. The database went on holding
195,689 links and 198,457 nodes identified in a scheme the code on disk no longer
produced, `rewt build` exited 0, and every published figure was intact and unaffected.

**What caught it was a unit test, and only by accident of how it was written.**
`test_a_publisher_feature_keeps_the_publishers_identity` compares `ids.publisher(...)`
against a literal. It imports the module, so it sees the new code; the database holds
the old. Nothing that read the database could have found this, because the database
was *internally consistent* — every identifier in it agreed with every other. A
consistency check would have passed. This is the failure mode where the artefact is
coherent and simply not the one the source code describes.

**The fix, and the direction it is deliberately wrong in.** The fingerprint now covers
the transitive closure of `rewt.*` imports from the module the stage is defined in,
resolved from the source text by AST rather than from `sys.modules` — an import that
has not executed yet in this process is still a dependency. It is coarse: a change to
`db.py` rebuilds nearly everything, because nearly everything imports it. That is the
right direction. **A rebuild that was not needed costs an hour; a cached artefact
built by code that no longer exists costs the reproducibility guarantee §2 rests on,
and costs it silently.**

Two tests hold it: one perturbs `rewt/ids.py` and requires the `load` stage's
fingerprint to move; one requires the walk to follow relative imports, since nearly
every import in this package is relative and a walk that only understood absolute ones
would return almost nothing while still producing a plausible-looking hash.

**The honest caveat.** §9's reproducibility check compares two builds. Both were run
against this defect, so what it demonstrated was that the pipeline is deterministic
given its cache — not that the cache corresponds to the source. That is a weaker claim
than the one I made for it, and it is the second time this session that a check has
reported success for the one case it could not see.

---

**D-050 — Tidal termini outside any delineated basin are named, not quietly dropped.**
*2026-09-01*

**4,067 of 13,030 tidal termini fall outside every delineated basin**, and 1,059 of
those are crawl seeds. They cannot appear in a per-basin figure, which is what §8 asks
the audit to report.

**It is not a defect of the terminus layer and it is not about the coast especially.**
53,755 of 197,734 nodes — 27% — have no basin assigned, because D8 delineation from
pour points does not cover every cell a node can sit on. Termini are at 31%, which is
close enough to the network-wide rate to be the same phenomenon rather than a worse
one. The delineation simply runs out near the coast, which is exactly where termini
are.

Recorded rather than fixed, and the audit now prints it as a named skip, because the
risk is not the gap itself but a per-basin reachability figure being read as covering
the whole coast when a fifth of the coast's termini are not in any basin to be
counted. The test on the published layer was written to match: it requires the
assigned share to sit near the network-wide share, so that the join silently returning
nothing — which looks identical to "these have no basin" in every downstream report —
fails loudly instead.

---

**D-051 — Two identifiers were being minted outside `ids.py`, and both were wrong the
moment the scheme changed.** *2026-09-01*

`rewt/ids.py` exists so that identifiers are composed in one place. The rule was
written down and not enforced, so it had been broken twice, and neither break
announced itself:

| where | what it built | what it should have built |
|---|---|---|
| `basins.py:222` | `rewt:basin-unanchored:1002` | `rewt:basin-unanchored/1002` |
| `candidates.py:357` | `os:node:{publisher_id}` | `os:node/{publisher_id}` |

**Both were f-strings, so the move to slashes went straight past them.** The first
shipped: every unanchored basin in the published GeoPackage carried an identifier
expanding to `https://w3id.org/rewt/basin-unanchored:1002` — a legal URI that
resolves to nothing, which is exactly the defect the slash rule was introduced to
prevent. The second is worse in kind though it never shipped: `candidates.inspect()`
composed a node id in the old form and looked it up in a database that now holds the
new one, so **the tool for adjudicating a defect at the place would have reported "not
found" for every node that exists.** It would have looked like a data problem.

**The lesson is the one D-049 already paid for, one level down.** There, a stage's
fingerprint did not cover the module it called. Here, a module's identifier scheme did
not cover the two places that composed identifiers without asking it. In both cases
the artefact was internally consistent and simply not what the source described, and
in both cases nothing that read the artefact could have noticed.

So the rule is now a test rather than a sentence. `test_no_module_but_ids_mints_an_
identifier` greps every module but `ids.py` for an f-string beginning `os:` or `rewt:`.
It is crude deliberately — it catches the *shape* of the mistake without having to
understand the code, and it found `candidates.py` immediately, which no amount of
reading had. A second test checks the published file itself, because a resolver meeting
these strings will not care which module composed them.

**What did not move.** In-scope reachability is **93.28%**, to the same 97,746 km of
104,785 as before the rebuild, and 334 basins remain in scope. The stale cache
affected the identifier scheme; it did not touch the measurement the project is
judged on. *(See the correction below: it did not affect the basin count either.)*


---

**Correction to D-049 and D-051 — the basin count was never evidence of staleness.**
*2026-09-01. Appended rather than edited into place; the entries above stand as
written, with a pointer.*

I reported that the basin count had moved from 1,049 to 1,279 across the rebuild, and
attributed the difference to the stale cache. **That was wrong, and the two numbers
were never in tension.**

`basins.py` logs `len(measured)` as *basins delineated* — every basin D8 produces,
**1,279**. It then stores only those that are in scope or above
`basins.min_basin_area_km2` (line 163), which is **1,049**, and that is what reaches
the `basin` table and the published GeoPackage. Both figures are correct, they measure
different things, and both have been printed by the same build all along. I compared
the delineated count from the running build against the stored count I remembered from
the published output, and read the difference as a defect.

**This is the exact error this repository has spent the day cataloguing — a real value
attached to the wrong object — committed while reporting on that error.** It is also
the failure the aggregates rule exists to prevent: I checked a summarising number
against my memory of another summarising number instead of against the thing each one
counts. Two minutes reading `basins.py` would have settled it, and I reached for an
explanation before I reached for the source.

**The mechanism is worth naming, because it is not carelessness and it will recur.**
I had just found a genuine staleness bug. That made an adjacent staleness explanation
feel *earned* rather than hypothesised — the second finding inherited the first one's
credibility without inheriting any of its evidence. A real finding is exactly the
condition under which the next wrong one goes unchallenged, so the guard belongs
immediately after a success and not after a failure: **having just been right is not
evidence about the next claim.**

**What survives, because it was established a different way.** D-049's stale-cache
defect is real and is not supported by the basin count at all: it was demonstrated by
perturbing `rewt/ids.py` and watching the `load` fingerprint move, and by the database
holding `os:link:` identifiers while the code on disk emitted `os:link/`. That evidence
is untouched. The identifier scheme was genuinely stale; the basin count never was.

**And the determinism result stands on its own.** 1,279 delineated across two
independent full terrain runs, with 195,015 edges and 334 in-scope basins reproduced
exactly, is evidence that the breach is deterministic at this granularity. It simply
never needed a discrepancy to explain, because there was none.

---

**D-052 — A link's basin is decided by its *oriented* downstream node, not the one it
was drawn towards.** *2026-09-01*

The audit attributes a link to a basin with `JOIN edge e ON e.to_node = nb.node_id` —
the oriented routing graph's downstream end. `link_scope`, which is where the
published `basin_id` comes from, attributed it by `link.to_node` — the **digitised**
end. For a reversed link those are opposite ends, and 335 links are reversed.

**64 links, 94.3 km, 56 of them reversed, sat in one basin in the published
GeoPackage and a different one in the audit.**

**The audit was right, which is why the disagreement had a sign.** A reversed link's
water leaves by the end it was drawn entering; the oriented sense is the only correct
basis for anything about where water goes, and `link_scope` keying on the digitised
end silently contradicted this project's own decision that reversals are applied.
`basins` runs after `repair` (D-028) precisely so that `edge` is available at this
point. It simply was not being used.

**Found from outside, which is the only place it could have been found.** rewt-fc
recomputed the per-basin figures from the published file and got 15 of 200 basins
differing, worst the Afon Hafren at −14.9 km on 6,917 km — **0.2%**. It tested the
obvious explanation, that the audit keyed on the *upstream* node, and got 161 of 200,
an order of magnitude worse, so it reported the difference as real and unexplained
rather than dropping it. Both halves of that matter: it refused its own first answer
(a mid-build snapshot, which it withdrew), and it refused mine (that the gap was all
retired links, which accounted for most but not all of it).

**Too small to notice, consistent enough to look like data.** That is the combination
that survives longest. A 0.2% worst case reads as rounding, and eleven of fifteen
differences sharing a sign reads as a property of large basins rather than as a defect.
Nothing inside the build was comparing the two, because both were computed by us and
each was self-consistent.

So the comparison is now inside the build.
`test_the_audit_and_the_published_file_agree_per_basin` sums the published link layer
per basin and requires the audit's own figure to within 0.5 km. **An outside reader
adding up the file must reach the number we report, or one of the two is lying about
the same rivers.**

**What moved.** In-scope totals shift by 44 km — 97,786 reached of 104,829, from
97,746 of 104,785 — because `link_scope.in_scope` keys on the same node. The share is
unchanged at **93.28%**, and the earlier figures were wrong in their third significant
figure rather than in their meaning.

**D-053 — Three UI modules are lifted from the scoping exercise, under a narrow exemption
from the no-import rule.** *2026-09-01*

*Granted by Stephen Gadd on the decision card `tracer-import`, 11:13, 1 Sep 2026, with no
note. Requested by rewt-2b. The grant is recorded as the tick on the card rather than as
the instruction that preceded it in conversation, because the card is the durable
artefact and the instruction is not.*

`AGENTS.md` says *do not import code or data from* `Premodern Rivers`, and D-001 says carry
across no code and no data. Both stand. **This entry exempts three files and nothing
else**: `docs/js/tracer.js`, `raster.js` and `anno.js`, now at `tools/tracer/js/`.

**The reasoning behind D-001 does not reach them.** That entry's argument is about the
audit — *an audit handed its answers is not an audit* — and about curated corrections made
against another build's graph. A drawing tool carries no answers. `tracer.js`'s own header
states the constraint it was written to: *this module knows nothing about rivers... everything
about what a trace MEANS belongs to the caller*, and the annotation profile is a separate
module for the same reason. Rewriting a working corridor livewire would buy no audit
independence whatever, and would cost a week. **The exemption does not hollow out the rule;
it marks where the rule's reason stops.**

**What is exempted, precisely.** 1,011 lines across three files: a MapLibre tracing mode, a
tile-mosaic-and-cost-surface reader, and a W3C Web Annotation profile. **No data. No curated
corrections. No network logic. No `rivers/` module.** The scoping exercise's traced courses
and its 73 corrections remain a validation set under D-001, unconsulted until this project's
own work stands.

**They are imported unmodified and adapted in a separate pass**, which is the part worth
recording. An exemption has a boundary and a reviewer must be able to see it; adapting
during the import would mix inherited code with new code in one commit and make the boundary
unrecoverable afterwards. That is this repository's own rule that nothing is deleted to
correct it, applied to an import: **an exemption whose boundary is unrecoverable is not an
exemption, it is an erasure.** `tools/tracer/js/README.md` records what needs adapting and at
which phase, and what must not be adapted away — the credential refusal, `conformsTo` being
required rather than defaulted, and the per-vertex `clicked`/`snapped` distinction.

**One thing the import does *not* need the exemption for, corrected before the card was put
to him.** The draft credited the import with `raster.js`'s finding that these sheets are
bimodal in blue content — median 0.000%, so a blue-water detector finds nothing on roughly
nineteen sheets in twenty, but the sheet type can be decided from the pixels at runtime.
That is a fact about NLS sheets, not about the predecessor's graph. It was never under
D-001, needs no exemption, and including it overstated what the exemption buys. **Only the
1,011 lines need it.**

**And the import immediately earned its own scrutiny.** Applied to these three files,
D-051's grep test — look for a composed scheme literal outside the module that owns the
scheme — finds that **`anno.js` does not own its identifier scheme at all**: it takes
`identifying` as an opaque `{source, label}` and leaves the caller to compose the URN, which
the predecessor does in a single template literal 1,885 lines into a UI module. That is
D-051's shape in JavaScript and worse in one respect, because **a wrong separator in a URN
stays a legal URN and stops resolving** — no database to disagree, no schema to complain.
The remedy is in `tools/tracer/PLAN.md` and belongs to phase 2, before the sites multiply.

---

**D-054 — The project keeps Ordnance Survey's identifiers and freezes the issue.**
*2026-09-01. Stephen's ruling on the identifier card: rejected minting our own, with
the note "Freeze on the 2026-04 issue".*

*Renumbered from D-053: rewt-2b and I appended entries within the same minute and both
took that number. Theirs was appended first and keeps it. Recorded rather than quietly
fixed, because a decision log whose numbers move without saying so is worse than one
with a gap.*

D-045 recorded the problem and left it open. OS's specification says, verbatim: *"The
identifier is not persistent between product versions; there is therefore no
change-history information for features."* §10 requires that a stretch present in two
published editions carries the same identifier in both, and borrowing a GUID that the
publisher declines to keep stable fails that outright — for 195,689 links and 198,457
nodes, measurably, since 12 of the predecessor's 73 corrections point at links absent
from the current issue.

**The ruling buys the guarantee with a policy rather than with a scheme.** With
exactly one version there is no second version for the identifiers to be inconsistent
with. The specification's warning is scoped to *between product versions*, so refusing
reissues satisfies it exactly, and the alternative — minting our own from geometry —
was never clean: OS re-generalises between issues, so a redrawn reach would take a new
identifier and look like a different river.

**The price is real and is the reason this was Stephen's to decide.** The project
never takes a reissue: no corrections OS makes, no new channels, and a widening gap
from the current survey. That is a cost paid indefinitely to buy stability, and it is
the sort of trade an agent should not make on its own.

**What makes it a mechanism rather than a note.** `conf/sources.yml` now carries
`frozen_issue: "2026-04-14"`, taken from the GeoPackage's own
`gpkg_contents.last_change` (D-038) because that states the day the product was
written and the API only gives a month. `load` **fails the build** if the file on disk
was written on a different day, and fails equally if the file records no date at all,
because an input that cannot identify itself cannot be pinned.

Failing rather than warning is the whole point. The reissue is a twice-yearly event,
so it is exactly the failure nobody is present for: the file changes, the build goes
green, 195,689 links are renumbered, and the first symptom is a curated correction
that matches nothing. Two tests hold it — one that the pin exists and has not moved
without a decision, and one that reads `load`'s own source to check the pin is
compared and raised on, because **a pin nobody checks is a comment.**

**One thing the freeze does not buy, recorded so nobody assumes it does.** It stops
the *publisher* moving identifiers under us. It does nothing about *us* moving them:
an anchored basin id is a digest of its outlet node id, so this morning's separator
change turned `rewt:basin/d5921800ed` into `rewt:basin/000e9ed6b8` for the same basin,
with no reissue involved. A derived identifier inherits every instability of its input,
including instability we introduce. The pin guards one direction; D-051's one-owner
rule and its test guard the other.

---

**D-055 — A test that fails when the method is right is not a falsification test.**
*2026-09-01*

`conf/params.yml` states, for each of the sea parameters, what would show it wrong.
Two of those clauses fired within an hour of being written, which is the first time in
this project that a stated falsification criterion has caught anything. One caught the
method. The other caught itself.

**The one that worked: resampling by maximum was wrong, and it closed the Solent.**
Taking the shallowest point in each cell looks like the conservative choice. It is not:
a 100 m cell holding one rock and 9,900 m² of deep water is still connected water, and
taking the rock erodes every channel until the coast is a wall. Resampling is by
**average**, and that also repairs `sea.clearance_m`'s own justification, which is
written as a margin against the cell *averaging* over its footprint — true of average
and false of max. **A parameter whose stated reasoning depends silently on a choice
made elsewhere** is the same shape §10 now warns about for identifiers, which is why
that one fact is in the plan and the rest of this entry is not.

**The one that caught itself: the Menai Strait test was mis-specified.** The comment
said the resolution was wrong if the Menai Strait closed. It closes at 100 m and at
200 m — **and it should.** The Swellies are rock and shallows that nearly dry, so a
surface of water 5 m below Lowest Astronomical Tide excludes them correctly. The test
would have failed on a working method, and passing it would have required breaking the
clearance rule.

So the general form, which is the part worth keeping and which is not about tidal
straits: **a falsification test must be something that fails only if the method is
wrong.** A test that a correct method fails is worse than no test, because the obvious
way to make it pass is to break the thing it was watching. The Solent is the control
now: a genuinely deep, wide channel that a correct surface keeps open.

**And state it so that it cannot be wrong about something else.** My first attempt
probed named coordinates and read depths off them. *"Solent off Cowes"* returned
**+35.2 m** — the Isle of Wight, because I had guessed the easting. A well-formed
number answering a question nobody asked, which is the day's recurring shape. The test
is now topological: **is the Isle of Wight a separate land mass in the passable
surface?** It needs no coordinate precision, both probes sit far from any shore, and it
cannot be quietly wrong in that way. It passes at 100 m and at 200 m.

**A note on where this is recorded.** rewt-1d took the average-versus-max fact into
PLAN.md §10 and declined the rest, on the grounds that a specification records what
must be true rather than what was tried, and that a plan which grows a paragraph
whenever something is found becomes a diary and stops being checkable. That is right,
and the boundary is worth having in writing.

---

**D-056 — A single sea network emerges, and I nearly reported that it did not.**
*2026-09-01*

§10's construction is built as far as the spanning tree, and it does what the
specification hoped: **cost-allocation partitions the sea into 3,438 territories, all
3,438 are adjacent-connected, and the minimum spanning tree over them has 3,437 edges
— a single tree spanning every entry point around Britain.** The loop was not drawn
and was not a parameter. It is what remained when the routes agreed.

**But the first two answers said otherwise, and both were mine rather than the sea's.**
The adjacency graph reported **84** components, then — after adding diagonal
adjacency, which can only add edges — **169**. More edges cannot produce more
components, and that impossibility is the only reason the result was questioned rather
than written up as a finding about patchy bathymetry.

**The cause: 421 of the 5,817 crossings cost exactly zero, and a sparse matrix does not
store an explicit zero as an edge.** `scipy.sparse` drops them, `connected_components`
walks the sparsity structure, and 421 real adjacencies — the cheapest ones, where two
territories meet at the very cell a source sits on — silently disappeared. The graph
was well-formed, the code ran clean, and the answer was confidently wrong in the
direction that would have looked like a *discovery*: a fragmented coastal sea, which is
exactly the finding §10 warns must be reported rather than repaired.

Adding an epsilon to every weight keeps each edge in the structure and the count
resolves to 1.

**This is the day's shape once more and the most dangerous instance of it.** The
others produced a wrong number. This one would have produced a wrong *conclusion about
the world* — and one the specification had pre-authorised me to report, since it says a
trunk that does not close is a finding about the bathymetry. **A prepared explanation
for a failure is what makes the failure easy to accept.** The check that saved it was
not scepticism about the data; it was noticing that the two runs contradicted each
other in a way arithmetic forbids.

So the rule earned here: **when a result changes after a change that could only move it
one way, the discrepancy is the finding.** Not the result.

**Two sharpenings from rewt-86, which checked its own code against this and was safe.**

*The exposure is narrower than "scipy drops zeros".* Its `connected_components` calls
build the matrix from `np.ones(len(pairs))` — indicators, never costs — so nothing was
ever dropped and its 1,724 and 4,068 place counts are unaffected. **The trap is
specific to matrices holding costs, where 0 is a meaningful value; it is absent from
matrices holding indicators, where 1 is.** Anyone using `connected_components` as a
union-find over pairs is safe. "Avoid scipy sparse" would be the wrong lesson and would
cost a good tool.

*And the better guard is the one that needs no knowledge of the cause.* The tell was
84 components, then 169 after adding edges that can only reduce them. **Where an
operation has a known direction of effect, assert the direction.** That catches this
with no insight into sparse storage whatever, and it catches the next instance too,
which will not be about scipy.

**One more, and it is the part that generalises furthest.** §10 states that a trunk
which does not close is a finding about the bathymetry. So a fragmented sea was a
*pre-registered* outcome, with an explanation already written down and waiting for it.
rewt-86 put it better than I did: **having a legitimate, pre-registered reason why
something might fail is the condition under which a real fault is least likely to be
debugged** — the explanation fits, so nobody looks further. That is worse than an
unexplained failure, which at least provokes a search. **When a result matches an
anticipated failure mode, that is the moment to check the machinery hardest, not to
write it up.**

---

**D-057 — `sea.clearance_m` was a guess that severed mouths from the sea; it is now
measured.** *2026-09-01*

I set it to 5.0 m before building anything, on reasoning about grid averaging and
survey error. The reasoning was fine and the number was unexamined, and it turned out
to be the single most consequential choice in the construction.

| clearance | 0 m | 1 m | 2 m | **5 m** | 10 m |
|---|---|---|---|---|---|
| tidal termini with open sea within 5 km | 76.0% | 67.5% | 63.8% | **56.0%** | 48.6% |
| coastal orphans, the same | 96.2% | 92.8% | 92.2% | **88.1%** | 80.3% |
| passable cells | 52.25M | 52.01M | 51.84M | 51.44M | 50.70M |

**The passable area moves 1.6% between 0 and 5 m while the connected share moves 20
points.** The cells that differ are not open sea being trimmed at the margins — they
*are* the coastal fringe, the strip that joins a mouth to the water. Around the Wash,
the Humber, Morecambe Bay, the Severn and most of the southern North Sea coast, water
5 m below Lowest Astronomical Tide lies kilometres offshore, so a terminus can sit
exactly on the waterline with nothing to reach.

**Set to 2.0 m.** It keeps a real margin for the 100 m cell averaging and the survey's
vertical uncertainty, and strands about four mouths in a hundred fewer than 5.0 did.
Not 0.0, which would admit water a hand's depth below the lowest tide and abandon the
margin the parameter exists to provide.

**The wrong explanation I carried for an hour is the part worth recording.** When 38%
of termini failed to reach open sea at 5 m, I told rewt-86 the failures were estuarine
nodes far inland where no sea exists — plausible, mechanistic, and consistent with its
finding that the median terminus is 3,410 m from a real survey. Measured, the failures
sit **97.1% within 500 m of mean high water and 0.0% more than 5 km inland**, and their
distance distribution is indistinguishable from the successes'. They were never inland.

rewt-86 had warned, before I measured, that distance from high water would not separate
the two cases. I recorded that as a refinement rather than as the objection it was,
because I already had an explanation I liked. **An explanation offered before its test
does not become evidence when a different measurement turns out to be compatible with
it** — and the CDI figure I leaned on was answering another question entirely.

---

**D-058 — The spanning tree *is* the sea network; the trunk step was left over from a
construction I had already refuted.** *2026-09-01*

§10 step 6 says the trunk is the segments many routes share, above `sea.trunk_share`.
Built, it yields **nothing: 0 cells at a threshold of 38 routes, from 3,770 traced
edges over 106,530 route cells.**

**That is not a finding about the bathymetry, and §10 would have let me report it as
one.** It is a defect in the specification, and mine. The usage-and-threshold step was
written for the *first* construction, where every terminus ran a path seaward to open
water: those paths would have converged, and a threshold would have found where. I
then refuted that construction — east-coast mouths run east, west-coast mouths west,
nothing converges — and replaced it with cost-allocation and a minimum spanning tree.
**The threshold step survived the rewrite without being re-examined.** In a spanning
tree over *adjacent* territories every edge is a short local hop between neighbours, so
no cell can carry many routes, and the threshold can only ever return nothing.

So it is vestigial and must come out of §10 rather than be tuned. Lowering
`trunk_share` until a line appeared would have manufactured exactly what the parameter
was written to forbid.

**What the construction actually produces, which is the thing that was wanted.** A
single connected network over all 3,771 sea entry points, 3,770 edges, traced into
106,530 cells of real geometry. Its shape says it follows the coast:

| degree | share | what it is |
|---|---|---|
| 1 | 25.2% | terminal mouths |
| **2** | **56.2%** | **chain — the coastal run** |
| 3+ | 18.6% | branch points, where an estuary's spur meets the chain |

A pure path would be ~100% degree 2. This is a coastal chain with spurs up each estuary
to the mouths inside it, which is what the geography implies and what a trunk-plus-
tributaries object should look like.

**One thing to be plain about: this is a tree, and a tree has no cycle, so it is not a
"loop" in the topological sense.** For the question Stage 1 asks — can every mouth
reach the sea and every other mouth — a tree is sufficient and a cycle adds nothing. A
closed circuit would add a second way round, which is a navigational convenience rather
than a connectivity fact, and this project has ruled navigation out of scope. If a
cycle is wanted it is one further edge, and it should be asked for as such rather than
arrived at by accident.

**All 3,770 edges traced, none refused, none unterminated** — which also confirms the
D8 backlink decoding, since a wrong direction convention would have sent walks off the
grid instead of into their sources.

---

**D-059 — §4's source count is right by accident; its composition is wrong.**
*2026-09-01. Raised by rewt-6a, which noticed 14 declarations against §4's six.*

§4 names four OS products plus two LiDAR services and says *resist adding more — every
extra source is a licence to check, a checksum to keep and a reason to defer the thing
that actually needs doing.* `conf/sources.yml` now declares **14**.

Counting declarations is the wrong measurement, so here is the right one: **6 of the 14
are read by a pipeline stage, and 8 are not.**

| | |
|---|---|
| read by a stage | `os_open_rivers`, `os_open_map_local`, `os_terrain_50`, `os_boundary_line`, `crt_navigation_structures`, `emodnet_bathymetry` |
| declared, read by nothing | `ea_lidar_composite_dtm_1m`, `nrw_lidar_dtm_1m`, `gb1900_raw_dump`, `eidc_uk_reservoir_inventory`, `mills_of_britain`, `nrw_large_raised_reservoirs`, `hct_historic_counties`, `nls_historic_map_tilesets` |

**So Stage 1 reads six sources, exactly as §4 budgeted — and not the six it names.**
Both LiDAR services are unread; the Canal & River Trust structures and EMODnet
bathymetry took their places. A reader checking the total would have found it correct
and concluded nothing had drifted. **The aggregate agreed while every row under it had
changed**, which is this repository's own recurring shape arriving in its own
specification.

**Not proposing to cut the eight.** Several are declared for consumers outside the
pipeline — `nls_historic_map_tilesets` for the tracer, `hct_historic_counties` as the
county vocabulary — and a registered source costs a licence check and a checksum,
which the tests already do and which is the cheap part. The two LiDAR services are §4's
own and are for the per-section work D-006 defers.

**What is worth fixing is the sentence, not the file.** §4 describes a repository that
no longer exists, and the useful form of its rule is not a count: *resist adding a
source that no stage reads*. A count invites exactly the error above — satisfied in
total, wrong in every particular. That is rewt-1d's to land in PLAN.md if Stephen wants
it, and this entry is what it would rest on.

**Amended, because "8 unread" was itself an aggregate hiding three different things.**
Pressed on whether the rule could be put under test, the eight separate cleanly:

| | |
|---|---|
| `stage: 2`, so no Stage 1 stage should read them — not drift | `gb1900_raw_dump`, `eidc_uk_reservoir_inventory`, `mills_of_britain`, `nrw_large_raised_reservoirs`, `hct_historic_counties`, `nls_historic_map_tilesets` |
| `stage: 1` and unread — **the whole of the actual drift** | `ea_lidar_composite_dtm_1m`, `nrw_lidar_dtm_1m` |

**And those two are not drift either, once the reason is visible.** D-006 has LiDAR
fetched *per section* when a person is adjudicating a place, never nationally —
`acquire.fetch` refuses a bulk request for it in terms. They are Stage 1 sources with
**no batch consumer**, which is a different thing from a source nothing wants. Marking
them `stage: 2` would have been wrong in the opposite direction, forbidding the Stage 1
tool they exist for.

The two states were indistinguishable until the declaration could say which, so they
now carry `per_section: true` with that reasoning inline. The rule is then testable and
passes today: **every source declaring `stage: 1` and not `per_section` is read by some
stage.** It would not have failed on the LiDAR entries; it would have asked, at the
moment they were registered, for the sentence explaining why nothing reads them — which
is the sentence that was missing for four months.

**Noting against myself that "8 unread" was the same error I had just written the entry
about.** I checked declarations against consumers, found a gap, and reported the gap as
a single number without asking whether it was one thing. It was three.

---

**D-060 — The sea test's headline number was measuring my snap radius, three times
over.** *2026-09-01*

§10 requires both readings published when the sea becomes a test: the old definition,
where *reaches tidal water* is true by construction, and the new one, where a mouth
must actually connect to the sea network. The old figure is **93.59%** of the in-scope
network. The new one moved twice under my own machinery before it settled, and each
move was a defect on my side rather than a fact about the coast.

| attempt | share | what it was actually measuring |
|---|---|---|
| test the outlet node's own attachment | 69.50% | the snap radius |
| follow the tidal channel first | 75.33% | the snap radius |
| **measure the radius and set it at the knee** | **88.18%** | the sea |

**The second fix was right and insufficient.** A basin's outlet is the tidal terminus
with the most water above it, which for the Humber sits 37 km up the estuary; its water
leaves at Spurn Head, and the `tidalRiver` links between are already in the network. So
a mouth reaches the sea if *any* terminus in its own tidal system does. That recovered
the Thames and six points, and left the Humber failing.

**Why the Humber failed is a fact about the source, and it is the case §10 was written
for.** OS Open Rivers draws linear watercourses. The Humber's tidal links stop at
E 503,007 — Trent Falls — and the estuary below it is an open water body the product
does not carry. So the water reaches the end of the survey and has nothing to continue
along. The Solway, the Tay and the Cree fail the same way. **Bridging exactly that gap
is what the sea network is for**, and my 5 km radius was too short to do it: the nearest
qualifying water is about 12 km east.

**The knee settles the parameter, and it is sharp:**

| radius | 5 km | 10 km | **15 km** | 20 km | 30 km | 50 km |
|---|---|---|---|---|---|---|
| share reaching the sea | 69.50% | 71.55% | **88.18%** | 88.19% | 88.20% | 88.88% |

16.6 points between 10 and 15 km, almost all of it the Humber and the 13,348 km behind
it. Past the knee the curve is flat — tripling the radius to 50 km buys 0.7 points —
and every kilometre past it is one in which a genuinely inland dead end might be joined
to a sea it does not reach. `sea.snap_radius_km: 15.0`.

**So the honest cost of turning a definition into a test is 5.4 points, not 24.**
93.59% reach tidal water; 88.18% reach tidal water that reaches the sea. **Most of the
network genuinely does get to the sea when asked; a twentieth of it does not, and
until today nothing could have told the difference.**

**The discipline that produced this is the one recorded in D-057, applied to a second
parameter.** Both numbers that mattered here — `clearance_m` and `snap_radius_km` — were
set by reasoning before anything was built, and both were wrong in ways that moved the
headline figure by tens of points. Neither was found by review. Both were found by
sweeping the parameter and looking for a knee, which costs minutes and should have been
done when they were written rather than after they had produced three different answers.

---

**D-061 — The sea test barely tests anything at the radius it is set to, and the
number swings 16 points on one estuary.** *2026-09-01*

§10's second reading is published as required, and **it is not yet a good test.** This
entry says so rather than letting 93.55% stand as an independent confirmation of
93.59%.

Swept against the test actually shipped — mouth attachment **plus** propagation through
tidal systems — the curve is not a knee but a cliff:

| radius | 1 km | 5 km | 10 km | **15 km** | 20 km |
|---|---|---|---|---|---|
| share reaching the sea | 61.79% | 75.33% | 77.04% | **93.55%** | 93.57% |
| km the test tells apart | 33,027 | 18,957 | 17,183 | **38** | 20 |

**17,145 km flips between 10 and 15 km**, almost all of it the Humber and what drains
into it. One mouth crossing one threshold attaches an entire tidal system, so the
national figure is decided by whether the nearest qualifying water to one estuary is
12 km away or 16 km. At 15 km the test separates **38 km of 97,195 — 0.04%** — which
is a test in form and not in substance.

**And I calibrated the radius on a different test from the one I shipped.** The 15 km
knee in D-060 was measured on seed attachment alone. Tidal-system propagation was then
added, which lengthens the effective reach, and the two changes were never swept
together. **A parameter calibrated against one test and used in another is not
calibrated**, and the resulting figure looked reassuring precisely because it agreed
with the number it was supposed to be checking.

**Not moving the radius to make the test look useful.** Choosing a threshold because it
produces more disagreement is the same act as choosing one because it produces less.
15 km is where the sweep on its own terms put it, and the cliff is a property of the
construction rather than of the value.

**What the construction actually needs**, recorded now while the reason is fresh: the
attachment is a *proximity jump* — a mouth is attached if open water lies within a
radius, with nothing said about what is in between. For the big estuaries the water in
between is the Humber, the Solway, the Tay: real tidal water that OS Open Rivers does
not draw and that this surface treats as impassable because it is shallower than
2 m. **The honest connection is a path through that water, not a jump over it** — the
estuary admitted to the cost surface as passable-but-expensive, so a mouth reaches the
sea by going down its own estuary rather than by being near enough to somewhere that
does. That would make the radius nearly irrelevant, which is the sign it is currently
doing work it should not be.

Until then the second figure should be read as *an upper bound with a known
discontinuity*, and the first as what it has always been.

---

**D-062 — The snap radius was a square, and both sweeps that calibrated it
reimplemented it.** *2026-09-01*

`sea.snap_radius_km` is named a radius and was a square. The search expands a window
of half-width *n* cells, so a cell in its corner sits *n*√2 away: at the declared 15 km
mouths were attached to water **21.1 km** off, and the published `sea_entry.snapped_m`
said so outright — a maximum of **21,143 m under a limit of 15,000**. It was in the
file before it was in my head, and rewt-fc asking for that column to be exported is
what put it there.

**The reason it survived two calibrations is worth more than the bug.** D-060's knee
and D-061's cliff were both measured by sweep scripts that **reimplemented the snap
inline** rather than calling `sea.snap`. So the instrument carried the same distortion
as the thing it was measuring, agreed with it perfectly, and could not have revealed
it. **A sweep that reimplements what it is calibrating is not calibrating it** — it is
two copies of one assumption agreeing, which is the day's shape again with the
measurement rather than the artefact as its subject.

The radius is now checked against the distance it claims, and the sweep calls
`sea.snap`. Re-run through the real function:

| radius | 5 km | 12 km | **15 km** | 20 km | 30 km |
|---|---|---|---|---|---|
| max snap | 5,000 m | 11,997 m | **14,946 m** | 19,998 m | 29,996 m |
| share reaching the sea | 75.33% | 77.05% | **93.53%** | 93.55% | 93.58% |
| km the test tells apart | 18,963 | 17,178 | **59** | 36 | 11 |

**The conclusions stand, which is the outcome that should be reported and not buried.**
The cliff is still between 12 and 15 km, still the Humber, and the test still separates
almost nothing at the working value — 59 km of 97,195. D-061 is unaffected in substance
and its figures are superseded by these. Had the correction moved the cliff, D-060's
choice of 15 km would have needed remaking; it did not.

**And the guard is now in the measurement rather than in my attention.** The sweep
prints `max snap` beside each radius. If it ever exceeds the radius again, the
parameter has stopped meaning what it says, and the table shows it without anyone
having to suspect it.

---

**D-063 — The Weaver drains, and the faults above it were undiagnosable until it did.**
*2026-09-01. Stephen: "It is obvious from satellite imagery that the River Weaver
empties into the Manchester Ship Canal, and so should share the same connection to the
sea — at Eastham Lock."*

He was right, and the fix was one reversal. The Manchester Ship Canal's 8,711 m reach
below Weston Point was digitised **eastward** along its whole length, so the canal
carried water inland: three links arrived at Weston Point and none left, with 1,178 km
above it. Turned round — keyed on the retired parent so it reached both children of the
Eastham split — the canal drains west through Stanlow and Ellesmere Port to Eastham
Locks and out to the tidal Mersey, every link on the chain reached, and the Weaver
leaves with it.

**Five further orientation faults then became provable, and could not have been
before.** `propose_reversals` requires the far end of a candidate to lie in the
*reached* set. While everything below Weston Point was stranded, no reversal upstream
could be justified — and the rule was right to refuse, because a reversal that points
water at a place which does not drain is not a fix. Once the canal opened, the rule
proposed the Wheelock (212.2 km), the Dane (75.7), Marbury Brook (50.4), an unnamed
watercourse beside the Dane (19.2) and a reach of the Macclesfield Canal. The Dane and
Wheelock now drain completely.

**So: a defect inside a stranded system is undiagnosable until the system's outlet is
fixed.** Not hidden by a weak rule — *unprovable*, because the evidence a reversal
needs does not exist yet. The audit's 953 stranded regions should be expected to hide a
similar tail, each openable only from its own outlet, and the corpus will grow in bursts
after each outlet is cleared rather than smoothly.

In-scope reachability moved **93.57% → 93.80%**; the Weaver work added about 1,950 km
across both steps.

**And chasing it exposed a flaw in the audit's own defect list.** It ranked dead ends by
the catchment standing above them, which counts water that has another way out.
**Stanlow Pool topped the Cheshire list with 1,514.5 km above it and nothing stranded
at all** — all three links arriving there reach the sea, because the node above also
drains west. A cul-de-sac off a working drain, ranked first in the list §6 asks a person
to work down. That is the most expensive place for a list to be wrong: the reader spends
their attention where there is nothing to find. The audit now computes stranded length
with a mask over the unreached links, publishes both figures, and ranks on the honest
one.

**One defect deliberately not fixed.** The largest remaining Weaver dead end is 356.6 km
at Northwich, where a reached Weaver link begins as a source **70.45 m away**. It has
the shape of a textbook connector — but the straight line between the two crosses **two
other watercourses**, and every one of the 1,204 connectors in the corpus was required
to cross none. It wants a person at the place, not a rule, and it is left on the list
rather than forced.

---

**D-064 — Browser reference data is committed under `docs/viewer/`, and the rule it
bends is named rather than assumed.** *2026-09-01. rewt-fc asked instead of excepting
itself, which is why this entry exists.*

`.gitignore` opens with *nothing acquired, derived or built is committed*.
`docs/viewer/` carries **337 KB of `counties.json`** — 52 Historic Counties polygons
simplified to about 200 m — and **16 `nls_*.json` collection lists**, about 160 KB.
All of it is derived, and all of it is committed.

**Why it cannot be fetched at runtime.** The browser masks the first-edition mosaics to
county boundaries in a canvas behind a `firsted://` protocol handler, because MapLibre
has no raster clip. That needs the rings client-side, before the first tile draws. The
NLS lists are the same: the viewer must know what collections exist to offer them.

**Why it is not generated in CI, which was the obvious answer and is wrong here.** The
Historic Counties source is declared `stage: 2`, and the pipeline refuses a Stage 1
stage that reads a Stage 2 source. Generating it in the Pages workflow would put two
external services in the path of every documentation deploy — a site that fails to
publish because a third party is down is a worse artefact than a stale polygon.

**So the rule's reason is what decides it, not its wording.** The reason is that a
committed artefact silently stops matching its inputs. **The two files differ in how
badly that bites.** The Historic Counties Standard is a fixed historical vocabulary and
does not change, so `counties.json` cannot drift from an input that is itself still.
The NLS lists are bucket listings and **will** drift as the Library adds collections —
that one is a real, accepted staleness, and its symptom is a collection the viewer does
not offer rather than a wrong answer about rivers.

**The boundary.** This exempts browser reference data that the page cannot function
without and cannot fetch at runtime. **It does not exempt the network, the basins, the
sea routes or any figure** — those are built in CI into `docs/viewer/data/` and are
committed nowhere, which is the whole reason Pages was moved off the branch build.

---

**D-065 — The map's data is a release asset, not a CI build. This corrects D-064's
closing sentence.**

*D-064 ends: "those are built in CI into `docs/viewer/data/`". That is wrong, and it was
wrong when written — I had not asked what CI would need in order to build them. It is
corrected here rather than edited there.*

**What CI cannot do.** Building `docs/viewer/data/` means having `published/`, and
`published/` is the output of the whole pipeline: OS Open Rivers, Terrain 50, Boundary-
Line, OpenMap Local, the Trust structures and 120 EMODnet windows, then the terrain
stage's twelve minutes of breaching and flow accumulation. A documentation deploy
cannot hold any of that, and a site that fails to publish because a bathymetry service
is down is the failure D-064 itself argued against two paragraphs earlier.

**The route it takes instead.** `rewt viewer-data` builds it beside a finished
`published/`; `rewt.tiles.pack()` tars it; the release carries it as `viewer-data.tar`;
`pages.yml` downloads it server-side and Jekyll copies it into the site. Nothing derived
is committed, which is the rule D-064 was defending, and it is defended better this way
than by a claim that could not be honoured.

**Why the download cannot be moved into the browser.** Release assets send no CORS
header, so a page cannot read one directly. Pages sends CORS *and* honours Range. The
hop through the workflow is what converts an unreadable asset into a Range-served file,
and Range is the whole mechanism: a PMTiles archive is read a viewport at a time. 322 MB
is served without any viewer downloading 322 MB. **This is what made a reduced extract
unnecessary** — the objection to the extract was that the viewer must be able to load
the whole dataset, and it now does, at every zoom to 14.

**A release event triggers the deploy, and the checkout must not follow it.** New data
means a new release, not a new commit, so `pages.yml` triggers on `release: published`.
But a release event's ref is the *tag*, and `actions/checkout` would then rebuild the
site from the tree as it stood at the tag — silently reverting every documentation
commit made since, with a green run and nothing to look at. The checkout pins the
default branch on release events. Adding `rewt/tiles.py` to the trigger paths would have
been the intuitive fix and does nothing: an edit there deploys nothing until a release
carries it. **The commit cycle and the release cycle are different clocks.**

**And the citations gate would not have caught it.** `sources_page.py --check` compares
two files in the same tree; at the tag they agree. Internal agreement is not correctness
unless something anchors it outside itself — which is also why
`release.attribution_drift()` checks each rendering against `conf/sources.yml` and never
against the other.

---

**D-066 — The never-thinned classes get their own archive, because sharing a tile with
the network was silently deleting them.**

*The viewer has said since its first hour that four classes are drawn whatever their
length — the stretch that cannot reach the sea, the retired line, the line this project
added, the line it turned round. **The archive was shipping 679 of 10,229 of them at
national view.** Found by rewt-fc, who tested the built archive instead of reading the
flags, and confirmed independently before anything was changed.*

**Why it is the worst possible defect for this project specifically.** A defect that
disappears when you zoom out does not look like a defect. The map looks *tidier*, and no
review catches it because there is nothing to see. A reader looking at 27 stranded links
on the Weaver at z13, zooming out to ask whether the problem is national, would have lost
24 of them and concluded it was local. **Every part was individually plausible and the
assembly was false**, which is what AGENTS.md means by checking the thing rather than the
aggregate.

**Two causes, and I reported the proportions backwards the first time.** Tiling
`link_kept` ALONE at the default budget puts 7,800 of 10,229 into the z5 tile; sharing a
tile at that budget gives 679. So eviction was the larger cause. The remainder is
coordinate quantisation, which no setting can reach: MVT snaps coordinates to a grid of
EXTENT units, at 53°N one unit is ~184 m at z5, and a line shorter than that collapses to
zero length and is discarded. The median never-thinned link is 394 m and a quarter are
under 80 m, so this takes about 2,430 of them at z5. I measured 1,100 once, concluded the
budget was irrelevant, and was corrected by an isolated build agreeing with rewt-fc's
independent browser count. **Two measurements that agree beat one that is convenient.**

**Raising the budget does not work, and the number proves it rather than suggesting it.**
Beside `link`, the points came out at 1,317 at z5 with MAX_SIZE at 20 MB and at *exactly*
1,317 with it at 500 MB. An identical count at a 25× budget means size was never the
binding constraint, and GDAL offers no way to prefer one layer's features over another's
within a tile.

**So the fix is structural: the four classes are not in the same tile as the 195,690
lines that were evicting them.** `rewt_kept.pmtiles` carries them as lines *and* as one
point each, taken on the line at its midpoint — a point has no length to lose, so
quantisation cannot touch it. Complete at every zoom, and the whole archive is 4 MB.

**The promise had to change as well as the data, because the old one was unkeepable.**
"Drawn at every zoom whatever their length" claims the *shape* is there, and at national
view it cannot be. The panel now says the classes appear below zoom 9 as marks rather
than as geometry — the mark says a defect is *there*, and the line appears when there is
a pixel to draw it in. Nothing is omitted at any zoom, which is the part that matters and
is now true.

**And the check is no longer a flag.** `rewt.tiles.verify()` reads the built archive back
through GDAL, zoom by zoom, and refuses a build where the point layer is short. The
original failure was a setting that was believed rather than tested; a second setting
would have been the same mistake with a different value.

---

**D-067 — Every gate in this repository compares the build against itself, and four
defects in one afternoon lived in exactly that blind spot.**

*Named by rewt-86 after finding the second of them. It is recorded as a decision because
it is a statement about what the checks cannot do, and the temptation on meeting each
instance is to write one more check of the same kind.*

**The four, all found the same way — by reading a published artefact against the code
that claims to produce it, which is not the same act as re-running the build.**

* **The attribution obligation had five renderings**, and the release note's was wrong:
  it dropped the consortium citation EMODnet's CC BY requires. Every renderer was
  internally consistent.
* **The never-thinned layer was thinned** — 679 of 10,229 at national view — while the
  viewer printed a promise that it was not. Nothing compared the promise to the archive.
* **`published/viewer-data.tar` was never repacked by anything.** `pack()` existed and no
  code path called it. The attached tar was ninety minutes older than the tiles, 35 MB
  different, and its `summary.json` agreed exactly with the shipped GeoPackage — so every
  count matched and the artefacts were a different pass.
* **The EMODnet `issue` fix could not reach the artefact.** The field is written at
  acquisition and the build only reads the stored record, so a full rebuild would have
  republished the old value with every gate green.

**Why more gates of the same kind would not have helped.** Each of these artefacts was
consistent — with itself, and with every other artefact. Consistency is what the gates
test. A stale upstream record propagates correctly into everything downstream, and the
whole set then agrees on the wrong string. **Agreement is not correctness unless
something anchors it outside the set.** That is the same sentence that made
`attribution_drift()` compare each rendering against `conf/sources.yml` rather than
against the other rendering, and it generalises further than that check does.

**What was actually built in response**, since a rule with no mechanism is a wish:
`viewer_data_drift()` compares the tar against the served tiles by size and digest rather
than by mtime; `tiles.verify()` reads the built archive back through GDAL instead of
trusting the settings that produced it; and `viewer-data` now repacks so the two cannot
be separate acts. Each of these anchors one comparison outside the thing being checked.

**The same shape occurs a level down, in the data rather than the artefacts.** rewt-86's
`propertyName` WFS fetch returned 46,766 features that were internally consistent, well
formed, and carried no geometry; every downstream computation was correct on data that
had lost the thing it was about. A count agreed with a count, and the request had
silently dropped the column the request existed for. **The test that catches that is not
a stronger consistency check but a question about what the data is for**, asked against
the thing itself.

**And the limit stays.** None of these gates would have caught the acquisition record,
and no gate of this kind will. The only thing that finds that class is a person or an agent
reading the artefact — which is why the release was held while four peers read it, and
why the value of that reading was highest exactly where the build was greenest.

---

**D-068 — The DOI badge resolved to a record containing no rivers.**

*Found by checking where the badge actually went, minutes after the first DOI was
minted. `zenodo.org/badge/latestdoi/<repo id>` redirected to `10.5281/zenodo.22238174`
— **one file, the source zipball** — while the deposit this project builds and checks
sat at `10.5281/zenodo.22238251` with all seven.*

**Both records are real and the hook made the other one.** Enabling the GitHub–Zenodo
integration means every published release is archived by the hook as well, and the hook
takes the source zipball only. `.github/workflows/zenodo.yml` exists *because* of that
— its opening comment says a hook-only record would resolve to a river project
containing no rivers — and the badge then pointed past the workflow to exactly the
record the workflow was written to replace. **The reasoning was right, was written down,
and the badge had not been checked against it.**

**Why the repository-id form was chosen, and why that was the mistake.** It never needs
editing: minted at the first release, follows every one after. That convenience is
precisely what binds it to the hook, because the repository id is the hook's handle and
there is no version of that URL that can point anywhere else. The badge now names the
concept DOI literally. It must be edited if the concept ever changes, and that is the
cost of it pointing where it is meant to.

**The duplicate cannot be withdrawn, only explained.** Both DOIs are permanent. The
remedy is to disable the hook so later releases mint one record rather than two, and to
say here which is which: **the citable record is `10.5281/zenodo.22238250`** (concept)
and its versions; `…22238174` is a source-only archive of the same tag.

**And it is D-067 once more, at the last possible moment.** Two artefacts, each
internally consistent — a correct deposit and a correct badge — produced by different
mechanisms, never compared. Every gate passed: the assets were verified byte-for-byte,
the record was checked file by file, and nothing asked whether the link a reader would
click led to the thing that had been checked.

---

**D-069 — A connector that runs uphill is refused. The rule that proposed them weighed
only distance.**

*Stephen looked at two connectors on the map and asked whether they were symptomatic.
They were, though not of what they looked like: both of his examples were defensible,
and measuring the class found 104 of 1,204 connectors climbing.*

**The rule, stated plainly.** `propose_component_outlets` takes a region of water that
cannot reach the sea and joins it to the nearest link that can, at their closest
approach — `ORDER BY gap_m LIMIT 1`. That is right in the large, and the measurement
says so: 942 connectors joined something other than tidal water, and from those same
points tidal water was a **median 26.8 km further**. Only 8 of 942 had tidal water at or
nearer than the target chosen. **The rule was not passing over obvious better targets.**

**What it could not see is the ground.** Two channels can be close in plan and separated
by an embankment, a road, or a watershed. Sampling the unconditioned Terrain 50 surface
at both ends of every connector: **104 of 1,204 rise more than a metre, 23 more than
five, and the worst climbs 27.4 m in 462 m.** Devonport Leat is among them — a leat is an
artificial contour-following channel, and a connector climbing 16 m out of one is not a
survey gap.

**Two metres is the model's noise, not a preference.** Terrain 50 is a 50 m grid; over a
few hundred metres of flat coast a metre of apparent rise means nothing, and rejecting on
it would refuse good joins in the Fens and the Levels where much of this work is. Two
metres is the observed 5th percentile of the fall distribution, so it is where signal
starts.

**Fixed in two places, and both are needed.** The proposer now considers several
approaches and takes the nearest that does not climb — terrain is a veto, never a
preference, so a longer connector is accepted only to avoid running uphill. And `repair`
refuses an uphill connector at apply time, because 1,205 proposals were already authored
and a fix in the proposer alone would have left every one of them applied. **62 are
refused**; the regions revert to dead ends, which the audit already reports with the
length stranded behind them. A join nobody can justify is worse than a defect somebody
can see.

**A person outranks a 50 m model.** Where the evidence does not say JUDGED BY RULE,
somebody looked at the place, and Terrain 50 cannot resolve a lock, a culvert or a pumped
outfall — which is what these joins usually are. Neither of the two human-authored
connectors climbs, so nothing is being overridden today; the exemption exists so that it
never silently is. The audit counts what got through, because a gate that is also its own
audit reports only that it ran.

**The check works at apply time only because `terrain` runs before `repair`.** That
ordering is load bearing: move `repair` earlier and the mosaic would be absent, the veto
would quietly pass everything, and a clean build would disagree with a rebuild. The stage
declares `terrain50_unconditioned` as a read so the dependency is stated rather than
relied on.

**And one performance trap, recorded because it nearly cost hours.** `raster.sample_points`
reads the whole band on every call. Sampling per connector would have read a 128 MB
raster 1,200 times; both the veto and the audit collect every coordinate first and read
it twice. The docstring says the function is for questions that are national — it is, and
that is exactly why calling it in a loop is wrong.

---

**D-070 — Before believing a selector, confirm it excludes something.**

*I reported a canal signal twice, with numbers, and there was no canal signal. The
classifier was `'canal' in reason.lower()`, and `propose_component_outlets` writes
"D-011: a canal reaches the sea through a structure the survey does not draw" into every
reason it generates. **It selected 517 of 517.** Measured on the actual `form` field,
canals climb LESS than everything else — 4.7% against 8.9%.*

**Why it was convincing.** The figure was not asserted, it was *computed*, which made it
look checked. A number carries the authority of a measurement whether or not the thing it
selected was the thing it was named for. Two people then spent an hour arguing about the
mechanism of the effect — aqueduct, cutting, embankment — and the argument got sharper as
it went, because that is what a real number does to careful people. rewt-fc's own line
came before either of us knew: *the physical story keeps being the part that is assumed
while the arithmetic is the part that is checked.*

**It is the same failure as D-039's `Medieval` also matching `Post Medieval`, in a field
nobody classes as a vocabulary.** That is why the recorded lesson did not fire: a `reason`
column is free prose until a template makes every value share a phrase, and then it is a
controlled vocabulary that nothing declares as one.

**Three sessions hit the shape in one night, in three surfaces.** This; a `curl` returning
200 from CARTO read as "no key needed", when the 200 was a tile with API KEY REQUIRED
written across it; and a grep of `nls_25_inch.json` for `mapseries` returning zero from a
file that holds layer *names* while a different file held the base URL. Status code for
content, substring for field value, filename for payload. **Each returns something crisp,
so it looks checked rather than assumed.**

**The test, which would have caught all three.** Print what the selector matches against
the population, and look at one row it rejected. `517 of 517` says it immediately;
`6.5% against 2.6%` does not. A filter that matches everything and a filter that matches
the right thing are indistinguishable from their output alone.

**What is retracted is an EXPLANATION, not a finding**, and the distinction matters
because "there is no canal signal" is easily misheard as "the refusals were wrong". The
veto never needed the canal story: 62 connectors climb more than 2 m, they climb whatever
they are made of, and joining a channel to water above it is wrong on its own terms. The
structure test stands. The 15 corroborated refusals remain the reinstatement candidates,
on the register rather than the terrain. **And the true headline is plainer than the
canals ever were: the dominant refusal is `inlandRiver -> inlandRiver`, 23 of 39 — an
ordinary stream joined to another stream that sits above it, needing no mechanism at all.**

---

**D-071 — The repository is public, and that reversed the ruling that contributed traces
stay private until published.**

*Recorded late, and the lateness is the point. `docuracy/REWT` was made public on
1 September 2026 and this entry is written on the 2nd, after rewt-2b went looking for a
number to cite and found that none existed. AGENTS.md says never to silently reverse a
decision recorded in this file — **the obligation is to the file, not to the
conversation**, and between two people who both knew what was happening it felt recorded
when it was not.*

**What was reversed.** Asked directly that morning whether contributed tracings could be
public, Stephen ruled they stay private until published. The reasoning was rewt-6a's
asymmetry and it is a good one: **private to public is one click; public to private is
impossible.** A trace released early cannot be recalled from a clone, a cache or an
index.

**Why it was overruled, in his own words.** *"Yes, the repo can go public: the Tracer
agent will warn that I said tracings should be private, but I am now overriding that
call."* He anticipated the objection and named the reversal himself, so nothing was
slipped past anybody. **What it bought was the DOI**: Zenodo does not archive a private
repository, and a citable record of the network — which is what the alpha existed to
produce — was not otherwise available.

**The argument was outweighed, not refuted, and that distinction is the reason to write
this down.** The asymmetry is still true. Nothing has shown that publishing early is
safe; a requirement simply arrived that was worth more. A reader meeting both rulings in
a year — with contributed traces flowing and the pooling question settled or not — needs
to know which of the two it was, because a refuted argument stays dead and an outweighed
one comes back the moment its counterweight is removed.

**What is actually public.** The code, the configuration, the curated judgements, and the
`traces` branch, which today holds five test events from Stephen and rewt-2b. Three of
their `reason` fields read *blah*. They were left deliberately: the branch's own rule is
that nothing is deleted to correct it, and suspending that the first time it is
*cosmetically* inconvenient is how such a rule stops meaning anything (D-067's neighbour
in reasoning, and rewt-2b withdrew the proposal to append a withdrawal).

**The gap this entry fills is the one it also demonstrates.** Two agents and a person all
knew the ruling had been overturned; the file did not. That is exactly the failure mode
D-067 describes at the level of artefacts, occurring at the level of decisions: everything
in the room agreed, and the record disagreed with all of it, and nothing compared them.

**D-072 — The viewer and the tracer treat the same NLS layers oppositely, and the
difference is whether there is a gate.** *2026-09-02*

*Stephen's ruling. Raised by rewt-fc and rewt-86; drafted by rewt-2b.*

The viewer publishes **no** NLS layer. The tracer publishes **all** of them — the seamless
six-inch first and second editions, the one-inch, and 88 county 25-inch sheets. Same
source, same unestablished licence, opposite treatment. Nothing recorded why, and the next
reader would have resolved that inconsistency in whichever direction they happened to
guess. This entry exists so they do not have to.

**The distinction is presentation, and it is D-043's reasoning applied to two tools.** NLS
state one condition: *"Re-use of these layers is intended within a desktop or local
environment. If you wish to present these layers online in a public website, please use our
Historic Maps API layers, or contact us."* The viewer renders sheets to any visitor and is
squarely inside that sentence. **The tracer renders nothing to anyone without a token** —
`startMap()` is reachable only from a successful sign-in, an anonymous visitor gets a wall
and fetches no tile, and no tile passes through this project's infrastructure at any point.
Stephen's ruling: the request concerns public presentation and does not reach a tool that
presents to nobody. *"The first edition MUST remain available on /tracer together with all
of the other historical map layers that we have assembled from NLS."*

**A second reading was raised and overruled, and it is recorded because the reasoning will
matter when the Library answers.** rewt-86 separated two things. The stated condition (a) is
about serving tiles, and a gate answers it — that half survives and is the basis above. But
(b): for the England-and-Wales layers **NLS publishes no URL at all**. They are absent from
the per-layer re-use table — counted in the page source, *England* 0, *Wales* 0,
*6inchsecond* 0 — and discoverable only by enumerating the S3 bucket. So a world-readable
catalogue is *an index the Library has not itself published, to precisely the layers it asks
not to be served publicly*, while a letter asking it for terms is pending. **Not a rights
question**: no copyright or database right subsists in the address of a tile, and rewt-86
declined to dress it up as one. A question of how it would look. Stephen decided the other
way, knowingly. The caution is recorded at its proper weight — raised, sound, overruled —
rather than dropped.

**The ruling rests on (a) alone, and it does so knowingly.** There is no "behind the gate"
for data. The repository is public — made so on 1 Sep 2026 because Zenodo will not mint a DOI for a
private one, which reversed Stephen's own earlier ruling that contributed traces stay
private until published — so the catalogue is
world-readable wherever it sits — `docs/`, `tools/`, anywhere. The gate covers **rendering**
and nothing else. Both remedies considered would have failed: relocating the file changes a
website URL and not its readability, and deriving the layer names at runtime cannot
reconstruct a seamless layer, which has no counties in it.

**Which is the collision worth recording, because it is the strongest argument for sending
the letter.** Applied honestly, the good-faith test removes exactly the layers whose names
had to be discovered — twelve of ninety, the rest being county names anyone would guess —
and two of the twelve are `os/6inchfirst` and `os/6inchsecond`. The second edition is the
tracer's default backdrop, the sheet the GB1900 work queue is transcribed from, and the
surface both tracing assists were calibrated on. The first is what the drowned-valley work
needs, and **the Historic Maps API carries no first edition at all** (D-037). So the
cautious answer takes out the layer the project most needs, and it was not engineered
around.

**One consequence to hold: the letter is now load-bearing.** Under this ruling nothing else
holds the position up. (a) is a reading of somebody else's sentence, and if NLS say a
credential gate is not what they meant, the position changes. That is a reason to send the
letter promptly rather than an argument against the ruling. The draft at
`~/Downloads/nls-enquiry-draft.md` asks the gate question in terms, and rewt-86 has amended
it to disclose that the catalogue is public — because asking whether a gate satisfies them
while omitting that would be asking a question with a fact missing from it, and the answer
would be worth nothing.

**And the split that follows.** The **viewer** uses NLS's Historic Maps API through MapTiler
— `uk-osgb10k1888`, six-inch second edition 1888–1913, **stated CC BY 3.0 with embedding
explicitly permitted**, which is the route their own guidance names. Attribution to the
National Library of Scotland with a link, free tier ≤100,000 tiles a month,
non-commercial. The **tracer** keeps the assembled S3 layers behind its gate and needs no
key at all. Neither tool carries both.

**Revisit this entry when maps@nls.uk answers.** It records a decision about how to read
someone else's terms, not a finding about what those terms are.

---

**D-073 — A surveyed structure outranks the terrain model. 16 refusals are reinstated.**

*D-069 refused 62 connectors for climbing more than 2 m. This exempts those the Canal &
River Trust's register corroborates, and it is corroboration overriding a measurement
rather than a threshold being loosened: `max_rise_m` keeps its value and its meaning, and
a connector with nothing near it is still refused however slightly it climbs.*

**The warrant.** Where the Trust records a lock, an aqueduct, a culvert or a weir within
150 m of a connector the terrain says climbs, **something was built at that place to move
water across it** — which is the very thing D-011 says the survey does not draw. A 50 m
grid whose cell is wider than a lock is the weaker witness. The rule already lets a
person's judgement override the terrain; a surveyed structure is the better warrant of the
two, because it was measured and a recollection was not.

**16 of 62, and the shape of them is the argument.** The corroborating structures are
**10 locks, 5 culverts and 1 weir**. D-011's own sentence names a lock first. Those 16 are
anomalous twice over — the terrain says uphill *and* something is there — which is what
makes them the reinstatement candidates rather than the doubtful ones. 46 remain refused,
with neither terrain support nor a structure, and they revert to dead ends the audit
reports with the length behind them.

**It is 16 rather than the 15 first reported, and the difference is where you look.** The
first count tested only the connector's first coordinate. **A lock or an aqueduct sits
where the two waters meet, which is an END of the connector** — and a short connector's
midpoint is a place where nothing was ever built. Testing both ends found one more.

**The stage order had to change, and the planner did it.** `structures` ran after `repair`,
so the register was not in the database when connectors were applied. Declaring `structure`
among `repair`'s reads let `plan()` reorder it — `acquire_structures` and `structures` now
run before `repair`. That is the same class of trap as D-069's terrain dependency, caught
the same way: **state the dependency and let the planner schedule it, rather than assuming
an order and reading a log to check.**

**150 m is not a new number.** It is the radius the audit already uses to corroborate a
refused 0 m crossing against this same register, so the two tests agree about what "at
this place" means.

---

**D-074 — An aggregate is not evidence that its members exist. Check that a number can
name its rows.**

*The audit published `connectors_that_climb: {climbing: 16}` and not one of the sixteen
places. Both producers of those findings ran after the findings table had been written,
so they appended to a list nobody read again. I then told rewt-fc the findings carried a
kind and a position, having written the code that emits them and never looked at the
output.*

**Why the count was persuasive.** `climbing: 16` reads as though something counted sixteen
things *it could name*. A summary carries an implicit claim about the enumeration it was
computed from, and here the enumeration was thrown away one line later while the summary
survived. Nothing was false: sixteen connectors do climb. The number was right and the
thing it implied was not.

**It is a different failure from D-070 and neither test catches the other.** D-070 is a
*selector* standing in for a measurement — `'canal' in reason` matching 517 of 517. This is
a *summary* standing in for its own members. The tests are separate:

* **before believing a selector, confirm it excludes something** (D-070);
* **before believing an aggregate, ask it to name a row** (this).

A selector that excludes nothing and an aggregate that can name nothing both produce
crisp, plausible output, and each passes the other's test.

**The fix that matters is the second one.** Moving the producers above the persist block
corrects today's instance. **Sealing the list corrects the class**: appending after the
write now raises a `StageError` naming the caller, so the next producer added in the wrong
place fails the build instead of quietly contributing nothing. rewt-fc's framing is right —
converting a silent wrong answer into a loud failure is the only kind of change that
survives someone who has not read the ordering. It is the same principle the viewer already
runs on a different surface: **an absent layer and an empty one must not look alike**, so it
names what is missing rather than drawing nothing.

**And the aggregate had already been published under a DOI.** `v0.1.1-alpha` carries the
count and none of the places. Stephen's call was to leave it rather than re-tag, which is
right — the figure is true, the gap is in detail rather than in fact, and the next edition
carries the repair.

---

**D-075 — Every release minted its own concept DOI. The badge pointed at a lineage of
one.**

*D-068 repointed the badge from the GitHub hook's record to a concept DOI of the real
deposit. It did not check that the concept was **shared**. `zenodo_deposit.py` called
`POST /deposit/depositions` unconditionally, which starts a fresh record every time, so
v0.1.0-alpha and v0.1.1-alpha became **two unrelated datasets** — concepts …22238250 and
…22248272 — rather than two versions of one.*

**What was false, and it was false in print.** The release notes tell a reader that the
concept DOI always resolves to the newest edition and that a result computed from a
particular edition must cite that edition's version DOI instead. The first half was
untrue for this project from the second release onward: …22238250 resolves to
v0.1.0-alpha and always will. `CITATION.cff` named it and described it in those words.

**Both DOIs are permanent and cannot be merged.** Zenodo does not support it and support
will not normally do it. The live lineage is **…22248272**, from v0.1.1-alpha onward;
…22238250 remains a single-version concept holding the first alpha alone. That is not
repairable, only stated.

**The fix, and why the anchor is declared rather than found.** `.zenodo.json` now names
`concept_recid`, and the script creates each release with `actions/newversion` on the
latest version under it. The *anchor* is stored and the *head* is asked for, because a
stored head goes stale at every release. Where no `concept_recid` is present the script
says loudly that it is starting a new lineage, so the silent case that caused this
becomes the announced one.

**And a new version inherits the previous version's files**, which are the previous
edition's data. They are cleared before uploading, or v0.1.2 would carry v0.1.1's
GeoPackage beside its own.

**It is D-068's own lesson one level deeper, and I made it while writing D-068.** That
entry says the repository-id badge was convenient and that the convenience is what bound
it to the wrong record. I replaced it with a literal concept DOI and verified the DOI
resolved — which it did, to a real record, with the real data in it. **Resolving to
something correct is not the same as resolving to the right thing**, and the check I ran
could not tell the difference. The test that would have caught it is the one D-074 asks
for in another form: not "does this identifier resolve", but "does it resolve to the
thing whose *name* it is being given" — here, the newest edition.

---

**D-076 — A figure in a message from another agent is not a measurement.**

*I told rewt-1d and rewt-2b that "267 of 1,806 probes at Ware" found channels whose sides
do not stay parallel, and proposed it as the centrepiece of a public page. rewt-2b searched
the tree, every markdown file and the whole git log, and **it is nowhere in this repository
or its history**. Nothing had measured it.*

**Where it came from.** rewt-1d's message to me: *"rewt-2b measured it at 267 of 1,806
probes on a six-inch patch at Ware."* I repeated it twice as fact, and told rewt-1d it was
*"the number you already put on the page"* — a provenance I invented for it by assuming
that a figure they had stated must be one they had published. **Three agents held a number
none of them had measured**, and each pass through a message made it look better sourced.

**Why it is a distinct failure and not a repeat.** D-070 is a selector that excluded
nothing; D-074 is an aggregate that could not name its rows. Both are about a computation
of one's own. This is about **provenance across a boundary**: a peer's message reads like a
report from a colleague who checked, and it may be a colleague repeating a third agent. The
usual defence — go and look at the artefact — is exactly what nobody did, because the
number was specific enough to look already looked-at.

**The test.** *A figure with no file behind it is a rumour.* Before relaying a peer's
measurement, find where it is recorded; if it is nowhere, say that it is unverified or ask
for the run. Being specific is not being sourced — `267 of 1,806` is more convincing than
`about a seventh` and was worth exactly as much.

**And where the figure carries an ATTRIBUTION, the cheaper test is to ask the agent named.**
*"rewt-2b measured it"* is the strongest false credential available and the easiest to
break: one message settles it, and **a peer who cannot say where their own number is
recorded has told you what you needed to know.** Nobody asked. rewt-2b has since put it on
the record that they never ran a sweep of 1,806 probes, at Ware or anywhere, and never
stated the figure — so the attribution was wrong before I ever repeated it, and repeating it
is what made it look confirmed.

**THE NEAR MISS IS THE SIGNATURE, NOT THE MITIGATION**, and this is the part to take
forward. The invented figure was `267 / 1,806 = 14.8%`; the measured one is
`3,346 / 24,336 = 13.7%`. Within a point. Every sanity check passed — right order of
magnitude, right sort of proportion for a refusal, nothing inviting a second look. **Had it
been 60% or 0.5% somebody would have gone and looked on instinct.**

It is the second instance in one day. rewt-fc's invented ink colour was `#6b6459` against a
real `#6c665d`, also within a point, and they said so unprompted: *the finding stood, but by
luck.* Two independent fabrications, both plausible, both landing inside the noise of the
true value. **That is not coincidence, it is what invention looks like**: a mind reaching for
a number reaches for a plausible one. So plausibility is evidence of nothing, and the
natural reaction to *it was nearly right* — relief — is the wrong one. The correct reading
is that the check failed silently and would have failed the same way at any value.

**And the real measurement contradicted the use I had planned for it.** rewt-2b then ran it:
24,336 probes over a 756 m square at Ware, of which 13.7% found a channel whose sides did
not hold — so the phenomenon is real and my instinct about it was right. But drawn on the
sheet, the acceptances follow the Lea and the New River **and equally the terraced streets,
the railway and the malthouses**. Asked everywhere, the assist is not selective for water at
all. Published as *"the tool sees something a person cannot judge by eye"* — which is what I
proposed — it would have been an untruth a reader could check in ten seconds by looking at
where the marks are.

**So the page says capability, then limit, then the evidence for the limit**, and the
cleverness it demonstrates is the tool knowing what it cannot tell. That is a better answer
to *show how clever the tool can be* than the one I was reaching for, and it exists because
somebody went looking for a number instead of passing it on.

---

**D-077 — "Not yet asked" and "asked, and it is not there" are different answers, and code
that conflates them fails silently.**

*rewt-fc's finding, recorded here because it is the third instance of one shape in a day
and the other two are already in this file.*

**The instance.** The viewer decided whether to offer the sea cross-tab theme by asking a
*rendered feature* what properties it carried:

```
map.querySourceFeatures('rewt', {sourceLayer: 'link'})[0]?.properties
```

It runs during boot, before the first tile has drawn, so it returned **zero features**, the
property set came back empty, and the theme was struck from the control. Seconds later the
same call returns 168,971 features carrying `reaches_sea`.

**Five confirmations across two sessions could not find it, and none of them was wrong.**
I verified the column in `export.py`, in the published GeoPackage, in the GeoPackage
downloaded back from the release, and in `rewt.pmtiles`; rewt-fc verified it independently
in the tar. Every check passed because **the data was never the problem**. The map's answer
to *does this build support the theme?* was decided by how much had rendered at one instant.

**The generalisation, which is the reason to write it down.** An empty answer was allowed to
wear the authority of a definite one — the same fault the predicate was trying to diagnose.
It is D-074's shape at a different scale: there an aggregate reported a count with no rows
behind it; here an absence of evidence was read as evidence of absence, and both produced
confident output nobody could challenge from the outside.

**The asymmetry that fixes it is not "read the metadata instead", though that is the
mechanism.** It is that **unknown must fail towards the visible fault**. Unknown now offers
the theme; only a metadata read that *succeeded* and did not list the property takes it
away. A theme that paints flat is a fault somebody reports. **A theme missing from a
dropdown is a fault nobody knows to look for** — so where a check cannot tell, it must
choose the loud failure over the quiet one, and that is a design rule rather than a bug fix.

**Three surfaces in one day**: an aggregate with no rows (D-074), a palette audit measuring
markers against markers rather than against the ground they sit on, and a capability probe
sampling a race. Each measurement was sound. **In each, the frame excluded the thing that
decided the answer.**

---

## D-078 — The canonical rule list lives in `conf/rules.yml`, and `rules/` is the intake

**3 September 2026, rewt-e8 (implementer).**

`rules/0001.md` asks for "a canonical machine+human-readable ordered list of rules", and
records the reason in its own first line: *"None of the examples given here should be fixed
with a one-off targeted fix, but rather by a general rule that should be applied across the
network."* Twelve observations, each given as an example of something general.

**The list is `conf/rules.yml` and there is one of it.** `rules/` keeps the raw intake — what
was observed, in the words of whoever observed it — and is never edited to agree with the
list. That separation is D-067's lesson applied before it can bite: TEAM.md and `rewt/team.py`
carried two renderings of one fact and had drifted apart within an hour of both being written,
in the file that records why that is dangerous. An intake note and a rule are genuinely
different documents, so they may both exist; two copies of the *rule* may not.

**Four things the file deliberately does not hold**, each because the alternative is a second
copy of a fact that will drift from the first:

- **No thresholds.** A rule names its parameters by dotted path into `conf/params.yml` and
  carries no number. `Rule.parameters()` resolves them, and raises for a path a rule names and
  the parameter file does not declare. A threshold written in two files will disagree with
  itself, and AGENTS.md already says where thresholds live.
- **No judgements about places.** A decision about one river belongs in `data/curated/` with a
  reason and evidence. `rules/0001.md`'s "Specific" entry — that `rewt:link/03cfec6fd5a1`
  should not exist because the streams it links cross with an aqueduct — stays an instance,
  recorded under `instances:` and pointing at the general rules it is an instance of (R-04,
  R-05). It is not promoted to a rule because it is not one.
- **No intent.** `status` says what is true of the build, not what anyone means to do. A rule
  is `implemented` only when `implements` names a module, and the loader refuses a rule that
  claims otherwise. Eleven of the twelve are `proposed`, which is the honest state of them.
- **No unresolved thresholds on a binding rule.** `proposed` may name a parameter that does
  not exist yet; `accepted` and `implemented` may not, and the loader raises. Otherwise a rule
  reads as binding while the number it depends on was never chosen.

**Order is semantic and is checked rather than assumed.** `order` runs 1..n with no gaps and
no ties, and the loader raises on either. R-01 redefines the sea before any connector is
invented, because a connector built against the wrong sea cannot be recognised as wrong
afterwards — the sequence is part of what the file says, and a tie means somebody added a rule
without deciding where in it the rule belongs.

**Every rule names a row.** Each carries the identifiers it was raised from, and
`rewt rules --check` resolves every one against the database. Same argument as the curated
files: a mistyped identifier does nothing while the stage reports success, which has happened
twice in the predecessor, once through a column nothing read. All 16 of Stephen's hand-typed
identifiers resolve, which is worth knowing rather than assuming. The check also has to look
in `repair_link` as well as `link`, for the reason in D-079.

**What this does not settle.** Whether each rule is *right* is not a question this file
answers, and eleven of twelve are `proposed` precisely so that the list can exist before the
argument is had. The failure mode to watch is a proposed rule quietly acquiring the authority
of an agreed one because it is written down in a configuration directory next to things the
build obeys. `rewt rules` prints the binding count for that reason, and it is 1.

---

## D-079 — The in-scope link population is not `link_scope JOIN link`, and the build has already got this wrong

**3 September 2026, rewt-e8 (implementer), with rewt-c1 (tests).**

Establishing what is in scope looks like a join and is not. `link_scope` carries 127,756
in-scope rows. 2,435 of those link ids are **not in `link`** — they are synthetic repair links
and live in `repair_link`. A further 635 in-scope rows are **retired**, and retired links are
kept in `link` rather than deleted, exactly as AGENTS.md requires. So:

    link_scope WHERE in_scope                      127,756
      minus retirement                                 635
      length from link OR repair_link
      = 127,121 links, 105,699.0 km

`link_scope JOIN link WHERE in_scope` gives **125,321 links and 105,462.8 km** — 1,800 links
and 236.2 km light. I wrote that join, believed it for several minutes, and was only caught
because the total failed to match `sea_reach.json`.

**This is not a hypothetical.** `published/audit/basins.json` publishes
`links.in_scope: 125321` and `in_scope_km: 105462.8`. `published/audit/sea_reach.json`, in the
same directory, publishes `in_scope_km: 105699.0`. **The repository ships two in-scope totals
that differ by 1,800 links, and nothing compares them.** Found by rewt-c1, who is widening the
suite to require every in-scope total published anywhere under `published/audit/` to agree.

**The general shape, which is why this is a decision and not a bug report.** The retirement
rule and the repair tables are each individually correct and each individually documented. The
population that satisfies both is stated nowhere, so every query that needs it re-derives it,
and the obvious derivation is wrong. **A rule about what is kept and a rule about where new
things live compose into a rule about what to count, and that third rule had no owner.** The
remedy is a single named view of the in-scope population that every consumer reads, rather
than four correct joins and one plausible one.

---

## D-080 — A delineated basin may not contain the sea, and the report that should have caught it filed it as correct

**3 September 2026, rewt-e8 (implementer), raised by rewt-46 (visualisation).**

Two in-scope basins labelled River Earn (4,176.3 km²) and River Nith (9,655.0 km²) are not
catchments. `ST_Contains` puts open sea off Arbroath and the mid Firth of Forth inside the
first, and the mid Solway and the mid Firth of Clyde inside the second. Both are single
contiguous polygons. The tidal surface was not removed before delineation, so every
watercourse entering a common firth accumulates to one sink and the firth ends up inside the
catchment. Between them they pull 5,411.5 km of network into scope, carrying 118 of the
1,303 declared defects — 9.1% of the backlog the deployed map calls the work.

**That 5,411.5 km is not "Scottish network", and an earlier draft of this entry said it
was.** It is the whole network in the two basins. `basins.json` puts 46.1% of the Nith's
area and 49.9% of the Earn's in Scotland, but that is area and not length, and every one
of the 6,654 links is in scope by the basin rule with none by the country rule, so the
build carries no measurement of the split. rewt-68 caught the overstatement, correctly,
on the ground that the claim would not survive being checked.

It is not two Scottish basins. Measured against this repository's own `sea_link` table, **99
in-scope basins enclose sea, totalling 2,896.9 km clipped to the polygon**, and **12 enclose
more sea network than river network** — Fleet Haven Outfall 104.2 km of sea against 102.3 km
of network, Afon Llifon 93.9 against 61.8. River Deben encloses sea off its own mouth; River
Lea encloses the mid Thames estuary. PLAN.md §4.1 warns about the shared-estuary trap in the
component census; this is the same trap in the topographic delineation, which the warning does
not cover.

**The part worth recording is not the defect. It is that the audit reported it as a success.**
`published/audit/basins.json` carries seven `cross_border_basin` findings. The Nith and the
Earn are two of them, next to the Tweed and the Esk, which are the genuine cross-border cases
D-024 exists to permit. The report says of the Nith: *"4,449 km2 of 9,655 km2 lies in
Scotland, and is in scope because the basin is"* — which is true, is the scope rule working
exactly as designed, and is completely uninformative about whether the 9,655 km² is a
catchment. **An amalgam was filed as an instance of a category that was working correctly, and
so was reviewed by everyone and questioned by nobody.**

That is worse than silence, and it is the generalisable part. D-077 says unknown must fail
towards the visible fault. This is the neighbouring case: **a correct measurement, reported
under a heading that supplies a reason for it.** The reason was real, so the reading stopped
there. The check that would have caught it does not need new data — the sea network was
already built, and no catchment may contain it.

**A one-row disagreement inside the audit, found while checking this.**
`audit.json`'s `shortfall_reason` for the Nith says *"93 dead end(s) remain"* and for the
Earn *"24 dead end(s) remain"*, totalling 117. `dead_ends.json` joined to `node_basin`
gives Nith 94 and Earn 24, totalling 118, and 118 is the figure rewt-46 reported and I
re-derived. One of the two attributions is wrong and both are published. rewt-68 found the
disagreement by reading the two files against each other; nothing in the build compares
them. Open, and in this directory.

**A second failure, and only one of them is visible to any check we have.** The Earn and the
Nith are findable because they drag Scotland into scope. The `rewt:basin-unanchored/`
coalescences are not: "River Aire" is 11,873.5 km² against a real catchment near 1,000 km²,
`outlet_node` NULL, and **100% of it in England and Wales**, so no scope figure can see it and
nothing else looks. Recorded as R-02 in `conf/rules.yml`; the remedy is R-01's, and neither is
implemented.

**On the labels, which are not the defect.** rewt-50 established that
`rewt/stages/basins.py:347 _label_for` takes the named river contributing the most
link-kilometres to the polygon, and its docstring says *"Purely for legibility in a report.
Nothing is decided on it."* So "River Aire, 11,873.5 km²" is a correct measurement printed
where it reads as a catchment name. Their warning is the useful half: **if the amalgams split,
these labels will start looking right without anything having been fixed, so that must not be
read as evidence the delineation improved.**

---

## D-081 — Four sessions, four different wrong numbers, and every one was caught by a peer

**3 September 2026, rewt-e8 (implementer).**

Recorded because the arrangement TEAM.md describes was tested on its first afternoon and the
tally is more useful than the conclusion. Working on D-080, four sessions each produced a
figure that was wrong, and **not one was caught by the session that produced it**:

- **rewt-e8**: summed whole `sea_link` lengths over an `ST_Intersects` join, so a sea link
  that merely touched a basin contributed its entire length. Afon Braint came out three times
  too large. Caught by rewt-46, who reproduced the wrong method exactly before clipping it.
- **rewt-e8**: added `reaches_tidal_km` to `sea_only_km` and reported a 58.3 km gap in
  `sea_reach.json`. The first already contains `reaches_tidal_only_km`, which is 58.3.
  `audit.json` sets `readings_are_nested: false` on that very section. Caught independently by
  rewt-46 and rewt-c1.
- **rewt-e8**: inner-joined to `audit_basin`, which 4 of 110 basins have no row in, and so
  reported 51 basins where there are 52 and bands summing to 106 against a headline of 110.
  Caught by rewt-c1 and rewt-46.
- **rewt-46**: grouped on `label`, which is NULL for 76 in-scope basins, and lost 23 of them —
  pandas drops null group keys where SQL keeps them.
- **rewt-c1**: the same fault in their own tooling, reporting 87 basins instead of 110, caught
  only because two sessions' numbers disagreed.

**Three things follow.**

**The disagreement did the work, not the re-derivation.** Several of these were found because
two sessions produced numbers that did not match, and one of them then went and looked. A
session re-checking its own figure re-runs its own assumption and obtains agreement (D-067).

**A different method beats the same method.** rewt-46 read the GeoPackage through geopandas
and rewt-c1 through shapely while I queried DuckDB. Where all three agreed the number is worth
something; the four errors above all survived at least one re-run by their author.

**Two of the five errors were the same error in two different sessions' tooling on the same
afternoon** — rows silently dropped, mine by an inner join to a table 4 basins have no row
in, rewt-c1's by a pandas groupby on a label that is NULL for 76 of 334. Neither would have
found it alone.

**rewt-c1 sharpened this and their form is the one to keep.** I first wrote it as "a
selector can exclude something and still return a plausible total". That is wrong in a way
that matters: *neither of us wrote a selector.* One wrote a join and the other a groupby,
and the row-dropping was the **tool's default** in both cases — nobody asked for it. This
is why D-070 does not reach it. "Confirm a selector excludes something" is phrased for a
WHERE clause, and 87 of 334 *does* exclude something, so that check passes while the
answer is wrong.

The rule that does reach it: **after any operation that can silently drop rows — an inner
join, a groupby on a nullable key, a merge, a `head` — the complement must be enumerable
and its reason nameable.** Not *did it exclude something* but *name what it excluded, and
why*. Had rewt-c1 asked which 247 basins were missing, "76 carry no label" would have come
back immediately and needed no second session at all.

A peer's count is the backstop and it worked here, but it is a weaker instrument than it
looks: **it only fires where a peer happens to compute the same quantity, and four of the
five figures above had nobody else computing them.** They were caught because they sat next
to one that did.

One near-collision worth writing down before it misleads someone: the sea enclosed by in-scope
basins is 2,896.9 km and `sea_reach.sea_only_km` is 2,890.4 km. They are unrelated quantities
0.2% apart, and TEAM.md's warning applies — a near miss is the signature of invention, and
here it is the signature of coincidence. Do not read either as confirming the other.
