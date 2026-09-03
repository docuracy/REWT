#!/usr/bin/env python3
"""The local viewer's server: `published/` on a socket, for looking at the place.

    .venv/bin/python tools/viewer/server.py            # http://127.0.0.1:8010/
    .venv/bin/python tools/viewer/server.py --port N
    .venv/bin/python tools/viewer/server.py --fetch-counties

Run from the repository root.

WHY THIS FILE EXISTS AT ALL, which is the part worth reading. `tools/viewer/viewer.js`
asks nine endpoints of its own and, until today, nothing in this repository served any
of them: the server had been spun up ad hoc, used, and lost before it ever reached the
index. `git log --diff-filter=D` over this directory is empty, so it was never even
deleted — it simply never existed as far as the repository was concerned, while a
57 KB client and an 18 KB README described it in detail. Stephen's ruling: "The server
we were using before was spun up ad hoc. It needs to be controlled as part of the repo."
An ad hoc server is exactly the thing that gets written, used and lost, and it is also
the thing that ends up rooted at a parent directory serving somebody's `.env` for
nineteen hours. Both halves of that are why this is a file and not a shell history.

FOUR CONSTRAINTS, none of them negotiable here.

**It reads `published/`, NEVER the database.** AGENTS.md: DuckDB is single-writer and a
read-only connection blocks writers, so a served map holding one fails the build — and
the failure presents as a broken build rather than as a lock, which is the worst
possible symptom because it sends you looking in the wrong place. Everything below
comes from `published/rewt_stage1_network.gpkg`,
`published/rewt_stage1_corrections.gpkg` and `published/audit/*.json`. Those are files.
They take no lock, they are what a consumer of this project actually gets, and they are
rewritten often enough that this server watches their mtimes and says so.

**It binds 127.0.0.1, explicitly.** `http.server`'s default is `0.0.0.0`, which is every
interface on the network and not merely this machine. TEAM.md's rule, and it has to be
typed to be true.

**It serves THIS DIRECTORY, never the repository root.** The one exception is
`/published/...`, which is mounted read-only and by an explicit allow-list of suffixes
rather than by widening the document root — see `_published`. A server rooted one level
too high is how `curl http://127.0.0.1:8899/REWT/.env` returned 935 bytes on this
machine this afternoon.

**`/api/reload` re-reads `published/` from disk. It does not run the build, and it must
not.** The viewer polls `/api/freshness.json` every thirty seconds and offers a reload
when the files under it have changed, which is the whole of the feature: you rebuild in
a terminal, the map notices, you press the button. An endpoint that let a page trigger a
build would be a write path from a browser into a single-writer database, reachable by
any script on any page the browser happens to have open. The decision is recorded here
because the endpoint's name does not say which of the two it is, and the next person to
read it should not have to guess.

WHAT IT DOES NOT DO. It does not write: not to the database, not to `published/`, not
to `data/`. Its only writes are the county tile cache under `tools/viewer/cache/`,
which is gitignored, and the county polygon download that `--fetch-counties` performs
against a declared and checksummed source.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import sys
import threading
import time
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLISHED = ROOT / "published"
AUDIT = PUBLISHED / "audit"

# The build's own definitions, imported rather than restated. A second arithmetic over
# the same tables is how two reachability figures came to disagree (D-058), and the
# layer definitions below are the same SQL the release runs — so the local map and the
# deployed one cannot drift apart without somebody editing `rewt/tiles.py`.
# `rewt.tiles` opens no database at import; it holds paths, SQL and two helpers.
sys.path.insert(0, str(ROOT))
from rewt import tiles as build                                   # noqa: E402

NETWORK = build.NETWORK
CORRECTIONS = build.CORRECTIONS

# The four classes that are drawn whatever their length, in the build's own words. The
# viewer's `thinning.never_thinned` list is the prose form of this expression and the
# two must say the same thing; this is the one that decides what is drawn.
KEPT = ("(in_scope AND NOT reaches_tidal) OR retired "
        "OR origin <> 'survey' OR routing_reversed")

MAX_FEATURES = 60000        # the cap the viewer's `meta.truncated` reports against


# ── published/, read once and re-read on request ─────────────────────────────

class Published:
    """Everything the endpoints serve, cached, with the mtimes it was read at.

    A long-running reader of files that are rewritten by a build MUST notice when they
    change underneath it — AGENTS.md says so of this tool by name. So every read
    records the stamp it was taken at, `/api/freshness.json` compares that stamp to the
    directory now, and the page says plainly that it is showing an older network rather
    than quietly showing one.
    """

    def __init__(self) -> None:
        # RE-ENTRANT, and it has to be: `counts()` is built while holding this lock and
        # its builder asks `frame()` and `audit()`, which take it again. A plain Lock
        # deadlocked the very first request and logged nothing at all, because the log
        # line is written when the response is — the server looked like a slow read of
        # a 218 MB file rather than like a bug.
        self._lock = threading.RLock()
        self._cache: dict[str, object] = {}
        self.stamp = self.disk_stamp()
        self.loaded_at = time.time()

    @staticmethod
    def disk_stamp() -> str:
        """A fingerprint of published/ as it is on disk right now."""
        parts = []
        for p in sorted(PUBLISHED.rglob("*")):
            if p.is_file():
                st = p.stat()
                parts.append(f"{p.relative_to(PUBLISHED)}:{st.st_mtime_ns}:{st.st_size}")
        return str(hash("\n".join(parts)))

    def reload(self) -> None:
        with self._lock:
            self._cache.clear()
            self.stamp = self.disk_stamp()
            self.loaded_at = time.time()

    def cached(self, key, build_fn):
        with self._lock:
            if key not in self._cache:
                self._cache[key] = build_fn()
            return self._cache[key]

    # ── the files ────────────────────────────────────────────────────────────

    def audit(self) -> dict:
        return self.cached("audit", lambda: json.loads((AUDIT / "audit.json").read_text()))

    def json_file(self, name: str):
        return self.cached(f"json:{name}", lambda: json.loads((AUDIT / name).read_text()))

    def provenance(self) -> dict:
        return self.cached(
            "prov", lambda: json.loads((PUBLISHED / "provenance.json").read_text()))

    # ── the GeoPackage ───────────────────────────────────────────────────────

    def frame(self, source: Path, layer: str, columns=None, geometry=True, bbox=None):
        """One layer, or one bounding box of it, in the file's own CRS (EPSG:27700).

        A bbox read is NOT cached: it is a different question every time and the
        GeoPackage's spatial index answers it in hundredths of a second.
        """
        import pyogrio

        if bbox is not None:
            return pyogrio.read_dataframe(source, layer=layer, columns=columns,
                                          read_geometry=geometry, bbox=bbox)
        key = f"gpkg:{source.name}:{layer}:{columns}:{geometry}"
        return self.cached(key, lambda: pyogrio.read_dataframe(
            source, layer=layer, columns=columns, read_geometry=geometry))

    def counts(self) -> dict:
        return self.cached("counts", self._counts)

    def _counts(self) -> dict:
        """The panel's counts, by the build's own definitions in rewt/tiles.py."""
        import pyogrio

        out = {}
        for layer, key in (("link", "links"), ("node", "nodes"), ("basin", "basins"),
                           ("terminus", "tidal_nodes"), ("sea_entry", "sea_entries"),
                           ("sea_route", "sea_routes")):
            out[key] = int(pyogrio.read_info(NETWORK, layer=layer)["features"])

        link = self.frame(NETWORK, "link", geometry=False,
                          columns=["origin", "routing_reversed", "retired"])
        out["connectors"] = int((link["origin"] == "connector").sum())
        out["reversals"] = int(link["routing_reversed"].sum())
        out["retired"] = int(link["retired"].sum())
        out["corrections"] = int(
            pyogrio.read_info(CORRECTIONS, layer="correction")["features"])
        out["seeds"] = int(self.frame(NETWORK, "terminus", geometry=False,
                                      columns=["is_crawl_seed"])["is_crawl_seed"].sum())

        basin = self.frame(NETWORK, "basin", geometry=False,
                           columns=["in_scope", "outlet_node"])
        out["basins_in_scope"] = int(basin["in_scope"].sum())
        out["no_outlet_in_scope"] = int(
            (basin["in_scope"] & basin["outlet_node"].isna()).sum())

        out["dead_ends_defect"] = self.audit()["sections"]["dead_ends"]["defects"]
        out["dead_ends_tidal"] = len(self.dead_ends_tidal())
        out["findings"] = len(self.findings())

        # THE BASIN LIST DOES NOT ACCOUNT FOR EVERY DEAD END, and the panel says so —
        # but only if it is given the number. A dead end is in scope because its
        # arriving link is, not because its node sits in an in-scope basin, and tidal
        # water is masked out of the DEM so an estuarine node sits in no basin at all.
        # Without this the list quietly holds fewer defects than the headline count and
        # nothing on the screen explains the difference.
        node_basin = dict(zip(*self.frame(NETWORK, "node", geometry=False,
                                          columns=["node_id", "basin_id"])
                              [["node_id", "basin_id"]].values.T.tolist()))
        defects = [r for r in self.json_file("dead_ends.json") if r.get("in_scope")]
        out["dead_ends_no_basin"] = sum(
            1 for r in defects if node_basin.get(r["node_id"]) is None)
        return out

    def basin_table(self) -> list[dict]:
        """The worst-first basin list, with a point to fly to.

        The share lives in `audit/basin_reach.json` and the geometry in the GeoPackage,
        so the join happens here. `representative_point` rather than a centroid, in the
        build's own words: a basin wrapping an estuary has its centroid in the water
        outside it — which for the two amalgams found this afternoon is not a nicety.
        """
        return self.cached("basin_table", self._basin_table)

    def _basin_table(self) -> list[dict]:
        basins = self.frame(NETWORK, "basin", columns=["basin_id", "outlet_node"])
        pts = basins.set_geometry(basins.geometry.representative_point()).to_crs(4326)
        where = {r.basin_id: (round(r.geometry.x, 5), round(r.geometry.y, 5))
                 for r in pts.itertuples()}
        has_outlet = {r.basin_id: r.outlet_node is not None
                      for r in basins.itertuples()}
        table = []
        for r in self.json_file("basin_reach.json"):
            if not r.get("in_scope"):
                continue
            lon, lat = where.get(r["basin_id"], (None, None))
            table.append({"basin_id": r["basin_id"], "label": r.get("label"),
                          "share": r.get("share"), "km": r.get("km"),
                          "unreached_km": r.get("unreached_km"),
                          "dead_ends": r.get("dead_ends"),
                          "shortfall_reason": r.get("shortfall_reason"),
                          "has_outlet": has_outlet.get(r["basin_id"], False),
                          "lon": lon, "lat": lat})
        # WORST FIRST, AND A BASIN WITH NO SHARE IS NOT THE WORST — it is unmeasured,
        # which is a different thing and belongs at the bottom rather than the top. The
        # first sort put `None` at -1 and headed the list with 84 nameless basins
        # holding 0.0 km, burying the finding the list exists to surface. Ties break on
        # length descending: PLAN.md §6's "a national 97% hides a basin at 40%" is about
        # a basin with water in it.
        table.sort(key=lambda b: (b["share"] is None,
                                  b["share"] if b["share"] is not None else 0,
                                  -(b["km"] or 0)))
        return table

    def dead_ends_tidal(self):
        """In-scope tidal termini with nothing flowing out of them — the correct case.

        DERIVED HERE, AND CHECKED, because it is the one layer the release does not
        publish as a file. The audit counts it as `dead_ends.at_tidal_water`; this
        reproduces the set by asking the published network the same question — a
        terminus at tidal water, in scope, that no link leaves. Where the two disagree
        the count beside the layer is THIS one, because it is the set actually drawn,
        and `warnings` in /api/summary.json says the audit differs. A mark count that
        describes a different set from the marks is the failure D-070 is about.
        """
        return self.cached("dead_ends_tidal", self._dead_ends_tidal)

    def _dead_ends_tidal(self):
        term = self.frame(NETWORK, "terminus")
        link = self.frame(NETWORK, "link", geometry=False,
                          columns=["from_node", "retired"])
        leaves = set(link.loc[~link["retired"].astype(bool), "from_node"])
        node = self.frame(NETWORK, "node", geometry=False,
                          columns=["node_id", "basin_in_scope"])
        in_scope = set(node.loc[node["basin_in_scope"].astype(bool), "node_id"])
        keep = term["node_id"].isin(in_scope) & ~term["node_id"].isin(leaves)
        return term[keep]

    def findings(self) -> list[dict]:
        """The audit's findings that have a place, in 4326. `detail` verbatim."""
        return self.cached("findings", self._findings)

    def _findings(self) -> list[dict]:
        import geopandas as gpd

        rows = [f for f in self.audit().get("findings", [])
                if f.get("easting") is not None and f.get("northing") is not None]
        if not rows:
            return []
        pts = gpd.GeoSeries(
            gpd.points_from_xy([f["easting"] for f in rows],
                               [f["northing"] for f in rows]), crs=27700).to_crs(4326)
        out = []
        for f, pt in zip(rows, pts):
            out.append({"kind": f["kind"], "detail": f["detail"],
                        "subject": f.get("subject"), "basin_id": f.get("basin_id"),
                        "corroborated": f.get("corroborated"),
                        "lon": round(pt.x, 5), "lat": round(pt.y, 5)})
        return out


