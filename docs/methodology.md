# Methodology

[← REWT](index.md)

## The finding that sets the order

A scoping exercise built this the obvious way: take the modern survey, filter out
channels known to be later, splice on attested medieval courses, model the flow. Each
stage layered on the last.

**Almost every serious defect it found was a fault in the modern survey's topology that
the later stages inherited, amplified, and then hid.** Rivers that stopped inland. Basins
draining into a node with no outflow. Tributaries drawn flowing away from the river they
join. Thousands of kilometres the water could never reach from the sea. Flow arriving at
a confluence and vanishing.

None of that is a reconstruction problem. It is a survey-topology problem, and everything
built above it stood on unstable ground. Hence the order below, which is a conclusion
rather than a preference.

---

## 0 · A build that reproduces

One command from an empty checkout to the published outputs, producing the same result
every time. Inputs immutable and checksummed; every stage idempotent; no cached
intermediate ever preferred to the configuration that produced it; the audit run as part
of the build rather than afterwards by hand.

This is first because the scoping exercise could not make that claim, and the failures
were mundane and expensive: stages that silently overwrote each other, a cached
intermediate preferred to a corrected setting for a month, a mistyped identifier that did
nothing at all while the pipeline reported it as applied.

## 1 · Make the modern network traversable

**OS Open Rivers does ship a topology** — some 197,000 explicit nodes, with flow direction
and names — and it is very nearly the only open British watercourse product that does.
What it does not offer, and does not claim to, is **traversability**: that from any
stretch the water can actually be followed downstream to the tide. It is a *generalised
cartographic* derivative with a node structure attached, not a hydrological model, and
nothing in it guarantees that a chain of links is unbroken or that every direction is
right.

Making it traversable is the first phase's work — as faithfully to the survey as the
evidence allows. **This phase reconstructs nothing.** Its product is a functioning
drainage network, and keeping that boundary sharp is what lets it use anything that
helps.

Three shapes of fault account for nearly all of it, and one question separates them:
*which end of the stranded channel touches the network?*

| finding | what it is | remedy |
|---|---|---|
| downstream end has inflows and **no outflow** | a real gap | a connector |
| **upstream** end touches a draining line | drawn backwards | reverse it — costs nothing |
| a reach two basins need in **opposite** directions | neither | make it two-way |
| the end sits *on* another channel, unjoined | no gap at all | a junction: add no geometry |

Getting that question wrong produces a fix that looks right nationally and is wrong at
the place. **Check at the place, never in the total.**

> ### Why start from OS Open Rivers at all?
>
> Because the alternatives are worse, and for instructive reasons. The choice was made
> on a comparison rather than by default.
>
> **CEH's 1:50 000 Digital River Network** — no topology, *by its publisher's own
> statement*, and available for educational use only. Neither problem is fixable.
>
> **OS OpenMap Local (water)** — open, and far better geometry: real polygons from which
> a true medial axis and channel width can be derived. But it is cartography with no
> topology whatever; measured, only about **4% of its endpoints are shared** between
> adjacent features. Four separate attempts to give it one failed. Its proper role is to
> contribute *attributes* — width, better centrelines — to a structure that comes from
> elsewhere.
>
> **The un-generalised OS water network** (Features API) — the same data before
> generalisation, and the obvious answer but for its licence: Premium, and not
> redistributable. Nothing derived from it could ever be published, which disqualifies
> it for an open dataset however good it is.
>
> **A network derived from a terrain model** — flow-routing over a digital elevation
> model produces a network that *cannot* have these defects: routing over a filled
> surface yields a directed forest, with no sinks and no cycles, by construction. It is
> genuinely tempting. But at 50 m resolution a cell spans roughly an eighth of a lowland
> meander wavelength, so the geometry is poorest exactly where this project cares most —
> the Fens, the Levels, the Humberhead — and it carries no names, so nothing in it joins
> to a documentary attestation. It is admissible as a **check on connectivity** and not
> as the network itself: it can say whether water can get from one place to another, and
> cannot say by which line.
>
> So: OS Open Rivers supplies the topology and the names; other products contribute
> geometry and evidence to it. The alternative is to ask a cartographic product to supply
> a topology it never had, which has been tried.

## 2 · Recover the old courses

Only once the modern network is sound, because a traced course must attach to something.

**From the maps.** Victorian six-inch sheets label some channels outright as superseded —
*Old Course*, *New Cut* — and volunteer transcription has made those labels searchable.
Each is an assertion by the surveyor, not an inference. Trace them at the resolution the
sheet supports, snapping to the printed ink.

**From under the reservoirs.** Channels drowned since the mid-nineteenth century are
recoverable from sheets made before the dam — which often means the *first* series, not
the second, because much of Victorian water supply predates it.

**From the documentary record.** Drainage and navigation works were legal acts over
specific ground, and a scheme had to be described against what was already there: land
taken had to be identified, and a new cut located relative to the old channel. So the
records behind such works — deposited plans, awards, estate and enclosure maps —
**sometimes** show the river as it ran before the work, and were drawn for a purpose that
required them to be accurate about it.

How often is not known, and should not be guessed. Survival is uneven, coverage is
patchy before the nineteenth century, and many plans show only the works proposed and not
the ground they replaced. The expectation is reasonable rather than established, and the
first task in this strand is to test it on a sample and find out — a scheme at a time,
recording what the record actually yields.

## 3 · Model the flow

Last, because it is cheap to re-run and meaningless on an unsound network. A per-cell
water balance routed over the network burned into a terrain model, validated against
modern gauged flow — and reported as a **relative index of channel capacity**, never as a
reconstruction of premodern discharge.

---

## Principles

**Every line carries what it rests on.** Source, date bounds, date precision, and a
confidence grade — never free text, never an unattributed assertion.

**Absence is drawn, not hidden.** Where the evidence runs out the map shows that it has
run out. A channel missing from the picture must never be readable as *no river here*.

**Nothing is deleted to correct it.** A superseded line is retired with its reason and
stays in the record. This is a research dataset; the audit trail is part of the product.

**Judgements live in diffable files.** A decision about a particular river belongs in a
committed text file with its evidence, not in code.

**The date is a parameter.** Nothing in the method fixes a single year.
