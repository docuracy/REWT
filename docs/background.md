# Background

## The proof of concept

REWT follows a scoping exercise carried out in 2026 under the name **Premodern Rivers**,
which produced a working reconstruction, two delivered datasets, and a published map.

Its site remains available and is worth reading for the detail behind the summaries here:

> **[Premodern Rivers — the proof-of-concept map and documentation](https://docuracy.github.io/premodern-rivers/)**
>
> and its [methodology and status pages](https://docuracy.github.io/premodern-rivers/guide/),
> including a [next-steps analysis](https://docuracy.github.io/premodern-rivers/guide/next-steps.html)
> and regional source surveys for the
> [Fens](https://docuracy.github.io/premodern-rivers/guide/regions/fens.html),
> the [Humber](https://docuracy.github.io/premodern-rivers/guide/regions/humber.html),
> the [Somerset Levels](https://docuracy.github.io/premodern-rivers/guide/regions/somerset.html)
> and [elsewhere](https://docuracy.github.io/premodern-rivers/guide/regions/other.html).

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

**Carried over:** the approach, the hand-made judgements and their reasoning, the tracing
and correction tooling, and the source declarations.

**Not carried over:** the pipeline's accumulated assumptions about the order of work. The
scoping exercise grew twenty-three stages in which the sequence was load-bearing and
largely undocumented, and several stages quietly overwrote each other. That is why REWT
starts from a clean sheet rather than a fork, and why reproducibility is the first phase
of work rather than an afterthought.

## Naming

The earlier work is cited as *Premodern Rivers*; its releases keep their identifiers and
remain valid. REWT is the name of the undertaking that follows it, and covers a wider
span — from Domesday to 1900 — than *premodern* honestly describes.
