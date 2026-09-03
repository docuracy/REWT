/* The network as currently assembled.
 *
 * WHAT THIS IS FOR. AGENTS.md: "Looking beats measuring... Aggregates have
 * repeatedly agreed that a broken thing was fixed", and "a national 97% hides a
 * basin at 40%, and the basin at 40% is the entire finding". Everything here exists
 * to put a defect on the ground where a person can see it, and every list in the
 * panel is sorted worst-first and flies the map to the place.
 *
 * TWO RULES IT KEEPS. The thinning in force is always stated, because a channel
 * missing from the picture must never read as "no river here". And four classes are
 * never thinned at any zoom — the unreached, the retired, the geometry this project
 * added, and the reversed — because those are the reason to be looking.
 */

const $ = (s) => document.querySelector(s);
const fmt = (n, d = 0) => (n == null || Number.isNaN(n) ? '—'
  : Number(n).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }));

/* A FIGURE THAT IS MISSING MUST NOT LOOK LIKE A FIGURE THAT IS ZERO OR UNKNOWN. The
   audit renamed `in_scope_km` to `total_in_scope_km` between builds and the headline
   quietly became "— km in scope, of which — km cannot reach the sea", which reads as
   "not measured" rather than "this tool is looking up the wrong key". Anything read out
   of the audit goes through here, so a rename is announced instead of absorbed. */
const missing = [];
function need(obj, ...names) {
  for (const n of names) if (obj && obj[n] !== undefined && obj[n] !== null) return obj[n];
  missing.push(names[0]);
  return null;
}
const pct = (x) => (x == null ? '—' : (x * 100).toFixed(2) + '%');
/* A SHARE IS NEVER ROUNDED UP TO 100%. The Tweed reads 99.84% and rounded to "100%",
   which is the one number on this page that must not be able to say "done" when
   5.3 km of it is stranded. Anything short of the whole shows a decimal and stops at
   99.9; only an exact 1 prints 100%. */
