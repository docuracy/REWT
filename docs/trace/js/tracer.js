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

const SRC = 'trace-src';
const SRC_CANDIDATE = 'trace-candidate-src';
const SRC_VERTEX = 'trace-vertex-src';

const emptyFC = () => ({ type: 'FeatureCollection', features: [] });

export function createTracer({ map, backdrop, onChange, centring = false }) {
  const state = {
    active: false,
    centring,
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
          'circle-radius': 5,
          /* THE DISPLAY OBLIGATION, not decoration. A vertex a person put down and one an
             algorithm moved are different evidence, and the person most likely to
             over-trust the second is the contributor, in the moment, with the line in
             front of them. Clicked reads solid; centred reads hollow. */
          'circle-color': ['case', ['==', ['get', 'origin'], 'clicked'], '#ff3b6b', '#ffffff'],
          'circle-stroke-color': ['case', ['==', ['get', 'origin'], 'centred'], '#00b4d8', '#ff3b6b'],
          'circle-stroke-width': 2,
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
      vertices: state.coordinates.length,
      coordinates: state.coordinates.slice(),
      origin: state.origin.slice(),
      lastCentre: state.lastCentre,
      busy: state.busy,
    };
  }

  /* ── the sheet under the cursor ────────────────────────────────────────────────── */

  /* Trace at the sheet's own best resolution rather than the screen's: the map may be at
     zoom 16.4, but the ink was drawn for a particular scale and a channel is only two
     banks at the layer's own maximum. */
  function traceZoom(source) {
    const max = Number(source?.zooms?.[1]) || 18;
    return Math.min(max, Math.max(14, Math.round(map.getZoom())));
  }

  async function patchFor(lon, lat) {
    const source = backdrop();
    if (!source?.tiles || !source.traceable) return null;
    const zoom = traceZoom(source);
    const key = `${source.id}|${zoom}|${Math.round(lon * 2000)}|${Math.round(lat * 2000)}`;
    if (state.patchKey === key && state.patch) return state.patch;
    state.patch = await loadPatch({ template: source.tiles, zoom, lon, lat, radiusPx: 140 });
    state.patchKey = state.patch ? key : null;
    return state.patch;
  }

  /* ── placing a vertex ──────────────────────────────────────────────────────────── */

  async function place(lngLat) {
    const to = [lngLat.lng, lngLat.lat];
    if (!state.coordinates.length || !state.centring) {
      push(to, 'clicked', null);
      return;
    }
    state.busy = true; redraw();
    try {
      const patch = await patchFor(to[0], to[1]);
      if (!patch) { push(to, 'clicked', { moved: false, why: 'no readable sheet here' }); return; }
      const prev = state.coordinates[state.coordinates.length - 1];
      const p = patchPixel(patch, to[0], to[1]);
      const q = patchPixel(patch, prev[0], prev[1]);
      const r = centreOnTransect(patch, p.x, p.y, q.x, q.y,
        { mPerPx: metresPerPixel(to[1], patch.zoom) });
      if (r.moved) {
        const ll = patchLonLat(patch, r.x, r.y);
        push([ll.lon, ll.lat], 'centred', r);
      } else {
        /* Refusing is the common case and is not a failure. The vertex goes exactly where
           it was put, and the reason is shown — never a silent no-op, which would read as
           the mode being broken. */
        push(to, 'clicked', r);
      }
    } finally {
      state.busy = false;
      redraw();
    }
  }

  function push(coord, origin, centreResult) {
    state.coordinates.push(coord);
    state.origin.push(origin);
    state.lastCentre = centreResult;
    state.candidate = [];
    redraw();
  }

  /* ── interaction ───────────────────────────────────────────────────────────────── */

  function onMouseMove(e) {
    if (!state.active || !state.coordinates.length) return;
    state.candidate = [state.coordinates[state.coordinates.length - 1], [e.lngLat.lng, e.lngLat.lat]];
    redraw();
  }
  function onClick(e) { if (state.active) place(e.lngLat); }
  function onKey(e) {
    if (!state.active) return;
    if (e.key === 'Escape') cancel();
    else if (e.key === 'Enter') onChange?.({ ...summary(), finished: true });
    else if (e.key === 'Backspace') { e.preventDefault(); undo(); }
  }

  function undo() {
    if (!state.coordinates.length) return;
    state.coordinates.pop();
    state.origin.pop();
    state.candidate = [];
    state.lastCentre = null;
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
    start, stop, undo, cancel, setCentring, refresh,
    get active() { return state.active; },
    get centring() { return state.centring; },
    result: () => ({
      coordinates: state.coordinates.slice(),
      vertexOrigin: state.origin.slice(),
      /* WHAT THE ANNOTATION IS ENTITLED TO SAY. Phase 2 has no cost surface, so no vertex
         came from one and naming a colour mode would imply a machine read the sheet when
         none did. `hand` is truthful even where centring moved a vertex: centring measures
         a width, it does not follow ink along a course. */
      snapMode: 'hand',
    }),
  };
}
