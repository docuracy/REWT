#!/usr/bin/env python3
"""Project the router's own artefacts into the data file /routing renders from.

The router's outputs carry their method in their own top-level `properties`: the
horizon formula, the refraction coefficient, the observer height, the extent, the
validation and the licence constraint. A page that retyped any of those would be a
second copy of a fact that has a first copy in the file the code reads -- which is
D-094 exactly, a constant living in prose and in code where the prose is the copy
nobody executes. The router session's own 3.86-for-3.7945 slip is the instance.

So nothing here is typed. THE HORIZON CONSTANT AND THE REFRACTION COEFFICIENT ARE
PARSED OUT OF THE LAYER'S OWN FORMULA STRING and everything the page says about
ranges is computed from them. Change `horizon_formula` in the router and the page
follows; change it to something this cannot parse and the build fails rather than
publishing a stale number.

WHAT IS DELIBERATELY NOT PROJECTED: cell counts, join counts and trace counts. The
router says the grid and the joins are still moving -- the banding scheme changed and
R-01 has not landed -- and a figure that moves belongs in the artefact a reader can
fetch, not in a sentence they will quote back in a month.

    python tools/docs/routing_page.py            # write docs/_data/routing.yml
    python tools/docs/routing_page.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import yaml

LAYER = Path("docs/router/data/sightline2_r6.geojson")
REACH = Path("docs/router/data/reach_summary.json")
MANIFEST = Path("conf/sources.yml")
TARGET = Path("docs/_data/routing.yml")

# What the page says about the layer's method, in the order the page reads them.
FROM_LAYER = [
    "what", "method", "bands", "band_km", "max_reach_km",
    "horizon_formula", "observer_height_m", "observer_height_basis",
    "gov_h_m_definition", "gov_h_m_provenance", "gov_reach_km_definition",
    "blind_sailing_buffer_km", "buffer_basis", "trimmed",
    "computation_domain_note", "tallest_governing_land_note",
    "distance_crs", "distance_crs_worst_error_pct", "validated_against",
    "week_km", "week_trim", "attribution", "use_constraint", "generation",
]
FROM_REACH = [
    "criterion", "calibration", "calibration_source", "week_km",
    "anchors_disagree", "measured_on", "not_a_radius", "time_not_computed",
]

# A deck observer, for saying what a lower eye costs against the masthead the surface
# assumes. Not a claim about any vessel: it is the comparison that makes the observer
# height a choice rather than a constant nobody noticed.
DECK_EYE_M = 2

BANNER = (
    "# GENERATED FILE -- do not edit.\n"
    "#\n"
    "# Written by tools/docs/routing_page.py from the router's own artefacts:\n"
    "#   docs/router/data/sightline2_r6.geojson  (its top-level `properties`)\n"
    "#   docs/router/data/reach_summary.json\n"
    "#\n"
    "# The horizon constant and refraction coefficient are PARSED from the layer's\n"
    "# formula string, never typed here, so the page cannot disagree with the code.\n"
    "# Counts of cells, joins and traces are not projected: they are still moving.\n"
)


def horizon(formula: str) -> dict:
    """The constant and the coefficient, read out of the layer's own sentence.

    Fails loudly. A formula string this cannot parse means the router has changed how
    it states its method, and the page must not go on quoting the last one it
    understood -- an unreadable formula is a reason to stop, not to fall back.
    """
    const = re.search(r"([0-9]+\.[0-9]+)\s*\*\s*sqrt", formula)
    k = re.search(r"refraction_k\s*=\s*([0-9]+\.[0-9]+)", formula)
    if not const or not k:
        raise SystemExit(
            f"cannot read the horizon constant and refraction_k out of "
            f"{formula!r}. tools/docs/routing_page.py must be taught the new wording "
            f"before /routing can quote it."
        )
    c, kv = float(const.group(1)), float(k.group(1))

    # The constant IS sqrt(2Rk) in km, so it can be checked rather than trusted. A
    # mismatch means the formula string and the coefficient it names disagree, which
    # is the same defect as a page disagreeing with a file.
    implied = math.sqrt(2 * 6_371_000 * kv) / 1000
    if abs(implied - c) > 0.01:
        raise SystemExit(
            f"the layer's formula says {c} * sqrt(h) with refraction_k = {kv}, but "
            f"sqrt(2Rk) for that k is {implied:.4f}. The router's own two statements "
            f"of its method disagree; /routing will not publish either."
        )
    return {"constant_km_per_sqrt_m": c, "refraction_k": kv,
            "constant_check_sqrt_2Rk": round(implied, 4)}


def check_attribution(layer: dict) -> None:
    """The layer's credit must not say less than the manifest asks for.

    AGENTS.md: provenance travels as a pointer, and wherever a short attribution appears
    it may never attribute less than `conf/sources.yml` does. The router's layer is
    drawn from a source outside this project's own release -- EMODnet's bathymetry, CC
    BY 4.0 -- so /routing discharges an obligation that the site's build-wide
    attribution does not cover. rewt-46 found the same credit missing from the map
    entirely, which is what this exists to stop happening here.

    Compared on collapsed whitespace, like release.attribution_drift: the manifest wraps
    long strings, so a line break is a difference in the bytes and not in the obligation.
    """
    said = " ".join(str(layer.get("attribution", "")).split())
    if not said:
        raise SystemExit("the layer carries no `attribution`; /routing will not publish it")
    manifest = " ".join(MANIFEST.read_text().split())
    if said not in manifest:
        raise SystemExit(
            f"the layer's attribution is not in {MANIFEST}:\n  {said}\n"
            "Either the source is unregistered or the wording has drifted. A credit that "
            "does not match the manifest may be attributing less than the licence asks."
        )


def project() -> dict:
    layer = json.loads(LAYER.read_text())["properties"]
    reach = json.loads(REACH.read_text())
    check_attribution(layer)
    h = horizon(layer["horizon_formula"])

    out = {
        "generated_from": f"{LAYER}, {REACH}",
        "generator": "tools/docs/routing_page.py",
        "layer": {k: layer[k] for k in FROM_LAYER if k in layer},
        "reach": {k: reach[k] for k in FROM_REACH if k in reach},
        "horizon": h,
    }

    # THE OBSERVER TERM, computed from the layer's own height and constant rather than
    # described. A sighted range is the land's horizon PLUS the observer's own, and the
    # page must say which of the two any number is.
    #
    # `ranges_are_floors` exists because this page has already been wrong about it once,
    # in the way that is hardest to catch: the height is projected, so it changed from 0
    # to 10 by itself, while the prose around it went on saying "an eye at sea level, the
    # one height that assumes nothing" and offering a masthead as something further to
    # add. Ten metres IS the masthead. A projected value cannot fix the sentence built on
    # its old meaning, so the page branches on this flag instead of asserting either.
    c = h["constant_km_per_sqrt_m"]
    eye_m = float(layer.get("observer_height_m", 0) or 0)
    out["horizon"]["observer_height_m"] = eye_m
    out["horizon"]["observer_term_km"] = round(c * math.sqrt(eye_m), 1)
    out["horizon"]["ranges_are_floors"] = eye_m == 0
    # What a lower observer costs, as a DIFFERENCE rather than as that observer's own
    # horizon. The router's own note conflated the two -- 5.4 km is a 2 m observer's
    # horizon, 6.6 km is what they lose against a masthead -- so it is computed here.
    deck = DECK_EYE_M
    out["horizon"]["deck_eye_m"] = deck
    out["horizon"]["deck_term_km"] = round(c * math.sqrt(deck), 1)
    out["horizon"]["deck_sees_less_km"] = round(
        c * math.sqrt(eye_m) - c * math.sqrt(deck), 1)
    # The value a reader is likely to supply from memory, named so the page can say
    # what it is rather than leaving the difference to be discovered.
    out["horizon"]["common_wrong_constant"] = 3.86
    out["horizon"]["common_wrong_refraction_k"] = 1.17
    return out


def render(data: dict) -> str:
    return BANNER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed file differs from the artefacts")
    args = ap.parse_args()

    for path in (LAYER, REACH):
        if not path.exists():
            print(f"{path} not found -- run from the repository root", file=sys.stderr)
            return 2

    text = render(project())

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} is missing; run tools/docs/routing_page.py", file=sys.stderr)
            return 1
        if TARGET.read_text() != text:
            print(f"{TARGET} is stale: the router's artefacts have moved on. "
                  f"Run tools/docs/routing_page.py and commit the result.", file=sys.stderr)
            return 1
        print(f"{TARGET} is current against the router's artefacts.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text)
    print(f"Wrote {TARGET}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
