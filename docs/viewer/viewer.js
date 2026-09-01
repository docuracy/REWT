/* REWT — the network as currently assembled, as a published map.
 *
 * THIS IS NOT THE LOCAL VIEWER MOVED. `tools/viewer/serve.py` answers twelve routes
 * with eleven methods that compute rather than serve — a per-viewport read of a 208 MB
 * GeoPackage, the county-masked tile compositor, the dead-end derivation with a reverse
 * BFS for every sink. A published site has no server, so the styling, the palette
 * rules, the hash-URL handling and the epoch control are shared and the data layer is
 * a different program: vector tiles fetched by range, and small layers as flat files.
 *
 * WHAT IT MUST NOT DO IS PRETEND. The local viewer states the thinning in force at
 * every zoom and never lets an absent channel read as "no river here". The same
 * promise holds here, and it is why the network is tiled as TWO layers: `link`, which
 * may drop features at low zoom, and `link_kept`, which may not — the unreached, the
 * retired, the geometry this project added and anything whose routing was reversed are
 * present at every zoom, because they are the reason to be looking.
 */

const $ = (s) => document.querySelector(s);
const fmt = (n, d = 0) => (n == null || Number.isNaN(n) ? '—'
  : Number(n).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x) => (x == null ? '—' : (x * 100).toFixed(2) + '%');
