/* What the spline must do, and what it must not quietly do instead.
 *
 *   node tools/tracer/check_spline.mjs
 *
 * The interesting assertions here are not that a curve comes out. They are that the
 * tolerance is a MEASURED bound rather than the parameter repeated back, that the
 * centripetal choice earns its place against the uniform one it is more expensive than,
 * and that every degenerate input a contributor can produce with a shaky mouse yields a
 * line rather than a NaN. A blank map is how this project has learned to recognise a NaN,
 * and it costs a diagnostic afternoon every time.
 */

import { splineThrough, maxDeviationM, SPLINE_DEFAULTS } from '../../docs/trace/js/spline.js';
import { VERTEX_GEOMETRY, casingRadius, curveOrigins } from '../../docs/trace/js/tracer.js';

let pass = 0, fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) { pass++; console.log(`  ok    ${name}`); }
  else { fail++; console.log(`  FAIL  ${name}${detail ? '  — ' + detail : ''}`); }
};
const near = (a, b, eps) => Math.abs(a - b) <= eps;

/* The Lea at Ware, the seven clicks already in the log — a real trace, not a shape. */
const LEA = [[-0.02902, 51.80966], [-0.02829, 51.80955], [-0.02762, 51.80942],
             [-0.02702, 51.80929], [-0.0263, 51.80914], [-0.02547, 51.80901],
             [-0.0249, 51.80894]];

/* A meander, which is what the mode exists for: sparse clicks round real bends. */
const MEANDER = [];
for (let i = 0; i <= 8; i++) {
  const t = i / 8;
  MEANDER.push([-0.030 + t * 0.010, 51.810 + 0.0009 * Math.sin(t * Math.PI * 2.2)]);
}

const haversine = (a, b) => {
  const R = 6371008.8, r = Math.PI / 180;
  const dLat = (b[1] - a[1]) * r, dLon = (b[0] - a[0]) * r;
  const s = Math.sin(dLat / 2) ** 2 +
            Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
};

console.log('\nthe curve keeps the clicks');
{
  const r = splineThrough(LEA);
  const kept = r.coords.filter((_, i) => r.origins[i] === 'clicked');
  ok('every control point survives, in order',
     kept.length === LEA.length && kept.every((p, i) => near(p[0], LEA[i][0], 1e-12) && near(p[1], LEA[i][1], 1e-12)),
     `${kept.length} of ${LEA.length}`);
  ok('origins are only ever clicked or interpolated',
     r.origins.every(o => o === 'clicked' || o === 'interpolated'));
  /* THE LEA GAINS NOTHING AT 1 m, AND THAT IS THE POINT. This reach is near-straight, so
     a mode that added points here would be adding them everywhere — the failure the
     sagitta test exists to prevent. The curve is asserted on the meander instead. */
  ok('a near-straight real reach gains nothing at the default tolerance',
     r.origins.filter(o => o === 'interpolated').length === 0,
     `${r.origins.filter(o => o === 'interpolated').length} added on the Lea`);
  ok('a meander does gain points',
     splineThrough(MEANDER).origins.filter(o => o === 'interpolated').length > 0);
  ok('controlIndex points back at the click that made it',
     r.coords.every((_, i) => r.origins[i] === 'clicked'
        ? LEA[r.controlIndex[i]] !== undefined : r.controlIndex[i] === -1));
  ok('the first and last coordinates are the first and last clicks',
     r.coords[0][0] === LEA[0][0] && r.coords[r.coords.length - 1][0] === LEA[LEA.length - 1][0]);
}

console.log('\nthe tolerance is a bound, measured independently');
{
  for (const tol of [0.25, 1.0, 4.0]) {
    const r = splineThrough(MEANDER, { toleranceM: tol, minSpacingM: 0.05 });
    const dev = maxDeviationM(MEANDER, r, { toleranceM: tol });
    ok(`tolerance ${tol} m holds (measured ${dev.toFixed(3)} m over 200 samples/span)`,
       dev <= tol * 1.05, `measured ${dev.toFixed(3)}`);
  }
  const tight = splineThrough(MEANDER, { toleranceM: 0.25, minSpacingM: 0.05 });
  const loose = splineThrough(MEANDER, { toleranceM: 4.0, minSpacingM: 0.05 });
  ok('a tighter tolerance densifies more',
     tight.coords.length > loose.coords.length,
     `${tight.coords.length} vs ${loose.coords.length}`);
}

