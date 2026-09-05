"""Seamarks as sightline sources: the NGA List of Lights, filtered to the extent.

**NOT IN USE. `sightline2.py` sets `use_seamarks: False` and the sightline is cast from
land alone.** This module is kept, fetched and parsed, because the decision to disable it
is a judgement that could be revisited and the work of getting the data should not have to
be done twice.

    python3 tools/router/lights.py

Run from the repository root; paths are relative (AGENTS.md).

TWO RULINGS, IN ORDER, BECAUSE THE SECOND REVERSED THE FIRST.

*4 September 2026, first:* use it, and queue the dating as a separate work package.

*4 September 2026, later:* limit the sightline to DAYTIME. Stephen: "they help with
night-time navigation but I cannot imagine that they are much use in day-time. We should
limit to day-time, I think, when the land itself can be seen." So the lights are out, and
what a sightline asserts is now narrower and better defined: land visible by day.

THE HEADLINE STATES THE SECOND RULING BECAUSE A CORRECTION BELOW A CLAIM GETS READ PAST.
This docstring opened with "STEPHEN'S RULING: use it" for a day while the pipeline had the
lights switched off, and recorded the reversal nowhere at all — so the module asserted the
opposite of its own behaviour to anyone who read the first paragraph. gotw-87 found the
same shape elsewhere today: a session read the CORRECTED file and relayed the superseded
claim anyway, because the correction sat several paragraphs below it. The fix is not a
longer note further down; it is that the first sentence carries the current state.

What follows is the caveat the first ruling knowingly accepted, kept because it is the
reason the dating package exists and would have to be rebuilt from scratch otherwise.

THE DATA HAS NO TEMPORAL INFORMATION. Its only date-like field is `noticeYear`, which is
when the entry was last AMENDED — 2015 for Bishop Rock, which has stood since 1858. So
this is a list of what stands now. Most of these lights are 18th and 19th century, and
some are 20th. Using them as sightline sources therefore puts structures of a known later
date into a surface that otherwise makes no historical claim at all.

That is a deliberate, recorded choice and not an oversight. It is ALSO the reason this
cannot silently become a claim about premodern navigation: until the dating package
lands, every reach that depends on a light is a reach available to a mariner of the
nineteenth century and not necessarily to one of the fifteenth.

WHY IT IS STILL BETTER THAN THE ALTERNATIVE. The comparison is not against nothing, it is
against Alvarez-Palau and Dunn's flat 20 m landmark at every one of 13,000 coastal
points — an assumption that raises a 2 m shore's reach by 232% and a mountain's by 1%,
doing most of its work exactly where the evidence is thinnest. A real light at a real
position with a real height is a weaker claim about date and a much stronger one about
place.

LICENCE — AND I GOT THIS WRONG. I wrote "a work of the United States Government: public
domain" from the general rule, without reading the publication. Pub 114's own notice is:

    (c) COPYRIGHT 2019 BY THE UNITED STATES GOVERNMENT.
    NO COPYRIGHT CLAIMED UNDER TITLE 17 U.S.C.

That disclaims copyright under the US statute and says nothing about anywhere else. The
identical notice is glossed in the SRTM specification as asserting protection for
products distributed OUTSIDE the United States, which is where this repository publishes
from. rewt-16 caught it; D-097 records it. Not registered, and it must not be registered
as public domain on the strength of who published it.

AND THE EXTERNAL CHECK IS SMALLER THAN I SAID. I offered the nominal ranges to two
sessions as "4,184 independent statements". `range` is a plain number in only 2,061 of
volume 114's 3,002 rows; it is null in 570 and in 371 it is a per-colour string —
"W. 15 ; R. 11" — on which float() throws, and where a parser taking the first integer
gets white and one taking the last gets green, both looking as though they worked.
`heightFeetMeters` is null in a different fifth. Rows carrying BOTH, inside the extent,
are the real sample size.

The general form is rewt-16's and outlives the episode: vetting a SOURCE and vetting the
RECORDS THAT DO THE WORK are two different audits, and passing the first says nothing
about the second. Both of us vetted this source. Neither asked what the answer was being
carried by, and it was television transmitters.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from extent import EXTENT
from generation import generation

VOLUMES = {113: "West coasts of Europe and Africa, Mediterranean",
           114: "British Isles, English Channel and North Sea",
           115: "Norway, Iceland and the Arctic",
           116: "Baltic Sea"}
API = ("https://msi.nga.mil/api/publications/ngalol/lights-buoys"
       "?volume={v}&includeRemovals=false&output=json")
CACHE = Path("tools/router/cache/lights")
OUT = Path("docs/router/data/lights_summary.json")
POS = re.compile(r"""(\d+)°\s*(\d+)'\s*([\d.]+)?"?\s*([NS])\s*(\d+)°\s*(\d+)'\s*([\d.]+)?"?\s*([EW])""")


