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
/* MEASURED, NOT CHOSEN BY EYE. Every pair that can share a screen was simulated for
 * protanopia, deuteranopia and tritanopia (Viénot, Brettel & Mollon) and separated with
 * CIEDE2000. The old `form` theme failed badly: canal against tidal river was **dE 2.5**
 * under deuteranopia — at the just-noticeable difference — with river/tidal at 2.7 and
 * river/canal at 4.5, so four of its five colours were one colour for roughly one man in
 * twelve. It is now dE 15 or better on every pair of every theme.
 *
 * The three that moved are canal, lake and tidal river; inland river keeps its blue
 * because it is the dominant class and a river map whose rivers are not blue is a worse
 * map however well it measures.
 *
 * CANAL IS WARM ON PURPOSE, and the reason is not only separation. Once river, tidal and
 * lake are all natural water and all cool, there is nowhere left in the blue-violet
 * family for a fourth — the first attempt put canal at #006699 and it measured well and
 * was nearly invisible on this ground, which only looking caught. A burnt sienna clears
 * the background, clears every other form by dE 25, and says "engineered, not natural"
 * at a glance, which is the actual distinction a reader wants from that class.
 *
 * ONE PAIR MEASURES CLOSE AND IS FINE: canal against the dead-end marks, dE 9.0 under
 * deuteranopia. Canals are lines and dead ends are circles sized by the length stranded
 * above them, so shape and size both separate them.
 *
 * Seeds against tidal river is the same case, dE 9.6, and the seed layer is off by
 * default besides. `tools/palette_audit.py` is the instrument; it lists both exceptions
 * with the channel that carries the distinction instead, and fails on anything new.
 */
const C = {
  reach: '#1b9ce6', canal: '#bb631b', lake: '#c6cce7', tidal: '#66ffcc',
  outscope: '#7f8b9c', unreached: '#ff2d55',
  add: '#ffd21e', rev: '#39e08b', retiredc: '#ff5cf0', seed: '#ffffff', warn: '#ff9f1c',
};

const DATA = 'data/';
const problems = [];

/* THE BANNER IS RE-RENDERED, NOT WRITTEN ONCE. It used to be built at the end of boot
   and never again, so anything that failed AFTER boot — a layer toggled on later, whose
   file had been renamed — pushed to `problems` and appeared nowhere. The layer row said
   "it is named in the warning at the top of this panel" and that sentence was false for
   exactly the case it was written for. Found by tools/viewer/shot.py's `missing` check,
   which asserted the banner named the layer and it did not. */
function showProblems() {
  const el = document.querySelector('#warn');
  if (!el || (!problems.length && !missing.length)) return;
  el.hidden = false;
  el.innerHTML = '<b>Not everything on this page is loaded.</b><br>'
    + problems.join('<br>')
    + (missing.length
      ? `<br>Figures absent from summary.json: <code>${missing.map(esc).join('</code>, <code>')}</code>`
      : '');
}

/* `name` is normally a file in `data/`, which pages.yml fills from the release. A name
   beginning `../` escapes it deliberately, for a layer that is NOT part of the release
   and must not borrow its provenance — see the sightline overlay, which comes from
   docs/router/ and carries its own stamp. Jekyll publishes everything under docs/, so
   the path is live on the deployed site and in a local preview alike. */
async function grab(name, what) {
  try {
    // KEEP the `../`: the browser resolves it against /viewer/, which is the point.
    // Slicing it off made it relative to /viewer/ and asked for /viewer/router/.
    const r = await fetch(name.startsWith('../') ? name : DATA + name);
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

/* A remembered view fills in only what the link did not say. A link is an instruction
   from a person; storage is a convenience for the same person returning. */
function stored() {
  try { return JSON.parse(localStorage.getItem('rewt-viewer/v1') || 'null'); }
  catch (e) { return null; }
}
const SAVED = stored() || {};
for (const k of ['zoom', 'lat', 'lon', 'b', 'o', 't', 'l']) {
  if (HASH[k] === undefined && SAVED[k] !== undefined) {
    HASH[k] = k === 'l' ? (SAVED[k].length ? SAVED[k].join(',') : '-') : SAVED[k];
  }
}

/* keys.json is written by the Pages workflow from a repository secret and is committed
   nowhere. Absent is the normal case, not an error: a local preview has no key, and a
   fork's deployment will not have one either. A 404, a network failure and a malformed
   file all mean the same thing — no keys — and none of them should stop the map. */
const [summary, backdrops, keys, release] = await Promise.all([
  grab('summary.json', 'the headline figures and the basin table'),
  fetch('backdrops.json').then((r) => r.json()),
  fetch('keys.json').then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  /* Written by the Pages workflow, which is the only thing that knows which release the
     data came from. Absent in a local preview, where the stamped version is all there
     is. See the citation box for why the two can differ. */
  fetch(DATA + 'release.json').then((r) => (r.ok ? r.json() : null)).catch(() => null),
]);

/* ── Figures ──────────────────────────────────────────────────────────────── */

const missing = [];
function need(obj, ...names) {
  for (const n of names) if (obj && obj[n] != null) return obj[n];
  missing.push(names[0]);
  return null;
}
const FINDINGS = (summary && summary.findings) || [];
const c = (summary && summary.counts) || {};
const R = (summary && summary.reachability) || {};
const inScopeKm = need(R, 'total_in_scope_km', 'in_scope_km');
const inScopeShare = need(R, 'in_scope_share');

/* THE HEADLINE SAID "REACHES THE SEA" OVER A TIDAL FIGURE, and until the sea network
   joined the routing graph the two were close enough that nobody caught it. They are
   not close now: 93.58% of in-scope length reaches tidal water and 96.26% reaches the
   sea, and the difference is 2,890 km of coastal drainage that discharges at a sea wall
   without ever touching a tidalRiver. The old line called all of that stranded — it
   printed "6,785 km cannot reach the sea" where the true figure for that sentence is
   3,894 km, overstating the work left by three quarters of it.

   `readings_are_nested: false` is stated in the audit's own section, so the data was
   saying this about itself while the panel rounded the two together. The label decides
   which number belongs under it: the sea question gets the sea figure, the tidal
   question is named as the tidal question, and the cell between them is printed rather
   than folded into either. Where the audit has no sea section — an older release — the
   panel falls back to the tidal reading AND relabels itself, because a stale number
   under a confident label is the failure being fixed. */
const SEA = (summary && summary.reachability_tested_against_the_sea) || {};
const haveSea = SEA.reaches_the_sea_share != null;
$('#f-share').textContent = pct(haveSea ? SEA.reaches_the_sea_share : inScopeShare);
$('#f-share-label').textContent = haveSea
  ? 'of in-scope length reaches the sea'
  : 'of in-scope length reaches tidal water — this build does not test the sea';
$('#f-defects').textContent = fmt(c.dead_ends_defect);
$('#f-detail').innerHTML = summary ? `
  ${fmt(inScopeKm)} km in scope, of which
  <b>${fmt(haveSea ? SEA.reaches_neither_km
    : (inScopeKm == null || inScopeShare == null ? null : inScopeKm * (1 - inScopeShare)))} km
  reaches neither tidal water nor the sea</b>.
  ${haveSea ? `<br><b>${fmt(SEA.reaches_sea_only_km)} km reaches the SEA ONLY</b> —
  coastal drainage with no tidal link, which the tidal reading alone counts as stranded;
  ${fmt(SEA.reaches_tidal_only_km)} km reaches tidal water the sea cannot take. The two
  readings are not nested.` : ''}<br>
  ${fmt(c.links)} links · ${fmt(c.nodes)} nodes · ${fmt(c.basins)} basins ·
  ${fmt(c.corrections)} curated judgements · ${fmt(c.retired)} retired.`
  : 'The figures could not be loaded.';
if (summary && summary.provenance) {
  $('#built').innerHTML = `Built ${esc((summary.provenance.built_at || '').slice(0, 16)
    .replace('T', ' '))}, fingerprint <code>${esc(summary.provenance.config_fingerprint)}</code>.`;
}
/* The attribution used to have a block of its own in the side panel. It is now the
   map's own attribution control, open rather than compact, and repeated in the
   "How to read this map" box — so there is nothing here to fill, and the line that
   tried threw on a null and stopped the whole boot before the network was fetched. */

/* ── Backdrops ────────────────────────────────────────────────────────────── */

const opts = backdrops.options;
const thin = backdrops.thinning;
/* A LAYER WHOSE KEY IS ABSENT IS NOT OFFERED, rather than being offered and failing.
   An entry that can only ever draw blank tiles is worse than no entry: it reads as a
   broken map instead of as an unconfigured one, and it invites someone to "fix" it by
   committing a credential. See `_no_keys` in backdrops.json.

   THIS HIDES THE HISTORIC LAYERS FROM A PREVIEW THAT HAS NO KEY — which is not the
   same as "from every local preview", as this comment said until 3 September. The
   deploy writes `keys.json`, and a machine that has ever run that workflow, or has
   copied the file, HAS one: `docs/viewer/keys.json` is gitignored, not absent. On such
   a machine the ten keyed layers ARE offered locally, the key is restricted by Allowed
   HTTP Origins to https://docuracy.github.io, and every tile 403s — so the layer draws
   blank, silently, which is precisely the failure the paragraph above says this test
   prevents. The test is right; the claim about its reach was a snapshot of a machine
   that happened not to have the file.

   So the gate stays, and `wireTileErrors` below covers the case the gate cannot: an
   offered layer whose tiles do not arrive says so on the page. Two mechanisms, because
   "not offered" and "offered and failing" are different states and only the first can
   be decided before a tile is requested. */
const usable = Object.entries(opts).filter(([, o]) => !o.requires_key || keys[o.requires_key]);
const sel = $('#backdrop');
const GROUPS = [
  ['modern', 'Modern'],
  ['seamless', 'Historic — seamless, Great Britain'],
  ['regional', 'Historic — one place only'],
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
/* `usable`, not `opts`: a link shared from the deployed site can name a keyed backdrop,
   and opening it where no key is configured would select an entry that is not in the
   dropdown and cannot draw. It falls back to the default instead, silently, because the
   reader did nothing wrong and the rest of the link — the view, the layers — is good. */
const offered = new Map(usable);
let backdropId = offered.has(backdrops.default) ? backdrops.default : usable[0][0];
if (HASH.b && offered.has(HASH.b)) backdropId = HASH.b;
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
  /* Substituted here and nowhere else, so there is one place a credential enters a URL.
     `usable` has already dropped every entry whose key is missing, so this cannot
     produce the literal string "{key}" in a request. */
  if (o.requires_key) t = t.replace('{key}', encodeURIComponent(keys[o.requires_key]));
  return [t];
};

/* THE HISTORIC BACKDROPS COME THROUGH THE LIBRARY'S OWN API, not from its tile bucket,
 * and the difference is the whole of it. NLS ask that the georeferenced S3 layers be
 * re-used "within a desktop or local environment" and that a public website use their
 * Historic Maps API or write to them. This site is public, so the 68 S3 layers went and
 * the eight API layers — the sanctioned route, delivered through MapTiler under this
 * project's own account — are what is offered instead.
 *
 * REMOVING THE S3 LAYERS WAS NOT ENOUGH, and that is the part worth remembering.
 * `composite.js` held the base URL of the six-inch bucket and `counties.json`
 * enumerated the 53 slugs that complete it, so the two of them together were still a
 * published index to those layers — with a working fetcher attached — after every one
 * had gone from `backdrops.json`. Separately each looked harmless, which is why it
 * survived the first pass. Both now live in `tools/viewer/`, gitignored, which is the
 * desktop environment the Library's sentence describes. Found by rewt-86.
 *
 * The backdrop machinery below still understands `counties` and `collection` options.
 * It is kept because it is generic and a future keyless mosaic would use it, not
 * because anything in this build does.
 */

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
      maxzoom: b0.max_zoom || 19, ...(b0.min_zoom ? { minzoom: b0.min_zoom } : {}),
      attribution: b0.attribution } } : {},
    layers: [
      { id: 'ground', type: 'background', paint: { 'background-color': '#0d1117' } },
      ...(b0.tiles ? [{ id: 'backdrop', type: 'raster', source: 'backdrop',
        paint: { 'raster-opacity': b0.opacity ?? 0.5 } }] : []),
    ],
  },
  center: [HASH.lon ?? -2.2, HASH.lat ?? 52.7],
  zoom: HASH.zoom ?? 5.7,
  maxZoom: 18,
  // The page footer used to carry a banner of licence text across the bottom, over the
  // legend. It belongs in the map's own attribution control, which is what that control
  // is for, and it opens rather than starting collapsed because an attribution nobody
  // can see is not an attribution. Added below rather than here, so it can be given a
  // corner: MapLibre puts it bottom-right by default, which is the legend's corner, and
  // moving the banner from over the legend to over the legend would fix nothing.
  attributionControl: false,
});
window.map = map;
map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'top-right');
/* COMPACT, AND OPENED — not `compact: false`, which is a different thing that looks
   the same on a wide screen. `compact: false` renders the text permanently with no
   button, so a reader who has read it once can never put it away; `compact: true`
   gives the ⓘ button and starts collapsed. What is wanted is the button AND the text
   showing, which is the state MapLibre's own toggle produces, so it is set by adding
   the class its toggle adds rather than by faking the appearance. */
/* One breakpoint, in the stylesheet, read here rather than restated — a width typed
   in both places is two copies of one decision. */
const NARROW = matchMedia('(max-width: 720px)');

const attrib = new maplibregl.AttributionControl({ compact: true,
  customAttribution: (summary && summary.attribution) || '' });
map.addControl(attrib, 'bottom-left');
/* OPEN ON A WIDE SCREEN, THE BUTTON ON A NARROW ONE. Forcing it open is right where
   there is room — an attribution nobody can see is not an attribution — and wrong where
   there is not: at 375 px the open control had no width to lay out in and rendered as a
   vertical ribbon of single words down the left edge of the map, one per line, over the
   country. Unreadable AND obscuring, which is the worst of both. The credit is still
   present and one tap away as MapLibre's own ⓘ, which is what that button is for.
   Re-evaluated on rotation rather than at boot, because a tablet turned sideways
   crosses the breakpoint without reloading. Found in a screenshot: the measurements
   said the map had gone from 15 px to 375 px and said nothing about what was on it. */
const openAttribution = () => {
  const el = document.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact');
  if (el) el.classList.toggle('maplibregl-compact-show', !NARROW.matches);
};
map.once('load', openAttribution);
NARROW.addEventListener('change', openAttribution);
$('#backdrop-opacity').value = Math.round((b0.opacity ?? 0.5) * 100);

/* ── Colouring ────────────────────────────────────────────────────────────── */

