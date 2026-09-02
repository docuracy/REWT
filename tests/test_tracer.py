"""The tracer's identifiers, and the restriction that keeps them honest.

`tools/tracer/check_ids.py` already checks three things well. This file exists for
two reasons that are not about redoing them.

**First, so they run in the build.** *If a step only runs when a person remembers to
run it, it is not part of the build* (AGENTS.md). A command with no arguments that
exits non-zero is the right shape and the wrong trigger; wrapping it here means it
runs whenever anything else does.

**Second, to make an absence into a check.** The tracer deliberately mints no
identifier for geometry, because `rewt/ids.py` digests coordinates rounded to three
decimal places — a millimetre in EPSG:27700 and **about 111 metres in the CRS84 the
browser works in**. An id minted there would digest two courses a hundred metres
apart to the same string, would never agree with Python's id for the same feature,
and would report nothing: well-formed, unique-looking, wrong.

That restriction is currently a comment and an absence. This repository has spent
today learning what reading does with absences — a guard that refused the one raster
it existed to permit because "conditioned" is a substring of "unconditioned", and a
documented claim resting on the word "Reservoir" never appearing in a lake link name.
An absence that matters should fail loudly when it ends.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

import pytest

from rewt import paths

TRACER = paths.ROOT / "tools" / "tracer"
BROWSER_JS = paths.ROOT / "docs" / "trace" / "js"


def _js_files():
    return sorted(BROWSER_JS.glob("*.js")) if BROWSER_JS.is_dir() else []


def test_the_tracers_identifier_checks_run_in_the_build():
    """Freshness, parity and shape, wrapped so nobody has to remember them.

    The script is the authority on what it checks; this only ensures it is asked.
    Its output is surfaced on failure, so a failure here reads the same as running
    it by hand.
    """
    script = TRACER / "check_ids.py"
    if not script.exists():
        pytest.skip(
            f"{paths.rel(script)} does not exist; the tracer has not been built yet"
        )
    if shutil.which("node") is None:
        pytest.skip(
            "node is not installed, so the Python/JavaScript parity check cannot "
            "run. This is a gap in the check, not a passing check."
        )
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=paths.ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"{paths.rel(script)} exited {result.returncode}:\n"
        + (result.stdout or "") + (result.stderr or "")
    )


# A content digest in the browser is the thing that must not appear. `randomUUID`
# is not one — it digests nothing and identifies an event rather than a geometry —
# so it is named as permitted rather than caught and argued about later.
_DIGEST = re.compile(
    r"crypto\s*\.\s*subtle|\.digest\s*\(|\bcreateHash\b|"
    r"""from\s*['"]node:crypto|require\s*\(\s*['"]crypto|"""
    r"\b(?:sha1|sha256|sha512|md5|murmur|fnv1a)\b",
    re.IGNORECASE,
)
_PERMITTED = re.compile(r"crypto\s*\.\s*randomUUID")


def _code_lines(text: str):
    """Lines with comments removed, so prose explaining the absence is not the thing
    that trips the check on it."""
    in_block = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw
        if in_block:
            if "*/" in line:
                line, in_block = line.split("*/", 1)[1], False
            else:
                continue
        if "/*" in line:
            head, rest = line.split("/*", 1)
            if "*/" in rest:
                line = head + rest.split("*/", 1)[1]
            else:
                line, in_block = head, True
        line = line.split("//", 1)[0]
        if line.strip():
            yield lineno, line


def test_the_browser_mints_no_identifier_for_geometry():
    """*A trace carries its geometry; the ingest reprojects and mints.*

    Three decimal places is a millimetre in EPSG:27700 and about 111 metres in
    CRS84. A digest of rounded CRS84 coordinates would collide two distinct courses
    and agree with Python about nothing, while looking exactly like an identifier.
    That is `basin-unanchored` again, with a coordinate where the separator was.

    So no content digest may appear in the browser code at all. If one is ever
    wanted, the decision to reproject before digesting has to be made deliberately
    and written down — which is what this failing will prompt.
    """
    files = _js_files()
    if not files:
        pytest.skip(f"{paths.rel(BROWSER_JS)} holds no JavaScript yet")
    offenders = []
    for path in files:
        for lineno, line in _code_lines(path.read_text(encoding="utf-8")):
            if _DIGEST.search(line) and not _PERMITTED.search(line):
                offenders.append(f"{paths.rel(path)}:{lineno}: {line.strip()[:90]}")
    assert not offenders, (
        "the browser composes a content digest:\n  " + "\n  ".join(offenders)
        + "\nAn identifier minted from CRS84 coordinates rounded to three decimal "
        "places is wrong by about 111 metres and looks entirely well-formed."
    )