const share = (x) => {
  if (x == null) return '—';
  if (x >= 1) return '100%';
  return Math.min(99.9, x * 100).toFixed(1) + '%';
};
const esc = (s) => String(s ?? '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

/* TWO PALETTES, AND ONE RULE ABOUT WHEN THEY MAY MEET.
 *
 * The network is a SURFACE coloured by a theme; the overlays are MARKS drawn on it.
 * The first version gave three overlays the same hue as a form category — connectors
 * were canal-yellow, reversals lake-teal, retired tidal-violet — so the legend showed
 * one colour against two meanings and the reader had no way to tell which they were
 * looking at. That is the map asserting a relationship that does not exist.
 *
 * The rule: **an overlay shares a theme's colour only where it means the same thing,
 * and must differ everywhere else.** Three alignments are therefore deliberate and are
 * kept — connectors are the form theme's "added by this project"; the dead-end layer is
 * the network's "does not reach tidal water"; tidal termini are its tidal water. Every
 * other pairing is separated.
 *
 * Theme colours are a cool family, because every one of them is water the survey drew.
 * Overlay colours are warm or bright, because none of them is.
 */
const C = {
  // the network, coloured by a theme — all water, all cool
  reach: '#1b9ce6',        // reaches tidal water / inland river
  canal: '#6c7bd9',        // canal: man-made, so a colder blue than a river
  lake: '#2ec4b6',         // lake
  tidal: '#8f6fe8',        // tidal river
  outscope: '#7f8b9c',     // out of scope
  unreached: '#ff2d55',    // in scope and does NOT reach — the one alarm colour

  // marks drawn on top — none of these is survey water
  add: '#ffd21e',          // geometry this project added (also the theme's "added")
  rev: '#39e08b',          // routing reversed
  retiredc: '#ff5cf0',     // retired, superseded, kept
  seed: '#ffffff',         // seed nodes
  warn: '#ff9f1c',         // a caution: unadjudicated, uncorroborated, in doubt
};

const [summary, backdrops] = await Promise.all([
  fetch('/api/summary.json').then((r) => r.json()),
  fetch('/api/backdrops.json').then((r) => r.json()),
]);

/* ── Figures ──────────────────────────────────────────────────────────────── */

const c = summary.counts;
const R = summary.reachability || {};
// Both spellings accepted: the field was renamed, and a viewer that only works against
// the newest build is a viewer that cannot open last week's published output.
const inScopeKm = need(R, 'total_in_scope_km', 'in_scope_km');
const inScopeShare = need(R, 'in_scope_share');
/* THE HEADLINE SAID "REACHES THE SEA" OVER THE TIDAL FIGURE. The deployed viewer was
   corrected for this (735b017); this one was not, because until today it could not be
   run and so nobody read it. It printed 93.58% under "reaches the sea" — that is the
   share reaching TIDAL WATER — and "6,785 km cannot reach the sea" where the figure for
   that sentence is 3,894 km, overstating the work left by three quarters of it. The
   difference is 2,890 km of coastal drainage that discharges at a sea wall without ever
   touching a tidalRiver, and `readings_are_nested: false` is stated in the audit's own
   section, so the data was saying this about itself while the panel rounded the two
   together. The label decides which number belongs under it, and where the audit has no
   sea section the panel falls back to the tidal reading AND relabels itself, because a
   stale number under a confident label is the failure being fixed. */
const SEA = summary.reachability_tested_against_the_sea || {};
const haveSea = SEA.reaches_the_sea_share != null;
$('#f-share').textContent = pct(haveSea ? SEA.reaches_the_sea_share : inScopeShare);
$('#f-share-label').textContent = haveSea
  ? 'of in-scope length reaches the sea'
  : 'of in-scope length reaches tidal water — this build does not test the sea';
$('#f-defects').textContent = fmt(c.dead_ends_defect);
$('#f-detail').innerHTML = `
  ${fmt(inScopeKm)} km in scope, of which
  <b>${fmt(haveSea ? SEA.reaches_neither_km
        : (inScopeKm == null || inScopeShare == null ? null
           : inScopeKm * (1 - inScopeShare)))} km
  reaches neither tidal water nor the sea</b>.
  ${haveSea ? `<br><b>${fmt(SEA.reaches_sea_only_km)} km reaches the SEA ONLY</b> —
  coastal drainage with no tidal link, which the tidal reading alone counts as stranded;
  ${fmt(SEA.reaches_tidal_only_km)} km reaches tidal water the sea cannot take. The two
  readings are not nested.` : ''}
  ${fmt(summary.stranded.count)} components holding
  ${fmt(summary.stranded.km)} km reach it nowhere at all.<br>
  ${fmt(c.links)} links · ${fmt(c.nodes)} nodes · ${fmt(c.basins)} basins
  (${fmt(c.basins_in_scope)} in scope, ${fmt(c.no_outlet_in_scope)} of those with no
  outlet node) · ${fmt(c.corrections)} curated judgements ·
  ${fmt(c.retired)} retired · ${fmt(summary.direction_faults)} direction faults ·
  ${fmt(summary.cycles.count)} closed loops.`;
$('#built').innerHTML = `Built ${esc((summary.provenance.built_at || '').slice(0, 16).replace('T', ' '))},
  fingerprint <code>${esc(summary.provenance.config_fingerprint)}</code>.
  OS Open Rivers ${esc(summary.provenance.sources?.os_open_rivers?.issue || '?')}.`;
$('#attribution').innerHTML = summary.attribution;

const warnings = [...(summary.warnings || [])];
if (missing.length) {
  warnings.push(`This viewer could not find ${missing.map((m) => `<code>${esc(m)}</code>`)
    .join(', ')} in published/audit/audit.json, so the figures above are incomplete. `
    + 'The audit has most likely renamed a field — the dashes are this tool reading the '
    + 'wrong key, not a measurement that is missing.');
}
if (warnings.length) {
  $('#warn').hidden = false;
  $('#warn').innerHTML = warnings.join('<br>');
}

/* A published file that has changed since this page loaded is the exact way to end
   up reasoning about an older network than the audit beside it. Say so, loudly. */
async function checkFreshness() {
  const f = await fetch('/api/freshness.json').then((r) => r.json()).catch(() => null);
  if (!f || !f.stale) return;
  $('#stale').hidden = false;
  $('#stale').innerHTML = 'published/ has been rewritten since this map loaded — '
    + 'you are looking at an older network than the one on disk. '
    + '<button id="reload-now">Reload it</button>';
  $('#reload-now').onclick = async () => {
    $('#stale').textContent = 'reloading…';
    await fetch('/api/reload');
    location.reload();
  };
}
setInterval(checkFreshness, 30000);
checkFreshness();

/* ── Backdrops ────────────────────────────────────────────────────────────── */

const opts = backdrops.basemap.options;
const keys = backdrops.keys || {};
const thin = backdrops.basemap.thinning;
/* A backdrop whose key is absent is not offered at all. The alternative — offering
   it and drawing nothing, in silence, when the tile 403s — has cost the predecessor
   a day, and is the failure mode this check exists for. */
/* ── The view, in the URL ───────────────────────────────────────────────────
   Everything a reader would have to describe in words to send someone to the same
   picture: where, how close, which sheet under it, how strongly, coloured by what,
   and which overlays. `#z/lat/lon` leads because that is the convention every other
   slippy map uses and a person can edit it by hand.

   Written with replaceState and not pushState: panning a map is not navigation, and
   filling the back button with three hundred intermediate viewports makes the back
   button useless for leaving. */

function readHash() {
  const h = decodeURIComponent(location.hash.replace(/^#/, ''));
  if (!h) return {};
  const [view, ...rest] = h.split('&');
  const out = {};
  const m = view.match(/^(-?[\d.]+)\/(-?[\d.]+)\/(-?[\d.]+)$/);
  if (m) { out.zoom = +m[1]; out.lat = +m[2]; out.lon = +m[3]; }
  for (const kv of rest) {
    const i = kv.indexOf('=');
    if (i > 0) out[kv.slice(0, i)] = kv.slice(i + 1);
  }
  return out;
}
const HASH = readHash();

const usable = Object.entries(opts).filter(([, o]) => !o.requires_key || keys[o.requires_key]);
const sel = $('#backdrop');
/* Grouped, because there are now more historic layers than a flat list can be read as.
   The group is declared per option so the ordering in backdrops.json stays the ordering
   on screen — a select that reorders what the file says is a select nobody can predict. */
const GROUPS = [
  ['modern', 'Modern'],
  ['seamless', 'Historic — seamless, England and Wales'],
  ['composited', 'Historic — composited by this server'],
  ['collection', 'Historic — pick a sheet or county'],
  ['other', 'Other'],
];
for (const [key, label] of GROUPS) {
  const rows = usable.filter(([, o]) => (o.group || (o.historic ? 'seamless' : 'modern')) === key);
  if (!rows.length) continue;
  const g = document.createElement('optgroup');
  g.label = label;
  for (const [id, o] of rows) g.append(new Option(o.label, id));
  sel.append(g);
}
let backdropId = backdrops.basemap.default in Object.fromEntries(usable)
  ? backdrops.basemap.default : usable[0][0];
/* A backdrop named in a link that this reader cannot have — a keyed one, or one
   removed since — falls back rather than failing, because a shared link should still
   land you in the right place with the wrong sheet. */
if (HASH.b && usable.some(([id]) => id === HASH.b)) backdropId = HASH.b;
sel.value = backdropId;
/* A COLLECTION IS A LAYER THAT IS REALLY MANY LAYERS — the first-edition six-inch by
   county, the pre-Ordnance county surveys, the town plans. Each supplies a list of items
   with an id, a label and real bounds, and the picker swaps one into the tile URL.
   Counties keep their Historic Counties Standard three-letter code as the id, because
   the Standard is this project's county vocabulary and the NLS filename is not. */
const items = {};                  // collection url -> item list
let chosen = {};                   // collection url -> chosen item id
const picked = new Set();          // collections where the reader has chosen for themselves
const itemsFor = (o) => items[o.counties || o.collection] || [];
const itemRow = (o) => itemsFor(o).find((c) => (c.code || c.id) === chosen[o.counties || o.collection]);

const tilesFor = (o) => {
  if (!o.tiles) return null;
  let t = o.tiles;
  if (o.requires_key) t = t.replace('{key}', encodeURIComponent(keys[o.requires_key]));
  if (o.counties || o.collection) {
    const r = itemRow(o);
    t = t.replace('{county}', r?.slug ?? r?.id ?? '').replace('{item}', r?.id ?? '');
  }
  return [t];
};

/* A raster source's `bounds` is what makes 71 county mosaics usable: MapLibre asks for
   no tile outside them, so selecting a county costs nothing outside its own sheets and
   the rest of the map is honestly empty rather than 404-ing across the country. */
const sourceFor = (o) => {
  const src = { type: 'raster', tiles: tilesFor(o), tileSize: 256,
    maxzoom: o.max_zoom || 19, attribution: o.attribution };
  if (o.min_zoom) src.minzoom = o.min_zoom;
  /* A layer's own extent, observed from the tiles the Library serves. Setting it means
     MapLibre asks for nothing outside it — no 404 storm over the rest of the country,
     and the empty area is honestly empty rather than pending. */
  if (o.bounds) src.bounds = o.bounds;
  const row = (o.counties || o.collection) ? itemRow(o) : null;
  if (row && row.bounds) src.bounds = row.bounds;
  if (row && row.zooms) {
    src.maxzoom = Math.max(...row.zooms);
    src.minzoom = Math.min(...row.zooms);
  }
  return src;
};

/* ── Map ──────────────────────────────────────────────────────────────────── */

/* THE OPENING STYLE NEVER CARRIES A COLLECTION. A collection's tile URL holds an
   `{item}` placeholder that only `applyBackdrop` can fill, and it cannot run until the
   map has loaded — so putting one in the initial style produces `.../25_inch//{z}/...`,
   MapLibre rejects the style, `load` never fires, and NOTHING initialises: no network
   source, no restore, no error a reader would connect to the cause. A link naming a
   county sheet did exactly that. The map therefore opens on no backdrop whenever the
   chosen one is a collection, and applyBackdrop installs it a moment later. */
const b0raw = opts[backdropId];
const b0 = (b0raw && (b0raw.counties || b0raw.collection)) ? { tiles: null } : b0raw;
const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: b0.tiles ? { backdrop: { type: 'raster', tiles: tilesFor(b0), tileSize: 256,
      maxzoom: b0.max_zoom || 19, attribution: b0.attribution } } : {},
    layers: [
      { id: 'ground', type: 'background', paint: { 'background-color': '#0d1117' } },
      ...(b0.tiles ? [{ id: 'backdrop', type: 'raster', source: 'backdrop',
        paint: { 'raster-opacity': b0.opacity ?? 0.5 } }] : []),
    ],
  },
  center: [HASH.lon ?? -2.2, HASH.lat ?? 52.7],
  zoom: HASH.zoom ?? 5.7,
  maxZoom: 18,
  attributionControl: { customAttribution: summary.attribution },
});
/* A local instrument gets a console handle. `map.flyTo(...)` from the devtools is
   how you get to a grid reference somebody read out to you over a message. */
