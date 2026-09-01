# Background

## The proof of concept

REWT follows a scoping exercise carried out in 2026 under the name **Premodern Rivers**,
which produced a working reconstruction, two delivered datasets, and a map.

**It began as a commission of three or four days.** Justin Colson ([Institute of Historical Research](https://www.history.ac.uk/){:target="_blank"})
wanted a GIS of rivers for a Domesday mapping project, and proposed the obvious
construction: take [Oksanen's routes](evidence#before-1348) and splice them into the modern
[OS Open Rivers](https://www.ordnancesurvey.co.uk/products/os-open-rivers){:target="_blank"} network.

**What grew it was a cartographic decision, not a difficulty.** A national river map is
unreadable and enormous unless the smallest streams are dropped, and it is uninformative
unless a river is drawn at a width that means something — so flow had to be *computed*,
first to clip low-flow channels reliably and second to give every drawn line a width
indicative of what it carried. That is a modest requirement with an immodest consequence:
**flow is modelled on the network, so the water has to be able to move through it.** The
modern survey, it turned out, does not let it — water cannot be followed from every stretch
to the sea — and a flow model over a network the water cannot leave returns confident
numbers about nothing.

So the three or four days became the finding that
[sets the order of everything since](methodology#the-finding-that-sets-the-order): repair the
modern network first, because nothing downstream of it means anything until it is sound. The
splice itself was dropped for a separate reason — where the synthesis's courses are derived
from parish boundaries they sit a median 236 m from the modern channel, so merging them would
have reconciled two orders of accuracy silently at every junction. The project now
[declines to do the thing it was asked for](methodology#go-to-the-sources-not-to-the-synthesis),
and the reasoning behind that refusal is most of what it has to offer.

**That work is not public**, and this page is the account of it. What it established, and
what was and was not carried forward, is set out below; the regional source surveys it
produced have been rewritten for this project and are [the rebuilt landscapes](regions/).

## What it established

**That the thing is buildable.** A national network can be assembled from open sources,
dated, and modelled — and published as a map that a reader can interrogate.

**That the modern survey is the problem.** This is the finding that reorders everything.
Defect after defect turned out to be a fault in the modern network's topology rather than
historical uncertainty: rivers ending inland, whole basins draining into nodes with no
outflow, thousands of kilometres unreachable from the sea. Every one was invisible in the
national totals and obvious on the map.

**That a plausible number is the dangerous kind.** A flow model will report a confident
figure over a network in which the water cannot actually leave. Nothing in the summary
statistics says so.

**That corrections should arrive as records, not descriptions.** A tool was built to let
a reader click the line that is wrong and say what is wrong with it, so a correction
carries the identifiers rather than a description of a place. It repeatedly found in
minutes what analysis had missed for days.

## What carries over, and what does not

**To be carried over:** the approach, the hand-made judgements and their reasoning, the
tracing and correction tooling, and the source declarations. The judgements and the source
declarations are here; the tooling is rebuilt rather than copied, and is not here yet.

**Not carried over:** the pipeline's accumulated assumptions about the order of work. The
scoping exercise grew twenty-three stages in which the sequence was load-bearing and
largely undocumented, and several stages quietly overwrote each other. That is why REWT
starts from a clean sheet rather than a fork, and why reproducibility is the first phase
of work rather than an afterthought.

## Naming

The earlier work is cited as *Premodern Rivers*; its releases keep their identifiers and
remain valid. REWT is the name of the undertaking that follows it, and covers a wider
span — from Domesday to the present-day channel it is built on — than *premodern* honestly
describes.
