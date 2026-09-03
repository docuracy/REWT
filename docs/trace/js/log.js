/**
 * The edit log: append-only, event-sourced, local first.
 *
 * WHY EVENTS AND NOT STATE. AGENTS.md: *never delete a geometry to correct it — retire it
 * with a reason and keep it. The audit trail is part of the product, and a retired link is
 * how a reader tells a correction from an omission.* That rule is written about the
 * network; it applies with more force to work contributed by someone who cannot run the
 * build and cannot see what their edit did. So this file records what HAPPENED, and the
 * current state is a fold over it.
 *
 * A SKIP IS DATA. `this reservoir has no pre-dam sheet` is a finding, and a tool that
 * records only successes throws it away. AGENTS.md's *name every skip* is not a courtesy
 * here — eleven of twenty-five corrections once did nothing silently in the predecessor,
 * including the largest single defect in the country.
 */

import { SYNC_EVERY_EVENTS, SYNC_IDLE_MS, BUILD } from './config.js';
import * as gh from './gh.js';

const DB_NAME = 'rewt-tracer';
const STORE = 'events';
const DB_VERSION = 1;

/* Deliberately not a library. One object store, put, getAll and a count; the raw
   IndexedDB API covers that in less code than an import would cost, and there is no
   build step to tree-shake an unused one. */
function open() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'uuid' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(db, mode, fn) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const out = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(out?.result ?? out);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}

/* ── the event ────────────────────────────────────────────────────────────── */

export const ACTS = ['trace', 'revise', 'withdraw', 'skip', 'note', 'hold-taken'];

/**
 * Every judgement in this repository carries `reason`, `evidence`, `author` and `dated`,
 * and `author`/`dated` are mandatory (rewt-6a) because a contribution that does not say
 * who made it and when cannot be weighed a year later. A contributed trace is where that
 * bites hardest: the person who made it cannot run the build and may never be reachable.
 *
 * AND A COORDINATE, ALWAYS. 332 corrections in the current build carried neither geometry
 * nor easting/northing, so nobody could go and look at them. A skip has no line geometry
 * of its own; it still gets a place. *Report at the place, not only in the total.*
 */
export function makeEvent({ act, taskId, reason, evidence, lon, lat, payload }, login, seq) {
  if (!ACTS.includes(act)) throw new Error(`unknown act: ${act}`);
  if (!reason) throw new Error('every event carries a reason in words');
  if (!evidence) throw new Error('every event carries its evidence');
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
    throw new Error('every event carries a coordinate, including a skip or a note');
  }
  const now = new Date();
  return {
    uuid: crypto.randomUUID(),
    seq,
    act,
    task_id: taskId ?? null,
    author: login,
    dated: now.toISOString().slice(0, 10),
    created: now.toISOString(),
    reason,
    evidence,
    /* CRS84 and it says so. A course whose CRS is unstated is a course whose numbers mean
       nothing, and assuming WGS 84 because they look like degrees is how a dataset
       acquires a silent offset. */
    crs: 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
    lon,
    lat,
    generator: 'rewt-tracer/' + BUILD,
    payload: payload ?? null,
    synced: false,
  };
}

/**
 * The fold's order is stated here rather than left to whoever reads the files.
 *
 * PLAN.md §2 requires deterministic ordering wherever a result depends on iteration
 * order, and this is such a place: two contributors' files merged on a branch have no
 * inherent order, and `revise` then `withdraw` is a different final state from the
 * reverse. Total order is (created, author, seq); uuid breaks any remaining tie so the
 * comparator is total rather than merely usually-total.
 */
export function compareEvents(a, b) {
  return (a.created < b.created ? -1 : a.created > b.created ? 1 : 0)
    || (a.author < b.author ? -1 : a.author > b.author ? 1 : 0)
    || (a.seq - b.seq)
    || (a.uuid < b.uuid ? -1 : a.uuid > b.uuid ? 1 : 0);
}

/* Events are idempotent by uuid, which is what makes offline flushing and 409 recovery
   the same code path as an ordinary save. */
export function union(...lists) {
  const by = new Map();
  for (const list of lists) for (const e of list) if (e && e.uuid) by.set(e.uuid, e);
  return [...by.values()].sort(compareEvents);
}

export function serialise(events) {
  return events.map((e) => {
    const { synced, ...line } = e;   // `synced` is local bookkeeping, not part of the record
    return JSON.stringify(line);
  }).join('\n') + '\n';
}

export function parse(text) {
  const out = [];
  for (const line of (text || '').split('\n')) {
    if (!line.trim()) continue;
    try { out.push(JSON.parse(line)); } catch { /* a corrupt line is not a reason to lose the rest */ }
  }
  return out;
}

/* ── the store ────────────────────────────────────────────────────────────── */

export const store = {
  async all() {
    const db = await open();
    const rows = await tx(db, 'readonly', (s) => s.getAll());
    return (rows || []).sort(compareEvents);
  },
  async put(event) {
    const db = await open();
    return tx(db, 'readwrite', (s) => s.put(event));
  },
  async markSynced(uuids) {
    const db = await open();
    const set = new Set(uuids);
    const rows = await tx(db, 'readonly', (s) => s.getAll());
    const db2 = await open();
    return tx(db2, 'readwrite', (s) => {
      for (const r of rows || []) if (set.has(r.uuid) && !r.synced) s.put({ ...r, synced: true });
    });
  },
  async unsyncedCount() {
    const rows = await this.all();
    return rows.filter((r) => !r.synced).length;
  },
};

