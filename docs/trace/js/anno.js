/**
 * W3C Web Annotation profile for georeferenced traces — REWT's adaptation.
 *
 * Adapted from `tools/tracer/js/anno.js`, which is the scoping exercise's copy carried
 * across unmodified under D-053 and deliberately left there so this file's diff shows what
 * REWT changed. Five changes, each forced by a rule this repository acquired after that
 * module was written; the rest of the profile is unaltered and its reasoning stands.
 *
 * ── THE PROFILE, UNCHANGED ──────────────────────────────────────────────────────────
 *
 * A course traced off a historic sheet is an annotation in the strict sense: the target is
 * a region of a map and the body says what that region is. Two departures from GB-STAMP,
 * both forced by the subject. **The target is a place, not a canvas** — the same channel
 * may be drawn on four editions, and a course in canvas pixels is meaningless to anything
 * but one scan, so geometry is carried in world coordinates with the sheet recorded as
 * provenance alongside. And **there is no standard geo selector** — W3C defines none that
 * can carry a polyline on the earth — so this profile defines `GeoJSONSelector`, which is
 * honest where silently overloading `FragmentSelector` would not be.
 *
 * `creator` versus `generator` — W3C's own separation of who is responsible from what
 * software serialised it — expresses the thing a semi-automatic tracer most needs to
 * record: which vertices a person put down and which the algorithm chose.
 *
 * ── WHAT REWT CHANGED, AND WHY ──────────────────────────────────────────────────────
 *
 * 1. **It did not own its identifier scheme, and now it does not compose one at all.**
 *    The original takes `identifying` as an opaque `{source, label}` and leaves the caller
 *    to build the URN — which the predecessor does in a single template literal 1,885
 *    lines into a UI module. That is D-051's shape in JavaScript and worse in one respect:
 *    a wrong separator in a URN stays a legal URN and stops resolving, with no database to
 *    disagree and no schema to complain. References are built by `ids.js` and nowhere else.
 *
 * 2. **A supersession is not an identity**, and conflating them is what forced the URN.
 *    *What this course is* and *what it replaces* are different claims. The second is a
 *    documented profile extension, `rewt:supersedes`, alongside `GeoJSONSelector`.
 *
 * 3. **It had no date model.** `docs/epochs.md` requires a bound rather than a year, and
 *    that nobody types one. `when` is an LPF object computed from the sheet, and where the
 *    sheet's survey date is not known it says so explicitly — because an absent `start`
 *    means *nobody knows when this began*, which is a different statement from *no bound
 *    could be computed*, and the two must not collapse.
 *
 * 4. **Four fields are mandatory** — `reason`, `evidence`, `author`, `dated` — because a
 *    contribution that does not say who made it and when cannot be weighed a year later,
 *    and the contributor cannot run the build or see what their edit did. **And a
 *    coordinate**, because 332 corrections in this build carried neither geometry nor
 *    easting/northing and nobody could go and look at them.
 *
 * 5. **The sheet is a citation, never a `source_id`.** The exporter exempts exactly one
 *    value — `rewt`, this project's own geometry — and refuses everything else against
 *    `conf/sources.yml`. Stamping a trace with the NLS source would convert a ruling about
 *    the *trace* into a claim about the *tiles*: D-043 was the first and not the second.
 *
 * No DOM, no MapLibre. Still liftable.
 */

import { publisher } from 'ids';

const CONTEXT = 'http://www.w3.org/ns/anno.jsonld';

/** The one value the exporter's licence gate exempts. See change 5 above. */
export const SOURCE_ID = 'rewt';

/* A tile template reaches this module with the provider's key already substituted in —
   that is what makes the backdrop render. An annotation is a FILE, destined for
   `data/curated/` and for git, so a keyed URL written into one is a credential committed
   to a repository intended to become public. Refuse loudly rather than sanitise: a caller
   passing a keyed URL has made a mistake worth seeing, and a quietly stripped key teaches
   nothing. */
const CREDENTIAL = /[?&](key|api[-_]?key|access[-_]?token|token|signature|sig)=/i;

export function assertNoCredential(value, where) {
  if (typeof value === 'string' && CREDENTIAL.test(value)) {
    throw new Error(
      `${where}: refusing to write a URL that carries a credential — pass the `
      + 'published source URL, not the resolved tile template');
  }
  return value;
}

/* Great-circle length. Traces are short — hundreds of metres to a few kilometres — so the
   spherical figure is well inside the error of a line drawn by hand off a scan, and a
   geodesic library would be false precision. */
const R = 6371008.8;