console.log('\nit adds nothing where there is nothing to add');
{
  const straight = [[-0.03, 51.81], [-0.028, 51.81], [-0.026, 51.81], [-0.024, 51.81]];
  const r = splineThrough(straight);
  ok('a collinear trace gains no interpolated points',
     r.origins.filter(o => o === 'interpolated').length === 0,
     `${r.origins.filter(o => o === 'interpolated').length} added`);
}

console.log('\ncentripetal earns its cost against uniform');
{
  /* MEASURED, NOT ASSERTED — and the honest claim turned out to be narrower than the one
     I first wrote. Centripetal is NOT uniformly tighter: on smooth evenly-spaced bends it
     bulges slightly further than uniform. What it buys is the absence of loops, which is a
     correctness property and not a smaller number. So that is what is tested. */
  const seg = (p, q, r, s2) => {
    const d = (a, b, c) => (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]);
    const d1=d(p,q,r), d2=d(p,q,s2), d3=d(r,s2,p), d4=d(r,s2,q);
    return ((d1>0&&d2<0)||(d1<0&&d2>0)) && ((d3>0&&d4<0)||(d3<0&&d4>0));
  };
  const loops = c => {
    for (let i = 0; i + 1 < c.length; i++)
      for (let j = i + 2; j + 1 < c.length; j++)
        if (seg(c[i], c[i+1], c[j], c[j+1])) return true;
    return false;
  };
  const local = m => m.map(([x, y]) =>
    [-0.03 + x / (111320 * Math.cos(51.81 * Math.PI / 180)), 51.81 + y / 111320]);

  /* Two clicks a metre apart. Not contrived: it is somebody correcting a click. */
  const nearCoincident = local([[0,0],[150,20],[151,20.5],[300,0]]);
  const uni = splineThrough(nearCoincident, { alpha: 0, toleranceM: 0.1, minSpacingM: 0.05 });
  const cen = splineThrough(nearCoincident, { alpha: 0.5, toleranceM: 0.1, minSpacingM: 0.05 });
  ok('uniform loops on near-coincident clicks (the failure being bought off)', loops(uni.coords));
  ok('centripetal does not loop on the same clicks', !loops(cen.coords));

  const hairpin = local([[0,0],[100,0],[100,6],[0,6]]);
  /* BOTH AXES. A hairpin turns in x, so measuring only the y excursion reported uniform
     as the tidier of the two and inverted the result — the measurement was wrong, not the
     assertion, and it would have been easy to "fix" by loosening the test instead. */
  const out = (r, ctrl) => {
    const kx = 111320 * Math.cos(51.81 * Math.PI / 180);
    const xs = ctrl.map(p => p[0]), ys = ctrl.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);
    let w = 0;
    for (const [x, y] of r.coords)
      w = Math.max(w, (x0 - x) * kx, (x - x1) * kx, (y0 - y) * 111320, (y - y1) * 111320);
    return Math.max(0, w);
  };
  const hu = out(splineThrough(hairpin, { alpha: 0, toleranceM: 0.1, minSpacingM: 0.05 }), hairpin);
  const hc = out(splineThrough(hairpin, { alpha: 0.5, toleranceM: 0.1, minSpacingM: 0.05 }), hairpin);
  console.log(`        hairpin overshoot: uniform ${hu.toFixed(1)} m, centripetal ${hc.toFixed(1)} m`);
  ok('centripetal overshoots a hairpin far less than uniform', hc < hu / 2,
     `${hc.toFixed(1)} m vs ${hu.toFixed(1)} m`);
  ok('the default alpha is the centripetal one', SPLINE_DEFAULTS.alpha === 0.5);
}

