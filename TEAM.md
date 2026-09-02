# TEAM.md

**How to start the other agents, and what each one owns.**

Read this if you are the only session running. `PLAN.md` is what to build; `AGENTS.md` is
how to work; this is who does which part and how they keep each other honest.

# TEAM.md

**How to start the other agents, and what each one owns.**

Six agents worked this repository in parallel on 1–2 September 2026 and the arrangement was
effective — but **its value was not the parallelism**. Every serious defect found in those two
days was found by one agent reading an artefact another had produced. None by the build, and the suite is not small. The division of labour is what made that possible; the cross-reading is what did
the work. **If you restart the team, restart both.**

**Read this first if you are the only session running.** Six agents worked this repository
in parallel and the arrangement was effective, but its value was not the parallelism. Every
serious defect found on 1–2 September was found by **one agent reading an artefact another
had produced** — none by the build, which and the suite is not small. The division of labour is what made
that possible; the cross-reading is what did the work. If you restart the team, restart both.

### Starting: the whole procedure

**Open six terminals and run `rewt team claim` in each.** That is the whole of it. Roles are
taken in the order below, so the first is the implementer; each session is told what it owns
and what to do first, and is told what it owns. **The role is printed on stdout**, so
`role=$(rewt team claim)` works.

**It cannot name the terminal tab, and an earlier version claimed it could.** An agent runs
each command through a tool that captures both streams, so a terminal escape never reaches
a terminal, and `/dev/tty` is not available to it either. PyCharm's six identical tabs are a
real problem and this is not the solution to it.

    rewt team                  # who holds what, and the other commands. Changes nothing.
    rewt team claim            # take the next free role
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

**Claim from the agent's session, not from a bare terminal.** The command can tell the
difference — `CLAUDECODE` is set in one and not the other — and refuses in a terminal,
because a role claimed by a person is held by nobody while five other sessions read it as
taken. **Pass `--name` with the name `ListAgents` shows for you**: there is no environment
variable carrying it, so without one the claim records a session id, which is unique and
traceable and not what a peer will call you in a message.

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

**An agent that opens a port owns closing it.** Servers outlive the session that started
them, and nothing this team built would tell you: the board tracks intent, `git status` stays
clean while a process serves `.env`, and `rewt team shutdown` knows nothing about sockets.
Two sessions each left one running and neither believed they had. **Two rules, because we
each broke a different one** — one server was rooted at the repository, the other ran for
twenty-three hours; a third pair, on this machine but from another project, was bound to
every interface for four days. Anyone writing down only the half that had bitten them would
have missed the rest:

- **Serve `docs/`, never the repository root.** `python3 -m http.server PORT --directory docs`.
  If a viewer needs something outside `docs/`, copy it in or fix the build; do not widen the
  server's root to reach it.
- **Bind to `127.0.0.1`.** The default is `0.0.0.0`, which is every interface on the network
  and not merely this machine. `--bind 127.0.0.1` is not the default and has to be typed.

Check before you close: `ss -ltnp | grep python` names the port, the bind address and the
pid, and `readlink /proc/PID/cwd` says what it is serving. A port you cannot account for
belongs to somebody — ask on the board before killing it.

### The six scopes

**The scopes live in `rewt/team.py` and nowhere else.** They were also written out here, by
hand, and the two had drifted apart within an hour of both being written — this file still
described the `sources` role as *"writes nothing; proposes conf/sources.yml and decision
text"* after the session that does the job had corrected it to something twice as long and
materially different. Two renderings of one fact, drifting, in the file that records why
that is dangerous (D-067).

So there is one copy, and it is the one the tool reads out to each session as it claims:

    rewt team status      # all six, with who holds what
    rewt team claim       # your own, printed to you at the moment you take it

Ownership is by directory and it is hard. **A session that needs a change outside its scope
asks the owner** rather than editing — including for a one-line fix, because the owner knows
what else reads it. Only the implementer builds, and only the implementer commits to `main`;
others commit within their own scope.

**Nothing but the implementer opens the database.** DuckDB is single-writer and a read-only
connection blocks writers, so anything else attaching fails the build — and the failure looks
like a broken build rather than a lock. Everything an analysis needs is in `published/` and
`data/raw/`, which are files, take no lock, and are rewritten often enough that a
long-running reader must notice when they change underneath.

### An opening prompt for each

Paste one of these, adjusting the tag. **Each names a scope and something to go and look at**
— an agent given "continue where you left off" reads its own past work and agrees with it.

- **implementer** — *"You own `rewt/`, `conf/`, `data/`, `db/`, `published/`, `DECISIONS.md`
  and git on main. You are the only session that builds or commits to main. Read PLAN.md,
  AGENTS.md and TEAM.md, then `rewt release-check <tag>` and tell me what it says."*
- **documentation** — *"You own `docs/`, the Jekyll site at docuracy.github.io/REWT. Check
  every figure on /scale and /methodology against `published/audit/audit.json` and tell me
  which no longer hold. Do not trust a figure because another page states it."*
- **tests** — *"You own `tests/`. The suite and the suite is not small and did not catch any of the seven
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
Give them at the start.

**Why six sessions and not one.** A session checking its own work re-runs its own
assumptions and obtains agreement, which is D-067 committed against yourself. Six sessions
produce *disagreements*, and a disagreement is the only thing that reliably makes somebody go
and look. Nearly every finding in D-065–D-078 began as two accounts that did not match. The
corollary is a duty rather than a courtesy: **contradict a peer plainly, and take a
contradiction plainly** — the session that accepts a flattering account of its own care has
removed the only mechanism the arrangement has.

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
- **Never truncate a check whose question is "is there anything else".** A `head` on an
  exploratory listing is a convenience; on a completeness check it is a bug, and a quiet one,
  because the thing you were looking for lands in the visible rows often enough to make the
  output look whole. This was found on the last afternoon: a session reported the machine's
  listening sockets from `ss -lntp | head -8`, of twenty-five. The two that mattered to the
  conversation were inside the eight. A third, network-bound and four days old, was not.
- **Unknown must fail towards the visible fault** (D-077). A thing that draws wrongly gets
  reported; a thing that quietly removes itself does not.
- **Agreement is not correctness unless something anchors it outside the set** (D-067).
  Two artefacts made by one process agree perfectly while both are wrong.
- **A rule may be written wider than the incident, but only if you can go and look.** The
  ports rule below has two halves and this team only broke one; the other half caught two
  servers nobody knew about. That was not foresight — `0.0.0.0` is the *default*, so the
  hazard was already universal on the machine and merely unlooked-for. The test that
  separates a justified widening from a guess in the same clothes is cheap and immediate:
  **can you search for instances of the wider rule right now?** If you can, do, and the
  count settles it. If you cannot, you are writing down a feeling.

### Ask for the command, not the number

**When another session reports a figure, ask how it was derived and re-derive it.** This was
the single most productive habit of the two days and it is not obvious — the natural response
to a colleague's table is to use it. Nearly every error the six sessions caught was caught
this way, and several were caught by somebody re-deriving with a **different** method, which
is stronger than re-running the same one: the same method repeats the same mistake, a
different one has to agree by accident.

rewt-86, whose role is largely this: *a peer who cannot say where their own number is
recorded has told you what you needed to know.*

### Passing figures between sessions

**State your numbers in handover messages** — but the receiver must treat them as *a test to
hold their own output against*, never as evidence. The same sentence is worth everything or
nothing depending on which it is: a figure accepted as a claim propagated a fabrication
through three sessions in a day, and a figure used as a check caught a false headline on the
public site within minutes.