export function lengthMetres(coordinates) {
  let total = 0;
  for (let i = 1; i < coordinates.length; i += 1) {
    const [lon1, lat1] = coordinates[i - 1];
    const [lon2, lat2] = coordinates[i];
    const p1 = (lat1 * Math.PI) / 180;
    const p2 = (lat2 * Math.PI) / 180;
    const dp = p2 - p1;
    const dl = ((lon2 - lon1) * Math.PI) / 180;
    const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    total += 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }
  return total;
}

/* ── the date, which nobody types ─────────────────────────────────────────────────── */

/**
 * The bound a sheet actually supports, in Linked Places `when` form.
 *
 * A channel drawn on a sheet surveyed in 1899 was there **by** 1899 and had not yet been
 * superseded **at** 1899. That is `start: {latest: 1899}, end: {earliest: 1899}` and it is
 * the whole of what the sheet says. It says nothing about when the channel began, and
 * `docs/epochs.md` is emphatic that a model requiring a start forces every source to
 * invent the half it does not have — which is how a datum comes to be fixed by the weakest
 * constraint in the evidence.
 *
 * WHERE THE SURVEY DATE IS NOT KNOWN, THIS RETURNS AN EXPLICIT UNKNOWN AND NOT NOTHING.
 * D-037 records that NLS state no date spans for these layers, and a seamless layer is a
 * composite of many sheets of different dates and so has no single survey date at all. An
 * *absent* `when` would read as "deliberately unbounded"; an empty `timespans` with
 * `certainty: 'unknown'` reads as "no bound could be computed", which is the true thing.
 * Unknown is not the same as unbounded (`docs/epochs.md`), and this is where that
 * distinction has to be drawn.
 */
/* A survey year no map could carry. The floor is deliberately generous — estate and
   county maps predate the Ordnance Survey by centuries — and its job is to catch a
   non-year that arithmetic turned into one, not to adjudicate cartographic history.
   `Number(null)` and `Number('')` are both 0, and `Number.isInteger(0)` is true: without
   this, a sheet with no recorded survey year produced `start: {latest: 0}` — a
   well-formed, entirely plausible-looking bound asserting the channel existed by the year
   zero, and reporting nothing. Found by the check that exists to make the refusals
   happen. */
const EARLIEST_PLAUSIBLE_SURVEY = 1500;
const LATEST_PLAUSIBLE_SURVEY = 2100;

export function boundFromSurveyYear(surveyYear, { certainty = 'certain' } = {}) {
  const y = typeof surveyYear === 'number' || (typeof surveyYear === 'string' && surveyYear.trim())
    ? Number(surveyYear) : NaN;
  if (!Number.isInteger(y) || y < EARLIEST_PLAUSIBLE_SURVEY || y > LATEST_PLAUSIBLE_SURVEY) {
    return {
      timespans: [],
      certainty: 'unknown',
      note: 'the survey date of this sheet is not recorded, so no bound follows from it',
    };
  }
  return {
    timespans: [{ start: { latest: y }, end: { earliest: y } }],
    certainty,
    note: `drawn on a sheet surveyed in ${y}: the channel was there by ${y}, `
      + 'and this says nothing about when it began',
  };
}

/** What the tool shows the contributor, so the claim is read back in words and confirmed. */
export function boundInWords(when) {
  if (!when || !when.timespans || !when.timespans.length) {
    return 'No date can be attached to this trace: this sheet carries no recorded survey '
      + 'year. That is recorded as unknown, which is a publishable fact.';
  }
  const t = when.timespans[0];
  const from = t.start?.latest ?? t.start?.in;
  return `This says the channel existed by ${from}, and nothing about when it began.`;
}

/* ── the annotation ───────────────────────────────────────────────────────────────── */

const REQUIRED = ['reason', 'evidence', 'author', 'dated'];

/**
 * One traced course.
 *
 * @param {object} o
 * @param {string} o.id                  IRI for this annotation (built by the caller's ids)
 * @param {Array<[number,number]>} o.coordinates  lon/lat, CRS84
 * @param {string[]} o.vertexOrigin      'clicked' | 'snapped', parallel to coordinates
 * @param {object} o.sheet               {id, label, url, attribution, zoom, surveyYear}
 * @param {?string} o.snapMode           'coloured' | 'monochrome' | 'hand' | null
 * @param {string} o.author              GitHub login of the person responsible
 * @param {string} o.dated               ISO date of the judgement
 * @param {string} o.reason              why this trace was made, in words
 * @param {string} o.evidence            what was looked at, including the sheet cited
 * @param {string[]} [o.supersedes]      publisher ids of what this course replaces
 * @param {object[]} [o.classifying]     {source, label}
 * @param {?string} [o.note]             the contributor's own words, including doubt
 * @param {?string} [o.name]             what the course is called, if known
 * @param {string} o.created             ISO 8601
 * @param {object} o.generator           the software
 */
