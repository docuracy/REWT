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
     "The suite has 227 tests and caught none of the defects in DECISIONS.md D-067 to "
     "D-077. Read those and say which are now testable."),
    ("sources", "nothing — proposes conf/sources.yml and decision text to the implementer",
     "Audit conf/sources.yml against published/ATTRIBUTION.md and the live licence "
     "terms, and propose corrections."),
]
BY_NAME = {r[0]: r for r in ROLES}


@dataclass
class Claim:
    role: str
    pid: int
    session: str
    claimed_at: str

    @property
    def age_hours(self) -> float:
        try:
            t = time.mktime(time.strptime(self.claimed_at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            return 0.0
        return (time.time() - t) / 3600.0

    # NO PID LIVENESS CHECK, AND THE FIRST VERSION HAD ONE THAT WAS ALWAYS FALSE.
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
            out[role] = Claim(role, int(d["pid"]), str(d.get("session", "?")),
                              str(d.get("claimed_at", "")))
        except (ValueError, KeyError):
            continue
    return out


def claim(role: str | None = None, session: str | None = None,
          force: bool = False) -> tuple[str, bool]:
    """Take a role, or the first free one in startup order. Returns (role, was_stale).

    Racing sessions are settled by the filesystem: `O_EXCL` gives one winner. A claim
    whose process has gone is cleared and retaken, and the caller is told, because a
    role that was held five minutes ago and is free now is worth a second look.
    """
    DIR.mkdir(exist_ok=True)
    held = read_all()
    wanted = [role] if role else [r for r, _, _ in ROLES]
    for want in wanted:
        if want not in BY_NAME:
            raise KeyError(f"no such role {want!r}; known: {', '.join(BY_NAME)}")
        existing = held.get(want)
        stale = False
        if existing is not None:
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
            stale = True
        try:
            fd = os.open(_path(want), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue          # lost the race; try the next role
        with os.fdopen(fd, "w") as fh:
            json.dump({"pid": os.getpid(), "session": session or os.environ.get(
                "CLAUDE_SESSION_NAME", "unnamed"),
                "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, fh)
        return want, stale
    raise RuntimeError("every role is claimed by a live process")


def release(role: str | None = None, session: str | None = None) -> list[str]:
    """Give back a role, by name or by the session holding it.

    **Not by pid**, which is what the first version matched on and which never survives
    the call. An agent knows its own session name, so that is the handle it has.
    """
    held = read_all()
    targets = []
    if role:
        targets = [role] if role in held else []
    elif session:
        targets = [r for r, c in held.items() if c.session == session]
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
    tell which is the tracer. The OSC 0 escape names the window and the tab, and is
    ignored harmlessly where it is not understood — so it costs nothing to send.
    """
    print(f"\033]0;{text}\007", end="", flush=True)
