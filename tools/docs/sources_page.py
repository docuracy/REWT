#!/usr/bin/env python3
"""Project `conf/sources.yml` into the data file the documentation renders from.

The manifest is the authority: every input is declared there before anything reads
it, and each declaration carries the attribution its licence requires. Those strings
are obligations rather than courtesies, so the page that discharges them must not be
maintained by hand -- a citations page that drifts from the manifest is a page that
credits the wrong people while looking authoritative, which is this project's own
recurring failure mode.

So the page renders from a projection of the manifest, this script writes it, and
`--check` fails the build when the committed copy has fallen behind. GitHub Pages
runs Jekyll in safe mode: no plugins, and symlinks out of the site source are
ignored, so a real committed file inside `docs/_data/` is the only mechanism
available. Regenerating is therefore a step someone can forget, which is precisely
why `--check` exists.

`notes` is deliberately NOT projected. It is written for whoever is implementing
against the source -- sign conventions, probe results, decision references -- and
belongs to the engineer, not the reader. What each source can and cannot say is
argued on /evidence, in prose written for that purpose.

    python tools/docs/sources_page.py            # write docs/_data/sources.yml
    python tools/docs/sources_page.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

MANIFEST = Path("conf/sources.yml")
TARGET = Path("docs/_data/sources.yml")

# Ordered as the page reads them: what the thing is, who made it, where it lives,
# on what terms, and how far this project has got with it.
PROJECTED = [
    "id", "title", "author", "year", "publisher",
    "url", "homepage", "doi",
    "licence", "attribution", "attribution_constructed", "use_constraint",
    "access", "redistribution", "status", "stage", "used_by",
    "format", "crs", "checksum",
]

BANNER = (
    "# GENERATED FILE -- do not edit.\n"
    "#\n"
    "# Written by tools/docs/sources_page.py from conf/sources.yml, which is the\n"
    "# authority. Edit the manifest and regenerate; an edit made here is lost at the\n"
    "# next run and, worse, silently credits the wrong terms in the meantime.\n"
    "#\n"
    "# `notes` is not projected: it is written for the implementer. See /evidence.\n"
)


def project(manifest: dict) -> dict:
    out = []
    for src in manifest["sources"]:
        row = {k: src[k] for k in PROJECTED if k in src and src[k] is not None}
        # Attribution strings are block scalars in the manifest and pick up a
        # trailing newline; it renders as a stray break in HTML.
        for k in ("attribution", "licence", "use_constraint"):
            if isinstance(row.get(k), str):
                row[k] = " ".join(row[k].split())
        if isinstance(row.get("format"), list):
            row["format"] = ", ".join(str(f) for f in row["format"])
        # `not_established` is a manifest value and reads as one. The page says it in
        # words, and says it from here rather than from a Liquid filter, so that a
        # value nobody has seen yet arrives on the page as itself instead of silently
        # matching nothing.
        row["redistribution_label"] = row["redistribution"].replace("_", " ")

        # WHERE THE CITATION POINTS, decided here rather than by a Liquid filter, because
        # the manifest holds two kinds of URL and only one of them is for a reader.
        # `url` is what the BUILD fetches -- an OGC endpoint, an S3 tile pattern, an API
        # route -- and several of those answer a browser with a 400 or a 500 while being
        # perfectly correct as manifest entries. `homepage` is the human landing page
        # where a publisher offers one. A reader following a citation to a 500 concludes
        # the source is gone, so the homepage wins wherever it exists.
        #
        # And a URL TEMPLATE is not a URL. `{layer}/{z}/{x}/{y}` cannot resolve for
        # anybody, so it is never published as a link -- the page renders the title
        # unlinked instead, which is visibly missing rather than quietly broken (D-077).
        # Today no source reaches that branch, because the one template in the manifest
        # also carries a homepage. That is a fact about today's manifest, which is
        # exactly the kind of thing this project keeps discovering it had relied on.
        link = row.get("homepage") or row.get("url")
        row["link"] = None if (link and ("{" in link or "}" in link)) else link
        out.append(row)
    out.sort(key=lambda r: r["title"].lower())

    # Which sources cannot be redistributed is DERIVED, never asserted in prose. The
    # page used to name "the one that is not settled" in a hand-written sentence, which
    # is true of today's manifest and becomes a lie the day a second one is registered
    # -- and a lie that reads perfectly well, which is the kind this project keeps
    # publishing. Counting here means the page cannot say "the one" when there are two.
    unsettled = [r for r in out if r["redistribution"] != "permitted"]

    # Registered is not the same as used, and the page must not blur them. A source
    # can be declared with its licence researched and its attribution recorded long
    # before anything fetches it -- half the manifest is in that state -- so a page
    # headed "every dataset this project reads" is false for half its own list, and
    # "the credit this project owes" claims a debt not yet incurred. What a release
    # actually owes is published/ATTRIBUTION.md, which is restricted to the sources
    # the build consumed. Counted here so the page states it rather than implying it.
    verified = [r for r in out if r.get("status") == "verified"]

    return {
        "generated_from": str(MANIFEST),
        "generator": "tools/docs/sources_page.py",
        "count": len(out),
        "unsettled_count": len(unsettled),
        "unsettled": unsettled,
        "verified_count": len(verified),
        "sources": out,
    }


def render(data: dict) -> str:
    return BANNER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed file differs from the manifest")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print(f"{MANIFEST} not found -- run from the repository root", file=sys.stderr)
        return 2

    text = render(project(yaml.safe_load(MANIFEST.read_text())))

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} is missing; run tools/docs/sources_page.py", file=sys.stderr)
            return 1
        if TARGET.read_text() != text:
            print(f"{TARGET} is stale: conf/sources.yml has moved on. "
                  f"Run tools/docs/sources_page.py and commit the result.", file=sys.stderr)
            return 1
        print(f"{TARGET} is current against {MANIFEST}.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text)
    print(f"Wrote {TARGET}: {yaml.safe_load(text)['count']} sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
