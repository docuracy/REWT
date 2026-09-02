"""The team board: one winner under a race, and a takeover that takes over.

`rewt/team.py` joins two things that were never joined — `ListAgents` knows session
*names* and `TEAM.md` names *roles* — so a restarted team can address each other. It
had no tests, and the property it rests on is one that is silent when it breaks:
**`O_EXCL` gives exactly one winner.** Two sessions both believing they hold the
tests role would each act as though the other's work were unowned, and nothing would
say so until the collision.

That is the shape worth testing here: not that a claim works, which is obvious the
first time anyone types it, but that a *second* claim fails. A predicate that cannot
fail is the failure this tool has already met once — D-077 records a pid liveness
check that declared every claim dead the instant it was made, a definite answer to a
question it had never measured.

Every test runs against a temp board. Nothing here touches `.team/`, so a suite run
cannot evict a live session from its role.
"""

from __future__ import annotations

import json
import multiprocessing
import time

import pytest

from rewt import team


@pytest.fixture
def board(tmp_path, monkeypatch):
    """A board of its own, so the running team is never disturbed."""
    monkeypatch.setattr(team, "DIR", tmp_path / ".team")
    return tmp_path / ".team"


def test_a_claim_is_recorded_with_who_and_when(board):
    role, was_stale = team.claim("tests", "session-one")
    assert role == "tests" and not was_stale
    held = team.read_all()
    assert held["tests"].session == "session-one"
    assert held["tests"].claimed_at, "a claim that does not say when cannot be judged"


def test_a_second_claim_on_a_held_role_is_refused(board):
    """The property the whole board rests on.

    Two sessions holding one role would each treat the other's work as unowned, and
    the filesystem is the only arbiter that does not depend on either of them asking.
    """
    team.claim("tests", "session-one")
    with pytest.raises(RuntimeError, match="claimed by session-one"):
        team.claim("tests", "session-two")
    assert team.read_all()["tests"].session == "session-one", (
        "the refused claim changed the board anyway"
    )


def test_an_unknown_role_is_refused_by_name(board):
    with pytest.raises(KeyError, match="no such role"):
        team.claim("archaeologist", "session-one")


def test_claiming_without_a_role_takes_the_first_free_one_in_startup_order(board):
    """Startup order matters: the implementer boots alone because the database is
    single-writer and five sessions racing the lock is the documented failure."""
    first, _ = team.claim(None, "session-one")
    assert first == team.ROLES[0][0]
    second, _ = team.claim(None, "session-two")
    assert second == team.ROLES[1][0]


def test_a_forced_claim_takes_the_role_over(board):
    team.claim("tests", "session-one")
    role, _ = team.claim("tests", "session-two", force=True)
    assert role == "tests"
    assert team.read_all()["tests"].session == "session-two", (
        "--force reported success and left the previous holder on the board"
    )


def test_releasing_by_session_frees_only_that_sessions_roles(board):
    """*Not by pid*, which never survives the call. A session knows its own name."""
    team.claim("implementer", "session-one")
    team.claim("tests", "session-two")
    freed = team.release(None, "session-two")
    assert freed == ["tests"]
    held = team.read_all()
    assert "tests" not in held and held["implementer"].session == "session-one"


def test_a_freed_role_can_be_claimed_again(board):
    team.claim("tests", "session-one")
    team.release("tests")
    role, was_stale = team.claim("tests", "session-two")
    assert role == "tests" and not was_stale


# --------------------------------------------------------------------------
# The race, which is the case that would be silent
# --------------------------------------------------------------------------


def _grab(directory, role, session, results, start):
    """Claim in a child process, on a signal, so the processes genuinely contend.

    The barrier is not decoration. Started in a loop without one, the first child
    can finish before the last begins, and the test then passes against a
    check-then-create implementation that is not atomic at all — a race test that
    never races. Measured: with the barrier, a deliberately non-atomic claim yields
    2 winners of 2 and 8 of 8; the harness discriminates.
    """
    import os

    from rewt import team as child_team

    child_team.DIR = directory
    start.wait(timeout=30)
    try:
        got, _ = child_team.claim(role, session)
        results.put(("won", session, os.getpid(), got))
    except Exception as exc:                      # a loser, by any route
        results.put(("lost", session, os.getpid(), type(exc).__name__))


@pytest.mark.parametrize("racers", [2, 8])
def test_exactly_one_process_wins_a_contested_role(board, racers):
    """`O_EXCL` gives one winner — demonstrated, not asserted.

    The claim is made by processes that start together and do not co-ordinate, which
    is the real case: six sessions booting after a restart, none of them aware of the
    others. Two winners here would mean two sessions each believing they owned
    `tests/`, and neither would find out.
    """
    ctx = multiprocessing.get_context("fork")
    results, start = ctx.Queue(), ctx.Event()
    board.mkdir(parents=True, exist_ok=True)
    procs = [
        ctx.Process(target=_grab, args=(board, "tests", f"session-{i}", results, start))
        for i in range(racers)
    ]
    for p in procs:
        p.start()
    time.sleep(0.2)          # every child is inside claim() before any may proceed
    start.set()
    for p in procs:
        p.join(timeout=30)

    outcomes = [results.get(timeout=5) for _ in range(racers)]
    winners = [o for o in outcomes if o[0] == "won"]
    assert len(winners) == 1, (
        f"{len(winners)} of {racers} processes claimed the same role: "
        + ", ".join(f"{o[1]}(pid {o[2]})" for o in winners)
    )

    # And the board records the winner, not the last writer.
    recorded = json.loads((board / "tests.json").read_text())
    assert recorded["session"] == winners[0][1], (
        f"the board says {recorded['session']} holds the role and "
        f"{winners[0][1]} was told it had won"
    )


def test_a_race_for_any_free_role_gives_every_process_a_different_one(board):
    """Claiming without a role should distribute, not collide.

    Six sessions starting at once with no role argument is the restart case exactly.
    """
    ctx = multiprocessing.get_context("fork")
    results, start = ctx.Queue(), ctx.Event()
    board.mkdir(parents=True, exist_ok=True)
    racers = len(team.ROLES)
    procs = [
        ctx.Process(target=_grab, args=(board, None, f"session-{i}", results, start))
        for i in range(racers)
    ]
    for p in procs:
        p.start()
    time.sleep(0.2)
    start.set()
    for p in procs:
        p.join(timeout=30)

    outcomes = [results.get(timeout=5) for _ in range(racers)]
    won = [o[3] for o in outcomes if o[0] == "won"]
    assert len(won) == len(set(won)), (
        "two processes were given the same role: " + ", ".join(sorted(won))
    )
    assert len(won) == racers, (
        f"{len(won)} of {racers} processes got a role, and there were "
        f"{racers} free"
    )