window.map = map;
window.rewt = { summary, backdrops };
map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
/* The scale goes UNDER THE ZOOM BUTTONS, not into the bottom-right corner. The legend
   is anchored there and grows upward as the theme and the visible overlays add rows, so
   the two were contending for the same ground and the scale — being a map control, and
   therefore above the legend — won, covering the bottom of the key. Two things that
   both grow into one corner will collide eventually; moving one is the fix, raising the
   other's offset only postpones it. */
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'top-right');

$('#backdrop-opacity').value = Math.round((b0.opacity ?? 0.5) * 100);
$('#historic-note').textContent = backdrops.basemap.historic_warning;

async function applyBackdrop() {
  const o = opts[backdropId];
  const src = o.counties || o.collection;
  if (src && !items[src]) {
    items[src] = await fetch(src).then((r) => r.json()).catch(() => []);
  }
  if (src) {
    /* PICK THE SHEET YOU ARE LOOKING AT. A collection is bounded to one item at a
       time, so choosing the first alphabetically means switching to it usually blanks
       the map and looks broken. If any item covers the current centre, that is the one
       meant; only fall back to the first when the view is outside every item. */
    const c = map.getCenter();
    const covers = (r) => r.bounds && c.lng >= r.bounds[0] && c.lng <= r.bounds[2]
      && c.lat >= r.bounds[1] && c.lat <= r.bounds[3];
    /* The SMALLEST item containing the centre, not the first. Extents are derived from
       a zoom-9 listing, so a bounding box is snapped to about 78 km and several counties
       genuinely contain any given point. The tightest box is the best guess available
       from coarse bounds, and it is right far more often than alphabetical order. */
    const area = (r) => (r.bounds[2] - r.bounds[0]) * (r.bounds[3] - r.bounds[1]);
    const here = itemsFor(o).filter(covers).sort((a, b) => area(a) - area(b))[0];
    /* ONLY GUESS UNTIL THE READER HAS CHOSEN. Re-guessing on every redraw overrode a
       manual selection the moment the map moved — you picked Somerset, the map redrew,
       and the smallest box containing the centre put you back in Wiltshire. */
    if (HASH.i && !picked.has(src)
        && itemsFor(o).some((r) => (r.code || r.id) === HASH.i)) {
      chosen[src] = HASH.i;                 // named in the link: not a guess
      picked.add(src);
    } else if (here && !picked.has(src)) chosen[src] = here.code || here.id;
    else if (!itemRow(o)) chosen[src] = itemsFor(o)[0] && (itemsFor(o)[0].code || itemsFor(o)[0].id);
    buildItemPicker(o);
  }
  if (map.getLayer('backdrop')) map.removeLayer('backdrop');
  if (map.getSource('backdrop')) map.removeSource('backdrop');
  if (o.tiles) {
    map.addSource('backdrop', sourceFor(o));
    map.addLayer({ id: 'backdrop', type: 'raster', source: 'backdrop',
      paint: { 'raster-opacity': o.opacity ?? 0.5 } }, map.getStyle().layers[1]?.id);
  }
  $('#backdrop-opacity').value = Math.round((o.opacity ?? 0.5) * 100);
  $('#county-field').hidden = !(o.counties || o.collection);
  /* THE HISTORIC WARNING IS SHOWN WHENEVER A HISTORIC SHEET IS. Stage 1 makes no
     historical claim, and a modern network drawn over an 1890s sheet is the easiest
     way in this whole project to imply one by accident. The note is not decoration;
     it is the reason the backdrop is allowed to be here at all. */
  $('#historic-note').hidden = !o.historic;
  $('#backdrop-note').innerHTML = o.note ? esc(o.note) : '';
  $('#backdrop-note').hidden = !o.note;
}
sel.onchange = () => {
  const prev = opts[backdropId];
  const prevSrc = prev && (prev.counties || prev.collection);
  if (prevSrc) picked.delete(prevSrc);      // leaving a collection forgets the choice
  backdropId = sel.value;
  applyBackdrop();
  writeHash();
};

function buildItemPicker(o) {
  const src = o.counties || o.collection;
  const list = itemsFor(o);
  const cs = $('#county');
  $('#county-label').textContent = o.item_label || 'Sheet';
  cs.innerHTML = '';
  for (const c of list) {
    const id = c.code || c.id;
    const flags = [
      c.masked === false ? 'unmasked' : null,
      c.in_scope === false ? 'out of scope' : null,
      c.zooms ? `to z${Math.max(...c.zooms)}` : null,
    ].filter(Boolean).join(', ');
    cs.append(new Option(`${c.name || id}${c.code ? ` (${c.code})` : ''}`
      + (flags ? ` — ${flags}` : ''), id));
  }
  if (!itemRow(o)) chosen[src] = list[0] && (list[0].code || list[0].id);
  cs.value = chosen[src];
  cs.onchange = () => {
    chosen[src] = cs.value;
    picked.add(src);
    applyBackdrop();
    writeHash();
    const row = itemRow(o);
    if (row && row.bounds) {
      map.fitBounds([[row.bounds[0], row.bounds[1]], [row.bounds[2], row.bounds[3]]],
        { padding: 30, maxZoom: 14 });
    }
  };
}
$('#backdrop-opacity').oninput = (e) => {
  if (map.getLayer('backdrop')) {
    map.setPaintProperty('backdrop', 'raster-opacity', Number(e.target.value) / 100);
  }
  writeHash();
};

/* ── Colouring ────────────────────────────────────────────────────────────── */

const THEMES = {
  reach: {
    colour: ['case',
      ['!', ['get', 'in_scope']], C.outscope,
      ['get', 'reaches_tidal'], C.reach,
      C.unreached],
    legend: [['Whether it reaches tidal water', null],
      ['reaches tidal water', C.reach],
      ['in scope, and does NOT — the work', C.unreached],
      ['out of scope', C.outscope]],
  },
  form: {
    colour: ['match', ['coalesce', ['get', 'form'], 'added'],
      'inlandRiver', C.reach, 'canal', C.canal, 'lake', C.lake,
      'tidalRiver', C.tidal, C.add],
    legend: [['Form of water', null], ['inland river', C.reach], ['canal', C.canal],
      ['lake', C.lake], ['tidal river', C.tidal],
      ['added by this project — the same yellow as the Connectors layer, '
       + 'deliberately: they are the same geometry', C.add]],
  },
  origin: {
    colour: ['case', ['==', ['get', 'origin'], 'survey'], C.reach, C.add],
    legend: [['Whose geometry it is', null],
      ["Ordnance Survey's, unmodified", C.reach],
      ['added by this project', C.add]],
  },
  scope: {
    colour: ['match', ['coalesce', ['get', 'scope_rule'], 'none'],
      'basin', C.reach, 'country', C.canal, 'neither', C.outscope, C.warn],
    legend: [['Why it is in scope', null], ['its basin is', C.reach],
      ['the country rule', C.canal], ['neither — out of scope', C.outscope]],
  },
  /* Lakes, and whether the survey gives them a name. Not one named lake link in this
     network carries the word "Reservoir", which is a claim about what OS Open Rivers
     records and is far more convincing seen than stated. Everything that is not a
     lake drops back to near-invisible so the lakes are the picture. */
  lake: {
    colour: ['case',
      ['!=', ['get', 'form'], 'lake'], '#39414d',
      ['==', ['coalesce', ['get', 'name'], ''], ''], C.warn,
      C.lake],
    legend: [['Lake links, by whether the survey names them', null],
      ['named', C.lake], ['unnamed', C.warn], ['not a lake', '#39414d'],
      ['`name` is the WELSH form where one exists — the English is in `name_alt`', null]],
  },
};
let theme = HASH.t && THEMES[HASH.t] ? HASH.t : 'reach';