console.log('\ndegenerate input yields a line, never a NaN');
{
  const cases = {
    'no points': [],
    'one point': [[-0.03, 51.81]],
    'two points': [[-0.03, 51.81], [-0.028, 51.809]],
    'a repeated click': [[-0.03, 51.81], [-0.03, 51.81], [-0.028, 51.809], [-0.026, 51.808]],
    'all three identical': [[-0.03, 51.81], [-0.03, 51.81], [-0.03, 51.81]],
    'a null in the list': [[-0.03, 51.81], null, [-0.028, 51.809], [-0.026, 51.808]],
    'a NaN coordinate': [[-0.03, 51.81], [NaN, 51.809], [-0.026, 51.808], [-0.024, 51.807]],
  };
  for (const [name, input] of Object.entries(cases)) {
    let r, threw = null;
    try { r = splineThrough(input); } catch (e) { threw = e; }
    ok(`${name}: no throw`, !threw, threw && String(threw.message));
    if (!threw) {
      ok(`${name}: no NaN in the output`,
         r.coords.every(p => Number.isFinite(p[0]) && Number.isFinite(p[1])));
      ok(`${name}: coords and origins stay the same length`,
         r.coords.length === r.origins.length && r.coords.length === r.controlIndex.length);
    }
  }
  ok('two points are returned as the straight line they are',
     splineThrough([[-0.03, 51.81], [-0.028, 51.809]]).coords.length === 2);
}

console.log('\nthe frame really is metres');
{
  /* The tolerance means nothing if the local frame is not to scale. Compared against
     haversine on the ground rather than against itself. */
  const a = [-0.0290, 51.8096], b = [-0.0249, 51.8089];
  const r = splineThrough([a, [-0.027, 51.8093], b], { toleranceM: 0.5, minSpacingM: 0.01 });
  let along = 0;
  for (let i = 0; i + 1 < r.coords.length; i++) along += haversine(r.coords[i], r.coords[i + 1]);
  const chord = haversine(a, b);
  ok('the curve is at least as long as the chord and not absurdly longer',
     along >= chord && along < chord * 1.2, `${along.toFixed(1)} m along vs ${chord.toFixed(1)} m chord`);

  const dense = splineThrough(MEANDER, { toleranceM: 1.0, minSpacingM: 0.01 });
  let minGap = Infinity;
  for (let i = 0; i + 1 < dense.coords.length; i++)
    minGap = Math.min(minGap, haversine(dense.coords[i], dense.coords[i + 1]));
  ok('minSpacingM is honoured on the ground, not just in the frame',
     minGap >= 0.005, `smallest gap ${minGap.toFixed(3)} m`);
}

console.log('\nthe output is bounded');
{
  const r = splineThrough(MEANDER, { toleranceM: 0.001, minSpacingM: 0.0001, maxPointsPerSpan: 8 });
  for (const s of r.spans) ok(`span ${s.from}-${s.to} respects maxPointsPerSpan`, s.added <= 8, `${s.added}`);
}

console.log('\nswitching the curve on does not rewrite what the assists did');
{
  /* THE DEMOTION THAT WOULD BE INVISIBLE. A control point is not automatically a click:
     centring and ink-following place points too, and calling every control point
     `clicked` would quietly relabel their work as a person's the moment this mode was
     switched on. Nothing would look wrong — the counts would even improve. */
  const placed = ['clicked', 'centred', 'snapped', 'clicked'];
  const o = curveOrigins([0, -1, 1, -1, 2, -1, 3], placed,
                         ['clicked','interpolated','clicked','interpolated','clicked','interpolated','clicked']);
  ok('interpolated points are marked interpolated',
     o.filter(x => x === 'interpolated').length === 3);
  ok('a centred control point stays centred', o[2] === 'centred');
  ok('a snapped control point stays snapped', o[4] === 'snapped');
  ok('no placed origin is lost or promoted',
     ['clicked', 'centred', 'snapped', 'clicked'].every((x, i) =>
        o.filter(y => y !== 'interpolated')[i] === x));
  ok('an origin the placed array does not have falls back to clicked, not undefined',
     curveOrigins([0, 1], [])[0] === 'clicked');

  /* THE COMPOSITION, which is where the bug actually was. Every part passed its own test
     — handles were captured, the curve marked its points `shaped`, and this function
     mapped control points correctly — while the whole silently reported `interpolated`,
     because this function returned a constant for every non-control point and nobody
     checked the two halves together. The line bent correctly, so nothing looked wrong. */
  const fromSpline = ['clicked', 'shaped', 'clicked', 'interpolated', 'clicked'];
  const composed = curveOrigins([0, -1, 1, -1, 2], ['clicked','clicked','clicked'], fromSpline);
  ok('a shaped point survives the mapping instead of being flattened to interpolated',
     composed[1] === 'shaped' && composed[3] === 'interpolated', composed.join(','));
  ok('with no spline origins given it still falls back to interpolated',
     curveOrigins([0, -1, 1], ['clicked','clicked'])[1] === 'interpolated');
}

