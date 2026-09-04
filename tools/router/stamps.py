"""A generation stamp must change when the bytes change. This checks that it did.

WHY. `traces.geojson` held 199 features under generation 20260904T193156Z, and then held
200 features under the SAME stamp, because I re-ran one stage under a fixed generation to
correct a miscount and reasoned that the data had not changed. It had. rewt-46's viewer
warns when two loaded layers carry different stamps — a check whose worth depends entirely
on the stamp's discipline, and for one file that day it was worth nothing.

A stamp is a claim: *these artefacts came from one consistent pass*. The claim is only
testable if a stamp is never reused over different content. So this keeps a ledger of
generation -> {file: sha256} and FAILS when a stamp reappears over bytes that have moved.

It does not stop a partial re-run. It stops a partial re-run being SILENT — which is the
part that cost a consumer something.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LEDGER = Path("docs/router/data/stamp_ledger.json")
WATCH = sorted(Path("docs/router/data").glob("*.geojson")) + \
    sorted(Path("docs/router/data").glob("*_summary.json"))


def _stamp(p: Path):
    try:
        d = json.loads(p.read_text())
    except Exception:
        return None
    return (d.get("properties") or d).get("generation")


def check(update: bool = False) -> int:
    led = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    bad = []
    for p in WATCH:
        if p.name == LEDGER.name:
            continue
        g = _stamp(p)
        if not g:
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        prev = led.get(g, {}).get(p.name)
        if prev and prev != h:
            bad.append((p.name, g, prev[:12], h[:12]))
        led.setdefault(g, {})[p.name] = h
    if bad:
        print("STAMP REUSED OVER CHANGED CONTENT — the stamp is asserting a consistency "
              "that does not hold:")
        for name, g, a, b in bad:
            print(f"  {name}  generation {g}  was {a}…  now {b}…")
        print("  A stage was re-run without a new generation. Either rebuild the whole "
              "pass under a fresh stamp, or accept that any consumer holding the earlier "
              "bytes believes it has the current ones.")
    if update:
        LEDGER.write_text(json.dumps(led, indent=1, sort_keys=True))
        print(f"ledger: {sum(len(v) for v in led.values())} entries over "
              f"{len(led)} generations -> {LEDGER}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(check(update="--update" in sys.argv))