/* Wide enough to be READ at national zoom. The first draft drew the trunk at 0.7 px
   over a 40% OpenStreetMap raster, and the network was less visible than the defects
   sitting on it — which inverts what the map is for. */
const WIDTH = ['interpolate', ['linear'], ['zoom'],
  5, ['case', ['get', 'in_scope'], 1.3, 0.7],
  9, ['case', ['get', 'in_scope'], 1.8, 0.9],
  13, ['case', ['get', 'in_scope'], 2.6, 1.3],
  17, 5.5];

/* ── Overlays, every one of which is small enough to serve whole ──────────── */

const OVERLAYS = [
  { id: 'basins', label: 'Basins, by share reaching the sea', url: '/api/basins.geojson',
    kind: 'polygon', on: false, swatch: '#3b4a5e',
    note: 'a basin at 40% is the finding a national figure hides' },
  { id: 'connectors', label: 'Connectors — geometry we added', url: '/api/lines?kind=connectors',
    kind: 'line', on: false, colour: C.add, width: 2.6, count: c.connectors },
  { id: 'reversals', label: 'Reversals — direction changed, geometry untouched',
    url: '/api/lines?kind=reversals', kind: 'line', on: false, colour: C.rev,
    width: 2.6, arrows: true, count: c.reversals },
  { id: 'retired', label: 'Retired — superseded, kept', url: '/api/lines?kind=retired',
    kind: 'line', on: false, colour: C.retiredc, width: 2.2, dash: [2, 2], count: c.retired },
  { id: 'dead_ends', label: 'Dead ends that are the work', url: '/api/points?kind=dead_ends',
    kind: 'point', on: true, colour: C.unreached, count: c.dead_ends_defect,
    radius: ['interpolate', ['linear'], ['zoom'],
      5, ['interpolate', ['linear'], ['get', 'upstream_km'], 0, 2.2, 50, 5, 1200, 11],
      12, ['interpolate', ['linear'], ['get', 'upstream_km'], 0, 4, 50, 9, 1200, 20]],
    note: 'sized by the length draining into them' },
  /* Its own pale blue rather than the network's: under the `reach` theme sharing blue
     would read as "this is the good case", which is true, but under `form` that same
     blue means inland river and the pairing becomes a false claim. A layer cannot
     borrow a hue whose meaning changes when the theme does. */
  { id: 'dead_ends_tidal', label: 'Dead ends at tidal water — correct',
    url: '/api/points?kind=dead_ends_tidal', kind: 'point', on: false, colour: '#7ad6ff',
    count: c.dead_ends_tidal },
  { id: 'corrections', label: 'Every curated judgement', url: '/api/points?kind=corrections',
    kind: 'point', on: false, count: c.corrections,
    colour: ['match', ['get', 'kind'], 'connector', C.add, 'reversal', C.rev,
      'junction', C.warn, '#ffffff'],
    note: 'click one and ask whether a person would have drawn it there' },
  { id: 'findings', label: "The audit's own findings", url: '/api/points?kind=findings',
    kind: 'point', on: false, count: c.findings,
    /* A refused crossing splits in two, and the split is the point: where the Canal &
       River Trust records an aqueduct or culvert within 150 m the refusal is
       corroborated, and where it does not it is only unrefuted — the Trust covers 101
       waterways, so no recorded structure is not evidence of absence. The uncorroborated
       ones are drawn hot because they are the ones a person has to settle. */
    colour: ['case',
      ['all', ['==', ['get', 'kind'], 'refused_crossing'], ['==', ['get', 'corroborated'], true]],
      '#5a8fb8',
      ['==', ['get', 'kind'], 'refused_crossing'], C.warn,
      ['match', ['get', 'kind'], 'dead_end', C.unreached,
        'direction_fault', C.warn, 'stranded_component', C.retiredc,
        'touching_not_joined', C.rev, '#ffffff']] },
  /* THREE CLASSES, NOT TWO. Colouring these by `corroborated` alone drew a map of
     where the Canal & River Trust has waterways, not of where a refusal is doubtful:
     all 232 corroborated crossings are in Trust country. The distinction that carries
     information is whether the register COULD have recorded a structure and did not —
     48 of them — against the 55 the register was never going to speak about. */
  { id: 'refused_crossings', label: 'Refused 0 m crossings — all 335',
    url: '/api/points?kind=refused_crossings', kind: 'point', on: false,
    colour: ['case',
      ['get', 'corroborated'], '#5a8fb8',
      ['get', 'in_trust_country'], C.unreached,
      C.warn],
    radius: ['interpolate', ['linear'], ['zoom'],
      5, ['case', ['get', 'corroborated'], 2.2, ['get', 'in_trust_country'], 4.2, 3],
      14, ['case', ['get', 'corroborated'], 4.5, ['get', 'in_trust_country'], 10, 6]],
    legend: [['corroborated — a Trust structure within 150 m', '#5a8fb8'],
             ['NOT corroborated, and in Trust country — the register could have '
              + 'recorded one and did not', C.unreached],
             ['not corroborated, outside Trust country — the register was never '
              + 'going to speak about these', C.warn]],
    note: 'the 48 red ones are the sharp list' },
  /* THE SEA NETWORK. Coloured by depth rather than given one colour, because depth is
     what makes a long limb reasonable or suspect: a 150 km hop through 60 m of water is
     a different object from a 150 km hop through 3 m, and one flat colour hides which
     you are looking at. It is a TREE — 4,183 edges over 4,184 entries, no cycle — so
     every line here is the only way between the two coasts it joins. */
  { id: 'sea_route', label: 'The sea network — routes', url: '/api/sea?kind=sea_route',
    kind: 'line', on: false, width: 1.6, count: c.sea_routes,
    colour: ['interpolate', ['linear'], ['coalesce', ['get', 'median_depth_m'], 0],
      0, '#9fe8ff', 10, '#37b6e8', 40, '#1f6fc4', 120, '#123f8a'],
    legend: [['shallow — under 10 m', '#9fe8ff'], ['about 40 m', '#1f6fc4'],
             ['deep — 120 m and over', '#123f8a'],
             ['a tree, not a loop: every line is the only way between the coasts '
              + 'it joins', null]],
    note: 'one connected component; the median route is 1.2 km and the longest is 150 km' },
  { id: 'sea_entry', label: 'Sea entries — where a mouth meets open water',
    url: '/api/sea?kind=sea_entry', kind: 'point', on: false, count: c.sea_entries,
    colour: ['case', ['==', ['get', 'kind'], 'blocked'], C.warn, '#5ce1e6'],
    radius: ['interpolate', ['linear'], ['zoom'],
      5, ['interpolate', ['linear'], ['get', 'snapped_m'], 0, 1.6, 15000, 7],
      13, ['interpolate', ['linear'], ['get', 'snapped_m'], 0, 3, 15000, 16]],
    legend: [['a tidal terminus', '#5ce1e6'], ['a blocked mouth', C.warn],
             ['sized by how far the mouth moved to reach open water — the tail is '
              + 'where the coast and the network disagree most', null]],
    note: 'blocked mouths sit at the coast (median 707 m moved); termini often sit well '
      + 'inside estuaries (median 2,524 m). 1,864 mouths attach to nothing at all, '
      + 'which is geography and not failure.' },
  { id: 'seeds', label: 'Seed nodes — where the crawl starts',
    url: '/api/points?kind=seeds', kind: 'point', on: false, colour: C.seed,
    count: c.seeds },
  /* Two colours, because the difference is load-bearing and invisible otherwise: a
     node can be tidal without the reachability crawl having started there, and 10,784
     of the 13,030 are. A single-colour layer here says "the network meets the sea in
     13,030 places", which is true, and lets a reader assume all of them were used. */
  { id: 'tidal', label: 'Tidal termini', url: '/api/points?kind=tidal', kind: 'point',
    on: false, count: c.tidal_nodes,
    colour: ['case', ['get', 'is_crawl_seed'], C.tidal, '#4a5568'],
    radius: ['interpolate', ['linear'], ['zoom'],
      5, ['case', ['get', 'is_crawl_seed'], 2.6, 1.6],
      14, ['case', ['get', 'is_crawl_seed'], 6, 3.5]],
    legend: [['the crawl started here', C.tidal],
             ['tidal, but not a crawl seed', '#4a5568']],
    note: 'the published terminus layer, not inferred — click one for how much length '
      + 'arrives and in what form' },
];

