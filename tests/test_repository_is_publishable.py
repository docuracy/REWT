"""Nothing licence-encumbered and nothing secret may be committed.

**This repository is private and is intended to become public** (AGENTS.md,
CLAUDE.md). Both of those are properties of the *repository*, not of the build, so
they are checked over what git tracks rather than over what a stage happens to read.

A credential in a public repository is unrecoverable: it is in the history, it is in
every clone and it is in whatever mirrored it before anyone noticed. Rotating the key
is the only remedy and it is not one this project can perform on someone else's
behalf. So this is a test and not a review step.

It matters more than it looks, because contributed records are coming: a tracing tool
whose tile templates have keys substituted into them will, if nothing stops it, commit
those templates. The check is cheap now and irreversible to have skipped.
"""

from __future__ import annotations

import re
import subprocess

import pytest

from rewt import paths

# Assembled from fragments so that this file does not itself match the patterns it
# defines. That keeps the scan over *every* tracked file, including this one, rather
# than carving out an exemption that a real secret could later hide in.
# A bare `token` is included deliberately, and it will occasionally match something
# innocent. The asymmetry justifies it: a false positive costs a reader ten seconds
# and a missed credential cannot be withdrawn from a public history at all.
_KEY = (
    "(?:api[_-]?" + "key|access[_-]?" + "token|auth[_-]?" + "token|"
    "to" + "ken|secret|passwo" + "rd)"
)
_ASSIGNED = re.compile(
    _KEY + r"""\s*[:=]\s*["']?([A-Za-z0-9_\-./+]{12,})["']?""", re.IGNORECASE
)
_IN_QUERY = re.compile(
    r"[?&](?:" + "key|apikey|api_" + "key|token|access_" + "token)=([A-Za-z0-9_\\-]{8,})",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\b" + "Bear" + r"er\s+[A-Za-z0-9_\-.=]{16,}")

# Values that match the shape and are not secrets: placeholders, and the words a
# configuration file uses to say a key is *not* needed.
_INNOCENT = re.compile(
    r"^(?:none|null|false|true|xxx+|todo|tbd|"
    r"(?:example|placeholder|your|my|some|dummy|fake|sample|change[_-]?me)[\w.-]*|"
    r"\$\{[^}]+\}|<[^>]+>|\{\{[^}]+\}\}|not[_-]?required|no[_-]?[\w-]+)$",
    re.IGNORECASE,
)

_SKIP_SUFFIXES = {
    ".gpkg", ".tif", ".tiff", ".zip", ".png", ".jpg", ".jpeg", ".pdf",
    ".shp", ".dbf", ".shx", ".prj", ".cpg", ".ddb", ".parquet",
}


def _tracked_text_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=paths.ROOT, capture_output=True, text=True, check=True,
    ).stdout
    names = [n for n in out.split("\0") if n]
    return [
        n for n in names
        if not any(n.lower().endswith(s) for s in _SKIP_SUFFIXES)
    ]


@pytest.fixture(scope="module")
def tracked():
    files = _tracked_text_files()
    if not files:
        pytest.skip("git tracks no files here; not a checkout")
    return files


def test_no_tracked_file_carries_a_credential(tracked):
    """A key in a public repository is unrecoverable. Rotating it is the only remedy.

    Three shapes are checked: an assignment, a credential in a URL's query string,
    and a bearer token. Placeholders are allowed — `${TOKEN}`, `your-key-here`,
    `none` — because a template that shows where a key would go is documentation and
    not a leak.
    """
    findings = []
    for name in tracked:
        path = paths.ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in (_ASSIGNED, _IN_QUERY, _BEARER):
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(1) if match.groups() else match.group(0)
                if _INNOCENT.match(value.strip()):
                    continue
                findings.append(f"{name}:{lineno}: {line.strip()[:90]}")
                break
    assert not findings, (
        f"{len(findings)} tracked line(s) look like a committed credential. This "
        "repository is intended to become public, and a key that reaches a public "
        "history cannot be withdrawn — it can only be rotated:\n  "
        + "\n  ".join(findings[:10])
    )


def test_the_open_sources_still_need_no_authentication():
    """*The four Ordnance Survey products are open and need no API key. Do not build
    an authentication path you will not use* (AGENTS.md).

    An authentication path that exists is one somebody will eventually put a key
    into.
    """
    from rewt import config

    with_auth = []
    for src in config.sources():
        blob = " ".join(str(v) for v in src.raw.values()).lower()
        if any(word in blob for word in ("api_key", "apikey", "access_token", "oauth")):
            with_auth.append(src.id)
    assert not with_auth, (
        "sources declaring an authentication path: " + ", ".join(with_auth)
    )


def test_no_build_artefact_is_tracked(tracked):
    """*The database is a build artefact, not a source of truth* — gitignored, rebuilt
    from scratch, never hand-edited.

    A committed artefact is one that can disagree with the configuration that
    produced it, which is the stale-cache failure with a longer half-life.
    """
    artefacts = [
        n for n in tracked
        if n.startswith(("db/", "data/interim/", "data/raw/", "published/"))
        and not n.endswith((".gitignore", ".gitkeep", "README.md"))
    ]
    assert not artefacts, (
        "build artefacts are tracked in git: " + ", ".join(artefacts[:10])
        + ". They are rebuilt from scratch; committing one lets it disagree with "
        "the configuration that produced it."
    )


def test_the_curated_judgements_are_tracked(tracked):
    """The other half of the same rule.

    `data/curated/` is a **source of truth**, hand-authored and committed. If the
    judgements are not in git they cannot be diffed, reviewed, or recovered, and the
    product §7 describes does not exist.
    """
    from rewt import curated

    authored = [
        f for f in curated.CLASSES.values() if (paths.CURATED / f).exists()
    ]
    if not authored:
        pytest.skip("no curated file has been authored yet")
    untracked = [f for f in authored if f"data/curated/{f}" not in tracked]
    assert not untracked, (
        "curated judgement files exist but are not tracked in git: "
        + ", ".join(untracked)
        + ". They are the product, not an artefact."
    )


