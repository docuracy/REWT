<img src="docs/assets/rewt-mark.svg" alt="" width="46" align="left" hspace="18">

# REWT

**Rivers of England and Wales, Temporally.**

A routable reconstruction of the river network of England and Wales, built so that the
water in it can reach the sea, and worked backwards from the present-day channel to a
series of dated cross-sections between Domesday and 1900.

**The baseline is modern, not Victorian.** Everything rests on OS Open Rivers, which is
reissued twice a year and describes the network as it is now — the build in this
repository is running against the **April 2026 issue**. The first deliverable is that
modern network made traversable, and it makes no historical claim at all; the dated
cross-sections are reconstructed backwards from it, and 1900 is the earliest date the
*map* record reaches, not the latest date the dataset covers.

### → **[Read the introduction](https://docuracy.github.io/REWT/)**

That site covers the [aims](https://docuracy.github.io/REWT/aims),
the [methodology](https://docuracy.github.io/REWT/methodology),
the [evidence and its licensing](https://docuracy.github.io/REWT/evidence),
and the [proof-of-concept work this follows](https://docuracy.github.io/REWT/background).

---

## Where to start

**[PLAN.md](PLAN.md) — Stage 1: a traversable modern network.** The specification.
Scoped to one thing and written to be picked up cold.

**[DECISIONS.md](DECISIONS.md) — why the build is the way it is.** Every judgement that
could reasonably have gone the other way, with what it cost. Several entries record
mistakes rather than choices, because a decision log that only holds the good calls is
a sales document.

**`published/`** — the deliverable, produced by the build and committed nowhere. The
network, the corrections as their own file so the difference from the survey can be
opened, the audit, and every source's required attribution statement in full.

## Running it

```
rewt build          # empty checkout to published outputs, one command
rewt release-check  # refuse a release that is stale, dirty, or not green
```

The build fetches its own inputs, records what it fetched, and fails if an input has
moved under a pin. It is deliberately coarse about caching: touching a module that many
stages import rebuilds nearly everything, because an unnecessary rebuild costs an hour
and a cached artefact built by code that no longer exists costs the reproducibility
guarantee silently.

## Status

**Stage 1 is built.** A traversable modern network for England and Wales, reproducible
from an empty checkout by one command, with 208 tests running inside the build and
failing it.

At the current edition, **93.80% of the in-scope network can reach tidal water** — and
the remaining **6,552 km cannot**, which is the honest measure of what Stage 1 has not
finished. That remainder is named per place rather than summarised: the audit lists
every dead end, ranked by the length actually stranded above it.

**The sea is now a test rather than a definition.** A network over the water itself —
one connected structure of 4,183 routes around the coast, derived from bathymetry
rather than drawn — lets a river mouth be shown to connect, or shown not to. **Both
readings are published side by side, deliberately.** *Reaches tidal water* is true by
construction; *reaches tidal water that reaches the sea* is a test a mouth can fail.
The second is currently an upper bound with a known discontinuity and **is not
independent confirmation of the first** — the reasoning is in
[DECISIONS.md](DECISIONS.md) D-061, and a reader who treats the two as agreeing has
been misled by a true statement.

**Figures move between editions; the audit is the authority.** Every number above comes
from `published/audit/audit.md`, which the build regenerates. Nothing here is typed by
hand into a release.

**The network is frozen on the OS Open Rivers 2026-04 issue and will not take
reissues.** OS states that its identifiers are not persistent between product versions,
so stability is bought by refusing updates rather than by minting our own, and the build
fails if the input moves. The cost is real: no correction OS makes reaches this network
until the pin is moved deliberately.

**Nothing here makes a historical claim.** The dated cross-sections are later stages.
Stage 1 is the present-day channel and the machinery for correcting it.

Material from the private scoping exercise (*Premodern Rivers*) is carried across
**selectively and deliberately**, under exemptions recorded one at a time.

## Repository conventions

Written down here because they are the ones easiest to get wrong, and each exists because
its absence cost something.

- **The build must reproduce.** One command from an empty checkout to the published
  outputs, same result every time. Immutable checksummed inputs; every stage idempotent;
  no cached intermediate preferred to the configuration that produced it.
- **Nothing licence-encumbered reaches a published artefact.** The exporter refuses to
  write a feature whose source is not openly licensed. That check is not a formality and
  must not be worked around.
- **Every source is declared before anything reads it**, with its licence and
  attribution. An unregistered source is a hard error.
- **Human judgements live in diffable files** under version control, each with its
  evidence and its reason — never hard-coded.
- **Nothing is deleted to correct it.** A superseded line is retired with its reason.
- **Fail loudly.** Unmatched inputs, topology errors and unresolved identifiers are
  reported, never silently repaired. The interesting findings live in those reports.

## Releases and citation

Editions are published as GitHub releases and deposited to
[Zenodo](https://zenodo.org), which mints a DOI for each. The deposit carries **the
built network as well as the source**, because a DOI that resolves to a river project
containing no rivers is worse than no DOI at all.

Zenodo mints two kinds. The **concept DOI** always resolves to the newest edition and
is what a paper about the project cites. **A result computed from a particular edition
must cite that edition's version DOI** — the concept DOI makes the figure uncheckable
the moment the next edition lands, and the figures do move between editions.

Release notes are generated from `published/audit/`, never written by hand. A note that
quotes a figure from memory is right once and wrong at the next edition, and reads as
authoritative in both states.

## Licence

**Code: [MIT](LICENSE).**

Data is a separate question. Every source carries its own licence and attribution, some
of them incompatible with redistribution, and the MIT grant covers this repository's code
and nothing that flows through it. See
[Evidence](https://docuracy.github.io/REWT/evidence).

## Contact

Stephen Gadd, [Docuracy Ltd](https://docuracy.co.uk).
