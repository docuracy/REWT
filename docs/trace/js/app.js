/**
 * Phase 1: the shell. Sign-in wall, event log, flush, export, status.
 *
 * No map, and that is the design rather than an omission. This phase depends on nothing
 * outstanding — not the release asset, not the work queue, not the lifted modules — and
 * it proves the one thing everything else rests on: that an invited contributor can get
 * work out of a browser and into this repository, with the network off included.
 */

import { BUILD, REPO } from './config.js';
import * as gh from './gh.js';
import { ACTS, makeEvent, store, createSync, serialise, union } from './log.js';
import { createTracer } from './tracer.js';
import { traceAnnotation, boundFromSurveyYear, boundInWords, representativePoint } from './anno.js';

const $ = (id) => document.getElementById(id);

let SESSION = null;   // { token, login, sync }
let MAP = null;
let TRACER = null;
let BACKDROPS = [];
let CURRENT = null;   // the backdrop being traced on

/* ── status: a count and a time, never a spinner ──────────────────────────── */

/**
 * The header carries only the two facts that must always be true: how much is held in
 * this browser, and when it last reached GitHub. A count and a time, never a spinner —
 * a contributor who does not trust the tool will re-do work, and an animation is not
 * evidence either way.
 *
 * Anything longer than a few words goes to #advice instead. The most important text this
 * tool will ever show is the explanation of why a token cannot see the repository, and a
 * paragraph wrapped through a status strip is a paragraph people stop reading.
 */
async function paint(msg, bad) {
  const held = await store.unsyncedCount().catch(() => 0);
  const last = SESSION?.sync?.lastPush;
  const bits = [];
  if (msg && msg.length <= 40) bits.push(msg);
  bits.push(`${held} held locally`);
  bits.push(last ? `last saved ${last.toLocaleTimeString()}` : 'not yet saved');
  if (!navigator.onLine) bits.push('offline');
  const el = $('status');
  el.textContent = bits.join(' · ');
  el.classList.toggle('bad', Boolean(bad));
  if (msg && msg.length > 40) advise(msg, bad);
  else if (!bad) advise(null);
}