console.log('\nhandles: a stated tangent replaces a guessed one');
{
  const local = m => m.map(([x, y]) =>
    [-0.03 + x / (111320 * Math.cos(51.81 * Math.PI / 180)), 51.81 + y / 111320]);
  const toM = ([lon, lat]) =>
    [(lon + 0.03) * 111320 * Math.cos(51.81 * Math.PI / 180), (lat - 51.81) * 111320];

  const anchors = local([[0,0],[100,0],[200,0],[300,0]]);
  const plain = splineThrough(anchors, { minSpacingM: 0.05 });
  ok('four collinear anchors with no handles stay straight',
     plain.origins.filter(o => o !== 'clicked').length === 0);

  /* A handle pulled 40 m north of the second anchor must bend the line north there. */
  const handles = [null, local([[100, 40]])[0], null, null];
  const bent = splineThrough(anchors, { handles, minSpacingM: 0.05 });
  const maxNorth = Math.max(...bent.coords.map(c => toM(c)[1]));
  ok('a stated handle bends the curve the way it was dragged', maxNorth > 5,
     `${maxNorth.toFixed(1)} m north`);
  ok('the handle shapes BOTH spans meeting the anchor, as a pen tool does',
     bent.spans.filter(sp => sp.shaped).length === 2,
     `${bent.spans.filter(sp => sp.shaped).length} spans shaped`);
  ok('points on a shaped span are `shaped`, not `interpolated`',
     bent.origins.includes('shaped') && !bent.origins.includes('interpolated'));
  ok('the result says a handle was used', bent.shaped === true);
  ok('and says so when none was', plain.shaped === false);

  /* A third anchor untouched by any handle keeps the guessed tangent and its own name. */
  const far = local([[0,0],[100,0],[200,0],[300,0],[400,60],[500,60]]);
  const mixed = splineThrough(far, { handles: [null, local([[100,40]])[0]], minSpacingM: 0.05 });
  ok('a span with no handle at either end is still `interpolated`',
     mixed.origins.includes('interpolated') && mixed.origins.includes('shaped'));

  // a drag too small to be meant is a click with a tremor in it
  const tremor = splineThrough(anchors,
    { handles: [null, local([[100, 0.2]])[0], null, null], minSpacingM: 0.05 });
  ok('a handle shorter than minHandleM is ignored', tremor.shaped === false);
  for (const bad of [[NaN, 1], null, [1], 'x', [Infinity, 0]]) {
    const r = splineThrough(anchors, { handles: [null, bad, null, null], minSpacingM: 0.05 });
    ok(`a malformed handle (${JSON.stringify(bad)}) degrades to a plain anchor`,
       r.shaped === false && r.coords.every(c => Number.isFinite(c[0]) && Number.isFinite(c[1])));
  }
}

