/**
 * A georeferenced tracer for MapLibre.
 *
 * Click to place a vertex; the segment from the last vertex to the cursor is snapped
 * to whatever the sheet underneath actually draws, and committed on the next click.
 * Enter finishes, Backspace undoes, Escape abandons.
 *
 * DESIGN CONSTRAINT: this module knows nothing about rivers. It is given a map, a way
 * to find the current raster backdrop, and a callback; it hands back coordinates and
 * per-vertex provenance. Everything about what a trace MEANS — which nodes it joins,
 * what it is called, how it is licensed — belongs to the caller, and the annotation
 * profile in anno.js is a separate module for the same reason. The intent is that
 * this is liftable into any project that needs to trace features off a historic map.
 *
 * WHY NOT TERRA DRAW OR MAPBOX-GL-DRAW. Both are good, and if the requirement were
 * plain drawing either would be the answer. The requirement here is snapping to
 * printed ink, which means a custom mode in either library — and a custom mode is
 * where their APIs are least stable and most bundler-dependent. This project has no
 * build step (CLAUDE.md), so a dependency has to work as a bare ES module from a CDN
 * with its own custom-mode API intact. The drawing part that would be inherited is
 * about eighty lines; the snapping part, which is the whole point, would have to be
 * written either way.
 */

import { loadSheet, sheetPixel, sheetLonLat, sheetContains, classifySheet, buildCost, livewire, simplify } from './raster.js';

const SRC = 'trace-src';
const SRC_CANDIDATE = 'trace-candidate-src';
const SRC_VERTEX = 'trace-vertex-src';
const SRC_DONE = 'trace-done-src';

/* Beyond this the corridor search covers a large area for a segment the tracer
   cannot see the ends of at once, and the honest answer is a straight line and a
   suggestion to click more often. */
const MAX_SNAP_PX = 520;
const SNAP_THROTTLE_MS = 55;

function emptyFC() {
  return { type: 'FeatureCollection', features: [] };
}

