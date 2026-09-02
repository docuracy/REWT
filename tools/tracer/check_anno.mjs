/**
 * Checks on the annotation profile. Exit non-zero on any failure.
 *
 *     node tools/tracer/check_anno.mjs
 *
 * Written to be invoked from the suite (`tests/` is rewt-6a's), so the guarantees are
 * enforced by something that runs. Each refusal is checked by making it happen: a check
 * that has never failed is a check nobody has tested.
 */
import { traceAnnotation, boundFromSurveyYear, boundInWords, lengthMetres, SOURCE_ID }
  from '../../docs/trace/js/anno.js';

let pass = 0; const fails = [];
const ok = (c, m) => (c ? pass++ : fails.push(m));
const throws = (fn, m) => { try { fn(); fails.push(m + ' (did not throw)'); } catch { pass++; } };

const good = {
  id: 'urn:uuid:11111111-2222-3333-4444-555555555555',
  coordinates: [[-0.0977, 51.5308], [-0.0961, 51.5321], [-0.0944, 51.5334]],
  vertexOrigin: ['clicked', 'clicked', 'clicked'],
  sheet: { id: 'os/six-inch-hertfordshire', label: 'OS Six-Inch, Hertfordshire',
           url: 'https://maps.nls.uk/os/6inch/', attribution: 'National Library of Scotland',
           zoom: 17, surveyYear: 1897 },
  snapMode: 'hand',
  author: 'docuracy', dated: '2026-09-01',
  reason: 'the surveyor letters this channel New Cut',
  evidence: 'OS six-inch, Hertfordshire, first edition, sheet XXIX',
  supersedes: ['1234567890'],
  created: '2026-09-01T13:00:00.000Z',
  generator: { id: 'https://docuracy.github.io/REWT/trace/', type: 'Software' },
};

// 1. the four mandatory fields, refused one at a time
for (const f of ['reason', 'evidence', 'author', 'dated']) {
  throws(() => traceAnnotation({ ...good, [f]: '' }), `missing ${f} must be refused`);
}

// 2. geometry preconditions
throws(() => traceAnnotation({ ...good, coordinates: [[-0.1, 51.5]] }),
  'a course of one position must be refused');
throws(() => traceAnnotation({ ...good, vertexOrigin: ['clicked'] }),
  'vertexOrigin not parallel to coordinates must be refused');

// 3. a credential in the sheet URL is refused LOUDLY, not stripped
throws(() => traceAnnotation({ ...good, sheet: { ...good.sheet, url: 'https://x/{z}.png?key=abc123' } }),
  'a keyed tile URL must be refused');

const a = traceAnnotation(good);

// 4. the CRS is stated, not assumed
ok(a.target.selector.conformsTo.endsWith('CRS84'), 'conformsTo states CRS84');
ok(a.target.selector.type === 'GeoJSONSelector', 'the profile extension is named');

// 5. the sheet is a citation, never the source of the geometry
const describing = JSON.parse(a.body.find((b) => b.format === 'application/json').value);
ok(describing.source_id === SOURCE_ID && SOURCE_ID === 'rewt',
  `source_id is 'rewt', not the NLS source (got ${describing.source_id})`);
ok(a.target.source['dcterms:identifier'] === 'os/six-inch-hertfordshire',
  'the sheet is cited in target.source');

// 6. supersession is composed by ids.js and is not an identity claim
ok(JSON.stringify(a['rewt:supersedes']) === JSON.stringify(['os:link/1234567890']),
  `supersedes uses the publisher scheme (got ${JSON.stringify(a['rewt:supersedes'])})`);
ok(!a.body.some((b) => b.purpose === 'identifying' && String(b.source || '').includes('link')),
  'a supersession is not smuggled into an identifying body');

// 7. nobody types a year: the bound is computed and it is the bound the sheet supports
ok(a.when.timespans[0].start.latest === 1897, 'start is bounded latest by the survey year');
ok(a.when.timespans[0].end.earliest === 1897, 'end is bounded earliest by the survey year');
ok(a.when.timespans[0].start.in === undefined, 'no start year is asserted');
ok(/existed by 1897/.test(boundInWords(a.when)), 'the claim is shown back in words');

// 8. an unknown survey date is STATED, not left absent
for (const bad of [undefined, null, '', '   ', 'c.1890', NaN, 0, 1899.5, -1899, 12, 3000, true, false, []]) {
  const w = boundFromSurveyYear(bad);
  ok(w.timespans.length === 0 && w.certainty === 'unknown',
    `an unrecorded survey year (${JSON.stringify(bad)}) is explicit, not absent`);
}
ok(/no recorded survey year/.test(boundInWords(boundFromSurveyYear(null))),
  'unknown is explained to the contributor');

