# REWT

**Rivers of England and Wales, Temporally.**

A routable reconstruction of the river network of England and Wales at a series of dated
cross-sections between Domesday and 1900, built so that the water in it can reach the sea.

### → **[Read the introduction](https://docuracy.github.io/REWT/)**

That site covers the [aims](https://docuracy.github.io/REWT/aims),
the [methodology](https://docuracy.github.io/REWT/methodology),
the [evidence and its licensing](https://docuracy.github.io/REWT/evidence),
and the [proof-of-concept work this follows](https://docuracy.github.io/REWT/background).

---

## Status

**Nothing is published yet, and there is no code here.** The repository is being built
from a clean sheet following a scoping exercise
([Premodern Rivers](https://docuracy.github.io/premodern-rivers/)) which established the
approach and, more usefully, what goes wrong.

Material is carried across **selectively and deliberately**, so that this repository can
be made public without any licence-encumbered data having to be removed first.

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

## Licence

**Code: [MIT](LICENSE).**

Data is a separate question. Every source carries its own licence and attribution, some
of them incompatible with redistribution, and the MIT grant covers this repository's code
and nothing that flows through it. See
[Evidence](https://docuracy.github.io/REWT/evidence).

## Contact

Stephen Gadd, [Docuracy Ltd](https://docuracy.co.uk).