const THEMES = {
  reach: { colour: ['case', ['!', ['get', 'in_scope']], C.outscope,
      ['get', 'reaches_tidal'], C.reach, C.unreached],
    legend: [['Whether it reaches tidal water', null], ['reaches tidal water', C.reach],
      ['in scope, and does NOT — the work', C.unreached], ['out of scope', C.outscope]] },
  /* THE TWO QUESTIONS ARE NOT NESTED, which is why this is a cross-tabulation and not a
     second shade on the reach theme. A mouth discharging through a sea wall reaches the
     SEA without ever touching a tidalRiver, so "reaches tidal water" and "reaches the
     sea" each have cases the other has not. Collapsing them into one "gets there"
     colour would hide the cell that is new — 2,890 km of coastal drainage that was
     stranded until the sea network joined the routing graph, and that the reach theme
     above still paints as a defect because it can only ask the tidal question.
     Offered only when the tiles actually carry `reaches_sea`; see `link_columns()`. */
  seareach: { needs: 'reaches_sea',
    colour: ['case', ['!', ['get', 'in_scope']], C.outscope,
      ['all', ['get', 'reaches_tidal'], ['get', 'reaches_sea']], C.reach,
      ['get', 'reaches_tidal'], C.tidal,
      ['get', 'reaches_sea'], C.lake,
      C.unreached],
    legend: [['Tidal water and the sea, cross-tabulated', null],
      ['both — tidal water AND the sea', C.reach],
      ['tidal water only — the sea cannot take it', C.tidal],
      ['THE SEA ONLY — coastal drainage with no tidal link', C.lake],
      ['neither — the work that is left', C.unreached],
      ['out of scope', C.outscope],
      ['"reaches the sea" is not a stronger form of "reaches tidal water": each has '
       + 'cases the other has not, which is why this is a table and not a scale', null]] },
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
/* A theme whose property the tiles do not carry would paint every link the same colour
   and look like a bug in the data rather than an absence in the build. Dropped from the
   control instead, and from the URL, so an old link naming it falls back rather than
   showing a flat map. `themeAvailable` is filled in once the source has loaded. */
const themeNeeds = (id) => THEMES[id] && THEMES[id].needs;
let themeReady = null;
/* null means NOT YET ASKED, and that is not the same as "the property is absent" —
   treating them alike is what removed a working theme. Unknown offers the theme; only a
   metadata read that succeeded and did not list the property takes it away. */
const themeUsable = (id) => !themeNeeds(id) || themeReady === null
  || themeReady.has(themeNeeds(id));
let theme = HASH.t && THEMES[HASH.t] ? HASH.t : 'reach';

const WIDTH = ['interpolate', ['linear'], ['zoom'],
  5, ['case', ['get', 'in_scope'], 1.3, 0.7],
  9, ['case', ['get', 'in_scope'], 1.8, 0.9],
  13, ['case', ['get', 'in_scope'], 2.6, 1.3], 17, 5.5];

/* ── Overlays: small enough to be flat files, and needed whole at every zoom ── */

/* ── PATTERN IS THE PRIMARY CHANNEL FOR PROVENANCE, HUE IS THE REDUNDANT ONE ────
 * Measured on this palette rather than asserted. Simulating protanopia, deuteranopia
 * and tritanopia and computing CIEDE2000 between every pair that can share a screen:
 * the default `reach` theme is clean (no pair under dE 15), but `form` collapses —
 * canal against tidal river is **dE 2.5** under deuteranopia, which is at the
 * just-noticeable difference, and river/tidal and river/canal are 2.7 and 4.5. Four of
 * its five colours become one colour for roughly one man in twelve.
 *
 * AND IT CANNOT BE FIXED BY CHOOSING BETTER COLOURS. Of a 2,149-colour pool, ZERO clear
 * both the fixed form colours and all five hues that already carry meaning here
 * (unreached, warn, reversals, retired, out of scope) at dE > 20 under all four vision
 * types; the constraint only becomes satisfiable at dE > 12, which is too weak for a
 * 2-pixel line. The map has simply run out of hue: seven meanings were already in it.
 *
 * So each provenance overlay is identifiable by PATTERN ALONE — dashed for geometry we
 * added, solid-with-arrows for a reversal, fine-dashed-and-offset for a retirement —
 * and keeps its hue as a second, redundant signal. Nobody who sees colour loses
 * anything; everybody who does not gets the distinction back. Pattern also survives a
 * projector and daylight, which is the same argument without the accessibility framing.
 * Raised by rewt-d3.
 */

const OVERLAYS = [
  /* Dashed because it is INFERRED GEOMETRY. No surveyor drew this line: the project put
     it there to close a gap, and a broken line is the conventional way to say so. That
     the dash also separates it from the solid network under any colour vision is the
     second reason, not the first. */
  { id: 'connectors', label: 'Connectors — geometry we added', file: 'connectors.geojson',
    kind: 'line', colour: C.add, width: 2.6, dash: [3, 1.6], count: c.connectors,
    legend: [['dashed — no surveyor drew it; this project inferred it', C.add, 'dash']] },
  /* Solid, and the ARROWS are its pattern — the only overlay whose finding is about
     direction, so the channel that carries it should show direction. A dash here would
     be a second signal for a distinction the arrows already make, which is noise rather
     than redundancy. */
  { id: 'reversals', label: 'Reversals — direction changed, geometry untouched',
    file: 'reversals.geojson', kind: 'line', colour: C.rev, width: 2.6, arrows: true,
    count: c.reversals,
    legend: [['solid, with arrows — the geometry is the survey’s, the direction is ours',
              C.rev]] },
  /* DRAWN BESIDE ITS REPLACEMENT, NOT ON TOP OF IT. Every one of these retirements is
     the same operation: OS Open Rivers carries no node partway along a link, so to
     attach a connector the link is cut, the original retired and two children created —
     674 originals became 1,446 children. Drawn without an offset, a retired link lies
     exactly over the two lines that replaced it, and reads as a mysterious third
     channel that a connector joins for no reason. Stephen could not work out what he
     was looking at, and he knows what the layer is for. The offset puts the old line
     alongside the new so the relation is visible instead of hidden. Found by rewt-d3. */
  { id: 'retired', label: 'Retired — superseded, kept', file: 'retired.geojson',
    kind: 'line', colour: C.retiredc, width: 2.2, dash: [2, 2], offset: 9,
    count: c.retired,
    legend: [['dashed, and set to one side — the superseded geometry', C.retiredc, 'dash']],
    note: 'every one of these was cut in two so that a connector could attach at the '
      + 'cut. The dashed line is the ORIGINAL, drawn offset to one side; the two lines '
      + 'that replaced it are in the network beneath it. Nothing is duplicated in the '
      + 'routing — only the children are in the graph.' },
  { id: 'dead_ends', label: 'Dead ends that are the work', file: 'dead_ends.geojson',
    kind: 'point', on: true, colour: C.unreached, count: c.dead_ends_defect,
    radius: ['interpolate', ['linear'], ['zoom'],
      5, ['interpolate', ['linear'], ['coalesce', ['get', 'stranded_km'], 0], 0, 2.2, 50, 5, 1200, 11],
      12, ['interpolate', ['linear'], ['coalesce', ['get', 'stranded_km'], 0], 0, 4, 50, 9, 1200, 20]],
    note: 'sized by the length STRANDED above them, not the length draining through — '
      + 'ranking on upstream length puts a cul-de-sac off a working drain first' },
  { id: 'corrections', label: 'Every curated judgement', file: 'corrections.geojson',
    kind: 'point', mixed: true, count: c.corrections,
    colour: ['match', ['get', 'kind'], 'connector', C.add, 'reversal', C.rev,
      'junction', C.warn, '#ffffff'],
    note: 'click one and ask whether a person would have drawn it there' },
  /* WHERE TWO WATERCOURSES CROSS AND DO NOT JOIN — an aqueduct or a culvert, one
     carried over or under the other. Drawn as a crossing glyph rather than a circle,
     because it is the one layer here that describes a RELATIONSHIP between two channels
     rather than a property of one, and a dot says nothing about that. */
  { id: 'refused_crossings', label: 'Crossings that do not join — aqueducts and culverts',
    file: 'refused_crossings.geojson', kind: 'symbol', on: true,
    icon: ['case', ['get', 'corroborated'], 'crossing-corroborated',
      ['get', 'in_trust_country'], 'crossing-untrusted', 'crossing-outside'],
    colour: ['case', ['get', 'corroborated'], '#5a8fb8', ['get', 'in_trust_country'],
      C.unreached, C.warn],
    legend: [['corroborated — a Trust structure within 150 m', '#5a8fb8'],
      ['NOT corroborated, and in Trust country — the register could have recorded one '
       + 'and did not', C.unreached],
      ['not corroborated, outside Trust country', C.warn]] },
  /* Not GeoJSON overlays — these two live in the tiles — but they are toggles like the
     rest and belong in the same list, so that one mechanism handles the panel, the
     legend, the URL and what is remembered. They were special-cased before and that is
     why they could not be defaulted on or persisted. */
  { id: 'sea_route', label: 'The sea network — routes, a tree not a loop', tiled: true,
    on: true, swatch: '#1f6fc4', count: c.sea_routes,
    legend: [['shallow — under 10 m', '#9fe8ff'], ['about 40 m', '#1f6fc4'],
             ['deep — 120 m and over', '#123f8a']] },
  { id: 'basins-fill', label: 'Basins, by share reaching the sea', tiled: true,
    on: true, swatch: '#ff9f1c', count: c.basins, also: ['basins-line'],
    legend: [['none of it reaches the sea — the network’s own red', C.unreached],
             ['about three quarters', '#ffb03b'],
             ['nearly all — 95%', '#ffe066'],
             ['all but a fraction — 99%', '#86c8e8'],
             ['all of it, exactly — the network’s own blue', C.reach],
             ['grey — out of scope, or no watercourse in it at all', '#39414d']] },
  /* ── THE TWO HALVES OF ONE DECISION, and they must be drawn as a pair ───────
     62 connectors climb more than 2 m on the unconditioned terrain, which would route
     water uphill. 46 are refused for it. 16 are APPLIED DESPITE IT, because a lock, a
     culvert or a weir in the Trust's register sits within 150 m and a surveyed
     structure outranks a 50 m terrain model — the same rule that already lets a
     person's judgement outrank it, extended to something that was measured rather than
     remembered.

     Drawing the refusals alone would say the veto refused every climbing connector and
     kept none, which is a stronger and more wrong claim than showing neither, so the
     viewer held both back until the release carried the 16. They are deliberately NOT
     the same colour: a red mark on both sets would make a reader assume the opposite of
     what happened to half of them. Refusals read as defects; reinstatements read as
     judgements, in the same yellow as every other curated decision. Raised by rewt-d3. */
  { id: 'refused_connectors', kind: 'point', file: 'refused_connectors.geojson',
    label: 'Connectors refused — they would run uphill', colour: C.unreached,
    radius: ['interpolate', ['linear'], ['zoom'], 5, 3, 14, 7],
    legend: [['refused — the terrain says this would run uphill', C.unreached]],
    note: 'the terrain says the water at the far end is ABOVE this channel, so joining '
      + 'them would invent a flow that runs uphill. Left as a dead end, which the audit '
      + 'reports with the length behind it.' },
  { id: 'reinstated_connectors', kind: 'point', findings: 'connector_climbs',
    label: 'Connectors applied despite climbing — a structure vouches for them',
    colour: C.add, radius: ['interpolate', ['linear'], ['zoom'], 5, 3.4, 14, 8],
    legend: [['applied on a surveyed structure’s warrant, not on the terrain', C.add]],
    note: 'these climb too, and were applied anyway because a lock, culvert or weir in '
      + 'the Canal & River Trust register is within 150 m. Evidence somebody measured '
      + 'outranks a 50 m terrain model. Each one is a place you can disagree with.' },
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
  /* ── WHERE LAND CAN THEORETICALLY BE SEEN FROM THE SEA ──────────────────────
     Built by rewt-c7 for the coastal cost surface (rules/H3.md), and the first layer
     on this map that comes from OUTSIDE the release. It is not derived from the REWT
     build at all — EMODnet's land side on an H3 grid — so it would be wrong to give it
     the release's fingerprint, which is why it loads from docs/router/ and prints its
     own stamp in the note below rather than inheriting the panel's.

     THREE STATES, AND THE THIRD IS THE ONE THAT MATTERS. The cached bathymetry stops
     at longitude -8, so a cell out there computes as "no land visible" when the truth
     is "not knowable" — the land that would have been seen lies outside the data. That
     is D-077 in a picture: the blank sea is the invisible fault and it looks exactly
     like an answer. rewt-c7 first offered the extent rectangle for this, but the
     rectangle marks where the DATA is and the ANSWER is unknowable for a wide band
     inside it; 6,735 of the 7,748 negatives, 87%, are unanswerable rather than
     negative. So it is a per-cell `known` flag and the unknown gets a colour of its
     own. When the cache is extended westward that band shrinks and the map visibly
     gains an answer, which is the right thing for it to do.

     Drawn at all, rather than waited for, BECAUSE the third state will move: a layer
     that arrives after the extension shows a confident zone with no history, and one
     that arrives now shows a reader where the edge of knowledge was. */
  /* ── THE ROUTING GRAPH, WHICH IS THE OTHER VIEW OF THE SAME WATER ───────────
     Stephen asked for a control that switches the sea cells to the actual routing
     edges between cell centres — the graph rather than the tiling. So these two are
     EXCLUSIVE: turning one on turns the other off, because a hexagon and the line
     between two hexagon centres drawn together are a mess that answers neither
     question, and the point of the switch is to see the same water two ways.

     WHAT IS DRAWN IS NOT WHAT IS ROUTED, TWICE OVER, and rewt-c7 put both sentences in
     the file rather than leaving me to write them: an edge is an ADJACENCY and not a
     track, and these links are the res-7 graph aggregated to the res 6 of the cells,
     so the drawn centres are ones no route uses. Separately each is a caveat; together
     they say this is a schematic of a graph. They print first, above the rest.

     `crosses_band` IS 59 OF 49,080 — 0.12%, and it is the interesting feature: the
     seam where two resolutions meet, which is what shows the banding is actually
     joined rather than seven disconnected sheets each locally perfect. rewt-c7 first
     told me 321; the file says 59, because several res-7 edges collapse into one drawn
     link. Reading it from the file rather than taking the number is what saved it, and
     `crossing_a_band_before_aggregation` holds the 321 so neither is lost. At that
     density a line is a hair, so the seams get marks of their own and their own
     toggle. */
  { id: 'edges', label: 'The routing graph — links between cell centres',
    file: '../router/data/edges.geojson', kind: 'line', exclusive: 'router', family: 'lines',
    width: ['interpolate', ['linear'], ['zoom'], 5, 0.4, 9, 0.8, 14, 1.6],
    colour: '#7ad6ff', on: false,
    legend: [['a link between two adjacent cell centres — an adjacency, not a track',
              '#7ad6ff']],
    note: 'the graph a route is measured on. Click a link for the cells it joins.' },
  /* NOT IN THE EXCLUSIVE GROUP. The seams are an overlay ON the graph, not an
     alternative to it — and putting them in the group made turning them on turn the
     graph off, so the check reported "the graph drew 0 links" and was right. The group
     is for the two views of the same water, the tiling and the lattice; a marker layer
     that annotates one of them is a third thing. */
  { id: 'edges-seam', label: 'Seams — links where two cell resolutions meet',
    /* THE GRAPH'S OWN SOURCE, not a second fetch of the same 11 MB. Two overlays
       pointing at one file meant two sources, two parses and two copies in memory of
       49,080 links — and, worse, two chances for the seams and the graph to be
       describing different data if the file changed between the fetches. `sourceOf`
       says: draw from that layer's source, and load it first if it is not there. */
    sourceOf: 'edges', kind: 'centre-mark',
    filter: ['get', 'crosses_band'], colour: C.add, on: false,
    radius: ['interpolate', ['linear'], ['zoom'], 5, 2.6, 12, 6],
    legend: [['a seam: the two cells sit at different resolutions', C.add]],
    note: 'the banding is only a grid if these join it. A count cannot show that and a '
      + 'picture can.' },
  /* ── WHERE THE RIVERS MEET THE SEA GRID ─────────────────────────────────────
     rewt-c7's joins: 389 attachments from a tidal terminus to the routing grid. MIXED
     GEOMETRY BY DESIGN, and the design is the argument — rules 1 and 2 are a LINE from
     the terminus to the cell centre, because a direct attachment is being ASSERTED and
     the line is the assertion; rule 3 is a POINT, because no straight connection is
     claimed and a line there would draw a route nobody computed. 44 / 115 / 230.

     So the LINES are what the grid knows and the POINTS are what it does not, and they
     are coloured accordingly rather than as one layer with two shapes in it. 230 of 389
     — the majority — are the inference case, which is the honest direction and is why
     the traces beside them must not look more settled than these do.

     This is the file that would have been drawn as a line layer and quietly lost its
     230 points: rewt-c7's own check page did exactly that and Stephen read the absence
     as missing joins on the Crouch. `mixed: true` draws both. */
  /* ── THE COAST AT THE GRID'S OWN RESOLUTION ─────────────────────────────────
     The res-6 layers above are an AGGREGATION: rewt-c7's routing graph is res 7, and
     the drawn centres there are ones no route uses. These two are the lattice itself,
     unaggregated, for every routing cell within 5 km of land — so here a link really
     does join two cell centres and nothing is a schematic.

     ITS EXTENT DELIBERATELY DOES NOT MATCH THE SIGHTLINE CELLS, and that is the point.
     I asked rewt-c7 this morning for two layers covering the same ground, because a
     toggle whose halves differ is a bug the eye finds in a second. They clipped 4,504
     perimeter cells away to give me it — and that clip is what cost 1,752 sea entries
     when I measured coverage against the published layer. Measured against the real
     res-7 grid the shortfall is much smaller: 83% of entries are within two rings, not
     58% in a cell. So the requirement was mine and it was wrong. A visible mismatch
     that is explained beats a tidy picture that has quietly lost the estuaries, and
     `extent_deliberately_differs` in the file says so on the page.

     AND IT HAS 32 COMPONENTS, WHICH IS NOT A DEFECT — do not "fix" it. A 5 km strip
     around separate landmasses IS separate; the water between them is further from land
     than the band is wide. Connectivity is a property of the graph, which is one
     component of 143,879, not of this window onto it. rewt-c7 put that sentence in the
     properties so it prints without my restating it, which is the whole discipline. */
  { id: 'coast-cells', label: 'Routing cells near the coast — the grid unaggregated',
    file: '../router/data/cells_r7_coast.geojson', kind: 'polygon', exclusive: 'router', family: 'cells',
    colour: '#2a6f8f', opacity: 0.3,
    legend: [['a routing cell within 5 km of land, at the resolution routes use',
              '#2a6f8f']],
    note: 'the band is 5 km because that is where the curve flattens — see below.' },
  { id: 'coast-edges', label: 'The routing lattice near the coast — real links',
    file: '../router/data/edges_r7_coast.geojson', kind: 'line', exclusive: 'router', family: 'lines',
    colour: '#9fe8ff', width: ['interpolate', ['linear'], ['zoom'], 5, 0.3, 9, 0.7, 14, 1.5],
    legend: [['a link between two adjacent routing cells — unaggregated, so this one '
              + 'is a link a route can actually use', '#9fe8ff']],
    note: 'turn the aggregated graph on beside it — both are lines, so they draw '
        + 'together — and the difference is what the aggregation costs.' },
  { id: 'joins', label: 'River mouths joined to the sea grid',
    file: '../router/data/joins.geojson', kind: 'point', mixed: true,
    colour: ['case', ['==', ['get', 'rule'], 3], C.warn, C.add],
    width: 1.6,
    radius: ['interpolate', ['linear'], ['zoom'], 5, 2.2, 12, 5],
    legend: [['a line — the grid reaches this terminus directly (rules 1 and 2)', C.add],
             ['a mark — no direct attachment is claimed; the way is the trace stage\u2019s '
              + 'to find (rule 3)', C.warn]],
    note: 'click one for the rule that placed it and how far it reached.' },
  /* THE PATHS FOUND FOR THE TERMINI THE GRID COULD NOT REACH DIRECTLY, and rewt-c7 has
     put `provisional` in the file: "R-01 unbuilt; this population will move twice."
     Dashed for the same reason the connectors are dashed — no surveyor drew this line
     and no vessel sailed it; it is a route inferred over a cost surface. */
  { id: 'traces', label: 'Traced ways out — provisional',
    file: '../router/data/traces.geojson', kind: 'line', colour: C.rev, width: 1.4,
    dash: [2, 2],
    legend: [['a traced path from a stranded terminus to the grid — inferred, not '
              + 'surveyed and not sailed', C.rev]],
    note: 'these move when R-01 lands. Click one for what it crossed.' },
  /* THE TERMINI WITH NO WAY TO THE SEA. Stephen expects the sea grid, the joins, the
     traces and the inland network to be ONE D8 network. rewt-c7 built all four into one
     graph and counted rather than answering from the design: 81.72% of in-scope river
     nodes reach the sea, 4,103 components, and thirty river mouths attached to nothing.
     The answer to "is it one network" is "not yet", and this layer is the part of the
     shortfall that can be pointed at.

     THE THIRTY IDS ARE NOT WRITTEN HERE. They are read from `network_summary.json` at
     load time and turned into a filter, because a list of another session's node ids
     copied into my file is frozen the moment they re-run — which is exactly how the
     horizon constant came to be wrong in three places. The stranded population moves
     when R-01 lands; rewt-c7 says so in `provisional` and the page prints it.

     It draws from the JOINS source, not a file of its own: every stranded terminus is
     already a join, so a second copy of the same geometry could disagree with the
     first. `sourceOf` exists for exactly that reason. */
  { id: 'stranded', label: 'River mouths with no way to the sea', sourceOf: 'joins',
    kind: 'stranded-mark', summary: '../router/data/network_summary.json',
    colour: C.warn,
    legend: [['a terminus the combined network cannot reach the sea from — its rule-3 '
              + 'trace failed', C.warn]],
    note: 'the count and the definition behind it are the file\u2019s own, below.' },
  { id: 'sightline', label: 'Where land can be seen from the sea', exclusive: 'router',
    family: 'cells',
    file: '../router/data/sightline2_r6.geojson', kind: 'polygon',
    /* NO `count` HERE. It was 15,861, typed from a message, and it was wrong within a
       day — wrong file and wrong number at once. The count is a property of rewt-c7's
       file and had no business living in mine; `ensure` now takes it from what actually
       loaded, so it cannot be stale and cannot disagree with what is drawn. */
    /* COLOURED BY WHAT HOLDS THE WATER IN SIGHT, because every cell in this file is in
       sight — the unknown and out-of-sight states are gone by construction, trimmed
       away rather than painted (H3-002 §3). One state is not a map. What varies, and
       what a reader is actually asking, is WHICH LAND: a thin fringe held by a 100 m
       hill is a different proposition from water held by a mountain 130 km off.

       Not the hot ramp the obvious instinct reaches for: red on this map is the alarm
       colour and means in scope and not reaching tidal water. Water held by a mountain
       is not a defect. So the ramp stays in the water family, pale for a low hill and
       deep for a summit, and borrows nothing that already means something else. */
    /* THREE CASES, AND THE ORDER IS THE ARGUMENT. Not knowable first, because it is
       not an answer; then out of sight, which is; then the ramp, which only means
       anything for a cell that can see something.

       This was a two-case expression for about an hour, written when the file held
       14,991 cells that were all in sight. rewt-c7 rebuilt it to 27,130 with the
       out-of-sight and not-knowable states back, and `coalesce(gov_h_m, 0)` then
       painted every out-of-sight cell the palest end of the ramp — reading as water
       held by a very low hill, which is the opposite of what it is. A ramp over a
       property that is null for 11,322 of 27,130 cells needs a case above it, not a
       default inside it. Caught by tools/viewer/shot.py within the hour. */
    colour: ['case',
      ['==', ['get', 'known'], false], C.warn,
      ['!', ['get', 'visible']], '#39414d',
      ['interpolate', ['linear'], ['coalesce', ['get', 'gov_h_m'], 0],
        0, '#cfeffb', 100, '#9fe8ff', 300, '#37b6e8', 700, '#1f6fc4', 1200, '#123f8a']],
    opacity: 0.34,
    /* HEIGHTS ONLY, NO RANGES. These read "about 38 km", "about 66", "about 100",
       "about 131" until now — correct, because I computed them from rewt-c7's 3.7945,
       and typed, so they would have gone silently wrong the moment the refraction
       constant moved. It has already moved once in the prose that describes it (3.86
       against 3.7945, which is where the 12.2 km masthead figure came from). A legend
       that restates a derived number is a second rendering of one fact, which is the
       thing this file has been losing to all day. The height is what the colour means;
       the range follows from it by the formula printed under the layer, and the popup
       computes it per cell from the file's own constant. */
    legend: [['held by a hill under 100 m', '#9fe8ff'],
             ['held by 300 m', '#37b6e8'],
             ['held by 700 m', '#1f6fc4'],
             ['held by 1,200 m and over', '#123f8a'],
             ['no land in sight, and that IS the answer', '#39414d'],
             ['NOT KNOWN — the land that would be visible lies outside the data, so '
              + 'this is not a negative', C.warn],
             /* THIS LINE USED TO PARAPHRASE THE FILE AND WENT BACKWARDS WITHIN A DAY.
                It read "the EDGE of this layer is a ROUTING decision, not a horizon and
                not a coast", which was true while the blind-sailing buffer was 56.4 km.
                Stephen then ruled the buffer to zero, so the edge became the limit of
                sight exactly — and my sentence asserted the opposite, in the legend, on
                the deployed map. The file's own `buffer_basis` had already inverted with
                it, and the stamp under this layer prints that sentence rather than
                restating it, so the panel was right while the legend was wrong.

                A number that moves is caught by a diff. A sentence that REVERSES is
                caught only where the thing quoting it quotes rather than paraphrases,
                because a paraphrase that was accurate when written reads exactly like
                one that still is (rewt-68, who hit the same thing on /routing). So this
                line no longer says what the edge means — it points at the words that do,
                and those come from the file at render time. */
             ['what the EDGE of this layer means is stated under it, in the words of '
              + 'the file that drew it — it has already reversed once', null]],
    /* The tally counts what the file HOLDS, so a change of shape shows on the page
       rather than being noticed later. It reported three states yesterday; today it
       reports one, which is the trim having landed. */
    states: (fs) => {
      const n = { 'in sight': 0, 'out of sight': 0, 'NOT KNOWN': 0 };
      for (const f of fs) {
        n[f.properties.visible ? 'in sight'
          : f.properties.known === false ? 'NOT KNOWN' : 'out of sight'] += 1;
      }
      return n;
    },
    note: 'theoretical sight of land: curvature and refraction only, no occlusion by '
      + 'intervening land and no weather. Click a cell for the land that holds it.' },
];
const loaded = new Set();
/* A layer's own provenance, keyed by layer id, read from the file it came in. */
const stamps = new Map();
/* What a layer's file actually holds, counted at load. See `o.states`. */
const tallies = new Map();

/* ── The network, from vector tiles ────────────────────────────────────────
 * TWO SOURCE LAYERS, and the second is the whole point. `link` may drop features at
 * low zoom so a tile stays small; `link_kept` may not, because it holds the four
 * classes this map has always promised are drawn whatever their length — the unreached,
 * the retired, the geometry this project added, and anything whose routing was
 * reversed. A defect that vanished when you zoomed out would make the map look tidier
 * and be a lie, and it is the failure the promise exists to prevent.
 */

/* Two channels crossing without joining: a ring with a cross in it. Drawn rather than
   loaded, so there is no sprite sheet and no third-party asset to pin.

   ONE GLYPH PER CLASS, not one glyph tinted three ways. `icon-color` and
   `icon-halo-color` apply only to SDF images, and this is an ordinary raster one, so a
   tint would have been silently ignored and all three classes would have come out
   identical — the corroborated crossing and the one the Trust register could have
   recorded and did not, indistinguishable. Three images, matched on the same property
   the legend names. */
const CROSSING_CLASSES = [
  ['crossing-corroborated', '#5a8fb8'],
  ['crossing-untrusted', C.unreached],
  ['crossing-outside', C.warn],
];

function crossingImage(ring) {
  const s = 20, r = 7.5, c = s / 2, cv = document.createElement('canvas');
  cv.width = cv.height = s;
  const g = cv.getContext('2d');
  g.fillStyle = '#0d1117';
  g.beginPath(); g.arc(c, c, r + 1.5, 0, Math.PI * 2); g.fill();
  g.strokeStyle = ring; g.lineWidth = 2.4;
  g.beginPath(); g.arc(c, c, r, 0, Math.PI * 2); g.stroke();
  g.strokeStyle = '#ffffff'; g.lineWidth = 1.8; g.lineCap = 'round';
  const d = r * 0.62;
  g.beginPath(); g.moveTo(c - d, c - d); g.lineTo(c + d, c + d);
  g.moveTo(c + d, c - d); g.lineTo(c - d, c + d); g.stroke();
  return g.getImageData(0, 0, s, s);
}

/* A seam mark: a filled disc with a dark rim, so it reads at 5 px over a pale sea and
   over a dark one. Drawn rather than borrowed from the crossing glyphs, which mean
   something else entirely — two watercourses that do not join. */
function seamImage(size = 16) {
  const d = new Uint8ClampedArray(size * size * 4);
  const c = (size - 1) / 2, r = size / 2 - 1.5;
  const fill = [255, 210, 30], rim = [13, 17, 23];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dist = Math.hypot(x - c, y - c);
      const i = (y * size + x) * 4;
      if (dist > r) continue;
      const col = dist > r - 1.6 ? rim : fill;
      d[i] = col[0]; d[i + 1] = col[1]; d[i + 2] = col[2];
      d[i + 3] = Math.round(255 * Math.min(1, r - dist + 1));
    }
  }
  return { width: size, height: size, data: d };
}

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
  const has = async (f) => {
    const r = await fetch(DATA + f, { method: 'HEAD' }).catch(() => null);
    return !!(r && r.ok);
  };

  if (!await has('rewt.pmtiles')) {
    problems.push('<code>data/rewt.pmtiles</code> — the network, the sea routes and the '
      + 'basins. Until the release that carries it is built, this map can draw the '
      + 'historic sheets and nothing of its own.');
    return false;
  }
  map.addSource('rewt', { type: 'vector', url: 'pmtiles://' + DATA + 'rewt.pmtiles' });

  /* TWO ARCHIVES, AND THE SPLIT IS STRUCTURAL RATHER THAN A TUNING. Tiled beside the
     195,690 lines of `link`, the four never-thinned classes came out at 1,317 of 10,229
     at z5 — and at exactly 1,317 with the size budget raised twenty-five fold, so the
     budget was never what bound them: they were being evicted from a tile they shared.
     Tiled alone the whole kept archive is 4 MB and complete. So they live apart. */
  const keptOk = await has('rewt_kept.pmtiles');
  if (keptOk) {
    map.addSource('rewt_kept',
      { type: 'vector', url: 'pmtiles://' + DATA + 'rewt_kept.pmtiles' });
  } else {
    /* NOT FATAL, AND WORTH SAYING WHY. `link_kept` is a duplicate subset of `link`, not
       an exclusive one, so losing this archive does not remove the unreached, the
       retired, our own geometry or the reversals from the map — it removes the
       GUARANTEE that they survive to low zoom. They still draw wherever `link` draws
       them. What is lost is the promise, and a promise silently withdrawn is the thing
       this layer exists to prevent. */
    problems.push('<code>data/rewt_kept.pmtiles</code> — the four never-thinned classes, '
      + 'tiled apart so they cannot be evicted by the rest of the network. Without it '
      + 'the unreached, the retired, this project\'s own geometry and the reversals are '
      + 'still drawn, but only as part of the general network: <b>at low zoom they thin '
      + 'with everything else, and a defect can vanish when you zoom out.</b>');
  }

  for (const [id, src] of [['network-out', 'link'], ['network', 'link']]) {
    map.addLayer({
      id, type: 'line', source: 'rewt', 'source-layer': src,
      filter: id.endsWith('-out') ? ['!', ['get', 'in_scope']] : ['get', 'in_scope'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': THEMES[theme].colour, 'line-width': WIDTH,
        ...(id.endsWith('-out') ? { 'line-opacity': 0.5 } : {}) },
    });
  }

  if (keptOk) {
    const layers = map.getSource('rewt_kept')?.vectorLayerIds || [];
    /* `vectorLayerIds` is empty until the archive's metadata has been read, so an
       absent name here means "not yet" as often as it means "not there". The marks
       are added regardless and the crossover only applied when the layer is known to
       exist — a dot layer over a missing source layer draws nothing and costs nothing,
       whereas holding the lines back on a false negative would empty the map. */
    const havePoints = layers.length === 0 || layers.includes('link_kept_pt');

    for (const [id, filt] of [['kept-out', ['!', ['get', 'in_scope']]],
                              ['kept', ['get', 'in_scope']]]) {
      map.addLayer({
        id, type: 'line', source: 'rewt_kept', 'source-layer': 'link_kept', filter: filt,
        // Lines from z9. Below that they are not thinned, they are UNDRAWABLE: a vector
        // tile quantises coordinates to EXTENT units across the tile, so at z5 one unit
        // is 184 m against a median kept link of 394 m and a quarter under 80 m. They
        // collapse to zero length and are dropped as degenerate. No flag changes that.
        minzoom: havePoints ? 9 : 0,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': THEMES[theme].colour, 'line-width': WIDTH,
          ...(id.endsWith('-out') ? { 'line-opacity': 0.5 } : {}) },
      });
    }

    /* ONE POINT PER KEPT LINK, on the line at its midpoint, same attributes. A point
       has no length to lose, so all 10,229 reach z5 where a quarter of the lines
       cannot. Below z9 this is what the promise actually rests on, and it is a weaker
       claim than the lines make — honestly so: the mark says a defect is THERE, and
       the geometry appears when there is a pixel to draw it in. */
    map.addLayer({
      id: 'kept-pt', type: 'circle', source: 'rewt_kept', 'source-layer': 'link_kept_pt',
      maxzoom: 10,
      paint: {
        'circle-color': THEMES[theme].colour,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 1.6, 8, 2.6, 10, 4],
        'circle-opacity': 0.9,
        'circle-stroke-color': '#0d1117', 'circle-stroke-width': 0.5,
      },
    });
  }

  map.addLayer({ id: 'sea_route', type: 'line', source: 'rewt', 'source-layer': 'sea_route',
    layout: { visibility: 'none', 'line-cap': 'round' },
    paint: { 'line-width': 1.6,
      'line-color': ['interpolate', ['linear'], ['coalesce', ['get', 'median_depth_m'], 0],
        0, '#9fe8ff', 10, '#37b6e8', 40, '#1f6fc4', 120, '#123f8a'] } }, 'network-out');
  /* THE BASIN TILES CARRY NO `share`, which is why every basin drew red: the ramp read
     `coalesce(share, 0)` and got 0 for all 1,049 of them. The reached share lives in
     summary.json, so the colour is joined here on `basin_id` rather than waiting for a
     rebuild. A basin with no share — out of scope, or with no watercourse in it at all
     — is grey, which is a third state and not the bottom of the ramp. */
  const shares = Object.fromEntries(((summary && summary.basins) || [])
    .filter((b) => b.share != null).map((b) => [b.basin_id, b.share]));
  const byId = ['match', ['get', 'basin_id']];
  for (const [id, sh] of Object.entries(shares)) byId.push(id, sh);
  byId.push(-1);                                  // no share: not zero, unknown
  /* COMPLETE IS A STEP, NOT THE TOP OF THE RAMP. 205 of the 319 basins with a share
     reach the sea entirely and another 73 fall between 0.95 and 1, so a ramp running
     smoothly to 1 painted both groups the same green and hid the only distinction
     anyone is looking for: a basin that is whole against one that is nearly whole. The
     `==` case takes the complete ones out first; the ramp then has 0 to 0.99 to itself
     and can spend its range where the variation is. */
  /* THE RAMP RAN RED TO GREEN, which is the classic failure and was the worst thing the
     palette audit found — worse than the form theme, because it inverts a meaning rather
     than merging two. "None of it reaches the sea" (#ff2d55) against "99% does" (#7cb342)
     measured **dE 1.4 under deuteranopia**: a basin that strands all its water looked
     identical to one that strands almost none. End to end it was dE 13.8 under
     protanopia.
     It runs red to BLUE now, ending on the two colours the network itself uses for the
     same two meanings — `unreached` red and `reach` blue — so the basin fill and the
     lines over it say the same thing in the same colours. End to end that is dE 46 to 60
     under all four vision types. */
  map.addLayer({ id: 'basins-fill', type: 'fill', source: 'rewt', 'source-layer': 'basin',
    layout: { visibility: 'none' },
    paint: { 'fill-opacity': 0.4, 'fill-color': ['case',
      ['<', byId, 0], '#39414d',
      ['>=', byId, 0.9999], C.reach,
      ['interpolate', ['linear'], byId,
        0, C.unreached, 0.4, '#ff6b35', 0.75, '#ffb03b', 0.95, '#ffe066', 0.99, '#86c8e8']] } },
    'network-out');
  map.addLayer({ id: 'basins-line', type: 'line', source: 'rewt', 'source-layer': 'basin',
    layout: { visibility: 'none' },
    paint: { 'line-color': '#8fa0b8', 'line-width': 0.6, 'line-opacity': 0.45 } },
    'network-out');
  return true;
}