const loaded = new Set();

function arrowImage(fill = C.rev) {
  const s = 14;
  const cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.fillStyle = '#0d1117';
  g.beginPath(); g.arc(s / 2, s / 2, s / 2 - 0.5, 0, Math.PI * 2); g.fill();
  g.fillStyle = fill;
  g.beginPath(); g.moveTo(s * 0.78, s / 2); g.lineTo(s * 0.28, s * 0.22);
  g.lineTo(s * 0.28, s * 0.78); g.closePath(); g.fill();
  return g.getImageData(0, 0, s, s);
}

map.on('load', async () => {
  /* The whole network's flow arrows are NEUTRAL; only the reversals' are green. They
     had shared a sprite, so turning on flow direction painted the entire network in the
     colour that means "this one was reversed". */
  map.addImage('arrow', arrowImage('#cfd8e3'));
  map.addImage('arrow-reversed', arrowImage(C.rev));

  map.addSource('network', { type: 'geojson', data: empty() });
  map.addLayer({
    id: 'network-out', type: 'line', source: 'network',
    filter: ['!', ['get', 'in_scope']],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': THEMES[theme].colour, 'line-width': WIDTH,
      'line-opacity': 0.5 },
  });
  map.addLayer({
    id: 'network', type: 'line', source: 'network', filter: ['get', 'in_scope'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': THEMES[theme].colour, 'line-width': WIDTH },
  });
  /* Flow direction. A reversal moves no geometry, so without arrows the single most
     error-prone correction in the build is invisible on a map. */
  map.addLayer({
    id: 'network-arrows', type: 'symbol', source: 'network', minzoom: 12,
    filter: ['get', 'in_scope'],
    layout: { 'symbol-placement': 'line', 'icon-image': 'arrow', 'icon-size': 0.75,
      'symbol-spacing': 90, 'icon-allow-overlap': false,
      'icon-rotation-alignment': 'map', visibility: 'none' },
    paint: { 'icon-opacity': 0.85 },
  });
  map.addLayer({ id: 'network-hi', type: 'line', source: 'network',
    filter: ['==', ['get', 'link_id'], ''],
    paint: { 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.5 } });

  buildLayerPanel();

  /* THE BOOT PATH GOES THROUGH THE SAME CODE A CLICK DOES. The map's opening style
     builds the backdrop inline, which is enough for a plain layer and not enough for a
     collection — the item picker never appears and a link naming a sheet cannot take
     effect. Running applyBackdrop() here means a shared link and a click reach the same
     state by the same route, which is the only way the two stay in agreement. */
  sel.value = backdropId;
  try {
    await applyBackdrop();
  } catch (err) {
    console.error('the backdrop named in the link could not be applied:', err);
  }

  /* A link's layer list replaces the defaults entirely — `l=-` means "none on", which
     is a state a reader can deliberately arrive at and must be able to send. */
  const wanted = HASH.l === undefined ? null
    : (HASH.l === '-' ? [] : HASH.l.split(','));
  const boxes = [...document.querySelectorAll('#layers .switch')];
  for (const [i, o] of OVERLAYS.entries()) {
    const want = wanted ? wanted.includes(o.id) : o.on;
    // ONE LAYER'S FAILURE MUST NOT SILENCE THE REST. An await that rejects inside this
    // loop abandons every layer after it, and the reader sees a link that restored
    // half of what it named with nothing said about the other half.
    try {
      if (want) await ensure(o);
      if (wanted) {
        const box = boxes[i]?.querySelector('input');
        if (box) box.checked = want;
        if (loaded.has(o.id)) setVisible(o, want);
      }
    } catch (err) {
      console.warn(`layer ${o.id} could not be restored from the link:`, err);
    }
  }
  if (HASH.o !== undefined) {
    $('#backdrop-opacity').value = HASH.o;
    $('#backdrop-opacity').dispatchEvent(new Event('input'));
  }
  $('#theme').value = theme;
  applyTheme();

  /* LAST WORD ON WHERE WE ARE. Restoring a backdrop can fly the map — choosing a county
     fits its bounds — so the view the link asked for is re-asserted after everything
     else has run, rather than trusting that nothing moved it. */
  if (HASH.zoom !== undefined) {
    map.jumpTo({ center: [HASH.lon, HASH.lat], zoom: HASH.zoom });
  }
  hashReady = true;                 // from here the address bar may follow the map
  refresh();
  writeHash();
});

function empty() { return { type: 'FeatureCollection', features: [] }; }

