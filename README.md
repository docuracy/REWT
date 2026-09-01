# The `traces` branch

**Contributed tracing work, and nothing else.** This branch is written to by the tracer at
`docs/trace/`, live, as contributors work. It is not a source branch and carries no code.

    traces/<login>/<batch>.jsonl

## Why it is a branch and not a directory on `main`

GitHub Pages rebuilds on a push to `main` under `docs/**`. A contributor saving every few
minutes would fire a full site rebuild each time, queue them serially, and bury `main`'s
history under thousands of commits. The branch costs nothing and avoids both.

## Why it is an ORPHAN branch

Two reasons, and the second is the one that would have bitten.

**The tool lists this tree on every sign-in.** It asks
`git/trees/traces?recursive=1` to find a contributor's file before requesting it — one
cheap call that avoids a red 404 on a first run. Branched from `main`, that call would
return the whole repository every time a contributor signed in. With no parent it returns
the traces and this file.

**A token that can write here can write anywhere on this branch.** There is no source code
on it to write to.

## What a line is

One JSON object per **committed act** — a trace finished, revised, or withdrawn; a task
skipped as impossible; a note attached — never one per mouse movement. Append-only: the
current state is a fold over the log, ordered by `(created, author, seq, uuid)`. Events are
idempotent by `uuid`, which is what makes an offline flush and a conflict recovery the same
code path as an ordinary save.

Every line carries `reason`, `evidence`, `author` and `dated`, and **a coordinate** — a skip
has no geometry of its own and still gets a place. *Report at the place, not only in the
total.*

## Two things this branch is not

**Not the dataset.** Contributions reach the published network through
`data/curated/traces/` after validation, as diffable files in this repository's existing
idiom. Nothing here is published as it stands.

**Not a place anything is deleted.** A withdrawn trace is an event recording the
withdrawal, with its reason. Nothing is removed to correct it — the audit trail is how a
reader tells a correction from an omission.

See `tools/tracer/PLAN.md` on `main` for the design, and D-043 and D-053 in `DECISIONS.md`
for the rulings this rests on.