/* `loaded` MARKS A LAYER WHEN THE FETCH STARTS, NOT WHEN IT FINISHES, and that is a
   race as soon as one layer depends on another. The seams draw from the graph's source
   and `await ensure(edges)` — but if the graph's own fetch is already in flight, that
   call returns immediately on `loaded.has`, the source does not exist yet, and the
   seams give up silently. Turning both switches on together does exactly that, which is
   what the panel does when it restores a remembered view.

   So an in-flight ensure is remembered as a PROMISE and a second caller awaits it. The
   symptom was a check reporting "no seams drew, of None in the file" in the suite while
   passing alone — and the suite was right: run one at a time, the graph had finished
   before the seams asked. */
const inflight = new Map();

async function ensure(o) {
  if (o.tiled) return;                 // already in the style, from the tile archives
  if (inflight.has(o.id)) return inflight.get(o.id);
  if (loaded.has(o.id)) return;
  const done = ensureOnce(o).finally(() => inflight.delete(o.id));
  inflight.set(o.id, done);
  return done;
}

async function ensureOnce(o) {
  loaded.add(o.id);
  /* Some layers are the audit's own findings rather than a file of their own. Built
     here from the array the panel already lists, so there is one copy of them on the
     page and a place in the list and a mark on the map cannot disagree. */
  /* A MARK ON SOME OF ANOTHER LAYER'S FEATURES, chosen by a list in a third file.
     Declared as its own kind rather than sniffed from the data — the same rule that the
     corrections layer was fixed under, after a first-feature sniff turned 1,560 mixed
     features into a symbol layer that drew none of them. */
  if (o.kind === 'stranded-mark') {
    const owner = OVERLAYS.find((x) => x.id === o.sourceOf);
    if (owner) await ensure(owner);
    if (!map.getSource(o.sourceOf)) { loaded.delete(o.id); return; }
    const net = await grab(o.summary, 'the one-network summary');
    if (!net) { loaded.delete(o.id); return; }
    /* Straight from the file. If rewt-c7 re-runs and the population changes, this
       changes with it; if the key is ever renamed the layer draws nothing and the
       count below says 0, which is visible rather than silent. */
    const ids = (net.stranded || []).map((x) => x.node_id).filter(Boolean);
    map.addLayer({ id: o.id, type: 'circle', source: o.sourceOf,
      filter: ['all', ['==', ['geometry-type'], 'Point'],
        ['in', ['get', 'node_id'], ['literal', ids]]],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 4, 12, 9],
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': o.colour,
        'circle-stroke-width': 2 } });
    /* NO TALLY. The tally renderer counts things in `cells`, and these are river
       mouths; the file already carries `termini_stranded`, which prints under its own
       key from rewt-c7's own words. One number, from the file that measured it. */
    stamps.set(o.id, net);
    checkGenerations();
    wireClicks(o);
    return;
  }
  /* A layer that draws from another's source: make sure that one is loaded, then use
     it. Its stamp and tally belong to the layer that fetched it. */
  if (o.sourceOf) {
    const owner = OVERLAYS.find((x) => x.id === o.sourceOf);
    if (owner) await ensure(owner);
    if (!map.getSource(o.sourceOf)) { loaded.delete(o.id); return; }
    map.addLayer({ id: o.id, type: 'symbol', source: o.sourceOf,
      ...(o.filter ? { filter: o.filter } : {}),
      layout: { 'symbol-placement': 'line-center', 'icon-image': 'seam',
        'icon-allow-overlap': true, 'icon-ignore-placement': true,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 12, 1.1] } });
    stamps.set(o.id, stamps.get(o.sourceOf));
    wireClicks(o);
    return;
  }
  const data = o.findings ? findingsAsPoints(o.findings)
    : await grab(o.file, o.label.toLowerCase());
  /* A TICKED BOX THAT DRAWS NOTHING IS A LIE, and this map is one rename away from it.
     `grab` names the failure in the banner at the top of the panel, which is right and
     is not enough: the toggle stayed ticked, so the control said the layer was ON while
     the map showed no such layer, and a reader looking at empty water would read it as
     empty water. The sightline layer changed file once today and its predecessor is
     about to be deleted, so this is a live path and not a hypothetical.

     The switch goes back, is disabled, and says why beside itself. `loaded` keeps the
     id, so a failed layer is not silently retried on every toggle — one clear statement
     rather than a control that flickers. */
  if (!data) {
    const row = document.querySelector(`#note-${o.id}`)?.previousElementSibling
      || [...document.querySelectorAll('#layers .switch')]
        .find((r) => r.querySelector('input') && r.textContent.includes(o.label));
    const box = row?.querySelector('input');
    if (box) { box.checked = false; box.disabled = true; }
    if (row) {
      row.style.opacity = '0.55';
      const why = document.createElement('span');
      why.className = 'hint';
      why.style.cssText = 'display:block;margin-left:22px;color:var(--warn)';
      why.textContent = `could not be loaded from ${o.file} — it is named in the `
        + 'warning at the top of this panel. Nothing of this layer is on the map.';
      row.after(why);
    }
    showProblems();
    return;
  }
  if (o.findings && !data.features.length) { loaded.delete(o.id); return; }
  /* A LAYER'S OWN STAMP, PRINTED FROM THE FILE AND NOT TYPED HERE. A FeatureCollection
     may carry top-level `properties`, and the sightline layer uses them to say what
     computed it: resolution, observer height, the refraction constant, the extent, and
     the bathymetry release with its digest. That belongs on the page, because this
     panel's own `built_at` and `config_fingerprint` describe the REWT build and cover
     nothing that came from outside it. Read from the data so it cannot drift from what
     was actually loaded — a stamp retyped into this file would be a second rendering of
     one fact, which is how the last four went wrong. */
  if (data.properties) { stamps.set(o.id, data.properties); checkGenerations(); }
  /* THE COMPOSITION OF THE FILE, COUNTED FROM THE FILE. A three-state layer whose
     third state has gone should say so on the page, not leave a reader to notice that
     a colour has stopped appearing. H3-002 §3 trims the grid to where the answer is
     known, so this tally is how the trim becomes visible when it lands — and if a
     state reappears that nobody expected, the same line reports that too. Derived,
     never typed: the legend describes what the layer CAN show and this says what it
     DOES. */
  if (o.states) tallies.set(o.id, o.states(data.features));
  /* THE COUNT BESIDE A LAYER IS A PROPERTY OF ITS FILE. Typing one here couples
     this file to somebody else's build, and the one literal that was typed went
     stale within a day. Taken from what loaded, so it describes what is drawn. */
  if (o.count == null && Array.isArray(data.features)) {
    o.count = data.features.length;
    const em = document.querySelector(`#note-${o.id}`)?.previousElementSibling
      ?.querySelector('em');
    if (em) em.textContent = fmt(o.count);
  }
  /* A LAYER'S OWN ATTRIBUTION GOES IN THE MAP'S ATTRIBUTION CONTROL, which is what
     that control is for. The sightline surface is EMODnet under CC BY 4.0 and comes
     from outside the release, so `summary.attribution` — which is the REWT build's —
     does not cover it, and until now it was displayed NOWHERE. Not a cosmetic gap: this
     repository's own README says attribution is a licence condition and not decoration.
     MapLibre shows a source's `attribution` while that source is in the style, so the
     credit appears when the layer is switched on and goes when it is switched off,
     which is exactly the right behaviour for a layer nobody has to load. */
  /* AN ATTRIBUTION MAY BE A STRING OR A LIST, and MapLibre only takes a string.
     Three of rewt-c7's four layers carry one string; `joins` carries two, because it
     derives from the bathymetry AND from the river network and credits both. Passing
     the array straight through made `addSource` reject the source, so the layer never
     appeared — no source, no layer, no error a reader would see, and the switch simply
     did nothing. Joined rather than truncated, because a short attribution may never
     attribute less than the manifest does. */
  const credit = data.properties?.attribution;
  map.addSource(o.id, { type: 'geojson', data,
    ...(credit ? { attribution: Array.isArray(credit) ? credit.join(' ') : credit } : {}) });
  if (o.kind === 'polygon') {
    map.addLayer({ id: o.id, type: 'fill', source: o.id,
      paint: { 'fill-color': o.colour, 'fill-opacity': o.opacity ?? 0.3 } },
      map.getLayer('network-out') ? 'network-out' : undefined);
    map.addLayer({ id: o.id + '-edge', type: 'line', source: o.id,
      paint: { 'line-color': o.colour, 'line-width': 0.4, 'line-opacity': 0.35 } },
      map.getLayer('network-out') ? 'network-out' : undefined);
  } else if (o.kind === 'line') {
    // A casing, so an overlay line never reads as a network line whatever the theme.
    map.addLayer({ id: o.id + '-casing', type: 'line', source: o.id,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0d1117', 'line-width': (o.width || 2) + 2.5,
        'line-opacity': 0.85,
        ...(o.offset ? { 'line-offset': o.offset } : {}) } });
    map.addLayer({ id: o.id, type: 'line', source: o.id,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': o.colour, 'line-width': o.width,
        ...(o.dash ? { 'line-dasharray': o.dash } : {}),
        // Screen pixels, so the line stays beside its replacement at every zoom rather
        // than drifting metres away from it as you zoom out. NINE, not four: at four
        // the offset was inside the network line's own casing and the retired line
        // read as a dashed centre-stripe decorating the channel it replaced — which is
        // a worse misreading than the overdraw it was meant to fix, because it looks
        // deliberate.
        ...(o.offset ? { 'line-offset': o.offset } : {}) } });
    if (o.arrows) {
      map.addLayer({ id: o.id + '-arrows', type: 'symbol', source: o.id,
        layout: { 'symbol-placement': 'line', 'icon-image': 'arrow-reversed',
          'icon-size': 0.9, 'icon-allow-overlap': true, 'icon-rotation-alignment': 'map' } });
    }
  } else if (o.kind === 'centre-mark') {
    /* ONE MARK AT THE MIDDLE OF EACH LINE. A circle layer over LineStrings draws at
       every vertex — two marks per link, at the ends, which is where a seam is not.

       DECLARED, NOT SNIFFED. This branch used to select itself on
       `data.features[0].geometry.type === 'LineString'` — one feature standing for a
       whole file. `corrections.geojson` is 1,205 LineStrings and 355 Points and happens
       to begin with a LineString, so "Every curated judgement" silently became a
       seam-icon layer and drew NOTHING, under a panel label reading 1,560. A first
       feature is a sample, and a sample was deciding the layer type for the file. */
    map.addLayer({ id: o.id, type: 'symbol', source: o.id,
      ...(o.filter ? { filter: o.filter } : {}),
      layout: { 'symbol-placement': 'line-center', 'icon-image': 'seam',
        'icon-allow-overlap': true, 'icon-ignore-placement': true,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 12, 1.1] } });
  } else if (o.kind === 'symbol') {
    map.addLayer({ id: o.id, type: 'symbol', source: o.id,
      layout: { 'icon-image': o.icon, 'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 6, 0.55, 12, 0.9, 16, 1.2] } });
  } else if (o.mixed) {
    /* A SOURCE HOLDING TWO GEOMETRY TYPES NEEDS TWO LAYERS. MapLibre draws nothing for
       a geometry its layer type cannot render, and reports no error — rewt-c7 lost 225
       of 389 joins to this today and read the gap as missing data on the Crouch and the
       Blackwater. `corrections` is 1,205 LineStrings and 355 Points and has been
       drawing only the points since long before today. Both are drawn now, and both are
       clickable, so a curated judgement on a channel is as findable as one at a place. */
    map.addLayer({ id: o.id + '-line', type: 'line', source: o.id,
      filter: ['match', ['geometry-type'], ['LineString', 'MultiLineString'], true, false],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': o.colour, 'line-width': o.width || 2.4 } });
    map.addLayer({ id: o.id, type: 'circle', source: o.id,
      filter: ['match', ['geometry-type'], ['Point', 'MultiPoint'], true, false],
      paint: { 'circle-color': o.colour,
        'circle-radius': o.radius ?? ['interpolate', ['linear'], ['zoom'], 5, 2.6, 14, 6],
        'circle-stroke-color': '#0d1117', 'circle-stroke-width': 1,
        'circle-opacity': 0.9 } });
  } else {
    map.addLayer({ id: o.id, type: 'circle', source: o.id,
      paint: { 'circle-color': o.colour,
        'circle-radius': o.radius ?? ['interpolate', ['linear'], ['zoom'], 5, 2.6, 14, 6],
        'circle-stroke-color': '#0d1117', 'circle-stroke-width': 1, 'circle-opacity': 0.9 } });
  }
  wireClicks(o);
}

/* A FeatureCollection from the findings of one kind. Empty is the normal case for a
   build whose audit did not publish that kind, and the layer then removes itself from
   the panel rather than offering a switch that turns nothing on. */
function findingsAsPoints(kind) {
  const rows = FINDINGS.filter((f) => f.kind === kind && f.lon != null);
  return { type: 'FeatureCollection', features: rows.map((f) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [f.lon, f.lat] },
    properties: { subject: f.subject, detail: f.detail, basin_id: f.basin_id },
  })) };
}

/* Whether two members of an exclusive group may be on the map at the same time.
   Different families (a hexagon layer and a line layer) never may; two cell layers
   never may; two line layers always may. See the group comment in buildLayerPanel. */
function conflicts(a, b) {
  return a.family !== b.family || a.family === 'cells';
}

function setVisible(o, on) {
  for (const id of [o.id, o.id + '-casing', o.id + '-arrows', ...(o.also || [])]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
  }
}

/* ── Panel, legend, backdrops ─────────────────────────────────────────────── */

/* THE LIST OF SWITCHES, COMPUTED ONCE. The panel renders this and the boot loop
   restores it, and they index into each other by position — so two copies of the
   predicate would mis-wire every checkbox after the first divergence, silently and
   without an error. One function, called twice.

   A layer built from findings the audit did not publish gets no switch at all. An empty
   layer offered as a control reads as "there are none of these", which is a claim;
   an absent control reads as "this build does not report them", which is the true one.
   Same rule as the findings panel hiding itself. */
const offeredOverlays = () => OVERLAYS.filter((o) => !o.findings
  || FINDINGS.some((f) => f.kind === o.findings && f.lon != null));

function buildLayerPanel() {
  const host = $('#layers');
  for (const o of offeredOverlays()) {
    const row = document.createElement('label');
    row.className = 'switch';
    /* A layer coloured by its data has no one colour; showing white for it made four
       different layers carry the same blank swatch, which reads as a key and is not
       one. Such a layer gets a band of the colours it actually uses. */
    const source = o.colour ?? o.swatch ?? (o.legend ? o.legend.map((l) => l[1]) : null);
    const hues = typeof source === 'string' ? [source]
      : ((source ? JSON.stringify(source).match(/#[0-9a-fA-F]{6}/g) : null) || ['#8a93a0']);
    const uniq = [...new Set(hues)];
    let sw = uniq.length === 1 ? uniq[0]
      : `linear-gradient(90deg, ${uniq.map((h, n) =>
          `${h} ${Math.round(n * 100 / uniq.length)}% ${Math.round((n + 1) * 100 / uniq.length)}%`).join(', ')})`;
    // The switch's swatch shows the pattern too, so that the row in the panel and the
    // line on the map are recognisably the same thing.
    if (o.dash && uniq.length === 1) {
      sw = `repeating-linear-gradient(90deg, ${uniq[0]} 0 3px, transparent 3px 6px)`;
    }
    /* The layer id on the switch, so an exclusive group can find its siblings without
       matching on label text — a label is prose and gets reworded. */
    row.innerHTML = `<input type="checkbox" data-layer="${esc(o.id)}" ${o.on ? 'checked' : ''}>
      <i class="sw ${o.kind === 'point' || o.kind === 'symbol' ? 'dot' : ''}" style="background:${sw}"
         title="${esc(uniq.join(' · '))}"></i>
      <span>${esc(o.label)}</span><em>${o.count != null ? fmt(o.count) : ''}</em>`;
    row.querySelector('input').onchange = async (e) => {
      /* EXCLUSIVE GROUPS, and the rule is about CELLS AGAINST LINES, not about any
         two layers. Stephen asked for a control that SWITCHES the sea cells to the
         routing edges, not one that adds them: a hexagon and the line between two
         hexagon centres drawn together answer neither question. So a cell layer and a
         line layer never draw together, in either direction.

         Two LINE layers may. rewt-c7 pointed out that the reason above is about
         hexagons against lines, and that the res-6 aggregated graph beside the res-7
         lattice is exactly the view that shows what the aggregation costs — which I had
         written a note inviting and the control forbidding. Their argument is right and
         it is their data; the group is now the narrower thing Stephen actually said.

         Two CELL layers still may not, and that part is mine rather than anyone's
         instruction: the sightline cells and the coastal band are hexagons at different
         resolutions, and stacked translucent hexagons at two resolutions are the muddle
         the rule is against, whichever way round they are.

         Siblings go off through their own switches, so the panel, the URL and what is
         remembered stay in step — setting `checked` alone would leave the hash claiming
         a layer that is not drawn. */
      if (e.target.checked && o.exclusive) {
        for (const other of OVERLAYS) {
          if (other === o || other.exclusive !== o.exclusive) continue;
          if (!conflicts(o, other)) continue;
          const box = [...document.querySelectorAll('#layers .switch input')]
            .find((b) => b.dataset.layer === other.id);
          if (box && box.checked) { box.checked = false; box.dispatchEvent(new Event('change')); }
        }
      }
      /* RE-READ THE SWITCH AFTER `ensure`, do not obey the state at dispatch time.
         `ensure` can take seconds on an 11 MB file, and the exclusive group above may
         turn this layer off while its fetch is still in flight. `setVisible(false)`
         was a no-op when that happened, because the layer did not exist yet — so
         showing it unconditionally here draws a layer whose switch reads off, and
         puts two members of an exclusive group on the map at once, which is the one
         thing the group exists to prevent. Found by the harness: turning every switch
         on in one pass left four layers visible with their boxes unchecked. */
      if (e.target.checked) await ensure(o);
      setVisible(o, e.target.checked);
      applyTheme(); writeHash();
      showStamp(o);
    };
    host.append(row);
    if (o.note) {
      const n = document.createElement('p');
      n.className = 'note'; n.style.margin = '0 0 6px 22px'; n.textContent = o.note;
      n.id = `note-${o.id}`;
      host.append(n);
    }
  }
}

/* THE STAMP GOES UNDER THE LAYER THAT CARRIES IT, once the file has actually arrived —
   before that there is nothing to print and a placeholder would be a claim. Only the
   fields a reader needs to judge the layer: what computed it, at what resolution, with
   what assumption about the observer, over what data, and — first, because it is the
   one that changes what the picture MEANS — the warning the file itself carries. */
const STAMP_FIELDS = [
  ['method', 'method'],
  ['observer_height_m', 'observer height, metres'],
  ['horizon_formula', 'horizon'],
  ['max_reach_km', 'furthest any land reaches, km'],
  ['blind_sailing_buffer_km', 'blind-sailing buffer, km'],
  ['week_km', "a week's sailing, km"],
  ['distance_crs', 'distances computed in'],
  ['distance_crs_worst_error_pct', 'worst projection error, %'],
  ['validated_against', 'validated against'],
  ['source_release', 'elevation'],
  ['source_checksum', 'digest'],
];
/* EVERY SENTENCE THE FILE CARRIES, NOT A LIST OF THE ONES I KNEW ABOUT. This was
   ['buffer_basis', 'week_trim', 'trimmed', 'gov_h_m_definition'] — four keys typed from
   a file I had read once, and within the hour rewt-c7 added `known_invariant` and
   `gov_reach_km_definition`, which are exactly the sentences a reader needs and which a
   hardcoded list would have silently dropped. It is the same coupling as the cell count
   that lived in this file and was wrong twice over: enumerating somebody else's schema
   means going stale every time they improve it.

   So anything long enough to be prose is prose, printed in the file's own order, minus
   what is already shown as a labelled field or handled separately. A layer that gains a
   caveat gains it on the page without my touching anything. */
/* `attribution` and `what` were on this list on the assumption they were shown
   elsewhere. `what` was not shown at all — my note said the same thing in my own words,
   which is a second rendering of one fact — and `attribution` was shown NOWHERE, which
   is a licence condition and not a formatting choice. Both are printed now, and the
   length threshold is gone with them: it was 60 characters, chosen from the file as it
   stood, and a short caveat is still a caveat. Anything not already a labelled field
   is prose. */
const STAMP_SHOWN = new Set(['use_constraint', 'warning',
  ...STAMP_FIELDS.map(([k]) => k)]);
/* TWO SENTENCES THAT MUST BE READ TOGETHER GO FIRST. rewt-c7 asked that
   `an_edge_is_not_a_route` and `aggregation` be visible without scrolling, and they are
   right about why: separately each is a caveat, together they say the picture is a
   schematic of a graph and not anything anybody could sail. I told them it was done
   before it was — the prose printed in file order, which put one second and the other
   fifth of twenty-two.

   A PREFERENCE, NOT A SCHEMA. Naming a key here cannot hide anything: everything is
   still printed, this only decides what comes first, and a key that is absent simply
   does not sort. That is the difference between this list and the one that dropped
   three of rewt-c7's sentences this morning. */
const STAMP_FIRST = ['an_edge_is_not_a_route', 'aggregation'];
const stampProse = (st) => {
  const rest = Object.entries(st)
    .filter(([k, v]) => typeof v === 'string' && !STAMP_SHOWN.has(k));
  const rank = (k) => (STAMP_FIRST.indexOf(k) + 1) || Infinity;
  return rest.sort(([a], [b]) => rank(a) - rank(b)).map(([, v]) => v);
};
/* TWO LAYERS FROM TWO PASSES, WHICH ONLY THE THING HOLDING BOTH CAN SEE. rewt-c7 puts
   a `generation` on every router artefact precisely so a reader who has two of them can
   tell whether they came from one run — and the viewer is the only place two of them
   are ever open at once. Their own message said the edges layer carried the same
   generation as the cells layer; the files said 20260904T101447Z and 20260904T092019Z,
   an hour and a half apart. The mechanism caught its author, which is the strongest
   thing that can be said for a mechanism.

   Not an error, and it does not stop anything drawing: the sightline surface may simply
   not have been rebuilt in the last pass. But a reader comparing a cell against the
   links leaving it is comparing two states of a graph that has moved, and nothing else
   on the page would tell them. */
function checkGenerations() {
  const all = [...stamps.entries()];
  const seen = all.filter(([, st]) => st && st.generation)
    .map(([id, st]) => [id, st.generation]);
  /* A LAYER WITH NO GENERATION IS NOT IN THE COMPARISON, and silence about that is the
     whole failure. rewt-c7 found that `joins.geojson` and `traces.geojson` carried no
     stamp at all while the two I happened to load did — so this check could have
     reported "one generation, no disagreement" over a set where half the members were
     never eligible, and the reassurance would have been manufactured entirely by the
     ones that had the field. D-082 with the polarity reversed: not a negative with no
     control, but agreement across a population nobody named. So the population is
     named, and an unstamped layer is reported even when the stamped ones agree. */
  const unstamped = all.filter(([, st]) => !st || !st.generation).map(([id]) => id);
  const distinct = new Set(seen.map(([, g]) => g));
  const el = document.querySelector('#warn');
  const NOTE = 'router-generations';
  document.getElementById(NOTE)?.remove();
  if (!el || (distinct.size < 2 && !unstamped.length)) return;
  if (distinct.size < 2 && unstamped.length) {
    el.hidden = false;
    const q = document.createElement('div');
    q.id = NOTE;
    q.innerHTML = `<b>${fmt(unstamped.length)} loaded layer`
      + `${unstamped.length === 1 ? ' carries' : 's carry'} no build stamp:</b> `
      + unstamped.map((id) => `<code>${esc(id)}</code>`).join(', ')
      + `. The ${fmt(seen.length)} that do agree, but that agreement says nothing about `
      + `these — they were never in the comparison.`;
    el.append(q);
    return;
  }
  el.hidden = false;
  const p = document.createElement('div');
  p.id = NOTE;
  p.innerHTML = `<b>Two router layers built in different passes.</b> `
    + seen.map(([id, g]) => `<code>${esc(id)}</code> ${esc(g)}`).join(', ')
    + `. They describe the same water at different moments, so a link and the cell it `
    + `leaves may disagree. Everything drawn is internally consistent; the two are not `
    + `necessarily consistent with each other.`
    + (unstamped.length
      ? ` A further ${fmt(unstamped.length)} loaded layer(s) carry no stamp at all and `
        + `are in none of this: ${unstamped.map((id) => esc(id)).join(', ')}.` : '');
  el.append(p);
}

/* ONE VALUE OF A STAMP, RENDERED FOR READING. The file's properties are rewt-c7's to
   shape and they have been three shapes today, so this handles the kinds rather than
   the keys:

   - AN ARRAY OF NUMBERS is a bounding box or a set of bands, and reads as numbers.
   - AN ARRAY OF RECORDS is data. `fmt` on an object returns NaN, so the 30 stranded
     termini printed as "NaN, NaN, NaN…" — a field that looks like a measurement and is
     not one. Counted here, drawn on the map instead.
   - AN OBJECT is the shape `coverage` and `rules` arrived in, and it printed as
     "[object Object]" on the page for as long as it took to notice. Flattened to its
     own pairs, which is what a reader wanted from it.

   Each of those was a real field rendered as nonsense, and each was found by looking at
   the page rather than by anything failing. */
function stampValue(v) {
  if (Array.isArray(v)) {
    return v.every((n) => typeof n === 'number')
      ? v.map((n) => fmt(n, 2)).join(', ')
      : `${fmt(v.length)} listed \u2014 see the map`;
  }
  if (v && typeof v === 'object') {
    return Object.entries(v)
      .map(([k, x]) => `${k} ${typeof x === 'number' ? fmt(x) : stampValue(x)}`)
      .join('; ');
  }
  return v;
}

function showStamp(o) {
  const st = stamps.get(o.id);
  const el = document.getElementById(`note-${o.id}`);
  if (!st || !el || el.dataset.stamped) return;
  el.dataset.stamped = '1';
  const tally = tallies.get(o.id);
  const counted = tally
    ? '<dl class="stamp">' + Object.entries(tally)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${fmt(v)} cells</dd>`).join('') + '</dl>'
    : '';
  /* THE CURATED FIELDS, THEN EVERYTHING ELSE THE FILE CARRIES. Fixing the prose to
     print whatever is there left the same hole open for values that are not strings:
     `bands` and `band_km` were in the file and shown nowhere, and rewt-c7's forthcoming
     `generation` — the stamp that says whether two of their artefacts were read
     mid-rebuild — would have been just as invisible. STAMP_FIELDS is now an ORDER and a
     set of nicer labels, not the list of what gets shown. Anything left over appears
     under its own key, arrays of numbers included, because a bounding box a reader can
     see is the difference between the computation domain and the cells that survived
     the trim — which are different things and were quoted at me as one. */
  const shown = new Set(STAMP_SHOWN);
  const rows = [
    ...STAMP_FIELDS.filter(([k]) => st[k] != null)
      .map(([k, label]) => [label, stampValue(st[k])]),
    ...Object.entries(st)
      .filter(([k, v]) => typeof v !== 'string' && !shown.has(k) && v != null)
      .map(([k, v]) => [k, stampValue(v)]),
  ].map(([label, v]) => `<dt>${esc(label)}</dt><dd>${esc(label === 'digest'
    ? String(v).slice(0, 12) + '…' : v)}</dd>`).join('');
  el.innerHTML = `${esc(o.note || '')}
    ${st.warning ? `<br><b style="color:var(--warn)">${esc(st.warning)}</b>` : ''}
    ${counted}<dl class="stamp">${rows}</dl>
    ${stampProse(st).map((v) => `<br>${esc(v)}`).join('')}
    ${st.use_constraint ? `<br><b>${esc(st.use_constraint)}</b>` : ''}`;
}

function applyTheme() {
  for (const id of ['network', 'network-out', 'kept', 'kept-out']) {
    if (map.getLayer(id)) map.setPaintProperty(id, 'line-color', THEMES[theme].colour);
  }
  if (map.getLayer('kept-pt')) map.setPaintProperty('kept-pt', 'circle-color', THEMES[theme].colour);
  /* `loaded` records a fetch, and a tiled layer never has one — it arrives with the
     style. Gating the legend on it kept the sea and basin keys off the map for exactly
     the two layers that are now on by default. */
  const extra = OVERLAYS.filter((o) => o.legend && (o.tiled || loaded.has(o.id))
      && map.getLayer(o.id) && map.getLayoutProperty(o.id, 'visibility') !== 'none')
    .flatMap((o) => [[o.label, null], ...o.legend]);
  const rows = [...THEMES[theme].legend];
  if (extra.length) rows.push(['Drawn on top', null], ...extra);
  rows.push([map.getZoom() < 9 ? 'Marked at this zoom, not drawn — a dot each'
    : 'Never thinned, at any zoom', null],
    ...(thin?.never_thinned || []).map((t) => [t, null]));
  /* A DASHED LAYER GETS A DASHED SWATCH. The retired layer is drawn as a broken line
     and its key was a solid block of magenta, so the legend showed a reader a thing
     they were not looking at: on the map the striping is the most obvious property of
     the line, and the key did not have it. Pattern is a second channel alongside hue —
     it survives a projector, daylight and colour vision deficiency, none of which
     blue-against-indigo does — and a channel the key does not explain is not a
     channel. Raised by rewt-d3. */
  $('#legend').innerHTML = rows.map(([text, colour, style], i) => colour
    ? `<span><i class="${style === 'dash' ? 'dashed' : ''}" style="${style === 'dash'
        ? `background:repeating-linear-gradient(90deg,${colour} 0 3px,transparent 3px 6px)`
        : `background:${colour}`}"></i>${esc(text)}</span>`
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
  /* THE PANEL IS USABLE BEFORE THE MAP IS. The figures and the backdrop list render as
     soon as summary.json lands, but the network takes a further twenty seconds, and a
     reader who picks a backdrop during that wait reached `addSource` before the style
     had finished loading — "Style is not done loading", thrown, and the rest of boot
     abandoned with the spinner still turning. Disabling the control would be the wrong
     fix: reading the panel while the map loads is exactly what that time is for. So the
     change is held until the style is ready instead. */
  if (!map.isStyleLoaded()) await new Promise((done) => map.once('styledata', done));

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
  tileErrors = 0;                    // a new backdrop is a new question
}

/* A BACKDROP THAT DRAWS NOTHING MUST SAY SO, because blank is the one state a reader
   cannot tell from a correct answer: an empty historic sheet and an empty stretch of
   country look identical, and the second is a real thing this map shows. The key gate
   above stops a layer being offered without a key; it cannot stop a key being present
   and refused, which is what an origin-restricted key does on localhost and what an
   expired or over-quota one does everywhere including the deployed site.

   Counted rather than reported on the first failure: a raster source 404s routinely
   at the edges of its own coverage — a county mosaic is bounded and the tiles outside
   it legitimately do not exist — so one error means nothing and a run of them means
   the layer is not going to draw. Three is enough to distinguish the two and low
   enough to fire before a reader has decided the map is broken. The message names the
   layer and the likely cause and does not guess between them. */
let tileErrors = 0;
function wireTileErrors() {
  map.on('error', (e) => {
    if (e?.sourceId !== 'backdrop' || !e.error) return;
    if (++tileErrors !== 3) return;
    const o = opts[backdropId] || {};
    $('#backdrop-note').hidden = false;
    $('#backdrop-note').innerHTML = `<b style="color:var(--warn)">This backdrop is not
      drawing.</b> Its tiles are being refused${o.requires_key
        ? `, and it needs the <code>${esc(o.requires_key)}</code> key — which is
           restricted to https://docuracy.github.io, so it will not draw on a local
           preview even when the key is present`
        : ''}. The network above it is unaffected: what you are looking at is a missing
      backdrop, not missing water.`;
  });
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

const STORE = 'rewt-viewer/v1';
/* THE HASH IS FOR SENDING, LOCAL STORAGE IS FOR RETURNING. A link carries a view to
   somebody else; storage brings a reader back to where they were. The link wins when
   there is one, because a shared view that quietly reopened somewhere else would be
   the more surprising failure. Wrapped because a private window throws on access
   rather than returning null. */
function remember(state) {
  try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) { /* private */ }
}
function recall() {
  try { return JSON.parse(localStorage.getItem(STORE) || 'null'); } catch (e) { return null; }
}

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
    remember({ zoom: map.getZoom(), lat: ctr.lat, lon: ctr.lng,
      b: backdropId, o: op, t: theme, l: on });
  }, 250);
}
map.on('moveend', writeHash);