async function ensure(o) {
  if (loaded.has(o.id)) return;
  loaded.add(o.id);
  const data = await fetch(o.url).then((r) => r.json());
  map.addSource(o.id, { type: 'geojson', data });
  if (o.kind === 'polygon') {
    map.addLayer({
      id: o.id + '-fill', type: 'fill', source: o.id,
      paint: {
        'fill-color': ['case',
          ['!', ['get', 'in_scope']], '#3a424f',
          ['==', ['get', 'share'], null], '#3a424f',
          ['interpolate', ['linear'], ['get', 'share'],
            0, '#ff2d55', 0.6, '#ff9f1c', 0.9, '#3b7d3b', 1, '#1b5e20']],
        'fill-opacity': 0.35,
      },
    }, 'network-out');
    map.addLayer({
      id: o.id + '-line', type: 'line', source: o.id,
      paint: { 'line-color': '#8fa0b8', 'line-width': 0.6, 'line-opacity': 0.5 },
    }, 'network-out');
  } else if (o.kind === 'line') {
    /* A CASING, so an overlay line is never mistaken for a network line. Colour alone
       cannot carry this: the network is drawn in whatever the current theme says, and a
       reader switching themes should not have to relearn which lines are the survey's
       and which are this project's marks on it. A dark halo says "on top" in every
       theme and at every zoom. */
    map.addLayer({
      id: o.id + '-casing', type: 'line', source: o.id,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0d1117', 'line-width': (o.width || 2) + 2.5,
        'line-opacity': 0.85 },
    });
    map.addLayer({
      id: o.id, type: 'line', source: o.id,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': o.colour, 'line-width': o.width,
        ...(o.dash ? { 'line-dasharray': o.dash } : {}),
      },
    });
    if (o.arrows) {
      map.addLayer({
        id: o.id + '-arrows', type: 'symbol', source: o.id,
        layout: { 'symbol-placement': 'line', 'icon-image': 'arrow-reversed',
          'icon-size': 0.9,
          'symbol-spacing': 70, 'icon-allow-overlap': true,
          'icon-rotation-alignment': 'map' },
      });
    }
  } else {
    map.addLayer({
      id: o.id, type: 'circle', source: o.id,
      paint: {
        'circle-color': o.colour,
        'circle-radius': o.radius ?? ['interpolate', ['linear'], ['zoom'], 5, 2.6, 14, 6],
        'circle-stroke-color': '#0d1117', 'circle-stroke-width': 1,
        'circle-opacity': 0.9,
      },
    });
  }
  wireClicks(o);
}

function setVisible(o, on) {
  const ids = [o.id, o.id + '-fill', o.id + '-line', o.id + '-arrows',
    o.id + '-casing'];
  for (const id of ids) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
  }
}

function buildLayerPanel() {
  const host = $('#layers');
  for (const o of OVERLAYS) {
    const row = document.createElement('label');
    row.className = 'switch';
    /* A LAYER COLOURED BY ITS DATA HAS NO ONE COLOUR, and showing white for it made
       four different layers — judgements, findings, refused crossings and seeds — carry
       the same blank swatch, which reads as a key and is not one. Such a layer gets a
       band of the colours it actually uses, pulled out of its own paint expression. */
    // `JSON.stringify(undefined)` is undefined, not '"undefined"' — the basins layer
    // carries a swatch and no colour, and this threw and emptied the whole panel.
    const hues = typeof o.colour === 'string' ? [o.colour]
      : ((o.colour ? JSON.stringify(o.colour).match(/#[0-9a-fA-F]{6}/g) : null)
         || [o.swatch || '#8a93a0']);
    const uniq = [...new Set(hues)];
    const swatch = uniq.length === 1 ? uniq[0]
      : `linear-gradient(90deg, ${uniq.map((h, n) =>
          `${h} ${Math.round(n * 100 / uniq.length)}% ${Math.round((n + 1) * 100 / uniq.length)}%`
        ).join(', ')})`;
    row.innerHTML = `<input type="checkbox" ${o.on ? 'checked' : ''}>
      <i class="sw ${o.kind === 'point' ? 'dot' : ''}" style="background:${swatch}"
         title="${esc(uniq.join(' · '))}"></i>
      <span>${esc(o.label)}</span><em>${o.count != null ? fmt(o.count) : ''}</em>`;
    row.querySelector('input').onchange = async (e) => {
      if (e.target.checked) { await ensure(o); setVisible(o, true); }
      else setVisible(o, false);
      applyTheme();
      writeHash();
    };
    host.append(row);
    if (o.note) {
      const n = document.createElement('p');
      n.className = 'note';
      n.style.margin = '0 0 6px 22px';
      n.textContent = o.note;
      host.append(n);
    }
  }
  const arrowRow = document.createElement('label');
  arrowRow.className = 'switch';
  arrowRow.innerHTML = `<input type="checkbox"><i class="sw" style="background:#cfd8e3"></i>
    <span>Flow direction on the whole network</span><em>z12+</em>`;
  arrowRow.querySelector('input').onchange = (e) =>
    map.setLayoutProperty('network-arrows', 'visibility', e.target.checked ? 'visible' : 'none');
  host.append(arrowRow);
}

function applyTheme() {
  for (const id of ['network', 'network-out']) {
    map.setPaintProperty(id, 'line-color', THEMES[theme].colour);
  }
  const l = $('#legend');
  /* A layer whose colours mean something other than the theme's says so, or the reader
     has three unexplained colours on the map and a legend about something else. */
  const extra = OVERLAYS.filter((o) => o.legend && loaded.has(o.id)
      && map.getLayer(o.id)
      && map.getLayoutProperty(o.id, 'visibility') !== 'none')
    .flatMap((o) => (o.legend ? [[o.label, null], ...o.legend] : []));
  const rows = [...THEMES[theme].legend];
  if (extra.length) rows.push(['Drawn on top', null], ...extra.slice(0));
  l.innerHTML = rows.map(([text, colour], i) => colour
    ? `<span><i style="background:${colour}"></i>${esc(text)}</span>`
    : i === 0 ? `<b>${esc(text)}</b>`
      : `<span class="foot">${esc(text)}</span>`).join('')
    + '<b>Never thinned, at any zoom</b>'
    + thin.never_thinned.map((t) => `<span style="opacity:.75">${esc(t)}</span>`).join('');
}
$('#theme').onchange = (e) => { theme = e.target.value; applyTheme(); writeHash(); };

/* ── The network itself, per viewport ─────────────────────────────────────── */

/* ── Writing the view back ─────────────────────────────────────────────────── */

let hashTimer;
/* NOTHING WRITES THE HASH UNTIL THE HASH HAS BEEN READ AND APPLIED. `moveend` fires
   during the restore, and a writeHash from it replaced the link a reader had just
   opened with the half-restored state — so following someone's link and then reloading
   took you somewhere else, and the original was gone from the address bar. A link that
   destroys itself on open is worse than no link. */
let hashReady = false;
function writeHash() {
  if (!hashReady) return;
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const c = map.getCenter();
    const o = opts[backdropId];
    const parts = [`${map.getZoom().toFixed(2)}/${c.lat.toFixed(5)}/${c.lng.toFixed(5)}`];
    if (backdropId !== backdrops.basemap.default) parts.push(`b=${backdropId}`);
    const src = o && (o.counties || o.collection);
    if (src && chosen[src]) parts.push(`i=${chosen[src]}`);
    const op = Math.round(Number($('#backdrop-opacity').value));
    if (o && op !== Math.round((o.opacity ?? 0.5) * 100)) parts.push(`o=${op}`);
    if (theme !== 'reach') parts.push(`t=${theme}`);
    const on = OVERLAYS.filter((x) => map.getLayer(x.id === 'basins' ? 'basins-fill' : x.id)
      && map.getLayoutProperty(x.id === 'basins' ? 'basins-fill' : x.id, 'visibility') !== 'none')
      .map((x) => x.id);
    const dflt = OVERLAYS.filter((x) => x.on).map((x) => x.id);
    if (on.join() !== dflt.join()) parts.push(`l=${on.join(',') || '-'}`);
    const k = $('#finding-kind');
    if (k && k.value) parts.push(`f=${k.value}`);
    history.replaceState(null, '', '#' + parts.join('&'));
  }, 250);
}

let pending = null;
let seq = 0;

