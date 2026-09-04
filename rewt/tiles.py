"""The viewer's data: the whole network as tiles, and the small layers whole.

**Built in CI, committed nowhere.** That is why Pages was moved off the branch build:
serving from `main:/docs` would mean committing this, and `.gitignore`'s first rule
forbids it. The rule is kept rather than excepted from.

**GDAL rather than tippecanoe.** GDAL 3.8 writes PMTiles directly and is already a
requirement of this build; adding a source-built tool would put a third-party
compilation in the path of every documentation deploy, which is the same objection
that kept `counties.json` out of CI (D-064).

**Two network layers, and the split is not an optimisation.** The viewer has said at
every zoom, since its first hour, that a channel not drawn is not a channel that is
missing — *and that four classes are drawn whatever their length, because they are the
reason to be looking*. A tiler dropping features to keep tiles small would break that
promise silently: a defect would vanish when you zoomed out, which is exactly the
failure the notice exists to prevent, and the map would simply look tidier. So the four
classes are a separate layer that is never thinned.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

from . import paths
from .report import log

NETWORK = paths.PUBLISHED / "rewt_stage1_network.gpkg"
CORRECTIONS = paths.PUBLISHED / "rewt_stage1_corrections.gpkg"
OUT = paths.ROOT / "docs" / "viewer" / "data"

MINZOOM, MAXZOOM = 5, 14

# The four classes that must never be thinned: a stretch that cannot reach the sea, a
# line this project retired, a line it added, and a line it turned round. Every one is
# a reason to be looking at the map rather than scenery on it.
# **A DUPLICATE SUBSET OF `link`, NEVER AN EXCLUSIVE ONE**, and the viewer's fallback
# notice depends on it: it tells a reader that without the kept archive these lines are
# still drawn as part of the general network and only the guarantee is lost. That is
# true because these same rows are also in `link`. If this ever became a partition —
# rows moved out of `link` rather than repeated — the notice would become wrong in the
# dangerous direction, promising a defect is visible when it is not. Two files would
# otherwise assume this independently and neither would say it.
KEPT = (
    "(in_scope AND NOT reaches_tidal) OR retired "
    "OR origin <> 'survey' OR routing_reversed"
)

# WHAT THE TILES CARRY, and what they deliberately do not.
#
# `publisher_id`, `from_node` and `to_node` are dropped. They are three of the five
# highest-cardinality columns in the table — 21 MB of the 32 MB attribute payload
# between them — and nothing on the map styles, filters or labels with any of them.
# Dropping them costs no information that cannot be recovered: rewt-fc checked, and
# `publisher_id` equals `link_id` minus the `os:link/` prefix for 99.3% of survey
# links, while **all 1,446 exceptions carry that GUID in `parent_link_id`** — they are
# the links this project split, which is exactly the class where a reader most needs
# the survey's own feature. So `parent_link_id` is kept and the trim is lossless in
# practice. The full record is in the GeoPackage the release ships.
#
# Measured honestly, this is a small win: 11% off a z6 `link` tile, not the large one
# the cardinality figures suggested. MVT builds its string dictionary per tile, so a
# column with 195,690 distinct values nationally has only as many as the tile holds.
_LINK_COLUMNS = (
    "link_id, source_id, origin, form, name, name_alt, "
    "length_m, basin_id, in_scope, scope_rule, reaches_tidal, seed_node, "
    "routing_reversed, reversed_by_correction, routing_mode, retired, retired_reason, "
    "superseded_by, parent_link_id, screening_elevation_upstream_m, "
    "screening_elevation_downstream_m, screening_fall_m, screening_terrain_verdict"
)

# Columns the map draws IF the build published them. `reaches_sea` arrived with the sea
# network joining the routing graph, and it is a genuinely different question from
# `reaches_tidal` — the two are not nested, because a mouth discharging through a sea
# wall reaches the sea without touching a tidalRiver. Asked for conditionally rather
# than added to the list above, so that a tile build against an older published/ does
# not fail on a column that does not exist yet; the viewer, in turn, offers the
# cross-tabulated theme only when the property is actually in the tiles.
_OPTIONAL_LINK_COLUMNS = ("reaches_sea",)


def link_columns() -> str:
    """The link columns to tile, minus any the published build has not got."""
    import pyogrio

    have = set(pyogrio.read_info(NETWORK, layer="link")["fields"])
    extra = [c for c in _OPTIONAL_LINK_COLUMNS if c in have]
    missing = [c for c in _OPTIONAL_LINK_COLUMNS if c not in have]
    if missing:
        log.detail(f"link has no {', '.join(missing)} — tiled without it, and the "
                   f"viewer will not offer the theme that needs it")
    return _LINK_COLUMNS + ("".join(f", {c}" for c in extra))

# WHY THE NEVER-THINNED LAYER NEEDS A POINT LAYER BESIDE IT.
#
# The archive shipped 679 of 10,229 kept features at z5 while the viewer promised all of
# them at every zoom. MAX_SIZE defaults to 500 KB across ALL layers in a tile together,
# and the national tile ran to 1.2 MB, so GDAL made room by discarding features — from
# `link_kept` as readily as from `link`.
#
# **TWO CAUSES, AND THE FIRST TIME I SPLIT THEM I GOT THE PROPORTIONS BACKWARDS.**
#
# The budget is the larger one. Tiling `link_kept` ALONE at the default budget puts 7,800
# of 10,229 into the z5 tile; sharing a tile with `link`, `basin` and `sea_route` at the
# same budget drops it to 679. So most of the loss was eviction, and raising the limits
# recovers most of it. I first measured 1,100 after raising them and concluded the budget
# barely mattered — the isolated build says otherwise, and rewt-fc's independent 7,792
# from the browser agrees with the isolated build. Trust the two that agree.
#
# The remainder is coordinate quantisation, and that part no flag can reach. MVT snaps
# coordinates to a grid of EXTENT units across the tile; at 53°N a unit is ~184 m at z5,
# and a line shorter than that collapses to zero length and is discarded as degenerate.
# The median kept link is 394 m and a quarter are under 80 m, so this takes about 2,430
# of 10,229 at z5 — a real 24%, not a rounding error. EXTENT=65536 still leaves 908 below
# one unit while inflating every tile. **A 10 m line cannot be drawn where a pixel is
# kilometres wide**, which is why the points below exist.
#
# So the four classes travel twice: as lines, which are the geometry and survive from the
# zoom where they are bigger than a pixel; and as ONE POINT EACH in `link_kept_pt`, which
# cannot collapse and so is complete at every zoom. The map draws the points at low zoom
# and the lines at high, and the promise it prints is then true — as a mark saying a
# defect is here, which is all a national view can honestly claim.
#
# The budget is still raised, because it was also real: with the points added, a national
# tile carrying every defect is worth more than a small one that hides some.
MAX_SIZE = 20_000_000
MAX_FEATURES = 1_000_000


def _run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} failed: {r.stderr.strip()[:400]}")


def build_tiles() -> None:
    """TWO archives, and the split is the whole reason the promise can be kept.

    `rewt.pmtiles` carries the network, the sea routes and the basins. `link` is allowed
    to thin at low zoom — the panel says so, and 195,690 lines cannot all be drawn where
    a pixel is kilometres wide.

    `rewt_kept.pmtiles` carries the four never-thinned classes, as lines and as one point
    each. **They are in a separate archive because sharing a tile with `link` is what was
    dropping them**, and no setting fixed it: tiled beside `link`, the points came out at
    1,317 of 10,229 at z5 with MAX_SIZE at 20 MB and at exactly 1,317 with it at 500 MB —
    the same number, so the limit was never the size. Tiled alone, with everything else
    equal, all 10,229 are present. I could not make GDAL prioritise one layer's features
    over another's inside a tile, so the layers do not share a tile.

    That also serves the first-load weight, rather than fighting it: the national view
    fetches a thinned `link` tile and a small complete `kept` tile, instead of one tile
    forced large enough to hold every line at full detail.
    """
    OUT.mkdir(parents=True, exist_ok=True)

    basin_src = _basins_on_land()
    main = [
        ("link", f"SELECT geom, {link_columns()} FROM link", NETWORK),
        ("sea_route", "SELECT geom, link_id, from_node, to_node, length_m, "
                      "min_depth_m, median_depth_m FROM sea_route", NETWORK),
        ("basin", "SELECT geom, basin_id, label, area_km2, in_scope, scope_reason, "
                  "england_wales_area_km2, outlet_node, provisional FROM basin",
         basin_src),
    ]
    kept = [("link_kept", f"SELECT geom, {link_columns()} FROM link WHERE {KEPT}", NETWORK)]

    _archive(OUT / "rewt.pmtiles", OUT / "_stage.gpkg", main,
             "REWT Stage 1", with_points=False)
    _archive(OUT / "rewt_kept.pmtiles", OUT / "_stage_kept.gpkg", kept,
             "REWT Stage 1 — the classes that are never thinned", with_points=True)


# In data/interim/ and not in published/: published/ is the release payload, and a
# derived convenience for one map layer is not part of it.
BASIN_LAND = paths.INTERIM / "viewer_basin_on_land.gpkg"


def _basins_on_land() -> pathlib.Path:
    """The basin polygons with the sea taken out of them — FOR DRAWING, and only that.

    A basin is delineated on a flow-direction raster, which does not stop at the shore:
    every coastal basin came out with a rectangle of sea attached, and 194,664 km2 of
    basin covered ground of which 15,312 km2 is water. Drawn, that reads as a claim that
    the catchment extends offshore, which it does not.

    The clip is against Boundary-Line's `country_region` polygons for England, Wales and
    Scotland — the same source, and the same layer, already used to decide scope. NOT
    against `high_water`, whose one recorded use is a later stage's coastal work
    (D-029), and not against OpenStreetMap land polygons, which are ODbL and would
    propagate share-alike into everything published here (D-004's situation).

    GB rather than England-and-Wales, because a basin that straddles the border really
    does extend into Scotland and clipping it at the border would delete ground rather
    than water. The clip empties nothing: 0 of 1,049 basins, 0 of the 334 in scope.

    **NOTHING UPSTREAM READS THIS.** `basin.geom` in the network GeoPackage is
    untouched, `area_km2` still measures the unclipped basin, and the scope decision is
    still made on the unclipped overlap — so no figure on the page moves because the map
    got tidier. It costs about four and a half minutes, so it is cached against the
    network's own mtime.
    """
    if (BASIN_LAND.exists()
            and BASIN_LAND.stat().st_mtime >= NETWORK.stat().st_mtime):
        log.detail(f"basin polygons on land — cached, {BASIN_LAND.name}")
        return BASIN_LAND

    import geopandas as gpd
    import shapely

    from .basins import country_polygon

    land = country_polygon(["England", "Wales", "Scotland"])
    frame = gpd.read_file(NETWORK, layer="basin")
    before = frame.area.sum() / 1e6
    frame["geometry"] = frame.geometry.intersection(land)
    # An intersection can hand back a GeometryCollection where a boundary grazes a
    # polygon edge; a GeoPackage layer holds one geometry type, so anything that is not
    # a surface is dropped from the piece rather than the piece from the layer.
    mixed = frame.geometry.geom_type == "GeometryCollection"
    if mixed.any():
        frame.loc[mixed, "geometry"] = frame.loc[mixed, "geometry"].apply(
            lambda g: shapely.union_all([p for p in g.geoms if p.area > 0]))
    empty = int(frame.geometry.is_empty.sum())
    if empty:
        raise RuntimeError(
            f"clipping the basins to land emptied {empty} of them; the clip is for "
            "drawing and must not remove a basin from the map")

    BASIN_LAND.parent.mkdir(parents=True, exist_ok=True)
    BASIN_LAND.unlink(missing_ok=True)
    frame.to_file(BASIN_LAND, layer="basin", driver="GPKG")
    after = frame.area.sum() / 1e6
    log.detail(f"basin polygons clipped to land for drawing — {before:,.0f} km2 to "
               f"{after:,.0f} km2, {before - after:,.0f} km2 of sea and foreshore out, "
               f"none emptied")
    return BASIN_LAND


def _archive(out: pathlib.Path, stage: pathlib.Path,
             layers: list[tuple[str, str, pathlib.Path]], name: str,
             with_points: bool) -> None:
    """Stage the layers into a GeoPackage, then tile the lot in one pass."""
    stage.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    for i, (layer, sql, src) in enumerate(layers):
        args = ["ogr2ogr", "-f", "GPKG"]
        if i:
            args += ["-update", "-append"]
        args += [str(stage), str(src), "-sql", sql, "-nln", layer]
        _run(args)
    if with_points:
        _kept_as_points(stage)

    _run([
        "ogr2ogr", "-f", "PMTiles", str(out), str(stage),
        "-dsco", f"MINZOOM={MINZOOM}", "-dsco", f"MAXZOOM={MAXZOOM}",
        "-dsco", f"MAX_SIZE={MAX_SIZE}", "-dsco", f"MAX_FEATURES={MAX_FEATURES}",
        "-dsco", f"NAME={name}",
        "-dsco", "DESCRIPTION=Rivers of England and Wales, Temporally — Stage 1. "
                 "Makes no historical claim.",
    ])
    stage.unlink(missing_ok=True)
    log.done(f"{out.relative_to(paths.ROOT)} — {out.stat().st_size / 1e6:,.1f} MB, "
             f"z{MINZOOM}-{MAXZOOM}, layers "
             + " / ".join([l for l, _, _ in layers]
                          + (["link_kept_pt"] if with_points else [])))


# The small layers, whole. Each is small enough to fetch entire, and each is a finding
# rather than scenery, so none of them is tiled or thinned.
#
# `dead_ends` carries the IN-SCOPE rows only — 1,281 of the 2,583 non-tidal sinks. That
# is not a convenience: `audit` defines a defect as `in_scope AND terminus <> 'tidal'`,
# the viewer labels the layer "dead ends that are the work" and prints that same 1,281
# beside it, and shipping all 2,583 under that count would put a number next to a
# different set of things. The 1,302 out-of-scope sinks are in `audit/dead_ends.json`,
# which the release publishes whole.
VECTORS = (
    ("connectors", NETWORK, "SELECT geom, link_id, name, form, length_m, parent_link_id "
                            "FROM link WHERE origin = 'connector'"),
    ("reversals", NETWORK, "SELECT geom, link_id, name, form, length_m, "
                           "reversed_by_correction FROM link WHERE routing_reversed"),
    ("retired", NETWORK, "SELECT geom, link_id, name, form, length_m, retired_reason, "
                         "superseded_by FROM link WHERE retired"),
    ("terminus", NETWORK, "SELECT * FROM terminus"),
    ("seeds", NETWORK, "SELECT * FROM terminus WHERE is_crawl_seed"),
    ("sea_entry", NETWORK, "SELECT * FROM sea_entry"),
    ("corrections", CORRECTIONS, "SELECT * FROM correction"),
)


def build_layers() -> None:
    """The nine small layers and the figures the panel reads."""
    OUT.mkdir(parents=True, exist_ok=True)

    for name, src, sql in VECTORS:
        out = OUT / f"{name}.geojson"
        out.unlink(missing_ok=True)
        _run(["ogr2ogr", "-f", "GeoJSON", str(out), str(src), "-sql", sql,
              "-t_srs", "EPSG:4326", "-lco", "COORDINATE_PRECISION=6",
              "-lco", "RFC7946=YES"])

    # Already 4326 and already a FeatureCollection: copied, not rebuilt, so the map and
    # the audit cannot drift apart.
    shutil.copyfile(paths.PUBLISHED / "audit" / "refused_crossings.geojson",
                    OUT / "refused_crossings.geojson")

    _dead_ends()
    _refused_connectors()
    _summary()
    total = sum(f.stat().st_size for f in OUT.glob("*.geojson")) / 1e6
    log.done(f"docs/viewer/data/ — 9 GeoJSON layers, {total:,.1f} MB, and summary.json")


def _dead_ends() -> None:
    """The defect list as points, from the audit's own file rather than from the DB."""
    rows = json.loads((paths.PUBLISHED / "audit" / "dead_ends.json").read_text())
    defects = [r for r in rows if r.get("in_scope")]
    from pyproj import Transformer
    to_wgs = Transformer.from_crs(27700, 4326, always_xy=True)
    feats = []
    for r in defects:
        lon, lat = to_wgs.transform(r["easting"], r["northing"])
        props = {k: v for k, v in r.items() if k not in ("easting", "northing")}
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point",
                                   "coordinates": [round(lon, 6), round(lat, 6)]}})
    (OUT / "dead_ends.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}, allow_nan=False))
    log.detail(f"dead_ends.geojson — {len(feats):,} in-scope defects of {len(rows):,} "
               f"non-tidal sinks; the rest are out of scope and stay in audit/")


def _refused_connectors() -> None:
    """The connectors refused for climbing, as points — the other half of a pair.

    THIS LAYER IS ONLY HALF A STORY ON ITS OWN, and that is why it is exported next to
    the `connector_climbs` findings rather than instead of them. A map showing the
    refusals alone says the veto refused every connector that climbed and reinstated
    none, which is a stronger and more wrong claim than showing neither. The viewer
    draws the two together: refused for climbing, and applied despite climbing on the
    warrant of a surveyed structure. Raised by rewt-d3, who was right that a red mark on
    both sets would make a reader assume the opposite of what happened to half of them.

    From `repair.json`, which the audit writes, rather than from the database: the same
    rule as `_dead_ends`, so the map and the audit cannot drift apart.
    """
    src = paths.PUBLISHED / "audit" / "repair.json"
    if not src.exists():
        log.detail("repair.json absent — no refused-connector layer")
        return
    from pyproj import Transformer

    rows = json.loads(src.read_text()).get("findings", [])
    climbs = [r for r in rows
              if "climbs" in (r.get("detail") or "")
              and r.get("easting") is not None and r.get("northing") is not None]
    to_wgs = Transformer.from_crs(27700, 4326, always_xy=True)
    feats = []
    for r in climbs:
        lon, lat = to_wgs.transform(r["easting"], r["northing"])
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            # `detail` is the audit's own sentence, printed verbatim. It carries the rise
            # and the reason, and rewording it here would be a second opinion wearing the
            # audit's name.
            "properties": {"subject": r.get("subject"), "detail": r.get("detail"),
                           "basin_id": r.get("basin_id")},
        })
    (OUT / "refused_connectors.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}, allow_nan=False))
    log.detail(f"refused_connectors.geojson — {len(feats):,} refused for climbing, "
               f"of {len(rows):,} skipped corrections")


def _summary() -> None:
    """The figures the panel prints, and the basin table it flies from.

    Read from `published/`, never recomputed here: a second arithmetic over the same
    tables is how two reachability figures came to disagree (D-058). If a figure is
    absent the viewer names it on the page rather than printing a plausible zero, so
    nothing here is defaulted.
    """
    import geopandas as gpd
    import pyogrio

    audit = json.loads((paths.PUBLISHED / "audit" / "audit.json").read_text())
    prov = json.loads((paths.PUBLISHED / "provenance.json").read_text())
    reach = audit["sections"]["reachability"]
    sea = audit["sections"].get("reachability_tested_against_the_sea", {})

    con_counts = {}
    for layer, key in (("link", "links"), ("node", "nodes"), ("basin", "basins"),
                       ("terminus", "tidal_nodes"), ("sea_entry", "sea_entries"),
                       ("sea_route", "sea_routes")):
        con_counts[key] = int(pyogrio.read_info(NETWORK, layer=layer)["features"])

    link = gpd.read_file(NETWORK, layer="link", read_geometry=False,
                         columns=["origin", "routing_reversed", "retired"])
    counts = {
        **con_counts,
        "connectors": int((link["origin"] == "connector").sum()),
        "reversals": int(link["routing_reversed"].sum()),
        "retired": int(link["retired"].sum()),
        "corrections": int(pyogrio.read_info(CORRECTIONS, layer="correction")["features"]),
        "seeds": int(gpd.read_file(NETWORK, layer="terminus", read_geometry=False,
                                   columns=["is_crawl_seed"])["is_crawl_seed"].sum()),
        "dead_ends_defect": audit["sections"]["dead_ends"]["defects"],
    }

    # A point to fly to. `representative_point` rather than a centroid: a basin wrapping
    # an estuary has its centroid in the water outside it.
    basins = gpd.read_file(NETWORK, layer="basin", columns=["basin_id", "outlet_node"])
    pts = basins.set_geometry(basins.geometry.representative_point()).to_crs(4326)
    where = {r.basin_id: (round(r.geometry.x, 5), round(r.geometry.y, 5))
             for r in pts.itertuples()}
    has_outlet = {r.basin_id: r.outlet_node is not None for r in basins.itertuples()}

    rows = json.loads((paths.PUBLISHED / "audit" / "basin_reach.json").read_text())
    table = []
    for r in rows:
        if not r.get("in_scope"):
            continue
        lon, lat = where.get(r["basin_id"], (None, None))
        table.append({
            "basin_id": r["basin_id"], "label": r.get("label"),
            "share": r.get("share"), "km": r.get("km"),
            "unreached_km": r.get("unreached_km"),
            "shortfall_reason": r.get("shortfall_reason"),
            "has_outlet": has_outlet.get(r["basin_id"], False),
            "lon": lon, "lat": lat,
        })

    # The audit's own findings, which the panel lists and flies to. They arrive in
    # EPSG:27700, like everything else in this project; 4326 happens here, at export,
    # and nowhere earlier. `detail` is the audit's sentence, printed verbatim — this
    # panel reports what the audit said, so rewording it here would be a second opinion
    # wearing the audit's name.
    findings = [f for f in audit.get("findings", [])
                if f.get("easting") is not None and f.get("northing") is not None]
    if findings:
        fp = gpd.GeoSeries(gpd.points_from_xy([f["easting"] for f in findings],
                                              [f["northing"] for f in findings]),
                           crs=27700).to_crs(4326)
        for f, pt in zip(findings, fp):
            f["lon"], f["lat"] = round(pt.x, 5), round(pt.y, 5)
    findings = [{"kind": f["kind"], "detail": f["detail"], "subject": f.get("subject"),
                 "basin_id": f.get("basin_id"), "lon": f["lon"], "lat": f["lat"]}
                for f in findings]

    # WHAT EACH LAYER IS, COMPUTED RATHER THAN WRITTEN. The viewer's legend used to
    # restate this in its own words, and D-095 is about what that costs: a paraphrase
    # that reverses is indistinguishable from one that is still true, so the panel
    # asserted the opposite of a corrected sentence two inches above the corrected one.
    # The remedy is that the viewer prints these rather than saying them.
    #
    # And the sea_route sentence is MEASURED at build time, not asserted. The legend
    # claimed "a tree not a loop, every line the only way between the coasts it joins"
    # from the day it was written and nobody tested it until visualisation did — it was
    # true, but it was true by luck as far as the file was concerned. Now a cycle would
    # CHANGE the sentence rather than silently falsify it.
    layers = {"sea_route": _sea_route_shape()}

    summary = {
        "counts": counts,
        "layers": layers,
        "citation": _citation(),
        "findings": findings,
        "reachability": reach,
        "reachability_tested_against_the_sea": sea,
        "basins": table,
        "provenance": {"built_at": prov["built_at"],
                       "config_fingerprint": prov["config_fingerprint"],
                       "sources": {k: v["issue"] for k, v in prov["sources"].items()}},
        "attribution": _attribution(prov),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False))
    kinds = len({f["kind"] for f in findings})
    log.detail(f"summary.json — {len(table):,} in-scope basins, each with a point to "
               f"fly to, {len(counts)} counts, and {len(findings):,} audit findings "
               f"across {kinds} kinds")


