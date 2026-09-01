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
LINK_COLUMNS = (
    "link_id, source_id, origin, form, name, name_alt, "
    "length_m, basin_id, in_scope, scope_rule, reaches_tidal, seed_node, "
    "routing_reversed, reversed_by_correction, routing_mode, retired, retired_reason, "
    "superseded_by, parent_link_id, screening_elevation_upstream_m, "
    "screening_elevation_downstream_m, screening_fall_m, screening_terrain_verdict"
)

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

    main = [
        ("link", f"SELECT geom, {LINK_COLUMNS} FROM link", NETWORK),
        ("sea_route", "SELECT geom, link_id, from_node, to_node, length_m, "
                      "min_depth_m, median_depth_m FROM sea_route", NETWORK),
        ("basin", "SELECT geom, basin_id, label, area_km2, in_scope, scope_reason, "
                  "england_wales_area_km2, outlet_node, provisional FROM basin", NETWORK),
    ]
    kept = [("link_kept", f"SELECT geom, {LINK_COLUMNS} FROM link WHERE {KEPT}", NETWORK)]

    _archive(OUT / "rewt.pmtiles", OUT / "_stage.gpkg", main,
             "REWT Stage 1", with_points=False)
    _archive(OUT / "rewt_kept.pmtiles", OUT / "_stage_kept.gpkg", kept,
             "REWT Stage 1 — the classes that are never thinned", with_points=True)


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

    summary = {
        "counts": counts,
        "reachability": reach,
        "reachability_tested_against_the_sea": sea,
        "basins": table,
        "provenance": {"built_at": prov["built_at"],
                       "config_fingerprint": prov["config_fingerprint"],
                       "sources": {k: v["issue"] for k, v in prov["sources"].items()}},
        "attribution": _attribution(prov),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False))
    log.detail(f"summary.json — {len(table):,} in-scope basins, each with a point to "
               f"fly to, and {len(counts)} counts")


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
    files = sorted(f for f in OUT.iterdir() if f.suffix in (".pmtiles", ".geojson", ".json"))
    if not files:
        raise FileNotFoundError(
            f"{OUT.relative_to(paths.ROOT)} is empty; run `rewt viewer-data` first"
        )
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
