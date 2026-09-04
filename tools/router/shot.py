#!/usr/bin/python3
"""Headless screenshots of the staged check page. No browser window, no foreground tab.

    /usr/bin/python3 tools/router/shot.py            # every stage
    /usr/bin/python3 tools/router/shot.py --stage grid --area severn

SYSTEM PYTHON, DELIBERATELY. playwright is installed for /usr/bin/python3 and not in
the project's .venv, and it is not in requirements.txt. Adding it to the shared venv
would put the environment and the manifest out of agreement, which is the gap I flagged
to the implementer over h3 and should not now create myself. This is a development
instrument outside the build and needs no project dependency.

THE RECIPE IS whg3-9a's, relayed by rewt-46, and two parts of it are load-bearing:

  Headless chromium has no GPU. Without software GL a WebGL map never resolves its
  sources, `map.loaded()` stays false and `idle` never fires — so every run times out
  on working AND broken pages and the harness discriminates nothing.

  Check the harness can fail. A green run can mean the subject never rendered at all.
  `--prove-it-fails` does exactly that, on purpose, and should be run before a pass is
  believed.

WAIT ON THE PAGE'S OWN FLAG, NOT THE LIBRARY'S (rewt-46). `map.on('load')` fires when
the STYLE loads — long before sources, tiles, or the page's own fetches. check.html
increments `window.__drawn` as the last act of drawing a stage, after `map.once('idle')`.
One flag meaning "this application has finished its own work" beats any library signal.
Every wait is bounded and a timeout is REPORTED rather than raised: "never" is a result.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

URL = "http://127.0.0.1:8021/router/check/"
OUT = Path("docs/router/check/shots")
GL = ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"]
STAGES = ["sightline2", "joins", "traces"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="append", choices=STAGES)
    ap.add_argument("--area", default="all")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--timeout", type=int, default=90_000)
    ap.add_argument("--prove-it-fails", action="store_true",
                    help="load a page with no map at all, to show a pass means something")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright, Error as PWError
    except ModuleNotFoundError:
        print(f"playwright is not importable from {sys.executable}.\n"
              f"Run this with /usr/bin/python3, which has it.", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    stages = a.stage or STAGES
    # A real mapless page, not a flag the page cooperates with: the point is to exercise
    # the timeout path, and a page that politely declines to draw is not the same subject.
    url = (a.url + "join_summary.json".join(["../data/", ""])
           if a.prove_it_fails else a.url)
    bad = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=GL)
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:200]}"))
        page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text[:200]}")
                if m.type == "error" else None)
        page.on("requestfailed", lambda r: errs.append(f"requestfailed: {r.url[-70:]}"))

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PWError as e:
            print(f"FAIL  cannot open {url}: {str(e)[:120]}")
            print("      is the server up?  python3 tools/viewer/serve.py")
            browser.close()
            return 1

        try:
            page.wait_for_function("window.__drawn >= 1", timeout=a.timeout)
        except PWError:
            print("FAIL  the page never finished its first draw")
            browser.close()
            return 1

        for st in stages:
            try:
                # ALWAYS switch, and wait for the counter to MOVE. The first version
                # skipped the switch when the requested stage was the first in the list,
                # so `--stage sightline2` screenshotted the default stage and reported
                # `ok` for a stage it never showed. The feature count was the evidence
                # and I was not checking it against anything.
                before = page.evaluate("window.__drawn")
                page.evaluate(f"window.setStage({st!r})")
                page.wait_for_function(f"window.__drawn > {before}", timeout=a.timeout)
                if a.area != "all":
                    page.evaluate(f"window.zoomTo({a.area!r})")
                    page.wait_for_timeout(1200)
                page.wait_for_function(
                    "window.map && window.map.loaded() && window.map.areTilesLoaded()",
                    timeout=20_000)
            except PWError:
                # a timeout is a RESULT, not a crash: say which wait never finished
                state = page.evaluate(
                    "({drawn: window.__drawn ?? null,"
                    " hasMap: !!window.map,"
                    " styleLoaded: window.map ? window.map.isStyleLoaded() : null,"
                    " loaded: window.map ? window.map.loaded() : null,"
                    " hidden: document.hidden})")
                print(f"FAIL  {st:<10} never finished drawing — {state}")
                if state.get("styleLoaded") and not state.get("loaded"):
                    print("      styleLoaded true with loaded false is the no-GPU / "
                          "hidden-tab signature (rewt-46)")
                bad += 1
                continue

            # CONTENT, NOT JUST COMPLETION: did anything actually draw, and is there a
            # control that draws nothing? An absence means nothing without one.
            # ASSERT THE SUBJECT, not just that something drew. A harness that cannot
            # tell which stage it is looking at will happily pass the wrong one.
            shown = page.evaluate("[...document.querySelectorAll('#stages button')]"
                                  ".find(b=>b.classList.contains('on'))?.dataset.s")
            if shown != st:
                print(f"FAIL  {st:<10} the page is showing {shown!r}, not {st!r}")
                bad += 1
                continue
            n = page.evaluate("window.map.queryRenderedFeatures()"
                              ".filter(f=>f.layer.id.startsWith('x-')"
                              " && !f.layer.id.startsWith('x-coast')).length")
            ctrl = page.evaluate(
                "window.map.queryRenderedFeatures("
                "  window.map.project([-1.55,52.60]))"          # inland Warwickshire
                ".filter(f=>f.layer.id.startsWith('x-')"
                " && !f.layer.id.startsWith('x-coast')).length")
            p = OUT / f"{st}-{a.area}.png"
            page.screenshot(path=str(p))
            flag = "" if n else "   ** NOTHING DREW **"
            if not n:
                bad += 1
            if ctrl:
                flag += f"   ** control drew {ctrl} — inland Warwickshire is not sea **"
                bad += 1
            print(f"{'ok  ' if not flag else 'FAIL'}  {st:<10} {n:>6,} features drawn, "
                  f"control {ctrl}  ->  {p}{flag}")

        browser.close()

    for e in dict.fromkeys(errs):
        print(f"      {e}")
    print(f"\n{'FAILED' if bad else 'all stages drew'}: {len(stages)-bad}/{len(stages)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
