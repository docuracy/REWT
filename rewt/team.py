"""Who is running, and which part of the work each session owns.

**Six agents can see each other's names and cannot tell which is which.** `ListAgents`
returns session names — `rewt-fc`, `rewt-2b` — and those are new random suffixes after a
restart, while `TEAM.md` names *roles*. Nothing joined the two, so on 1-2 September the
sessions could message each other only because one of them had learnt by observation who
was who. A restarted team would have six agents that can address each other and cannot
work out who to address.

**A claim is taken, not assigned.** The alternative was a master session handing out roles,
which is worse on every axis: it makes one session a single point of failure for everyone's
identity, and an instruction arriving from a peer is not the same thing as one from the
person running the work — an agent should not take its whole remit on a message it cannot
verify. A claim in a file is a fact anybody can read, survives the claimant dying, and is
visible to the human without asking anyone.

**Claims are atomic and stale ones are reclaimable.** `O_EXCL` means two sessions racing for
the same role produce one winner and one loser rather than two holders. A claim records the
process that took it, so a session that dies does not hold its role for ever.

The directory is runtime state and is not committed: it describes this machine at this
moment, not the repository.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass

from . import paths
from .report import log

DIR = paths.ROOT / ".team"

# THE ORDER IS THE STARTUP ORDER, and the first entry is first for a reason: the
# implementer owns the database, which is single-writer, so it must be up and settled
# before anything else attaches. The rest are ordered by how much they unblock.
ROLES: list[tuple[str, str, str]] = [
    ("implementer", "rewt/, conf/, data/, db/, published/, DECISIONS.md, git on main",
     "The only session that builds or commits to main. Read PLAN.md, AGENTS.md and "
     "TEAM.md, then run `rewt release-check <tag>` and say what it reports."),
    ("visualisation", "tools/viewer/, docs/viewer/",
     "Load the deployed map. Check every figure on the panel against the audit it came "
     "from, and report what you see rather than what should be there."),
    ("tracer", "tools/tracer/, docs/trace/",
     "Read tools/tracer/PLAN.md for the phase in hand. Nothing under docs/trace/ may "
     "carry YAML front matter."),
    ("documentation", "docs/ (Jekyll, docuracy.github.io/REWT); README.md and PLAN.md on request",
     "Check every figure on /scale and /methodology against published/audit/audit.json "
     "and say which no longer hold. Do not trust a figure because another page states it."),
    ("tests", "tests/",
     "The suite caught none of the defects in DECISIONS.md D-067 to D-077 and is not "
     "small. Read those and say which are now testable."),
    # DESCRIBED AS A PERMISSION AND CALLED A ROLE, which is how it was written and what
    # was wrong with it: "writes nothing" was true and a session reading it as its job
    # would do a fraction of the work. By volume the role measures things and reads
    # published artefacts against the code that claims to produce them — both pre-DOI
    # defects came from the second, and D-067 exists because no gate here compares the
    # build to anything outside itself. Corrected by rewt-86, who did the job.
    ("sources",
     "nothing — proposes conf/sources.yml entries and DECISIONS.md text to the "
     "implementer; measures from published/ and data/raw/, NEVER the database, which "
     "the implementer holds and which blocks its build",
     "Find, vet and licence evidentiary sources; measure what they do and do not carry; "
     "and read published artefacts against the code that claims to produce them. Start "
     "by auditing conf/sources.yml against published/ATTRIBUTION.md and the live terms."),
]
BY_NAME = {r[0]: r for r in ROLES}


@dataclass
class Claim:
    role: str
    session: str
    claimed_at: str

    @property
    def age_hours(self) -> float:
        try:
            t = time.mktime(time.strptime(self.claimed_at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            return 0.0
        return (time.time() - t) / 3600.0

    # NO PID AT ALL, AND THE FIRST VERSION RECORDED ONE THAT WAS ALWAYS DEAD.
    #
    # It recorded `os.getpid()` — the pid of the CLI invocation, which exits a moment
    # later — so every claim read back as held by a dead process and every role was
    # instantly reclaimable. The check ran, returned a definite answer, and the answer
    # was always the same one: exactly D-077's shape, a predicate that cannot fail
    # reporting a state it never measured.
    #
    # There is no stable pid to record. An agent runs each command in a fresh shell, so
    # nothing on this side of the boundary outlives the call. **Liveness is a question
    # for `ListAgents`**, which knows which sessions exist, and the claim file answers a
    # different one: who said they were doing what, and when. Age is shown so a reader
    # can judge; taking a role over is explicit, because a claim that looks abandoned
    # and is not is a collision the filesystem cannot prevent.
    #
    # **The field is deleted, not merely documented as useless.** rewt-fc: a `pid` left
    # in the file with a note saying not to trust it is a loaded gun with a label on it
    # — the next person wanting a liveness check finds it already populated and uses it
    # in one line, with nothing in the diff to suggest they should not. `claimed_at`
    # carries the only part that was ever true.


def in_agent_shell() -> bool:
    """Whether this command is running inside an agent's shell or a person's terminal.

    `CLAUDECODE` is set in the first and absent in the second, which is the distinction
    the board actually needs: **a role claimed from a bare terminal is held by nobody.**
    A person typing `rewt team claim` takes a role no session is doing, and five other
    agents then see it as taken — which happened the first time Stephen typed
    `rewt team`, because the action defaulted to claim.
    """
    return bool(os.environ.get("CLAUDECODE"))


def _default_session() -> str:
    """A name for a claim that did not give one.

    **`CLAUDE_SESSION_NAME` does not exist and I invented it.** Every claim made without
    `--name` recorded the literal string "unnamed", which defeats the whole purpose of
    joining roles to sessions — and nothing said so, because "unnamed" looks like a
    reasonable value rather than a failure. Verified against the real environment rather
    than assumed a second time: what exists is `CLAUDE_CODE_SESSION_ID`, a uuid, which is
    unique and traceable and not what a peer will call you in a message.

    So the id is a fallback and `--name` is what to pass; the CLI says so.
    """
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    return f"session-{sid[:8]}" if sid else "unnamed"


def _path(role: str):
    return DIR / f"{role}.json"


def read_all() -> dict[str, Claim]:
    out: dict[str, Claim] = {}
    if not DIR.exists():
        return out
    for role, _, _ in ROLES:
        p = _path(role)
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
            out[role] = Claim(role, str(d.get("session", "?")),
                              str(d.get("claimed_at", "")))
        except (ValueError, KeyError):
            continue
    return out


def claim(role: str | None = None, session: str | None = None,
          force: bool = False) -> tuple[str, "Claim | None"]:
    """Take a role, or the first free one in startup order. Returns (role, was_stale).

    Racing sessions are settled by the filesystem: `O_EXCL` gives one winner.

    Returns the role taken and **whatever claim was displaced**, or `None` if the role
    was free. It used to return a bare `was_stale` flag, true for any forced claim — so
    the caller could not tell *I reclaimed something abandoned* from *I evicted a
    colleague*, and the CLI printed "held by a process that has gone" either way. There
    is no liveness here to know that by (see below), so the honest report is who held it
    and since when, and let the reader judge. rewt-6a, who declined to write a test
    pinning the old behaviour on the grounds that it would record what the code did
    rather than what it should.
    """
    DIR.mkdir(exist_ok=True)
    held = read_all()
    wanted = [role] if role else [r for r, _, _ in ROLES]
    for want in wanted:
        if want not in BY_NAME:
            raise KeyError(f"no such role {want!r}; known: {', '.join(BY_NAME)}")
        existing = held.get(want)
        displaced: Claim | None = None
        if existing is not None:
            # ALREADY YOURS IS SUCCESS, NOT A CRASH. Re-running the command in the same
            # session raised, and told the caller to check `ListAgents` for whether the
            # holder was still running — which is unfollowable when the holder is you:
            # you find yourself alive and there is no path. `--force` would have worked
            # and is documented as retaking a role "whose holder has gone", so following
            # the advice meant asserting something false about your own claim.
            if session and existing.session == session:
                return want, None
            if not force:
                if role:
                    raise RuntimeError(
                        f"{want} is claimed by {existing.session} "
                        f"{existing.age_hours:,.1f} h ago. Check `ListAgents` for whether "
                        f"that session is still running; if it is not, retake it with "
                        f"--force."
                    )
                continue
            _path(want).unlink(missing_ok=True)
            displaced = existing
        try:
            fd = os.open(_path(want), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            # Lost the race. With a role named there is nothing else to try, and the
            # fall-through said "every role is claimed by a live process" — false, and
            # misleading in the one situation where somebody is already unsure who holds
            # what. Two sessions forcing the same role can both unlink before either
            # creates; the loser lands here.
            if role:
                raise RuntimeError(
                    f"lost a race for {want}: another session claimed it between this "
                    "one clearing it and taking it. Run `rewt team status` — somebody "
                    "else is forcing the same role at the same moment."
                )
            continue
        with os.fdopen(fd, "w") as fh:
            json.dump({"session": session or _default_session(),
                       "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, fh)
        return want, displaced
    raise RuntimeError("every role is claimed by a live process")


def release(role: str | None = None, session: str | None = None,
            force: bool = False) -> list[str]:
    """Give back a role, by name or by the session holding it.

    **Not by pid**, which is what the first version matched on and which never survives
    the call. An agent knows its own session name, so that is the handle it has.

    **A session may not release another session's role without `--force`.** The first
    version had no ownership check at all: `release --role visualisation` deleted whoever
    held it, silently, with no confirmation — so any session could unseat any other by
    typing a name. `claim` had exactly this guard and `release` did not, which is the
    asymmetry that made it invisible. Found by rewt-2b from the code, who declined to
    demonstrate it by unseating a live session, and was saved from doing it by accident
    only because they mistyped the role and got a warning.
    """
    held = read_all()
    if role:
        c = held.get(role)
        if c is None:
            return []
        if session and c.session != session and not force:
            raise PermissionError(
                f"{role} is held by {c.session}, not by {session}. Releasing another "
                "session's role takes --force, and it is worth asking them first."
            )
        targets = [role]
    elif session:
        targets = [r for r, c in held.items() if c.session == session]
    else:
        return []
    for r in targets:
        _path(r).unlink(missing_ok=True)
    return targets


def shutdown() -> list[str]:
    """Clear every claim, for when the whole team is being stopped.

    **A stale claim is not harmful** — `status` shows its age and `--force` retakes it —
    but a directory of claims from a team that no longer exists makes the next start
    ambiguous in exactly the way this file was written to prevent. Running this once when
    the last session closes leaves the next start with a clean board.
    """
    held = read_all()
    for r in held:
        _path(r).unlink(missing_ok=True)
    return sorted(held)


def terminal_title(text: str) -> None:
    """Name the terminal tab, because PyCharm does not.

    Six sessions in six tabs all read `zsh`, and the person running them has no way to
    tell which is the tracer. The OSC 0 escape names the window and the tab.

    **Only to a real terminal, and only on stderr.** The first version printed it
    unconditionally to stdout, and an agent reading the output through a tool rather than
    a terminal got `]0;REWT · sourcesdone  you are the sources` — the ESC and BEL eaten,
    the rest jammed into the first line of the first message a restarted session ever
    sees. Harmless where it is understood and corruption everywhere else, which is the
    worst distribution: it looks perfect to the person who wrote it and wrong to every
    consumer. Found by rewt-86, who read it through a tool, which is what five of the six
    sessions do.
    """
    if not sys.stderr.isatty():
        return
    print(f"\033]0;{text}\007", end="", file=sys.stderr, flush=True)