# --------------------------------------------------------------------------
# One place, and only one — the same shape as ids.py's grep
# --------------------------------------------------------------------------

# Each of these is a rule AGENTS.md states in one sentence and that nothing else
# enforces. They are deliberately crude: they read source text rather than reason
# about the code, because the mistake they catch is a shape — an import appearing
# in a second file — and a check that catches the shape is worth more than its
# ugliness costs. The grep for identifiers minted outside rewt/ids.py found a live
# bug on its first run that reading had missed twice.
ONE_PLACE_ONLY = [
    (
        "duckdb",
        r"^\s*(?:import\s+duckdb|from\s+duckdb\b)",
        {"rewt/db.py"},
        "One module owns the database connection; everything else asks it for one. "
        "This is what keeps a move to PostGIS cheap, and it is why there is one "
        "module and not six.",
    ),
    (
        "requests",
        r"^\s*(?:import\s+requests|from\s+requests\b)",
        {"rewt/acquire.py"},
        "Declare every input; hard-code no URL. Sources are fetched by one module, "
        "so an unregistered source is an error rather than a quiet download.",
    ),
    (
        "the export CRS",
        r"crs\.export",
        {"rewt/stages/export.py"},
        "EPSG:27700 throughout; EPSG:4326 only at export. Reproject once, at the "
        "boundary, and nowhere else — a second place is how half a network ends up "
        "in degrees.",
    ),
]


@pytest.mark.parametrize(
    "what,pattern,allowed,why", ONE_PLACE_ONLY, ids=[r[0] for r in ONE_PLACE_ONLY]
)
def test_only_one_module_may_do_it(what, pattern, allowed, why):
    """A rule with exactly one legitimate home, checked by looking for a second."""
    rx = re.compile(pattern, re.MULTILINE)
    offenders = sorted(
        f"{path.relative_to(paths.ROOT)}"
        for path in (paths.ROOT / "rewt").rglob("*.py")
        if str(path.relative_to(paths.ROOT)) not in allowed
        and rx.search(path.read_text(encoding="utf-8"))
    )
    assert not offenders, (
        f"{what} appears outside {', '.join(sorted(allowed))}: "
        + ", ".join(offenders)
        + f". {why}"
    )


def _configured_secrets() -> dict[str, str]:
    """The real values, from the gitignored `.env`. Never printed."""
    env = paths.ROOT / ".env"
    if not env.exists():
        return {}
    out = {}
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if len(value) >= 12:
            out[name.strip()] = value
    return out


def test_no_configured_secret_appears_in_a_tracked_file(tracked):
    """The exact check, which the pattern check cannot be.

    Patterns guess at the shape of a secret. This asks the only question that
    matters: **is the key I actually hold present in a file that would be
    published?** No false positives, no false negatives, and it needs no
    imagination about what a provider calls its parameter.

    It exists because the pattern check has a real gap. `_KEY` requires an `api`
    prefix, so `api_key` matches and a bare `keys` does not — and the viewer's
    server hands the browser exactly that shape:

        {"basemap": ..., "keys": {"maptiler": "<the key>"}}

    Correct while a server reads it from `.env`. Statically there is no server, so
    that response becomes a committed file under `docs/`, which GitHub Pages
    publishes — **public even though this repository is private.** A naive static
    build would create the leak rather than inherit it. Found by rewt-fc in its own
    code before any of it was written.

    The failure names the variable and never the value: a test that prints a secret
    to make its point has published it to every log that captures the run.
    """
    secrets = _configured_secrets()
    if not secrets:
        pytest.skip(
            "no .env present, so there is no configured secret to search for; the "
            "pattern check still runs over every tracked file"
        )
    findings = []
    for name in tracked:
        path = paths.ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for var, value in secrets.items():
            if value in text:
                findings.append(f"{var} appears in {name}")
    assert not findings, (
        "a value from .env is present in a tracked file. It cannot be withdrawn "
        "from a public history — it can only be rotated:\n  " + "\n  ".join(findings)
    )


_BASEMAP_PROVIDER = re.compile(
    r"(maptiler|mapbox|thunderforest|stadiamaps|carto(?:cdn)?)\b[^\n]{0,40}?"
    r"[\"']([A-Za-z0-9_\-]{16,})[\"']",
    re.IGNORECASE,
)



def test_a_basemap_key_cannot_hide_under_a_bare_name(tracked):
    """The pattern check, widened to the shape that slipped past it.

    `_KEY` needs an `api` prefix, so a tile provider's key sitting under `keys`,
    `token` or its own brand name is invisible to it. This looks for a provider's
    name followed closely by an opaque value, which is what a published basemap
    configuration looks like whatever the surrounding key is called.

    Kept separate from the exact check above because the two fail for different
    reasons: this one catches a key nobody has in `.env` — a collaborator's, a
    provider's example that turns out to be live — and the exact one catches ours.
    """
    findings = []
    for name in tracked:
        path = paths.ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            m = _BASEMAP_PROVIDER.search(line)
            if m and not _INNOCENT.match(m.group(2).strip()):
                findings.append(f"{name}:{lineno}: {m.group(1)} … {m.group(2)[:6]}…")
    assert not findings, (
        f"{len(findings)} tracked line(s) put an opaque value beside a tile "
        "provider's name. GitHub Pages serves docs/ publicly even from a private "
        "repository:\n  " + "\n  ".join(findings[:10])
    )
