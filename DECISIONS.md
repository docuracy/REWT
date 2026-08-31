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
