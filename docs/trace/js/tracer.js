/**
 * A georeferenced tracer for MapLibre — REWT, phase 2.
 *
 * Click to place a vertex; Enter finishes, Backspace undoes one click, Escape abandons.
 *
 * ADAPTED from `tools/tracer/js/tracer.js`, the scoping exercise's copy carried across
 * unmodified under D-053 and left there so this file's diff shows what changed. Two
 * changes, and one deliberate absence:
 *
 *   - **No livewire.** Phase 2 draws straight segments between clicks and nothing else, so
 *     `snapMode` is `'hand'` — which is the truthful value, because with no cost surface no
 *     vertex came from one. Following printed ink is phase 3.
 *   - **Centring, which is new here**: a vertex may be moved to the middle of the channel
 *     by measuring across the direction of travel (`ink.js`). Experimental, off by default.
 *   - The origin of every vertex is `clicked`, `centred`, or later `snapped`, and it is
 *     **visible while tracing** rather than only recorded in the file — a provenance field
 *     that only a later reader sees does nothing for the person deciding, in the moment,
 *     whether to trust the line.
 *
 * DESIGN CONSTRAINT, inherited and kept: this module knows nothing about rivers. It is
 * given a map, a way to find the current backdrop, and a callback; it hands back
 * coordinates and per-vertex provenance. What a trace MEANS belongs to the caller.
 */

import { loadPatch, patchPixel, patchLonLat, centreOnTransect, metresPerPixel } from './ink.js';
import { snapSegment, LIVEWIRE_DEFAULTS } from './livewire.js';
import { splineThrough, maxDeviationM, SPLINE_DEFAULTS } from './spline.js';

const SRC = 'trace-src';
const SRC_CANDIDATE = 'trace-candidate-src';
const SRC_VERTEX = 'trace-vertex-src';
const SRC_HANDLE = 'trace-handle-src';
/* Below this a press is a click, not a drag. Four pixels is about the wobble of a hand
   releasing a mouse button, and treating that as a stated tangent would put a direction
   into the record that nobody meant to state. */
const DRAG_PX = 4;

const emptyFC = () => ({ type: 'FeatureCollection', features: [] });

/**
 * THE FOUR VERTEX STATES, AS DATA RATHER THAN AS FOUR HAND-WRITTEN STYLE EXPRESSIONS.
 *
 * `r` is the marker's radius and `stroke` its width, so its outer edge is `r + stroke`
 * and the white casing must begin exactly there — flush, covering nothing. I got that
 * wrong by hand the first time a fourth state was added, giving `interpolated` a casing
 * at 2.2 against an outer edge of 3.6, so the ring sat INSIDE the marker it was meant to
 * protect. It would have rendered as a slightly muddier dot and nothing would have
 * complained. `check_spline.mjs` asserts the invariant now instead of me re-deriving it.
 *
 * Sizes ARE the hierarchy: a click is a judgement and is largest; an interpolated point
 * is nobody's decision and is smallest. Colour is checked separately, in the palette
 * audit, because "they look different to me" is not evidence.
 */
/**
 * The origin of every point on the curve: `interpolated` where the spline invented one,
 * and OTHERWISE WHATEVER THE PLACED POINT ALREADY WAS.
 *
 * Pure, and exported, so the mapping can be checked without a map. The temptation is to
 * call a control point `clicked` — it is a control point, after all — and that would
 * silently demote every centred and snapped vertex the moment splining was switched on,
 * rewriting the provenance of work the assists had done. The curve passing through a
 * centred vertex does not make it a click.
 */
export function curveOrigins(controlIndex, placed, splineOrigins) {
  return controlIndex.map((ci, i) => (ci >= 0
    ? (placed[ci] || 'clicked')
    /* THE SPLINE'S OWN VERDICT, not a constant. This returned a hardcoded
       `'interpolated'` until the pen arrived, and then silently threw away every
       `shaped` the curve had worked out — the handles were captured, stored, passed in
       and honoured by the geometry, and the provenance was overwritten one function
       later. It cost nothing visible: the line bent correctly and the record simply
       understated what a person had contributed. */
    : (splineOrigins?.[i] || 'interpolated')));
}

export const VERTEX_GEOMETRY = {
  clicked:      { r: 5,   stroke: 2   },
  centred:      { r: 5,   stroke: 2   },
  snapped:      { r: 2.5, stroke: 2   },
  shaped:       { r: 2.4, stroke: 1.5 },
  interpolated: { r: 2.2, stroke: 1.4 },
};

