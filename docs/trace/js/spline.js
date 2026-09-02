/* A curve through the clicks, for channels that bend.
 *
 * WHY THIS EXISTS, AND WHY IT IS NOT A WEAKENING OF THE EVIDENCE.
 * The obvious objection is that a spline invents geometry nobody looked at. It does. But
 * the polyline it replaces invents geometry too: a straight segment between two clicks
 * asserts the channel runs straight between them, which on a meander is simply false. So
 * the question is not evidence against inference, it is **which prior is less wrong**, and
 * for a watercourse a smooth curve beats a corner. Rivers do not have vertices.
 *
 * What follows from that is the whole design:
 *
 *   - The curve must PASS THROUGH the clicks. Those are the evidenced points — a person
 *     looked at each one — so an approximating spline (a B-spline) is disqualified no
 *     matter how smooth it is. Catmull-Rom interpolates, and is therefore the family.
 *   - CENTRIPETAL parameterisation (alpha = 0.5), not uniform. Uniform Catmull-Rom forms
 *     a LOOP when consecutive spans differ sharply in length — and two clicks a metre
 *     apart is not a contrived input, it is a contributor making a small correction. The
 *     measured case is in `check_spline.mjs`: clicks at 0, 150, 151 and 300 m give a
 *     self-intersecting curve under uniform and a clean one under centripetal, and a
 *     hairpin overshoots by 12.5 m under uniform against 2.9 m. A loop is not a river,
 *     and it reads as a rendering artefact rather than as the wrong claim it is.
 *
 *     **Centripetal is not uniformly tighter, and the honest statement is narrower than
 *     "it overshoots less".** On smooth, evenly-spaced bends it bulges slightly further
 *     from the control polygon than uniform does — measured, on three of six test inputs.
 *     What it buys is the absence of loops and cusps, which is a correctness property
 *     rather than a smaller number, and that is the trade being made.
 *   - The points it adds are marked `interpolated` and are NOT the same evidence as a
 *     click. They are offered to the assists, and where the ink supports one it is
 *     promoted and stops being an inference. Where it does not, it stays an inference and
 *     is drawn as the weakest of the four states.
 *
 * DENSIFY BY SAGITTA, NOT BY SPACING. Adding a point every N metres over-samples the
 * straight reaches and under-samples the bends the spline was added for — and it makes
 * the error a function of how the contributor clicked rather than a number anybody can
 * state. Subdividing until the chord is within `toleranceM` of the curve bounds the
 * deviation in metres, which is a claim that can go in the record and be checked. It is
 * Ramer-Douglas-Peucker run backwards, and shares its tolerance with the livewire's
 * `simplifyM` on purpose: densifying to a finer tolerance than the other assist simplifies
 * to would be two halves of one tool disagreeing about what a metre is worth.
 */

export const SPLINE_DEFAULTS = {
  alpha: 0.5,          // centripetal. 0 is uniform and cusps; 1 is chordal and slackens.
  toleranceM: 1.0,     // max distance from chord to curve. Matches LIVEWIRE simplifyM.
  minSpacingM: 1.0,    // never emit two points closer than this
  maxDepth: 8,         // 2^8 = 256 subdivisions per span is far past any real need
  maxPointsPerSpan: 64,
  /* Below this a drag was a click with a tremor in it. A pen tool that turned every
     imprecise press into a tangent would make the gesture unusable for the people least
     able to complain about it. */
  minHandleM: 0.5,
};

const R = 6378137;
const D2R = Math.PI / 180;

/* METRES, LOCALLY. The tolerance is in metres, so the maths has to happen somewhere
   metres are constant. Web Mercator is not that place — it stretches by about 1.6 at
   these latitudes, so a 1 m tolerance would silently become 1.6 m of ground. A local
   equirectangular frame about the trace's own centre is exact enough over the few
   kilometres a trace spans and costs one cosine. */
function frame(control) {
  let lat0 = 0, lon0 = 0;
  for (const [lon, lat] of control) { lon0 += lon; lat0 += lat; }
  lon0 /= control.length; lat0 /= control.length;
  const kx = Math.cos(lat0 * D2R) * R * D2R, ky = R * D2R;
  return {
    toXY: ([lon, lat]) => [(lon - lon0) * kx, (lat - lat0) * ky],
    toLonLat: ([x, y]) => [lon0 + x / kx, lat0 + y / ky],
  };
}