/* PASTING A SHARED LINK INTO A TAB THAT ALREADY HAS THE MAP OPEN did nothing at all:
   changing only the fragment is a same-document navigation, so boot never re-ran, the
   hash was never re-read, and the first `moveend` overwrote the pasted link with the
   view already on screen. The reader watched their colleague's link erase itself.

   Reloading is the honest fix rather than a lazy one. Restoring a view means centre,
   zoom, backdrop, opacity, theme, county sheet and an async `ensure()` per layer — the
   whole of boot — and a second implementation of boot that ran only on paste is a
   second implementation to keep in step. `writeHash` uses replaceState, which does not
   fire this event, so anything arriving here came from outside: a paste, or the back
   button. Both want the state in the bar. */
addEventListener('hashchange', () => location.reload());
/* The legend's own heading changes at z9 — marks below, geometry above — so it has to
   follow the zoom rather than only the controls. */
map.on('zoomend', () => { if (hashReady) applyTheme(); });

function dl(obj) {
  return '<dl>' + Object.keys(obj).filter((k) => obj[k] != null && obj[k] !== '')
    .map((k) => `<dt>${esc(k)}</dt><dd>${esc(obj[k])}</dd>`).join('') + '</dl>';
}

/* ── One click, one popup (R-10, R-11) ─────────────────────────────────────────
   EVERY CLICKABLE LAYER USED TO BIND ITS OWN `click` HANDLER, and a node drawn on
   top of the link it terminates is two layers under one cursor: both fired, both
   opened a popup, and the second landed on the first. At
   os:node/7D63F86E-1FBE-4AC3-AEFE-B28073CDAF05 — a Grand Union Canal dead end with
   two inflows — you got the node's panel over a link's panel, and the link shown was
   whichever one MapLibre happened to hit-test first. The second inflow, which is the
   whole reason that node is a defect, was not on the screen at all.

   So the layers no longer bind anything. They register here, and one handler on the
   map answers the click for all of them: query every registered layer at once, put
   the marks first because a mark is what you were aiming at, and give each link its
   own collapsible block. One popup, everything under the cursor in it, nothing
   hidden behind anything else.

   WHAT THIS CANNOT DO, SAID IN THE POPUP RATHER THAN GLOSSED. `from_node` and
   `to_node` are deliberately not tiled — they are the two highest-cardinality columns
   in the table and rewt/tiles.py drops them — so the deployed viewer holds no
   node-to-link index and CANNOT enumerate the links attached to a node. What it can
   do is return every link drawn within a few pixels of the click, which at a node is
   the same set in practice and is not the same claim. The popup says which of the two
   it is doing, and where a mark carries `inflows` it compares the count and says so
   when they disagree, because a quietly short list is the failure that looks like
   success. */

