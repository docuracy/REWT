#!/usr/bin/env python3
"""Re-derive every GB1900 figure published in docs/.

    .venv/bin/python tools/gb1900/measure.py
    .venv/bin/python tools/gb1900/measure.py --archive /path/to/dump.zip --places out.csv

D-019 says: do not publish a number you cannot re-run. These are the numbers on
docs/scale.md and docs/evidence.md, and this is how to re-run them. It is NOT a build
stage — `gb1900_raw_dump` is registered `stage: 2, used_by: docs`, and rewt/pipeline.py
refuses any stage that declares it. Nothing here writes to the database.

The input is the CC0 **raw dump**, never the CC-BY-SA gazetteers: share-alike would reach
this project's exports, and the abridgement drops every string occurring 300 or more times
nationally, which is exactly the mill and towing-path vocabulary these counts rest on.
A copy of the abridged file sits in ~/Downloads and must not be substituted (D-018).

Method, in one paragraph. Every volunteer transcription is scanned, not only the reading
made when the pin was dropped, so a pin whose first reading was blank is still found; each
pin's text is then the reading most of its matching transcriptions gave. Pins are split to
England and Wales by OS Boundary-Line country polygon — a proxy for the basin scope rule of
PLAN.md §4.1, which is why the counts undercount slightly in the Scottish parts of the
Tweed and Border Esk. Labels sharing a normalised caption are collapsed into one *place* by
single linkage at 1 km, because the Ordnance Survey repeated a name along the feature it
named and a count of labels is a count of type, not of rivers.
"""
from __future__ import annotations

import argparse, collections, csv, hashlib, io, json, re, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE = ROOT / "data/raw/gb1900/GB1900_final_raw_dump_july_2018.zip"
BOUNDARY = ROOT / "data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg"
MEMBER_TRANSCRIPTIONS = "GB1900_final_raw_dump_july_2018/gb1900_transcriptions.csv"
MEMBER_LOCATIONS = "GB1900_final_raw_dump_july_2018/gb1900_locations.csv"
ENCODING = "utf-16"

# Declared here rather than in code comments so a reader can see exactly what was counted.
# `(?! works)` excludes Cornish tin and wolfram streaming from the old-course class.
CLASSES = {
    "old_course":   r"(?i)\bold (river|course|channel|bed|stream|ea|eau)\b(?!\s+works\b)|\bold r\.",
    "new_cut":      r"(?i)\bnew (cut|river|channel|course|drain)\b",
    "towing_path":  r"(?i)tow(ing)? ?path",
    "mill_channel": r"(?i)mill (race|leat|lade|lead|stream|cut|tail|head|pond|pool)|\bleat\b",
}
CLUSTER_M = 1000          # the published "distinct places" radius
SOURCE_ID = "gb1900_raw_dump"


def registered_checksum() -> str | None:
    """The checksum conf/sources.yml declares. One source of truth, not a copy of it."""
    import yaml
    conf = yaml.safe_load((ROOT / "conf/sources.yml").read_text())
    for src in conf.get("sources", []):
        if src.get("id") == SOURCE_ID:
            return src.get("checksum")
    return None


def check(archive: Path, unverified: bool) -> None:
    expected = registered_checksum()
    if not archive.exists():
        sys.exit(
            f"No GB1900 raw dump at {archive}.\n"
            f"Acquire it (conf/sources.yml: {SOURCE_ID}) from\n"
            "  https://www.visionofbritain.org.uk/downloads/GB1900_final_raw_dump_july_2018.zip\n"
            f"and check sha256 == {expected}.\n"
            "The server sends an incomplete certificate chain; supply the intermediate rather\n"
            "than disabling verification. Do NOT substitute the abridged gazetteer: it is\n"
            "CC-BY-SA, and its abridgement removes the vocabulary these counts rest on.")
    h = hashlib.sha256()
    with archive.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    got = h.hexdigest()
    if got == expected:
        return
    message = (f"{archive}\n  sha256   {got}\n  declared {expected}\n"
               "The archive does not match the checksum in conf/sources.yml.")
    if not unverified:
        sys.exit(message + "\nRe-run with --unverified only if the provenance question is "
                           "known and being handled elsewhere.")
    print("!" * 76, file=sys.stderr)
    print(message, file=sys.stderr)
    print("Proceeding UNVERIFIED at your request. Figures from this run carry no "
          "provenance.", file=sys.stderr)
    print("!" * 76, file=sys.stderr)


def matching_pins(archive: Path, patterns: dict) -> dict:
    """pin_id -> consensus text, over EVERY transcription rather than the first."""
    csv.field_size_limit(10_000_000)
    hits: dict = collections.defaultdict(collections.Counter)
    seen = 0
    with zipfile.ZipFile(archive) as z:
        stream = io.TextIOWrapper(z.open(MEMBER_TRANSCRIPTIONS), encoding=ENCODING, newline="")
        for row in csv.DictReader(stream):
            seen += 1
            text = (row.get("transcription") or "").strip()
            if text and any(p.search(text) for p in patterns.values()):
                hits[row["pin_id"]][text] += 1
    print(f"{seen:,} transcriptions read; {len(hits):,} pins with a matching reading")
    return {pin: max(sorted(texts), key=texts.get) for pin, texts in hits.items()}


