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
            "link_id", "publisher_id", "origin", "form", "name", "routing_reversed",
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
    # Sources the build reads. One declared for a later stage has nothing in this
    # export to attribute, and requiring it here would only report staleness.
    missing = [
        src.id
        for src in config.sources()
        if src.get("stage", default=1) == 1 and src.attribution not in text
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


# --------------------------------------------------------------------------
# What the report says, as against what the figures say
# --------------------------------------------------------------------------


def test_no_basin_short_of_the_sea_reports_as_complete():
    """*Every basin either reaches 100% reachable, or its shortfall is named with a
    reason* (§9). It may not do both in the same sentence.

    A share formatted to whole percent rounds 0.99794 to 100, so a basin listed
    under the heading "Every basin short of 100%" prints as "(100% reached)" while
    the same line goes on to name the dead ends it still has. A reader quotes the
    number and not the clause after it.

    This is the failure this repository keeps meeting in a new place: *481 km of new
    holes once arrived alongside a network that had grown in both count and length*,
    and an aggregate agreed that a broken thing was fixed.

    Measured when this was written: 17 basins hold a share that rounds to 100% while
    still carrying stranded length — about 34 km of river between them — and 2 of
    those, the Wye at 6.6 km and the Tweed at 6.2 km, were printed in this section
    as "(100% reached)".
    """
    import re

    path = paths.PUBLISHED / "audit" / "audit.md"
    if not path.exists():
        pytest.skip(f"{paths.rel(path)} does not exist; the audit has not run")
    text = path.read_text(encoding="utf-8")

    heading = re.search(r"^##\s+Every basin short of 100%.*$", text, re.MULTILINE)
    if not heading:
        pytest.skip("audit.md has no per-basin shortfall section to check")
    section = text[heading.end() :]
    end = re.search(r"^##\s", section, re.MULTILINE)
    if end:
        section = section[: end.start()]

    claiming = [
        m.group(1)
        for m in re.finditer(r"^-\s+\*\*(.+?)\*\*\s+\(100%\s+reached\)", section, re.MULTILINE)
    ]
    assert not claiming, (
        f"{len(claiming)} basins are listed as short of 100% and printed as "
        "'(100% reached)': " + ", ".join(claiming[:8])
        + ". A share rounded to whole percent reports a stranded basin as complete, "
        "which is the one claim §9 does not allow to be made loosely."
    )


def test_a_basin_with_stranded_length_does_not_score_one(audit):
    """The figures behind the formatting, checked independently of it.

    `share` is a float and cannot round, so this is the check that survives whatever
    the report chooses to print: a basin with unreached length is not complete.
    """
    basins = audit.get("basins")
    if not basins:
        pytest.skip("the audit reports no per-basin section")
    wrong = [
        f"{b['label']!r} share={b['share']:.6f} with {b['unreached_km']:.2f} km unreached"
        for b in basins
        if b.get("unreached_km", 0) > 1e-9 and b.get("share", 0) >= 1.0
    ]
    assert not wrong, (
        "basins scored as fully reaching the sea while length stands above them:\n  "
        + "\n  ".join(wrong)
    )


def test_the_per_basin_shares_are_arithmetic(audit):
    """reached + unreached is the whole basin, and share is their ratio."""
    basins = audit.get("basins")
    if not basins:
        pytest.skip("the audit reports no per-basin section")
    inconsistent = []
    for b in basins:
        total = b.get("km") or 0
        if total <= 0:
            continue
        if abs((b.get("reached_km", 0) + b.get("unreached_km", 0)) - total) > 0.01:
            inconsistent.append(f"{b['label']!r}: reached + unreached != {total:.2f} km")
        elif abs(b.get("share", 0) - b.get("reached_km", 0) / total) > 1e-6:
            inconsistent.append(f"{b['label']!r}: share is not reached / total")
    assert not inconsistent, "\n  ".join(["per-basin arithmetic:"] + inconsistent[:10])


def test_a_lake_link_is_never_named_for_the_water_body_it_crosses(links):
    """A measured fact about the source, pinned because its absence has been read.

    **Not one lake link in the network carries the word "Reservoir".** Of 24,163
    lake links, 6,043 are named, 68.1% of those with a running-water name — Burn,
    Brook, River, Beck — and 4.3% with a standing-water one. Kielder Water is
    crossed by links called Kielder Burn and White Kielder Burn; Ladybower by
    Ladybower Brook; Rutland Water's links carry no name at all.

    So OS names a lake link for the watercourse running through the water body, not
    for the water body. **The absence of "Reservoir" is total and says nothing about
    reservoirs**, and any claim resting on that absence is reading a naming
    convention as evidence. PLAN.md §5 wants reservoirs flagged — from the water-body
    polygons, never from these names.

    If this ever fails, OS has changed how it names lake links and anything that
    inferred from the old convention needs re-reading.
    """
    lake = links[links["form"] == "lake"] if "form" in links else None
    if lake is None:
        pytest.skip("the link layer was read without its form column")
    named = lake["name"].dropna().astype(str)
    reservoirs = [n for n in named if "reservoir" in n.lower()]
    assert not reservoirs, (
        f"{len(reservoirs)} lake links are named for a reservoir "
        f"({', '.join(sorted(set(reservoirs))[:5])}). The convention this test "
        "records has changed, and any reasoning that rested on it needs re-reading."
    )


# --------------------------------------------------------------- PLAN.md §10
# Three things §10 asks Stage 1 for, checked in the deliverable rather than in the
# database, because §10's whole argument is that a later stage must be able to *join*
# to these rather than re-derive them — and a later stage will have the GeoPackage.


@pytest.fixture(scope="module")
def termini():
    return _read(
        NETWORK,
        "terminus",
        ["node_id", "terminus", "basin_id", "arriving_form", "is_crawl_seed"],
    )


def test_tidal_termini_are_published_as_objects(termini):
    """*Every tidal terminus is identified and kept as a first-class thing rather than
    implied by the absence of an outflow* (§10).

    The failure this guards is a layer that exists but is empty, or one that has
    quietly become a copy of the seed set.
    """
    assert len(termini) > 0, "the terminus layer is empty"
    assert set(termini["terminus"].unique()) == {"tidal"}


def test_a_terminus_is_not_the_same_thing_as_a_crawl_seed(termini):
    """The distinction the layer exists to preserve.

    A node can be tidal without the crawl having seeded from it. If these two sets
    were identical the layer would be redundant, and — worse — a later stage joining
    a depth contour to "the termini" would be attaching to whichever nodes *this*
    build's crawl happened to use. That would make a Stage 2 artefact depend on a
    Stage 1 implementation detail, which is the re-derivation §10 asks us to prevent.
    """
    seeds = termini["is_crawl_seed"].fillna(False).astype(bool)
    assert seeds.any(), "no published terminus was a crawl seed — the join is broken"
    assert not seeds.all(), (
        "every tidal terminus is also a crawl seed. Either the network really has "
        "changed, or the layer is being derived from `seed` rather than from "
        "`node.terminus` — check the export before believing the first."
    )


def test_the_terminus_layer_carries_basins_where_basins_exist(termini):
    """§8 asks for reporting per basin, so the layer must carry the basin.

    It cannot carry one for every terminus, and that is a property of the
    delineation rather than of this layer: **53,755 of 197,734 nodes — 27% —
    fall outside any delineated basin**, and tidal termini sit at the coast
    where that is most likely. 4,067 of 13,030 have no basin, which is close
    to the network-wide rate and so is not evidence of anything worse.

    What this test guards is the join breaking altogether, which would look
    identical to "these termini have no basin" in every downstream report. So
    it requires the assigned share to stay in the neighbourhood of the
    network-wide share rather than requiring it to be complete — a bound that
    fails loudly if the join silently starts returning nothing.
    """
    assigned = termini["basin_id"].notna().mean()
    assert 0.5 < assigned < 1.0, (
        f"{assigned:.1%} of published termini carry a basin. Network-wide, 73% "
        "of nodes do. Far below that means the join has broken; exactly 100% "
        "means it is no longer reading node_basin."
    )


def test_fall_is_published_for_screening_and_named_as_such(links):
    """§10 asks for the fall of every link from the unconditioned terrain.

    The name is the load-bearing part, not the number. A 50 m model does not resolve
    a mill's head — a weir and a leat make metres of fall over a few hundred — so a
    column called `fall_m` in a published GeoPackage would eventually be read as a
    site measurement by someone who never saw this repository. The prefix is the only
    part of the artefact that travels with the value, so it is worth a test.
    """
    import pyogrio

    fields = set(pyogrio.read_info(NETWORK, layer="link")["fields"])
    for column in (
        "screening_elevation_upstream_m",
        "screening_elevation_downstream_m",
        "screening_fall_m",
        "screening_terrain_verdict",
    ):
        assert column in fields, f"{column} is not published"

    bare = {f for f in fields if f in ("fall_m", "elevation_m", "gradient")}
    assert not bare, (
        f"{sorted(bare)} published without the `screening_` prefix. The prefix is "
        "what stops a 50 m sample being read as a survey."
    )


def test_every_published_identifier_expands_to_a_routable_uri(links, termini):
    """A CURIE expands by concatenation, so the separator has to be a slash.

    `rewt:basin/4385554389` expands onto `https://w3id.org/rewt/basin/4385554389`,
    which w3id routes. `rewt:basin-unanchored:1002` expands onto
    `https://w3id.org/rewt/basin-unanchored:1002`, which is a legal URI that
    resolves to nothing — and it shipped, because it was built by an f-string in
    another module rather than by `ids.py`.

    Checked on the published file because that is where an outside consumer meets
    these strings, and a resolver will not care which module composed them.
    """
    import re

    import pyogrio

    shape = re.compile(r"^(os|rewt):[a-z][a-z0-9-]*/[^/:]+$")
    for name, frame, column in (
        ("link", links, "link_id"),
        ("terminus", termini, "node_id"),
    ):
        bad = [v for v in frame[column].dropna().unique()[:5000] if not shape.match(v)]
        assert not bad, f"{name}.{column} identifiers do not expand: {bad[:5]}"

    basins = _read(NETWORK, "basin", ["basin_id"])
    bad = [v for v in basins["basin_id"].dropna().unique() if not shape.match(v)]
    assert not bad, f"basin identifiers do not expand: {bad[:5]}"


def test_the_audit_and_the_published_file_agree_per_basin():
    """The per-basin figures a reader computes must match the ones we report.

    They did not. The audit attributes a link to a basin by its **oriented**
    downstream node (`edge.to_node`); `link_scope` attributed it by the
    **digitised** one. For a reversed link those are opposite ends, and 335 links
    are reversed — so 64 links, 94.3 km, sat in one basin in the published file
    and a different one in the audit.

    The error was small (worst basin 0.2%) and systematic, which is the bad
    combination: too small to notice, consistent enough to look like a real
    property of the data. It was found by rewt-fc recomputing our figures from
    outside and refusing to accept its own first answer.

    So the check belongs here — an outside reader summing the published file must
    reach the audit's number, or one of the two is lying about the same rivers.
    """
    import json

    from rewt import paths

    audit_path = paths.PUBLISHED / "audit" / "audit.json"
    if not audit_path.exists():
        pytest.skip("the audit has not run")
    rows = json.loads(audit_path.read_text())["sections"]["basins"]

    frame = _read(NETWORK, "link", ["basin_id", "length_m", "retired"])
    live = frame[~frame["retired"].fillna(False).astype(bool)]
    mine = live.groupby("basin_id")["length_m"].sum() / 1000.0

    worst = (0.0, None)
    for row in rows:
        theirs = float(row["km"])
        ours = float(mine.get(row["basin_id"], 0.0))
        gap = abs(theirs - ours)
        if gap > worst[0]:
            worst = (gap, row["label"])

    assert worst[0] < 0.5, (
        f"the published file and the audit disagree by {worst[0]:,.1f} km on "
        f"{worst[1]!r}. Both count the same rivers, so one of them attributes a "
        "link to the wrong basin — check whether each is keying on the oriented "
        "or the digitised downstream node."
    )


def test_the_published_ids_are_what_the_scheme_would_mint_today(links):
    """The golden values pin the rule; this pins the artefact against the rule.

    `test_the_identifier_scheme_has_not_moved` fails when a composition rule
    changes, which is the loud half. The quiet half is the published file, which
    keeps whatever ids it was written with — so a scheme change plus an obliging
    update to the golden values would leave the export carrying ids the code can no
    longer mint, and nothing would say so.

    Changing `ids.publisher` from `os:link:` to `os:link/` renumbered every anchored
    basin and went through a full green build. This is the check that would have
    caught it in the artefact rather than in the rule.
    """
    from rewt import ids

    survey = links[(links["origin"] == "survey") & links["publisher_id"].notna()]
    if survey.empty:
        pytest.skip("no survey link carries a publisher id")
    mismatched = [
        f"{row.link_id} should be {ids.publisher('link', row.publisher_id)}"
        for row in survey.head(5000).itertuples()
        if row.link_id != ids.publisher("link", row.publisher_id)
    ]
    assert not mismatched, (
        f"{len(mismatched)} published link ids are not what rewt.ids would mint "
        "today, so the export and the scheme have parted company:\n  "
        + "\n  ".join(mismatched[:5])
    )


def test_the_national_reachability_reproduces_from_the_published_network(audit):
    """The headline number, re-derived from the ingredients published beside it.

    *Reachability. The share of length from which the sea can be reached. This is
    the headline number and the one to watch* (§6). It is also the number most
    likely to be quoted on its own, so it should be checkable by anyone holding the
    GeoPackage and nothing else.

    The keys used to be `gb_km` and `in_scope_km`, meaning the lengths **reached**
    — which this test had to establish by computing both readings, because the
    names did not say. They are now `reached_*` with `total_*` beside them, so the
    ambiguity this docstring existed to warn about is gone from the artefact
    rather than only documented here. Renamed by rewt-d3; the assertion below is
    unchanged in substance and now names which quantity it is checking.
    """
    reachability = audit.get("reachability")
    if not reachability:
        pytest.skip("the audit reports no reachability section")

    frame = _read(
        NETWORK, "link", ["in_scope", "reaches_tidal", "length_m", "retired"]
    )
    live = frame[~frame["retired"].astype(bool)]

    for label, subset in (
        ("gb", live),
        ("in_scope", live[live["in_scope"].astype(bool)]),
    ):
        total_km = subset["length_m"].sum() / 1000.0
        reached_km = (
            subset[subset["reaches_tidal"].astype(bool)]["length_m"].sum() / 1000.0
        )
        assert abs(reached_km / total_km - reachability[f"{label}_share"]) < 1e-6, (
            f"{label} reachable share is {reached_km / total_km:.6f} in the published "
            f"network and {reachability[f'{label}_share']:.6f} in the audit"
        )
        assert abs(reached_km - reachability[f"reached_{label}_km"]) < 0.1, (
            f"{label}_km is {reachability[f'reached_{label}_km']:,.1f} in the audit and "
            f"{reached_km:,.1f} reached in the published network"
        )


def test_the_reachability_prose_says_something_true():
    """*"93.28% of 97,786 km"* — a complete sentence, and a false one.

    97,786 km is the length **reached**, not the length in scope. So the line
    asserts that the in-scope network is 97,786 km and that about 91,200 km of it
    reaches the sea, when the true statement is 93.28% of 104,829 km. Both figures
    in the reader's hand are wrong, from a sentence that is internally consistent
    and reads perfectly.

    This is the Tweed rounding again in a different place: **the number is exact and
    the sentence around it is false.** The author read the line a dozen times
    without seeing it, because they already knew which figure was which — which is
    what makes this class need a test rather than a proofread.

    Nothing here is pinned to a value. Both sides are recomputed from the published
    network, so this keeps working as the figures move.
    """
    import re

    path = paths.PUBLISHED / "audit" / "audit.md"
    if not path.exists():
        pytest.skip(f"{paths.rel(path)} does not exist; the audit has not run")

    frame = _read(
        NETWORK, "link", ["in_scope", "reaches_tidal", "length_m", "retired"]
    )
    live = frame[~frame["retired"].astype(bool)]
    scopes = {
        "great britain": live,
        "in scope": live[live["in_scope"].astype(bool)],
    }

    pattern = re.compile(
        r"^-\s+(.+?):\s+\*\*([\d.]+)%\*\*\s+of\s+([\d,]+(?:\.\d+)?)\s*km",
        re.MULTILINE | re.IGNORECASE,
    )
    claims = [
        (m.group(1).strip().lower(), float(m.group(2)), float(m.group(3).replace(",", "")))
        for m in pattern.finditer(path.read_text(encoding="utf-8"))
    ]
    if not claims:
        pytest.skip("audit.md states no 'N% of M km' reachability claim")

    wrong = []
    for label, percent, stated_km in claims:
        subset = scopes.get(label)
        if subset is None:
            continue
        total_km = subset["length_m"].sum() / 1000.0
        reached_km = (
            subset[subset["reaches_tidal"].astype(bool)]["length_m"].sum() / 1000.0
        )
        # "P% of N km" says N is the whole and P% of it was reached.
        if abs(stated_km - total_km) > max(1.0, total_km * 0.001):
            wrong.append(
                f"{label!r}: the line says {percent:.2f}% of {stated_km:,.0f} km, "
                f"but {stated_km:,.0f} km is not the total — the total is "
                f"{total_km:,.0f} km and {reached_km:,.0f} km of it is reached. "
                f"As written the sentence claims {stated_km * percent / 100:,.0f} km "
                "reaches the sea."
            )
        elif abs(percent - reached_km / total_km * 100) > 0.01:
            wrong.append(
                f"{label!r}: the line says {percent:.2f}% where the published "
                f"network gives {reached_km / total_km * 100:.2f}%"
            )
    assert not wrong, (
        "the audit's reachability prose does not describe the network it "
        "published:\n  " + "\n  ".join(wrong)
    )


def test_no_published_json_carries_a_bare_nan():
    """`NaN` is not JSON, and Python is the only reader that will not say so.

    RFC 8259 has no `NaN` literal. Python's encoder emits one anyway and its own
    decoder accepts it back, so the value round-trips perfectly in the language
    that produced it and fails `JSON.parse` outright — one missing number breaks
    an entire payload in a browser while reading cleanly here.

    Found by rewt-fc, whose map broke on `terminus.inflow_length_m`: NaN for the
    10,784 termini the crawl did not seed from, correct in the GeoPackage and
    fatal once it reached an encoder. This reads the published files as a
    non-Python consumer would, rather than trusting the writer.
    """
    import json

    from rewt import paths

    checked = []
    for path in sorted(paths.PUBLISHED.rglob("*.json")) + sorted(
        paths.PUBLISHED.rglob("*.geojson")
    ):
        text = path.read_text(encoding="utf-8")
        checked.append(path.name)
        # json.loads accepts NaN; a strict reader does not. parse_constant fires on
        # exactly the three literals JSON has no place for.
        def refuse(literal, _p=path):
            raise AssertionError(
                f"{_p.name} contains the bare literal {literal!r}, which is not JSON "
                "and which JSON.parse rejects. Use null."
            )

        json.loads(text, parse_constant=refuse)
    assert checked, "no published JSON found to check"


def test_the_two_reachability_readings_are_computed_the_same_way(audit):
    """§10 publishes both readings so the sea becoming a test never reads as the
    network improving. That only holds if they are comparable.

    They were not. The first version summed the sea reading over `link`, which
    omits the 2,650 links this project adds, while the reachability section sums
    over `edge`. The audit then carried **two in-scope totals differing by 1,844
    km** — 103,855 beside its own 105,699 — and the smaller denominator made the
    sea share look higher. Neither number was wrong; the pair was, which is
    precisely the failure the requirement to publish both exists to prevent.

    Found because the release-notes generator reads the audit rather than
    restating it, and put both totals on one page.
    """
    r = audit.get("reachability")
    s = audit.get("reachability_tested_against_the_sea")
    if not r or not s:
        pytest.skip("the audit reports only one reading")
    assert abs(r["total_in_scope_km"] - s["in_scope_total_km"]) < 0.5, (
        f"the two readings disagree about the size of the in-scope network: "
        f"{r['total_in_scope_km']:,.1f} km against {s['in_scope_total_km']:,.1f} km. "
        "They are published side by side to be compared, so they must be summed over "
        "the same thing."
    )
    assert abs(r["reached_in_scope_km"] - s["reaches_tidal_water_km"]) < 0.5, (
        "the two readings disagree about how much reaches tidal water, which is the "
        "quantity they share"
    )
    assert s["reaches_the_sea_km"] <= s["reaches_tidal_water_km"] + 0.5, (
        "more length reaches the sea than reaches tidal water, which cannot happen: "
        "the sea test is a filter applied to the tidal one"
    )