const CLICKABLE = new Map();          // layer id -> { label, role, o }
const HIT = 6;                        // pixels either side of the cursor

const detail = new maplibregl.Popup({ maxWidth: '360px', closeOnClick: false });
detail.on('close', () => { highlight([]); drawRay(null); });
const popup = (ll, html) => detail.setLngLat(ll).setHTML(html).addTo(map);

/* Registered rather than bound. `role` decides which half of the popup a feature
   lands in: a link is a channel, a mark is a place on one. `kept-pt` is a mark
   standing for a link, so it is a link — it carries the link's own attributes. */
function clickable(id, label, role, o) {
  if (CLICKABLE.has(id)) return;
  CLICKABLE.set(id, { label, role, o });
  map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
}

function wireClicks(o) {
  clickable(o.id, o.label, 'mark', o);
}

function wireNetwork() {
  for (const id of ['network', 'kept', 'kept-pt']) {
    if (map.getLayer(id)) clickable(id, 'Link', 'link', null);
  }
}

/* THE HALO GOES UNDERNEATH, which is why it is a source of its own rather than a
   filter on each layer. A clicked feature may come from a vector tile or from a
   GeoJSON overlay; `queryRenderedFeatures` hands back geographic geometry either way,
   so copying it into one source highlights both by the same mechanism. Drawn below
   `network-out` so it reads as a glow behind the thing you clicked rather than as a
   new mark on top of it — a highlight that covers the feature answers the question by
   hiding the evidence. Yellow is Stephen's suggestion (R-11); it is wide, blurred and
   half-transparent so that it cannot be mistaken for the solid yellow dot that means
   a curated judgement. */