DATA = Published()


# ── GeoJSON ──────────────────────────────────────────────────────────────────

def to_geojson(frame, precision: int = 6, extra: dict | None = None) -> dict:
    """A GeoDataFrame in EPSG:27700 to a WGS84 FeatureCollection.

    27700 is this project's CRS everywhere; 4326 happens at the edge, here, and nowhere
    earlier — the same rule `rewt/tiles.py` follows at export.
    """
    if len(frame) == 0:
        doc = {"type": "FeatureCollection", "features": []}
    else:
        wgs = frame.to_crs(4326) if frame.crs is not None else frame
        doc = json.loads(wgs.to_json(drop_id=True, to_wgs84=False))
        for f in doc["features"]:
            f["properties"] = {k: v for k, v in f["properties"].items() if v is not None}
    if extra:
        doc.update(extra)
    return doc


def _round(doc: dict, precision: int = 6) -> dict:
    """Coordinates to six decimals — about 10 cm, and a third off the payload."""
    def walk(c):
        if isinstance(c, (int, float)):
            return round(c, precision)
        return [walk(x) for x in c]
    for f in doc.get("features", []):
        if f.get("geometry"):
            f["geometry"]["coordinates"] = walk(f["geometry"]["coordinates"])
    return doc


# ── the endpoints ────────────────────────────────────────────────────────────