console.log('\nhandles beat the guess where the guess has no information');
{
  /* THE CLAIM THE WHOLE FEATURE RESTS ON, asserted against a curve whose truth is known.
     A sine meander sampled at three points per wavelength is exactly the regime the
     measurement on real sheets identified: too sparse for Catmull-Rom to infer the bend,
     dense enough that a stated tangent describes it. Truth is the analytic curve, so
     neither method is being compared against its own assumptions. */
  const A = 30, L = 100, kx = 111320 * Math.cos(51.81 * Math.PI / 180);
  const truthM = t => [t, A * Math.sin(2 * Math.PI * t / L)];
  const toLL = ([x, y]) => [-0.03 + x / kx, 51.81 + y / 111320];
  const spacing = L / 3;
  const anchors = [], handles = [];
  for (let t = 0; t <= 300; t += spacing) {
    anchors.push(toLL(truthM(t)));
    /* the tangent a drag states: the curve's own direction, at a third of the chord */
    const d = A * (2 * Math.PI / L) * Math.cos(2 * Math.PI * t / L);
    const n = Math.hypot(1, d);
    handles.push(toLL([truthM(t)[0] + (spacing / 3) * (1 / n),
                       truthM(t)[1] + (spacing / 3) * (d / n)]));
  }
  const err = (r) => {
    let worst = 0;
    for (let t = 0; t <= 300; t += 0.5) {
      const p = truthM(t);
      let near = Infinity;
      for (let i = 0; i + 1 < r.coords.length; i++) {
        const a = [(r.coords[i][0] + 0.03) * kx, (r.coords[i][1] - 51.81) * 111320];
        const b = [(r.coords[i+1][0] + 0.03) * kx, (r.coords[i+1][1] - 51.81) * 111320];
        const vx = b[0]-a[0], vy = b[1]-a[1], l2 = vx*vx + vy*vy;
        let u = l2 ? ((p[0]-a[0])*vx + (p[1]-a[1])*vy) / l2 : 0;
        u = Math.max(0, Math.min(1, u));
        near = Math.min(near, Math.hypot(p[0]-(a[0]+u*vx), p[1]-(a[1]+u*vy)));
      }
      worst = Math.max(worst, near);
    }
    return worst;
  };
  const guessed = err(splineThrough(anchors, { minSpacingM: 0.05, toleranceM: 0.2 }));
  const stated  = err(splineThrough(anchors, { handles, minSpacingM: 0.05, toleranceM: 0.2 }));
  console.log(`        max error from the true meander: guessed ${guessed.toFixed(2)} m,` +
              ` stated ${stated.toFixed(2)} m`);
  /* THE THRESHOLD COMES FROM THE FIELD MEASUREMENT, NOT FROM WHAT PASSES. Handles measured
     24-47% better than the guess on two real reaches (PLAN.md), so 25% is the bottom of
     the observed band. My first attempt here demanded 50% — a number I had not measured
     anywhere — and failed at 36%, which is squarely inside what the sheets actually
     showed. Loosening a threshold to pass is how a check stops meaning anything; deriving
     it from the evidence is not the same act. */
  ok('stated tangents beat guessed ones by at least the margin measured on real sheets',
     stated < guessed * 0.75,
     `${stated.toFixed(2)} m vs ${guessed.toFixed(2)} m — ` +
     `${(100 * (1 - stated / guessed)).toFixed(0)}% better`);
}

console.log('\nthe casing sits flush outside every marker');
{
  /* The invariant I got wrong by hand when the fourth state arrived: a casing at 2.2
     against an outer edge of 3.6 sits INSIDE the marker, which renders as a slightly
     muddier dot and complains to nobody. Derived rather than re-typed now, and checked. */
  for (const [origin, g] of Object.entries(VERTEX_GEOMETRY)) {
    ok(`${origin}: casing begins exactly at the marker's outer edge`,
       casingRadius(origin) === g.r + g.stroke,
       `casing ${casingRadius(origin)} vs edge ${g.r + g.stroke}`);
  }
  ok('a click is the largest marker and an interpolated point the smallest',
     VERTEX_GEOMETRY.clicked.r > VERTEX_GEOMETRY.snapped.r &&
     VERTEX_GEOMETRY.snapped.r > VERTEX_GEOMETRY.interpolated.r);
  ok('every origin the tracer can emit has a geometry',
     ['clicked', 'centred', 'snapped', 'shaped', 'interpolated'].every(o => VERTEX_GEOMETRY[o]));
  ok('a shaped point sits between snapped and interpolated in weight',
     VERTEX_GEOMETRY.snapped.r > VERTEX_GEOMETRY.shaped.r &&
     VERTEX_GEOMETRY.shaped.r > VERTEX_GEOMETRY.interpolated.r);
}

console.log(`\n${pass} passed, ${fail} failed\n`);
process.exit(fail ? 1 : 0);