const HALO = 'click-halo';
function wireHighlight() {
  map.addSource(HALO, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  const under = map.getLayer('network-out') ? 'network-out' : undefined;
  map.addLayer({
    id: HALO + '-line', type: 'line', source: HALO,
    filter: ['match', ['geometry-type'], ['LineString', 'MultiLineString'], true, false],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': C.add, 'line-blur': 2,
      'line-opacity': ['case', ['boolean', ['get', 'hover'], false], 0.35, 0.6],
      'line-width': ['interpolate', ['linear'], ['zoom'], 5, 6, 12, 12, 17, 18] },
  }, under);
  /* AND A FILL, because the halo source takes whatever was clicked and the sightline
     cells are Polygons. Without this, clicking a sea cell highlighted NOTHING — the
     line and circle layers cannot draw a polygon, MapLibre says nothing, and the
     feature I built for R-11 simply did not work on the layer added a day later. Found
     by the geometry-coverage check on its first run, in the third place today: after
     rewt-c7's 225 joins and this viewer's 1,205 curated judgements. */
  map.addLayer({
    id: HALO + '-fill', type: 'fill', source: HALO,
    filter: ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
    paint: { 'fill-color': C.add,
      'fill-opacity': ['case', ['boolean', ['get', 'hover'], false], 0.22, 0.4] },
  }, under);
  map.addLayer({
    id: HALO + '-pt', type: 'circle', source: HALO,
    filter: ['match', ['geometry-type'], ['Point', 'MultiPoint'], true, false],
    paint: { 'circle-color': C.add, 'circle-blur': 0.5,
      'circle-opacity': ['case', ['boolean', ['get', 'hover'], false], 0.35, 0.6],
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 7, 12, 12, 17, 18] },
  }, under);

  /* The sightline ray: the line from a sea cell to the hill that governs it. A dashed
     line, because it is a claim about sight and not a channel — every solid line on
     this map is water. Drawn ABOVE the network, unlike the halo, because it is the
     answer to the click rather than an emphasis of it. */
  map.addSource('sightline-ray', { type: 'geojson',
    data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'sightline-ray', type: 'line', source: 'sightline-ray',
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': '#5ce1e6', 'line-width': 1.6, 'line-opacity': 0.9,
      'line-dasharray': [3, 2] } });
  map.addLayer({ id: 'sightline-ray-end', type: 'circle', source: 'sightline-ray',
    paint: { 'circle-color': '#5ce1e6', 'circle-radius': 3.5,
      'circle-stroke-color': '#0d1117', 'circle-stroke-width': 1 } });
}