def api_summary() -> dict:
    """The figures the panel prints. Read from published/, never recomputed."""
    audit = DATA.audit()
    prov = DATA.provenance()
    sections = audit["sections"]
    counts = DATA.counts()

    warnings = []
    stated = sections.get("dead_ends", {}).get("at_tidal_water")
    if stated is not None and stated != counts["dead_ends_tidal"]:
        warnings.append(
            f"The audit counts {stated:,} dead ends at tidal water; this server derives "
            f"{counts['dead_ends_tidal']:,} from the published network and draws those. "
            "The two ask the question slightly differently — the audit knows the full "
            "scope rule, and <code>node.basin_in_scope</code> is the only half of it "
            "the GeoPackage carries — so the layer is the derived set and this notice "
            "is the disagreement rather than a silent choice between them.")

    return {
        "counts": counts,
        "citation": build._citation(),
        "findings": DATA.findings(),
        "reachability": sections["reachability"],
        "reachability_tested_against_the_sea":
            sections.get("reachability_tested_against_the_sea", {}),
        "basins": DATA.basin_table(),
        "stranded": {"count": sections["stranded_components"]["count"],
                     "km": sections["stranded_components"]["km"]},
        "direction_faults": sections.get("direction_faults"),
        "cycles": sections.get("cycles", {}),
        "provenance": {
            "built_at": prov["built_at"],
            "config_fingerprint": prov["config_fingerprint"],
            "sources": prov["sources"],
        },
        "attribution": build._attribution(prov),
        "warnings": warnings,
    }