const share = (x) => (x == null ? '—' : x >= 1 ? '100%' : Math.min(99.9, x * 100).toFixed(1) + '%');
const esc = (s) => String(s ?? '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

/* Two palettes, one rule: an overlay shares a theme's colour only where it means the
   same thing. Theme colours are cool because every one of them is water the survey
   drew; overlay colours are warm or bright because none of them is. */
const C = {
  reach: '#1b9ce6', canal: '#6c7bd9', lake: '#2ec4b6', tidal: '#8f6fe8',
  outscope: '#7f8b9c', unreached: '#ff2d55',
  add: '#ffd21e', rev: '#39e08b', retiredc: '#ff5cf0', seed: '#ffffff', warn: '#ff9f1c',
};

const DATA = 'data/';
const problems = [];

async function grab(name, what) {
  try {
    const r = await fetch(DATA + name);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) {
    /* NAMED, NEVER SWALLOWED. A layer that is absent because the release has not been
       built yet and a layer that is absent because there is nothing to show are
       opposite things, and a map that draws neither looks identical. */
    problems.push(`<code>${esc(name)}</code> — ${esc(what)} (${esc(e.message)})`);
    return null;
  }
}

/* ── The view, in the URL ─────────────────────────────────────────────────── */

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

const [summary, backdrops] = await Promise.all([
  grab('summary.json', 'the headline figures and the basin table'),
  fetch('backdrops.json').then((r) => r.json()),
]);

/* ── Figures ──────────────────────────────────────────────────────────────── */

const missing = [];
function need(obj, ...names) {
  for (const n of names) if (obj && obj[n] != null) return obj[n];
  missing.push(names[0]);
  return null;
}
const c = (summary && summary.counts) || {};
const R = (summary && summary.reachability) || {};
const inScopeKm = need(R, 'total_in_scope_km', 'in_scope_km');
const inScopeShare = need(R, 'in_scope_share');

$('#f-share').textContent = pct(inScopeShare);
$('#f-defects').textContent = fmt(c.dead_ends_defect);
$('#f-detail').innerHTML = summary ? `
  ${fmt(inScopeKm)} km in scope, of which
  <b>${fmt(inScopeKm == null || inScopeShare == null ? null : inScopeKm * (1 - inScopeShare))} km
  cannot reach the sea</b>.<br>
  ${fmt(c.links)} links · ${fmt(c.nodes)} nodes · ${fmt(c.basins)} basins ·
  ${fmt(c.corrections)} curated judgements · ${fmt(c.retired)} retired.`
  : 'The figures could not be loaded.';
if (summary && summary.provenance) {
  $('#built').innerHTML = `Built ${esc((summary.provenance.built_at || '').slice(0, 16)
    .replace('T', ' '))}, fingerprint <code>${esc(summary.provenance.config_fingerprint)}</code>.`;
}
$('#attribution').innerHTML = (summary && summary.attribution)
  || 'Contains OS data © Crown Copyright and database rights 2026.';

/* ── Backdrops ────────────────────────────────────────────────────────────── */

const opts = backdrops.options;
const thin = backdrops.thinning;
/* No key handling at all, deliberately: this build has no keyed backdrop to hold one
   for. See `_no_keys` in backdrops.json. */
const usable = Object.entries(opts);
const sel = $('#backdrop');
const GROUPS = [
  ['modern', 'Modern'],
  ['seamless', 'Historic — seamless, England and Wales'],
  ['composited', 'Historic — composited in your browser'],
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
let backdropId = opts[backdrops.default] ? backdrops.default : usable[0][0];
if (HASH.b && opts[HASH.b]) backdropId = HASH.b;
sel.value = backdropId;

const items = {};
let chosen = {};
const picked = new Set();
const itemsFor = (o) => items[o.counties || o.collection] || [];
const itemRow = (o) => itemsFor(o).find((r) => (r.code || r.id) === chosen[o.counties || o.collection]);

const tilesFor = (o) => {
  if (!o.tiles) return null;
  let t = o.tiles;
  if (o.counties || o.collection) {
    const r = itemRow(o);
    t = t.replace('{county}', r?.slug ?? r?.id ?? '').replace('{item}', r?.id ?? '');
  }
  return [t];
};

/* ── The first edition, composited in the browser ──────────────────────────
 * The National Library of Scotland publishes the six-inch FIRST edition county by
 * county, and the mosaics are not cut at the county line — each bleeds over its
 * neighbours, so stacking them puts two different surveys of the same ground on top of
 * each other with the join wherever the draw order falls. The local viewer composites
 * this server-side. A published site has no server, and MapLibre cannot clip a raster
 * to a polygon, so it is done here with a protocol handler and a canvas.
 *
 * A pixel is taken only where the county OWNS the ground and its own sheet HAS
 * something to say there. Both conditions matter: the first stops a mosaic bleeding
 * past its boundary, the second keeps its internal margins transparent rather than
 * painting them white over a neighbour.
 */

let COUNTIES = null;

function tileBounds(z, x, y) {
  const lon = (i) => (i / 2 ** z) * 360 - 180;
  const lat = (j) => {
    const n = Math.PI - (2 * Math.PI * j) / 2 ** z;
    return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
  };
  return [lon(x), lat(y + 1), lon(x + 1), lat(y)];
}

async function countyTile(slug, z, x, y) {
  const url = `https://mapseries-tilesets.s3.amazonaws.com/os/six-inch-${slug}/${z}/${x}/${y}.png`;
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return await createImageBitmap(await r.blob());
  } catch (e) { return null; }
}

maplibregl.addProtocol('firsted', async (params, abort) => {
  const m = params.url.match(/^firsted:\/\/(\d+)\/(\d+)\/(\d+)/);
  if (!m || !COUNTIES) return { data: null };
  const [z, x, y] = m.slice(1).map(Number);
  const [w, s, e, n] = tileBounds(z, x, y);
  const here = COUNTIES.filter((r) => r.in_scope && r.bounds
    && !(r.bounds[2] < w || r.bounds[0] > e || r.bounds[3] < s || r.bounds[1] > n));
  const cv = new OffscreenCanvas(256, 256);
  const g = cv.getContext('2d');
  for (const r of here) {
    const img = await countyTile(r.slug, z, x, y);
    if (!img) continue;
    const layer = new OffscreenCanvas(256, 256);
    const lg = layer.getContext('2d');
    lg.drawImage(img, 0, 0);
    if (r.mask) {
      /* `destination-in` keeps only what falls inside the filled polygon — a mask in
         two operations and no per-pixel work. A county with no polygon (the Isle of
         Man, which the Historic Counties Standard omits) is masked by its own alpha
         alone, which is right: it is an island and no neighbour's sheets reach it. */
      lg.globalCompositeOperation = 'destination-in';
      lg.fillStyle = '#000';
      lg.beginPath();
      for (const ring of r.mask) {
        ring.forEach(([lo, la], i) => {
          const px = ((lo - w) / (e - w)) * 256;
          const py = ((n - la) / (n - s)) * 256;
          i ? lg.lineTo(px, py) : lg.moveTo(px, py);
        });
        lg.closePath();
      }
      lg.fill();
    }
    g.drawImage(layer, 0, 0);
  }
  const blob = await cv.convertToBlob({ type: 'image/png' });
  return { data: new Uint8Array(await blob.arrayBuffer()) };
});

/* ── Map ──────────────────────────────────────────────────────────────────── */

const pm = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', pm.tile);

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
  attributionControl: { customAttribution: (summary && summary.attribution) || '' },
});
window.map = map;
map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'top-right');
$('#backdrop-opacity').value = Math.round((b0.opacity ?? 0.5) * 100);

