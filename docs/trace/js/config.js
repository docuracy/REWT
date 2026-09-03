/**
 * Everything that changes between deployments, in one place.
 *
 * WHY THIS IS A MODULE AND NOT SCATTERED CONSTANTS. The repository the log is
 * written to is not settled: REWT is private today, and D-043 rules that traces are
 * OPEN OUTPUT — which means the contribution repository does not have to be private,
 * and if it is public the token we ask a volunteer for drops from `repo` (every
 * repository they can reach, public and private) to `public_repo` (public only,
 * no access to any private repository of theirs or ours). That is a large reduction
 * in what we are asking for, and it is one constant here rather than a rewrite.
 */

/* Must match the ?v= on the script tag in index.html. Browsers go on serving a cached
   module, and the page then reports the behaviour of code that is not deployed —
   which arrives as a bug report about something nobody can reproduce. */
export const BUILD = '0.8.0-hold';

export const REPO = {
  owner: 'docuracy',
  name: 'REWT',
  /* Never `main`. Pages rebuilds on a push to main under docs/**, so a contributor
     saving every few minutes would fire a site rebuild each time, queue them serially,
     and bury main's history under thousands of commits. */
  branch: 'traces',
  /* `docuracy/REWT` became public on 1 Sep 2026, so this is `public_repo` — which grants
     read and write to PUBLIC repositories only and **no access to any private repository**
     of the contributor's or of ours. That is a large reduction in what we ask a volunteer
     to hand over, and it is the one good consequence of the change for this tool: while the
     repository was private nothing narrower than `repo` could reach it, and `repo` is every
     repository they can see.
     
     Stated here rather than written into the sign-in text, so the scope we ask for and the
     scope we describe cannot drift apart. */
  scope: 'public_repo',
  private: false,
};

/* The whole Pages site shares one origin and therefore one localStorage. Read live
   rather than copying, so revoking or replacing a token anywhere propagates instead of
   leaving a stale duplicate behind. */
export const TOKEN_KEYS = ['rewt_gh_token', 'github_token'];

/* WHICH WAY THE UNKNOWN FAILS, and it is the only real decision in this file.
 *
 * Hold is the DEFAULT and publishing is the opt-in, which is the opposite of what the
 * tool did through phase 1. The asymmetry decides it: an unwanted hold is visible on
 * every screen (the header carries the count and the status line says so on every
 * suppressed push) and is undone by one click; an unwanted publication is invisible to
 * the person who caused it and cannot be undone at all, because the repository is public
 * and history is world-readable the moment it is pushed.
 *
 * So a contributor whose stored choice is missing — cleared site data, a private window,
 * a second machine, a browser that lost its localStorage — resumes HELD rather than
 * resuming published. That case is not hypothetical: it is the ordinary way a volunteer
 * comes back on Monday. TEAM.md's rule is that the unknown must fail towards the visible
 * fault, and between these two only the hold is visible. */
export const HOLD_BY_DEFAULT = true;

/* Per-login, because one browser may be shared and the mode is a property of the working
   arrangement rather than of the machine. `rewt_tracer_mode:<login>`. */
export const MODE_KEY = (login) => `rewt_tracer_mode:${login}`;

export const SYNC_EVERY_EVENTS = 10;
export const SYNC_IDLE_MS = 60_000;

/* GitHub wants base64; btoa wants a binary string; String.fromCharCode(...bytes) passes
   every byte as a separate argument and blows the JS argument stack somewhere past a
   hundred thousand of them. This stopped saving in the London Customs Accounts editors
   once one file passed 360 kB. */
export const B64_CHUNK = 0x8000;