def api_backdrops() -> dict:
    """`backdrops.json` plus whatever keys this machine actually holds.

    Two files, joined here rather than in one: `backdrops.json` is the catalogue and is
    gitignored for a licence reason; `keys.local.json` is a credential and is gitignored
    for the obvious one. The viewer offers no layer whose key is absent, so a machine
    without a key gets a shorter list rather than a list of layers that draw nothing.
    """
    catalogue = json.loads((HERE / "backdrops.json").read_text())
    keys = {}
    kf = HERE / "keys.local.json"
    if kf.exists():
        keys = json.loads(kf.read_text())
    # The environment wins over the file, so a key can be supplied for one run without
    # writing a credential to disk at all. README.md states both sources.
    for name, var in (("carto", "CARTO_API_KEY"), ("maptiler", "MAPTILER_API_KEY")):
        if os.environ.get(var):
            keys[name] = os.environ[var]
    return {"basemap": catalogue, "keys": keys}


def api_freshness() -> dict:
    now = DATA.disk_stamp()
    return {"stale": now != DATA.stamp,
            "loaded_at": DATA.loaded_at,
            "checked_at": time.time()}


def api_network(bbox_4326, zoom: float) -> dict:
    """The network in this viewport, thinned by zoom, with what it did reported.

    THE THINNING IS THE HONEST PART. Below z12 a short link is not drawn, and a reader
    who does not know that will read an empty valley as an empty valley. So `meta`
    carries the threshold, how many links were in the viewport, how many were drawn and
    whether the cap truncated the answer — and the panel prints all four. The four
    never-thinned classes are exempt whatever their length, by the build's own `KEPT`
    expression rather than by a second list that could drift from it.
    """
    from pyproj import Transformer

    to_bng = Transformer.from_crs(4326, 27700, always_xy=True)
    w, s, e, n = bbox_4326
    xs, ys = zip(*[to_bng.transform(lon, lat)
                   for lon, lat in ((w, s), (e, s), (e, n), (w, n))])
    bbox = (min(xs), min(ys), max(xs), max(ys))

    ladder = json.loads((HERE / "backdrops.json").read_text())["thinning"]
    threshold = 0
    for at_zoom, metres in ladder["ladder"]:
        if zoom >= at_zoom:
            threshold = metres
    tolerance = max(1.0, 30000.0 / (2 ** zoom))

    frame = DATA.frame(NETWORK, "link", bbox=bbox)
    in_viewport = len(frame)

    kept = (frame["in_scope"].astype(bool) & ~frame["reaches_tidal"].astype(bool)) \
        | frame["retired"].astype(bool) \
        | (frame["origin"] != "survey") \
        | frame["routing_reversed"].astype(bool)
    frame = frame[kept | (frame["length_m"] >= threshold)]

    truncated = len(frame) > MAX_FEATURES
    if truncated:
        # Longest first, so what survives the cap is the skeleton of the place rather
        # than an arbitrary slice of it — and `truncated` says the answer is partial.
        frame = frame.sort_values("length_m", ascending=False).head(MAX_FEATURES)

    drawn = len(frame)
    if drawn:
        frame = frame.copy()
        frame["geometry"] = frame.geometry.simplify(tolerance, preserve_topology=False)

    doc = to_geojson(frame)
    doc["meta"] = {"threshold_m": threshold, "tolerance_m": round(tolerance, 1),
                   "drawn": drawn, "in_viewport": in_viewport,
                   "truncated": truncated, "national": False}
    return _round(doc)