def _sea_route_shape() -> dict:
    """Describe the sea network from the sea network, at the moment it is published.

    A spanning tree over the mouths, or not — and if not, the sentence says so. The
    claim is about topology, so it is computed from topology: `edges - (nodes -
    components)` is the number of independent cycles, and zero of them means every line
    really is the only way between the coasts it joins.
    """
    import geopandas as gpd
    import networkx as nx

    routes = gpd.read_file(NETWORK, layer="sea_route", read_geometry=False,
                           columns=["from_entry", "to_entry"])
    g = nx.Graph()
    g.add_edges_from(zip(routes["from_entry"], routes["to_entry"]))
    nodes, edges = g.number_of_nodes(), g.number_of_edges()
    comps = nx.number_connected_components(g) if nodes else 0
    excess = edges - (nodes - comps) if nodes else 0

    if comps == 1 and excess == 0:
        shape = (f"A spanning tree over {nodes:,} sea entries: one component, "
                 f"{edges:,} routes, and no cycle anywhere — so every line is the only "
                 "way between the coasts it joins.")
    elif excess == 0:
        shape = (f"A forest over {nodes:,} sea entries in {comps:,} components, "
                 f"{edges:,} routes, no cycle within any of them.")
    else:
        shape = (f"{nodes:,} sea entries, {edges:,} routes, {comps:,} component(s) and "
                 f"{excess:,} independent cycle(s) — it is NO LONGER A TREE, and any "
                 "claim that a line is the only way between two coasts is false.")

    return {
        "entries": nodes, "routes": edges, "components": comps, "cycles": excess,
        "shape": shape,
        # THE DISTINGUISHING SENTENCE, requested by visualisation once the comparison
        # existed (D-099). Both authors of the two sea networks agree the mesh does not
        # replace this one today, and the figure is theirs rather than mine.
        "against_the_mesh": (
            "Not superseded by the H3 routing mesh. Measured on 4 September 2026, the "
            "published mesh reaches 2,432 of these 4,184 entries — 58.1% — leaving "
            "5,557 of 11,958 river mouths in no published cell. That is a lower bound: "
            "the comparison used the aggregated res-6 layer, clipped to the sightline "
            "cells, and the routing grid is finer."
        ),
    }


