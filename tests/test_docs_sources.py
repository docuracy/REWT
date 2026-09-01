"""The public citations page, which must not drift from the manifest.

`conf/sources.yml` is where a licence and its required attribution are declared, and
`tests/test_licence.py` checks that every source carries them. This file checks the
other half: that the page a reader is actually shown says the same thing.

**The failure this exists to prevent is silent.** GitHub Pages runs Jekyll in safe
mode, so the page cannot read `conf/` and renders from a committed projection under
`docs/_data/`. That projection is written by a script somebody has to remember to
run. Forget it, and the site goes on crediting the terms that applied last month --
confidently, legibly, and wrongly, which is the shape of every provenance failure
this project has had.

Nothing here needs the build database.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "tools/docs/sources_page.py"
DATA = ROOT / "docs/_data/sources.yml"
PAGE = ROOT / "docs/sources.md"
MANIFEST = ROOT / "conf/sources.yml"


@pytest.fixture(scope="module")
def projected() -> dict:
    if not DATA.exists():
        pytest.fail(f"{DATA.relative_to(ROOT)} is missing; run {GENERATOR.relative_to(ROOT)}")
    return yaml.safe_load(DATA.read_text())


def test_projection_is_current() -> None:
    """The committed data file matches the manifest it was generated from."""
    result = subprocess.run(
        [sys.executable, str(GENERATOR.relative_to(ROOT)), "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_every_declared_source_is_published(projected: dict) -> None:
    """No source is used without appearing on the page that credits it."""
    declared = {s["id"] for s in yaml.safe_load(MANIFEST.read_text())["sources"]}
    published = {s["id"] for s in projected["sources"]}
    assert declared == published, f"not credited: {sorted(declared - published)}"


def test_every_source_carries_its_attribution(projected: dict) -> None:
    """The page renders an attribution for each; an empty one would render blank."""
    missing = [s["id"] for s in projected["sources"] if not s.get("attribution", "").strip()]
    assert not missing, f"no attribution to render: {missing}"


def test_notes_are_not_published(projected: dict) -> None:
    """`notes` is written for the implementer and is deliberately not projected.

    It carries probe results, sign conventions and decision references, and some of it
    is provisional in a way the prose on /evidence is not. Publishing it by widening
    the projection would put working notes on a public page without anyone deciding to.
    """
    leaked = [s["id"] for s in projected["sources"] if "notes" in s]
    assert not leaked, f"working notes projected to the public page: {leaked}"


def test_unsettled_count_is_derived_not_written(projected: dict) -> None:
    """The page counts unredistributable sources rather than naming them in prose.

    A sentence saying "the one that is not settled" is true of one manifest and false
    of the next, and reads just as well either way.
    """
    expected = [s for s in projected["sources"] if s["redistribution"] != "permitted"]
    assert projected["unsettled_count"] == len(expected)
    assert [s["id"] for s in projected["unsettled"]] == [s["id"] for s in expected]


def test_page_renders_from_data_not_from_a_list_of_sources() -> None:
    """No source is named in the page's own text.

    The page must render whatever the manifest holds. A title typed into the prose
    survives the source being removed, and is how a page starts crediting something
    that is no longer used.
    """
    body = PAGE.read_text()
    named = [
        s["title"] for s in yaml.safe_load(MANIFEST.read_text())["sources"]
        if s["title"] in body
    ]
    assert not named, f"named in the page text rather than rendered: {named}"