def api_link(link_id: str) -> dict:
    """One link, with its corrections and BOTH its ends named.

    THE GEOPACKAGE CARRIES `from_node` AND `to_node`; the tiles do not. `rewt/tiles.py`
    drops them as two of the five highest-cardinality columns, which is why the deployed
    viewer cannot enumerate the links attached to a node and this one can. R-10 asked
    for a node's popup to show every link attached to it: here that is a real join and
    not a proximity guess, so `attached` is the answer to the question actually asked.
    """
    link = DATA.frame(NETWORK, "link", geometry=False)
    row = link[link["link_id"] == link_id]
    if row.empty:
        return {"error": f"no link {link_id}"}
    d = {k: v for k, v in row.iloc[0].to_dict().items() if v is not None}
    for k, v in list(d.items()):
        if hasattr(v, "item"):
            d[k] = v.item()

    node = DATA.frame(NETWORK, "node", geometry=False)
    ends = {}
    for end in ("from_node", "to_node"):
        nid = d.get(end)
        hit = node[node["node_id"] == nid]
        ends[end] = ({k: (v.item() if hasattr(v, "item") else v)
                      for k, v in hit.iloc[0].to_dict().items() if v is not None}
                     if not hit.empty else None)
    d["from_node_detail"], d["to_node_detail"] = ends["from_node"], ends["to_node"]

    # Every OTHER link meeting this one at either end — the join the tiles cannot do.
    attached = []
    for nid in (d.get("from_node"), d.get("to_node")):
        if not nid:
            continue
        touching = link[((link["from_node"] == nid) | (link["to_node"] == nid))
                        & (link["link_id"] != link_id)]
        for r in touching.itertuples():
            attached.append({"at": nid, "link_id": r.link_id, "name": r.name,
                             "form": r.form, "length_m": float(r.length_m),
                             "retired": bool(r.retired),
                             "origin": r.origin,
                             "leaves": bool(r.from_node == nid)})
    d["attached"] = attached

    corr = DATA.frame(CORRECTIONS, "correction", geometry=False)
    col = "link_id" if "link_id" in corr.columns else None
    d["corrections"] = ([{k: v for k, v in r.items() if v is not None}
                         for r in corr[corr[col] == link_id].to_dict("records")]
                        if col else [])
    return d