/* ── Colouring ────────────────────────────────────────────────────────────── */

const THEMES = {
  reach: { colour: ['case', ['!', ['get', 'in_scope']], C.outscope,
      ['get', 'reaches_tidal'], C.reach, C.unreached],
    legend: [['Whether it reaches tidal water', null], ['reaches tidal water', C.reach],
      ['in scope, and does NOT — the work', C.unreached], ['out of scope', C.outscope]] },
  form: { colour: ['match', ['coalesce', ['get', 'form'], 'added'],
      'inlandRiver', C.reach, 'canal', C.canal, 'lake', C.lake, 'tidalRiver', C.tidal, C.add],
    legend: [['Form of water', null], ['inland river', C.reach], ['canal', C.canal],
      ['lake', C.lake], ['tidal river', C.tidal],
      ['added by this project — the same yellow as the Connectors layer, deliberately: '
       + 'they are the same geometry', C.add]] },
  origin: { colour: ['case', ['==', ['get', 'origin'], 'survey'], C.reach, C.add],
    legend: [['Whose geometry it is', null], ["Ordnance Survey's, unmodified", C.reach],
      ['added by this project', C.add]] },
  scope: { colour: ['match', ['coalesce', ['get', 'scope_rule'], 'none'],
      'basin', C.reach, 'country', C.canal, 'neither', C.outscope, C.warn],
    legend: [['Why it is in scope', null], ['its basin is', C.reach],
      ['the country rule', C.canal], ['neither — out of scope', C.outscope]] },
  lake: { colour: ['case', ['!=', ['get', 'form'], 'lake'], '#39414d',
      ['==', ['coalesce', ['get', 'name'], ''], ''], C.warn, C.lake],
    legend: [['Lake links, by whether the survey names them', null], ['named', C.lake],
      ['unnamed', C.warn], ['not a lake', '#39414d'],
      ['`name` is the WELSH form where one exists — the English is in `name_alt`', null]] },
};
let theme = HASH.t && THEMES[HASH.t] ? HASH.t : 'reach';

const WIDTH = ['interpolate', ['linear'], ['zoom'],
  5, ['case', ['get', 'in_scope'], 1.3, 0.7],
  9, ['case', ['get', 'in_scope'], 1.8, 0.9],
  13, ['case', ['get', 'in_scope'], 2.6, 1.3], 17, 5.5];

/* ── Overlays: small enough to be flat files, and needed whole at every zoom ── */

const OVERLAYS = [
  { id: 'connectors', label: 'Connectors — geometry we added', file: 'connectors.geojson',
    kind: 'line', colour: C.add, width: 2.6, count: c.connectors },
  { id: 'reversals', label: 'Reversals — direction changed, geometry untouched',
    file: 'reversals.geojson', kind: 'line', colour: C.rev, width: 2.6, arrows: true,
    count: c.reversals },
  { id: 'retired', label: 'Retired — superseded, kept', file: 'retired.geojson',
    kind: 'line', colour: C.retiredc, width: 2.2, dash: [2, 2], count: c.retired },
  { id: 'dead_ends', label: 'Dead ends that are the work', file: 'dead_ends.geojson',
    kind: 'point', on: true, colour: C.unreached, count: c.dead_ends_defect,
    radius: ['interpolate', ['linear'], ['zoom'],
      5, ['interpolate', ['linear'], ['coalesce', ['get', 'stranded_km'], 0], 0, 2.2, 50, 5, 1200, 11],
      12, ['interpolate', ['linear'], ['coalesce', ['get', 'stranded_km'], 0], 0, 4, 50, 9, 1200, 20]],
    note: 'sized by the length STRANDED above them, not the length draining through — '
      + 'ranking on upstream length puts a cul-de-sac off a working drain first' },
  { id: 'corrections', label: 'Every curated judgement', file: 'corrections.geojson',
    kind: 'point', count: c.corrections,
    colour: ['match', ['get', 'kind'], 'connector', C.add, 'reversal', C.rev,
      'junction', C.warn, '#ffffff'],
    note: 'click one and ask whether a person would have drawn it there' },
  { id: 'refused_crossings', label: 'Refused 0 m crossings', file: 'refused_crossings.geojson',
    kind: 'point',
    colour: ['case', ['get', 'corroborated'], '#5a8fb8', ['get', 'in_trust_country'],
      C.unreached, C.warn],
    legend: [['corroborated — a Trust structure within 150 m', '#5a8fb8'],
      ['NOT corroborated, and in Trust country — the register could have recorded one '
       + 'and did not', C.unreached],
      ['not corroborated, outside Trust country', C.warn]] },
  { id: 'sea_entry', label: 'Sea entries', file: 'sea_entry.geojson', kind: 'point',
    count: c.sea_entries,
    colour: ['case', ['==', ['get', 'kind'], 'blocked'], C.warn, '#5ce1e6'],
    legend: [['a tidal terminus', '#5ce1e6'], ['a blocked mouth', C.warn]] },
  { id: 'tidal', label: 'Tidal termini', file: 'terminus.geojson', kind: 'point',
    count: c.tidal_nodes,
    colour: ['case', ['get', 'is_crawl_seed'], C.tidal, '#4a5568'],
    legend: [['the crawl started here', C.tidal], ['tidal, but not a crawl seed', '#4a5568']] },
  { id: 'seeds', label: 'Seed nodes', file: 'seeds.geojson', kind: 'point',
    colour: C.seed, count: c.seeds },
];
const loaded = new Set();