# An identifier is *composed*. In Python that means an f-string, which is why
# D-051's grep looks for `f"rewt:` and not for the prefix on its own; the JavaScript
# equivalent is a template literal with a substitution in it, or a concatenation.
#
# The distinction is not pedantry, it is the difference between a rule and a false
# positive: `{ 'rewt:supersedes': supersedes }` in anno.js is a **JSON-LD property
# name** — a term in a vocabulary, the key of a key/value pair — and nothing about
# it identifies a feature. Matching presence rather than composition caught it, and
# a test that cries wolf about a correct line is one people learn to ignore.
_MINTING = re.compile(
    r"`[^`]*\b(?:os|rewt):[^`]*\$\{"                 # `os:link/${id}`
    r"""|['"][^'"]*\b(?:os|rewt):[^'"]*['"]\s*\+"""   # 'rewt:node/' + h
    r"""|\+\s*['"]\s*(?:os|rewt):"""                  # h + 'rewt:node/'
)


def test_the_browser_composes_no_identifier_outside_its_own_module():
    """D-051's grep, pointed at the browser, and held here as well as in the script.

    `check_ids.py` checks this too. It is repeated rather than delegated because
    this one runs in the build, and because the rule has already caught a live bug
    in the Python that reading had missed twice.

    **A vocabulary term is not an identifier**, so this matches composition and not
    presence. Whether the JSON-LD vocabulary should itself have one owner is a real
    question — a term invented in one module and misspelled in another fails as
    silently as an identifier does — but it is a different rule and wants its own
    test and its own sentence rather than being smuggled in as this one.
    """
    files = [p for p in _js_files() if p.name != "ids.js"]
    if not files:
        pytest.skip(f"{paths.rel(BROWSER_JS)} holds no module but ids.js")
    offenders = [
        f"{paths.rel(path)}:{lineno}: {line.strip()[:90]}"
        for path in files
        for lineno, line in _code_lines(path.read_text(encoding="utf-8"))
        if _MINTING.search(line)
    ]
    assert not offenders, (
        "identifiers composed outside docs/trace/js/ids.js:\n  "
        + "\n  ".join(offenders)
    )


# ─── THE CREDIT THAT IS PIXELS ────────────────────────────────────────────────────────
# Raised by rewt-1d, whose page carries the figure. Every screenshot of the tracer has
# the map credit burnt into it, and the tracer's credit currently reads "Re-use terms
# for these layers are not established (D-037)". If D-037 ever resolves, the generated
# attribution changes on the next build and the committed JPEGs do not — they are pixels,
# so no generator refreshes them and no diff shows them going stale.
#
# This is the shape D-049 warned about, arriving somewhere nobody would look for it: an
# artefact that stays internally consistent while the thing it asserts stops being true.
# The remedy is not to remember. It is to make the end of the absence fail.

CREDIT_FIGURES = (
    "docs/assets/maps/tracer-lea-at-ware.jpg",
)


def test_a_resolved_D_037_fails_here_and_names_the_figures_to_reshoot():
    """The burnt-in map credit, tied to the decision it quotes.

    Passing means D-037 still records re-use as not established and the generated
    attribution still says so. Failing means one of them moved, and the figures listed
    below now assert something the project no longer claims. **A re-shoot is the only
    fix** — nothing regenerates a screenshot — so the failure names them.
    """
    decisions = (paths.ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    heading = next((ln for ln in decisions.splitlines() if ln.startswith("**D-037")), None)
    assert heading, "D-037 has been renumbered or removed; the figures quote it by number"

    # The whole entry's heading, unwrapped: it runs onto the following line.
    start = decisions.index(heading)
    entry = " ".join(decisions[start:start + 400].split())
    assert "re-use recorded as not established" in entry.lower(), (
        "D-037 no longer records re-use as not established.\n"
        "The tracer's map credit quotes that state, and these figures have it burnt in:\n"
        + "\n".join(f"  {f}  — re-shoot" for f in CREDIT_FIGURES)
    )

    source = (TRACER / "gen_backdrops.py").read_text(encoding="utf-8")
    assert "not established (D-037)" in source, (
        "gen_backdrops.py no longer emits the D-037 credit, so the committed figures "
        "and the live map now say different things:\n"
        + "\n".join(f"  {f}  — re-shoot" for f in CREDIT_FIGURES)
    )

    for rel in CREDIT_FIGURES:
        assert (paths.ROOT / rel).is_file(), f"{rel} is listed as carrying the credit but is missing"
