/**
 * GitHub as the only shared state there is.
 *
 * The tool has no server. Reading and writing the edit log, and later the basin holds,
 * happen through the REST API with the contributor's own token, and GitHub — not
 * JavaScript — performs the access control. A check in this file could gate the
 * interface; it could not gate the data, and describing it as if it could would be
 * worse than no gate at all.
 */

import { REPO, TOKEN_KEYS, B64_CHUNK } from './config.js';

const API = 'https://api.github.com';

/**
 * Every failed request goes through here on its way to the console.
 *
 * WHY. The messages this module returns are written for a contributor, so they say what
 * to DO — and in saying it they drop the status, the URL and GitHub's own words, which
 * are what a diagnosis needs. Twice now that has cost a round trip: a 401 was reported
 * without saying which call produced it, and the auth scheme it was sent with was
 * invisible. The console gets the facts; the page gets the advice.
 */
export async function report(label, response) {
  let body = {};
  try { body = JSON.parse(await response.clone().text() || '{}'); } catch { /* not JSON */ }
  /* One flat line, not an object. A console viewer that collapses objects to `Object`
     hides exactly the fields this exists to surface, and the person reading it is often
     reading it through something other than devtools. */
  const h = (k) => response.headers.get(k) ?? '-';
  console.error(
    `[tracer] ${label} -> HTTP ${response.status} | github says: "${body.message || '-'}"`
    + ` | scheme: ${AUTH_SCHEME} | scopes on token: [${h('x-oauth-scopes')}]`
    + ` | scopes accepted here: [${h('x-accepted-oauth-scopes')}]`
    + ` | rate limit left: ${h('x-ratelimit-remaining')}`
    + ` | sso: ${h('x-github-sso')} | url: ${response.url}`);
  return body;
}

/* ── the token ────────────────────────────────────────────────────────────── */

export function readToken() {
  for (const k of TOKEN_KEYS) {
    let v = null;
    try { v = (localStorage.getItem(k) || '').trim(); } catch { /* private browsing */ }
    if (v) return { token: v, source: k };
  }
  return { token: '', source: null };
}

export function storeToken(token) {
  try { localStorage.setItem(TOKEN_KEYS[0], (token || '').trim()); } catch { /* ignore */ }
}

export function forgetToken() {
  for (const k of TOKEN_KEYS) { try { localStorage.removeItem(k); } catch { /* ignore */ } }
}

/**
 * WHY THIS FUNCTION EXISTS AT ALL, rather than letting the caller report a 404.
 *
 * GitHub answers 404, not 403, for a private repository a token cannot see. So a
 * wrong-KIND token looks exactly like a missing file or a missing branch, and the
 * person reads it as a fault in the tool. Two people lost an afternoon to this in the
 * London Customs Accounts editors.
 *
 * And the reason a fine-grained token is not merely under-scoped but INAPPLICABLE:
 * fine-grained tokens only ever reach repositories owned by the token's own account
 * (or an organisation that has opted in). `docuracy` is a personal account, so a
 * collaborator's fine-grained token can never see this repository however it is
 * configured. Verified against GitHub's documentation, 1 Sep 2026.
 */
export function tokenAdvice(token) {
  const t = token || readToken().token;
  if (/^github_pat_/.test(t)) {
    return 'That is a fine-grained token. Fine-grained tokens can only reach repositories '
      + 'owned by your own account, so this one cannot see this repository however it is '
      + 'configured — it is not under-scoped, it is the wrong kind. Create a CLASSIC token '
      + `with the \`${REPO.scope}\` scope at https://github.com/settings/tokens/new`;
  }
  return 'The token cannot see this repository. Either it lacks the '
    + `\`${REPO.scope}\` scope, or you have not yet accepted the invitation to collaborate. `
    + 'GitHub answers 404 rather than 403 in both cases, so this message cannot tell them '
    + 'apart — check the invitation first, it is the commoner one.';
}

/* ── requests ─────────────────────────────────────────────────────────────── */

/**
 * `Bearer`, NOT `token`.
 *
 * GitHub no longer accepts the legacy `Authorization: token <t>` scheme for personal
 * access tokens: it answers **401 Bad credentials**, which is indistinguishable from an
 * expired or revoked token and sends you to mint a new one that fails identically.
 * Measured 1 Sep 2026 against one live token, same request, only the scheme differing:
 *
 *     Authorization: Bearer <t>   ->  200, login returned, scopes: repo
 *     Authorization: token  <t>   ->  401 Bad credentials
 *
 * This module inherited `token ` from the London Customs Accounts editors, written when
 * it still worked. The failure cost a real token: the diagnostic written to investigate
 * it used the same header, so it reproduced the bug and reported it as a verdict on the
 * credential. An instrument built with the fault it is looking for will confirm itself.
 */
const AUTH_SCHEME = 'Bearer';

function headers(token, accept = 'application/vnd.github+json') {
  return { Authorization: AUTH_SCHEME + ' ' + token, Accept: accept };
}

/**
 * WHY EACH STATUS GETS ITS OWN SENTENCE. The first version of this reported `HTTP 401`
 * and nothing else, which is precisely the failure the 404 advice below was written to
 * avoid — a bare status code in the one place a contributor meets first. The three
 * outcomes mean quite different things and only one of them is about this project:
 *
 *   401  the credential is not recognised AT ALL. Not scopes, not collaborator status,
 *        not the branch, not this repository. Expired, revoked, or mistyped.
 *   403  the credential IS recognised and the request was refused — a rate limit or a
 *        block, which will pass.
 *   200  a valid token, whatever its scopes: /user needs none. So reaching this line
 *        proves the token is real and defers every question about access to findBlob.
 */