const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);

/* Barry-Goldman: the numerically honest way to evaluate a Catmull-Rom span at an
   arbitrary knot spacing. The matrix form assumes uniform knots and quietly gives the
   wrong curve when they are not, which is the whole point of using centripetal. */
function pointAt(p0, p1, p2, p3, t0, t1, t2, t3, t) {
  const lerp = (a, b, ta, tb) => {
    if (tb === ta) return a.slice();
    const w = (t - ta) / (tb - ta);
    return [a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w];
  };
  const A1 = lerp(p0, p1, t0, t1), A2 = lerp(p1, p2, t1, t2), A3 = lerp(p2, p3, t2, t3);
  const B1 = lerp(A1, A2, t0, t2), B2 = lerp(A2, A3, t1, t3);
  return lerp(B1, B2, t1, t2);
}

function knots(p0, p1, p2, p3, alpha) {
  const t0 = 0;
  const t1 = t0 + Math.pow(dist(p0, p1), alpha);
  const t2 = t1 + Math.pow(dist(p1, p2), alpha);
  const t3 = t2 + Math.pow(dist(p2, p3), alpha);
  return [t0, t1, t2, t3];
}

/* Distance from a point to the segment ab — the sagitta test's measuring stick. */
function offChord(p, a, b) {
  const vx = b[0] - a[0], vy = b[1] - a[1];
  const len2 = vx * vx + vy * vy;
  if (len2 === 0) return dist(p, a);
  let u = ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / len2;
  u = Math.max(0, Math.min(1, u));
  return Math.hypot(p[0] - (a[0] + u * vx), p[1] - (a[1] + u * vy));
}

/* Cubic Bezier, which is what a pen-tool handle IS. */
function bezierAt(P0, C1, C2, P3, t) {
  const u = 1 - t, a = u*u*u, b = 3*u*u*t, c = 3*u*t*t, d = t*t*t;
  return [a*P0[0] + b*C1[0] + c*C2[0] + d*P3[0],
          a*P0[1] + b*C1[1] + c*C2[1] + d*P3[1]];
}

/**
 * The centripetal Catmull-Rom span p1->p2, converted EXACTLY to Bezier controls.
 *
 * Exact rather than approximated, and that matters: it is what lets one code path serve
 * both modes. A span whose anchors nobody dragged must draw precisely the curve the
 * Catmull-Rom implementation drew before handles existed, or every measurement taken
 * against that mode stops applying to it.
 *
 * The span is a cubic in t, so four samples determine it. Evaluating at 0, 1/3, 2/3 and 1
 * and inverting the Bernstein basis recovers the control points without differentiating
 * Barry-Goldman by hand — which is where the sign errors live.
 */
function crControls(p0, p1, p2, p3, alpha) {
  const [t0, t1, t2, t3] = knots(p0, p1, p2, p3, alpha);
  const at = u => pointAt(p0, p1, p2, p3, t0, t1, t2, t3, t1 + (t2 - t1) * u);
  const P0 = at(0), Q1 = at(1/3), Q2 = at(2/3), P3 = at(1);
  const C1 = [], C2 = [];
  for (let k = 0; k < 2; k++) {
    const A = 27*Q1[k] - 8*P0[k] - P3[k];
    const B = 27*Q2[k] - P0[k] - 8*P3[k];
    C1[k] = (2*A - B) / 18;
    C2[k] = (B - 6*C1[k]) / 12;
  }
  return [C1, C2];
}

/* Recursive bisection in PARAMETER space, with the test in GROUND space. Splitting the
   parameter evenly is not splitting the curve evenly, which is why the test has to be the
   measured deviation rather than a count of levels. */
