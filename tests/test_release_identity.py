"""The DOI, which is what a reader clicks and what a citation resolves to.

Two failures here, six days apart, and neither was visible from inside the build.

**D-068 — the badge resolved to a record containing no rivers.** The badge was the
convenient form, `zenodo.org/badge/latestdoi/<repo id>`, which follows every release
without ever needing an edit. That convenience is exactly what binds it to the
GitHub–Zenodo hook, whose handle is the repository id and which archives the source
zipball alone. `.github/workflows/zenodo.yml` exists *because* a hook-only record would
resolve to a river project containing no rivers, and the badge then pointed past the
workflow at precisely the record the workflow was written to replace.

**D-075 — every release minted its own concept DOI, so the badge named a lineage of
one.** The fix for D-068 pointed the badge at a literal concept DOI and checked that it
resolved. It did, to a real record with the real data in it. **Resolving to something
correct is not the same as resolving to the right thing**: the deposit script called
`POST /deposit/depositions` unconditionally, so each release started a fresh lineage and
the concept named in the badge froze at v0.1.0-alpha while the data moved on.

Both are the same shape as D-067 — two artefacts, each internally consistent, produced
by different mechanisms and never compared — and both are cheap to test, because every
party to the disagreement is a file in this repository. Nothing here touches the
network: whether a DOI resolves is Zenodo's business, and whether the three files agree
about which DOI it is, is ours.
"""

from __future__ import annotations

import json
import re

import pytest

from rewt import paths

ZENODO = paths.ROOT / ".zenodo.json"
CITATION = paths.ROOT / "CITATION.cff"
README = paths.ROOT / "README.md"
DEPOSIT = paths.ROOT / ".github" / "scripts" / "zenodo_deposit.py"

# `![alt](target)` and `[text](target)` alike — the target is what a reader reaches.
LINK_TARGETS = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)")
# A Zenodo DOI wherever it appears in a URL: 10.5281/zenodo.22248272.
DOI_IN_URL = re.compile(r"10\.\d{4,}/zenodo\.\d+")


def _concept_recid() -> int:
    if not ZENODO.exists():
        pytest.skip(f"{paths.rel(ZENODO)} does not exist")
    recid = json.loads(ZENODO.read_text(encoding="utf-8")).get("concept_recid")
    assert isinstance(recid, int), (
        f"{paths.rel(ZENODO)} names no integer `concept_recid`. Without it "
        "`zenodo_deposit.py` starts a new lineage at every release, which is D-075: "
        "v0.1.0-alpha and v0.1.1-alpha became two unrelated datasets rather than two "
        "versions of one, and the two concepts can never be merged."
    )
    return recid


def test_the_badge_the_citation_and_the_deposit_name_one_concept():
    """Three files, one number, and nothing but this comparing them.

    `CITATION.cff` is generated from `.zenodo.json` by `rewt citation`, so those two
    agree by construction — but only if the generator has been run since the anchor
    last moved, which is a thing a reader cannot see. The README badge is written by
    hand and agrees with neither by construction.
    """
    concept = _concept_recid()
    expected = f"10.5281/zenodo.{concept}"

    for path in (CITATION, README):
        if not path.exists():
            pytest.skip(f"{paths.rel(path)} does not exist")

    citation = CITATION.read_text(encoding="utf-8")
    assert expected in citation, (
        f"{paths.rel(CITATION)} does not name {expected}, the concept anchored in "
        f"{paths.rel(ZENODO)}. CITATION.cff is generated — run `rewt citation` — and a "
        "stale copy tells everyone who cites this project to cite a different dataset."
    )

    targets = LINK_TARGETS.findall(README.read_text(encoding="utf-8"))
    # A DOI REFERENCE, not merely a link mentioning Zenodo. The first version of this
    # matched any target containing "zenodo" and failed on `[Zenodo](https://zenodo.org)`
    # in the prose — a selector that matched the right thing AND something else, which
    # reads exactly like a real finding until you look at the row it named.
    dois = {t for t in targets if DOI_IN_URL.search(t) or "badge/latestdoi" in t}
    assert dois, (
        f"{paths.rel(README)} has no DOI badge or link at all. The badge is how a "
        "reader reaches the archived record; a citable dataset that does not say so is "
        "not citable in practice."
    )
    wrong = sorted(t for t in dois if str(concept) not in t)
    assert not wrong, (
        f"{paths.rel(README)} points at a DOI other than the anchored concept "
        f"{expected}:\n      " + "\n      ".join(wrong) + "\n      D-075: a badge that "
        "resolves to a real record with real data in it is still wrong if that record "
        "is not the newest edition. Resolving is not the test; resolving to the thing "
        "whose name it is being given is."
    )


def test_the_badge_is_not_the_repository_id_form():
    """D-068 itself, and it can come back in one careless edit.

    `zenodo.org/badge/latestdoi/<repo id>` is the form GitHub offers, needs no
    maintenance and cannot be made to point anywhere but the hook's own record. The
    literal concept DOI must be edited if the concept ever changes, and that cost is
    the reason it points where it is meant to.
    """
    if not README.exists():
        pytest.skip(f"{paths.rel(README)} does not exist")
    text = README.read_text(encoding="utf-8")
    targets = LINK_TARGETS.findall(text)
    latestdoi = sorted(t for t in targets if "badge/latestdoi" in t)
    assert not latestdoi, (
        f"{paths.rel(README)} links to the repository-id badge form:\n      "
        + "\n      ".join(latestdoi)
        + "\n      That URL follows the GitHub–Zenodo HOOK, which archives the source "
        "zipball and nothing else — a river project containing no rivers (D-068). Name "
        "the concept DOI literally, and accept that it needs editing if the concept "
        "moves."
    )
    # The selector reads LINK TARGETS and not the file, and the difference is the whole
    # of it: the README discusses `badge/latestdoi` at length in prose, and a substring
    # search would fail on the explanation of why the thing it warns about is absent.
    assert "badge/latestdoi" in text, (
        "the README no longer explains why the repository-id badge is not used. That "
        "is not a failure of the code, but this test's selector was written around the "
        "explanation being there, and it is now weaker than it reads."
    )


def test_the_deposit_extends_the_concept_rather_than_starting_a_lineage():
    """D-075's mechanism, read from the script that performs it.

    The anchor is STORED and the head is ASKED FOR: `.zenodo.json` names the concept,
    and the script finds the latest version under it at run time, because a stored head
    goes stale at the next release.
    """
    if not DEPOSIT.exists():
        pytest.skip(f"{paths.rel(DEPOSIT)} does not exist")
    source = DEPOSIT.read_text(encoding="utf-8")

    assert "concept_recid" in source, (
        f"{paths.rel(DEPOSIT)} does not read `concept_recid` from .zenodo.json, so it "
        "cannot know which lineage to extend."
    )
    assert "actions/newversion" in source, (
        f"{paths.rel(DEPOSIT)} never calls `actions/newversion`. A release created with "
        "a bare `POST /deposit/depositions` is a NEW DATASET with its own concept DOI, "
        "not a new version of this one — D-075, and Zenodo cannot merge the two "
        "afterwards."
    )
    assert re.search(r'DELETE.*files', source), (
        f"{paths.rel(DEPOSIT)} does not delete the files a new version inherits. Zenodo "
        "carries the previous version's files forward, so without this v0.1.2 ships "
        "v0.1.1's GeoPackage beside its own."
    )
