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
