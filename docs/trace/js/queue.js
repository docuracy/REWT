/**
 * The work queue: which place a contributor is looking at, and how they were sent there.
 *
 * ── A SLICE IS A VIEW, NOT A PARTITION ──────────────────────────────────────────────
 *
 * Work is handed out with a URL fragment — `#cls=assertion&from=0&n=20` — which a
 * coordinator shares. The fragment rather than the query string, because it never reaches
 * the server and so cannot interact with Pages caching, and because two people can be
 * pointed at exactly the same places by sharing one link. That is the London Customs
 * Accounts editors' arrangement, which has worked across a corpus of thousands.
 *
 * **A slice narrows what you work ON, not what you have done.** Everything already
 * contributed stays in the log and stays yours; the slice is a view.
 *
 * ── WHY THERE IS NO CLAIMING ────────────────────────────────────────────────────────
 *
 * Assignment is the mechanism, not locking. Disjoint slices handed out by a coordinator
 * mean two people never meet; a claim file in a repository with no server is a race, and
 * the basin hold (PLAN.md §8) is a design rather than an artefact. Where two contributors
 * do land on one place, the event log records both with a coordinate and the collision is
 * found by folding the log — which is this project's crawl-from-the-sea habit applied to
 * people: do not prevent what you can detect, and let what arrives twice be the report.
 *
 * ── A SKIP IS DATA ──────────────────────────────────────────────────────────────────
 *
 * *This reservoir has no pre-dam sheet.* *The channel here is under a housing estate.*
 * Those are findings, and a queue that records only successes throws them away. AGENTS.md
 * requires every skip to be named; here it is a first-class event with a reason, a
 * coordinate and the task id, exactly like a trace.
 */

const CLASSES = {
  assertion: {
    file: './tasks/assertions.json',
    label: 'Old Course / New Cut',
    blurb: 'A place where the surveyor lettered one channel as superseded and, often, its '
         + 'replacement. An assertion by someone who was there — not an inference from the '
         + 'modern line.',
  },
  mill: {
    file: './tasks/mill-channels.json',
    label: 'Mill channels',
    blurb: 'A mill race, leat or pond. Frequently medieval, and belonging in the '
         + 'reconstruction — but the map does not say when it was cut.',
  },
};

export function parseSlice(hash = location.hash) {
  const q = new URLSearchParams((hash || '').replace(/^#/, ''));
  const cls = CLASSES[q.get('cls')] ? q.get('cls') : 'assertion';
  const from = Math.max(0, parseInt(q.get('from'), 10) || 0);
  const n = parseInt(q.get('n'), 10);
  return {
    cls,
    from,
    n: Number.isFinite(n) && n > 0 ? n : null,
    label: q.get('label') || null,
    /* Blind is fixed by the LINK and never by a checkbox. An agreement figure is worthless
       if half the contributors forgot to tick the box, so the person handing out the work
       decides and the person doing it cannot accidentally opt out. Reserved for phase 7;
       nothing reads it yet. */
    blind: ['1', 'true', 'yes'].includes((q.get('blind') || '').toLowerCase()),
  };
}

export async function loadQueue(slice) {
  const spec = CLASSES[slice.cls];
  const res = await fetch(spec.file, { cache: 'no-store' });
  if (!res.ok) throw new Error(`no task list for ${slice.cls} (HTTP ${res.status})`);
  const doc = await res.json();
  const all = doc.tasks;
  const end = slice.n ? Math.min(all.length, slice.from + slice.n) : all.length;
  const tasks = all.slice(slice.from, end);
  return {
    spec,
    doc,
    all,
    tasks: tasks.length ? tasks : all,
    /* Said out loud, because a contributor who does not know how much of the whole they
       are seeing cannot tell a finished slice from a broken one. */
    describe: tasks.length && tasks.length !== all.length
      ? `${slice.label || spec.label}: places ${slice.from + 1}–${end} of ${all.length}`
      : `${spec.label}: all ${all.length} places`,
  };
}

/** What the contributor is told about the place, in the words the surveyor used. */
export function describeTask(task) {
  const captions = task.captions.join(' · ');
  if (task.kind === 'locate') {
    return {
      captions,
      caveat: 'The surveyor did not letter the channel here — only something named after '
            + 'it. The water is nearby and is not where the label is. Weaker evidence '
            + 'than a lettered channel, and better than none.',
    };
  }
  return { captions, caveat: null };
}