export function traceAnnotation(o) {
  if (!Array.isArray(o.coordinates) || o.coordinates.length < 2) {
    throw new Error('traceAnnotation: a course needs at least two positions');
  }
  if (o.vertexOrigin && o.vertexOrigin.length !== o.coordinates.length) {
    throw new Error('traceAnnotation: vertexOrigin must parallel coordinates');
  }
  for (const field of REQUIRED) {
    if (!o[field]) {
      throw new Error(
        `traceAnnotation: \`${field}\` is required. Every judgement in this repository `
        + 'carries reason, evidence, author and dated — a contribution that does not say '
        + 'who made it and when cannot be weighed a year later.');
    }
  }
  assertNoCredential(o.sheet?.url, 'sheet.url');
  assertNoCredential(o.id, 'annotation id');

  const origins = o.vertexOrigin || o.coordinates.map(() => 'clicked');
  const snapped = origins.filter((v) => v === 'snapped').length;
  const when = boundFromSurveyYear(o.sheet?.surveyYear);

  const body = [];

  /* WHAT THIS COURSE REPLACES — a documented profile extension rather than an
     `identifying` body, because a supersession is not an identity. Every id comes from
     `ids.js`; nothing here composes one. */
  const supersedes = (o.supersedes || []).map((id) => (
    id.includes(':') ? id : publisher('link', id)));

  for (const c of o.classifying || []) {
    body.push({ purpose: 'classifying', source: c.source, ...(c.label ? { value: c.label } : {}) });
  }
  if (o.note) {
    body.push({ type: 'TextualBody', purpose: 'commenting', value: o.note, format: 'text/plain' });
  }

  /* The four mandatory fields travel INSIDE the annotation, not only on the event line
     that carries it. A trace is extracted into `data/curated/traces/` on its own, and at
     that point the event is elsewhere; an annotation that cannot say who made it and on
     what evidence is not a judgement this repository can hold. */
  body.push({
    type: 'TextualBody', purpose: 'assessing', format: 'text/plain', value: o.reason,
  });
  body.push({
    type: 'TextualBody', purpose: 'identifying', format: 'text/plain', value: o.evidence,
  });

  body.push({
    type: 'TextualBody',
    purpose: 'describing',
    format: 'application/json',
    value: JSON.stringify({
      length_m: Math.round(lengthMetres(o.coordinates) * 10) / 10,
      vertices: o.coordinates.length,
      vertices_snapped: snapped,
      vertices_clicked: o.coordinates.length - snapped,
      /* Parallel to the coordinate array, so a reader can tell position by position
         whether a person put the vertex there or an algorithm did. */
      vertex_origin: origins,
      traced_at_zoom: o.sheet?.zoom ?? null,
      /* WHAT THE ANNOTATION IS ENTITLED TO SAY. With snapping off no vertex came from a
         cost surface, so naming the sheet's colour mode would imply a machine read one
         when none did. `hand` is the truthful value. */
      snap_mode: o.snapMode ?? null,
      /* The one value the exporter's licence gate exempts. The sheet is cited in
         `evidence` and in `target.source`; it is never the source of the geometry. */
      source_id: SOURCE_ID,
    }),
  });

  return {
    '@context': CONTEXT,
    id: o.id,
    type: 'Annotation',
    ...(o.name ? { label: o.name } : {}),
    motivation: 'describing',
    body,
    /* PROFILE EXTENSION. Documented rather than smuggled, for the same reason
       `GeoJSONSelector` is: naming an extension is honest, overloading a standard term is
       not. */
    ...(supersedes.length ? { 'rewt:supersedes': supersedes } : {}),
    /* PROFILE EXTENSION. Linked Places `when`, per docs/epochs.md. Always present, so an
       unknown bound is stated rather than inferred from an absence. */
    when,
    target: {
      /* The sheet, as a citable published resource — never the tile template. */
      source: {
        id: o.sheet?.url ?? null,
        type: 'Dataset',
        ...(o.sheet?.label ? { label: o.sheet.label } : {}),
        ...(o.sheet?.id ? { 'dcterms:identifier': o.sheet.id } : {}),
        ...(o.sheet?.attribution ? { 'dcterms:rightsHolder': o.sheet.attribution } : {}),
      },
      selector: {
        type: 'GeoJSONSelector',
        conformsTo: 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        value: { type: 'LineString', coordinates: o.coordinates },
      },
    },
    creator: { type: 'Person', id: `https://github.com/${o.author}`, name: o.author },
    'dcterms:date': o.dated,
    generator: o.generator,
    generated: o.created,
    created: o.created,
  };
}

/** A representative coordinate for an annotation — every record carries a place. */
export function representativePoint(coordinates) {
  return coordinates[Math.floor(coordinates.length / 2)];
}
