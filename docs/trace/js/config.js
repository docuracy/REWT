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
export const BUILD = '0.4.3-p4';

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

export const SYNC_EVERY_EVENTS = 10;
export const SYNC_IDLE_MS = 60_000;

/* GitHub wants base64; btoa wants a binary string; String.fromCharCode(...bytes) passes
   every byte as a separate argument and blows the JS argument stack somewhere past a
   hundred thousand of them. This stopped saving in the London Customs Accounts editors
   once one file passed 360 kB. */
export const B64_CHUNK = 0x8000;
