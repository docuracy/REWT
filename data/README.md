# data/

**Nothing here is committed except declarations and hand-authored judgements.**

`raw/` holds immutable downloads, identified by checksum, and is gitignored — the build
fetches them from the declarations in `conf/sources.yml`. `interim/` and any database are
build artefacts and are gitignored too: deleting them loses nothing, because they can be
rebuilt from the raw inputs and the code.

`curated/` will hold human judgements — decisions about particular rivers, each in a
diffable file with its evidence and its reason. **It is empty, deliberately.**

## Why nothing has been carried over from the earlier work

A scoping exercise accumulated a substantial set of curated topology corrections:
connectors where the survey draws no channel, reversals where it draws one the wrong way
round, junctions where two channels meet with no node between them. They are real
judgements, checked at the place by a person, and they are **not here**.

Two reasons. They were made against that build's own graph, and importing them would seed
a clean sheet with another pipeline's assumptions — including the ones this rebuild exists
to leave behind. And more importantly, **Stage 1 has to build an audit that can find such
defects on its own**. An audit handed the answers is not an audit.

They remain available in the predecessor repository as a **validation set**, to be
consulted *after* the audit works and never as an input to it. If the audit independently
finds what a person found by looking, both are corroborated. If it does not, that is the
more interesting result and it is worth knowing.
