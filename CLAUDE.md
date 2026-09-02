# CLAUDE.md

See **[AGENTS.md](AGENTS.md)** for the working conventions, and **[PLAN.md](PLAN.md)** for
the specification. Read `PLAN.md` first.

**If you are the only session running, read [TEAM.md](TEAM.md) before doing anything else.**
Six agents worked this repository in parallel; TEAM.md is how to restart them — the six
scopes, what to tell each at startup, and the standing orders that made them catch each
other's mistakes. Start the implementer alone first: the database is single-writer, and five
sessions booting at once race the lock.

Three things that override any default behaviour:

1. **Stage 1 only.** If a task requires knowing what year it is, it is not Stage 1.
2. **Run from the repository root.** Paths in code are relative.
3. **This repository is intended to become public.** Nothing licence-encumbered may be
   committed or exported.
