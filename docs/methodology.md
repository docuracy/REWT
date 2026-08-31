# Methodology

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

**[OS Open Rivers](https://www.ordnancesurvey.co.uk/products/os-open-rivers){:target="_blank"} does ship a topology** — some 197,000 explicit nodes, with flow direction
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

> ### What an unburned terrain run actually does
>
> This qualification decides how far a terrain check can be trusted, and it cuts against
> the idea above.
>
> Any hydrological conditioning **burns the mapped network into the surface** before
> routing, deeply enough that the burned line wins against 50 m cells over embanked and
> levelled ground where the true gradient is below the vertical resolution. Wherever the
> survey draws a channel through a culvert or under a bridge, the burn cuts a trench and
> the water follows it. **Continuity there is supplied by the survey's line, not by the
> terrain** — which is precisely why a burned run is no use as independent evidence.
>
> Unburned, the two cases behave very differently on a bare-earth model:
>
> - **Bridges are not in it.** A deck is not ground, so a bridged valley stays continuous
>   and routes correctly without help. This case is fine.
> - **Embankments are ground, and they are in it.** A river culverted under a motorway or
>   a railway meets, in the model, an unbroken dam. Flow ponds behind it — and depression
>   *breaching* then carves a trench along the steepest descent, through the embankment at
>   whatever point is lowest, which may be hundreds of metres from the actual culvert. The
>   result is not a gap. It is worse: **a false continuation**, geometrically wrong and
>   indistinguishable in the output from a real one.
>
> So the terrain's verdict is sound on **connectivity** — *can the water get from here to
> the sea at all* — and unsound on **route** — *by which line*. That is still the question
> this phase needs answered, because a dead end is a connectivity failure. But it means the
> terrain may **flag and rank, never draw**. Any continuation it proposes is a place to
> look, not a line to adopt.
>
> Three cheap things sharpen it, in rough order of value:
>
> 1. **Run it both ways and diff.** A discontinuity that appears in the *burned* run as
>    well is a real gap in the survey; one that appears only unburned is an embankment
>    artefact. That single comparison separates the two populations with no extra data.
> 2. **Record breach depth per carve.** A trench cut several metres through ground is
>    telling you it crossed an embankment; a shallow one is following a valley.
> 3. **Mask the embankments** using the open road and rail networks — a culvert candidate
>    is a road or railway crossing a modelled flow path. Most work, least certain, and it
>    should follow the first two.

### The sea is currently an abstraction, and it should be an object

Every rule in this phase ends at the same place — *and then it reaches the tide* — and the
tide is not modelled at all. A river mouth terminates in a patch of nowhere, each basin in its
own separate patch, and "reaches the sea" is true by definition rather than by test. That is
also why an estuary is the hardest thing here: the survey draws a river mouth as an **area**
and offers the network no line to end on.

The proposal is to give the sea a geometry: **a single path around the coast of England and
Wales at optimum sailing distance, with branches connecting it to each river — and the loop
is the terminus.** Three things follow, and the third is why it works where an attested
gazetteer of ports does not.

- **The audit gets an object to test against.** *No node has inflows and no outflow, except at
  the sea* becomes *except where it joins the loop*, which is checkable rather than
  definitional. A river that fails to reach the loop is a finding; today it is an assumption.
- **Port to port becomes computable** — down one river, along the coast, up another. That is
  the journey the [navigation evidence](evidence#navigation) is actually about, and no purely
  fluvial network can express it.
- **It is generated rather than attested**, so it exists at *every* river mouth. A corpus of
  historical ports, however good, records where trade happened and not where rivers end; it is
  a sample where this needs a structural feature.

**One distinction has to be kept sharp, because it decides which phase this belongs to.** A
path optimised for *distance* is a geometric object with no year on it, and could be built
alongside the modern network. A path optimised for a particular vessel in a particular month —
which is what a sailing-route model actually computes, from wind, current, draught and
visibility — is a **historical claim**, and belongs with the dated cross-sections. They are
different objects that would look similar on a map, and building the second while calling it
the first is exactly the kind of drift this project is arranged to prevent.

**Exit condition.** No node carries more than a nominal flow into nowhere; the unreached
residue is *explained* rather than merely counted; and the audit runs clean or every
exception is named with a reason.

## 2 · Recover the old courses

Only once the modern network is sound, because a traced course must attach to something.

**From the maps.** [Victorian six-inch sheets](https://maps.nls.uk/os/6inch-england-and-wales/){:target="_blank"} label some channels outright as
superseded — *Old Course*, *New Cut* — and [GB1900](http://www.gb1900.org/){:target="_blank"}, a volunteer transcription of every label on
them, has made those statements searchable.
Each is an assertion by the surveyor, not an inference. Trace them at the resolution the
sheet supports, snapping to the printed ink.

**From the sheets themselves, and not only from their labels.** A caption is the surveyor
volunteering an observation. Most abandoned courses never got one: *Old Course* is written
where somebody thought the fact worth recording, not wherever a river has moved. **The labels
are a lower bound on what the six-inch record holds** — the cheapest findings in it, not the
complete set.

So the sheets should also be read *systematically*: **every river course inspected along its
whole length against the printed channel**, on the **first edition** where it exists and the
second where it does not, flagging every significant departure of the historic channel from
the modern line. That finds the courses no volunteer transcribed because no surveyor
captioned them, which is most of them.

Two things keep this bounded rather than open-ended. The first pass is **mechanisable**: the
modern network can be overlaid on the georeferenced sheet and the divergence measured, so a
person judges only the places where it exceeds a threshold. And **the threshold has to sit
above the modern product's own generalisation** — OS Open Rivers is a cartographic
derivative, and a sweep tuned finer than its own smoothing will report the difference between
two drawing conventions and call it a change in the river.

It is work that scales with the **length of the network** rather than with the number of
labels, which puts it in a different class of cost from the labelled assertions above. It
also divides cleanly — one reach, or one sheet, at a time — which makes it the most natural
thing in the whole programme to invite help with.

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

**Exit condition.** Every *Old Course* and *New Cut* label adjudicated — traced, rejected
with a reason, or recorded as illegible — with provenance per vertex; every matched reservoir
either traced from a pre-dam sheet or recorded as having none; and every reach swept against
the earliest available edition, with each flagged departure traced, dismissed as
generalisation, or recorded as illegible. [How many that is](scale).

### Go to the sources, not to the synthesis

The deeper point about this phase, and it reframes what [Oksanen's GIS of pre-1348 inland navigation](https://doi.org/10.5284/1057497){:target="_blank"} is *for*.

A synthesis of medieval navigation is a **digitisation of other people's evidence** —
documentary attestations of shipping, archaeological finds, place-name landing places, and
courses fossilised in parish boundaries — published at the resolution a national synthesis
needed. Where a course is boundary-derived it sits a median **236 m** from the modern
channel.

**That 236 m is not error.** It is the historical signal: the boundary remembers where the
river was, and it is exactly the quantity a higher-resolution trace would sharpen. So the
route to a better course is **the material behind the synthesis, retraced and georeferenced
more finely than the synthesis needed** — not the synthesis resampled.

> ### Why an existing synthesis is not spliced in
>
> An earlier plan had a further phase: connect the courses carrying no map label and no
> traced replacement, so that the synthesis formed a network rather than a set of drawn
> assertions. **It is dropped**, and the reasoning is worth keeping.
>
> A boundary-derived course sits a median 236 m from the modern channel. A traced course
> sits where the ink is. Merging two geometries of different orders of accuracy means the
> reconciliation gets made **by the pipeline, silently, at every junction** — in exactly
> the places nobody is looking. Splicing a national synthesis into a traced network would
> degrade it.
>
> The synthesis keeps its two proper roles: an **index** saying where to look, and a
> **check** saying whether a trace is corroborated. Both are served by keeping it *beside*
> the network as an evidence layer rather than *in* it.
>
> This also removes the hardest unsolved problem of the scoping exercise. Holding two
> graphs over one geometry was entirely a consequence of keeping a synthesised line and the
> modern network in a single table. If it is never spliced, the problem cannot arise.

## 3 · Model the flow

Last, because it is cheap to re-run and meaningless on an unsound network. A per-cell
water balance routed over the network burned into a terrain model ([OS Terrain 50](https://www.ordnancesurvey.co.uk/products/os-terrain-50){:target="_blank"}), validated against
modern gauged flow — and reported as a **relative index of channel capacity**, never as a
reconstruction of premodern discharge.

### What the flow model is for, beyond drawing the river

**Power available at a site is flow times fall**, and both are quantities this network will
hold: a modelled discharge for every reach, and a drop along it taken from the terrain. So
the same model that says how much water moved says **where water could be made to work** —
and that is a different map from the river, with a different audience.

Two questions follow, and they belong to different centuries. **Corn**: how much grinding
capacity a district could raise, set against how many people it had to feed — the constraint
that put a mill on nearly every workable fall in medieval England. And **power for tools**:
the fall-and-flow that drove hammers, bellows, fulling stocks and finally machinery, which is
where a hydrography stops being a landscape question and becomes an industrial one.

**It is a potential surface, and must be published as one.** Three limits, stated here so
they travel with it:

- **Potential is not attestation.** A reach with power is not a reach with a mill. The
  interesting output is the *disagreement* — power that was never taken up, and mills
  standing on less fall than the model expects, which usually means a leat is doing work the
  terrain model cannot see.
- **The flow is a relative index** under a modern rainfall baseline, so the potential is
  comparative and not a figure in kilowatts.
- **A 50 m terrain model does not see a mill's head.** A weir and a leat make several metres
  of fall over a few hundred, below what the national surface resolves. The product is a
  **screening** layer that says where to look, not a site assessment.

This is also what gives the mill channels a use even if they are never dated: **some four
thousand labelled leats are a validation set** for a potential model, and a model that puts
power where the surveyors found none, or none where they found a mill, has told you something
either way.

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

---

## Where this is worked out in detail

| | |
|---|---|
| [The rebuilt landscapes](regions/) | the regions where the modern channel is worthless, and the sources that record what was there before |
| [The scale of the work](scale) | how much is bounded, how much is not, and who does it |
| [Temporality](epochs) | which dates get published, and why an epoch is a build rather than a filter |
| [Evidence](evidence) | what each source can and cannot say |
