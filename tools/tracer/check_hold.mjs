/**
 * Does hold mode actually hold? Exercises the REAL docs/trace/js/log.js — not a copy —
 * with the network faked at gh.js's own boundary (`fetch`), which is the method phase 1
 * used and the only one that can produce the cases that matter.
 *
 * The five publish routes are driven the way the app drives them: touch() past the event
 * threshold, touch() then the idle timer, an `online`-style push(true), a
 * `beforeunload`-style push(true), and the Save-now push(true). A PUT that reaches the
 * fake is a publication.
 */

// ── an in-memory IndexedDB, only as much as log.js's open()/tx() actually use ──
const DATA = new Map();
function req(result) {
  const o = { result, onsuccess: null, onerror: null, onupgradeneeded: null };
  queueMicrotask(() => o.onsuccess && o.onsuccess());
  return o;
}
globalThis.indexedDB = {
  open() {
    const store = {
      put: (v) => { DATA.set(v.uuid, v); return req(undefined); },
      getAll: () => req([...DATA.values()]),
    };
    const db = {
      objectStoreNames: { contains: () => true },
      transaction: () => {
        const t = { objectStore: () => store, oncomplete: null, onerror: null, onabort: null };
        queueMicrotask(() => t.oncomplete && t.oncomplete());
        return t;
      },
    };
    return req(db);
  },
};

// ── the network, refusing to be surprising ──
let PUTS = [];
globalThis.fetch = async (url, opts = {}) => {
  const u = String(url);
  if ((opts.method || 'GET') === 'PUT') {
    PUTS.push(u);
    return { ok: true, status: 200,
      json: async () => ({ content: { sha: 'newsha' + PUTS.length } }),
      text: async () => '' };
  }
  // findBlob / readBlob: pretend the branch has nothing yet.
  return { ok: false, status: 404, json: async () => ({ message: 'Not Found' }),
           text: async () => 'Not Found', headers: { get: () => null } };
};

const { createSync, makeEvent, store } = await import(
  '/home/stephen/PycharmProjects/REWT/docs/trace/js/log.js');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0;
const check = (name, got, want) => {
  const ok = got === want;
  if (!ok) fails += 1;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  (got ${got}, want ${want})`}`);
};

async function record(sync, n) {
  for (let i = 0; i < n; i += 1) {
    await store.put(makeEvent(
      { act: 'note', reason: 'r', evidence: 'e', lon: -0.1, lat: 51.5 }, 'satchell', i));
    sync.touch();
  }
}

// ══ 1. HOLD MODE: every route, nothing published ══════════════════════════════
DATA.clear(); PUTS = [];
const held = createSync({ token: 't', login: 'satchell', batch: 'phase1',
                          hold: true, onStatus: () => {} });

await record(held, 12);                    // past SYNC_EVERY_EVENTS (10)
check('touch() past the event threshold publishes nothing', PUTS.length, 0);

await sleep(120);                          // an idle timer would have to be pending
check('no idle timer fires in hold mode', PUTS.length, 0);

await held.push(true);                     // the `online` listener's call
check('the online listener publishes nothing', PUTS.length, 0);

await held.push(true);                     // beforeunload's call, were it not guarded
check('a beforeunload push publishes nothing', PUTS.length, 0);

check('12 events really are in the store', (await store.all()).length, 12);
check('and all 12 are unsynced', await store.unsyncedCount(), 12);

// ══ 2. RELEASE: exactly one publication, and the gate closes behind it ═════════
await held.release();
check('release() publishes once', PUTS.length, 1);
check('released work is marked synced', await store.unsyncedCount(), 0);

await record(held, 11);                    // more work after the release
check('the gate closed again — no second automatic push', PUTS.length, 1);
await held.push(true);
check('and push() is still refused after a release', PUTS.length, 1);

// ══ 3. A FAILED RELEASE MUST RE-ARM THE GATE ══════════════════════════════════
DATA.clear(); PUTS = [];
const flaky = createSync({ token: 't', login: 'satchell', batch: 'phase1',
                           hold: true, onStatus: () => {} });
await record(flaky, 3);
const good = globalThis.fetch;
globalThis.fetch = async () => { throw new Error('network down'); };
await flaky.release();                     // must not throw, must not leave the gate open
globalThis.fetch = good;
check('a failed release published nothing', PUTS.length, 0);
await flaky.push(true);
check('and the gate is shut again afterwards', PUTS.length, 0);
await flaky.release();
check('a later release still works', PUTS.length, 1);

// ══ 4. PUBLISH MODE still behaves as it did before ════════════════════════════
DATA.clear(); PUTS = [];
const open_ = createSync({ token: 't', login: 'satchell', batch: 'phase1',
                           hold: false, onStatus: () => {} });
await record(open_, 10);
await sleep(50);
check('publish mode still auto-publishes at the threshold', PUTS.length >= 1, true);

// ══ 5. setHold(true) cancels a timer already counting down ════════════════════
DATA.clear(); PUTS = [];
const switcher = createSync({ token: 't', login: 'satchell', batch: 'phase1',
                              hold: false, onStatus: () => {} });
await record(switcher, 1);                 // arms the idle timer, does not reach 10
switcher.setHold(true);                    // the person presses "hold" mid-countdown
await sleep(120);
check('switching to hold cancels the pending push', PUTS.length, 0);

console.log(fails ? `\n${fails} FAILED` : '\nall passed');
process.exit(fails ? 1 : 0);

/* ── WHAT THIS PROVES, AND THE ONE THING IT DOES NOT ──────────────────────────────
 *
 * Verified by breaking each gate in turn and re-running, because a test that has never
 * failed has not been shown to test anything:
 *
 *   push()'s gate removed   ->  8 of 15 checks fail, exit 1.   LOAD-BEARING.
 *   touch()'s gate removed  ->  every check still passes.      NOT load-bearing.
 *
 * So the guarantee lives in `push`, exactly as intended: it is the single point every
 * publish route funnels through, and removing it is caught loudly. `touch`'s early return
 * is redundant for safety and is there to keep a pointless timer from repainting the
 * status line mid-trace — which is why this file cannot see it, and why nobody should
 * "fix" the redundancy by deleting the one in `push`.
 */
