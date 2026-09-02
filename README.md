<img src="docs/assets/rewt-mark.svg" alt="" width="46" align="left" hspace="18">

# REWT

**Rivers of England and Wales, Temporally.**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22248272.svg)](https://doi.org/10.5281/zenodo.22248272)

<!-- THE REPOSITORY-ID BADGE POINTED AT THE WRONG RECORD, and the wrong record was the
     exact failure this project set out to avoid.

     `zenodo.org/badge/latestdoi/<repo id>` resolves to whatever the GitHub–Zenodo HOOK
     deposited, and the hook archives the source zipball and nothing else. This
     repository commits nothing acquired, derived or built, so that record holds the
     code and the curated judgements and NO RIVERS AT ALL. `.github/workflows/zenodo.yml`
     exists precisely because of this, and deposits the built network explicitly — but
     the badge went on pointing past it to the hook's record. At v0.1.0-alpha the hook
     minted 10.5281/zenodo.22238174 (one file) beside the real deposit's
     10.5281/zenodo.22238251 (seven), and the badge resolved to the former.

     So the badge now names the CONCEPT DOI of the explicit deposit directly. It always
     resolves to the newest edition, which is what a paper about the project cites; a
     result computed from a particular edition must cite that edition's VERSION DOI
     instead, or it becomes uncheckable the moment the next edition lands.

     AND THE CONCEPT ITSELF MOVED ONCE, which is the second half of the same lesson.
     The deposit script created a fresh deposition per release, so v0.1.0-alpha and
     v0.1.1-alpha got separate concept DOIs — …22238250 and …22248272 — and were two
     unrelated datasets rather than two versions of one. The badge named the first, so
     it would have gone on resolving to the first alpha for ever while claiming to
     resolve to the newest. Checking that the badge pointed at *a* concept DOI was not
     the same as checking it pointed at *the* one.

     The live lineage is …22248272, from v0.1.1-alpha onward, and every later release
     extends it with `actions/newversion`. …22238250 remains a permanent single-version
     concept holding v0.1.0-alpha alone; DOIs cannot be merged or withdrawn.

     It is a literal DOI rather than a repository id, so it needs editing if the concept
     ever changes — which is the cost of it pointing where it is supposed to. -->

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

## Identifiers

**`rewt` is a registered CURIE prefix.** It is registered at the prefix.cc registry, which
records it as `rewt` → `https://w3id.org/rewt/`, and that namespace is
**[permanent and under this project's control](https://w3id.org/rewt/)** — maintained in
[perma-id/w3id.org](https://github.com/perma-id/w3id.org/tree/master/rewt), so the
identifiers survive any move of the hosting. Identifiers are minted as CURIEs —
`rewt:basin/4385554389` — and a registered prefix is what lets a consumer expand one
without having been told how by us.

**One colon, then slashes, and it is not cosmetic.** A CURIE expands by plain concatenation
of namespace and reference, so `rewt:basin/4385554389` becomes
`https://w3id.org/rewt/basin/4385554389`, which is the shape the namespace's rules are
written for. The build first minted
`rewt:basin:4385554389`, which expands to `https://w3id.org/rewt/basin:4385554389` — a
perfectly legal URI that resolves to nothing. Both are URIs; only one is the identifier, and
the failure would have been silent and total the moment anything was serialised as JSON-LD
([DECISIONS.md](DECISIONS.md) D-044).

**What resolves today** is the namespace itself and the documentation:

| | |
|---|---|
| `https://w3id.org/rewt/` | the documentation site |
| `https://w3id.org/rewt/docs/{path}` | a documentation page |

**What is reserved and deliberately not yet routed:** `link/`, `node/`, `basin/`, `course/`,
`correction/` and `context`. The scheme is settled and written into the namespace's own
configuration, but a rule is enabled only once it has a live target to reach. **A 303 into
nothing is a worse answer than a 404**, because it looks like it worked.

**Entities are grouped by type, never by edition.** The same stretch of river must carry one
identifier across every published edition, and partitioning by edition would mint a second
identifier for a reach the moment a later edition described it again. That the *publisher's*
own identifiers are not persistent between product versions is a separate and unresolved
problem — it is why the network is frozen on one issue, and it is recorded as D-045.

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
and nothing that flows through it.
[Sources](https://docuracy.github.io/REWT/sources) lists every dataset used and the credit
it requires; [Evidence](https://docuracy.github.io/REWT/evidence) sets out the reasoning.

## Contact

Stephen Gadd, [Docuracy Ltd](https://docuracy.co.uk).
