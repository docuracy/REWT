"""Generate the tracer's work queue from the GB1900 places.

    python tools/tracer/gen_tasks.py            # write
    python tools/tracer/gen_tasks.py --check    # fail if the committed files are stale

Reads `tools/tracer/queue/*.csv` and writes `docs/trace/tasks/*.json` — reprojected to
CRS84, because the tracer works in lon/lat and AGENTS.md puts the reprojection at the
boundary rather than in four places.

## Three outcomes, not two

The obvious cleaning pass asks *is this place a channel or not*. That is the wrong question
and it was asked twice before anyone noticed. A caption naming a channel and a caption
naming a structure **on** a channel are different evidence, and only the third case is
useless:

* **`trace`** — a caption letters the channel itself. `New Cut`, `Old River Ancholme`.
* **`locate`** — the only captions name a structure named *after* the channel: `New Cut
  Bridge`, `Old River Farm`. The surveyor did not letter the water, but he put its name on
  something beside it, so **the channel is located and not lettered**. Weaker evidence, not
  absent evidence, and a task carrying that caveat rather than a rejection.
* **`drop`** — the captions are the New River Company's built estate: `NEW RIVER STREET`,
  `New River Head`, a pumping station, a filter bed. No channel is implied at that point, a
  contributor sent there will not find one, **and the failure will read as their mistake
  rather than the queue's** — which is the reason this pass exists at all.

Measured over the 274 assertion places: about 94% `trace`, 3% `locate`, 3% `drop`. The
`drop` set is small enough to list in a commit message and was worth finding anyway.

## Why the test runs over `captions` and never over `text`

`text` is the captions joined for display. A merged cluster is a **set of statements**, so
`NEW CUT; New Cut Bridge; New Cut Bridge (Draw)` contains a structure word and is a
perfectly good task. Testing the joined string asks *does any caption match* when the
question is *does no caption describe a channel*. Two agents made that mistake
independently on the same afternoon, which is why the `captions` column exists.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
IN = ROOT / "tools/tracer/queue"
OUT = ROOT / "docs/trace/tasks"

# ── What a caption is naming, decided by its HEAD NOUN ────────────────────────────────
#
# THE FIRST VERSION ASKED WHETHER A CAPTION *CONTAINED* A STRUCTURE WORD, and that is the
# same mistake this file's docstring warns about, one level down. `\bmill\b` was in the
# structure list — correct for `Mill House`, and catastrophic for the mill-channel queue,
# where every caption contains "mill" by construction. It classed **3,975 of 4,064 mill
# channels as structures and 89 as channels**, which is the answer inverted. A classifier
# built for one population, reused on another, giving a confident wrong answer: the same
# shape as reading the nearest label.
#
# The head noun settles it. `Mill Leat` is a leat; `Mill House` is a house; `Old Course of
# Bridge Dike` is a dike, not a bridge — which the contains-test also got wrong, and which
# two people separately flagged as a false positive before anyone fixed the rule.
WATER = {
    "leat", "leats", "lade", "goit", "race", "pond", "ponds", "pool", "cut", "river",
    "brook", "stream", "beck", "burn", "dike", "dyke", "drain", "channel", "course",
    "ea", "eau", "water", "canal", "navigation", "lode", "rhyne", "gutter", "tail",
    # AMBIGUOUS, AND DELIBERATELY RESOLVED TOWARDS WATER. A filter bed and the New River
    # Head are built works; a river bed and a mill head are the watercourse. The head noun
    # cannot separate them, so the tie goes to water — because **a false keep costs a
    # contributor one look and produces a skip with a reason, which is data, while a false
    # drop removes a real task and nothing ever says so.** Putting these in the estate list
    # silently dropped `Old River Bed` and nine `Mill Head`s.
    "bed", "head",
}
# Built works that imply no channel at this point at all — the New River Company's estate
# and its kind. A contributor sent here would find nothing, and read that as their fault.
ESTATE = {
    "street", "walk", "road", "works", "reservoir", "company", "well", "tower",
    "station", "yard", "office", "hall",
}
# A thing named AFTER a channel. The water is there; the surveyor lettered its neighbour.
BESIDE = {
    "bridge", "farm", "house", "cottage", "cottages", "lane", "gate", "plantation",
    "halt", "mill", "wharf", "lock", "inn", "bank", "walkway", "close", "field",
}

_WORD = re.compile(r"[A-Za-z']+")


def head_noun(caption: str) -> str:
    """The last word, ignoring a bracketed qualifier: `New Cut Bridge (Draw)` -> bridge."""
    caption = re.sub(r"\([^)]*\)", " ", caption)
    words = _WORD.findall(caption.lower())
    return words[-1] if words else ""


def classify_caption(caption: str) -> str:
    h = head_noun(caption)
    if h in ESTATE:
        return "drop"
    if h in WATER:
        return "trace"
    if h in BESIDE:
        return "locate"
    # An unrecognised head noun is most often a proper name — `New Cut`, `Old Ea`, a
    # river's own name. Treat it as the channel: this queue's whole purpose is captions
    # the surveyor wrote on watercourses, and refusing what we cannot parse would drop
    # the ones with the least common names.
    return "trace"


def classify(captions: list[str]) -> str:
    """`trace`, `locate` or `drop` — the best evidence any caption in the cluster offers."""
    verdicts = {classify_caption(c) for c in captions}
    if "trace" in verdicts:
        return "trace"
    if "locate" in verdicts:
        return "locate"
    return "drop"


def to_crs84(rows):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    for r in rows:
        lon, lat = t.transform(float(r["easting"]), float(r["northing"]))
        r["lon"], r["lat"] = round(lon, 6), round(lat, 6)
    return rows


def build(name: str, cls: str) -> dict:
    rows = list(csv.DictReader((IN / name).open(encoding="utf-8")))
    for r in rows:
        r["captions"] = json.loads(r["captions"])
    to_crs84(rows)
    tasks, dropped = [], []
    for r in rows:
        kind = classify(r["captions"])
        rec = {
            "id": r["place_id"], "cls": cls, "kind": kind,
            "captions": r["captions"], "labels": int(r["labels"]),
            "lon": r["lon"], "lat": r["lat"],
        }
        (dropped if kind == "drop" else tasks).append(rec)
    return {
        "_what": f"{cls} tasks for the REWT tracer, one per place",
        "_source": "GB1900 CC0 raw dump, clustered by tools/gb1900/measure.py; "
                   "see tools/tracer/queue/README.md",
        "_crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
        "_kinds": {
            "trace": "a caption letters the channel itself",
            "locate": "only a structure named after the channel is lettered — the channel "
                      "is located but not lettered, which is weaker evidence and not none",
        },
        "_dropped": {
            "count": len(dropped),
            "why": "captions name built works and imply no channel; a contributor sent "
                   "there would not find one",
            "ids": [d["id"] for d in dropped],
        },
        "tasks": tasks,
    }


def render() -> dict[pathlib.Path, str]:
    return {
        OUT / "assertions.json": json.dumps(build("assertion_places.csv", "assertion"),
                                            indent=1, ensure_ascii=False) + "\n",
        OUT / "mill-channels.json": json.dumps(build("mill_channel_places.csv", "mill"),
                                               indent=1, ensure_ascii=False) + "\n",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not IN.exists():
        print(f"{IN} is missing — the queue inputs are not here", file=sys.stderr)
        return 1

    fresh = render()
    if args.check:
        stale = [p for p, text in fresh.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            for p in stale:
                print(f"{p.relative_to(ROOT)} is stale — run "
                      f"`python tools/tracer/gen_tasks.py`", file=sys.stderr)
            return 1
        print("the work queue is current with tools/tracer/queue/")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for p, text in fresh.items():
        p.write_text(text, encoding="utf-8")
        d = json.loads(text)
        by = {}
        for t in d["tasks"]:
            by[t["kind"]] = by.get(t["kind"], 0) + 1
        print(f"wrote {p.relative_to(ROOT)}  {len(d['tasks'])} tasks "
              f"({', '.join(f'{v} {k}' for k, v in sorted(by.items()))}), "
              f"{d['_dropped']['count']} dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