/* ── The network, from vector tiles ────────────────────────────────────────
 * TWO SOURCE LAYERS, and the second is the whole point. `link` may drop features at
 * low zoom so a tile stays small; `link_kept` may not, because it holds the four
 * classes this map has always promised are drawn whatever their length — the unreached,
 * the retired, the geometry this project added, and anything whose routing was
 * reversed. A defect that vanished when you zoomed out would make the map look tidier
 * and be a lie, and it is the failure the promise exists to prevent.
 */

function arrowImage(fill) {
  const s = 14, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.fillStyle = '#0d1117';
  g.beginPath(); g.arc(s / 2, s / 2, s / 2 - 0.5, 0, Math.PI * 2); g.fill();
  g.fillStyle = fill;
  g.beginPath(); g.moveTo(s * 0.78, s / 2); g.lineTo(s * 0.28, s * 0.22);
  g.lineTo(s * 0.28, s * 0.78); g.closePath(); g.fill();
  return g.getImageData(0, 0, s, s);
}

async function addNetwork() {
  const head = await fetch(DATA + 'rewt.pmtiles', { method: 'HEAD' }).catch(() => null);
  if (!head || !head.ok) {
    problems.push('<code>data/rewt.pmtiles</code> — the network, the sea routes and the '
      + 'basins. Until the release that carries it is built, this map can draw the '
      + 'historic sheets and nothing of its own.');
    return false;
  }
  map.addSource('rewt', { type: 'vector', url: 'pmtiles://' + DATA + 'rewt.pmtiles' });
  for (const [id, src] of [['network-out', 'link'], ['network', 'link'],
                           ['kept-out', 'link_kept'], ['kept', 'link_kept']]) {
    const inScope = id.endsWith('-out') ? ['!', ['get', 'in_scope']] : ['get', 'in_scope'];
    map.addLayer({
      id, type: 'line', source: 'rewt', 'source-layer': src, filter: inScope,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': THEMES[theme].colour, 'line-width': WIDTH,
        ...(id.endsWith('-out') ? { 'line-opacity': 0.5 } : {}) },
    });
  }
  map.addLayer({ id: 'sea_route', type: 'line', source: 'rewt', 'source-layer': 'sea_route',
    layout: { visibility: 'none', 'line-cap': 'round' },
    paint: { 'line-width': 1.6,
      'line-color': ['interpolate', ['linear'], ['coalesce', ['get', 'median_depth_m'], 0],
        0, '#9fe8ff', 10, '#37b6e8', 40, '#1f6fc4', 120, '#123f8a'] } }, 'network-out');
  map.addLayer({ id: 'basins-fill', type: 'fill', source: 'rewt', 'source-layer': 'basin',
    layout: { visibility: 'none' },
    paint: { 'fill-opacity': 0.35, 'fill-color': ['case',
      ['!', ['get', 'in_scope']], '#3a424f',
      ['interpolate', ['linear'], ['coalesce', ['get', 'share'], 0],
        0, '#ff2d55', 0.6, '#ff9f1c', 0.9, '#3b7d3b', 1, '#1b5e20']] } }, 'network-out');
  return true;
}

