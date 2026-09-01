/* GENERATED FROM rewt/ids.py BY tools/tracer/gen_ids.py — DO NOT EDIT.
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
 * coordinates, **rounded to 3 decimal places**. That is a millimetre in EPSG:27700,
 * which is the CRS the build works in and far below the survey's own precision.
 *
 * The tracer works in CRS84 degrees, because that is what a GeoJSON selector carries and
 * what the sheet is georeferenced to. **3 decimal places of a degree is about 111
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

export const PREFIX = 'rewt';

/** `os:link/12345` — a feature that is the publisher's, and says so.
 *
 *  ONE COLON, THEN SLASHES, and it is not cosmetic. `rewt` is a registered w3id prefix,
 *  and a CURIE expands by plain concatenation — so `rewt:basin/438` becomes
 *  https://w3id.org/rewt/basin/438, which resolves, while `rewt:basin:438` becomes
 *  https://w3id.org/rewt/basin:438, which is a legal URI that resolves to nothing. The
 *  moment this data is serialised as JSON-LD every identifier would be wrong at once and
 *  nothing would report it.
 */
export function publisher(kind, publisherId) {
  return `os:${kind}/${publisherId}`;
}

export function isPublisher(identifier) {
  return String(identifier).startsWith('os:');
}

export function isOurs(identifier) {
  return String(identifier).startsWith(PREFIX + ':');
}

/** The publisher's own id back out of ours, or null if we made the feature. */
export function publisherIdOf(identifier) {
  if (!isPublisher(identifier)) return null;
  const s = String(identifier);
  return s.includes('/') ? s.slice(s.indexOf('/') + 1) : null;
}
