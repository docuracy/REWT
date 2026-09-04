"""How far each coast can be seen from: the per-coast cut of the sightline layer.

    python3 tools/router/coasts.py

Run from the repository root; paths are relative (AGENTS.md).

Stephen's observation, 4 September 2026: Britain's sightlines are very significantly
broader than the continent's. This makes it a file rather than a sentence, because
documentation will not publish a figure whose only home is a message — correctly, and
they said so about mine.

WHAT IS SAFE HERE AND WHAT IS NOT.

  SAFE     the median governing height and the range it implies. Two numbers and one
           formula, re-derivable by anyone from a gazetteer, and independent of where
           this model stops.
  NOT SAFE any SHARE of the layer. The surface is trimmed to a week's sailing OF ENGLAND
           AND WALES, so it is defined outward from Britain, and Britain's share of it is
           substantially a property of that choice. rewt-68 turned my own caution about
           "percentage of sea that can see land" onto my own headline figure and was
           right. Cell counts are emitted for scale, flagged, and must not be published
           as a proportion.

THE CLASSIFICATION IS A GEOGRAPHIC BOX, not a landmass. A cell is assigned by ITS OWN
position, not by where the land that governs it lies, so a cell in mid-Channel may be
counted to whichever side the box puts it. The boxes are declared below so a reader can
see exactly what was asked. The medians are robust to this; the counts are not.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import h3
from generation import generation

# THE NOTE THAT OUTLIVED ITS NUMBER. This read "every range is a FLOOR: an eye at sea
# level, which is the one value that assumes nothing" — true when observer height was 0 m,
# and left standing when Stephen set it to 10 m. It then sat in the published summary
# immediately beside `observer_height_m: 10.0`, contradicting the field above it. The
# primary note is now TAKEN FROM THE LAYER rather than restated here, so it cannot drift
# from the run again; this second one says what changed, because a reader who saw the old
# sentence deserves to know it was withdrawn rather than quietly edited.
OBSERVER_NOTE = (
    "NOT a floor at sea level. The observer is at 10 m, a masthead lookout, so every range "
    "here already contains 12.0 km of observer horizon. A deck observer at 2 m has an "
    "observer term of 5.4 km, which is 6.6 km LESS — 5.4 is that observer's own horizon, "
    "not the difference. This note previously read 'every range is a FLOOR: an eye at sea level'; "
    "that was written when the height was 0 m and it survived the change to 10 m, sitting "
    "next to the field that contradicted it."
)

LAYER = Path("docs/router/data/sightline2_r6.geojson")
OUT = Path("docs/router/data/coast_summary.json")

# name: (lon_min, lat_min, lon_max, lat_max)
# name: (lon_min, lat_min, lon_max, lat_max, tallest land the NAMED region can supply)
#
# THE LABEL MUST DESCRIBE WHAT SUPPLIES THE LAND, not merely where the cell sits. rewt-68
# found this box reporting a tallest governing land of 1,400 m while a buffer regression
# was live — Norwegian mountains reaching across the Skagerrak into cells labelled "Low
# Countries, Germany and Denmark", which have no such ground. Under the no-blind-sailing
# rule those cells are gone, but the box has not changed and would report it again.
#
# So each box declares the tallest land its own name can account for, and the run FAILS if
# the measured maximum exceeds it. This layer cannot say which summit governs a cell —
# only the height of the band that reached it — so the label cannot be derived. What it
# can do is refuse to publish a label its own numbers contradict.
BOXES = {
    "British Isles": (-13.24, 49.00, -1.00, 62.12, 1345),          # Ben Nevis
    "north France and Brittany": (-6.00, 44.50, 2.00, 50.50, 1200),
    "Low Countries, Germany and Denmark": (2.00, 50.50, 11.50, 58.00, 1200),   # the Harz
}


def main() -> None:
    gj = json.loads(LAYER.read_text())
    props = gj.get("properties", {})
    rows = []
    for f in gj["features"]:
        p = f["properties"]
        if not p.get("visible"):
            continue
        la, lo = h3.cell_to_latlng(p["h3"])
        rows.append((la, lo, p["gov_h_m"], p["gov_reach_km"]))
    print(f"{len(rows):,} cells in sight of land")

    out = {}
    bad = []
    for name, (w, s, e, n, plausible) in BOXES.items():
        v = np.array([(h, r) for la, lo, h, r in rows if w <= lo <= e and s <= la <= n])
        if not len(v):
            continue
        tallest = int(v[:, 0].max())
        if tallest > plausible:
            bad.append((name, tallest, plausible))
        out[name] = {
            "box_lon_lat": [w, s, e, n],
            "tallest_the_label_can_supply_m": plausible,
            "cells_in_sight": int(len(v)),
            "median_governing_land_m": int(round(float(np.median(v[:, 0])))),
            "median_reach_km": round(float(np.median(v[:, 1])), 1),
            "tallest_governing_land_m": int(v[:, 0].max()),
            "greatest_reach_km": round(float(v[:, 1].max()), 1),
        }
        print(f"  {name:<38} {len(v):>7,} cells   median "
              f"{np.median(v[:, 0]):>5.0f} m -> {np.median(v[:, 1]):>5.1f} km   "
              f"max {v[:, 0].max():>5.0f} m -> {v[:, 1].max():>5.1f} km")

    if bad:
        print()
        for name, tallest, plausible in bad:
            print(f"  ** {name}: governing land reaches {tallest} m, but that region has "
                  f"nothing above {plausible} m. The cells are governed from OUTSIDE the "
                  f"named geography and the label would lie. **")
        raise SystemExit("refusing to write a per-coast table whose labels its own numbers "
                         "contradict — split the box or rename it")

    OUT.write_text(json.dumps({
        "generation": generation(), "what": "median height of the land that governs each cell in sight, by coast, "
                "and the range it implies",
        "safe_to_publish": ["median_governing_land_m", "median_reach_km",
                            "tallest_governing_land_m", "greatest_reach_km"],
        "not_safe_to_publish": "any SHARE or PERCENTAGE derived from cells_in_sight. The "
                               "surface is trimmed to a week's sailing of England and "
                               "Wales, so it is defined outward from Britain and "
                               "Britain's share of it is largely a property of that "
                               "choice — it moves with the extent without anything about "
                               "the world changing.",
        "classification": "by the CELL's own position within a declared box, not by where "
                          "the governing land lies. The medians are robust to this; the "
                          "counts are not.",
        "horizon_formula": props.get("horizon_formula"),
        "observer_height_m": props.get("observer_height_m"),
        "observer_note": props.get("observer_height_basis"),
        "observer_note_2": OBSERVER_NOTE,
        "attribution": props.get("attribution"),
        "use_constraint": props.get("use_constraint"),
        "coasts": out,
    }, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