export function createTracer({ map, backdrop, onChange, corridorPx = 36,
                               snap: snapEnabled = true }) {
  const state = {
    active: false,
    /* SNAPPING IS A SEPARATE QUESTION FROM TRACING, and conflating them made the
       tool unusable where it is most needed. Arming the map for clicks and
       following the printed ink between them are different decisions: the ink runs
       out, forks, or is crossed by a road, and there the only honest line is the
       one a person draws. With this off a vertex lands exactly where it was put and
       the segment to it is straight — and the annotation still records every
       vertex as `clicked`, which is what it is. */
    snapping: snapEnabled !== false,
    /* Committed positions, and where each came from. A vertex the tracer placed by
       algorithm is a different kind of evidence from one a person clicked, and the
       annotation says which is which — so the distinction is carried from the moment
       it arises rather than reconstructed later. */
    coordinates: [],
    origin: [],
    candidate: [],
    completed: null,
    sheet: null,
    sheetInfo: null,
    loading: false,
    lastSnap: 0,
  };

  /* Adding a source before the style is ready throws "Style is not done loading", and
     the caller may well render an empty completed-course list during wiring — which is
     before anything has loaded.
     TRY AND RETRY rather than test `isStyleLoaded()` first. That flag stays false for
     as long as ANY source is still resolving, so a single unrelated source that never
     resolves — a tile archive missing from a local preview, say — would disable the
     tracer permanently on a map that is otherwise perfectly usable. Attempting the
     work and retrying on the next style event is decided by whether it succeeded,
     which is the thing actually being asked. */
  let layersPending = false;

  function retryLayersLater() {
    if (layersPending) return;
    layersPending = true;
    map.once('styledata', () => {
      layersPending = false;
      if (ensureLayers()) {
        redraw();
        if (state.completed) map.getSource(SRC_DONE).setData(state.completed);
      } else {
        retryLayersLater();
      }
    });
  }

  function addSourceOnce(id) {
    if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: emptyFC() });
  }

  function ensureLayers() {
    // The last layer added is the completion marker: a half-built set must not pass.
    if (map.getLayer('trace-vertices')) return true;
    try {
      return buildLayers();
    } catch {
      retryLayersLater();
      return false;
    }
  }

  function buildLayers() {
    addSourceOnce(SRC);
    addSourceOnce(SRC_CANDIDATE);
    addSourceOnce(SRC_VERTEX);
    addSourceOnce(SRC_DONE);
    /* Finished courses stay on the map. A trace that vanishes when you finish it
       gives you no way to see what you have already covered, which on a reach with
       several channels is exactly when you need to. Added FIRST so it draws beneath
       the course in progress. */
    if (!map.getLayer('trace-done')) map.addLayer({
      id: 'trace-done',
      type: 'line',
      source: SRC_DONE,
      paint: {
        'line-color': '#3ddc97', 'line-width': 3, 'line-opacity': 0.9,
      },
    });
    if (!map.getLayer('trace-done-labels')) map.addLayer({
      id: 'trace-done-labels',
      type: 'symbol',
      source: SRC_DONE,
      layout: {
        'symbol-placement': 'line',
        'text-field': ['coalesce', ['get', 'name'], ''],
        'text-size': 11,
        'text-offset': [0, -0.8],
      },
      paint: {
        'text-color': '#3ddc97',
        'text-halo-color': 'rgba(0,0,0,0.75)',
        'text-halo-width': 1.5,
      },
    });
    if (!map.getLayer('trace-line')) map.addLayer({
      id: 'trace-line',
      type: 'line',
      source: SRC,
      paint: {
        'line-color': '#ff3b6b', 'line-width': 3, 'line-opacity': 0.95,
      },
    });
    if (!map.getLayer('trace-candidate')) map.addLayer({
      id: 'trace-candidate',
      type: 'line',
      source: SRC_CANDIDATE,
      /* Dashed, because it is not committed. The same visual grammar the rest of the
         map uses for "conjectural" (PLAN §13.2). */
      paint: {
        'line-color': '#ff3b6b', 'line-width': 2, 'line-dasharray': [2, 2],
        'line-opacity': 0.8,
      },
    });
    if (!map.getLayer('trace-vertices')) map.addLayer({
      id: 'trace-vertices',
      type: 'circle',
      source: SRC_VERTEX,
      paint: {
        'circle-radius': 4,
        /* Clicked vertices read solid; snapped ones hollow. The provenance the
           annotation records is visible while the trace is being made, not only
           afterwards in the file. */
        'circle-color': ['case', ['==', ['get', 'origin'], 'clicked'], '#ff3b6b', '#ffffff'],
        'circle-stroke-color': '#ff3b6b',
        'circle-stroke-width': 1.5,
      },
    });
    return true;
  }

  function redraw() {
    if (!map.getLayer('trace-vertices')) { if (onChange) onChange(summary()); return; }
    map.getSource(SRC).setData(state.coordinates.length >= 2
      ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.coordinates } }
      : emptyFC());
    map.getSource(SRC_CANDIDATE).setData(state.candidate.length >= 2
      ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.candidate } }
      : emptyFC());
    map.getSource(SRC_VERTEX).setData({
      type: 'FeatureCollection',
      features: state.coordinates.map((c, i) => ({
        type: 'Feature',
        properties: { origin: state.origin[i] || 'clicked' },
        geometry: { type: 'Point', coordinates: c },
      })),
    });
    if (onChange) onChange(summary());
  }

  function summary() {
    return {
      active: state.active,
      snapping: state.snapping,
      vertices: state.coordinates.length,
      snapMode: state.sheetInfo ? (state.sheetInfo.coloured ? 'coloured' : 'monochrome') : null,
      sheetReady: Boolean(state.sheet),
      loading: state.loading,
      coordinates: state.coordinates.slice(),
      origin: state.origin.slice(),
    };
  }

  /* ── The sheet under the map ─────────────────────────────────────────────── */

  async function refreshSheet(force = false) {
    const source = backdrop();
    if (!source || !source.tiles) {
      state.sheet = null; state.sheetInfo = null;
      redraw();
      return;
    }
    const c = map.getCenter();
    if (!force && sheetContains(state.sheet, c.lng, c.lat, 96)
        && state.sheet.zoom === snapZoom(source)) return;
    if (state.loading) return;
    state.loading = true;
    redraw();
    try {
      const b = map.getBounds();
      const sheet = await loadSheet({
        template: source.tiles,
        zoom: snapZoom(source),
        bounds: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
      });
      const info = sheet ? classifySheet(sheet.image) : null;
      if (sheet && info.usable) {
        state.sheetInfo = info;
        sheet.costed = buildCost(sheet.image, info.coloured);
        state.sheet = sheet;
      } else if (sheet) {
        /* Blank paper: outside coverage, or the tiles were refused. Snapping to a
           uniform field would produce a confident-looking line and a false claim
           about how it was made. */
        state.sheet = null;
        state.sheetInfo = null;
      } else {
        /* Too much ground for one mosaic: zoomed too far out to trace usefully. */
        state.sheet = null;
        state.sheetInfo = null;
      }
    } catch (err) {
      console.warn('[tracer] sheet unavailable', err);
      state.sheet = null;
      state.sheetInfo = null;
    } finally {
      state.loading = false;
      redraw();
    }
  }

  /* Trace at the sheet's own best resolution rather than the screen's: the map may
     be at zoom 14.3, but the ink was drawn for a particular scale and the cost
     surface is sharpest at the layer's native maximum. */
  function snapZoom(source) {
    const max = Number(source.max_zoom) || 16;
    return Math.min(max, Math.max(13, Math.round(map.getZoom())));
  }

  /* ── Snapping ────────────────────────────────────────────────────────────── */

  function snap(fromLonLat, toLonLat) {
    const sheet = state.sheet;
    if (!sheet || !sheet.costed) return null;
    if (!sheetContains(sheet, fromLonLat[0], fromLonLat[1], 2)
        || !sheetContains(sheet, toLonLat[0], toLonLat[1], 2)) return null;
    const a = sheetPixel(sheet, fromLonLat[0], fromLonLat[1]);
    const b = sheetPixel(sheet, toLonLat[0], toLonLat[1]);
    if (Math.hypot(b.x - a.x, b.y - a.y) > MAX_SNAP_PX) return null;
    const path = livewire(sheet.costed, a, b, corridorPx);
    if (!path || path.length < 2) return null;
    return simplify(path).map(([x, y]) => {
      const ll = sheetLonLat(sheet, x, y);
      return [ll.lon, ll.lat];
    });
  }

  function candidateFor(lngLat) {
    const to = [lngLat.lng, lngLat.lat];
    if (!state.coordinates.length) return { coords: [to], snapped: false };
    const from = state.coordinates[state.coordinates.length - 1];
    const snapped = state.snapping ? snap(from, to) : null;
    return snapped ? { coords: snapped, snapped: true } : { coords: [from, to], snapped: false };
  }

  /* ── Interaction ─────────────────────────────────────────────────────────── */

  function onMouseMove(e) {
    if (!state.active) return;
    const now = Date.now();
    if (now - state.lastSnap < SNAP_THROTTLE_MS) return;
    state.lastSnap = now;
    state.candidate = candidateFor(e.lngLat).coords;
    redraw();
  }

  function onClick(e) {
    if (!state.active) return;
    const { coords, snapped } = candidateFor(e.lngLat);
    if (!state.coordinates.length) {
      state.coordinates.push(coords[0]);
      state.origin.push('clicked');
    } else {
      /* The interior of a snapped run is machine-placed; the vertex the person
         actually clicked is the last one. */
      const body = coords.slice(1);
      body.forEach((c, i) => {
        state.coordinates.push(c);
        state.origin.push(snapped && i < body.length - 1 ? 'snapped' : 'clicked');
      });
    }
    state.candidate = [];
    redraw();
  }

  function onKey(e) {
    if (!state.active) return;
    if (e.key === 'Escape') { cancel(); }
    else if (e.key === 'Enter') { if (onChange) onChange({ ...summary(), finished: true }); }
    else if (e.key === 'Backspace') { e.preventDefault(); undo(); }
  }

  function undo() {
    /* Remove back to and including the previous clicked vertex, so one Backspace
       undoes one click rather than one algorithmically-placed pixel. */
    if (!state.coordinates.length) return;
    state.coordinates.pop();
    state.origin.pop();
    while (state.origin.length && state.origin[state.origin.length - 1] === 'snapped') {
      state.coordinates.pop();
      state.origin.pop();
    }
    state.candidate = [];
    redraw();
  }

  function cancel() {
    state.coordinates = [];
    state.origin = [];
    state.candidate = [];
    redraw();
  }

  function start(seed) {
    ensureLayers();
    state.active = true;
    map.getCanvas().style.cursor = 'crosshair';
    if (seed) {
      state.coordinates = [seed.slice()];
      state.origin = ['clicked'];
    }
    map.on('mousemove', onMouseMove);
    map.on('click', onClick);
    map.on('moveend', onMoveEnd);
    window.addEventListener('keydown', onKey);
    refreshSheet(true);
    redraw();
  }

  function stop() {
    state.active = false;
    map.getCanvas().style.cursor = '';
    map.off('mousemove', onMouseMove);
    map.off('click', onClick);
    map.off('moveend', onMoveEnd);
    window.removeEventListener('keydown', onKey);
    state.candidate = [];
    redraw();
  }

  function onMoveEnd() { if (state.active) refreshSheet(false); }

  /* Changing the mode must not disturb what is already drawn: the vertices placed
     so far keep their own provenance, and only the segment now under the cursor
     changes shape. */
  function setSnapping(on) {
    state.snapping = Boolean(on);
    state.candidate = [];
    redraw();
    if (state.snapping && state.active) refreshSheet(false);
    if (onChange) onChange(summary());
  }

  /* Finished courses, owned by the caller — the tracer only draws them. Kept here
     rather than in the caller so the layer and its styling travel with the module. */
  function setCompleted(featureCollection) {
    state.completed = featureCollection || emptyFC();
    if (ensureLayers()) map.getSource(SRC_DONE).setData(state.completed);
  }

  return {
    start,
    stop,
    undo,
    cancel,
    refreshSheet,
    setCompleted,
    setSnapping,
    get active() { return state.active; },
    get snapping() { return state.snapping; },
    result: () => ({
      coordinates: state.coordinates.slice(),
      vertexOrigin: state.origin.slice(),
      /* WHAT THE ANNOTATION IS ENTITLED TO SAY. With snapping off no vertex came
         from the cost surface, so naming the sheet's colour mode would imply a
         machine read one when none did. `hand` is the truthful value, and
         `vertexOrigin` says the same thing per vertex. */
      snapMode: !state.snapping ? 'hand'
        : (state.sheetInfo ? (state.sheetInfo.coloured ? 'coloured' : 'monochrome') : null),
      zoom: state.sheet ? state.sheet.zoom : null,
    }),
  };
}