def _citation() -> dict:
    """What to cite, READ FROM CITATION.cff rather than written out again here.

    The first draft of the viewer's citation box was typed by hand and got the publisher
    wrong, invented nothing else only because there was nothing else to invent, and
    would have gone on being wrong through every version bump. CITATION.cff is itself
    generated from .zenodo.json for exactly that reason — authorship is declared once —
    and a third copy in a JavaScript template string would have been the drift the
    generation exists to prevent.

    The file is not under docs/, so the page cannot fetch it; it is carried into
    summary.json here, at the same build that reads the audit.
    """
    import yaml

    cff = yaml.safe_load((paths.ROOT / "CITATION.cff").read_text())
    doi = next((i for i in cff.get("identifiers", [])
                if i.get("type") == "doi"), {})
    return {
        "title": " ".join(cff["title"].split()),
        "version": cff.get("version"),
        "licence": cff.get("license"),
        "authors": [f"{a['family-names']}, {a['given-names']}"
                    for a in cff.get("authors", [])],
        "orcids": [a["orcid"] for a in cff.get("authors", []) if a.get("orcid")],
        "affiliations": [a["affiliation"] for a in cff.get("authors", [])
                         if a.get("affiliation")],
        "doi": doi.get("value"),
        "doi_note": doi.get("description"),
        # The .cff's own warning about citing the concept DOI rather than the edition.
        # Carried whole: it is the point of the box, not a caption on it.
        "message": " ".join(cff.get("message", "").split()),
    }