async function refresh() {
  const z = map.getZoom();
  const b = map.getBounds();
  const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
    .map((v) => v.toFixed(4)).join(',');
  const mine = ++seq;
  const url = `/api/network?bbox=${bbox}&zoom=${z.toFixed(2)}`;
  const data = await fetch(url).then((r) => r.json()).catch(() => null);
  if (!data || mine !== seq) return;
  map.getSource('network').setData(data);
  const m = data.meta;
  const th = m.threshold_m
    ? `Drawing every link of <b>${fmt(m.threshold_m)} m and over</b>`
    : 'Drawing <b>every link</b>';
  $('#thinning').innerHTML = `${th}${m.national ? ' nationally' : ' in this viewport'}
    — ${fmt(m.drawn)} of ${fmt(m.in_viewport)}, simplified to ${fmt(m.tolerance_m)} m.
    ${m.truncated ? '<b style="color:var(--bad)">Truncated at the cap — zoom in.</b> ' : ''}
    Four classes are drawn whatever their length; the legend names them.
    ${m.threshold_m ? 'A channel not drawn here is <em>not</em> a channel that is missing.' : ''}`;
}

let debounce;
const scheduleRefresh = () => { clearTimeout(debounce); debounce = setTimeout(refresh, 180); };
map.on('moveend', scheduleRefresh);
map.on('moveend', writeHash);
map.on('zoomend', scheduleRefresh);
/* A flight started from the panel ends in `moveend` like any other move, but the
   panel's own await (the basin index is 2 MB) can start the flight late enough that
   the listener is attached mid-animation. Asking again when it settles is cheap and
   a viewport drawn from the previous place is the worst thing this map could do. */
map.on('idle', () => { if (!debounce) scheduleRefresh(); });

/* ── Clicking things ──────────────────────────────────────────────────────── */

function dl(obj, order) {
  const keys = order || Object.keys(obj);
  return '<dl>' + keys.filter((k) => obj[k] !== null && obj[k] !== undefined && obj[k] !== '')
    .map((k) => `<dt>${esc(k)}</dt><dd>${esc(obj[k])}</dd>`).join('') + '</dl>';
}

function popup(lngLat, html) {
  new maplibregl.Popup({ maxWidth: '340px', closeButton: true })
    .setLngLat(lngLat).setHTML(html).addTo(map);
}