def parse_position(s: str):
    m = POS.search(" ".join(str(s).split()))
    if not m:
        return None
    la = int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3) or 0) / 3600
    lo = int(m.group(5)) + int(m.group(6)) / 60 + float(m.group(7) or 0) / 3600
    return (-la if m.group(4) == "S" else la, -lo if m.group(8) == "W" else lo)


def parse_height_m(s):
    """`heightFeetMeters` is "144\\n44" — feet then metres. Take the metres."""
    if not s:
        return None
    parts = [p.strip() for p in str(s).split("\n") if p.strip()]
    try:
        return float(parts[-1]) if parts else None
    except ValueError:
        return None


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    w, s_, e, n = EXTENT
    keep, seen, per_vol = [], set(), {}
    for v, what in VOLUMES.items():
        p = CACHE / f"pub{v}.json"
        if not p.exists():
            print(f"fetching Pub {v} ({what})...")
            urllib.request.urlretrieve(API.format(v=v), p)
        rows = json.loads(p.read_text()).get("ngalol", [])
        got = 0
        for r in rows:
            if r.get("aidType") != "Lighted Aids":
                continue
            ll = parse_position(r.get("position", ""))
            h = parse_height_m(r.get("heightFeetMeters"))
            if not ll or h is None or h <= 0:
                continue
            la, lo = ll
            if not (s_ <= la <= n and w <= lo <= e):
                continue
            key = (round(la, 5), round(lo, 5), round(h, 1))
            if key in seen:                      # one structure, several characteristics
                continue
            seen.add(key)
            keep.append({"lat": round(la, 5), "lon": round(lo, 5), "height_m": h,
                         "name": " ".join(str(r.get("name", "")).split()),
                         "volume": v})
            got += 1
        per_vol[v] = got
        print(f"  Pub {v}: {got:,} lights inside the extent")

    hs = sorted(x["height_m"] for x in keep)
    med = hs[len(hs) // 2] if hs else 0
    (CACHE / "lights.json").write_text(json.dumps(keep))
    OUT.write_text(json.dumps({
        "generation": generation(),
        "what": "NGA List of Lights, lighted aids with a stated height, inside the extent",
        "source": "National Geospatial-Intelligence Agency, List of Lights, Radio Aids "
                  "and Fog Signals, Pub. 113-116, msi.nga.mil",
        "licence": "NOT public domain on the publication's own wording. Pub 114 states "
                   "'(c) COPYRIGHT 2019 BY THE UNITED STATES GOVERNMENT. NO COPYRIGHT "
                   "CLAIMED UNDER TITLE 17 U.S.C.' — a disclaimer under the US statute "
                   "only, which is glossed elsewhere as asserting protection for "
                   "distribution OUTSIDE the United States. This repository publishes "
                   "from the UK. Unresolved; the source is NOT registered and is NOT an "
                   "input (D-097).",
        "registered_in_conf_sources": False,
        "registration_note": "conf/sources.yml is the implementer's file. This is fetched "
                             "to the router's cache and the registration is PROPOSED.",
        "count": len(keep), "by_volume": per_vol,
        "height_m_median": med, "height_m_max": max(hs) if hs else None,
        "NO_TEMPORAL_INFORMATION": "the only date-like field is `noticeYear`, the year the "
                                   "ENTRY was last amended — 2015 for Bishop Rock, which "
                                   "has stood since 1858. These are the lights standing "
                                   "NOW. Most are 18th or 19th century. Every reach that "
                                   "depends on one is a reach available to a mariner of "
                                   "that date and not necessarily to an earlier one.",
        "deferred_work_package": "dating the lights: queued, deferred (Stephen, 4 Sep "
                                 "2026). Until it lands this surface carries undated "
                                 "structures by explicit decision, not by oversight.",
    }, indent=1))
    print(f"\n{len(keep):,} lights inside the extent, median height {med:.0f} m, "
          f"tallest {max(hs):.0f} m")
    print(f"wrote {CACHE / 'lights.json'} and {OUT}")


if __name__ == "__main__":
    main()
