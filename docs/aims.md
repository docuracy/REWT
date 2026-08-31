# Aims

## What this produces

A **routable river network for England and Wales**, published as a series of dated
cross-sections, with modelled flow on each and the evidence for every line carried with
it.

Routable means what it says: from any stretch you can follow the water downstream and
reach tidal water. That is not true of the modern published network, and making it true
is most of the work.

**The name is a pun on *route*, and it is meant seriously.** A river network that cannot be
traversed cannot answer the questions rivers were used for, and those questions are largely
economic: what could be moved, from where, and at what cost. River improvement in the late
seventeenth century was undertaken above all to get **coal** to towns where hauling it
overland made it ruinously dear. So [where a river ran and when it could be worked](evidence#navigation)
is an input to the history of commerce and industrialisation, and not only to the history of
landscape. Navigability is a property of a *route*; this is the only open historical river
dataset being built to carry one.

## Who it is for

- **Landscape and economic historians**, for whom river access is a variable that has
  never had a usable national dataset behind it — did navigable water shape where towns
  grew, where markets were sited, what could be moved and at what cost?
- **Archaeologists and local historians**, who need to know where a river ran before it
  was straightened.
- **Historians of industry and technology.** Flow and fall together give **water power
  potential** — where a river could have been made to grind corn, and later to drive tools.
  [What that is and is not](methodology#what-the-flow-model-is-for-beyond-drawing-the-river)
  is set out with the method; the short form is that it is a screening surface, and its most
  useful output is where it disagrees with the mills that were actually built.
- **Anyone needing a routable hydrography of England and Wales**, historical interest or
  not. The first edition is useful on its own terms — and there is currently nothing open
  that does the job.

**On that last point, because it is the reason the first edition is worth publishing at
all.** The open national product, [OS Open Rivers](https://www.ordnancesurvey.co.uk/products/os-open-rivers){:target="_blank"}, ships a topologically structured
link-and-node network and is the base this project builds on — but Ordnance Survey's own
documentation says detailed analysis is *not supported* in it and directs anyone wanting that
to a licensed product. This project's measurements agree: the topology is there and the
traversability is not. The open datasets that *are* routable at national scale are global and
**derived from elevation** — [HydroRIVERS](https://www.hydrosheds.org/products/hydrorivers){:target="_blank"} is extracted from a 15-arc-second gridded
surface — which is a hydrological model of where water would run, not a record of the
channels that are there.

**The closed products are the other way round, and this is worth stating precisely because
the opposite is often assumed.** The Environment Agency's Detailed River Network, its
successor the OS MasterMap Water Network Layer, and the [UKCEH Digital River Network](https://www.ceh.ac.uk/data/15000-watercourse-network){:target="_blank"} are
all **derived from survey**, not from a terrain model: the EA network was captured from OS
MasterMap and built into a topologically correct network with automated rules and field
survey, and the UKCEH network was digitised from OS 1:50,000 mapping and then used to *define
the flow paths in* CEH's terrain model rather than being derived from it. So the gap this
project fills is not methodological. **Good routable survey-based hydrographies of England
and Wales exist; they are licensed, and none of them is dated.**

## Two axes of publication

These are independent, and confusing them would mean publishing nothing until the
research is finished — which is to say never.

### Editions — how complete the evidence is

| | |
|---|---|
| **First** | the modern survey repaired into a working drainage network. Makes no historical claim, and ships as soon as it is sound. |
| **Second** | old courses recovered from map evidence — channels labelled as superseded, and valleys drowned by reservoirs. Bounded, countable work. |
| **Third and after** | courses recovered from documentary and cartographic research, released **incrementally**, a course at a time. This part never completes. |

### Epochs — which date is drawn

Each epoch is a **separate build**, not a filter: flow is modelled *on* the network, so
changing which channels exist changes where the water goes. Seven are proposed, each
chosen to sit *between* phases of change rather than mid-transformation:

**1086 · 1300 · 1540 · 1600 · 1700 · 1830 · 1900**

1600 is the one that matters most — the last state before the Fens and Humberhead were
rebuilt. 1900 is where the first edition starts, because a repaired modern survey should
be dated honestly as what it is.

An epoch is published **when its evidence supports it and not before**. An empty medieval
map is worse than no medieval map, because it looks like a finding.

## Publication

**A paper will announce the first edition**, which settles its timing: after the modern
network is sound, and not waiting on the documentary research behind the later ones. Venue
and collaborators are not yet decided, and this page will name them when they are rather
than before.

What the paper is *about* is decided, and it follows from [the navigation strand](evidence#navigation):
a traced, dated, routable watercourse network is an input to the economic history of
movement — what could be carried, from where, at what cost — and that is a literature with
its own established datasets and its own people. The natural collaborators are the ones
already working on transport and industrialisation, and the contribution offered to them is
the channel rather than the question.

**And it is meant to bring people in.** The paper is as much a solicitation as an
announcement. [The scale of the work](scale) sets out which strands can be finished in house
and which cannot, and the ones that cannot — the mill channels, and the regional documentary
research — need people who already know a region or a record class and will be faster at it
by an order of magnitude than anyone learning it. Contribution is wanted at both ends of
that range: a reader who can correct one stretch of river matters as much as a collaborator
who can take on a county, and [the tooling](scale#designing-for-contribution) is built so
that either arrives attached to a specific line rather than as a remark about a map.

## What this is not

- **Not a claim to have found the medieval rivers.** It is a reconstruction with its
  uncertainty attached, and the uncertainty is part of the product.
- **Not a flow reconstruction.** Modelled flow is a relative index of channel capacity
  under a *modern* rainfall baseline. Every row says so.
- **Not finished, and not intended to be.** The design assumes correction: readers can
  report an error against the specific line that is wrong, and later editions are meant
  to be fed by them.