export async function whoami(token) {
  const r = await fetch(API + '/user', { headers: headers(token), cache: 'no-store' });
  if (!r.ok) await report('whoami GET /user', r);
  if (r.status === 401) {
    throw new Error(
      'GitHub does not recognise that token — 401 is a statement about the credential '
      + 'itself, so this is not about scopes, not about collaborator status, and not '
      + 'about this repository. It is expired, revoked, or mistyped. Before making a new '
      + 'one, check what is actually in the field: a browser password manager will '
      + 'happily autofill a masked field with an older saved value, and it looks '
      + 'identical to the token you meant to paste.');
  }
  if (r.status === 403) {
    throw new Error(
      'GitHub refused the request (403). The token IS recognised — this is a rate limit '
      + 'or a block rather than a bad credential, and it will pass. Wait and try again.');
  }
  if (!r.ok) throw new Error('sign-in failed: HTTP ' + r.status);
  return (await r.json()).login;
}

const repoPath = () => `${REPO.owner}/${REPO.name}`;

/**
 * Ask the branch tree whether a file exists before requesting it.
 *
 * Going straight to /contents works, but on a first run it logs a red 404 in the console
 * that means "you have not started yet" — which reads as a fault and gets reported as
 * one. One cheap tree call avoids that, and it yields the sha needed for the next write.
 */
export async function findBlob(token, path) {
  const url = `${API}/repos/${repoPath()}/git/trees/${REPO.branch}?recursive=1`;
  const r = await fetch(url, { headers: headers(token), cache: 'no-store' });
  if (!r.ok) await report(`findBlob GET trees/${REPO.branch}`, r);
  if (r.status === 404 || r.status === 403) throw await diagnose404(token);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const tree = await r.json();
  const hit = (tree.tree || []).find((n) => n.path === path && n.type === 'blob');
  return hit ? hit.sha : null;
}

/**
 * A 404 on the branch tree has two quite different causes and the API will not tell them
 * apart: the token cannot see the repository, or the repository is visible and the BRANCH
 * does not exist. The second is the ordinary state on the very first run, before anyone
 * has contributed anything.
 *
 * This function exists because the first version of this module reported both as "your
 * token cannot see this repository" — which is the same 404-is-ambiguous trap the token
 * advice was written to avoid, reintroduced one level down, and it would have greeted the
 * first contributor with a message about their token when nothing was wrong with it.
 *
 * One extra request settles it: if the repository itself answers, the token is fine.
 */
async function diagnose404(token) {
  try {
    const r = await fetch(`${API}/repos/${repoPath()}`, { headers: headers(token), cache: 'no-store' });
    if (r.ok) {
      return Object.assign(
        new Error(`Your token is fine and the repository is visible, but the branch `
          + `\`${REPO.branch}\` does not exist yet. It has to be created once, by someone `
          + `with push access, before any contribution can be saved. Your work is safe in `
          + `this browser meanwhile, and Export saves it to a file.`),
        { missingBranch: true });
    }
  } catch { /* offline, or the network refused — fall through to the token advice */ }
  return new Error(tokenAdvice(token));
}

/**
 * Read through the blob API, never /contents: that endpoint refuses to return a file
 * over 1 MB, and a working contributor's log will pass it.
 */
export async function readBlob(token, sha) {
  const r = await fetch(`${API}/repos/${repoPath()}/git/blobs/${sha}`,
    { headers: headers(token, 'application/vnd.github.raw'), cache: 'no-store' });
  if (r.status === 404 || r.status === 403) throw await diagnose404(token);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.text();
}

export function toBase64(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = '';
  for (let i = 0; i < bytes.length; i += B64_CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + B64_CHUNK));
  }
  return btoa(bin);
}

/**
 * Write the whole file. The Contents API has no append, so a save is a PUT of everything
 * with the previous sha — which is fine at this size and forces the one-file-per-
 * contributor partitioning that means two people can never touch the same path.
 *
 * A 409 is a conflict, not a failure: the caller pulls, unions by event uuid, retries.
 */
export async function putFile(token, path, text, sha, message) {
  const body = { message, content: toBase64(text), branch: REPO.branch };
  if (sha) body.sha = sha;
  const r = await fetch(`${API}/repos/${repoPath()}/contents/${path}`, {
    method: 'PUT', headers: headers(token), body: JSON.stringify(body),
  });
  if (!r.ok) await report('putFile PUT contents/' + path, r);
  if (r.status === 409) { const e = new Error('conflict'); e.conflict = true; throw e; }
  if (r.status === 404 || r.status === 403) {
    throw new Error(tokenAdvice(token)
      + ' — your work is safe in this browser, and Export saves it to a file');
  }
  if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + (await r.text()).slice(0, 160));
  return (await r.json()).content.sha;
}

/**
 * Create-only: a PUT with no sha creates a file and fails 422 if one already exists.
 * That is a real compare-and-swap on non-existence, and it is what makes the basin hold
 * (phase 4) an actual hold rather than an advisory read-then-write.
 *
 * NOT YET RELIED ON. Documented behaviour this project has not seen with its own eyes;
 * phase 4 verifies it against the live API before anything is built on it.
 */
export async function createOnly(token, path, text, message) {
  const r = await fetch(`${API}/repos/${repoPath()}/contents/${path}`, {
    method: 'PUT', headers: headers(token),
    body: JSON.stringify({ message, content: toBase64(text), branch: REPO.branch }),
  });
  if (r.status === 422) return { created: false };
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return { created: true, sha: (await r.json()).content.sha };
}