async function ensure(o) {
  if (loaded.has(o.id)) return;
  loaded.add(o.id);
  const data = await grab(o.file, o.label.toLowerCase());
  if (!data) return;
  map.addSource(o.id, { type: 'geojson', data });
  if (o.kind === 'line') {
    // A casing, so an overlay line never reads as a network line whatever the theme.
    map.addLayer({ id: o.id + '-casing', type: 'line', source: o.id,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0d1117', 'line-width': (o.width || 2) + 2.5,
        'line-opacity': 0.85 } });
    map.addLayer({ id: o.id, type: 'line', source: o.id,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': o.colour, 'line-width': o.width,
        ...(o.dash ? { 'line-dasharray': o.dash } : {}) } });
    if (o.arrows) {
      map.addLayer({ id: o.id + '-arrows', type: 'symbol', source: o.id,
        layout: { 'symbol-placement': 'line', 'icon-image': 'arrow-reversed',
          'icon-size': 0.9, 'icon-allow-overlap': true, 'icon-rotation-alignment': 'map' } });
    }
  } else {
    map.addLayer({ id: o.id, type: 'circle', source: o.id,
      paint: { 'circle-color': o.colour,
        'circle-radius': o.radius ?? ['interpolate', ['linear'], ['zoom'], 5, 2.6, 14, 6],
        'circle-stroke-color': '#0d1117', 'circle-stroke-width': 1, 'circle-opacity': 0.9 } });
  }
  wireClicks(o);
}

function setVisible(o, on) {
  for (const id of [o.id, o.id + '-casing', o.id + '-arrows']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
  }
}

/* ── Panel, legend, backdrops ─────────────────────────────────────────────── */