def api_node(node_id: str) -> dict:
    """One node and EVERY link attached to it. R-10, answered rather than approximated.

    The deployed viewer cannot do this: `rewt/tiles.py` drops `from_node` and `to_node`
    as two of the five highest-cardinality columns, so it falls back to "the links drawn
    within a few pixels" and says so. The GeoPackage keeps both on all 195,568 rows, so
    here the question has an actual answer — every link whose oriented ends name this
    node, with `leaves` saying which way the water goes. A node reached by two inflows
    and left by none is R-07's suspect canal dead end, and this is where you can see it.
    """
    node = DATA.frame(NETWORK, "node", geometry=False)
    hit = node[node["node_id"] == node_id]
    if hit.empty:
        return {"error": f"no node {node_id}"}
    d = {k: (v.item() if hasattr(v, "item") else v)
         for k, v in hit.iloc[0].to_dict().items() if v is not None}

    link = DATA.frame(NETWORK, "link", geometry=False)
    touching = link[(link["from_node"] == node_id) | (link["to_node"] == node_id)]
    attached = []
    for r in touching.itertuples():
        attached.append({
            "link_id": r.link_id, "name": r.name, "name_alt": r.name_alt,
            "form": r.form, "origin": r.origin, "length_m": float(r.length_m),
            "in_scope": bool(r.in_scope), "reaches_tidal": bool(r.reaches_tidal),
            "retired": bool(r.retired), "routing_reversed": bool(r.routing_reversed),
            "screening_terrain_verdict": r.screening_terrain_verdict,
            "leaves": bool(r.from_node == node_id),
        })
    # Arrivals first, then departures, longest first within each: at a dead end the
    # inflows are the question and a list that opens with the outflow buries it.
    attached.sort(key=lambda a: (a["leaves"], -a["length_m"]))
    d["attached"] = attached
    d["inflows"] = sum(1 for a in attached if not a["leaves"] and not a["retired"])
    d["outflows"] = sum(1 for a in attached if a["leaves"] and not a["retired"])
    return d


def api_lines(kind: str) -> dict:
    """connectors, reversals, retired — the build's own SQL, run here on the file."""
    where = {"connectors": lambda f: f["origin"] == "connector",
             "reversals": lambda f: f["routing_reversed"].astype(bool),
             "retired": lambda f: f["retired"].astype(bool)}[kind]
    frame = DATA.frame(NETWORK, "link")
    return _round(to_geojson(frame[where(frame)]))


