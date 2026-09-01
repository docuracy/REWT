"""The deliverable, checked as a reader would find it (PLAN.md §7).

**Stage 1 is finished not when the network is good but when someone else can pick it
up.** These checks read `published/` and nothing else — no database, so they hold no
lock and can run while a build is in progress.

The distinction they exist for: a correction that the build applied and the published
output cannot show is, to a reader, a correction that did not happen. §7 asks for the
corrections as their own file *so the difference between the survey and the published
network is a thing you can open* — which is only true if every judgement can be found
in what was opened.
"""

from __future__ import annotations

import pytest

from rewt import paths

pytestmark = pytest.mark.published

NETWORK = paths.PUBLISHED / "rewt_stage1_network.gpkg"
CORRECTIONS = paths.PUBLISHED / "rewt_stage1_corrections.gpkg"


def _read(path, layer, columns, geometry=False):
    import pyogrio

    if not path.exists():
        pytest.skip(
            f"{paths.rel(path)} does not exist; the export stage has not run"
        )
    return pyogrio.read_dataframe(
        path, layer=layer, columns=columns, read_geometry=geometry
    )


@pytest.fixture(scope="module")
def links():
    return _read(
        NETWORK,
        "link",
        [
            "link_id", "publisher_id", "origin", "routing_reversed",
            "reversed_by_correction", "retired", "superseded_by", "parent_link_id",
        ],
    )


@pytest.fixture(scope="module")
def corrections():
    return _read(
        CORRECTIONS,
        "correction",
        ["correction_id", "kind", "subject", "resolved_to", "applied",
         "easting", "northing"],
        geometry=True,
    )


def test_every_applied_reversal_is_visible_in_the_published_network(links, corrections):
    """An applied correction a reader cannot find did not, as far as they know, happen.

    The case this catches: a reversal is applied, and the link it names is later cut
    by a connector and retired. The two successors inherit the geometry but not
    `reversed_by_correction`, so the judgement is recorded as applied while nothing
    in the published network carries it. `superseded_by` is followed here, because
    that is the trail a reader would follow.

    *Never delete a geometry to correct it. Retire it with a reason and keep it* —
    and a retired link is how a reader tells a correction from an omission, which
    only works if the correction travels to whatever replaced it.
    """
    applied = corrections[
        (corrections["kind"] == "reversal") & corrections["applied"].astype(bool)
    ]
    if applied.empty:
        pytest.skip("no reversal has been applied yet")

    carried = set(links["reversed_by_correction"].dropna())
    # publisher_id is not unique once a link has been cut, so group rather than index.
    by_publisher = {
        pid: frame for pid, frame in links.groupby("publisher_id", dropna=True)
    }
    lost = []
    for _, row in applied.iterrows():
        if row["correction_id"] in carried:
            continue
        where = "no link in the published network carries this correction"
        frame = by_publisher.get(row["subject"])
        if frame is not None and len(frame):
            link = frame.iloc[0]
            if bool(link["retired"]):
                children = [
                    c for c in str(link["superseded_by"] or "").split(",") if c.strip()
                ]
                where = (
                    f"its link was retired and superseded by {len(children)} "
                    "successors, none of which carries the reversal"
                )
        lost.append(f"{row['correction_id']} on {str(row['subject'])[:8]}: {where}")

    assert not lost, (
        f"{len(lost)} of {len(applied)} applied reversals are invisible in the "
        "published network, so the difference between the survey and this network "
        "cannot be opened for them:\n  " + "\n  ".join(lost)
    )


def test_every_correction_can_be_gone_and_looked_at(corrections):
    """*Report at the place, not only in the total. Emit a coordinate with every
    finding* (AGENTS.md).

    A judgement with neither geometry nor easting/northing cannot be found on a map,
    and *looking beats measuring* — which matters most for a corpus that says of
    itself that it was judged by rule rather than by a person at the place. The
    remedy for that is to go and look, and a correction with no coordinate cannot be
    looked at.
    """
    placeable = corrections.geometry.notna() | corrections["easting"].notna()
    unplaceable = corrections[~placeable]
    if unplaceable.empty:
        return
    by_kind = unplaceable.groupby("kind").size().to_dict()
    pytest.fail(
        f"{len(unplaceable):,} of {len(corrections):,} corrections carry neither a "
        f"geometry nor an easting and northing: "
        + ", ".join(f"{k} {v:,}" for k, v in sorted(by_kind.items()))
        + ". Each names a place in its own evidence text, so the coordinate exists "
        "and is not being written out."
    )


def test_a_reader_can_tell_the_survey_from_this_project(links):
    """*A consumer must be able to tell what came from Ordnance Survey and what this
    project added, without reading the code* (§7)."""
    origins = set(links["origin"].dropna().unique())
    unexpected = origins - {"survey", "connector", "skeleton"}
    assert not unexpected, (
        f"links carry origins §7 does not define: {', '.join(sorted(unexpected))}"
    )
    assert "survey" in origins, "no link is marked as the survey's own"


def test_nothing_was_deleted_to_correct_it(links):
    """*Never delete a geometry to correct it. Retire it with a reason and keep it.*

    A retired link with nothing named as its successor is indistinguishable from an
    omission, which is the one thing retirement exists to prevent.
    """
    retired = links[links["retired"].astype(bool)]
    if retired.empty:
        return
    orphaned = retired[retired["superseded_by"].isna() | (retired["superseded_by"] == "")]
    assert orphaned.empty, (
        f"{len(orphaned):,} retired links name nothing that superseded them, so a "
        "reader cannot tell the correction from an omission: "
        + ", ".join(str(x)[:12] for x in orphaned["link_id"].head(5))
    )