function buildLayerPanel() {
  const host = $('#layers');
  for (const o of OVERLAYS) {
    const row = document.createElement('label');
    row.className = 'switch';
    /* A layer coloured by its data has no one colour; showing white for it made four
       different layers carry the same blank swatch, which reads as a key and is not
       one. Such a layer gets a band of the colours it actually uses. */
    const hues = typeof o.colour === 'string' ? [o.colour]
      : ((o.colour ? JSON.stringify(o.colour).match(/#[0-9a-fA-F]{6}/g) : null) || ['#8a93a0']);
    const uniq = [...new Set(hues)];
    const sw = uniq.length === 1 ? uniq[0]
      : `linear-gradient(90deg, ${uniq.map((h, n) =>
          `${h} ${Math.round(n * 100 / uniq.length)}% ${Math.round((n + 1) * 100 / uniq.length)}%`).join(', ')})`;
    row.innerHTML = `<input type="checkbox" ${o.on ? 'checked' : ''}>
      <i class="sw ${o.kind === 'point' ? 'dot' : ''}" style="background:${sw}"
         title="${esc(uniq.join(' · '))}"></i>
      <span>${esc(o.label)}</span><em>${o.count != null ? fmt(o.count) : ''}</em>`;
    row.querySelector('input').onchange = async (e) => {
      if (e.target.checked) { await ensure(o); setVisible(o, true); } else setVisible(o, false);
      applyTheme(); writeHash();
    };
    host.append(row);
    if (o.note) {
      const n = document.createElement('p');
      n.className = 'note'; n.style.margin = '0 0 6px 22px'; n.textContent = o.note;
      host.append(n);
    }
  }
  for (const [id, label, colour] of [
    ['sea_route', 'The sea network — routes, a tree not a loop', '#1f6fc4'],
    ['basins-fill', 'Basins, by share reaching the sea', '#3b4a5e']]) {
    const row = document.createElement('label');
    row.className = 'switch';
    row.innerHTML = `<input type="checkbox"><i class="sw" style="background:${colour}"></i>
      <span>${esc(label)}</span><em>${id === 'sea_route' ? fmt(c.sea_routes) : fmt(c.basins)}</em>`;
    row.querySelector('input').onchange = (e) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', e.target.checked ? 'visible' : 'none');
      writeHash();
    };
    host.append(row);
  }
}

function applyTheme() {
  for (const id of ['network', 'network-out', 'kept', 'kept-out']) {
    if (map.getLayer(id)) map.setPaintProperty(id, 'line-color', THEMES[theme].colour);
  }
  const extra = OVERLAYS.filter((o) => o.legend && loaded.has(o.id) && map.getLayer(o.id)
      && map.getLayoutProperty(o.id, 'visibility') !== 'none')
    .flatMap((o) => [[o.label, null], ...o.legend]);
  const rows = [...THEMES[theme].legend];
  if (extra.length) rows.push(['Drawn on top', null], ...extra);
  rows.push(['Never thinned, at any zoom', null],
    ...(thin?.never_thinned || []).map((t) => [t, null]));
  $('#legend').innerHTML = rows.map(([text, colour], i) => colour
    ? `<span><i style="background:${colour}"></i>${esc(text)}</span>`
    : i === 0 ? `<b>${esc(text)}</b>` : `<span class="foot">${esc(text)}</span>`).join('');
}
$('#theme').onchange = (e) => { theme = e.target.value; applyTheme(); writeHash(); };

const sourceFor = (o) => {
  const src = { type: 'raster', tiles: tilesFor(o), tileSize: 256,
    maxzoom: o.max_zoom || 19, attribution: o.attribution };
  if (o.min_zoom) src.minzoom = o.min_zoom;
  if (o.bounds) src.bounds = o.bounds;
  const row = (o.counties || o.collection) ? itemRow(o) : null;
  if (row?.bounds) src.bounds = row.bounds;
  if (row?.zooms) { src.maxzoom = Math.max(...row.zooms); src.minzoom = Math.min(...row.zooms); }
  return src;
};

async function applyBackdrop() {
  const o = opts[backdropId];
  const src = o.counties || o.collection;
  if (src && !items[src]) {
    items[src] = await fetch(src).then((r) => r.json()).catch(() => []);
  }
  if (src) {
    const ctr = map.getCenter();
    const covers = (r) => r.bounds && ctr.lng >= r.bounds[0] && ctr.lng <= r.bounds[2]
      && ctr.lat >= r.bounds[1] && ctr.lat <= r.bounds[3];
    const area = (r) => (r.bounds[2] - r.bounds[0]) * (r.bounds[3] - r.bounds[1]);
    const here = itemsFor(o).filter(covers).sort((a, b) => area(a) - area(b))[0];
    if (HASH.i && !picked.has(src) && itemsFor(o).some((r) => (r.code || r.id) === HASH.i)) {
      chosen[src] = HASH.i; picked.add(src);
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
  $('#county-field').hidden = !src;
  $('#historic-note').hidden = !o.historic;
  $('#backdrop-note').innerHTML = o.note ? esc(o.note) : '';
  $('#backdrop-note').hidden = !o.note;
}
sel.onchange = () => {
  const prev = opts[backdropId];
  const p = prev && (prev.counties || prev.collection);
  if (p) picked.delete(p);
  backdropId = sel.value; applyBackdrop(); writeHash();
};

function buildItemPicker(o) {
  const src = o.counties || o.collection;
  const cs = $('#county');
  $('#county-label').textContent = o.item_label || 'Sheet';
  cs.innerHTML = '';
  for (const r of itemsFor(o)) {
    const id = r.code || r.id;
    const flags = [r.masked === false ? 'unmasked' : null,
      r.in_scope === false ? 'out of scope' : null,
      r.zooms ? `to z${Math.max(...r.zooms)}` : null].filter(Boolean).join(', ');
    cs.append(new Option(`${r.name || id}${r.code ? ` (${r.code})` : ''}${flags ? ` — ${flags}` : ''}`, id));
  }
  cs.value = chosen[src];
  cs.onchange = () => {
    chosen[src] = cs.value; picked.add(src); applyBackdrop(); writeHash();
    const r = itemRow(o);
    if (r?.bounds) map.fitBounds([[r.bounds[0], r.bounds[1]], [r.bounds[2], r.bounds[3]]],
      { padding: 30, maxZoom: 14 });
  };
}
$('#backdrop-opacity').oninput = (e) => {
  if (map.getLayer('backdrop')) map.setPaintProperty('backdrop', 'raster-opacity', Number(e.target.value) / 100);
  writeHash();
};

/* ── Hash, clicks, lists, epochs ──────────────────────────────────────────── */

let hashTimer, hashReady = false;
function writeHash() {
  if (!hashReady) return;
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const ctr = map.getCenter(), o = opts[backdropId];
    const parts = [`${map.getZoom().toFixed(2)}/${ctr.lat.toFixed(5)}/${ctr.lng.toFixed(5)}`];
    if (backdropId !== backdrops.default) parts.push(`b=${backdropId}`);
    const src = o && (o.counties || o.collection);
    if (src && chosen[src]) parts.push(`i=${chosen[src]}`);
    const op = Math.round(Number($('#backdrop-opacity').value));
    if (op !== Math.round((o.opacity ?? 0.5) * 100)) parts.push(`o=${op}`);
    if (theme !== 'reach') parts.push(`t=${theme}`);
    const on = OVERLAYS.filter((x) => map.getLayer(x.id)
      && map.getLayoutProperty(x.id, 'visibility') !== 'none').map((x) => x.id);
    const dflt = OVERLAYS.filter((x) => x.on).map((x) => x.id);
    if (on.join() !== dflt.join()) parts.push(`l=${on.join(',') || '-'}`);
    history.replaceState(null, '', '#' + parts.join('&'));
  }, 250);
}
map.on('moveend', writeHash);

function dl(obj) {
  return '<dl>' + Object.keys(obj).filter((k) => obj[k] != null && obj[k] !== '')
    .map((k) => `<dt>${esc(k)}</dt><dd>${esc(obj[k])}</dd>`).join('') + '</dl>';
}
const popup = (ll, html) => new maplibregl.Popup({ maxWidth: '340px' })
  .setLngLat(ll).setHTML(html).addTo(map);

function wireClicks(o) {
  map.on('mouseenter', o.id, () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', o.id, () => { map.getCanvas().style.cursor = ''; });
  map.on('click', o.id, (e) => {
    const p = { ...e.features[0].properties };
    let head = `<b>${esc(o.label)}</b>`, extra = '';
    if (o.id === 'corrections') {
      extra = `<div class="quote"><b>${p.by_rule
        ? 'JUDGED BY RULE — no person has looked at this place'
        : 'adjudicated at the place'}</b><br>${esc(p.evidence)}</div>`;
      delete p.evidence; delete p.by_rule;
    }
    popup(e.lngLat, head + dl(p) + extra);
  });
}

/* The network's own click detail comes out of the tile — there is no /api/link here. */
function wireNetwork() {
  for (const id of ['network', 'kept']) {
    if (!map.getLayer(id)) continue;
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
    map.on('click', id, (e) => {
      const d = { ...e.features[0].properties };
      const title = d.name
        ? esc(d.name) + (d.name_alt ? ` <span style="color:var(--ink-dim)">/ ${esc(d.name_alt)}</span>` : '')
        : (d.name_alt ? esc(d.name_alt) : '(unnamed)');
      popup(e.lngLat, `<b>${title}</b>` + dl(d));
    });
  }
}

function renderBasins(filter = '') {
  const host = $('#basin-list');
  host.innerHTML = '';
  const f = filter.toLowerCase();
  const rows = ((summary && summary.basins) || [])
    .filter((b) => !f || (b.label || '').toLowerCase().includes(f));
  if (!rows.length) { host.innerHTML = '<li><span class="t">no basin table loaded</span></li>'; return; }
  for (const b of rows.slice(0, 250)) {
    const li = document.createElement('li');
    if (b.share != null && b.share < 0.75) li.className = 'warnrow';
    li.innerHTML = `<span class="t">${esc(b.label || b.basin_id)}${b.has_outlet ? ''
      : ' <span style="color:var(--warn)">· no outlet</span>'}</span>
      <span class="m">${share(b.share)}</span>
      <span class="bar"><i style="width:${(b.share ?? 0) * 100}%"></i></span>
      <span class="cap">${fmt(b.unreached_km, 1)} km stranded of ${fmt(b.km, 0)} km</span>`;
    li.onclick = () => { if (b.lon != null) map.flyTo({ center: [b.lon, b.lat], zoom: 11 }); };
    host.append(li);
  }
}
$('#basin-filter').oninput = (e) => renderBasins(e.target.value);

/* ── Epochs ────────────────────────────────────────────────────────────────
 * The rationale for each date is NOT copied here, not even as an illustration in this
 * comment — an illustrative quotation is still a second copy and drifts the same way
 * while looking harmless because it does not render. `docs/_data/epochs.yml` owns it,
 * Jekyll publishes it as epochs.json, and the temporality page and this control render
 * the same string. A bare year is the one thing this control must never show. */

const DATUM_NOTE = 'The datum, and what you are looking at: the present-day network '
  + 'made traversable. It is NOT an epoch in the series — the dated cross-sections are '
  + 'worked backwards from it. Nothing on this map is dated.';

async function buildEpochs() {
  const host = $('#epoch-steps'), note = $('#epoch-note');
  const table = await fetch('../epochs.json').then((r) => (r.ok ? r.json() : null))
    .then((d) => (d && d.epochs) || null).catch(() => null);
  const link = '<a href="../epochs">Why these dates</a>';
  const datum = `${esc(DATUM_NOTE)} ${link}`;
  const say = (h) => { note.innerHTML = h; };
  say(datum);
  const rows = table || [1086, 1300, 1540, 1600, 1700, 1830, 1900].map((year) => ({ year, why: null }));
  if (!table) say(`The epoch rationales could not be fetched, so these stops carry their
    dates only. They remain unbuilt either way. ${link}`);
  for (const e of [...rows, { year: 'Modern', why: DATUM_NOTE }]) {
    const built = e.year === 'Modern';
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.state = built ? 'built' : 'planned';
    b.innerHTML = `<span class="yr">${esc(e.year)}</span>`;
    b.disabled = !built;
    b.title = built ? DATUM_NOTE : `${e.year} — not built yet.${e.why ? ' ' + e.why : ''}`;
    b.addEventListener('mouseenter', () => say(built ? datum
      : `<b>${esc(e.year)} — not built.</b> ${e.why ? esc(e.why) + ' ' : ''}`
        + 'The selector switches between separately modelled networks; it does not '
        + `animate one, so nothing is interpolated between stops. ${link}`));
    host.append(b);
  }
  host.addEventListener('mouseleave', () => say(datum));
}

$('#copy-link').onclick = async () => {
  writeHash();
  await new Promise((r) => setTimeout(r, 300));
  const el = $('#copied');
  const say = (m) => { el.hidden = false; el.textContent = m; setTimeout(() => { el.hidden = true; }, 4000); };
  try { await navigator.clipboard.writeText(location.href); say('Copied.'); }
  catch (e) { say('The browser refused clipboard access — copy the address bar instead.'); }
};

/* ── Boot ─────────────────────────────────────────────────────────────────── */

map.on('load', async () => {
  map.addImage('arrow-reversed', arrowImage(C.rev));
  COUNTIES = await fetch('counties.json').then((r) => r.json()).catch(() => null);
  await addNetwork();
  wireNetwork();
  buildLayerPanel();
  await applyBackdrop();

  const wanted = HASH.l === undefined ? null : (HASH.l === '-' ? [] : HASH.l.split(','));
  const boxes = [...document.querySelectorAll('#layers .switch')];
  for (const [i, o] of OVERLAYS.entries()) {
    const want = wanted ? wanted.includes(o.id) : !!o.on;
    try {
      if (want) await ensure(o);
      const box = boxes[i]?.querySelector('input');
      if (box) box.checked = want;
      if (loaded.has(o.id)) setVisible(o, want);
    } catch (err) { console.warn(`layer ${o.id} could not be restored:`, err); }
  }
  if (HASH.o !== undefined) {
    $('#backdrop-opacity').value = HASH.o;
    $('#backdrop-opacity').dispatchEvent(new Event('input'));
  }
  $('#theme').value = theme;
  applyTheme();
  renderBasins();
  await buildEpochs();

  $('#thinning').innerHTML = map.getSource('rewt')
    ? 'The network is served as vector tiles and fetched a viewport at a time, so every '
      + 'one of its links is reachable by zooming in. <b>Four classes are drawn at every '
      + 'zoom whatever their length</b>; the legend names them. A channel not drawn here '
      + 'is <em>not</em> a channel that is missing.'
    : 'The network is not loaded — see the notice above.';

  if (problems.length || missing.length) {
    $('#warn').hidden = false;
    $('#warn').innerHTML = '<b>Not everything on this page is loaded.</b><br>'
      + problems.join('<br>')
      + (missing.length ? `<br>Figures absent from summary.json: <code>${missing.map(esc).join('</code>, <code>')}</code>` : '');
  }
  if (HASH.zoom !== undefined) map.jumpTo({ center: [HASH.lon, HASH.lat], zoom: HASH.zoom });
  hashReady = true;
  writeHash();
});
