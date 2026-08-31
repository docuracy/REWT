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

## 7. Reference code, and how to use it

The predecessor is at `~/PycharmProjects/premodern-rivers` (private). **Do not copy from
it.** It carries assumptions from a pipeline that grew to 23 stages, and the point of
starting again is to leave those behind. Read it to avoid rediscovering a problem, then
write something cleaner.

| where to look | what for | what to avoid |
|---|---|---|
| `rivers/acquire.py`, `conf/sources.yml` | the declarative source model, and licence/attribution per source. Sound; the pattern is worth keeping | — |
| `rivers/network.py` | loading OS Open Rivers, node orientation, scope | it does a great deal besides |
| `rivers/repair.py` | the topology repair vocabulary, and the split-a-link-to-attach construction | grew case by case |
| `rivers/closure.py` | how connectors, reversals and junctions are actually applied; the "attach by cutting" logic | ~1,600 lines, rewritten in place five times, and its own handover says split it before adding more. **Read it; do not imitate its shape** |
| `rivers/db.py` | one module owns the database connection. Small and right | — |
| `tests/test_curated_ids_resolve.py` | the id-validation test. Port the *idea* | — |
| `data/curated/connectors/` | **the validation set** — 73 corrections with their reasons. Consult only after the audit works | do not import |
| `DECISIONS.md` D-065, D-124, D-133, D-136 – D-144 | why each correction class exists, and four measured failures | very long |

**On efficiency.** Two things dominated runtime and both have cheap answers. Spatial
self-joins over 120,000 links are slow: join on rounded endpoint coordinates instead, and
a query that ran for ten minutes runs in seconds. And per-row inserts with per-row geometry
parsing took ten minutes for 122,000 rows where one bulk insert took moments.

**On the database.** The earlier work uses DuckDB with a spatial extension, single-writer,
which is a good fit and worth keeping. Note that a read-only connection blocks writers, so
any long-running viewer must be stopped before a build.

---

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