def api_points(kind: str) -> dict:
    if kind == "dead_ends":
        return _round(_dead_ends_geojson())
    if kind == "dead_ends_tidal":
        return _round(to_geojson(DATA.dead_ends_tidal()))
    if kind == "corrections":
        return _round(to_geojson(DATA.frame(CORRECTIONS, "correction")))
    if kind == "findings":
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature",
             "properties": {k: v for k, v in f.items()
                            if k not in ("lon", "lat") and v is not None},
             "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]}}
            for f in DATA.findings()]}
    if kind == "refused_crossings":
        # Copied, not rebuilt: the audit publishes this one in 4326 already, and a
        # second derivation is a second chance for the map and the audit to disagree.
        return DATA.cached("refused", lambda: json.loads(
            (AUDIT / "refused_crossings.geojson").read_text()))
    if kind == "seeds":
        frame = DATA.frame(NETWORK, "terminus")
        return _round(to_geojson(frame[frame["is_crawl_seed"].astype(bool)]))
    if kind == "tidal":
        return _round(to_geojson(DATA.frame(NETWORK, "terminus")))
    raise KeyError(kind)


def _dead_ends_geojson() -> dict:
    """The defect list, from the audit's own file rather than from the network.

    `rewt/tiles.py` builds the deployed layer this way for a stated reason — the audit
    defines a defect and the panel prints the audit's count beside it — so this reads
    the same file by the same rule rather than asking the GeoPackage a similar question
    and getting a similar answer.
    """
    from pyproj import Transformer

    to_wgs = Transformer.from_crs(27700, 4326, always_xy=True)
    rows = [r for r in DATA.json_file("dead_ends.json") if r.get("in_scope")]
    feats = []
    for r in rows:
        lon, lat = to_wgs.transform(r["easting"], r["northing"])
        feats.append({"type": "Feature",
                      "properties": {k: v for k, v in r.items()
                                     if k not in ("easting", "northing")},
                      "geometry": {"type": "Point",
                                   "coordinates": [round(lon, 6), round(lat, 6)]}})
    return {"type": "FeatureCollection", "features": feats}


def api_sea(kind: str) -> dict:
    return _round(to_geojson(DATA.frame(NETWORK, {"sea_route": "sea_route",
                                                  "sea_entry": "sea_entry"}[kind])))


def api_basins() -> dict:
    """Basins with the reached share joined on, so the fill can mean something.

    The share lives in `audit/basin_reach.json`, not in the GeoPackage. Joined here and
    left NULL where the audit has no row, because the viewer paints a null share grey
    and a zero share the network's own red — and a basin nobody measured is not a basin
    that reaches nothing.
    """
    frame = DATA.frame(NETWORK, "basin")
    reach = {r["basin_id"]: r for r in DATA.json_file("basin_reach.json")}
    frame = frame.copy()
    frame["share"] = [reach.get(b, {}).get("share") for b in frame["basin_id"]]
    frame["unreached_km"] = [reach.get(b, {}).get("unreached_km")
                             for b in frame["basin_id"]]
    frame["geometry"] = frame.geometry.simplify(200, preserve_topology=True)
    return _round(to_geojson(frame), precision=5)


# ── county composite tiles ───────────────────────────────────────────────────

_counties = None
_pool = ThreadPoolExecutor(max_workers=8)


def counties():
    """The county index, built once. Absent tilesets and an absent ZIP both explain
    themselves rather than 500-ing with a traceback the browser will never show."""
    global _counties
    if _counties is None:
        import counties as counties_mod

        # `nls_counties.json` is the catalogue's answer to "which counties does the
        # Library publish a first-edition six-inch mosaic for" — 71 of them, keyed by
        # the NLS's own filename slug. `Counties` matches those against the Historic
        # Counties Standard's 92 and keeps the intersection, which is why England and
        # Wales come out at 53 and Scotland and Ireland drop out on their own.
        cat = HERE / "nls_counties.json"
        if not cat.exists():
            raise FileNotFoundError(
                f"{cat.relative_to(ROOT)} is missing — it is the list of counties the "
                "NLS publishes a first-edition six-inch mosaic for, and without it "
                "there is nothing to composite. Rebuild it with "
                "tools/nls_catalogue.py; it is gitignored for a licence reason.")
        have = {row["county"] for row in json.loads(cat.read_text()) if row.get("county")}
        _counties = counties_mod.Counties(have)
    return _counties