// 9. provenance survives per vertex, and snapMode tells the truth
ok(JSON.stringify(describing.vertex_origin) === JSON.stringify(good.vertexOrigin),
  'vertex_origin is carried position by position');
ok(describing.snap_mode === 'hand', "snapMode 'hand' is recorded when snapping was off");
ok(describing.vertices_snapped === 0 && describing.vertices_clicked === 3,
  'the clicked/snapped counts agree with the origins');

// 10. length is plausible for the three points given (a few hundred metres)
const m = lengthMetres(good.coordinates);
ok(m > 250 && m < 500, `length is plausible (${m.toFixed(1)} m)`);

// 11. the responsible person is named
ok(a.creator.name === 'docuracy' && a['dcterms:date'] === '2026-09-01',
  'author and dated reach the annotation itself');

// 12. a splined course: the curve is recorded, the clicks are kept, and losing either is refused
const splined = {
  ...good,
  coordinates: [[-0.0977, 51.5308], [-0.09695, 51.53148], [-0.0961, 51.5321],
                [-0.09525, 51.53277], [-0.0944, 51.5334]],
  vertexOrigin: ['clicked', 'interpolated', 'clicked', 'interpolated', 'clicked'],
  controlPoints: [[-0.0977, 51.5308], [-0.0961, 51.5321], [-0.0944, 51.5334]],
  controlOrigin: ['clicked', 'clicked', 'clicked'],
  splineToleranceM: 1.0,
  splineDeviationM: 0.42,
};
const sp = traceAnnotation(splined);
const spBody = JSON.parse(sp.body.find((b) => b.purpose === 'describing').value);
ok(spBody.vertices_interpolated === 2, 'interpolated vertices are counted as their own kind');
ok(spBody.vertices_clicked === 3,
  'clicked is the remainder after snapped AND interpolated, not after snapped alone');
ok(JSON.stringify(spBody.control_points) === JSON.stringify(splined.controlPoints),
  'the clicks travel with the curve');
ok(spBody.spline === 'centripetal-catmull-rom', 'the curve names the family that made it');
ok(spBody.spline_deviation_m === 0.42, 'the MEASURED deviation is recorded, not the tolerance');
ok(spBody.spline_tolerance_m === 1.0 && spBody.spline_deviation_m <= spBody.spline_tolerance_m,
  'the measurement is within the tolerance asked for');

// the two refusals that keep a splined record honest
throws(() => traceAnnotation({ ...splined, controlPoints: undefined }),
  'a curve without its control points must be refused');
throws(() => traceAnnotation({ ...splined, splineDeviationM: undefined }),
  'a curve without a measured deviation must be refused');

// and an ordinary trace is not padded with spline fields it has no use for
ok(JSON.parse(a.body.find((b) => b.purpose === 'describing').value).control_points === undefined,
  'an unsplined trace carries no control_points');

// 13. a shaped course: the handles are recorded, and shaped is counted apart from interpolated
const shapedTrace = {
  ...splined,
  vertexOrigin: ['clicked', 'shaped', 'clicked', 'interpolated', 'clicked'],
  handles: [[-0.0975, 51.53095], null, null],
};
const sh = traceAnnotation(shapedTrace);
const shBody = JSON.parse(sh.body.find((b) => b.purpose === 'describing').value);
ok(shBody.vertices_shaped === 1 && shBody.vertices_interpolated === 1,
  'shaped and interpolated are counted apart — they are different evidence');
ok(shBody.vertices_clicked === 3,
  'clicked is the remainder after snapped, shaped AND interpolated');
ok(shBody.handles_stated === 1, 'the number of stated tangents is recorded');
ok(JSON.stringify(shBody.handles) === JSON.stringify(shapedTrace.handles),
  'the handles travel as dragged, parallel to the control points');
ok(/bezier/i.test(shBody.spline) && /catmull/i.test(shBody.spline),
  'the record names both curve families, because a mixed course used both');
ok(!/bezier/i.test(JSON.parse(sp.body.find((b) => b.purpose === 'describing').value).spline),
  'a course with no handle does not claim a Bezier it never used');
throws(() => traceAnnotation({ ...shapedTrace, controlPoints: undefined }),
  'a shaped course without its control points must be refused too');

console.log(`${pass} passed, ${fails.length} failed`);
for (const f of fails) console.error('  FAIL ' + f);
process.exit(fails.length ? 1 : 0);