function refine(out, ev, ta, tb, pa, pb, tol, depth, budget) {
  if (depth >= budget.maxDepth || budget.n >= budget.max) return;

  /* SAMPLED AT SEVERAL POINTS, NOT JUST THE MIDPOINT. Testing only the midpoint bounds
     the midpoint and not the span: on an asymmetric bend the curve can sit within
     tolerance halfway along and wander well outside it at the quarter points, and the
     subdivision stops satisfied. `maxDeviationM` caught this claiming 1.75 m against a
     1.0 m tolerance — the parameter repeated back as though it were a measurement, which
     is the exact failure this module's comment warns about two screens up. */
  let worst = 0;
  for (const u of [0.2, 0.4, 0.5, 0.6, 0.8]) {
    const d = offChord(ev(ta + (tb - ta) * u), pa, pb);
    if (d > worst) worst = d;
  }
  if (worst <= tol) return;

  const tm = (ta + tb) / 2;
  const pm = ev(tm);
  refine(out, ev, ta, tm, pa, pm, tol, depth + 1, budget);
  /* Checked again HERE, not only on entry: the left half may have spent the budget, and
     pushing regardless is how a cap that reads like a cap overruns it. */
  if (budget.n >= budget.max) return;
  out.push(pm); budget.n++;
  refine(out, ev, tm, tb, pm, pb, tol, depth + 1, budget);
}

/**
 * Every span as a cubic Bezier, with a stated handle overriding the guessed tangent.
 *
 * THE WHOLE POINT OF THE HANDLE, in one line of code. Catmull-Rom must GUESS the tangent
 * at an anchor from its neighbours, and when the neighbours are a meander wavelength apart
 * the guess carries no information about the bend — measured, and worth about 2%. A drag
 * states the tangent instead, from somebody looking at the ink, and the same measurement
 * puts that at 24-47%. So a handle simply replaces the control point the guess produced.
 *
 * Symmetric, as a pen tool is: dragging H from an anchor sends the curve out along +H and
 * brings it in along -H, so one gesture shapes both sides and the curve stays smooth
 * through the anchor.
 */
function spansOf(P, handles, alpha) {
  const ext = [reflect(P[0], P[1]), ...P, reflect(P[P.length - 1], P[P.length - 2])];
  const spans = [];
  for (let i = 0; i + 3 < ext.length; i++) {
    const [p0, p1, p2, p3] = [ext[i], ext[i + 1], ext[i + 2], ext[i + 3]];
    let [C1, C2] = crControls(p0, p1, p2, p3, alpha);
    const hA = handles && handles[i], hB = handles && handles[i + 1];
    if (hA) C1 = [p1[0] + hA[0], p1[1] + hA[1]];
    if (hB) C2 = [p2[0] - hB[0], p2[1] - hB[1]];
    spans.push({ P0: p1, C1, C2, P3: p2, from: i, to: i + 1,
                 shaped: Boolean(hA || hB) });
  }
  return spans;
}

/**
 * A centripetal Catmull-Rom curve through `control`, densified to a sagitta tolerance.
 *
 * Returns `{ coords, origins, controlIndex, spans }` where `origins[i]` is `'clicked'`
 * for a control point and `'interpolated'` for one this module invented, and
 * `controlIndex[i]` is the index in `control` for a clicked point or `-1` otherwise.
 *
 * Fewer than three control points is not a refusal and not an error — two points ARE a
 * straight line, and there is nothing to curve. It returns them unchanged so the caller
 * has no special case to forget.
 */