def _attribution(prov: dict) -> str:
    """The credit line, composed from the manifest and from nothing else.

    The first version of this was a hand-written sentence naming OS, EMODnet and the
    Trust, and `test_no_url_is_hard_coded_in_the_code` refused it — correctly, and for
    a larger reason than the URL it caught. It would have been a THIRD rendering of an
    obligation that already has two (`published/ATTRIBUTION.md` and
    `docs/_data/sources.yml`), maintained by hand, on a page carrying the project's
    headline figures. `release.attribution_drift()` checks the other two against
    `conf/sources.yml`; this one cannot drift because it is not written down.

    Only the sources this build actually consumed are credited: `provenance.json`
    records what was fetched, and crediting a registered-but-unused source would be a
    claim about the data that is not true.
    """
    from . import config

    used = set(prov.get("sources", {}))
    reg = {s.id: s for s in config.sources()}
    # Deduplicated: the four Ordnance Survey products carry one identical statement,
    # and discharging it once is what OGL asks for. Printing it four times credits
    # nobody extra and reads as a bug.
    lines: list[str] = []
    for i in sorted(used):
        if i in reg and reg[i].attribution not in lines:
            lines.append(reg[i].attribution)
    unknown = sorted(used - set(reg))
    if unknown:
        raise RuntimeError(
            f"provenance.json names source(s) absent from conf/sources.yml: "
            f"{', '.join(unknown)}. An uncredited input cannot be published."
        )
    return " ".join(lines) + (
        " Bathymetry is NOT for navigation. This is Stage 1: it makes no historical "
        "claim whatever."
    )


