"""Generate `docs/trace/js/ids.js` from `rewt/ids.py`.

    python tools/tracer/gen_ids.py            # write
    python tools/tracer/gen_ids.py --check    # fail if the committed file is stale

WHY GENERATE RATHER THAN MIRROR. D-051 found `ids.py`'s one-module rule broken twice
because it was a sentence and not a test, both times in an f-string a separator change
went straight past — and one of them shipped. A second implementation in another language
recreates that hazard exactly: two copies agree only while somebody remembers to change
both, and an equality test over hand-listed inputs passes for every input somebody
happened to list. That is the enumeration problem, not the equality problem. Generating
turns drift into a dirty tree, which is loud.

WHAT GENERATION COVERS, AND WHAT IT DOES NOT — measured rather than assumed. Drifting
`rewt/ids.py`'s separator from `/` to `:` and re-running the checks: **freshness passed and
parity failed.** Generation propagates the values read out of the module (`PREFIX`,
`_PLACE_DP`); the *shape* of `publisher()` is in the template here, so a change to the
Python function body does not make the committed file stale. Parity is what catches that,
which is exactly the case rewt-d3 said to keep the equality test for — *it catches the
generator itself being wrong* — and it is not a hypothetical: it is the failure mode this
file would otherwise have.

WHY THE GENERATED FILE IS COMMITTED, WHICH LOOKS LIKE A BREACH AND IS NOT. `.gitignore`
opens with *nothing acquired, derived or built is committed*. That rule exists because a
committed artefact silently stops matching its inputs and nobody notices, because it looks
like data. A generated file whose regeneration is checked on every build is the one case
where the drift is made loud instead of silent — the rule's reason satisfied rather than
evaded. The violation would be a committed artefact that nothing regenerates. **The file
is committed only for as long as the check that guards it runs**: if `--check` is ever
dropped from the build, this file goes back into `.gitignore`.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from rewt import ids as py  # noqa: E402

OUT = pathlib.Path("docs/trace/js/ids.js")

TEMPLATE = '''/* GENERATED FROM rewt/ids.py BY tools/tracer/gen_ids.py — DO NOT EDIT.
 *
 * Regenerate with `python tools/tracer/gen_ids.py`. The build fails if this file and the
 * Python module disagree, so editing it by hand will be reverted by the next check rather
 * than quietly kept.
 *
 * ── WHAT IS HERE, AND THE LARGER PART THAT DELIBERATELY IS NOT ──────────────────────
 *
 * ONLY THE PROJECTION-FREE HALF OF THE SCHEME CROSSES INTO THE BROWSER.
 *
 * `rewt/ids.py` mints an identifier for geometry this project created by digesting the
 * coordinates, **rounded to {dp} decimal places**. That is a millimetre in EPSG:27700,
 * which is the CRS the build works in and far below the survey's own precision.
 *
 * The tracer works in CRS84 degrees, because that is what a GeoJSON selector carries and
 * what the sheet is georeferenced to. **{dp} decimal places of a degree is about 111
 * metres.** A geometry id minted here would therefore digest two courses a hundred metres
 * apart to the same identifier, and would never agree with the id Python gives the same
 * feature. Nothing would report an error: the string is well-formed, unique-looking and
 * wrong — which is `basin-unanchored` again, with a coordinate instead of a separator.
 *
 * So the tracer does not mint identifiers for geometry, and this file offers no way to.
 * That is not a limitation to be worked around later; it is AGENTS.md's own rule —
 * *EPSG:27700 throughout; EPSG:4326 only at export... reproject once, at the boundary* —
 * and the tracer sits on the 4326 side of that boundary. **A trace carries its geometry;
 * the ingest reprojects it and mints its id**, in the one module that is allowed to.
 *
 * What the browser genuinely needs is the ability to *reference* a feature the publisher
 * already identified — the link a traced course supersedes — and that is pure string
 * composition with no coordinates in it. It is all that follows.
 *
 * A happy consequence: with no digest, this file needs no crypto and stays synchronous.
 */

export const PREFIX = {prefix!r};

/** `os:link/12345` — a feature that is the publisher's, and says so.
 *
 *  ONE COLON, THEN SLASHES, and it is not cosmetic. `rewt` is a registered w3id prefix,
 *  and a CURIE expands by plain concatenation — so `rewt:basin/438` becomes
 *  https://w3id.org/rewt/basin/438, which resolves, while `rewt:basin:438` becomes
 *  https://w3id.org/rewt/basin:438, which is a legal URI that resolves to nothing. The
 *  moment this data is serialised as JSON-LD every identifier would be wrong at once and
 *  nothing would report it.
 */
export function publisher(kind, publisherId) {{
  return `os:${{kind}}/${{publisherId}}`;
}}

export function isPublisher(identifier) {{
  return String(identifier).startsWith('os:');
}}

export function isOurs(identifier) {{
  return String(identifier).startsWith(PREFIX + ':');
}}

/** The publisher's own id back out of ours, or null if we made the feature. */
export function publisherIdOf(identifier) {{
  if (!isPublisher(identifier)) return null;
  const s = String(identifier);
  return s.includes('/') ? s.slice(s.indexOf('/') + 1) : null;
}}
'''


def render() -> str:
    return TEMPLATE.format(prefix=py.PREFIX, dp=py._PLACE_DP).replace("'rewt'", "'rewt'")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed file differs from a fresh generation")
    args = ap.parse_args()

    fresh = render()
    if args.check:
        if not OUT.exists():
            print(f"{OUT} is missing; run `python tools/tracer/gen_ids.py`", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != fresh:
            print(f"{OUT} is stale — rewt/ids.py has moved under it.\n"
                  f"Run `python tools/tracer/gen_ids.py` and commit the result.",
                  file=sys.stderr)
            return 1
        print(f"{OUT} is current with rewt/ids.py")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(fresh, encoding="utf-8")
    print(f"wrote {OUT} ({len(fresh)} bytes) from rewt/ids.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