function highlight(features, hover = false) {
  const src = map.getSource(HALO);
  if (!src) return;
  src.setData({ type: 'FeatureCollection', features: features.map((f) => ({
    type: 'Feature', geometry: f.geometry, properties: { hover },
  })) });
}

/* Only the layers that are registered AND currently in the style: a layer is removed
   when its toggle goes off, and querying a missing one throws. */
function hits(point) {
  const layers = [...CLICKABLE.keys()].filter((id) => map.getLayer(id));
  if (!layers.length) return [];
  return map.queryRenderedFeatures(
    [[point.x - HIT, point.y - HIT], [point.x + HIT, point.y + HIT]], { layers });
}

/* One feature per thing, not one per layer that draws it. A link in view at z9 is in
   both `network` and `kept`; a link below z10 is in `kept` and `kept-pt` at once. */
function split(features) {
  const links = [], marks = [], seen = new Set();
  for (const f of features) {
    const d = CLICKABLE.get(f.layer.id);
    if (!d) continue;
    const p = f.properties || {};
    const key = d.role === 'link'
      ? 'link:' + (p.link_id ?? JSON.stringify(f.geometry.coordinates))
      : `mark:${d.o?.id}:${p.node_id ?? p.correction_id ?? p.subject
          ?? JSON.stringify(f.geometry.coordinates)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    (d.role === 'link' ? links : marks).push({ d, f });
  }
  return { links, marks };
}

const linkTitle = (d) => (d.name
  ? esc(d.name) + (d.name_alt ? ` <span style="color:var(--ink-dim)">/ ${esc(d.name_alt)}</span>` : '')
  : (d.name_alt ? esc(d.name_alt) : '(unnamed)'));

function markBlock({ d, f }) {
  const p = { ...f.properties };
  let extra = '';
  if (d.o && d.o.id === 'corrections') {
    extra = `<div class="quote"><b>${p.by_rule
      ? 'JUDGED BY RULE — no person has looked at this place'
      : 'adjudicated at the place'}</b><br>${esc(p.evidence)}</div>`;
    delete p.evidence; delete p.by_rule;
  }
  /* A SIGHTLINE CELL ANSWERS IN A SENTENCE OR IT ANSWERS IN NOTHING. Three states and
     the reader must not have to work out which one they are looking at from a colour:
     the unknown case says what it does NOT mean, because "no land visible" is the
     reading it will otherwise get. Where there is a landmark, `drawRay` puts the line
     on the map so the claim is inspectable rather than asserted — you can see which
     hill, and how far, and judge it. */
  if (d.o && d.o.id === 'sightline') {
    const st = stamps.get('sightline') || {};
    /* `p.known === false`, NOT `!p.known` — the same distinction the fill expression
       was hardened for in 2105a43, and I fixed one of the two places. The trimmed layer
       carries no `known` property at all, so `!p.known` is true for every cell in it and
       every popup announced NOT KNOWN over water whose answer is perfectly well known.
       Absent means answered; only an explicit false means not knowable. Found by
       tools/viewer/shot.py on the switch to sightline2, not by me reading it twice. */
    if (p.known === false) {
      extra = `<div class="quote"><b style="color:var(--warn)">NOT KNOWN, which is not
        the same as no land in sight.</b> The land that would be visible from here lies
        outside the bathymetry cache, so this cell has no answer — it is not a
        negative.</div>`;
    } else if (p.visible) {
      /* `gov_reach_km` IS `gov_h_m`, AND THE POPUP SAYS SO. It is 3.7945*sqrt(h) for
         every one of the 14,991 cells — 67 distinct heights, 67 distinct pairs — so the
         two fields are one variable in two units. Printed side by side they read as two
         measurements agreeing, which is the most persuasive thing a single measurement
         can pretend to be. */
      extra = `<div class="quote">Land is in sight from here. The tallest land that
        reaches this cell is <b>${fmt(p.gov_h_m)} m</b>, which is why the reach is
        ${fmt(p.gov_reach_km, 0)} km — that figure is
        ${esc(st.horizon_km_per_sqrt_metre ?? '?')}·√${fmt(p.gov_h_m)} and not a second
        measurement.
        Curvature and refraction only: nothing here accounts for intervening land, haze,
        or an observer above sea level${st.observer_height_m === 0
          ? ', and the observer is AT sea level, so every range here is a floor —'
            + ` a masthead at 10 m would add about ${fmt(
                (st.horizon_km_per_sqrt_metre || 0) * Math.sqrt(10), 0)} km`
          : ''}.</div>`;
    } else {
      extra = '<div class="quote">No land in sight, and this cell is far enough inside '
        + 'the data for that to be the answer rather than a gap.</div>';
    }
    /* The ray is NOT drawn here. `describe` runs before the popup is shown, and
       showing it re-adds the same Popup instance, which fires `close` — whose
       handler clears the ray. Drawing it here therefore worked on the FIRST
       sightline click of a session and silently not afterwards, because only
       then was there no open popup to close. The click handler draws it after
       the popup instead. Found by tools/viewer/shot.py, which clicks a node
       before a cell and so hit the case I never did by hand. */
  }
  return `<b>${esc(d.label)}</b>` + dl(p) + extra;
}

/* The line from the cell to the hill that governs it. Its own source, because it is a
   claim about the world and not a highlight — the halo says "you clicked this", and
   this says "and THAT is why". Cleared whenever there is nothing to say. */
/* THE RAY NEEDS A LANDMARK POSITION AND THE NEW FILE DOES NOT CARRY ONE. The layer
   computed from the land outwards knows the governing HEIGHT of the band that first
   reached a cell, not which summit it was — `gov_h_m_definition` says so. So there is
   nothing to draw a line to, and drawing one to a guessed position would be the worst
   kind of illustration: precise, wrong, and inspectable. It stays here because the
   property may come back, and because it draws nothing whenever it is absent. */
function drawRay(p, geom) {
  const src = map.getSource('sightline-ray');
  if (!src) return;
  const ok = p && p.visible && p.landmark_lat != null && p.landmark_lon != null && geom;
  /* The cell's own centre, averaged from its ring: the file gives the landmark's
     position and the cell's shape, and the observer is the cell. */
  let from = null;
  if (ok) {
    const ring = geom.type === 'Polygon' ? geom.coordinates[0] : geom.coordinates[0][0];
    from = [ring.reduce((a, c) => a + c[0], 0) / ring.length,
            ring.reduce((a, c) => a + c[1], 0) / ring.length];
  }
  src.setData({ type: 'FeatureCollection', features: ok ? [{
    type: 'Feature', properties: {},
    geometry: { type: 'LineString', coordinates: [from, [p.landmark_lon, p.landmark_lat]] },
  }] : [] });
}

function describe(links, marks) {
  let html = marks.map(markBlock).join('');

  /* A NODE'S OWN COUNT IS THE ONLY CHECK AVAILABLE HERE, so it is used. `inflows` is
     arrivals only, never the full degree, so it can be met while an outflow is still
     missing from the list — it can therefore disagree downwards and not upwards, and
     only the downward disagreement is reported. That is the direction that matters:
     it is the one where the popup is showing you less than there is. */
  const expected = marks.map((m) => m.f.properties?.inflows)
    .filter((n) => typeof n === 'number');
  const wanted = expected.length ? Math.max(...expected) : null;

  if (links.length) {
    html += `<div class="hint">${links.length} link${links.length === 1 ? '' : 's'}`
      + ` drawn within ${HIT} px of this point`
      + (wanted != null && links.length < wanted
        ? ` — <b style="color:var(--warn)">the node records ${wanted} inflows, so at`
          + ` least ${wanted - links.length} more is attached and not drawn here.`
          + ` Zoom in, or turn on the layer it belongs to.</b>`
        : '')
      + `</div>`;
    for (const { f } of links) {
      const p = { ...f.properties };
      html += `<details${links.length === 1 ? ' open' : ''}>`
        + `<summary>${linkTitle(p)}<span class="t"> · ${esc(p.form || 'link')}`
        + `${p.length_m ? ' · ' + fmt(p.length_m / 1000, 2) + ' km' : ''}</span></summary>`
        + dl(p) + '</details>';
    }
  }
  /* Said once, at the bottom, in the popup rather than only in this file: proximity
     is not topology and the reader is entitled to know which one they are looking at. */
  if (links.length && marks.length) {
    html += '<div class="hint">These are the links drawn near the click, not a list '
      + 'of the links attached to the node — the tiles carry no node index.</div>';
  }
  return html;
}

function wireMapClicks() {
  map.on('click', (e) => {
    const { links, marks } = split(hits(e.point));
    if (!links.length && !marks.length) { detail.remove(); return; }
    popup(e.lngLat, describe(links, marks));
    highlight([...marks, ...links].map((x) => x.f));
    /* AFTER the popup, for the reason in `markBlock`: showing it closes the previous
       one, and the close handler clears the ray. */
    const sight = marks.find((m) => m.d.o && m.d.o.id === 'sightline');
    drawRay(sight ? sight.f.properties : null, sight ? sight.f.geometry : null);
  });

  /* HOVER IS A PREVIEW AND CLICK IS A PIN, so hover never disturbs an open popup.
     Above z12 only: below it a hover halo is wider than the features under it and
     every mousemove over the network lights up half the screen. */
  let last = '';
  map.on('mousemove', (e) => {
    if (detail.isOpen() || map.getZoom() < 12) return;
    const { links, marks } = split(hits(e.point));
    const feats = [...marks, ...links].map((x) => x.f);
    const key = feats.map((f) => f.properties?.link_id ?? f.properties?.node_id
      ?? JSON.stringify(f.geometry.coordinates)).join('|');
    if (key === last) return;
    last = key;
    highlight(feats, true);
  });
  map.on('mouseout', () => { if (!detail.isOpen()) highlight([]); });
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

/* ── The audit's own findings ──────────────────────────────────────────────
 * This block was rendering empty, under a heading reading "The audit's own findings" —
 * which says the audit found nothing, and it found 232. The list was never absent from
 * the audit; it was absent from summary.json, so the fix belongs in the build
 * (rewt/tiles.py) and not in a fallback here. If it is still empty the block hides
 * itself, because an empty list under that heading is a false statement about the
 * audit rather than a cosmetic blemish. */

const FINDING_LABEL = {
  dead_end: 'Dead ends',
  direction_fault: 'Direction faults',
  stranded_component: 'Stranded components',
  refused_crossing: 'Refused crossings',
  touching_not_joined: 'Touching, not joined',
  cycle: 'Cycles',
};

function renderFindings() {
  const host = $('#finding-list');
  const kind = $('#finding-kind').value;
  host.innerHTML = '';
  const rows = FINDINGS.filter((f) => !kind || f.kind === kind);
  for (const f of rows.slice(0, 250)) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="t">${esc(FINDING_LABEL[f.kind] || f.kind)}</span>
      <span class="cap">${esc(f.detail || '')}</span>`;
    li.onclick = () => { if (f.lon != null) map.flyTo({ center: [f.lon, f.lat], zoom: 14 }); };
    host.append(li);
  }
  if (!rows.length) host.innerHTML = '<li><span class="t">none of this kind</span></li>';
}

function buildFindings() {
  /* The audit publishes the worst N of each kind, not all of them, so the count in the
     option is the count of what is listed here — not of what exists. Saying "50" where
     the network has 1,195 dead ends would be the more misleading number. */
  const sel = $('#finding-kind');
  $('#findings-block').hidden = FINDINGS.length === 0;
  if (!FINDINGS.length) return;
  const kinds = [...new Set(FINDINGS.map((f) => f.kind))];
  sel.innerHTML = `<option value="">All ${FINDINGS.length} listed</option>`
    + kinds.map((k) => {
      const n = FINDINGS.filter((f) => f.kind === k).length;
      return `<option value="${esc(k)}">${esc(FINDING_LABEL[k] || k)} — ${n}</option>`;
    }).join('');
  sel.onchange = renderFindings;
  $('#findings-block').querySelector('.hint').textContent =
    `${FINDINGS.length} listed, worst first — click to fly`;
  renderFindings();
}

/* ── Epochs ────────────────────────────────────────────────────────────────
 * The rationale for each date is NOT copied here, not even as an illustration in this
 * comment — an illustrative quotation is still a second copy and drifts the same way
 * while looking harmless because it does not render. `docs/_data/epochs.yml` owns it,
 * Jekyll publishes it as epochs.json, and the temporality page and this control render
 * the same string. A bare year is the one thing this control must never show. */

/* The epoch rationales are written as table cells — "the high medieval maximum…",
   "the Dissolution; …" — so they read as fragments when a control puts them after a
   full stop. Capitalised for display only; the source string is rewt-1d's and is not
   edited here, which is the point of fetching rather than copying it. */
const sentence = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : t);

