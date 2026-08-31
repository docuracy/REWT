# Stage 1 — a traversable modern network

**Scope: this document, and nothing beyond it.** Stage 1 produces one thing — a river
network for England and Wales in which the water can get from any stretch to the sea. It
makes **no historical claim at all**. Everything about dates, old courses, attestation and
flow belongs to later stages and must not leak into this one.

Read [the methodology](https://docuracy.github.io/REWT/methodology) first for why the
order of work is what it is. This plan assumes it.

---

## 1. What "traversable" means, precisely

From every link, following flow direction downstream, you reach tidal water or a
boundary of the study area. Equivalently: **no node has inflows and no outflow**, except
at the sea or at the edge of scope.

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

Keep it small. Stage 1 needs three tables and no more.

**`link`** — one row per watercourse segment. Publisher id (stable, and the reason the
curated corrections survive a rebuild), geometry, name, length, and the two node ids.

**`node`** — one row per junction, with geometry and a terminus classification (sea,
boundary of scope, or neither).

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

**OS Open Rivers** is declared in `conf/sources.yml` and is the only source Stage 1 needs.
Ordnance Survey, Open Government Licence v3, attribution required: *Contains OS data
© Crown Copyright and database rights 2026.* Fetched from the OS Downloads API; reissued
twice a year, so record which issue was used — a result that cannot name its input cannot
be reproduced.

Resist adding more. Every extra source is a licence to check, a checksum to keep and a
reason to defer the thing that actually needs doing.

**Scope**: England and Wales, plus the catchments they share with Scotland — water that
drains through the study area must be routed even where it is not drawn. Decide the
treatment of Scottish headwaters explicitly and record it; the earlier work routes them
and never draws them.

---

## 5. Making it traversable

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

**Dead ends.** Nodes with inflows and no outflow, classified by terminus: at the sea
(correct), at the scope boundary (correct), or neither (a defect). Report count, length
above each, and the largest by catchment.

**Direction faults.** Nodes with one inflow and two outflows are the signature of a
tributary drawn flowing away from its parent — a class that a single earlier pass found
245 of.

**Touching but not joined.** Links whose endpoints coincide within a metre while sharing
no node.

**Cycles.** A closed loop with no exit strands everything above it, and is invisible in
any total.

**Reachability.** The share of length from which the sea can be reached. This is the
headline number and the one to watch.

**Report at the place, not only in the total.** Every serious defect in the earlier work
was invisible in the national figures — 481 km of holes arrived alongside a network that
had grown in both link count and length. Emit a coordinate for every finding.

---

## 7. What the predecessor learned

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

## 8. Definition of done

- One command, empty checkout to finished network, twice, identical output.
- The audit runs in the build and reports: reachable share, dead ends by class, direction
  faults, unjoined touching pairs, cycles.
- Every curated correction you author is applied and verified, or rejected with a reason.
- Every identifier in `data/curated/` resolves against the database, enforced by a test.
- The audit's findings compared against the predecessor's 73 recorded corrections, and the
  agreements and disagreements written up.
- No dates, no historical claims, no flow, anywhere in the output.

---

## 9. What Stage 2 will need from you

Not to be built now, but cheap to allow for and expensive to retrofit:

- **Stable identifiers.** Later stages add courses and epochs. A stretch present in two
  published editions must carry the same id in both. Design the scheme once, here.
- **Room for a course that is not an OS link.** Later, traced geometry joins the network.
  It should not require a second table or a second graph — the earlier work held two
  graphs for one geometry and could not reconcile them.
- **Corrections addressable by id.** The tooling that lets a reader report a defect
  depends on every drawn feature carrying an id they can send back.
