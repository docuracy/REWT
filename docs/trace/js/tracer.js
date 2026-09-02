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

const SRC = 'trace-src';
const SRC_CANDIDATE = 'trace-candidate-src';
const SRC_VERTEX = 'trace-vertex-src';

const emptyFC = () => ({ type: 'FeatureCollection', features: [] });

export function createTracer({ map, backdrop, tileSource, onChange, centring = false, snapping = false }) {
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
    lastSnap: null,
    snapAt: 0,
    coordinates: [],
    origin: [],
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
                each vs the paper    25.7 / 30.4 / 38.5

             All clear the tool's threshold of 15. The tightest pair is the one that
             matters least — both are machine-placed — while **a person's vertex against a
             machine's, which is the distinction the design rests on, is the widest.**
             Shape carries it too: clicked is solid and 5 px, the others hollow, snapped
             2.5 px. Colour alone would still be a single point of failure.

             THE DISPLAY OBLIGATION, not decoration. A vertex a person put down and one an
             algorithm moved are different evidence, and the person most likely to
             over-trust the second is the contributor, in the moment, with the line in
             front of them. Clicked reads solid; centred reads hollow. */
          'circle-color': ['case', ['==', ['get', 'origin'], 'clicked'], '#ff3b6b', '#ffffff'],
          'circle-stroke-color': ['case',
            ['==', ['get', 'origin'], 'centred'], '#00b4d8',
            ['==', ['get', 'origin'], 'snapped'], '#7a5cff',
            '#ff3b6b'],
          'circle-stroke-width': 2,
          /* A snapped vertex is one of dozens in a run and was nobody's decision; a clicked
             one is a judgement. Drawing them the same size would give the run a visual
             weight it has not earned. */
          'circle-radius': ['case', ['==', ['get', 'origin'], 'snapped'], 2.5, 5],
        } });
      return true;
    } catch {
      retryLater();
      return false;
    }
  }

  function redraw() {
    if (!map.getLayer('trace-vertices')) { onChange?.(summary()); return; }
    map.getSource(SRC).setData(state.coordinates.length >= 2
      ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.coordinates } }
      : emptyFC());
    map.getSource(SRC_CANDIDATE).setData(state.candidate.length >= 2
      ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.candidate } }
      : emptyFC());
    map.getSource(SRC_VERTEX).setData({
      type: 'FeatureCollection',
      features: state.coordinates.map((c, i) => ({
        type: 'Feature', properties: { origin: state.origin[i] || 'clicked' },
        geometry: { type: 'Point', coordinates: c },
      })),
    });
    onChange?.(summary());
  }

  function summary() {
    return {
      active: state.active,
      centring: state.centring,
      snapping: state.snapping,
      lastSnap: state.lastSnap,
      vertices: state.coordinates.length,
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
  async function place(lngLat) {
    const to = [lngLat.lng, lngLat.lat];
    if (!state.coordinates.length) { push(to, 'clicked', null, null); return; }
    const prev = state.coordinates[state.coordinates.length - 1];

    state.busy = true; redraw();
    try {
      const patch = await patchFor(prev, to);
      if (!patch) {
        push(to, 'clicked', { moved: false, why: 'no readable sheet here' }, null);
        return;
      }
      const mPerPx = metresPerPixel(to[1], patch.zoom);

      let centre = null;
      if (state.centring) {
        const p = patchPixel(patch, to[0], to[1]);
        const q = patchPixel(patch, prev[0], prev[1]);
        centre = centreOnTransect(patch, p.x, p.y, q.x, q.y, { mPerPx });
        if (centre.code === 'moved') { push([...toLonLatOf(patch, centre)], 'centred', centre, null); return; }
        if (centre.code === 'central') { push(to, 'clicked', centre, null); return; }
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
               actually clicked is the last one. */
            state.coordinates.push(c);
            state.origin.push(i < body.length - 1 ? 'snapped' : 'clicked');
          });
          state.lastCentre = centre;
          state.candidate = [];
          redraw();
          return;
        }
      }
      push(to, 'clicked', centre, state.lastSnap);
    } finally {
      state.busy = false;
      redraw();
    }
  }

  function toLonLatOf(patch, r) {
    const ll = patchLonLat(patch, r.x, r.y);
    return [ll.lon, ll.lat];
  }

  function push(coord, origin, centreResult, snapResult) {
    state.coordinates.push(coord);
    state.origin.push(origin);
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
  function onClick(e) { if (state.active) place(e.lngLat); }
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
    while (state.origin.length && state.origin[state.origin.length - 1] === 'snapped') {
      state.coordinates.pop();
      state.origin.pop();
    }
    state.candidate = [];
    state.lastCentre = null; state.lastSnap = null;
    redraw();
  }

  function cancel() {
    state.coordinates = []; state.origin = []; state.candidate = []; state.lastCentre = null;
    redraw();
  }

  function start() {
    ensureLayers();
    state.active = true;
    map.getCanvas().style.cursor = 'crosshair';
    map.on('mousemove', onMouseMove);
    map.on('click', onClick);
    window.addEventListener('keydown', onKey);
    redraw();
  }

  function stop() {
    state.active = false;
    map.getCanvas().style.cursor = '';
    map.off('mousemove', onMouseMove);
    map.off('click', onClick);
    window.removeEventListener('keydown', onKey);
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
    start, stop, undo, cancel, setCentring, setSnapping, refresh,
    get active() { return state.active; },
    get centring() { return state.centring; },
    get snapping() { return state.snapping; },
    result: () => ({
      coordinates: state.coordinates.slice(),
      vertexOrigin: state.origin.slice(),
      /* WHAT THE ANNOTATION IS ENTITLED TO SAY. With snapping off no vertex came from a
         cost surface, so naming the sheet's colour mode would imply a machine read one when
         none did — `hand` is the truthful value, and it stays truthful where centring moved
         a vertex, because centring measures a width across the channel and does not follow
         ink along it. Only a run the livewire actually produced earns `monochrome` or
         `coloured`, and `vertexOrigin` says which vertices those were. */
      snapMode: state.origin.includes('snapped')
        ? (state.lastSnap?.mode ?? 'monochrome')
        : 'hand',
    }),
  };
}