# ── the server ───────────────────────────────────────────────────────────────

ROUTES_JSON = {
    "/api/summary.json": lambda q: api_summary(),
    "/api/backdrops.json": lambda q: api_backdrops(),
    "/api/freshness.json": lambda q: api_freshness(),
    "/api/counties.json": lambda q: counties().as_json(),
    "/api/basins.geojson": lambda q: api_basins(),
    "/api/lines": lambda q: api_lines(q["kind"][0]),
    "/api/points": lambda q: api_points(q["kind"][0]),
    "/api/sea": lambda q: api_sea(q["kind"][0]),
    "/api/link": lambda q: api_link(q["id"][0]),
    "/api/node": lambda q: api_node(q["id"][0]),
    "/api/network": lambda q: api_network(
        [float(v) for v in q["bbox"][0].split(",")], float(q["zoom"][0])),
    "/api/reload": lambda q: (DATA.reload(), {"reloaded": True,
                                              "stamp": DATA.stamp})[1],
}

# The only paths outside this directory that are served, and they are read-only files
# from the release. An allow-list of suffixes rather than a wider document root: the
# rule broken this afternoon was not "bind wrongly", it was "root one level too high".
PUBLISHED_SUFFIXES = {".json", ".geojson", ".md", ".csv", ".cff"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):                                     # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path, query = parsed.path, urllib.parse.parse_qs(parsed.query)

        if path in ROUTES_JSON:
            return self._json(ROUTES_JSON[path], query)
        if path.startswith("/backdrop/six-inch-first/"):
            return self._tile(path)
        if path.startswith("/published/"):
            return self._published(path)
        return super().do_GET()

    def _json(self, fn, query):
        try:
            body = json.dumps(fn(query), allow_nan=False).encode()
        except KeyError as e:
            return self.send_error(400, f"bad or missing parameter: {e}")
        except FileNotFoundError as e:
            return self.send_error(503, f"published/ is incomplete: {e}")
        except Exception:                                 # noqa: BLE001
            traceback.print_exc()
            return self.send_error(500, "see the server's console")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _tile(self, path):
        import counties as counties_mod

        try:
            z, x, y = (int(v) for v in path.rsplit("/", 3)[-3:][0:3])
        except ValueError:
            z, x, y = (int(v) for v in path[len("/backdrop/six-inch-first/"):]
                       .removesuffix(".png").split("/"))
        try:
            body = counties_mod.composite(counties(), z, x, y, _pool)
        except FileNotFoundError as e:
            return self.send_error(503, str(e))
        except Exception:                                 # noqa: BLE001
            traceback.print_exc()
            return self.send_error(500, "see the server's console")
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _published(self, path):
        """One release file, read-only, by suffix. Never a directory listing."""
        rel = urllib.parse.unquote(path[len("/published/"):])
        target = (PUBLISHED / rel).resolve()
        if not target.is_file() or PUBLISHED not in target.parents \
                or target.suffix not in PUBLISHED_SUFFIXES:
            return self.send_error(404, "not served from published/")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(str(target)))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):                    # one line, not three
        code = args[1] if len(args) > 1 else ""
        print(f"  {code} {self.path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--fetch-counties", action="store_true",
                    help="download the Historic County Borders polygons and check them "
                         "against the checksum declared in conf/sources.yml")
    args = ap.parse_args()

    if args.fetch_counties:
        import counties as counties_mod
        counties_mod.fetch_zip()
        return

    if not NETWORK.exists():
        raise SystemExit(
            f"{NETWORK.relative_to(ROOT)} is missing. This server reads published/ and "
            "there is nothing published yet — run the build first. Run from the "
            "repository root.")

    print(f"published/ from {PUBLISHED}")
    print(f"network: {NETWORK.stat().st_size / 1e6:,.0f} MB, "
          f"built {DATA.provenance()['built_at'][:16].replace('T', ' ')}")
    print(f"http://127.0.0.1:{args.port}/   (Ctrl-C to stop)")
    # 127.0.0.1 and not the default 0.0.0.0. TEAM.md, and it has to be typed.
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
