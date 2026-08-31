"""The curated files themselves, read without a database.

**Curated files are the human judgements, and they are the product** (PLAN.md §7).
Every row carries a stable identifier for what it acts on, a `reason` in words, and
**evidence** — a place, a source, or a person and the date they looked. *A correction
without evidence is indistinguishable from a guess a year later.*

These checks run whether or not anything has been built, because a malformed curated
file is wrong before the build starts.
"""

from __future__ import annotations

import pytest

from rewt import curated, paths


def test_curated_files_parse(curated_judgements):
    """Reading them at all is the test; `curated` raises on a malformed row."""
    assert isinstance(curated_judgements, list)


def test_every_judgement_carries_a_reason_and_evidence(curated_judgements):
    """The parser enforces this. So does this, in case the parser stops."""
    thin = [
        f"{j.kind} {j.subject!r} ({j.source_file} row {j.source_row})"
        for j in curated_judgements
        if not j.reason.strip() or not j.evidence.strip()
    ]
    assert not thin, (
        "judgements with no reason or no evidence: " + ", ".join(thin)
    )


def test_evidence_is_more_than_a_gesture(curated_judgements):
    """A reason in *words*.

    This cannot check that evidence is true, only that someone wrote something a
    reader could follow. "fixed", "obvious" and "yes" are not evidence.
    """
    empty_gestures = {"", "-", "n/a", "na", "none", "yes", "ok", "obvious", "fixed", "tbd"}
    weak = [
        f"{j.kind} {j.subject!r} ({j.source_file} row {j.source_row}): "
        f"reason={j.reason!r} evidence={j.evidence!r}"
        for j in curated_judgements
        if j.reason.strip().lower() in empty_gestures
        or j.evidence.strip().lower() in empty_gestures
    ]
    assert not weak, (
        "a correction without evidence is indistinguishable from a guess a year "
        "later (§7):\n  " + "\n  ".join(weak)
    )


def test_no_two_judgements_of_a_kind_act_on_the_same_subject(curated_judgements):
    """Two rows acting on one feature is a contradiction, not a correction.

    Whichever is applied second wins silently, and the file no longer says what the
    build did.
    """
    seen: dict[tuple[str, str], str] = {}
    clashes = []
    for j in curated_judgements:
        if j.kind == "connector":
            continue                     # keyed on geometry, not on a subject
        key = (j.kind, j.subject)
        where = f"{j.source_file} row {j.source_row}"
        if key in seen:
            clashes.append(f"{j.kind} {j.subject!r}: {seen[key]} and {where}")
        else:
            seen[key] = where
    assert not clashes, "duplicate judgements:\n  " + "\n  ".join(clashes)


def test_connectors_are_lines_with_length(curated_judgements):
    """A connector is defined by its geometry (§5).

    A zero-length connector once reached a published dataset as a row with no
    country. What that case wants is a junction, which adds nothing at all.
    """
    import shapely

    bad = []
    for j in curated_judgements:
        if j.kind != "connector":
            continue
        if j.geometry is None:
            bad.append(f"{j.source_file} feature {j.source_row}: no geometry")
        elif shapely.length(j.geometry) <= 0:
            bad.append(f"{j.source_file} feature {j.source_row}: zero length")
    assert not bad, "\n  ".join(["connectors:"] + bad)


def test_connector_coordinates_are_in_the_working_crs(curated_judgements):
    """EPSG:27700 throughout; EPSG:4326 only at export (AGENTS.md).

    A connector authored in degrees is the mistake this catches: 2.5 and 52.6 are
    valid British National Grid numbers, so nothing downstream would object — the
    connector would simply sit in the sea off the Isles of Scilly.
    """
    import shapely

    # The National Grid's own extent, generously. Anything in degrees falls inside
    # a few hundred metres of the south-west origin and is caught here.
    suspicious = []
    for j in curated_judgements:
        if j.kind != "connector" or j.geometry is None:
            continue
        minx, miny, maxx, maxy = shapely.bounds(j.geometry)
        if not (0 <= minx <= 700_000 and 0 <= miny <= 1_300_000):
            suspicious.append(
                f"{j.source_file} feature {j.source_row}: bounds "
                f"({minx:.1f}, {miny:.1f}, {maxx:.1f}, {maxy:.1f})"
            )
        elif maxx < 1_000 and maxy < 1_000:
            suspicious.append(
                f"{j.source_file} feature {j.source_row}: coordinates look like "
                f"degrees, not EPSG:27700 metres ({minx:.4f}, {miny:.4f})"
            )
    assert not suspicious, (
        "connector geometry outside the British National Grid:\n  "
        + "\n  ".join(suspicious)
    )


def test_connectors_can_say_where_they_are(curated_judgements):
    """Report at the place, not only in the total (AGENTS.md).

    A connector carries its own geometry, so it can always name a place; a CSV row
    may not, and an optional easting/northing is not required of it. What must never
    happen is a connector the reader cannot go and look at — *looking beats
    measuring*.
    """
    placeless = [
        f"{j.kind} {j.subject!r} ({j.source_file} row {j.source_row})"
        for j in curated_judgements
        if j.place() == (None, None) and j.kind == "connector"
    ]
    assert not placeless, (
        "connectors with no derivable place: " + ", ".join(placeless)
    )


@pytest.mark.parametrize("kind,filename", sorted(curated.CLASSES.items()))
def test_each_class_has_one_file_and_the_right_extension(kind, filename):
    """One diffable file per correction class (§7).

    Connectors are GeoJSON because they are defined by geometry; reversals,
    junctions, exclusions and modes are CSV keyed on publisher ids.
    """
    expected_suffix = ".geojson" if kind == "connector" else ".csv"
    assert filename.endswith(expected_suffix), (
        f"the {kind} class is declared as {filename}, which is not {expected_suffix}"
    )
    path = paths.CURATED / filename
    if not path.exists():
        pytest.skip(
            f"{paths.rel(path)} has not been authored yet — no {kind} judgements exist. "
            "This is a legitimate state before the audit has been adjudicated."
        )
    assert path.stat().st_size > 0, f"{paths.rel(path)} is empty rather than absent"