function advise(msg, bad) {
  const el = $('advice');
  el.hidden = !msg;
  if (!msg) return;
  /* Linkify a bare URL so the token instructions are one click rather than a
     copy-and-paste from a status message. Nothing else in the string is interpreted. */
  el.innerHTML = escapeHtml(msg).replace(/(https:\/\/[^\s]+)/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>');
  el.classList.toggle('good', !bad);
}

async function paintLedger() {
  const rows = await store.all();
  $('rows').innerHTML = rows.slice(-40).reverse().map((e) => `
    <tr><td>${e.created.slice(11, 19)}</td><td>${e.act}</td>
        <td>${e.task_id ?? ''}</td><td>${escapeHtml(e.reason)}</td>
        <td>${e.synced ? '✓' : '—'}</td></tr>`).join('');
  $('ledger').hidden = rows.length === 0;
}

const escapeHtml = (s) => String(s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* ── sign in ──────────────────────────────────────────────────────────────── */

function scopeLine() {
  return REPO.private
    ? `It needs the <code>repo</code> scope, which is broad: it grants read and write to
       <em>every</em> repository you can reach, public and private. Nothing narrower works
       while this repository is private, and we would rather say so than let you discover
       it.`
    : `It needs the <code>public_repo</code> scope, which grants read and write to public
       repositories only and <strong>no access to any private repository</strong> of yours
       or ours.`;
}

async function signIn(token) {
  if (/^github_pat_/.test(token)) { await paint(gh.tokenAdvice(token), true); return; }
  try {
    await paint('checking…');
    const login = await gh.whoami(token);
    gh.storeToken(token);
    const batch = 'phase1';
    const sync = createSync({
      token, login, batch,
      onStatus: ({ msg, bad }) => paint(msg, bad).then(paintLedger),
    });
    SESSION = { token, login, sync };

    /* Recover anything this contributor did on another machine before anything is
       written, so a second device does not silently start from nothing. */
    const remote = await sync.pull();
    if (remote.length) {
      const local = await store.all();
      for (const ev of union(remote, local)) await store.put({ synced: true, ...ev });
    }

    $('wall').hidden = true;
    $('workbench').hidden = false;
    $('mapsection').hidden = false;
    await startMap();
    $('signout').hidden = false;
    $('pathline').innerHTML = `Writing to <code>${REPO.owner}/${REPO.name}</code>,
      branch <code>${REPO.branch}</code>, at <code>${sync.path()}</code>.`;
    await paint(`signed in as ${login}` + (remote.length ? ` — recovered ${remote.length} events` : ''));
    await paintLedger();
  } catch (e) {
    await paint(e.message, true);
  }
}

/* ── the map ──────────────────────────────────────────────────────────────── */

/**
 * The backdrop a contributor can actually trace on.
 *
 * BOUNDS ARE A HINT, NOT A CONTAINMENT TEST. The catalogue's extents are derived from a
 * listing at zoom 9, so a box is snapped to about 78 km and several counties genuinely
 * contain any given point. Picking the SMALLEST box containing the centre lands on the
 * right county far more often than picking the first — at Northwich the first is
 * `Shrop_Derby`, which draws one tile in fifty-seven. It is a default, and the picker is
 * there because a default is all it can be.
 */
function bestFor(lon, lat, group) {
  const inside = BACKDROPS.filter((l) => l.group === group
    && lon >= l.bounds[0] && lon <= l.bounds[2] && lat >= l.bounds[1] && lat <= l.bounds[3]);
  if (!inside.length) return null;
  const area = (l) => (l.bounds[2] - l.bounds[0]) * (l.bounds[3] - l.bounds[1]);
  return inside.sort((a, b) => area(a) - area(b))[0];
}

function backdropOptions(lon, lat) {
  const best = bestFor(lon, lat, '25_inch');
  const order = [
    ...(best ? [best] : []),
    ...BACKDROPS.filter((l) => l.group === 'seamless'),
    ...BACKDROPS.filter((l) => l.group === '25_inch' && l !== best),
    ...BACKDROPS.filter((l) => l.group === 'modern'),
  ];
  $('backdrop').innerHTML = order.map((l) =>
    `<option value="${l.id}">${l.name}</option>`).join('');
  return order[0];
}

function applyBackdrop(layer) {
  CURRENT = layer;
  const style = {
    version: 8,
    sources: { sheet: { type: 'raster', tiles: [layer.tiles], tileSize: 256,
                        maxzoom: layer.zooms[1], attribution: layer.attribution } },
    layers: [{ id: 'sheet', type: 'raster', source: 'sheet' }],
  };
  MAP.setStyle(style);
  MAP.once('styledata', () => TRACER?.refresh());
  paintWhen();
}

function paintWhen() {
  const when = boundFromSurveyYear(CURRENT?.surveyYear);
  $('whenline').textContent = boundInWords(when);
}

async function startMap() {
  BACKDROPS = (await (await fetch('./backdrops.json', { cache: 'no-store' })).json()).layers;
  /* Ware, on the Lea — the calibration ground for the centring mode, and a place with a
     New Cut, a navigation and the New River within one screen. */
  const start = { lon: -0.0290, lat: 51.8080, zoom: 16 };
  const first = backdropOptions(start.lon, start.lat);
  MAP = new maplibregl.Map({
    container: 'map', center: [start.lon, start.lat], zoom: start.zoom,
    style: { version: 8, sources: {}, layers: [] },
    /* The tracer reads tiles it fetches itself rather than the map's canvas, so the
       drawing buffer need not be preserved — which is a real per-frame cost avoided. */
    preserveDrawingBuffer: false,
  });
  await new Promise((r) => MAP.on('load', r));
  applyBackdrop(first);
  window.map = MAP;

  TRACER = createTracer({
    map: MAP,
    backdrop: () => CURRENT,
    onChange: paintTrace,
  });

  MAP.on('zoom', () => { $('zoompill').textContent = 'z' + MAP.getZoom().toFixed(1); });
  $('zoompill').textContent = 'z' + MAP.getZoom().toFixed(1);

  $('backdrop').onchange = () => {
    const l = BACKDROPS.find((x) => x.id === $('backdrop').value);
    if (l) applyBackdrop(l);
  };
}

function paintTrace(s) {
  const n = s.vertices ?? 0;
  $('finish').disabled = n < 2;
  $('undo').disabled = n < 1;
  $('abandon').disabled = n < 1;
  $('record').disabled = n < 2;
  const note = $('centrenote');
  if (s.busy) { note.textContent = 'reading the sheet…'; note.className = ''; return; }
  const c = s.lastCentre;
  if (!s.centring) { note.textContent = ''; note.className = ''; return; }
  if (!c) { note.textContent = 'Centring is on. It measures the channel ACROSS the way you '
    + 'are going, so it needs a previous vertex to take a bearing from.'; note.className = ''; return; }
  if (c.moved) {
    note.textContent = `Moved ${c.movedM.toFixed(1)} m to the middle. The channel is `
      + `${c.widthM.toFixed(1)} m wide here, measured across ${c.transectsAgreeing} transects.`;
    note.className = 'moved';
  } else {
    note.textContent = 'Left where you put it — ' + c.why;
    note.className = '';
  }
  if (s.finished) $('record').focus();
}

/* ── wiring ───────────────────────────────────────────────────────────────── */

function boot() {
  $('scopeline').innerHTML = scopeLine();
  $('act').innerHTML = ACTS.map((a) => `<option>${a}</option>`).join('');

  $('signin').onclick = () => signIn($('token').value.trim());
  $('token').onkeydown = (e) => { if (e.key === 'Enter') $('signin').click(); };

  $('signout').onclick = () => { gh.forgetToken(); location.reload(); };

  $('emit').onclick = async () => {
    if (!SESSION) return;
    try {
      const seq = (await store.all()).length;
      const ev = makeEvent({
        act: $('act').value,
        taskId: $('taskid').value.trim() || null,
        reason: $('reason').value.trim(),
        evidence: $('evidence').value.trim(),
        lon: Number($('lon').value),
        lat: Number($('lat').value),
      }, SESSION.login, seq);
      await store.put(ev);
      $('reason').value = '';
      SESSION.sync.touch();
      await paint('recorded');
      await paintLedger();
    } catch (e) {
      /* makeEvent throws on a missing reason, evidence or coordinate. Those are the
         repository's own requirements on a judgement, so the tool refuses rather than
         writing a row nobody can weigh later. */
      await paint(e.message, true);
    }
  };

  $('pushnow').onclick = () => SESSION && SESSION.sync.push(true);

  /* Always available, and working signed out, offline, or refused by GitHub. The
     difference between an annoyance and a lost evening. */
  $('export').onclick = async () => {
    const text = serialise(await store.all());
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'application/x-ndjson' }));
    a.download = `rewt-tracer-${SESSION?.login ?? 'local'}.jsonl`;
    a.click();
  };

  addEventListener('online', () => SESSION && SESSION.sync.push(true));
  addEventListener('offline', () => paint('offline — work is held here'));

  addEventListener('beforeunload', () => {
    if (SESSION && SESSION.sync.dirty) SESSION.sync.push(true);
  });

  $('starttrace').onclick = () => {
    TRACER.cancel(); TRACER.start();
    $('starttrace').textContent = 'Tracing — click along the channel';
  };
  $('undo').onclick = () => TRACER.undo();
  $('abandon').onclick = () => { TRACER.cancel(); TRACER.stop();
    $('starttrace').textContent = 'Start tracing'; };
  $('finish').onclick = () => { TRACER.stop(); $('starttrace').textContent = 'Start tracing'; };
  $('centring').onchange = (e) => TRACER.setCentring(e.target.checked);
  $('record').onclick = recordTrace;

  const held = gh.readToken();
  if (held.token) signIn(held.token); else paint('sign in to begin');
}