/** The casing radius for each state: flush with the marker's outer edge, by construction. */
export const casingRadius = (o) => VERTEX_GEOMETRY[o].r + VERTEX_GEOMETRY[o].stroke;

const byOrigin = (pick, fallback) => ['match', ['get', 'origin'],
  'interpolated', pick('interpolated'),
  'shaped', pick('shaped'),
  'snapped', pick('snapped'),
  'centred', pick('centred'),
  fallback];

export function createTracer({ map, backdrop, tileSource, onChange, centring = false, snapping = false, splining = false }) {
  const state = {
    active: false,
    /* SNAPPING IS A SEPARATE SWITCH FROM TRACING, and conflating them made the predecessor's
       tool unusable where it was most needed. Arming the map for clicks and following the
       printed ink between them are different decisions: the ink runs out, forks, or is
       crossed by a road, and there the only honest line is the one a person draws. With
       this off a vertex lands exactly where it was put, the segment to it is straight, and
       the annotation records every vertex as `clicked` — which is what it is. */
    snapping,
    centring,
    /* A THIRD SWITCH, AND DELIBERATELY NOT A THIRD ASSIST. Centring and ink-following read
       the sheet; this one does not read anything. It draws a curve through the points that
       are already there, on the argument that a straight segment between two clicks is
       ALSO an invention — one asserting the channel runs straight, which round a bend is
       simply false. The points it adds are marked `interpolated` and are the weakest thing
       the tool records. */
    splining,
    /* SHARED WITH THE LIVEWIRE'S `simplifyM` ON PURPOSE. One half of the tool densifying
       to a finer tolerance than the other simplifies to would be two halves disagreeing
       about what a metre is worth, and the disagreement would show up as points appearing
       and vanishing as a contributor toggled switches. */
    splineToleranceM: SPLINE_DEFAULTS.toleranceM,
    lastSnap: null,
    snapAt: 0,
    coordinates: [],
    origin: [],
    /* Parallel to `coordinates`, and null wherever nobody dragged. Stored as the lon/lat
       the contributor dragged TO — what they actually did — rather than as a tangent
       vector, which is a derived thing and would lose the gesture. */
    handles: [],
    candidate: [],
    patch: null,
    patchKey: null,
    lastCentre: null,
    busy: false,
  };

  /* Adding a source before the style is ready throws. Try and retry on `styledata` rather
     than testing `isStyleLoaded()`, which stays false while ANY source is resolving — a
     single unrelated source that never resolves would disable the tracer permanently on a
     map that is otherwise perfectly usable. */
  let pending = false;
  function retryLater() {
    if (pending) return;
    pending = true;
    map.once('styledata', () => { pending = false; if (ensureLayers()) redraw(); else retryLater(); });
  }

  function ensureLayers() {
    if (map.getLayer('trace-vertices')) return true;
    try {
      for (const id of [SRC, SRC_CANDIDATE, SRC_VERTEX]) {
        if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: emptyFC() });
      }
      map.addLayer({ id: 'trace-line', type: 'line', source: SRC,
        paint: { 'line-color': '#ff3b6b', 'line-width': 3, 'line-opacity': 0.95 } });
      map.addLayer({ id: 'trace-candidate', type: 'line', source: SRC_CANDIDATE,
        /* Dashed, because it is not committed. */
        paint: { 'line-color': '#ff3b6b', 'line-width': 2, 'line-dasharray': [2, 2], 'line-opacity': 0.8 } });
      /* A CASING, BECAUSE THE GROUND IS THE COMPETITOR AND NOT THE OTHER MARKERS.
         The three origin colours separate from each other well past threshold — but they
         are drawn ON a historic sheet, which is 20–30% ink, and a marker landing on a
         hachure, a parish boundary or a block of stipple is competing with that. Measured
         against ink sampled from real NLS six-inch tiles rather than guessed at
         (rewt-fc's `GROUNDS`, tools/palette_audit.py):

             on the worst real ink, worst vision type
               clicked   dE  1.9 on #878070 (protan)   <- BELOW the just-noticeable difference
               centred   dE 31.1
               snapped   dE 23.3

         The worst case falls on the marker that matters MOST — the person's own
         judgement, the only thing the display obligation exists to distinguish — while
         the two machine-placed states are safe. The wrong way round, and mechanically so:
         `clicked` is the one marker drawn SOLID in its own colour, so it is wholly against
         the ground, where the other two are white-filled and carry their own pale
         interior. A white casing gives all three that interior. Measured after:

               clicked 30.8   centred 26.9   snapped 39.3   (against the casing)
               casing vs the four sampled inks   33.5 / 43.0 / 51.3 / 55.7
               casing vs paper                    4.4   <- correctly invisible where
                                                            nothing is wrong

         Both of those lines are constraints, in opposite directions. The ring is 2 px, so
         its OUTER edge is casing-against-ink and not marker-against-casing: it has to
         clear the ink on its own account rather than merely give the marker something to
         sit on. It does, by 33.5 at worst — better than any of the three markers managed
         unaided. So do not thin the ring or tint it toward the paper to soften it. And do
         not "fix" the 4.4: a ring that showed on blank paper would be decoration, since
         the markers already clear paper at 21.3 and up.

         The same move as the viewer's line casings, for the same reason. Ring geometry is
         flush with the marker and does not overlap it: marker 5+2 px, casing 7..9;
         snapped marker 2.5+2, casing 4.5..6.5. */
      /* HANDLES ARE AN EDITING AID, NOT EVIDENCE, and are drawn only while tracing.
         Leaving them on a finished line would put a construction line into every
         screenshot and invite a reader to take the tangent for something the survey drew. */
      map.addSource(SRC_HANDLE, { type: 'geojson', data: emptyFC() });
      map.addLayer({ id: 'trace-handle', type: 'line', source: SRC_HANDLE,
        paint: { 'line-color': '#880000', 'line-width': 1.2, 'line-dasharray': [2, 2],
                 'line-opacity': 0.9 } });
      map.addLayer({ id: 'trace-handle-knob', type: 'circle', source: SRC_HANDLE,
        filter: ['==', ['geometry-type'], 'Point'],
        paint: { 'circle-radius': 3.2, 'circle-color': '#ffffff',
                 'circle-stroke-color': '#880000', 'circle-stroke-width': 1.6 } });
      map.addLayer({ id: 'trace-vertex-casing', type: 'circle', source: SRC_VERTEX,
        paint: {
          'circle-color': 'rgba(0,0,0,0)',
          'circle-radius': byOrigin(casingRadius, casingRadius('clicked')),
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 2,
          'circle-stroke-opacity': 0.95,
        } });
      map.addLayer({ id: 'trace-vertices', type: 'circle', source: SRC_VERTEX,
        paint: {
          /* ── MEASURED FOR COLOUR VISION, NOT CHOSEN BY EYE ─────────────────────────
             The whole display obligation is carried by these three, so "they look
             different to me" is not evidence. Run through `tools/palette_audit.py`
             (rewt-fc's, which found the viewer's `form` theme collapsing to one colour),
             CIEDE2000 separation under normal, protan, deutan and tritan vision:

                clicked vs centred   worst 34.4 (protan)
                clicked vs snapped   worst 35.8 (normal)
                centred vs snapped   worst 16.4 (deutan)   <- the tightest pair

             All clear the tool's threshold of 15. Marker against marker is only the easy
             half, though, and measuring it alone is what let the ink failure through —
             see the casing above, and `against_ground` for the half that decides it. The tightest pair is the one that
             matters least — both are machine-placed — while **a person's vertex against a
             machine's, which is the distinction the design rests on, is the widest.**
             Shape carries it too: clicked is solid and 5 px, the others hollow, snapped
             2.5 px. Colour alone would still be a single point of failure.

             THE DISPLAY OBLIGATION, not decoration. A vertex a person put down and one an
             algorithm moved are different evidence, and the person most likely to
             over-trust the second is the contributor, in the moment, with the line in
             front of them. Clicked reads solid; centred reads hollow. */
          'circle-color': ['case', ['==', ['get', 'origin'], 'clicked'], '#ff3b6b', '#ffffff'],
          /* THE FOURTH STATE WAS NOT A FREE CHOICE. Six colours picked by eye all failed
             the threshold against one of the three already here — the space is crowded —
             so it was searched rather than guessed: of 968 colours clearing dE 15 against
             clicked, centred, snapped AND the white casing, this dark neutral measures
             30.5 at worst (clicked 32.4, centred 44.9, snapped 30.5, casing 73.4).

             DARK, YET THE LEAST ASSERTIVE OF THE FOUR. Weight here is carried by SIZE and
             not by washing the colour out — a faint marker would be an unreadable one on a
             sheet that is a fifth ink, which is the mistake the casing exists to undo. So
             it reads as least by being smallest: 2.2 px against snapped's 2.5 and a
             click's 5. */
          'circle-stroke-color': ['match', ['get', 'origin'],
            'centred', '#00b4d8',
            'snapped', '#7a5cff',
            'interpolated', '#2b2b33',
            /* Searched, not chosen: of 604 colours clearing dE 15 against all four
               existing markers and the casing, this measures 26.6 at worst. Deliberately
               the click's own family and deliberately darker — a shaped point is derived
               from a direction a person stated, so it belongs with the human end and
               below it. */
            'shaped', '#880000',
            '#ff3b6b'],
          'circle-stroke-width': byOrigin(o => VERTEX_GEOMETRY[o].stroke, VERTEX_GEOMETRY.clicked.stroke),
          /* A snapped vertex is one of dozens in a run and was nobody's decision; a clicked
             one is a judgement. Drawing them the same size would give the run a visual
             weight it has not earned. */
          'circle-radius': byOrigin(o => VERTEX_GEOMETRY[o].r, VERTEX_GEOMETRY.clicked.r),
        } });
      return true;
    } catch {
      retryLater();
      return false;
    }
  }

  /**
   * WHAT IS DRAWN AND WHAT IS RECORDED, which with splining on are not the placed points.
   *
   * The placed points — clicked, centred, snapped — stay the record of what happened;
   * this is a derived view over them and nothing here mutates `state.coordinates`. Undo
   * therefore removes a click rather than an interpolated point, which is the only thing
   * a person can mean by undo.
   *
   * **Recomputed from scratch on every redraw, and the whole curve rather than the last
   * span.** An interpolating spline's shape near a point depends on its NEIGHBOURS, so
   * adding a click legitimately changes the span before it. Freezing completed spans would
   * be cheaper and would draw a line that is not the curve the coordinates describe — the
   * kind of divergence that survives review because both halves look right.
   */
  function curve() {
    if (!state.splining || state.coordinates.length < 3) {
      return { coords: state.coordinates, origins: state.origin, controlIndex: null, deviationM: 0 };
    }
    const r = splineThrough(state.coordinates,
      { toleranceM: state.splineToleranceM, handles: state.handles });
    return {
      coords: r.coords,
      origins: curveOrigins(r.controlIndex, state.origin, r.origins),
      controlIndex: r.controlIndex,
      deviationM: r.spans.length ? maxDeviationM(state.coordinates, r) : 0,
    };
  }

  /** The tangent at an anchor, drawn both ways because a pen-tool handle is symmetric. */
  function paintHandles() {
    if (!map.getSource || !map.getSource(SRC_HANDLE)) return;
    const feats = [];
    const add = (anchor, to) => {
      const back = [2 * anchor[0] - to[0], 2 * anchor[1] - to[1]];
      feats.push({ type: 'Feature', properties: {},
                   geometry: { type: 'LineString', coordinates: [back, anchor, to] } });
      feats.push({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: to } });
      feats.push({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: back } });
    };
    if (state.active) {
      state.handles.forEach((h, i) => { if (h && state.coordinates[i]) add(state.coordinates[i], h); });
      if (drag?.dragged && drag.to) add([drag.at.lng, drag.at.lat], [drag.to.lng, drag.to.lat]);
    }
    map.getSource(SRC_HANDLE).setData({ type: 'FeatureCollection', features: feats });
  }

  function redraw() {
    if (!map.getLayer('trace-vertices')) { onChange?.(summary()); return; }
    paintHandles();
    const c = curve();
    map.getSource(SRC).setData(c.coords.length >= 2
      ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: c.coords } }
      : emptyFC());
    map.getSource(SRC_CANDIDATE).setData(state.candidate.length >= 2
      ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.candidate } }
      : emptyFC());
    map.getSource(SRC_VERTEX).setData({
      type: 'FeatureCollection',
      features: c.coords.map((coord, i) => ({
        type: 'Feature', properties: { origin: c.origins[i] || 'clicked' },
        geometry: { type: 'Point', coordinates: coord },
      })),
    });
    onChange?.(summary());
  }

  function summary() {
    return {
      active: state.active,
      centring: state.centring,
      snapping: state.snapping,
      splining: state.splining,
      lastSnap: state.lastSnap,
      /* TWO COUNTS, NOT ONE. `vertices` is what the person placed and `drawn` is what the
         curve holds; reporting only the second would let a mode that quietly quadrupled
         the geometry read as a productive afternoon. */
      vertices: state.coordinates.length,
      drawn: state.splining ? curve().coords.length : state.coordinates.length,
      splineDeviationM: state.splining ? curve().deviationM : 0,
      handlesStated: state.handles.filter(Boolean).length,
      coordinates: state.coordinates.slice(),
      origin: state.origin.slice(),
      lastCentre: state.lastCentre,
      busy: state.busy,
    };
  }

  /* ── the sheet under the cursor ────────────────────────────────────────────────── */

  /**
   * The sheet's own best resolution, ALWAYS — never the screen's.
   *
   * The lifted module said this and the first REWT version did not do it: it took
   * `min(max, max(14, round(mapZoom)))`, which caps at the layer's maximum but otherwise
   * follows the map. So a contributor at map zoom 16.4 read the six-inch at z16, where
   * 1.48 m per pixel blurs a bank line into the paper and **every vertex is refused with
   * "no bank on both sides"** — measured: 0 of 5 on a real trace at z16, against 2 of 5
   * at z17 on the same trace and the same code.
   *
   * The reader is not looking at what the person is looking at. It is looking at the ink,
   * and the ink was engraved for one scale; there is no version of this where reading a
   * downsampled copy is better. Zoom is a property of the view and irrelevant here.
   */
  function traceZoom(source) {
    return Number(source?.zooms?.[1]) || 18;
  }

  /**
   * The sheet under a SEGMENT, not under a point.
   *
   * The first version centred the patch on the new click with a fixed 140 px radius — about
   * 103 m at z17 — so the moment two clicks were further apart than that, the PREVIOUS
   * vertex fell outside the patch, the path search rejected it as out of bounds, and the
   * segment silently fell back to a straight line. Silently is the word that matters: the
   * livewire worked perfectly when handed a patch that contained both ends, so the bug
   * looked like the algorithm failing when it was the window being too small to see the
   * question.
   *
   * So the patch is centred on the MIDPOINT and sized to hold both ends, the corridor
   * around them, and a margin. A segment too long for a sensible patch is refused by
   * `snapSegment` with a reason, which is the honest answer to a click 400 m from the last.
   */
  async function patchFor(from, to) {
    const source = backdrop();
    if (!source?.tiles || !source.traceable) return null;
    const zoom = traceZoom(source);
    const mid = [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2];
    const mPerPx = metresPerPixel(mid[1], zoom);
    const spanPx = Math.hypot(
      (to[0] - from[0]) * Math.cos(mid[1] * Math.PI / 180) * 111320 / mPerPx,
      (to[1] - from[1]) * 110540 / mPerPx);
    /* half the span, plus the corridor, plus a margin for the transects and the search */
    const radiusPx = Math.ceil(spanPx / 2 + (LIVEWIRE_DEFAULTS.corridorM / mPerPx) + 60);
    const key = `${source.id}|${zoom}|${Math.round(mid[0] * 4000)}|${Math.round(mid[1] * 4000)}|${radiusPx}`;
    if (state.patchKey === key && state.patch) return state.patch;
    const tile = tileSource?.() ?? null;
    state.patch = await loadPatch({
      ...(tile ? { tile } : { template: source.tiles }),
      zoom, lon: mid[0], lat: mid[1], radiusPx,
    });
    state.patchKey = state.patch ? key : null;
    return state.patch;
  }

  /* ── placing a vertex ──────────────────────────────────────────────────────────── */

  /**
   * Place a vertex, choosing the assist from what the surveyor drew.
   *
   * THE TWO ASSISTS ARE FOR DIFFERENT REACHES AND THE SAME TEST CHOOSES BETWEEN THEM.
   * Where a channel is drawn as two banks there is a middle to find, and following ink
   * would ride whichever bank is nearer. Where it is a single stroke there is no middle,
   * and following the ink IS the channel. `centreOnTransect` already distinguishes those
   * from the pixels — it refuses with *that point is on ink* on a single-stroke reach — so
   * its answer selects the operation. That is Stephen's correction made mechanical: the
   * choice is a property of the reach in front of the contributor, not of the loaded sheet.
   */
  async function place(lngLat, handle) {
    const to = [lngLat.lng, lngLat.lat];
    if (!state.coordinates.length) { push(to, 'clicked', null, null, handle); return; }
    const prev = state.coordinates[state.coordinates.length - 1];

    state.busy = true; redraw();
    try {
      const patch = await patchFor(prev, to);
      if (!patch) {
        push(to, 'clicked', { moved: false, why: 'no readable sheet here' }, null, handle);
        return;
      }
      const mPerPx = metresPerPixel(to[1], patch.zoom);

      let centre = null;
      if (state.centring) {
        const p = patchPixel(patch, to[0], to[1]);
        const q = patchPixel(patch, prev[0], prev[1]);
        centre = centreOnTransect(patch, p.x, p.y, q.x, q.y, { mPerPx });
        /* The handle travels with the vertex when centring moves it. The contributor
           stated a DIRECTION at a place; shifting the anchor a metre to the middle of the
           channel does not change which way they said the water goes. */
        if (centre.code === 'moved') { push([...toLonLatOf(patch, centre)], 'centred', centre, null, handle); return; }
        if (centre.code === 'central') { push(to, 'clicked', centre, null, handle); return; }
      }

      /**
       * FOLLOWING THE INK IS THE ANSWER FOR A SINGLE-STROKE REACH, NOT FOR EVERY REACH
       * CENTRING DECLINED.
       *
       * An earlier version fell through to the livewire on any refusal, and the comment
       * here claimed that a refusal meant a single stroke. It does not. `no-banks` means
       * open ground and `width-disagrees` means a channel WAS found and its two sides did
       * not stay parallel — and on a two-bank reach the livewire follows whichever bank is
       * cheaper, which is precisely the half-width offset this whole design exists to
       * avoid. Falling through there would have used the wrong assist at exactly the place
       * the right one had just failed.
       *
       * So the ink is followed when centring is OFF — the contributor's own choice — or
       * when centring reports `on-ink`, which is the pixels saying the channel here is one
       * stroke. Any other refusal means neither assist fits, and a straight line between
       * two clicks is the honest answer.
       */
      const inkIsTheChannel = !state.centring || centre?.code === 'on-ink';
      if (state.snapping && inkIsTheChannel) {
        const snap = snapSegment(patch, prev, to);
        state.lastSnap = snap;
        if (snap.snapped && snap.coordinates.length > 2) {
          const body = snap.coordinates.slice(1);
          body.forEach((c, i) => {
            /* The interior of a snapped run is machine-placed; the vertex the person
               actually clicked is the last one, and it is the one their handle belongs to. */
            const last = i === body.length - 1;
            state.coordinates.push(c);
            state.origin.push(last ? 'snapped' : 'snapped');
            state.handles.push(last ? (handle || null) : null);
          });
          if (state.origin.length) state.origin[state.origin.length - 1] = 'clicked';
          state.lastCentre = centre;
          state.candidate = [];
          redraw();
          return;
        }
      }
      push(to, 'clicked', centre, state.lastSnap, handle);
    } finally {
      state.busy = false;
      redraw();
    }
  }

  function toLonLatOf(patch, r) {
    const ll = patchLonLat(patch, r.x, r.y);
    return [ll.lon, ll.lat];
  }

  function push(coord, origin, centreResult, snapResult, handle) {
    state.coordinates.push(coord);
    state.origin.push(origin);
    state.handles.push(handle || null);
    state.lastCentre = centreResult;
    if (snapResult !== undefined) state.lastSnap = snapResult;
    state.candidate = [];
    redraw();
  }

  /* ── interaction ───────────────────────────────────────────────────────────────── */

  /* The candidate segment, previewed as the cursor moves.
   *
   * THROTTLED, AND SYNCHRONOUS-OR-NOTHING. The livewire is a Dijkstra over a corridor and
   * runs on mouse-move; at 55 ms it is comfortable and at every event it is not. And it
   * only previews from a patch ALREADY IN HAND — a preview that awaited a tile fetch would
   * make the line lag the cursor by a network round trip, which reads as the tool being
   * broken rather than busy. Until the patch arrives the preview is the straight line,
   * which is also exactly what will be committed if the sheet turns out to be unreadable. */
  function onMouseMove(e) {
    if (drag) {
      const dx = e.point.x - drag.from.x, dy = e.point.y - drag.from.y;
      if (Math.hypot(dx, dy) > DRAG_PX) { drag.dragged = true; drag.to = e.lngLat; paintHandles(); }
      return;
    }
    if (!state.active || !state.coordinates.length) return;
    const from = state.coordinates[state.coordinates.length - 1];
    const to = [e.lngLat.lng, e.lngLat.lat];
    state.candidate = [from, to];

    if (state.snapping && state.patch && !state.busy) {
      const now = Date.now();
      if (now - state.snapAt >= 55) {
        state.snapAt = now;
        const snap = snapSegment(state.patch, from, to);
        if (snap.snapped) state.candidate = snap.coordinates;
      }
    }
    redraw();
  }
  /* ── the pen gesture ───────────────────────────────────────────────────────────
   *
   * Press to place an anchor, drag to state which way the channel leaves it. Measured
   * before it was built (PLAN.md): a stated tangent beats the one Catmull-Rom guesses by
   * 24-47% on real reaches, where the guess itself was worth about 2%. What a handle
   * supplies is INFORMATION — the derivative at the anchor — which is why it works where
   * more smoothing did not.
   *
   * AND IT IS NOT A PRECISION INSTRUMENT, which is the finding that makes it usable by
   * volunteers: with the handle angle randomised by 45 degrees and its length by 40%, it
   * is still about a fifth better than straight segments. Nobody needs to be taught to
   * drag accurately, and the interface must not imply they do.
   */
  let drag = null;

  function onDown(e) {
    if (!state.active || !state.splining) return;
    drag = { at: e.lngLat, from: e.point, to: null, dragged: false };
    /* The map must not pan out from under a gesture that starts as a press. */
    if (e.originalEvent?.button === 0) e.preventDefault?.();
  }

  function onUp(e) {
    if (!drag) return;
    const d = drag; drag = null;
    paintHandles();
    if (!state.active) return;
    place(d.at, d.dragged && d.to ? [d.to.lng, d.to.lat] : null);
  }

  function onClick(e) {
    /* With the pen active the anchor is committed on mouseup, so letting `click` through
       would place every vertex twice. */
    if (state.active && !state.splining) place(e.lngLat, null);
  }
  function onKey(e) {
    if (!state.active) return;
    if (e.key === 'Escape') cancel();
    else if (e.key === 'Enter') onChange?.({ ...summary(), finished: true });
    else if (e.key === 'Backspace') { e.preventDefault(); undo(); }
  }

  /* One Backspace undoes ONE CLICK, not one algorithmically-placed pixel. A snapped run can
     be dozens of vertices and none of them was a decision. */
  function undo() {
    if (!state.coordinates.length) return;
    state.coordinates.pop();
    state.origin.pop();
    state.handles.pop();
    while (state.origin.length && state.origin[state.origin.length - 1] === 'snapped') {
      state.coordinates.pop();
      state.origin.pop();
      state.handles.pop();
    }
    state.candidate = [];
    state.lastCentre = null; state.lastSnap = null;
    redraw();
  }

  function cancel() {
    state.coordinates = []; state.origin = []; state.handles = [];
    state.candidate = []; state.lastCentre = null;
    drag = null;
    redraw();
  }

  /**
   * THE GESTURE COLLIDES WITH PANNING, and something has to give.
   *
   * A left-drag on a map means pan, and with the pen active it has to mean "state the
   * tangent" — the two cannot both own the same button. But a contributor tracing a long
   * channel MUST be able to move the map, so simply disabling the pan would trade one
   * unusable tool for another.
   *
   * Space held down restores panning, which is what Photoshop does — and Photoshop is
   * where this gesture comes from, so the hand that knows the pen already knows the
   * escape. It is also the only spare key that is not already a browser shortcut.
   *
   * Panning is disabled ONLY while the pen is active. With the curve mode off, drag is
   * pan exactly as before, and none of this is reachable.
   */
  function penHasTheMouse() { return state.active && state.splining; }

  function applyDragPan() {
    if (penHasTheMouse() && !spaceDown) map.dragPan.disable();
    else map.dragPan.enable();
    map.getCanvas().style.cursor =
      !state.active ? '' : (spaceDown ? 'grab' : 'crosshair');
  }

  let spaceDown = false;
  function onSpace(e) {
    if (e.code !== 'Space' || !state.active) return;
    const want = e.type === 'keydown';
    if (want === spaceDown) return;
    /* Space scrolls the page by default, which would move the map out from under the
       cursor at the exact moment somebody reached for it. */
    e.preventDefault();
    spaceDown = want;
    applyDragPan();
  }

  function start() {
    ensureLayers();
    state.active = true;
    map.on('mousemove', onMouseMove);
    map.on('mousedown', onDown);
    map.on('mouseup', onUp);
    map.on('click', onClick);
    window.addEventListener('keydown', onKey);
    window.addEventListener('keydown', onSpace);
    window.addEventListener('keyup', onSpace);
    applyDragPan();
    redraw();
  }

  function stop() {
    state.active = false;
    drag = null; spaceDown = false;
    map.off('mousemove', onMouseMove);
    map.off('mousedown', onDown);
    map.off('mouseup', onUp);
    map.off('click', onClick);
    window.removeEventListener('keydown', onKey);
    window.removeEventListener('keydown', onSpace);
    window.removeEventListener('keyup', onSpace);
    map.dragPan.enable();
    map.getCanvas().style.cursor = '';
    state.candidate = [];
    redraw();
  }

  /* Changing a mode must not disturb what is already drawn: the vertices placed so far keep
     their own provenance, and only the segment now under the cursor changes shape. */
  function setSnapping(on) {
    state.snapping = Boolean(on);
    state.candidate = [];
    redraw();
    onChange?.(summary());
  }

  function setSplining(on) {
    state.splining = Boolean(on);
    drag = null;
    /* Turning the pen off mid-trace has to give the mouse back to the map immediately,
       or the contributor is left unable to pan with no visible reason why. */
    applyDragPan();
    redraw();
  }

  function setCentring(on) {
    state.centring = Boolean(on);
    state.patch = null; state.patchKey = null;
    onChange?.(summary());
  }

  /* A style change wipes every source and layer on the map, so a backdrop switch destroys
     the trace layers while leaving `state` intact. The caller calls this after switching
     and the course in progress reappears — rather than the contributor watching their work
     vanish because they changed sheet. */
  function refresh() { if (ensureLayers()) redraw(); else retryLater(); }

  return {
    start, stop, undo, cancel, setCentring, setSnapping, setSplining, refresh,
    get active() { return state.active; },
    get centring() { return state.centring; },
    get snapping() { return state.snapping; },
    get splining() { return state.splining; },
    result: () => {
      const c = curve();
      return {
      /* THE CURVE IS WHAT IS RECORDED, and the clicks are recorded beside it.
         Storing control points alone would be smaller and exactly reproducible, and is
         wrong here: a consumer reading our GeoJSON without our spline would get a visibly
         different river, and D-035 settled that a published geometry has to be readable
         without our code. So the densified line is the geometry, and the clicks travel
         with it as the record of what a person actually did — which is also what a later
         re-tracing at a different tolerance would need. */
      coordinates: c.coords.slice(),
      vertexOrigin: c.origins.slice(),
      splining: state.splining,
      controlPoints: state.splining ? state.coordinates.slice() : null,
      controlOrigin: state.splining ? state.origin.slice() : null,
      /* The tolerance ASKED FOR and the deviation MEASURED, because they are different
         claims and only the second is evidence. */
      splineToleranceM: state.splining ? state.splineToleranceM : null,
      /* What the contributor dragged, kept as they did it. A tangent is derivable from
         this; the gesture is not derivable from a tangent. */
      handles: state.splining ? state.handles.slice() : null,
      handlesStated: state.handles.filter(Boolean).length,
      splineDeviationM: state.splining ? c.deviationM : null,
      /* WHAT THE ANNOTATION IS ENTITLED TO SAY. With snapping off no vertex came from a
         cost surface, so naming the sheet's colour mode would imply a machine read one when
         none did — `hand` is the truthful value, and it stays truthful where centring moved
         a vertex, because centring measures a width across the channel and does not follow
         ink along it. Only a run the livewire actually produced earns `monochrome` or
         `coloured`, and `vertexOrigin` says which vertices those were. */
      snapMode: state.origin.includes('snapped')
        ? (state.lastSnap?.mode ?? 'monochrome')
        : 'hand',
      };
    },
  };
}
