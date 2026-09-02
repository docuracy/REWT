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
import { parseSlice, loadQueue, describeTask } from './queue.js';

const $ = (id) => document.getElementById(id);

let SESSION = null;   // { token, login, sync }
let MAP = null;
let TRACER = null;
let BACKDROPS = [];
let CURRENT = null;   // the backdrop being traced on
let QUEUE = null;     // { spec, tasks, describe }
let AT = 0;           // index into QUEUE.tasks

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
  /* A REFUSAL ALWAYS GOES TO #advice, WHATEVER ITS LENGTH. The rule used to be by size —
     short messages to the header, long ones to the notice — and that made a short refusal
     invisible: "every event carries a reason in words" is 34 characters, so it went to the
     status strip and was overwritten by the next repaint. The contributor saw their skip
     simply not happen. Length is a property of the sentence; whether it is a refusal is a
     property of what happened, and only the second should decide where it is shown. */
  const bits = [];
  if (msg && !bad && msg.length <= 40) bits.push(msg);
  bits.push(`${held} held locally`);
  bits.push(last ? `last saved ${last.toLocaleTimeString()}` : 'not yet saved');
  if (!navigator.onLine) bits.push('offline');
  const el = $('status');
  el.textContent = bits.join(' · ');
  el.classList.toggle('bad', Boolean(bad));
  if (bad || (msg && msg.length > 40)) advise(msg, bad);
  else advise(null);
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
       or ours. It is still a classic token — a fine-grained one cannot write to a
       repository owned by another account, public or private.`;
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

/* ── the queue ────────────────────────────────────────────────────────────── */

async function startQueue() {
  const slice = parseSlice();
  try {
    QUEUE = await loadQueue(slice);
  } catch (e) {
    /* No queue is a working state, not a broken one: a contributor can trace a place they
       already know. Say which it is rather than leaving the panel blank. */
    $('slicenote').textContent = 'No task list loaded — ' + e.message
      + '. You can still trace anywhere on the sheet.';
    $('queue').hidden = false;
    return;
  }
  AT = 0;
  $('queue').hidden = false;
  $('taskblurb').textContent = QUEUE.spec.blurb;
  $('slicenote').textContent = QUEUE.describe;
  showTask();
}

function showTask() {
  if (!QUEUE || !QUEUE.tasks.length) return;
  const t = QUEUE.tasks[AT];
  const d = describeTask(t);
  $('taskpos').textContent = `${AT + 1} / ${QUEUE.tasks.length}`;
  $('taskcaptions').textContent = d.captions;
  $('taskcaveat').hidden = !d.caveat;
  if (d.caveat) $('taskcaveat').textContent = d.caveat;
  $('prevtask').disabled = AT === 0;
  $('nexttask').disabled = AT >= QUEUE.tasks.length - 1;
  $('t_task').value = t.id;
  if (MAP) MAP.flyTo({ center: [t.lon, t.lat], zoom: 17.5, duration: 0 });
  TRACER?.cancel();
}

/** A skip is an event with a reason and a place, exactly like a trace. */
async function skipTask() {
  if (!QUEUE || !SESSION) return;
  const t = QUEUE.tasks[AT];
  const reason = $('skipreason').value.trim();
  try {
    const seq = (await store.all()).length;
    await store.put(makeEvent({
      act: 'skip', taskId: t.id, reason,
      evidence: `${CURRENT?.name ?? 'no sheet'}; captions: ${t.captions.join('; ')}`,
      lon: t.lon, lat: t.lat,
      payload: { kind: t.kind, captions: t.captions },
    }, SESSION.login, seq));
    $('skipreason').value = '';
    SESSION.sync.touch();
    await paint('skip recorded');
    await paintLedger();
    if (AT < QUEUE.tasks.length - 1) { AT += 1; showTask(); }
  } catch (e) {
    /* makeEvent refuses a skip with no reason. *Name every skip* is not a courtesy: eleven
       of twenty-five corrections once did nothing silently in the predecessor. */
    await paint(e.message, true);
  }
}

/* ── the map ──────────────────────────────────────────────────────────────── */

/**
 * The backdrop a contributor can actually trace on — decided by asking, not by arithmetic.
 *
 * BOUNDS ARE A HINT AND NOT A CONTAINMENT TEST, and this function exists because the first
 * version forgot that. The catalogue's extents are derived from a listing at zoom 9, so a
 * box is snapped to about 78 km and several counties genuinely contain any given point.
 * Choosing the smallest box containing the centre picked **Bedfordshire for a point in
 * Ware, Hertfordshire** — whose tiles do not cover it, so the map drew nothing at all and
 * said nothing about why. That is rewt-fc's Northwich case arriving unprompted: picking the
 * first box there lands on `Shrop_Derby`, which draws one tile in fifty-seven.
 *
 * So the boxes only NOMINATE. The bucket decides: fetch the one tile covering the point
 * from each candidate in turn and take the first that answers. One request per candidate,
 * usually one candidate, and it is the difference between a sheet and a blank screen.
 */
function tileXY(lon, lat, z) {
  const n = 2 ** z;
  return {
    x: Math.floor(((lon + 180) / 360) * n),
    y: Math.floor((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2 * n),
  };
}

/* WITH A TIMEOUT, BECAUSE THIS IS ON THE STARTUP PATH. A bare `fetch` waits as long as the
   network takes, and this runs once per candidate county before the map is built — so a
   single stalled request left the tool showing "checking…" for ever, with no error, no map
   and nothing said. A probe that cannot answer promptly has answered: assume the layer
   does not serve here and let the picker offer the rest. */
const PROBE_MS = 4000;

async function servesTile(layer, lon, lat) {
  const z = Math.min(layer.zooms[1], 16);
  const { x, y } = tileXY(lon, lat, z);
  const url = layer.tiles.replace('{z}', z).replace('{x}', x).replace('{y}', y);
  try {
    const r = await fetch(url, { method: 'GET', cache: 'no-store',
                                 signal: AbortSignal.timeout(PROBE_MS) });
    return r.ok;
  } catch {
    return false;                       // offline, refused, or too slow to be waited on
  }
}

function candidatesFor(lon, lat, group) {
  const area = (l) => (l.bounds[2] - l.bounds[0]) * (l.bounds[3] - l.bounds[1]);
  return BACKDROPS
    .filter((l) => l.group === group
      && lon >= l.bounds[0] && lon <= l.bounds[2] && lat >= l.bounds[1] && lat <= l.bounds[3])
    .sort((a, b) => area(a) - area(b));
}

/* Smallest boxes first, and only a few of them: the box is a hint, so the third-smallest
   candidate is already a guess about a guess, and the picker offers everything anyway. */
const MAX_PROBES = 4;

async function bestFor(lon, lat, group) {
  for (const l of candidatesFor(lon, lat, group).slice(0, MAX_PROBES)) {
    if (await servesTile(l, lon, lat)) return l;
  }
  return null;
}

async function backdropOptions(lon, lat) {
  const best = await bestFor(lon, lat, '25_inch');
  /* THE SIX-INCH FIRST, AND THIS ORDER WAS WRONG UNTIL IT WAS CORRECTED. An earlier version
     defaulted to the 25-inch on the grounds that it is finer. It is — but the work is on
     the six-inch: the task queue comes from GB1900's transcription of the six-inch second
     edition, and the seamless layers cover England and Wales where the 25-inch is county
     by county with gaps.

     The two sheets afford DIFFERENT OPERATIONS rather than the same one at two qualities.
     On the six-inch a watercourse is a single stroke, so the operation is to follow the ink
     and centring correctly refuses. On the 25-inch it is two banks, so a middle exists to
     be found and a width can be read. Defaulting to the 25-inch put contributors on the
     sheet where the ordinary operation does not apply. */
  const order = [
    ...BACKDROPS.filter((l) => l.group === 'seamless'),
    ...(best ? [best] : []),
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
  /* WHICH OPERATION FITS IS A PROPERTY OF THE REACH, NOT OF THE SHEET, and an earlier
     version of this function got that wrong: it disabled centring off the 25-inch, on my
     claim that a six-inch watercourse is a single stroke. It is not universally. OS
     switches from one line to two at a GROUND width, so a six-inch sheet carries both — a
     mill leat as a single stroke and a navigable river as a pair of banks, sometimes in
     one frame. `docs/evidence.md` records the Weaver at Northwich drawn as two banks on
     the six-inch. The gate would therefore have been wrong on every wide river, which is
     exactly where the navigation evidence lives.

     The per-vertex refusal below already decides this correctly and from the pixels — *that
     point is on ink, so the channel here is drawn as a single line* — so the sheet-level
     gate was a worse test layered on top of a working one. Removed. What the finer scale
     changes is how many channels fall on the two-bank side of the threshold, not whether
     the distinction exists. */
  const finer = (CURRENT?.group === '25_inch');
  $('centring').disabled = false;
  $('centring').parentElement.title =
    'Finds the middle where the surveyor drew two banks, and refuses where the channel is '
    + 'a single stroke. Which of those it is depends on the reach, not on the sheet.';
  $('sheetnote').textContent = finer
    ? '1:2,500 — more channels are drawn as two banks at this scale, so centring applies '
      + 'more often and a width can be read more often.'
    : 'Six-inch — a leat is a single stroke and a navigable river is a pair of banks, '
      + 'often on the same sheet. Centring finds the middle of the second and refuses on '
      + 'the first; it decides per vertex, from the ink.';
}

async function startMap() {
  BACKDROPS = (await (await fetch('./backdrops.json', { cache: 'no-store' })).json()).layers;
  /* Ware, on the Lea — the calibration ground for the centring mode, and a place with a
     New Cut, a navigation and the New River within one screen. */
  const start = { lon: -0.0290, lat: 51.8080, zoom: 16 };
  const first = await backdropOptions(start.lon, start.lat);
  MAP = new maplibregl.Map({
    container: 'map', center: [start.lon, start.lat], zoom: start.zoom,
    style: { version: 8, sources: {}, layers: [] },
    /* The tracer reads tiles it fetches itself rather than the map's canvas, so the
       drawing buffer need not be preserved — which is a real per-frame cost avoided. */
    preserveDrawingBuffer: false,
  });
  await new Promise((r) => MAP.on('load', r));
  applyBackdrop(first);
  /* The same affordance the viewer offers, and for the same reason: somebody reads out a
     coordinate and you need to get there. `window.rewt` also carries the tracer, so the
     experimental centring can be exercised from the console without clicking. */
  window.map = MAP;
  window.rewt = { get map() { return MAP; }, get tracer() { return TRACER; },
                  get backdrop() { return CURRENT; }, backdrops: () => BACKDROPS };

  TRACER = createTracer({
    map: MAP,
    backdrop: () => CURRENT,
    onChange: paintTrace,
  });

  await startQueue();

  MAP.on('zoom', () => { $('zoompill').textContent = 'z' + MAP.getZoom().toFixed(1); });
  $('zoompill').textContent = 'z' + MAP.getZoom().toFixed(1);

  $('backdrop').onchange = async () => {
    const l = BACKDROPS.find((x) => x.id === $('backdrop').value);
    if (!l) return;
    applyBackdrop(l);
    /* A sheet that covers no ground here draws nothing and says nothing, which reads as a
       broken map rather than a wrong choice. Say it. */
    if (l.traceable && !(await servesTile(l, MAP.getCenter().lng, MAP.getCenter().lat))) {
      await paint(`${l.name} has no sheet over this ground — the map will be blank here. `
        + 'County extents in the catalogue are approximate; the sheet itself is the test.', true);
    }
  };
}

function paintTrace(s) {
  const n = s.vertices ?? 0;
  $('finish').disabled = n < 2;
  $('undo').disabled = n < 1;
  $('abandon').disabled = n < 1;
  $('record').disabled = n < 2;
  /* The two notes are independent, and an early return used to swallow the second: with
     centring off this function returned before reaching paintSnap, so the livewire never
     said anything at all and looked switched off. Neither note may depend on the other's
     mode being on. */
  paintCentre(s);
  paintSnap(s);
  if (s.finished) $('record').focus();
}

/**
 * What the livewire did, said while tracing rather than only recorded.
 *
 * The same obligation as the centring note and for the same reason: a run of snapped
 * vertices looks more authoritative than a drawn line and is not — it is a cheapest path
 * through ink that describes roads, railways and parish boundaries as readily as rivers.
 * The corridor is what bounds how wrong it can be, so the corridor is what the contributor
 * is told about.
 */
function paintCentre(s) {
  const note = $('centrenote');
  if (s.busy) { note.textContent = 'reading the sheet…'; note.className = ''; return; }
  const c = s.lastCentre;
  if (!s.centring) { note.textContent = ''; note.className = ''; return; }
  if (!c) {
    note.textContent = 'Centring is on. It measures the channel ACROSS the way you are '
      + 'going, so it needs a previous vertex to take a bearing from.';
    note.className = ''; return;
  }
  if (c.moved) {
    note.textContent = `Moved ${c.movedM.toFixed(1)} m to the middle. The channel is `
      + `${c.widthM.toFixed(1)} m wide here, measured across ${c.transectsAgreeing} transects.`;
    note.className = 'moved';
  } else {
    note.textContent = 'Left where you put it — ' + c.why;
    note.className = '';
  }
}

function paintSnap(s) {
  const el = $('snapnote');
  if (!s.snapping) { el.textContent = ''; return; }
  const k = s.lastSnap;
  if (!k) {
    el.textContent = 'Following the ink between your clicks, inside a corridor around the '
      + 'straight line — so it can only choose among ink you have already pointed at. '
      + 'Where the ink runs out or forks, click more often.';
    return;
  }
  el.textContent = k.snapped
    ? `Followed the ink: ${k.vertices} vertices from ${k.pixels} pixels, on a `
      + `${k.mode} sheet, inside a ${k.corridorM} m corridor.`
    : 'Straight line — ' + k.why;
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
  $('snapping').onchange = (e) => TRACER.setSnapping(e.target.checked);
  $('record').onclick = recordTrace;
  $('prevtask').onclick = () => { if (AT > 0) { AT -= 1; showTask(); } };
  $('nexttask').onclick = () => { if (QUEUE && AT < QUEUE.tasks.length - 1) { AT += 1; showTask(); } };
  $('skip').onclick = skipTask;
  addEventListener('hashchange', () => startQueue());

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
    /* Move on, because the unit of work is a place and the contributor has finished this
       one. Their slice is a view, so nothing about the queue position is recorded. */
    if (QUEUE && AT < QUEUE.tasks.length - 1) { AT += 1; showTask(); }
    await paint('trace recorded');
    await paintLedger();
  } catch (e) {
    /* traceAnnotation refuses a missing reason, evidence, author or dated, and refuses a
       keyed URL. Those are the repository's requirements on a judgement; the tool says so
       rather than writing a row nobody can weigh later. */
    await paint(e.message, true);
  }
}

/**
 * THE BUILD STAMP, ACTUALLY CHECKED — which is what `config.js` has claimed since phase 1
 * and what nothing did until now.
 *
 * `?v=` on the script tag versions the ENTRY POINT only. Sibling modules are separate URLs
 * with no query, so they cache independently: this morning `app.js?v=0.4.0-p4` was running
 * against a `config.js` from `0.3.3-p3`, and the only reason anyone noticed was that the
 * console printed the older number. An import map fixes the caching and **breaks the
 * checks**, because import maps are a browser feature and node cannot resolve a bare
 * specifier — so the remedy disabled a guard, which is a worse trade than the problem.
 *
 * Detection is what was actually missing. If the modules disagree the page says so, loudly,
 * rather than behaving like a version nobody is looking at.
 */
function checkBuild() {
  const src = document.querySelector('script[type=module]')?.getAttribute('src') || '';
  const tag = (src.match(/[?&]v=([^&]+)/) || [])[1];
  if (tag && tag !== BUILD) {
    advise(`This page is serving mixed versions: the entry point is ${tag} and the modules `
      + `it loaded report ${BUILD}. Your browser is holding an old copy of part of the `
      + `tool. Reload with Ctrl+Shift+R before trusting anything it does.`, true);
    console.error(`[tracer] MIXED BUILD: entry ${tag}, modules ${BUILD}`);
  }
}

/* The build stamp, checked rather than recorded. Browsers go on serving a cached module,
   and a contributor then reports behaviour of code that is not deployed. */
console.info('[tracer] build ' + BUILD);

boot();
checkBuild();