def locate(archive: Path, consensus: dict, patterns: dict) -> list:
    from shapely import wkb
    csv.field_size_limit(10_000_000)
    out = []
    with zipfile.ZipFile(archive) as z:
        stream = io.TextIOWrapper(z.open(MEMBER_LOCATIONS), encoding=ENCODING, newline="")
        for row in csv.DictReader(stream):
            text = consensus.get(row.get("pin_id"))
            if not text:
                continue
            classes = [n for n, p in patterns.items() if p.search(text)]
            if not classes:
                continue                      # consensus reading no longer matches
            try:
                pt = wkb.loads(bytes.fromhex(row.get("g_point_wgs") or ""))
            except Exception:                 # noqa: BLE001
                continue
            out.append({"pin_id": row["pin_id"], "text": text,
                        "classes": "|".join(classes), "lon": pt.x, "lat": pt.y})
    return out


def normalise(text: str) -> str:
    t = str(text).casefold().replace("&", "and")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def cluster(points: list, d: int) -> list:
    """Single-linkage over a grid of cell size d. Returns lists of member indices."""
    cells = collections.defaultdict(list)
    for i, (e, n) in enumerate(points):
        cells[(int(e // d), int(n // d))].append(i)
    parent = list(range(len(points)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    d2 = d * d
    for (cx, cy), idx in cells.items():
        for dx in (0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy < 0:
                    continue
                other = cells.get((cx + dx, cy + dy))
                if not other:
                    continue
                for i in idx:
                    for j in other:
                        if (dx, dy) == (0, 0) and i >= j:
                            continue
                        if (points[i][0] - points[j][0]) ** 2 + \
                           (points[i][1] - points[j][1]) ** 2 <= d2:
                            ra, rb = find(i), find(j)
                            if ra != rb:
                                parent[ra] = rb
    groups = collections.defaultdict(list)
    for i in range(len(points)):
        groups[find(i)].append(i)
    return list(groups.values())


def places(rows, cls) -> list:
    """One entry per distinct place: same normalised caption, single-linked at 1 km."""
    by_text = collections.defaultdict(list)
    for r in rows:
        if cls in r["classes"]:
            by_text[normalise(r["text"])].append(r)
    out = []
    for group in by_text.values():
        pts = [(r["easting"], r["northing"]) for r in group]
        for members in cluster(pts, CLUSTER_M):
            es = [pts[i][0] for i in members]
            ns = [pts[i][1] for i in members]
            out.append({"text": group[members[0]]["text"], "labels": len(members),
                        "easting": round(sum(es) / len(es), 1),
                        "northing": round(sum(ns) / len(ns), 1)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    ap.add_argument("--places", type=Path,
                    help="write one row per mill-channel place to this CSV")
    ap.add_argument("--unverified", action="store_true",
                    help="proceed when the archive does not match the declared checksum, "
                         "with a warning; the run then carries no provenance")
    args = ap.parse_args()

    check(args.archive, args.unverified)
    patterns = {k: re.compile(v) for k, v in CLASSES.items()}
    rows = locate(args.archive, matching_pins(args.archive, patterns), patterns)

    import geopandas as gpd
    import pandas as pd
    df = pd.DataFrame(rows)
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat),
                           crs="EPSG:4326").to_crs("EPSG:27700")
    countries = gpd.read_file(BOUNDARY, layer="country_region")
    scotland = countries[countries["Name"] == "Scotland"].geometry.union_all()
    pts["easting"], pts["northing"] = pts.geometry.x, pts.geometry.y
    pts["scotland"] = pts.geometry.within(scotland)
    ew = pts[~pts["scotland"]].to_dict("records")
    gb = pts.to_dict("records")

    print("\nclass          GB labels   E&W labels   E&W places (1 km)")
    for cls in CLASSES:
        g = sum(cls in r["classes"] for r in gb)
        e = sum(cls in r["classes"] for r in ew)
        print(f"{cls:<14} {g:>9,} {e:>12,} {len(places(ew, cls)):>18,}")

    both = [r for r in ew if "old_course" in r["classes"] or "new_cut" in r["classes"]]
    coords = [(r["easting"], r["northing"]) for r in both]
    print(f"\nold_course + new_cut, England and Wales: {len(both):,} labels at "
          f"{len(cluster(coords, CLUSTER_M)):,} places, clustering on position alone")

    if args.places:
        rows_out = sorted(places(ew, "mill_channel"), key=lambda r: (r["easting"], r["northing"]))
        with args.places.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, ["place_id", "text", "labels", "easting", "northing"])
            w.writeheader()
            for i, r in enumerate(rows_out):
                w.writerow({"place_id": f"mc{i:05d}", **r})
        print(f"\nwrote {len(rows_out):,} mill-channel places to {args.places}")


if __name__ == "__main__":
    main()