/**
 * A finished trace becomes an annotation, and the annotation becomes one event.
 *
 * The four mandatory fields are enforced twice, in both modules, and that is deliberate
 * rather than redundant: `makeEvent` guards the log and `traceAnnotation` guards the
 * record, and a trace extracted into `data/curated/traces/` on its own has left the event
 * behind. Neither can rely on the other having looked.
 */
async function recordTrace() {
  const r = TRACER.result();
  if (r.coordinates.length < 2) return;
  try {
    const point = representativePoint(r.coordinates);
    const replaces = $('t_replaces').value.trim();
    const annotation = traceAnnotation({
      id: `urn:uuid:${crypto.randomUUID()}`,
      coordinates: r.coordinates,
      vertexOrigin: r.vertexOrigin,
      snapMode: r.snapMode,
      sheet: { id: CURRENT.id, label: CURRENT.name, url: 'https://maps.nls.uk/',
               attribution: CURRENT.attribution, zoom: Math.round(MAP.getZoom()),
               surveyYear: CURRENT.surveyYear },
      author: SESSION.login,
      dated: new Date().toISOString().slice(0, 10),
      reason: $('t_reason').value.trim(),
      evidence: $('t_evidence').value.trim(),
      supersedes: replaces ? [replaces] : [],
      note: $('t_note').value.trim() || null,
      name: $('t_name').value.trim() || null,
      created: new Date().toISOString(),
      generator: { id: 'https://docuracy.github.io/REWT/trace/', type: 'Software',
                   'schema:softwareVersion': BUILD },
    });
    const seq = (await store.all()).length;
    const ev = makeEvent({
      act: 'trace',
      taskId: $('t_task').value.trim() || null,
      reason: $('t_reason').value.trim(),
      evidence: $('t_evidence').value.trim(),
      lon: point[0], lat: point[1],
      payload: { annotation },
    }, SESSION.login, seq);
    await store.put(ev);
    TRACER.cancel();
    SESSION.sync.touch();
    await paint('trace recorded');
    await paintLedger();
  } catch (e) {
    /* traceAnnotation refuses a missing reason, evidence, author or dated, and refuses a
       keyed URL. Those are the repository's requirements on a judgement; the tool says so
       rather than writing a row nobody can weigh later. */
    await paint(e.message, true);
  }
}

/* The build stamp, checked rather than recorded. Browsers go on serving a cached module,
   and a contributor then reports behaviour of code that is not deployed. */
console.info('[tracer] build ' + BUILD);

boot();
