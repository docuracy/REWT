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

const $ = (id) => document.getElementById(id);

let SESSION = null;   // { token, login, sync }

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
    $('signout').hidden = false;
    $('pathline').innerHTML = `Writing to <code>${REPO.owner}/${REPO.name}</code>,
      branch <code>${REPO.branch}</code>, at <code>${sync.path()}</code>.`;
    await paint(`signed in as ${login}` + (remote.length ? ` — recovered ${remote.length} events` : ''));
    await paintLedger();
  } catch (e) {
    await paint(e.message, true);
  }
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

  const held = gh.readToken();
  if (held.token) signIn(held.token); else paint('sign in to begin');
}

/* The build stamp, checked rather than recorded. Browsers go on serving a cached module,
   and a contributor then reports behaviour of code that is not deployed. */
console.info('[tracer] build ' + BUILD);

boot();
