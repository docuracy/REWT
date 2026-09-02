"""Generate `docs/trace/backdrops.json` — the tracer's curation of the NLS catalogue.

    python tools/tracer/gen_backdrops.py [--check]

`tools/nls_layers.json` is rewt-fc's machine walk of the NLS bucket: what exists, where,
and at what zooms, every extent observed from the keys the Library actually serves rather
than described. It is the shared statement of fact. **It is not a list of what the tracer
offers**, and the two are deliberately different objects — the viewer curates it one way,
for reading ground against, and this curates it another, for tracing on. One source of
fact, two presentations.

WHAT THIS ADDS: nothing. It selects, and it refuses to add a date.

**No layer gets a survey year here.** The bucket does not carry one, D-037 records that NLS
state no date spans for these layers, and a seamless layer is a composite of many sheets of
different dates and so has no single survey date at all. A tileset called
`os/one-inch-old-series-all` invites the label *1805–1874*, and that label would come from
somebody's knowledge of the series rather than from anything NLS said about that tileset.
It has already caught this project once, labelling the six-inch second edition *1888–1913*
from a different product's naming. So `surveyYear` is null everywhere, and the annotation
profile turns that into an explicit unknown rather than a guess.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "tools/nls_layers.json"
OUT = ROOT / "docs/trace/backdrops.json"

NLS_ATTRIBUTION = ("Reproduced with the permission of the National Library of Scotland. "
                   "Re-use terms for these layers are not established (D-037).")

# Seamless layers worth offering, in the order a contributor would reach for them.
SEAMLESS = {
    "os/6inchsecond": "OS Six-Inch, 2nd edition — seamless",
    "os/6inchfirst": "OS Six-Inch, 1st edition — seamless",
    "os/one-inch-rev": "OS One-Inch, revised — seamless",
}


def load_catalogue() -> list[dict]:
    raw = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return raw["layers"] if isinstance(raw, dict) else raw


def build() -> dict:
    layers = load_catalogue()
    by_id = {l["id"]: l for l in layers}
    out = []

    # OpenStreetMap: keyless, and the only way to find a place before a sheet is chosen.
    out.append({
        "id": "osm", "name": "OpenStreetMap (for finding the place)", "group": "modern",
        "tiles": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "zooms": [1, 19], "bounds": [-180, -85, 180, 85], "surveyYear": None,
        "historic": False, "traceable": False,
        "attribution": '© OpenStreetMap contributors',
    })

    # THE FIRST EDITION HAS NO SEAMLESS LAYER, so this project makes one. NLS publish it
    # county by county, and the mosaics are not cut at the county line — each bleeds over
    # its neighbours, so stacking them puts two different surveys of the same ground on top
    # of each other with the join wherever the draw order happens to fall. MapLibre cannot
    # clip a raster to a polygon, so the tile is composited in a canvas, each county masked
    # to its own Historic Counties Standard polygon.
    #
    # It matters because **two in five reservoir valleys need the first edition** — 14
    # first-edition-only and 26 surveyed while the dam was building, of 165 impounding
    # reservoirs — and because 19 predate both editions and have no OS sheet at all.
    out.append({
        "id": "composite/six-inch-first", "name": "OS Six-Inch, 1st edition — composited",
        "group": "composite",
        # No URL: assembled in the browser. `tiles` is the scheme MapLibre is given.
        "tiles": "firsted://{z}/{x}/{y}",
        "zooms": [9, 17], "bounds": [-6.5, 49.8, 1.8, 55.9],
        "surveyYear": None, "historic": True, "traceable": True,
        "composited": True,
        "attribution": NLS_ATTRIBUTION + " County boundaries: this mapping made use of "
                       "data provided by the Historic County Borders Project, "
                       "https://www.county-borders.co.uk",
    })

    for lid, label in SEAMLESS.items():
        l = by_id.get(lid)
        if not l:
            continue
        out.append({
            "id": l["id"], "name": label, "group": "seamless",
            "tiles": l["tiles"], "zooms": l["zooms"], "bounds": l["bounds"],
            # A composite of many sheets has no single survey date. Stated, not guessed.
            "surveyYear": None, "historic": True, "traceable": True,
            "attribution": NLS_ATTRIBUTION,
        })

    # THE TRACING SURFACE. 1:2,500, zoom 18 and in places 19 — roughly 0.6 m per pixel,
    # an order of magnitude finer than the six-inch, and the scale at which a channel is
    # drawn as two banks rather than one line.
    for l in sorted(layers, key=lambda x: x["id"]):
        if not l["id"].startswith("25_inch/"):
            continue
        if (l.get("england_wales_share") or 0) < 0.5:
            continue
        out.append({
            "id": l["id"], "name": f"25-inch — {l['name']}", "group": "25_inch",
            "tiles": l["tiles"], "zooms": l["zooms"], "bounds": l["bounds"],
            "surveyYear": None, "historic": True, "traceable": True,
            "attribution": NLS_ATTRIBUTION,
        })

    return {
        "_generated_by": "tools/tracer/gen_backdrops.py from tools/nls_layers.json",
        "_no_dates": "Deliberate. The bucket carries no survey years and this file invents "
                     "none; the annotation records an explicit unknown instead.",
        "_bounds_are_a_hint": "Extents are derived from a listing at zoom 9, so a box is "
                              "snapped to about 78 km and several counties contain any "
                              "given point. Fine for choosing a default; not a containment "
                              "test. To know what actually covers a coordinate, ask the "
                              "bucket for the tile.",
        "layers": out,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not CATALOGUE.exists():
        print(f"{CATALOGUE} not found — it is rewt-fc's, and generated", file=sys.stderr)
        return 1
    fresh = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != fresh:
            print(f"{OUT} is stale — run `python tools/tracer/gen_backdrops.py`", file=sys.stderr)
            return 1
        print(f"{OUT} is current")
        return 0
    OUT.write_text(fresh, encoding="utf-8")
    n = len(build()["layers"])
    print(f"wrote {OUT} — {n} layers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