export function splineThrough(control, opts = {}) {
  const o = { ...SPLINE_DEFAULTS, ...opts };
  const pts = dedupe(control);
  if (pts.length < 3) {
    return {
      coords: pts.map(p => p.slice()),
      origins: pts.map(() => 'clicked'),
      controlIndex: pts.map((_, i) => i),
      spans: [],
      why: pts.length < 2 ? 'nothing to curve yet' : 'two points are a straight line',
    };
  }

  const f = frame(pts);
  const P = pts.map(f.toXY);
  /* A handle arrives as the lon/lat the contributor dragged TO — what they actually did —
     and becomes an offset in metres here. Anything that is not a usable pair is dropped
     rather than trusted: a half-finished drag must degrade to a plain anchor, not to NaN. */
  const H = (opts.handles || []).map((h, i) => {
    if (!Array.isArray(h) || !Number.isFinite(h[0]) || !Number.isFinite(h[1])) return null;
    const q = f.toXY(h), a = P[i];
    if (!a) return null;
    const v = [q[0] - a[0], q[1] - a[1]];
    return Math.hypot(v[0], v[1]) < (o.minHandleM ?? 0.5) ? null : v;
  });
  const anyHandle = H.some(Boolean);

  const spans = spansOf(P, anyHandle ? H : null, o.alpha);

  const coords = [pts[0].slice()];
  const origins = ['clicked'];
  const controlIndex = [0];
  const spanInfo = [];

  for (const sp of spans) {
    const ev = t => bezierAt(sp.P0, sp.C1, sp.C2, sp.P3, t);
    const interior = [];
    const budget = { n: 0, max: o.maxPointsPerSpan, maxDepth: o.maxDepth };
    refine(interior, ev, 0, 1, sp.P0, sp.P3, o.toleranceM, 0, budget);

    let last = sp.P0, kept = 0;
    for (const q of interior) {
      if (dist(q, last) < o.minSpacingM || dist(q, sp.P3) < o.minSpacingM) continue;
      coords.push(f.toLonLat(q));
      /* SHAPED IS NOT INTERPOLATED, and collapsing them would be the quiet kind of lie.
         A point on a span whose anchor somebody dragged is derived from a stated human
         judgement about which way the channel leaves that anchor; a point on a span with
         no handle is derived from a smoothness assumption and nobody looked at it. */
      origins.push(sp.shaped ? 'shaped' : 'interpolated');
      controlIndex.push(-1);
      last = q; kept++;
    }
    coords.push(pts[sp.to].slice());
    origins.push('clicked');
    controlIndex.push(sp.to);
    spanInfo.push({ from: sp.from, to: sp.to, added: kept, shaped: sp.shaped,
                    chordM: dist(sp.P0, sp.P3) });
  }

  return { coords, origins, controlIndex, spans: spanInfo, shaped: anyHandle };
}

function reflect(a, b) { return [2 * a[0] - b[0], 2 * a[1] - b[1]]; }

/* Two clicks at the same place are one click. Left in, they give a zero-length span whose
   centripetal knot collapses, and the curve fills with NaN — the failure looks like a
   blank map rather than a bad point, so it is cheaper to refuse the duplicate here. */
function dedupe(control) {
  const out = [];
  for (const p of control || []) {
    if (!Array.isArray(p) || p.length < 2) continue;
    if (!Number.isFinite(p[0]) || !Number.isFinite(p[1])) continue;
    const prev = out[out.length - 1];
    if (prev && prev[0] === p[0] && prev[1] === p[1]) continue;
    out.push([p[0], p[1]]);
  }
  return out;
}

/**
 * The worst distance, in metres, between the returned polyline and the curve it samples.
 *
 * **This exists so the tolerance is a measurement and not a hope.** The subdivision stops
 * when a midpoint is within tolerance, which bounds that midpoint and not the whole span;
 * checking the claim needs an independent, much denser sampling. The tests use it, and it
 * is exported so a future caller can put a real number in the record rather than repeating
 * the parameter it asked for.
 */
export function maxDeviationM(control, result, opts = {}) {
  const o = { ...SPLINE_DEFAULTS, ...opts };
  const pts = dedupe(control);
  if (pts.length < 3) return 0;
  const f = frame(pts);
  const P = pts.map(f.toXY);
  const H = (opts.handles || []).map((h, i) => {
    if (!Array.isArray(h) || !Number.isFinite(h[0]) || !Number.isFinite(h[1])) return null;
    const q = f.toXY(h), a = P[i];
    if (!a) return null;
    const v = [q[0] - a[0], q[1] - a[1]];
    return Math.hypot(v[0], v[1]) < (o.minHandleM ?? 0.5) ? null : v;
  });
  const spans = spansOf(P, H.some(Boolean) ? H : null, o.alpha);
  const poly = result.coords.map(f.toXY);
  let worst = 0;
  for (const sp of spans) {
    for (let k = 0; k <= 200; k++) {
      const q = bezierAt(sp.P0, sp.C1, sp.C2, sp.P3, k / 200);
      let near = Infinity;
      for (let j = 0; j + 1 < poly.length; j++) near = Math.min(near, offChord(q, poly[j], poly[j + 1]));
      worst = Math.max(worst, near);
    }
  }
  return worst;
}