function wireClicks(o) {
  const target = o.kind === 'polygon' ? o.id + '-fill' : o.id;
  map.on('mouseenter', target, () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', target, () => { map.getCanvas().style.cursor = ''; });
  map.on('click', target, (e) => {
    const p = { ...e.features[0].properties };
    let head = `<b>${esc(o.label)}</b>`;
    let extra = '';
    if (o.id === 'corrections') {
      /* The distinction the whole layer turns on: whether a person looked at the
         place, or a rule decided. Say it before anything else. */
      extra = `<div class="quote"><b>${p.by_rule === true || p.by_rule === 'true'
        ? 'JUDGED BY RULE — no person has looked at this place'
        : 'adjudicated at the place'}</b><br>${esc(p.evidence)}</div>`;
      if (p.placed && p.placed !== 'recorded with the judgement') {
        head += `<br><span style="color:var(--warn)">position derived: ${esc(p.placed)}</span>`;
      }
      delete p.evidence; delete p.by_rule;
    }
    if (o.id.startsWith('dead_end')) {
      head += `<br>${fmt(p.upstream_km, 1)} km drains here and stops`;
    }
    popup(e.lngLat, head + dl(p) + extra);
  });
}

map.on('click', 'network', async (e) => {
  const f = e.features[0];
  map.setFilter('network-hi', ['==', ['get', 'link_id'], f.properties.link_id]);
  popup(e.lngLat, '<b>loading…</b>');
  const d = await fetch('/api/link?id=' + encodeURIComponent(f.properties.link_id))
    .then((r) => r.json());
  const corr = d.corrections || [];
  delete d.corrections;
  const fromN = d.from_node_detail; const toN = d.to_node_detail;
  delete d.from_node_detail; delete d.to_node_detail;
  /* `name` is OS's `watercourseName`, which carries the WELSH form where one exists;
     the English sits in `name_alt`. On a map of England and Wales both belong in the
     heading, or half the country reads as unnamed to an English speaker. */
  const title = d.name
    ? esc(d.name) + (d.name_alt ? ` <span style="color:var(--ink-dim)">/ ${esc(d.name_alt)}</span>` : '')
    : (d.name_alt ? esc(d.name_alt) : '(unnamed)');
  let html = `<b>${title}</b>` + dl(d);
  if (fromN || toN) {
    html += `<b>Ends</b><dl>
      <dt>upstream</dt><dd>${esc(fromN?.category ?? '?')} / ${esc(fromN?.terminus ?? '?')}</dd>
      <dt>downstream</dt><dd>${esc(toN?.category ?? '?')} / ${esc(toN?.terminus ?? '?')}</dd></dl>`;
  }
  for (const k of corr) {
    html += `<div class="quote"><b>${esc(k.kind)} — ${esc(k.correction_id)}</b><br>
      ${esc(k.reason)}<br><br>${esc(k.evidence)}</div>`;
  }
  popup(e.lngLat, html);
});
map.on('mouseenter', 'network', () => { map.getCanvas().style.cursor = 'pointer'; });
map.on('mouseleave', 'network', () => { map.getCanvas().style.cursor = ''; });

/* ── The lists: worst first, click to fly ─────────────────────────────────── */

let basinIndex = null;

async function basinCentres() {
  if (basinIndex) return basinIndex;
  const g = await fetch('/api/basins.geojson').then((r) => r.json());
  basinIndex = {};
  for (const f of g.features) {
    let minx = 180, miny = 90, maxx = -180, maxy = -90;
    const walk = (a) => {
      if (typeof a[0] === 'number') {
        minx = Math.min(minx, a[0]); maxx = Math.max(maxx, a[0]);
        miny = Math.min(miny, a[1]); maxy = Math.max(maxy, a[1]);
      } else a.forEach(walk);
    };
    walk(f.geometry.coordinates);
    basinIndex[f.properties.basin_id] = [[minx, miny], [maxx, maxy]];
  }
  return basinIndex;
}

function renderBasins(filter = '') {
  const host = $('#basin-list');
  host.innerHTML = '';
  const f = filter.toLowerCase();
  const rows = summary.basins.filter((b) => !f || (b.label || '').toLowerCase().includes(f));
  for (const b of rows.slice(0, 250)) {
    const li = document.createElement('li');
    if (b.share != null && b.share < 0.75) li.className = 'warnrow';
    li.innerHTML = `<span class="t">${esc(b.label || b.basin_id)}${b.has_outlet ? ''
      : ' <span style="color:var(--warn)">· no outlet</span>'}</span>
      <span class="m">${share(b.share)}</span>
      <span class="bar"><i style="width:${(b.share ?? 0) * 100}%"></i></span>
      <span class="cap">${fmt(b.unreached_km, 1)} km stranded of ${fmt(b.km, 0)} km${
        b.dead_ends ? ` · ${fmt(b.dead_ends)} dead end${b.dead_ends === 1 ? '' : 's'}` : ''}</span>`;
    li.onclick = async () => {
      const idx = await basinCentres();
      const bb = idx[b.basin_id];
      if (bb) map.fitBounds(bb, { padding: 60, maxZoom: 12 });
    };
    host.append(li);
  }
  if (!rows.length) host.innerHTML = '<li><span class="t">nothing matches</span></li>';
}
$('#basin-filter').oninput = (e) => renderBasins(e.target.value);
renderBasins();

/* THE BASIN LIST DOES NOT ACCOUNT FOR EVERY DEAD END, and an unexplained difference
   between two counts on one screen is how a wrong one gets quoted. A dead end is in
   scope because its arriving link is, not because its node sits in an in-scope basin;
   tidal water is masked out of the DEM, so an estuarine node sits in no basin at all.
   Those are the ones where the answer matters most. */
if (c.dead_ends_no_basin) {
  const n = document.createElement('p');
  n.className = 'note';
  n.innerHTML = `<b>${fmt(c.dead_ends_no_basin)} of the ${fmt(c.dead_ends_defect)}
    dead ends sit in no basin at all</b> and are in none of these rows — tidal water is
    masked out of the DEM, so an estuarine node belongs to no catchment. They are on the
    map. Scope follows the arriving link, not the node's basin.`;
  $('#basin-list').after(n);
}

const findings = await fetch('/api/points?kind=findings').then((r) => r.json());
const kinds = [...new Set(findings.features.map((f) => f.properties.kind))].sort();
const ksel = $('#finding-kind');
ksel.append(new Option('every kind', ''));
for (const k of kinds) {
  const n = findings.features.filter((f) => f.properties.kind === k).length;
  ksel.append(new Option(`${k.replace(/_/g, ' ')} (${n})`, k));
}
/* A refused crossing that nothing corroborates goes to the top of its own list: it is
   the only kind here where the finding is a question rather than a defect. */
const uncorrob = findings.features.filter(
  (f) => f.properties.kind === 'refused_crossing' && f.properties.corroborated === false).length;
if (uncorrob) ksel.append(new Option(`refused crossing, uncorroborated (${uncorrob})`, '!rc'));
function renderFindings() {
  const want = ksel.value;
  const host = $('#finding-list');
  host.innerHTML = '';
  const match = (x) => (want === '!rc'
    ? x.properties.kind === 'refused_crossing' && x.properties.corroborated === false
    : !want || x.properties.kind === want);
  for (const f of findings.features.filter(match)) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="t">${esc(f.properties.detail || f.properties.subject)}</span>
      <span class="m">${esc(f.properties.kind.replace(/_/g, ' '))}</span>`;
    li.onclick = () => {
      map.flyTo({ center: f.geometry.coordinates, zoom: 14 });
      popup(f.geometry.coordinates,
        `<b>${esc(f.properties.kind.replace(/_/g, ' '))}</b>${dl(f.properties)}`);
    };
    host.append(li);
  }
}
ksel.onchange = () => { renderFindings(); writeHash(); };
if (HASH.f && [...ksel.options].some((o) => o.value === HASH.f)) ksel.value = HASH.f;
renderFindings();


/* ── Sharing ───────────────────────────────────────────────────────────────── */

$('#copy-link').onclick = async () => {
  writeHash();
  await new Promise((r) => setTimeout(r, 300));       // let the debounce land
  const url = location.href;
  const say = (msg) => {
    const el = $('#copied');
    el.hidden = false;
    el.textContent = msg;
    setTimeout(() => { el.hidden = true; }, 4000);
  };
  try {
    await navigator.clipboard.writeText(url);
    say('Copied. It carries the place, the zoom, the backdrop and sheet, the colouring '
        + 'and which layers are on.');
  } catch (e) {
    /* clipboard access is refused on an insecure origin in some browsers, and localhost
       is not always treated as secure. Selecting the address bar is the fallback a
       reader can act on; a silent failure is not. */
    say('The browser refused clipboard access — copy the address bar instead.');
  }
};


/* ── Epochs ─────────────────────────────────────────────────────────────────
 * The stops are `docs/epochs.md`'s published set, and the datum is deliberately NOT one
 * of them: the modern network is what the whole series is worked back from, not an
 * epoch in it. So the control has one reachable position and seven that visibly are
 * not, which is the true state of the project and is the point of showing it.
 *
 * Stage 1 makes no historical claim whatever. This map is the artefact on which most
 * people will actually form a belief about that, and it was the one saying nothing.
 *
 * THE RATIONALE FOR EACH DATE IS NOT COPIED HERE, not even as an example in this
 * comment — an illustrative quotation is still a second copy, and it drifts in exactly
 * the same way while looking harmless because it does not render. `docs/epochs.md`
 * carries a "why this date" for every epoch; that file is the only place it lives.
 * Retyping any of it here would make two copies of one fact, and two copies are
 * two things that can disagree; four sentences in this project were true in the morning
 * and false by the afternoon today, none caught by anything that was running. So the
 * selector carries STATUS, which is its own to know, and links to the page for the
 * reasoning — one click away rather than one copy away. If the epoch table ever becomes
 * data, `epochs.json` beside this file is read instead and the drift becomes impossible.
 */

const EPOCHS_JSON = 'https://docuracy.github.io/REWT/epochs.json';
const EPOCHS_PAGE = 'https://docuracy.github.io/REWT/epochs';
const EPOCH_YEARS = [1086, 1300, 1540, 1600, 1700, 1830, 1900];
const DATUM_NOTE =
  'The datum, and what you are looking at: the present-day network made traversable. '
  + 'It is NOT an epoch in the series — the dated cross-sections are worked backwards '
  + 'from it. Nothing on this map is dated.';

async function buildEpochs() {
  const host = $('#epoch-steps');
  const note = $('#epoch-note');
  /* Generated by Jekyll from `docs/_data/epochs.yml`, which owns both the temporality
     page's table and this control. Fetched from the published site rather than the
     repository path because it exists only in the built output — and cross-origin from
     localhost, which works because Pages sends `access-control-allow-origin: *`. */
  const table = await fetch(EPOCHS_JSON).then((r) => (r.ok ? r.json() : null))
    .then((d) => (d && d.epochs) || null).catch(() => null);

  const say = (html) => { note.innerHTML = html; };
  const link = `<a href="${EPOCHS_PAGE}" target="_blank" rel="noopener">Why these dates</a>`;
  const datum = `${esc(DATUM_NOTE)} ${link}`;
  say(datum);

  /* A BARE YEAR IS THE ONE THING THIS CONTROL MUST NOT SHOW. Seven unlabelled dates on
     a map in a project called "Temporally" invite exactly the reading Stage 1 exists to
     prevent. The reason belongs on the stop, and if the data did not load the stops are
     still disabled and still say so — never bare and selectable. */
  const rows = table || EPOCH_YEARS.map((year) => ({ year, why: null }));
  if (!table) {
    say('The epoch rationales could not be fetched from the site, so these stops carry '
      + `their dates only. They remain unbuilt either way. ${link}`);
  }

  for (const e of [...rows, { year: 'Modern', why: DATUM_NOTE }]) {
    const built = e.year === 'Modern';
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.state = built ? 'built' : 'planned';
    b.innerHTML = `<span class="yr">${esc(e.year)}</span>`;
    b.disabled = !built;
    b.title = built ? DATUM_NOTE
      : `${e.year} — not built yet.${e.why ? ' ' + e.why : ''}`;
    // A disabled button swallows its own events, so the explanation hangs on the row.
    b.addEventListener('mouseenter', () => say(built ? datum
      : `<b>${esc(e.year)} — not built.</b> ${e.why ? esc(e.why) + ' ' : ''}`
        + 'The selector switches between separately modelled networks; it does not '
        + `animate one, so nothing is interpolated between stops. ${link}`));
    host.append(b);
  }
  host.addEventListener('mouseleave', () => say(datum));
}
buildEpochs();
