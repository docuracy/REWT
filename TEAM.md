# TEAM.md

**How to start the other agents, and what each one owns.**

Read this if you are the only session running. `PLAN.md` is what to build; `AGENTS.md` is how
to work; this is who does which part and how they keep each other honest.

Six agents worked this repository in parallel on 1–2 September 2026 and the arrangement was
effective — but **its value was not the parallelism**. Every serious defect found in those two
days was found by one agent reading an artefact another had produced. None by the build, which
has 227 tests. The division of labour is what made that possible; the cross-reading is what did
the work. **If you restart the team, restart both.**

**Read this first if you are the only session running.** Six agents worked this repository
in parallel and the arrangement was effective, but its value was not the parallelism. Every
serious defect found on 1–2 September was found by **one agent reading an artefact another
had produced** — none by the build, which has 227 tests. The division of labour is what made
that possible; the cross-reading is what did the work. If you restart the team, restart both.

### Starting: the whole procedure

**Open six terminals and run `rewt team claim` in each.** That is the whole of it. Roles are
taken in the order below, so the first is the implementer; each session is told what it owns
and what to do first, and **names its own terminal tab** — PyCharm gives six tabs that all
read `zsh`, and the escape sequence fixes that at no cost.

    rewt team claim            # take the next free role
    rewt team status           # who holds what, and for how long
    rewt team release --name X # give a role back
    rewt team shutdown         # clear the board when stopping the team

`rewt` is `bin/rewt`, a wrapper — the project is deliberately not installed, because
`AGENTS.md` requires it to run from the repository root and an installed console script
invites running it from anywhere and finding nothing. **To make `rewt` typeable, permanently, link it into a directory already on your PATH:**

    ln -s ~/PycharmProjects/REWT/bin/rewt ~/.local/bin/rewt

A symlink, so it always runs the current script. `~/.local/bin` is on PATH by default on
most Linux desktops — check with `echo $PATH` before assuming.

`export PATH="$PWD/bin:$PATH"` works **for that terminal only**, and must not go in
`~/.bashrc`: `$PWD` expands when the shell starts, so it would silently put the wrong
directory on PATH and never find the command. Use an absolute path or the symlink.

Until either is done, it is `./bin/rewt`.

**Sessions find each other with `ListAgents`, which returns session names — not roles.**
Those names change at every restart, so `rewt team status` is the join between the two: it
says which live session is the tracer. Without it six agents can address each other and
cannot work out who to address, which is how the arrangement fails silently rather than
loudly.

**Nobody hands out roles.** A master session assigning them would make one session a single
point of failure for everyone's identity, and an instruction arriving from a peer is not the
same thing as one from the person running the work — an agent should not take its whole
remit from a message it cannot verify. A claim is a fact in a file that anyone can read.

**Claims do not expire, and that is deliberate.** There is no stable process to watch: an
agent runs each command in a fresh shell, so nothing outlives the call. The first version of
this checked a pid and reported every claim dead the instant it was made — a predicate that
could not fail, returning a definite answer it had never measured (D-077, again). So the file
records who said they were doing what and when; **liveness is `ListAgents`'s question**, and
taking a role over is explicit with `--force`.

### Stopping

**Run `rewt team shutdown` before closing the last session.** A stale claim is not harmful —
`status` shows its age and `--force` retakes it — but a board of claims from a team that no
longer exists makes the next start ambiguous in exactly the way this file exists to prevent.

### The six scopes

Ownership is by directory and is hard. A session that needs a change outside its scope
**asks the owner** rather than editing — including for a one-line fix, because the owner
knows what else reads it.

| session | owns | never touches |
|---|---|---|
| **implementer** | `rewt/**`, `conf/**`, `data/**`, `db/**`, `published/**`, `DECISIONS.md`, git on `main` | `docs/**`, `tools/**`, `tests/**` |
| **documentation** | `docs/**` (Jekyll, live at docuracy.github.io/REWT); edits `README.md` and `PLAN.md` on request | anything under `rewt/` |
| **tests** | `tests/**` | the code under test |
| **sources** | writes nothing; proposes `conf/sources.yml` and decision text to the implementer | the repository |
| **visualisation** | `tools/viewer/**`, `docs/viewer/**` | the pipeline |
| **tracer** | `tools/tracer/**`, `docs/trace/**` | the pipeline |

**Only the implementer builds, and only the implementer commits to `main`.** Others commit
within their own scope. Nothing but the implementer opens the database: everything a viewer
or an analysis needs is in `published/`, which is a file, takes no lock, and is rewritten
often enough that a long-running reader must notice when it changes underneath.

### An opening prompt for each

Paste one of these, adjusting the tag. **Each names a scope and something to go and look at**
— an agent given "continue where you left off" reads its own past work and agrees with it.

- **implementer** — *"You own `rewt/`, `conf/`, `data/`, `db/`, `published/`, `DECISIONS.md`
  and git on main. You are the only session that builds or commits to main. Read PLAN.md,
  AGENTS.md and TEAM.md, then `rewt release-check <tag>` and tell me what it says."*
- **documentation** — *"You own `docs/`, the Jekyll site at docuracy.github.io/REWT. Check
  every figure on /scale and /methodology against `published/audit/audit.json` and tell me
  which no longer hold. Do not trust a figure because another page states it."*
- **tests** — *"You own `tests/`. The suite has 227 tests and did not catch any of the seven
  defects in DECISIONS.md D-067 to D-077. Read those and tell me which are now testable."*
- **sources** — *"You write nothing. Audit `conf/sources.yml` against `published/ATTRIBUTION.md`
  and the live licence terms, and propose corrections to the implementer."*
- **visualisation** — *"You own `tools/viewer/` and `docs/viewer/`. Load the deployed map,
  check every figure on the panel against the audit it came from, and report what you see
  rather than what should be there."*
- **tracer** — *"You own `tools/tracer/` and `docs/trace/`. Read tools/tracer/PLAN.md for the
  phase you are on. Nothing under `docs/trace/` may carry YAML front matter."*

**State the current tag, and say that `DECISIONS.md` from D-067 onward is the handover.**
Those entries are all about how this repository fools people who are being careful, which is
the thing an arriving session cannot infer from the code.

### The standing orders that made the cross-reading work

These are decisions, but a session that has to discover them has already shipped the mistake.
Give them at the start:

- **A figure with no file behind it is a rumour** (D-076). Before relaying another agent's
  measurement, find where it is recorded. **Where it names a source, ask that source** — one
  message settles it, and an agent that cannot say where its own number is recorded has told
  you what you needed to know.
- **A near miss is the signature of invention, not a mitigation.** Two fabricated figures in
  one day each landed within one point of the truth, because a mind reaching for a number
  reaches for a plausible one. *It was nearly right* means the check failed silently.
- **Before believing a selector, confirm it excludes something** (D-070). Print what it
  matches against the population. `517 of 517` says it at once; a plausible percentage does
  not.
- **Before believing an aggregate, ask it to name a row** (D-074). A count implies an
  enumeration it may no longer have.
- **Unknown must fail towards the visible fault** (D-077). A thing that draws wrongly gets
  reported; a thing that quietly removes itself does not.
- **Agreement is not correctness unless something anchors it outside the set** (D-067).
  Two artefacts made by one process agree perfectly while both are wrong.

### Passing figures between sessions

**State your numbers in handover messages** — but the receiver must treat them as *a test to
hold their own output against*, never as evidence. The same sentence is worth everything or
nothing depending on which it is: a figure accepted as a claim propagated a fabrication
through three sessions in a day, and a figure used as a check caught a false headline on the
public site within minutes.
