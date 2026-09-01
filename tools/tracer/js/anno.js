/**
 * W3C Web Annotation profile for GEOREFERENCED TRACES.
 *
 * A course traced off a historic sheet is an annotation in the strict sense: the
 * target is a region of a map, and the body says what that region is. That is the
 * shape of the W3C Web Annotation Data Model, so this defines a PROFILE — a
 * documented use of the standard — rather than another schema. The profile
 * deliberately follows GB-STAMP's (WorldHistoricalGazetteer/gb-stamp), which models
 * map text the same way, so a tracer and a text-spotter emit compatible records.
 *
 * TWO DEPARTURES FROM GB-STAMP, both forced by what is being annotated.
 *
 *   1. THE TARGET IS A PLACE, NOT A CANVAS. GB-STAMP targets IIIF canvases and
 *      selects with an SvgSelector in image pixels. A trace has to survive the sheet
 *      it came from: the same channel may be drawn on four editions, and a course in
 *      canvas pixels is meaningless to anything but that one scan. So geometry is
 *      carried in world coordinates and the sheet is recorded as provenance
 *      alongside, not as the coordinate system.
 *
 *   2. THERE IS NO STANDARD GEO SELECTOR. W3C defines Fragment, CSS, XPath,
 *      TextQuote, TextPosition, DataPosition, Range and Svg selectors, and none of
 *      them can carry a polyline on the earth. `FragmentSelector` with a CRS
 *      `conformsTo` — which GB-STAMP uses — expresses a box, not a course. This
 *      profile therefore defines `GeoJSONSelector`, whose value is a GeoJSON
 *      geometry per RFC 7946 and so is always CRS84 (WGS 84, lon/lat). Naming it as
 *      a profile extension is honest; silently overloading FragmentSelector would
 *      not be.
 *
 * WHAT THE PROFILE EARNS. `creator` versus `generator` — W3C's own separation of
 * who is responsible from what software serialised it — turns out to express the
 * thing a semi-automatic tracer most needs to record: which vertices a person put
 * down and which the snapping algorithm chose. A trace where every vertex was
 * computed is a different evidential object from one a person placed by eye, and
 * downstream work is entitled to tell them apart. See `vertex_origin` below.
 *
 * No DOM, no MapLibre, no project vocabulary. This module is meant to be liftable.
 */

const CONTEXT = 'http://www.w3.org/ns/anno.jsonld';

/* Tile templates reach this module with the provider's API key already substituted
   in — that is what makes the backdrop render. An annotation is a FILE, destined for
   data/curated/ and for git, so a keyed URL written into one is a credential
   committed to a public repository. DECISIONS.md D-009 and D-075 are the standing
   rules about keys in docs/; this is the same rule at the other end of the pipe.
   Refuse loudly rather than sanitise: a caller passing a keyed URL has made a
   mistake worth seeing, and a quietly stripped key teaches nothing. */
const CREDENTIAL = /[?&](key|api[-_]?key|access[-_]?token|token|signature|sig)=/i;

export function assertNoCredential(value, where) {
  if (typeof value === 'string' && CREDENTIAL.test(value)) {
    throw new Error(
      `${where}: refusing to write a URL that carries a credential — pass the ` +
      'published source URL, not the resolved tile template');
  }
  return value;
}

/* Great-circle length. Traces are short — hundreds of metres to a few kilometres —
   so the spherical figure is well inside the error of the sheet being traced, and a
   geodesic library would be false precision on a line drawn by hand off a scan. */
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
    const a = Math.sin(dp / 2) ** 2
      + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    total += 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }
  return total;
}

/**
 * One traced course.
 *
 * @param {object} o
 * @param {string} o.id                     stable IRI for this annotation
 * @param {Array<[number,number]>} o.coordinates  lon/lat, CRS84
 * @param {string[]} o.vertexOrigin         'clicked' | 'snapped', parallel to coordinates
 * @param {object} o.sheet                  {id, label, url, attribution, zoom}
 * @param {?string} o.snapMode              'coloured' | 'monochrome' | 'hand' | null
 *                                         'hand' means the tracer's snapping was OFF and
 *                                         every vertex was placed by a person.
 * @param {?object} o.creator               the person responsible
 * @param {object} o.generator              the software
 * @param {string} o.created                ISO 8601
 * @param {object[]} [o.identifying]        {source, label} — what this course IS
 * @param {object[]} [o.classifying]        {source, label} — what KIND of thing
 * @param {?string} [o.note]                free text from the tracer
 * @param {?string} [o.name]                what the course is called, if known
 */