/* ── the flusher ──────────────────────────────────────────────────────────── */

/**
 * ── HOLD MODE, AND WHY THE GATE IS HERE RATHER THAN AT THE CALL SITES ──────────────
 *
 * The repository is public, so a commit is a publication — `tools/tracer/PLAN.md` §2:
 * *the moment of contribution is the moment of publication*. For an invited contributor
 * that was argued through and disclosed on the sign-in wall. For a third party working
 * against a corpus whose terms are unresolved it is not acceptable at all: their false
 * starts and withdrawn judgements would be world-readable as they were committed, and
 * **there is no private branch to escape to, because every branch of a public repository
 * is public.** Hold mode is therefore the only held-back path available.
 *
 * THERE ARE FIVE WAYS THIS MODULE PUBLISHES and only one of them is a button:
 * `touch()` at ten events, `touch()` after sixty idle seconds, the `online` listener,
 * `beforeunload`, and `Save now`. Gating them one by one in `app.js` would work today
 * and would leak the first time somebody adds a sixth — and the leak is unrecoverable,
 * because nothing can be unpublished. So the gate is INSIDE `push`, which every route
 * already funnels through: a new caller added in ignorance of hold mode does nothing
 * instead of publishing.
 *
 * **`release()` is the only way out**, and it is one-shot. It does not clear the hold; it
 * lets exactly one push through and closes again, so a released batch cannot be followed
 * by a silent automatic one.
 *
 * WHAT HOLD MODE COSTS, stated because it is a real trade and not a free win. Held work
 * lives in IndexedDB in one browser. Clearing site data, a private window, or a different
 * machine loses it, and no push has happened to recover it from. Publication risk is
 * traded for loss risk — which is why `Export` exists, works signed out, and is the thing
 * to reach for before trusting the hold overnight.
 */
export function createSync({ token, login, batch, hold = false, onStatus }) {
  const path = () => `traces/${login}/${batch}.jsonl`;
  let held = hold;
  let sha = null;
  let dirty = 0;
  let timer = null;
  let busy = false;
  let lastPush = null;
  let releasing = false;

  const say = (msg, bad) => onStatus && onStatus({ msg, bad, dirty, lastPush });

  async function pull() {
    sha = await gh.findBlob(token, path());
    if (!sha) return [];                       // first run: nothing to recover, and no red 404
    return parse(await gh.readBlob(token, sha));
  }

  async function push(force) {
    /* THE GATE. Held work is not a failure and must not be reported as one: the events are
       in the store, the count is on screen, and nothing is lost. Saying so on every
       suppressed push is what keeps the hold visible rather than silent — a mode that
       stops publishing and stops mentioning it is indistinguishable from a broken one. */
    if (held && !releasing) {
      say(dirty ? `held — ${dirty} event${dirty === 1 ? '' : 's'} not published`
                : 'held — nothing to publish');
      return;
    }
    if (busy || (!dirty && !force)) return;
    busy = true;
    say('saving…');
    try {
      const local = await store.all();
      if (!local.length) { say('nothing to save yet'); return; }
      const body = serialise(union(local));
      try {
        sha = await gh.putFile(token, path(), body, sha,
          `Tracer: ${login} (${local.length} events, build ${BUILD})`);
      } catch (e) {
        if (!e.conflict) throw e;
        const remote = await pull();
        const merged = union(remote, local);
        for (const ev of merged) await store.put({ synced: false, ...ev });
        sha = await gh.putFile(token, path(), serialise(merged), sha,
          `Tracer: ${login} (${merged.length} events, merged after conflict)`);
      }
      await store.markSynced(local.map((e) => e.uuid));
      dirty = 0;
      lastPush = new Date();
      say(`saved ${local.length} events`);
    } catch (e) {
      say('save failed: ' + e.message, true);
    } finally {
      busy = false;
    }
  }

  function touch() {
    dirty += 1;
    clearTimeout(timer);
    /* No timer at all in hold mode, rather than a timer whose push is refused. A pending
       timer that fires into the gate every sixty seconds would repaint the status line
       out of nowhere while somebody is tracing, and would look like the tool trying to
       save and failing. */
    if (held) { say(`held — ${dirty} event${dirty === 1 ? '' : 's'} not published`); return; }
    if (dirty >= SYNC_EVERY_EVENTS) { push(); return; }
    timer = setTimeout(() => push(), SYNC_IDLE_MS);
  }

  /* One push, then closed again. `finally` rather than a trailing assignment because a
     failed release must re-arm the gate: a network error during the one permitted push
     would otherwise leave it open for whatever fires next, which is precisely the
     automatic publication hold mode exists to prevent. */
  async function release() {
    if (!held) return push(true);
    releasing = true;
    try { await push(true); } finally { releasing = false; }
  }

  return {
    pull, push, touch, release, path,
    /* A getter and a setter rather than a captured boolean, so a mode change takes
       effect on the next event instead of at the next sign-in. Turning the hold ON also
       cancels any timer already counting down towards a push — otherwise the switch
       would be followed, up to sixty seconds later, by exactly the automatic publication
       the person had just asked to stop. */
    get hold() { return held; },
    setHold(v) {
      held = Boolean(v);
      if (held) clearTimeout(timer);
      return held;
    },
    get dirty() { return dirty; },
    get lastPush() { return lastPush; },
  };
}
