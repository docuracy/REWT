"""Stage: run the build's own tests, as part of the build.

AGENTS.md is specific about this, and it is not satisfied by a test suite that exists:
**every identifier in `data/curated/` is validated against the database by a test that
runs in the build.** A mistyped id does nothing while the stage reports success; that
happened twice in the predecessor, once through a column nothing read, so the error was
invisible. And PLAN.md §2: *if a step only runs when a person remembers to run it, it
is not part of the build.*

So the suite is a stage, it runs last, and a failure fails the build.

It runs **in this process**, deliberately. A read-only DuckDB connection blocks writers
and a subprocess would deadlock against the connection the build is already holding; in
process, a test asking for the connection gets the one that is already open.
"""

from __future__ import annotations

from .. import paths
from ..pipeline import PIPELINE, StageError
from ..report import log


@PIPELINE.stage(
    "check",
    "run the build's own tests; a failure fails the build",
    reads=["link", "node", "correction", "edge"],
    writes=[],
    always=True,
)
def run() -> dict:
    tests = paths.ROOT / "tests"
    if not tests.is_dir():
        raise StageError(
            "tests/ does not exist. AGENTS.md requires that every identifier in "
            "data/curated/ is validated against the database by a test that runs in "
            "the build. An absent suite is a failure, not a skip — otherwise the "
            "guarantee is that nothing is checked."
        )

    import pytest

    log.info(f"  pytest {paths.rel(tests)}")
    tally = _Tally()
    code = pytest.main(["-q", "--no-header", str(tests)], plugins=[tally])
    if code != 0:
        raise StageError(
            f"the build's own tests failed (pytest exit {code}). The findings above "
            "are the build's, not a separate concern to be looked at later."
        )

    # A suite that skips its way to green is a silent pass, and pytest returns 0 for
    # it. Inside a finished build that would report the curated identifiers as
    # validated when nothing looked at them — which is the precise failure AGENTS.md
    # describes: "a mistyped id does nothing while the stage reports success". So the
    # exit code is not the test; having actually run something is.
    if tally.passed == 0:
        raise StageError(
            f"the build's tests passed nothing: {tally.skipped} skipped, "
            f"{tally.passed} passed. pytest returned 0, and that is exactly the "
            "signal not to trust — a suite that skips its way to green reports "
            "checks that nobody performed."
        )
    log.detail(
        f"    {tally.passed:,} passed, {tally.skipped:,} skipped"
        + (f", {tally.failed:,} failed" if tally.failed else "")
    )
    if tally.skipped:
        for reason in tally.skip_reasons[:10]:
            log.detail(f"      skipped: {reason}")
    return {"pytest": int(code), "passed": tally.passed, "skipped": tally.skipped}


class _Tally:
    """Counts what actually ran, because an exit code does not say."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.skip_reasons: list[str] = []

    def pytest_runtest_logreport(self, report) -> None:
        if report.when != "call" and not (report.when == "setup" and report.skipped):
            return
        if report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1
        elif report.skipped:
            self.skipped += 1
            reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else ""
            reason = str(reason).replace("Skipped: ", "").strip()
            if reason and reason not in self.skip_reasons:
                self.skip_reasons.append(reason)