def test_the_published_network_is_in_the_declared_crs():
    """EPSG:27700 throughout; EPSG:4326 only at export, and only if declared."""
    import pyogrio

    from rewt import config

    if not NETWORK.exists():
        pytest.skip(f"{paths.rel(NETWORK)} does not exist")
    declared = config.param("crs.export")
    for layer in ("link", "node", "basin"):
        info = pyogrio.read_info(NETWORK, layer=layer)
        assert info["crs"] == declared, (
            f"layer {layer!r} is {info['crs']}, not the declared {declared}"
        )


def test_the_attribution_travels_with_the_data():
    """*Provenance travels as a pointer.* A short attribution may never attribute
    less than conf/sources.yml does."""
    from rewt import config

    path = paths.PUBLISHED / "ATTRIBUTION.md"
    if not path.exists():
        pytest.skip(f"{paths.rel(path)} does not exist; the export stage has not run")
    text = path.read_text(encoding="utf-8")
    missing = [
        src.id for src in config.sources() if src.attribution not in text
    ]
    assert not missing, (
        "sources whose required attribution is not reproduced in full in "
        f"{paths.rel(path)}: {', '.join(missing)}"
    )


@pytest.fixture(scope="module")
def audit():
    import json

    path = paths.PUBLISHED / "audit" / "audit.json"
    if not path.exists():
        pytest.skip(f"{paths.rel(path)} does not exist; the audit has not run")
    return json.loads(path.read_text(encoding="utf-8"))["sections"]


def test_the_audits_dead_ends_reproduce_from_the_published_network(audit):
    """The audit's headline figures, re-derived from the artefact it published.

    **From every link, following flow direction downstream, you reach tidal water.
    Equivalently: no node has inflows and no outflow, except at the sea** (§1). That
    is a definition anyone can apply to the published GeoPackage, so the audit's own
    count of it should be reproducible without reading the audit's code — and if the
    two disagree, either the audit or the export is wrong and the network is not
    what the report says it is.

    Two definitions matter and are recorded here because neither is obvious:

    * a dead end is a node that some live link arrives at and no live link leaves,
      counted over links that have not been retired, since a retired link is kept
      for the audit trail and is not in the routing graph;
    * *in scope* for this count follows the arriving link's own scope flag, not the
      node's basin. §4.1 has the reason: tidal water is masked out of a DEM and so
      sits on no basin at all, which is exactly where these nodes are. Counting by
      basin gives 1,393 rather than 1,722 and silently drops the estuaries.

    This reproduces the export at 4,933 national, 1,722 in scope, 418 of those at
    tidal water and 1,304 defects — which is §6's calibration shape.
    """
    dead_ends = audit.get("dead_ends")
    if not dead_ends:
        pytest.skip("the audit reports no dead_ends section")

    links = _read(
        NETWORK, "link", ["from_node", "to_node", "retired", "in_scope"]
    )
    nodes = _read(NETWORK, "node", ["node_id", "terminus"])

    live = links[~links["retired"].astype(bool)]
    arrives_at = set(live["to_node"])
    leaves_from = set(live["from_node"])
    dead = arrives_at - leaves_from

    assert len(dead) == dead_ends["national"], (
        f"the published network has {len(dead):,} nodes with an inflow and no "
        f"outflow; the audit reports {dead_ends['national']:,}. One of the two is "
        "describing a different network."
    )

    in_scope_arrivals = set(live[live["in_scope"].astype(bool)]["to_node"])
    in_scope = dead & in_scope_arrivals
    assert len(in_scope) == dead_ends["in_scope"], (
        f"{len(in_scope):,} in-scope dead ends against the audit's "
        f"{dead_ends['in_scope']:,}"
    )

    terminus = dict(zip(nodes["node_id"], nodes["terminus"]))
    at_tidal = sum(1 for n in in_scope if terminus.get(n) == "tidal")
    assert at_tidal == dead_ends["at_tidal_water"], (
        f"{at_tidal:,} in-scope dead ends stand at tidal water against the audit's "
        f"{dead_ends['at_tidal_water']:,}"
    )
    assert len(in_scope) - at_tidal == dead_ends["defects"], (
        f"{len(in_scope) - at_tidal:,} defects against the audit's "
        f"{dead_ends['defects']:,}"
    )


def test_the_audit_accounts_for_every_in_scope_dead_end(audit):
    """At tidal water is correct; anywhere else is the work. There is no third case.

    *There is no second escape clause* (§1): an exit at the edge of the study area
    is a defect and not a terminus, so every in-scope dead end is one or the other.
    """
    dead_ends = audit.get("dead_ends")
    if not dead_ends:
        pytest.skip("the audit reports no dead_ends section")
    assert (
        dead_ends["at_tidal_water"] + dead_ends["defects"] == dead_ends["in_scope"]
    ), (
        f"{dead_ends['at_tidal_water']:,} at tidal water plus "
        f"{dead_ends['defects']:,} defects does not account for "
        f"{dead_ends['in_scope']:,} in-scope dead ends"
    )