def pack() -> pathlib.Path:
    """Tar what the map reads, for the release to carry and `pages.yml` to fetch.

    **Why a release asset and not a commit, and not a CI build.** The workflow that
    deploys the site cannot build this — it has neither the sources nor the hours. And
    it cannot be committed: `.gitignore`'s first rule. So it travels as a release asset,
    the workflow downloads it server-side, and Pages serves it. That last hop matters:
    release assets send no CORS header, so a browser cannot read one directly, but
    Pages both sends CORS and honours Range — which is what a PMTiles archive needs to
    be read a viewport at a time rather than downloaded whole.

    Uncompressed on purpose. PMTiles is gzipped internally and a second pass buys
    nothing; a tar that CI can stream and unpack is worth more than a few per cent.
    """
    import tarfile

    out = paths.PUBLISHED / "viewer-data.tar"
    # NOT release.json. It is written by pages.yml AFTER this asset is unpacked, because
    # the deploy is the only thing that knows which release the data was attached to —
    # the build cannot know, since the tag does not exist until after the build.
    #
    # It is excluded rather than merely not created here, because this function sweeps
    # the directory by suffix and will pick up whatever a local preview left behind. It
    # already did: a fixture written by hand at 08:40 to test the citation box shipped
    # inside v0.2.0-alpha declaring itself v0.1.1-alpha. Harmless in the deploy, where
    # the workflow overwrites it a moment later, and wrong for anyone who reads the
    # asset directly — which is the exact failure that file exists to prevent, packaged
    # inside the artefact.
    # PACKED FROM A MANIFEST, NOT SWEPT FROM A DIRECTORY.
    #
    # Excluding `release.json` by name fixed the instance; the fault was the sweep. A
    # glob over suffixes ships whatever happens to be lying in the directory, and its
    # output is indistinguishable from a correct manifest's — which is why the fixture
    # went unnoticed into a published release. **The build knows exactly what it wrote**,
    # so it should say so, and anything else present is somebody's leftover.
    expected = (
        ["rewt.pmtiles", "rewt_kept.pmtiles", "summary.json"]
        + [f"{name}.geojson" for name, _, _ in VECTORS]
        + ["dead_ends.geojson", "refused_crossings.geojson",
           "refused_connectors.geojson"]
    )
    missing = [n for n in expected if not (OUT / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"{OUT.relative_to(paths.ROOT)} is missing {', '.join(missing)}; run "
            "`rewt viewer-data`. The tar is built from a manifest, so a file the build "
            "should have written and did not is an error rather than a smaller archive."
        )
    files = [OUT / n for n in expected]

    # Named, never silently left behind — a stray file is usually a leftover and
    # occasionally something the manifest has forgotten.
    strays = sorted(f.name for f in OUT.iterdir()
                    if f.is_file() and f.name not in set(expected))
    if strays:
        log.detail(f"not packed, not in the manifest: {', '.join(strays)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w") as tar:
        for f in files:
            tar.add(f, arcname=f.name)
    log.done(f"published/viewer-data.tar — {len(files)} files, "
             f"{out.stat().st_size / 1e6:,.1f} MB")
    return out


# The four classes `link_kept` carries, named here so the check can report which one a
# reader would have lost. This restates KEPT's clauses in words and nothing else.
NEVER_THINNED = (
    "in scope and not reaching tidal water — the defect",
    "retired — the audit trail",
    "geometry this project added (origin is not 'survey')",
    "routing reversed by a correction",
)


def verify(archive: pathlib.Path | None = None) -> None:
    """Count what is IN the archive at every zoom, and refuse a thinned `link_kept`.

    **This exists because a flag was trusted and the features went anyway.** The build
    named a never-thinned layer, the viewer printed a promise about it at every zoom,
    and the archive shipped 679 of 10,229 at z5 — because GDAL's per-tile budget
    discards features across all layers together and says nothing. Every part was
    plausible on its own and the assembly was false, which is this repository's own
    recurring failure and the reason `AGENTS.md` says to check the thing rather than
    the aggregate.

    So the check reads the built archive back through GDAL, zoom by zoom, and compares
    against the source. It is deliberately not a re-derivation of the same arithmetic:
    it opens the file that will be published and counts what a browser would receive.
    """
    archive = archive or (OUT / "rewt_kept.pmtiles")
    if not archive.exists():
        raise FileNotFoundError(f"{archive} does not exist; run `rewt viewer-data`")

    expected = int(subprocess.run(
        ["ogrinfo", "-q", "-sql", f"SELECT count(*) AS n FROM link WHERE {KEPT}",
         str(NETWORK)], capture_output=True, text=True, check=True,
    ).stdout.split("n (Integer) = ")[1].split()[0])

    log.info(f"link_kept must carry {expected:,} features at EVERY zoom "
             f"{MINZOOM}-{MAXZOOM} — the four classes are:")
    for c in NEVER_THINNED:
        log.detail(c)

    def count(layer: str, z: int) -> int:
        r = subprocess.run(
            ["ogrinfo", "-oo", f"ZOOM_LEVEL={z}", "-q", str(archive), layer],
            capture_output=True, text=True)
        return r.stdout.count("OGRFeature")

    # `link_kept_pt` IS THE PROMISE. Points cannot quantise away, so this must be
    # complete at every zoom and a shortfall is a failure. The line layer is reported
    # beside it as information: it thins at low zoom for a reason no flag can change,
    # and the map draws the points there instead.
    short: list[str] = []
    log.detail(f"{'zoom':<6}{'points':>10}{'lines':>10}   of {expected:,}")
    for z in range(MINZOOM, MAXZOOM + 1):
        pt, ln = count("link_kept_pt", z), count("link_kept", z)
        # A tile clips a line at its edge and returns both halves, so a feature crossing
        # a boundary counts twice. Short is the failure; over is geometry.
        log.detail(f"z{z:<5}{pt:>10,}{ln:>10,}   {'ok' if pt >= expected else 'SHORT'}")
        if pt < expected:
            short.append(f"z{z}: {pt:,} of {expected:,} points "
                         f"({100 * (1 - pt / expected):.0f}% absent)")

    if short:
        raise RuntimeError(
            "THE NEVER-THINNED CLASSES ARE NOT ALL IN THE ARCHIVE, and the viewer "
            "promises them at every zoom:\n  " + "\n  ".join(short) + "\n"
            "These are points and cannot collapse, so this is a budget: raise MAX_SIZE "
            "and MAX_FEATURES in rewt/tiles.py. A national tile that will not fit a "
            "budget wants a bigger tile, never fewer defects."
        )
    log.done(f"link_kept_pt carries all {expected:,} never-thinned classes at every "
             f"zoom {MINZOOM}-{MAXZOOM}")


def _kept_as_points(stage: pathlib.Path) -> None:
    """One point per never-thinned link, so the four classes survive every zoom.

    A point has no length to lose, so quantisation cannot discard it. The point is taken
    ON the line rather than at its bounding-box centre, so it always falls on the channel
    it marks — a centroid of a curved reach can sit on the far bank, or on land.
    """
    import geopandas as gpd

    kept = gpd.read_file(stage, layer="link_kept")
    if kept.empty:
        raise RuntimeError("link_kept is empty; the never-thinned layer would be a lie")
    pts = kept.copy()
    pts["geometry"] = kept.geometry.interpolate(0.5, normalized=True)
    pts.to_file(stage, layer="link_kept_pt", driver="GPKG")
    log.detail(f"link_kept_pt — {len(pts):,} points, one per never-thinned link, "
               "so the four classes cannot quantise away at low zoom")
