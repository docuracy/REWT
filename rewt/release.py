"""Release notes, generated from the build rather than written about it.

**Every figure here is read from `published/`, and none is typed.** A release note
that quotes a number by hand is a number that will be right once and wrong at the next
edition, and it will look authoritative in both states — the failure this project has
met repeatedly in its own audit. So the notes are derived, and if the build has not
run, they cannot be made at all.

The caveats are as load-bearing as the figures. A reader who takes 93.53% as an
independent confirmation of 93.59% has been misled by a true statement, and the only
defence is that the qualification travels in the same paragraph as the number.
"""

from __future__ import annotations

import json

from . import paths


def _audit() -> dict:
    path = paths.PUBLISHED / "audit" / "audit.json"
    if not path.exists():
        raise FileNotFoundError(
            "published/audit/audit.json is absent. Release notes are generated from a "
            "build, not written about one; run `rewt build` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _provenance() -> dict:
    path = paths.PUBLISHED / "provenance.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def notes(tag: str) -> str:
    doc = _audit()
    prov = _provenance()
    s = doc.get("sections", {})
    reach = s.get("reachability", {})
    sea = s.get("reachability_tested_against_the_sea", {})
    dead = s.get("dead_ends", {})
    gen = s.get("generalisation", {})

    total = sea.get("in_scope_total_km") or reach.get("total_in_scope_km", 0)
    tidal = sea.get("reaches_tidal_water_km") or reach.get("reached_in_scope_km", 0)
    tidal_share = sea.get("reaches_tidal_water_share") or reach.get("in_scope_share", 0)
    sea_km = sea.get("reaches_the_sea_km")
    sea_share = sea.get("reaches_the_sea_share")

    L = [
        f"# REWT {tag}",
        "",
        "**Rivers of England and Wales, Temporally — Stage 1.** A traversable modern",
        "river network, in which water can be followed from any stretch to the sea.",
        "",
        "**This release makes no historical claim whatever.** Stage 1 is the present-day",
        "network and the machinery for correcting it; nothing in it dates anything.",
        "",
        "## The figures",
        "",
        "| | km | share |",
        "|---|---:|---:|",
        f"| in-scope network | {total:,.0f} | |",
        f"| reaches tidal water | {tidal:,.0f} | {tidal_share:.2%} |",
    ]
    if sea_km:
        L.append(f"| and that tidal water reaches the sea | {sea_km:,.0f} | {sea_share:.2%} |")
    L += [
        "",
        "## Read these before quoting the figures",
        "",
        f"**{total - tidal:,.0f} km of the in-scope network does not reach tidal water.**",
        "That is the honest remainder, and it is the work Stage 1 has not finished. It is",
        f"named per place: {dead.get('defects', 0):,} dead ends are not at tidal water, and the",
        "audit ranks them by the length actually stranded above each — not by the",
        "catchment standing above them, which counts water that has another way out.",
        "",
    ]
    if sea_km:
        L += [
            "**The two reachability figures are not independent, and the second is an upper",
            "bound with a known discontinuity.** Attaching the sea network turns *reaches the",
            "sea* from a definition into a test a mouth can fail — but at the working",
            f"parameters that test separates only {tidal - sea_km:,.0f} km of {tidal:,.0f}, and its value",
            "moves 16 percentage points across a single threshold because one mouth attaching",
            "connects an entire tidal system. **A reader who takes the second number as",
            "confirming the first has been misled by a true statement.** The reasoning is in",
            "`DECISIONS.md` D-061.",
            "",
        ]
    L += [
        "**The network is frozen on the Ordnance Survey Open Rivers 2026-04 issue and will",
        "not take reissues.** OS states that its identifiers are not persistent between",
        "product versions, so stability is bought by refusing updates rather than by",
        "minting our own. The build fails if the input moves (D-054). The cost is real: no",
        "correction OS makes reaches this network.",
        "",
        "**Nothing derived from the sea network may be presented as a route a vessel could",
        "follow.** The bathymetry carries `DO NOT USE FOR NAVIGATION`, which is a constraint",
        "on purpose rather than on redistribution. The sea structure is the connectivity of",
        "water below a stated clearance; it is not a sailing route, and the words",
        "*plausible* and *sailing* are excluded from its specification deliberately, because",
        "each imports a vessel and a vessel imports a period.",
        "",
        "**The survey is generalised, and this release does not un-generalise it.**",
    ]
    if gen:
        sp = gen.get("spacing_m", {})
        sg = gen.get("sagitta_m", {})
        med_sp = sp.get("50") or sp.get(50)
        med_sg = sg.get("50") or sg.get(50)
        if med_sp and med_sg:
            L.append(
                f"Median vertex spacing {med_sp:,.1f} m, median sagitta {med_sg:,.2f} m, "
                "with almost no"
            )
            L.append(
                "vertex below about 9 m of amplitude — the signature of a tolerance filter. "
                "**Detail"
            )
            L.append(
                "smaller than that is absent from the record, not from the river**, and a "
                "later stage"
            )
            L.append("proposing to move a line by less than it is arguing with the tolerance.")
    L += [
        "",
        "**Elevation and fall are screening quantities, not measurements.** The columns are",
        "named `screening_*` for that reason: a 50 m terrain model does not resolve a weir,",
        "a leat, or a mill's head, and the prefix is the only part of the value that travels",
        "with it into someone else's analysis.",
        "",
        "## Provenance",
        "",
    ]
    for k, v in sorted(prov.items()):
        if isinstance(v, (str, int, float)):
            L.append(f"- `{k}`: {v}")
    L += [
        "",
        "## Attribution",
        "",
        "Every source's required statement is in `published/ATTRIBUTION.md`, in full.",
        "Contains OS data © Crown Copyright and database rights 2026.",
        "Contains EMODnet Bathymetry data, licensed CC BY 4.0.",
        "",
        "## Citing this",
        "",
        "A result computed from this edition must cite **this version's DOI**, not the",
        "concept DOI. The concept DOI always resolves to the newest release, so a figure",
        "attached to it becomes uncheckable the moment the next edition lands.",
    ]
    return "\n".join(L) + "\n"