const DATUM_NOTE = 'The datum, and what you are looking at: the present-day network '
  + 'made traversable. It is NOT an epoch in the series — the dated cross-sections are '
  + 'worked backwards from it. Nothing on this map is dated.';

async function buildEpochs() {
  const host = $('#epoch-steps'), note = $('#epoch-note');
  const table = await fetch('../epochs.json').then((r) => (r.ok ? r.json() : null))
    .then((d) => (d && d.epochs) || null).catch(() => null);
  /* _blank like every other link on this page: the map holds a view the reader has
     usually spent a while arranging, and navigating away from it in the same tab
     throws that away for the sake of a footnote. */
  const link = '<a href="../epochs" target="_blank" rel="noopener">Why these dates</a>';
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
    b.title = built ? DATUM_NOTE
      : `${e.year} — not built yet.${e.why ? ' ' + sentence(e.why) : ''}`;
    b.addEventListener('mouseenter', () => say(built ? datum
      : `<b>${esc(e.year)} — not built.</b> ${e.why ? esc(sentence(e.why)) + ' ' : ''}`
        + 'The selector switches between separately modelled networks; it does not '
        + `animate one, so nothing is interpolated between stops. ${link}`));
    host.append(b);
  }
  host.addEventListener('mouseleave', () => say(datum));
}

/* ── How to read this map ──────────────────────────────────────────────────
 * Where the long prose went. It was in the side panel, above the layer switches, and
 * it pushed what most readers came for below the fold. It is not decoration — the
 * thinning rule and the licence position are both things a reader has to be able to
 * find — so it moves rather than going. */

function buildAbout() {
  const prov = (summary && summary.provenance) || {};
  const cite = summary && summary.citation;
  /* The version the BUILD stamped, against the release the data was attached to. They
     agree in the ordinary case and the box says nothing; when they disagree the tag
     wins, because a citation must name the edition the numbers came from. */
  const stamped = cite && cite.version;
  const version = (release && release.tag) || stamped;
  const year = (prov.built_at || '').slice(0, 4) || '2026';
  $('#about-body').innerHTML = `
    <h3>What this is</h3>
    <p>The river network of England and Wales, made traversable, as it is now.
    <b>Stage 1 makes no historical claim whatever</b> — nothing here is dated, and the
    epoch selector shows the seven dated cross-sections as unbuilt because they are.</p>

    <h3>How the network is drawn</h3>
    <p>Served as vector tiles and fetched a viewport at a time, so every one of its
    ${fmt(c.links)} links is reachable by zooming in. <b>Below zoom 9 four classes
    appear as marks rather than as geometry</b> — one dot per link — because at that
    scale a pixel is kilometres wide and a short channel has no drawable length. The
    mark says a defect is <em>there</em>; the line appears when there is a pixel to draw
    it in. <b>Nothing is omitted at any zoom</b>, and a channel not drawn is
    <em>not</em> a channel that is missing.</p>
    <p>Those four classes are the ones it would be worst to lose: water that does not
    reach the sea, links retired and kept for the audit trail, geometry this project
    added, and anything whose routing direction was corrected.</p>

    <h3>The historic backdrops</h3>
    <p>Eight sheets, 1885 to 1961, from the National Library of Scotland's collections
    through their Historic Maps API. <b>A sheet under this network is a backdrop and not
    evidence.</b> Nothing here is dated, and a channel lying over an 1890s sheet is not
    thereby attested in the 1890s — the backdrops are here to read the ground against.</p>
    <p>They are the Library's <em>API</em> layers. Their georeferenced tile bucket holds
    far more, including the England-and-Wales six-inch first edition, but NLS ask that
    those be re-used <q>within a desktop or local environment</q> and that a public
    website use the API or contact them; this site is public, so the bucket layers are
    drawn only in the local viewer in the repository.</p>

    <h3>Sources and attribution</h3>
    <p>${(summary && summary.attribution) || ''}</p>

    ${cite ? `<h3>Citing this</h3>
    <p><code>${esc(cite.authors.join('; '))} (${esc(year)}).
    ${esc(cite.title)}. Version ${esc(version)}.
    ${esc(cite.affiliations.join('; '))}. doi:${esc(cite.doi)}</code></p>
    <p>${esc(cite.message)}</p>
    <p><a href="https://doi.org/${esc(cite.doi)}" target="_blank" rel="noopener">${esc(cite.doi)}</a>
    — ${esc(cite.doi_note || '')}. Licensed ${esc(cite.licence)}.
    ${cite.orcids.map((o) => `<a href="${esc(o)}" target="_blank" rel="noopener">ORCID</a>`).join(' ')}</p>
    <p>This is generated from the repository's <code>CITATION.cff</code>, which is
    itself generated from <code>.zenodo.json</code>, so that whom to credit is declared
    once and this box cannot drift away from it.</p>` : ''}

    <h3>This build</h3>
    <p>Built ${esc((prov.built_at || '').slice(0, 16).replace('T', ' '))}, configuration
    fingerprint <code>${esc(prov.config_fingerprint || '—')}</code>.
    ${release ? `The figures above are read from the data attached to release
    <b>${esc(release.tag)}</b>.` : 'No release is named, so these figures come from a '
      + 'local build rather than from a published edition.'}</p>
    ${stamped && release && stamped !== release.tag ? `<p><b>The version to cite is
    ${esc(release.tag)}, not ${esc(stamped)}.</b> The citation is stamped into the data
    when it is built, and the version is bumped when the release is cut a few minutes
    later — so a freshly built asset can carry the previous edition's number. The tag is
    what the data was actually published as, and it is what this box shows.</p>` : ''}

    <h3>Elsewhere</h3>
    <p><a href="../" target="_blank" rel="noopener">The project site</a> ·
    <a href="../evidence" target="_blank" rel="noopener">Evidence and its licensing</a> ·
    <a href="../epochs" target="_blank" rel="noopener">Why these dates</a> ·
    <a href="https://github.com/docuracy/REWT" target="_blank" rel="noopener">Code on GitHub</a></p>`;
}
const showAbout = (on) => { $('#about').hidden = !on; };
$('#open-about').onclick = (e) => { e.preventDefault(); showAbout(true); };
$('#about-close').onclick = () => showAbout(false);
$('#about').onclick = (e) => { if (e.target.id === 'about') showAbout(false); };
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') showAbout(false); });

$('#copy-link').onclick = async () => {
  writeHash();
  await new Promise((r) => setTimeout(r, 300));
  const el = $('#copied');
  const say = (m) => { el.hidden = false; el.textContent = m; setTimeout(() => { el.hidden = true; }, 4000); };
  try { await navigator.clipboard.writeText(location.href); say('Copied.'); }
  catch (e) { say('The browser refused clipboard access — copy the address bar instead.'); }
};

/* ── Small screens ──────────────────────────────────────────────────────────
   Measured before it was designed: at 400 px the map was 15 px wide, 4% of the
   screen, because the panel is a fixed 360 px and the map was inset by it. The CSS
   gives the map the whole viewport below 720 px and turns the panel into a drawer;
   this is the behaviour that makes a drawer usable rather than merely present.

   `matchMedia` rather than a width test, so the breakpoint lives in ONE place — the
   stylesheet — and rotating a phone re-evaluates it without a reload. A number typed
   here as well would be a second copy of a decision, which this file has spent two
   days learning not to keep. */

function wireDrawer() {
  const panel = $('#panel');
  const toggle = $('#panel-toggle');
  const legend = $('#legend');
  if (!panel || !toggle) return;
  toggle.hidden = false;

  const setOpen = (open) => {
    panel.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? 'Map' : 'Panel';
  };
  toggle.onclick = () => setOpen(!panel.classList.contains('open'));

  /* THE DRAWER GETS OUT OF THE WAY WHEN THE MAP IS USED. A reader who taps a basin in
     the list wants to SEE the place it flies to, and on a phone the drawer is over it.
     Closing on the flight rather than on the tap means the list is still there if the
     tap missed. `movestart` covers panning and zooming too, but only when the move came
     from the reader — a programmatic flyTo carries no originalEvent, and closing on
     those as well would shut the drawer during boot. */
  map.on('movestart', (e) => {
    if (NARROW.matches && e.originalEvent) setOpen(false);
  });
  /* DELEGATED, because `wireDrawer` runs during boot and the basin and finding lists
     are built after it — binding per item here would bind to nothing, silently, and
     the drawer would simply not close. One listener on the panel outlives every
     re-render of the lists, including the basin filter rebuilding them on every
     keystroke. */
  panel.addEventListener('click', (e) => {
    if (NARROW.matches && e.target.closest('#basin-list li, #finding-list li')) {
      setOpen(false);
    }
  });

  /* Leaving the narrow layout must not leave the drawer state behind: above the
     breakpoint `.open` means nothing and the panel is always shown, but the toggle's
     label and aria state would still be describing a drawer. */
  /* CROSSING THE BREAKPOINT CHANGES THE MAP'S CONTAINER, not just the panel's. MapLibre
     tracks its container with a ResizeObserver, but the drawer opening and closing does
     NOT resize the container — the map is full width either way below 720 px — while a
     rotation does. Asking for a resize on the media change is cheap and idempotent, and
     the alternative is a strip down one edge where the backdrop was never fetched for a
     width the map did not know it had. */
  NARROW.addEventListener('change', () => { setOpen(false); map.resize(); });
  setOpen(false);

  /* The legend starts collapsed on a phone, where it was covering twelve times the
     area of the map, and open everywhere else. Its heading is the control. */
  if (legend) {
    legend.classList.toggle('shut', NARROW.matches);
    legend.addEventListener('click', (e) => {
      if (NARROW.matches && e.target.closest('b')) legend.classList.toggle('shut');
    });
    NARROW.addEventListener('change', () => legend.classList.toggle('shut', NARROW.matches));
  }
}

/* ── Boot ─────────────────────────────────────────────────────────────────── */

/* Named `progress`, not `say`: there are already two local `say`s in this file — one
   writes the epoch note, one flashes the copy-link confirmation — and a third at module
   scope reads at a glance like the same function doing a third thing. */
const progress = (t) => { const el = $('#loading-what'); if (el) el.textContent = t; };
const doneLoading = () => {
  const el = $('#loading');
  if (!el || el.hidden) return;
  el.style.opacity = '0';
  setTimeout(() => { el.hidden = true; }, 350);
};

map.on('load', async () => {
  map.addImage('arrow-reversed', arrowImage(C.rev));
  for (const [name, ring] of CROSSING_CLASSES) map.addImage(name, crossingImage(ring));
  map.addImage('seam', seamImage());
  progress('Fetching the network…');
  await addNetwork();
  wireNetwork();
  wireHighlight();
  wireMapClicks();
  wireTileErrors();
  wireDrawer();
  buildLayerPanel();
  buildAbout();
  await applyBackdrop();

  /* WHICH PROPERTIES THE TILES CARRY, read from the ARCHIVE'S OWN METADATA. The
     deployed data comes from a release and can be older than this code, so the question
     is real — but the first version of this asked a rendered feature, and that is a
     race it loses: at this point in boot no tile has been drawn yet, so
     `querySourceFeatures` returned zero features, the property list came back empty,
     and the cross-tab theme was removed from a build that fully supported it. Seconds
     later the same call returns 168,971 features. The bug was invisible in every check
     that asked whether the column was in the tiles, because it was.

     PMTiles carries `vector_layers[].fields` in its metadata — a few KB by range
     request, available before the first tile and independent of what has rendered. A
     failure to read it leaves every theme in place: a theme that paints flat is a
     visible fault someone reports, where a theme silently missing from the control is
     one nobody knows to look for. */
  try {
    const meta = await new pmtiles.PMTiles(new URL(DATA + 'rewt.pmtiles', location.href).href)
      .getMetadata();
    const link = (meta.vector_layers || []).find((l) => l.id === 'link');
    if (link && link.fields) themeReady = new Set(Object.keys(link.fields));
  } catch (e) {
    console.warn('could not read the archive metadata; every theme left offered:', e);
  }
  for (const opt of [...$('#theme').options]) {
    if (!themeUsable(opt.value)) opt.remove();
  }
  if (!themeUsable(theme)) theme = 'reach';

  progress('Drawing the layers…');
  const wanted = HASH.l === undefined ? null : (HASH.l === '-' ? [] : HASH.l.split(','));
  const boxes = [...document.querySelectorAll('#layers .switch')];
  for (const [i, o] of offeredOverlays().entries()) {
    const want = wanted ? wanted.includes(o.id) : !!o.on;
    try {
      if (want) await ensure(o);
      const box = boxes[i]?.querySelector('input');
      if (box) box.checked = want;
      if (o.tiled || loaded.has(o.id)) setVisible(o, want);
    } catch (err) { console.warn(`layer ${o.id} could not be restored:`, err); }
  }
  if (HASH.o !== undefined) {
    $('#backdrop-opacity').value = HASH.o;
    $('#backdrop-opacity').dispatchEvent(new Event('input'));
  }
  $('#theme').value = theme;
  applyTheme();
  renderBasins();
  buildFindings();
  await buildEpochs();

  /* THE OLD WORDING PROMISED SOMETHING GEOMETRY CANNOT GIVE. It said the four classes
     were "drawn at every zoom whatever their length", which implied their shape was
     there, and below z9 it is not: a vector tile quantises coordinates, so a line
     shorter than one unit — 184 m at z5, against a median kept link of 394 m — has no
     length left and cannot be drawn at all. The claim that survives is narrower and
     true: below z9 the four classes are MARKED, not drawn. */

  showProblems();
  if (HASH.zoom !== undefined) map.jumpTo({ center: [HASH.lon, HASH.lat], zoom: HASH.zoom });
  hashReady = true;
  writeHash();

  /* THE SPINNER GOES WHEN THE MAP IS ACTUALLY PAINTED, not when the fetches return.
     `idle` fires once the style is loaded and every visible tile has been rendered,
     which is the moment a reader can tell the map is working — twenty seconds earlier
     it is indistinguishable from a crash. The timeout is a backstop: if `idle` never
     comes, a spinner that spins for ever is its own kind of lie. */
  progress('Painting…');
  map.once('idle', doneLoading);
  setTimeout(doneLoading, 30000);

  /* A HANDLE FOR A TEST HARNESS, and for nothing else. `viewer.js` is a module, so
     nothing in it is reachable from the page: a browser test can screenshot this map
     and cannot ask it a question, which is the weakest possible way to check a map and
     the reason the click collision above survived to be reported by a person.
     `?debug` puts the map object and the click machinery within reach so a test can
     do what this file's own comments say to do — ask the RENDERER what draws, never
     the network (D-077, and whg3-9a hit the same thing on another project today).

     Behind a query parameter rather than always on: the hash carries view state and a
     search parameter does not disturb it, and a global that only appears when asked
     for cannot be leant on by anything shipped. `ready` last, so a harness can wait on
     one flag instead of racing boot. */
  if (new URLSearchParams(location.search).has('debug')) {
    window.rewt = { map, hits, split, describe, highlight, CLICKABLE, loaded, stamps,
      tallies, STAMP_FIELDS, ready: true };
  }
});
