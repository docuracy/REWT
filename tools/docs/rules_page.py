#!/usr/bin/env python3
"""Project `conf/rules.yml` into the data file the documentation renders from.

`conf/rules.yml` says of itself that it is the only rendering of the rule list, because
two renderings of one fact drift apart within the hour (D-067). A hand-written rules
page on the site would be exactly that second rendering, and the drift would be
invisible in the direction that matters: a rule the site says is `implemented` while the
build has it `proposed` reads as a promise kept.

So the page renders from a projection, this script writes it, and `--check` fails when
the committed copy has fallen behind. GitHub Pages runs Jekyll in safe mode -- no
plugins, and symlinks out of the site source are ignored -- so a real committed file
inside `docs/_data/` is the only mechanism available, and regenerating is therefore a
step someone can forget. That is what `--check` is for.

WHAT IS NOT PROJECTED, and why. `evidence` and `instances` carry row identifiers --
`rewt:basin/54261d5c6c` and the like -- which a reader cannot resolve and which exist so
that a rule can name a row when challenged (D-074). `implements` and `params` name
modules and dotted parameter paths. All four are written for whoever is implementing the
rule. The reader is told how many rows of evidence a rule stands on, which is the part
that bears on whether to believe it, and the file is named so anyone can go and read the
rest.

    python tools/docs/rules_page.py            # write docs/_data/rules.yml
    python tools/docs/rules_page.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

MANIFEST = Path("conf/rules.yml")
TARGET = Path("docs/_data/rules.yml")

# Ordered as the page reads them: what the rule is, why it exists, where it applies,
# what it waits on, and where it came from.
PROJECTED = [
    "id", "order", "kind", "title", "statement", "why",
    "status", "stage", "needs", "supersedes", "superseded_by",
    "raised", "raised_by", "source", "owner",
]

# Free text in the manifest is written as block scalars, which arrive with newlines
# that render as stray breaks in HTML. Collapsed here rather than in a Liquid filter,
# so the projection is what the page shows.
COLLAPSE = ("title", "statement", "why", "supersedes", "superseded_by")

BANNER = (
    "# GENERATED FILE -- do not edit.\n"
    "#\n"
    "# Written by tools/docs/rules_page.py from conf/rules.yml, which is the only\n"
    "# copy of the rule list. Edit the manifest and regenerate; an edit made here is\n"
    "# lost at the next run and, in the meantime, tells a reader the build does\n"
    "# something it does not do.\n"
    "#\n"
    "# `evidence`, `instances`, `implements` and `params` are not projected: they are\n"
    "# written for whoever implements the rule. See conf/rules.yml.\n"
)


def project(manifest: dict) -> dict:
    out = []
    for rule in manifest["rules"]:
        row = {k: rule[k] for k in PROJECTED if k in rule and rule[k] is not None}
        for k in COLLAPSE:
            if isinstance(row.get(k), str):
                row[k] = " ".join(row[k].split())
        if isinstance(row.get("needs"), list):
            row["needs"] = [" ".join(str(n).split()) for n in row["needs"]]
        # What a rule stands on, as a count rather than as identifiers a reader
        # cannot resolve. Zero is worth showing: a rule with no evidence row is a
        # rule nobody has yet been able to point at a place.
        row["evidence_count"] = len(rule.get("evidence") or [])
        out.append(row)
    out.sort(key=lambda r: r["order"])

    # Counted here rather than asserted in prose on the page. "The rules are not yet
    # applied" is true of today's manifest and becomes a lie the day one is, and it is
    # the kind of lie that reads perfectly well -- which is this project's own
    # recurring failure mode. The page states the tally the file supports.
    by_status: dict[str, int] = {}
    for row in out:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1

    # The vocabulary is projected as a LIST of term/meaning rather than as the mapping
    # it is in the manifest. Liquid can iterate a hash, but it yields two-element
    # arrays subscripted by position, and nothing else on this site does it -- a
    # construct used once is a construct nobody will recognise as broken.
    vocab = manifest.get("vocabulary", {})

    def terms(name: str) -> list[dict]:
        return [{"term": k, "meaning": " ".join(str(v).split())}
                for k, v in (vocab.get(name) or {}).items()]

    return {
        "generated_from": str(MANIFEST),
        "generator": "tools/docs/rules_page.py",
        "version": manifest.get("version"),
        "count": len(out),
        "by_status": by_status,
        "implemented_count": by_status.get("implemented", 0),
        "instance_count": len(manifest.get("instances") or []),
        "status_vocabulary": terms("status"),
        "kind_vocabulary": terms("kind"),
        "rules": out,
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
            print(f"{TARGET} is missing; run tools/docs/rules_page.py", file=sys.stderr)
            return 1
        if TARGET.read_text() != text:
            print(f"{TARGET} is stale: conf/rules.yml has moved on. "
                  f"Run tools/docs/rules_page.py and commit the result.", file=sys.stderr)
            return 1
        print(f"{TARGET} is current against {MANIFEST}.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text)
    print(f"Wrote {TARGET}: {yaml.safe_load(text)['count']} rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
