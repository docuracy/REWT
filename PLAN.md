# Stage 1 — a traversable modern network

**Scope: this document, and nothing beyond it.** Stage 1 produces one thing — a river
network for England and Wales in which the water can get from any stretch to the sea. It
makes **no historical claim at all**. Everything about dates, old courses, attestation and
flow belongs to later stages and must not leak into this one.

Read [the methodology](https://docuracy.github.io/REWT/methodology) first for why the
order of work is what it is. This plan assumes it.

---

## 1. What "traversable" means, precisely

From every link, following flow direction downstream, you reach tidal water.
Equivalently: **no node has inflows and no outflow**, except at the sea.

Note there is no second escape clause. Because scope is whole basins (§4.1) and every
basin drains to a coast, **an exit at the edge of the study area is not a legitimate
terminus — it is a defect.** Anything that appears to leave sideways means the scope was
drawn wrong, not that the water went somewhere unmodelled.

OS Open Rivers ships a topology — roughly 197,000 explicit nodes, with flow direction and
names, and it is very nearly the only open British watercourse product that does. What it
does not offer, and does not claim to, is this property. Supplying it is the whole of
Stage 1.

**Exit condition.** The audit in §6 runs clean, or every exception is named with a reason.
No node carries more than a nominal catchment draining into nowhere.

**Explicitly out of scope.** Dating channels. Removing canals or drains. Oksanen or any
attested course. Flow modelling. Tiles, maps, products, releases. If a task requires
knowing what year it is, it is not Stage 1.

---

## 2. Reproducibility comes first, not last

**One command from an empty checkout to the finished network, producing the same result
every time.** Build this before building anything it will run, because retrofitting it is
what the earlier work could not do.

The requirements, each drawn from a specific failure:

- **Declare every input; hard-code no URL.** Sources live in a configuration file with
  licence and attribution, and are fetched by one module. An unregistered source is an
  error, not a warning.
- **Inputs are immutable and checksummed.** Record a digest at acquisition; verify on use.
- **Every stage is idempotent** — it clears what it wrote before writing it. A stage that
  appends leaves the second run's output describing the first run's world.
- **No cached intermediate is ever preferred to the configuration that produced it**
  without a recorded fingerprint of that configuration. A corrected setting sat unused for
  a month behind a cached raster, and nothing said so.
- **Declare stage inputs and outputs so the order is enforced, not remembered.** In the
  earlier work one stage rebuilt a table another had written columns into; running them in
  the wrong order produced a plausible network with stale values on it.
- **Deterministic ordering** wherever a result depends on iteration order; a seed wherever
  anything is sampled.
- **The audit is part of the build**, not a script someone remembers to run.

---

## 3. Data model

Keep it small. Stage 1 needs four tables and no more.

**`link`** — one row per watercourse segment. Publisher id (stable, and the reason the
curated corrections survive a rebuild), geometry, name, length, and the two node ids.

**`node`** — one row per junction, with geometry and a terminus classification (sea,
boundary of scope, or neither).

**`basin`** — one row per delineated catchment, with geometry, its outlet node, and
whether it is in scope. This is the unit the audit reports in (§6) and the unit scope is
decided on (§4.1); it is derived, not acquired, and it is re-derived after repair.

**`correction`** — what was applied and why, one row per curated judgement, so the
difference between the survey and the published network is inspectable rather than
implied.

**Store the nodes already oriented**, so `from_node` is upstream and `to_node` downstream
for every row whatever the source. OS encodes direction *relative to the digitised line*,
and in the earlier work four separate places had to remember to flip it. Resolve it once,
at load.

**Never delete a link to correct it.** Retire it with a reason and keep it. The audit trail
is part of the product, and a retired link is how a reader tells a correction from an
omission.

---

## 4. Acquisition

Four sources, all Ordnance Survey, all open and all redistributable — so the repository
can go public without a licence review. Attribution for every one of them: *Contains OS
data © Crown Copyright and database rights 2026.*

| source | why Stage 1 needs it |
|---|---|
| **OS Open Rivers** | the network: geometry, topology, names, direction |
| **OS Terrain 50** | basins (§4.1), and a weak national screen on direction (§5) |
| **OS Boundary-Line** | the England-and-Wales polygon the scope rule tests against |
| **OS OpenMap – Local** | water-body polygons, for crossings only (§5) |

Plus two fetched **per section, never nationally**, for adjudicating a single link:
**EA LiDAR Composite DTM 1 m** (England, WCS) and **Welsh Government / NRW LiDAR DTM 1 m**
(Wales, tile catalogue). Both OGL. §5 has the endpoints and the traps.

OS Open Rivers is reissued twice a year, so **record which issue was used** — a result
that cannot name its input cannot be reproduced.

Resist adding more. Every extra source is a licence to check, a checksum to keep and a
reason to defer the thing that actually needs doing.

### 4.1 Scope is decided on basins, not on the border

**A basin is in scope if any part of it lies in England or Wales; the whole of that basin
then is, Scottish headwaters included.** Everything draining only to Scotland — Forth,
Tay, Clyde, Spey — leaves the project.

Clipping to the political line would replace one wrong answer with another. The Tweed
reaches the sea at Berwick with four fifths of its basin in Scotland; the Border Esk rises
in Cumbria and reaches the Solway in Dumfriesshire. Cut either at the border and
everything below the cut has lost most of the water that made it.

**Do not use the network's connected components as basins.** This is the cheap test, it
looks right, and it fails instructively: OS Open Rivers models the Solway Firth as
connected tidal water, so the Annan, the Border Esk and the Eden all land in a *single*
component — and the test drags Dumfriesshire into an England-and-Wales project because
three rivers share an estuary. **A shared estuary is not a shared catchment.** Only a
topographic delineation tells them apart, which is why Terrain 50 is in the list above and
why basins must be delineated before scope is decided.

**Two rules, and the second is not a fudge.** A link is in scope if its downstream end
falls in an in-scope basin, **or** if it falls in England or Wales. The second is needed
because tidal water is masked out of a DEM and so sits on no basin at all; without it the
scope silently drops the tidal Thames, the Humber, and the navigable head of every major
estuary in the country. For calibration, the earlier work put 72,367 links and 50,851 km
outside scope, and kept 122,104 links and 101,875 km.

**Nothing is deleted.** Out-of-scope links are flagged, not dropped, so the rule can be
changed without re-reading the source and "what was excluded, and was it right?" stays
answerable.

**Basins are recomputed after repair, not before.** Repair changes connectivity, so an
early delineation is provisional. Use a generous provisional scope to avoid doing national
work, and re-derive basins once the network is closed.

---

## 5. Making it traversable

### Start at the sea and crawl uphill

**Do not patch the network where it looks broken. Grow it from the sea, and let whatever
fails to arrive be the report.** Seed at tidal termini; admit a link only when the node at
its downstream end is already in the network; repeat until nothing more is admitted.

The two framings sound equivalent and are not. Patching asks *is this hole closed?*, and
answers yes for a hole whose closure leads somewhere else broken — in the earlier work a
link-by-link check reported every gap bridged while 3,440 km of river was still draining
into nowhere. The crawl asks the only question that matters, *can the water get out?*, and
cannot answer yes for a reach that cannot.

It also yields the audit for nothing. What the crawl did not reach **is** the defect list,
ranked by how much water stands above each entry, and every entry has a place.

**Seeds are a finding, not a parameter.** A seed is a node with no outflow standing at
tidal water. Take them from the survey's own `form = tidalRiver`, not from a coastline: a
coastline decides the question by distance from a modern shore, and is wrong at exactly
the estuaries where the answer matters. Seed anywhere in an in-scope basin, **including
Scotland** — the Border Esk's mouth is in Dumfriesshire, and a basin seeded only inside
England and Wales would strand the whole of it. Write the seed set out and look at it.

### The metadata will not tell you which links are wrong

Worth knowing before you plan around the flow-direction attribute: **it carries almost no
signal.** Of 194,471 links in Great Britain, **three** are recorded as flowing against the
digitised line. Direction *is* digitised order. A line drawn backwards is therefore
invisible in the attributes, and identical in every respect to one drawn correctly — which
is why the faults in §5's table are found from the graph and not from the columns, and why
a single earlier pass turned up 245 of one class alone.

So a node with inflows and no outflow is a *symptom* with several causes, and the table
below is how to tell them apart.

This is the substance. **Almost every fault is one of three shapes, and one question
separates them: *which end of the stranded link touches the network?***

| finding | what it is | remedy |
|---|---|---|
| downstream end is a node with inflows and **no outflow** | a real gap | a **connector** |
| **upstream** end touches a draining line at ~0 m | drawn backwards | a **reversal** |
| the end sits *on* another channel with no node | no gap at all | a **junction** |
| a reach two basins need in **opposite** directions | neither | `mode: both` |

Ask it **of every inflow separately**, not of the first that answers. Three channels
arrive at a sink; reversing the wrong one gives the node an outflow pointing deeper into
the same stranded region, and the total improves while the place stays broken.

**Find them yourself.** The predecessor accumulated 31 connectors, 17 reversals and 25
junctions, each checked at a place by a person. They are deliberately **not** carried
across (see `data/README.md`): they were made against that build's graph, and an audit
handed its answers is not an audit. Derive the candidates from §6, adjudicate them, and
record each as a curated judgement of your own.

Consult them afterwards, as a **validation set**. Independent agreement corroborates both;
disagreement is the more interesting result.

Three properties of these corrections are worth knowing in advance, because each was
learned expensively. **A connector is defined by its geometry, not by any link id** — each
end is resolved onto the network, cutting a link where there is no node, because snapping
to the nearest node left connectors attached to nothing 280 m and 377 m away and the stage
counted them as successes. **A reversal moves no geometry and changes no published
attribute** — only the routing graph — so the correction stays answerable. **A junction
adds nothing at all**: no geometry, no feature, no output row; the target is cut and the
node merged. A connector cannot express that, because its two ends would coincide, and a
zero-length connector once reached a published dataset as a row with no country.

### Flat water: canals, lakes and reservoirs

**A canal is not a drainage feature.** Water enters it from feeders and leaves through
locks, weirs and overflows that the survey does not draw, and its surface is level by
construction. OS assigns each canal link a direction regardless, because direction here
means digitised order. Lakes are the same case: a mesh of links across a surface with no
gradient at all.

The scale of it, measured on the earlier network: **252 canal links totalling 812 km
arrive at a node with no outflow** — about 30% of all canal length in England and Wales —
along with 101 lake links. Canals are only 1,584 links out of 194,471; they are wildly
over-represented in the fault list, and that is not a coincidence.

- **Do not require a canal to reach the sea down its own channel.** It reaches it through a
  structure. Either connect it to the receiving river where the overflow actually is and
  record that as a curated judgement, or exclude canals from the reachability requirement
  and say which. What you must not do is reverse canal links until the total improves.
- **Do not trust a direction fault on flat water at face value.** On level ground both
  directions are defensible from the geometry and neither is defensible from the terrain
  (below). These are the cases to adjudicate at the place, on a map, one at a time.
- **Reservoirs are the trap inside the trap.** A reservoir is a modern impoundment, so
  every link across it is a modern artefact — and a later stage will want to know that a
  valley lies underneath. Flag them now; the information is free at this point and
  expensive to recover later.

### Water bodies, where the survey routes through them or not at all

A fourth case, and it needs a second source. Where a watercourse meets a lake, reservoir
or broad, OS Open Rivers either draws a **schematic straight line** across it — some
2,300 km of the network is routed this way — or draws nothing, and the network is severed.

**A straight line through standing water is not a river course.** It is a routing device,
and where the water body is a modern impoundment the line runs where a valley used to be.
For Stage 1 that distinction does not matter — no historical claim is being made — but the
line must be **flagged as what it is**, so a later stage cannot mistake it for a channel.

Where no route exists at all, the defensible answer is the polygon's **medial axis**.
**OS OpenMap – Local** (Ordnance Survey, OGL) draws a watercourse as an *area* once it is
wide enough to show, and those polygons are the only open source of channel width in
Britain; their skeleton follows the channel more closely than OS Open Rivers, which is
generalised from larger-scale data. Width falls out as a by-product, which Stage 1 does
not need and later stages do.

Three cautions, all measured:

- **It is not a base network and must not be made one.** Its water has no topology
  whatever: 1.36 million lines in 892,000 components, only 4% of endpoints shared with
  another line, and **0.7% of its length in a component that reaches tidal water**. It
  supplies geometry; OS Open Rivers keeps supplying topology.
- **Width can measure the sea.** At estuary scale a "channel" is a bay, and a medial axis
  through one is meaningless. Exclude tidal water rather than discovering this in the
  output.
- **Skeletonise only where it earns its place** — where the survey gives no route, or
  where the schematic line is doing real routing work. Skeletonising every water body in
  the country is a large computation in exchange for very little.

### What a DEM can and cannot settle

Two jobs, and it is good at one of them.

**Basins: yes, and this is the real reason to acquire it.** §4.1 has the argument — without
a topographic delineation there is no way to tell a shared estuary from a shared catchment,
and the scope rule has nothing to test.

**Direction: a screen, never an authority.** Sampling the raw 50 m surface at both ends of
every in-scope link, against OS's stated direction:

| the DEM says | links | share |
|---|---|---|
| falls more than 4 m — clearly agrees | 54,747 | 44.9% |
| falls 0.5–4 m — agrees, weakly | 29,953 | 24.5% |
| within ±0.5 m — says nothing at all | 29,639 | 24.3% |
| rises 0.5–4 m — disagrees, weakly | 6,963 | 5.7% |
| **rises more than 4 m — clearly disagrees** | **757** | **0.6%** |

That last row is the useful one: **757 links, 589 km — a human-sized list**, worth
generating and adjudicating one by one.

But look where the DEM goes quiet. Terrain 50 posts every 50 m with an RMSE of about 4 m,
so a fall inside ±4 m is inside its own error bar. The share of each form that falls there:

| form | the DEM cannot adjudicate |
|---|---|
| inlandRiver | 46.6% |
| canal | 82.3% |
| tidalRiver | 89.1% |
| lake | 91.8% |

**It screens the uplands, where you least need it, and is silent on the levels, where you
most do.** Use it to rank candidates for a person to look at. Never let it flip a link on
its own, and never report a direction correction as made on terrain evidence when the
evidence was inside the error bar.

### A better DEM, per section, when you need to adjudicate one

Terrain 50 is the wrong instrument for the last mile. It is the right one for basins —
national, seamless, small enough to condition in one pass — but for settling *this* link
you want the best surface available at *that* place, fetched on demand. Both exist, both
are OGL, and both were tested against a live endpoint while this plan was written.

**England: EA LiDAR Composite DTM 1 m**, with a national WCS. Verified live: WCS 2.0.1,
axis labels `E`/`N`, EPSG:27700, GeoTIFF, covering 80000,4000–656000,665000. Ask it for an
80 m window at each end of a link and it answers in a second. Vertical error is around
±0.15 m against Terrain 50's ~4 m — confirm the current published figure when you write
the acquisition note.

It works. On six links where Terrain 50 was **completely mute** (|fall| ≤ 0.5 m over 1.5–4
km), the 1 m surface resolved four — including one canal falling 2.29 m *against* its
recorded direction, which Terrain 50 had scored as +0.30 m. There are 730 such links in
England in that length band alone: a real, worked, human-sized list.

**Wales: Welsh Government / NRW 1 m LiDAR (2020–23)**, OGL, but by a different route. There
is a WCS at DataMapWales and **it does not carry the DTM** — only noise-mapping coverages.
Use the tile catalogue instead: a WFS query by bounding box returns per-kilometre-square
features carrying a `dtm_link` to a GeoTIFF. Verified end to end — a 400 m box returned
square SH6055, and its tile is 1000×1000 at 1 m, 2.7 MB.

**Two traps, both hit while testing.**

- **The English service returns ZEROS over Wales, not nodata.** Asked for Snowdonia it
  answers 0.0 m across a full grid of valid-looking cells; the Welsh tile for the same
  point reads 579–1055 m. Nothing in the response says the data is absent. A sampler
  without a guard will compute confident nonsense for the whole of Wales and along the
  border, and it will not look like an error. **Test coverage explicitly; never infer it
  from nodata.**
- **A level canal is level at any resolution.** The Monmouthshire and Brecon fell 0.00 m
  over 3.91 km on the 1 m surface. Resolution is not the constraint there — the water
  genuinely has no gradient, and no DEM will ever settle it. Those links need a different
  kind of evidence, or an explicit exclusion.

**Sample a window, not a point.** A single cell lands on a bank, a bridge deck or a
building. Take a low percentile — the 10th worked — of an 80 m box, and treat a fall of a
few centimetres as no answer: the composite mixes flight epochs, and a river's surface
moves with its stage.

**One circularity to avoid.** Burning the network into the DEM is the standard first step
in any hydrological conditioning, and it is correct for delineating catchments — a 50 m
surface gives no gradient at all across embanked or levelled ground. But a burned DEM has
had the network's own direction stamped into it, so **checking direction against it proves
nothing**. Sample the unconditioned surface for that, and keep the two rasters distinct
and distinctly named.

**Order matters and is not obvious.** In the earlier work, corrections applied before the
features they referenced existed reported "no such edge" and did nothing — silently
except for a log line, and including the single largest defect in the country. Apply each
class where its targets exist, and **name every skip**.

**Validate every identifier against the database.** A mistyped id does nothing while the
stage reports the correction as loaded. This has happened twice, and once through a
column that nothing reads — so the wrong value was invisible. Make it a test.

---

## 6. The audit

Build this as a stage that runs with every build and fails loudly.

**Dead ends.** Nodes with inflows and no outflow, classified: at tidal water
(correct) or not (a defect). Break the defects down by the form of the water arriving —
inlandRiver, canal, lake, tidalRiver — because the classes have different causes and
different remedies, and a single total conceals that canals are ten times
over-represented. Report count, length above each, and the largest by catchment.

**Direction faults.** Nodes with one inflow and two outflows are the signature of a
tributary drawn flowing away from its parent — a class that a single earlier pass found
245 of.

**Touching but not joined.** Links whose endpoints coincide within a metre while sharing
no node.

**Cycles.** A closed loop with no exit strands everything above it, and is invisible in
any total.

**Reachability.** The share of length from which the sea can be reached. This is the
headline number and the one to watch.

**Report per basin, and rank them.** A basin is the natural unit: it has one outlet,
so "what share of this basin can reach its own sea?" is a complete question with a number
for an answer. A national figure of 97% hides a basin at 40%, and the basin at 40% is the
entire finding. Rank by unreached length and work down the list.

**Report at the place, not only in the total.** Every serious defect in the earlier work
was invisible in the national figures — 481 km of holes arrived alongside a network that
had grown in both link count and length. Emit a coordinate for every finding.

### Calibration: what the first audit should say

Check the loader against known figures before trusting anything downstream. OS Open
Rivers **as shipped**, whole of Great Britain, before any repair:

| | links | length |
|---|---:|---:|
| inlandRiver | 156,808 | 138,402 km |
| lake | 24,490 | 5,864 km |
| tidalRiver | 11,589 | 5,738 km |
| canal | 1,584 | 2,722 km |
| **total** | **192,865** | |

with about 198,000 explicit nodes, and **three** links recorded as flowing against the
digitised line.

And the defect list Stage 1 exists to clear, on the orientation OS ships:

| | nodes |
|---|---:|
| inflow and no outflow, Great Britain | 6,197 |
| the same, in scope | 2,985 |
| of those, at tidal water — correct | 469 |
| **not at tidal water — the work** | **2,516** |

By the form arriving there: inlandRiver 2,323 links and 2,861 km, canal 635 and 1,535 km,
lake 261 and 94 km. **That canal figure is 56% of all canal length in Britain**, and it
corroborates §5 — read it as one structural fact about canals, not as 635 bugs.

The GB figures should match closely; if they do not, the loader is wrong and nothing
downstream is worth looking at. The in-scope figures depend on your own basin
delineation, so expect them to differ by a few per cent — and if they differ by more than
that, question the delineation before questioning the network.

---

## 7. The deliverable, and the conventions around it

Stage 1 is finished not when the network is good but when someone else can pick it up.
Four things the sections above leave implicit.

**What comes out.** A published directory, rebuilt from scratch by the same one command:

- **the network**, GeoPackage, EPSG:27700, links and nodes as separate layers. Every link
  carries the publisher id, the oriented `from_node`/`to_node`, name, length, form, its
  basin, whether it reaches tidal water, and an `origin` saying whether it is survey,
  connector or skeleton. A consumer must be able to tell what came from Ordnance Survey
  and what this project added, without reading the code.
- **the corrections**, as their own layer or file, so the difference between the survey and
  the published network is a thing you can open.
- **the audit**, machine-readable and human-readable, per basin and national.
- **the attribution**, carrying every source's required statement in full.

**Curated files are the human judgements, and they are the product.** One diffable file
per correction class under `data/curated/`, one row per judgement. Every row carries a
stable identifier for what it acts on, a `reason` in words, and **evidence** — a place, a
source, or a person and the date they looked. A correction without evidence is
indistinguishable from a guess a year later. Connectors are defined by their geometry so
they are GeoJSON; reversals, junctions and exclusions are CSV keyed on publisher ids.
Every identifier in every one of them is validated against the database by a test that
runs in the build, not by hand.

**Keep an append-only decision log.** Dated, numbered, one entry per design decision, with
the reasoning and not just the outcome — and never silently reverse one. It is the single
most useful artefact the predecessor produced, and the cheapest to keep.

**Provenance travels with the data.** Wherever a short attribution appears, it may never
attribute less than `conf/sources.yml` does.

### What this plan deliberately does not decide

Yours to choose: language and packaging, module layout, and how stages are invoked.
Nothing in §1–§6 depends on any of it.

The defaults assumed here, to be overturned only with a recorded reason: **Python**;
**DuckDB with its spatial extension**, with exactly one module owning the connection so
that moving to PostGIS stays cheap; and stages as subcommands of a single entry point.
Note that a read-only DuckDB connection blocks writers, so anything long-running that
holds one — a viewer, a served map — must be stopped before a build.

The four OS products are **open, and need no API key**. Do not build an authentication
path you will not use.

---

## 8. What the predecessor learned

A scoping exercise built this once, under the name *Premodern Rivers*. Its reasoning is
public and worth reading before starting; its code is not the model to follow.

**Public, and the place to start:**

- [Methodology](https://docuracy.github.io/premodern-rivers/guide/methodology.html) — how
  the network was assembled, and the order of operations that turned out to matter.
- [Status](https://docuracy.github.io/premodern-rivers/guide/status.html) — what worked,
  what did not, and the measured limits. Candid by design.
- [Next steps](https://docuracy.github.io/premodern-rivers/guide/next-steps.html) — the
  analysis this plan implements, including why the modern survey's topology comes first.

**The lessons that bear on Stage 1**, stated here so they need no access to anything:

| lesson | what it cost |
|---|---|
| A cartographic product will not supply a topology it never had | four attempts to give one to an area-based water layer, all abandoned |
| A correction that references a feature by id does nothing, silently, when the id is wrong — while the stage reports it applied | twice in one day, once through a column nothing reads, so the error was invisible |
| Corrections applied before their targets exist are skipped silently | 11 of 25 did nothing, including the single largest defect in the country |
| Ask *which end touches the network* of **every** inflow, not the first that answers | a sink given an outflow pointing deeper into the same stranded region |
| A defect is invisible in national totals and obvious at the place | 481 km of holes arrived alongside a network that had grown in both count and length |
| A flow model reports a confident number over a network the water cannot leave | months of figures that had to be withdrawn |
| Two graphs over one geometry cannot be reconciled after the fact | the reason that pass stopped where it did |

**One architectural warning.** The predecessor's routing module reached ~1,600 lines and
was rewritten in place five times; its own handover records that it should be split before
anything more is added. Whatever you build here, keep the trace, the curated inputs and
the reporting as three separable things.

**Two performance findings**, each of which cost a day. Spatial self-joins over ~120,000
links are prohibitively slow — join on **rounded endpoint coordinates** instead and a
ten-minute query becomes seconds. And per-row inserts that parse geometry per row took ten
minutes for 122,000 rows where a single bulk insert took moments.

**On the database.** DuckDB with a spatial extension proved a good fit and is worth
keeping: one module owning the connection, and the option of moving to PostGIS left open.
Note that a read-only connection blocks writers, so any long-running viewer must be
stopped before a build.

*The predecessor repository is private. Its source is available on request, and should be
read for context rather than copied — the point of starting again is to leave its
accumulated assumptions behind.*

## 9. Definition of done

- One command, empty checkout to finished network, twice, identical output.
- The loader reproduces §6's calibration figures for Great Britain.
- The deliverable of §7 exists, and a stranger can tell survey from correction in it.
- The audit runs in the build and reports, **per basin and nationally**: reachable share,
  dead ends by class, direction faults, unjoined touching pairs, cycles.
- Basins delineated, scope decided on them, and the in-scope set written out for
  inspection — with the cross-border cases named individually.
- Every basin either reaches 100% reachable, or its shortfall is named with a reason.
  Canals excluded from the requirement is an acceptable reason; "improved a lot" is not.
- Every curated correction you author is applied and verified, or rejected with a reason.
- Every identifier in `data/curated/` resolves against the database, enforced by a test.
- The audit's findings compared against the predecessor's 73 recorded corrections, and the
  agreements and disagreements written up.
- No dates, no historical claims, no flow, anywhere in the output.

---

## 10. What Stage 2 will need from you

Not to be built now, but cheap to allow for and expensive to retrofit:

- **Stable identifiers.** Later stages add courses and epochs. A stretch present in two
  published editions must carry the same id in both. Design the scheme once, here.
- **Room for a course that is not an OS link.** Later, traced geometry joins the network.
  It should not require a second table or a second graph — the earlier work held two
  graphs for one geometry and could not reconcile them.
- **Corrections addressable by id.** The tooling that lets a reader report a defect
  depends on every drawn feature carrying an id they can send back.