export function traceAnnotation(o) {
  if (!Array.isArray(o.coordinates) || o.coordinates.length < 2) {
    throw new Error('traceAnnotation: a course needs at least two positions');
  }
  if (o.vertexOrigin && o.vertexOrigin.length !== o.coordinates.length) {
    throw new Error('traceAnnotation: vertexOrigin must parallel coordinates');
  }
  assertNoCredential(o.sheet?.url, 'sheet.url');
  assertNoCredential(o.id, 'annotation id');

  const origins = o.vertexOrigin || o.coordinates.map(() => 'clicked');
  const snapped = origins.filter((v) => v === 'snapped').length;

  const body = [];
  for (const it of o.identifying || []) {
    body.push({ purpose: 'identifying', source: it.source, ...(it.label ? { value: it.label } : {}) });
  }
  for (const c of o.classifying || []) {
    body.push({ purpose: 'classifying', source: c.source, ...(c.label ? { value: c.label } : {}) });
  }
  if (o.note) {
    body.push({ type: 'TextualBody', purpose: 'commenting', value: o.note, format: 'text/plain' });
  }

  /* Measurements go in a `describing` body as JSON, following GB-STAMP's treatment
     of cap height: what a thing physically IS is a measurement, not a
     classification, and does not belong in a classifying body. */
  body.push({
    type: 'TextualBody',
    purpose: 'describing',
    format: 'application/json',
    value: JSON.stringify({
      length_m: Math.round(lengthMetres(o.coordinates) * 10) / 10,
      vertices: o.coordinates.length,
      vertices_snapped: snapped,
      vertices_clicked: o.coordinates.length - snapped,
      /* Parallel to the coordinate array, so a reader can tell, position by
         position, whether a person put the vertex there or an algorithm did. */
      vertex_origin: origins,
      traced_at_zoom: o.sheet?.zoom ?? null,
      /* Which cost surface the snapping followed, or null where the tracer had no
         raster and every segment is a straight line between clicks. Measured on this
         series: roughly one sheet in twenty is coloured, so `monochrome` is the
         normal case and `coloured` the lucky one. */
      snap_mode: o.snapMode ?? null,
    }),
  });

  return {
    '@context': CONTEXT,
    id: o.id,
    type: 'Annotation',
    /* What the course is called. Optional, and `label` rather than a body: a name is
       what the thing IS called, not a claim made about it, and the anno.jsonld context
       already carries `label` for exactly this. */
    ...(o.name ? { label: o.name } : {}),
    /* The annotation describes a region of a historic map and says what it is. The
       bodies carry `identifying` and `classifying` purposes of their own; the
       annotation-level motivation is the weaker, truthful claim. */
    motivation: 'describing',
    body,
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
        /* PROFILE EXTENSION — see the header. GeoJSON per RFC 7946, hence CRS84. */
        type: 'GeoJSONSelector',
        conformsTo: 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        value: { type: 'LineString', coordinates: o.coordinates },
      },
    },
    ...(o.creator ? { creator: o.creator } : {}),
    generator: o.generator,
    generated: o.created,
    created: o.created,
  };
}

/** An AnnotationPage — the standard container, so a file of traces is one document. */
export function annotationPage({ id, label, items, partOf }) {
  return {
    '@context': CONTEXT,
    id,
    type: 'AnnotationPage',
    ...(label ? { label } : {}),
    ...(partOf ? { partOf } : {}),
    items,
  };
}

/**
 * The same traces as a FeatureCollection.
 *
 * Not a replacement for the annotations — the annotation is the record, with its
 * provenance intact — but `data/curated/` is read by a pipeline that wants geometry,
 * and every GIS on earth opens GeoJSON. Both are diffable; both go in the file.
 */
export function toFeatureCollection(annotations) {
  return {
    type: 'FeatureCollection',
    features: annotations.map((a) => {
      const describing = (a.body || []).find(
        (b) => b.purpose === 'describing' && b.format === 'application/json');
      const measured = describing ? JSON.parse(describing.value) : {};
      const identifying = (a.body || []).filter((b) => b.purpose === 'identifying');
      const comment = (a.body || []).find((b) => b.purpose === 'commenting');
      return {
        type: 'Feature',
        id: a.id,
        properties: {
          annotation_id: a.id,
          name: a.label ?? null,
          source_sheet: a.target?.source?.['dcterms:identifier'] ?? null,
          identifies: identifying.map((b) => b.source).filter(Boolean).join('; ') || null,
          note: comment ? comment.value : null,
          creator: a.creator?.name ?? a.creator?.id ?? null,
          created: a.created ?? null,
          ...measured,
          /* An array per feature would not survive most GIS attribute tables; the
             counts above carry the same fact in a portable form. */
          vertex_origin: undefined,
        },
        geometry: a.target?.selector?.value ?? null,
      };
    }),
  };
}
