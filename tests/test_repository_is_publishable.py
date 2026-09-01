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
