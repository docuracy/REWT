#!/usr/bin/python3
"""Headless screenshots of the staged check page. No browser window, no foreground tab.

    /usr/bin/python3 tools/router/shot.py            # every stage
    /usr/bin/python3 tools/router/shot.py --stage grid --area severn

SYSTEM PYTHON, DELIBERATELY. playwright is installed for /usr/bin/python3 and not in
the project's .venv, and it is not in requirements.txt. Adding it to the shared venv
would put the environment and the manifest out of agreement, which is the gap I flagged
to the implementer over h3 and should not now create myself. This is a development
instrument outside the build and needs no project dependency.

THE SOFTWARE-GL FLAGS ARE KEPT AS INSURANCE, NOT BECAUSE THEY ARE LOAD-BEARING HERE.
This docstring used to say they were, attributed to rewt-46, who had relayed the recipe
without running it and later measured and corrected their own file. The correction did not
travel: gotw-87 reports four sessions relayed this to them today, two passing on the wrong
version — and I was one of the two, hours after reading the corrected source. A claim
travels faster than its correction (D-099), and correcting your own copy is not the same as
chasing it to the places it was copied to.

MEASURED HERE, on this page, chromium-1217, with `--no-gl-flags` against a normal run:

    with the flags   cells 17,492  net 48,581  coast 64,221  detail 1,056  traces 21  joins 50
    args=[]          cells 17,492  net 48,581  coast 64,221  detail 1,056  traces 21  joins 50

Identical, and `WEBGL_debug_renderer_info` reports the same string either way — ANGLE over
SwiftShader — because this bundled chromium already does in software what the trio asks for.
So on this page they buy nothing today. They stay because they cost nothing, because a
different chromium or a machine with a real GPU and a display may not default the same way,
and because a harness that works by accident of a default is one upgrade from not working.
**`--no-gl-flags` re-measures it in one run; if that ever fails, they are load-bearing again
and this note is wrong.**

CHECK THE HARNESS CAN FAIL. A green run can mean the subject never rendered at all.
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
LAYERS = ["cells", "net", "coast", "seabed", "seabedfine", "thalweg", "detail", "traces", "joins"]
# check.html turned its exclusive stages into four independent toggles, so a shot is
# now of a SET of layers. Each named layer is still shot alone, because a layer that
# draws nothing is invisible in a composite that another layer has filled.


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", action="append", choices=LAYERS)
    ap.add_argument("--stage", action="append", choices=LAYERS,
                    help="deprecated alias for --layer")
    ap.add_argument("--all-on", action="store_true",
                    help="one shot with every layer on, as the page opens it")
    ap.add_argument("--area", default="all")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--timeout", type=int, default=90_000)
    ap.add_argument("--no-gl-flags", action="store_true",
                    help="launch with args=[] — measures whether the software-GL trio is "
                         "actually load-bearing on THIS page, rather than inheriting the "
                         "claim from whoever relayed it")
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
    stages = ["__all__"] if a.all_on else (a.layer or a.stage or LAYERS)
    # A real mapless page, not a flag the page cooperates with: the point is to exercise
    # the timeout path, and a page that politely declines to draw is not the same subject.
    url = (a.url + "join_summary.json".join(["../data/", ""])
           if a.prove_it_fails else a.url)
    bad = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[] if a.no_gl_flags else GL)
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
                sel = LAYERS if st == "__all__" else [st]
                page.evaluate(f"window.setLayers({sel!r})")
                page.wait_for_function(f"window.__drawn > {before}", timeout=a.timeout)
                # `detail` only exists inside a named area — it is the true res-7
                # lattice for whichever area holds the centre of the view. Shooting it at
                # the whole extent reports NOTHING DREW, which is correct and useless.
                if st == "detail" and a.area == "all":
                    page.evaluate("window.zoomTo('severn')")
                    page.wait_for_timeout(1500)
                    page.evaluate("window.setLayers(['detail'])")
                    page.wait_for_timeout(2500)
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
            # The control is now four toggles, so the subject is a SET and the assertion
            # has to compare sets. Comparing against a single name passed every
            # single-layer shot and failed the composite, which is the shape of check
            # that agrees with you until the moment it matters.
            # the legend IS the control now, so the assertion reads the same thing a
            # person does — the switched-on groups in the panel, not a separate row of
            # buttons that no longer exists
            shown = set(page.evaluate(
                "[...document.querySelectorAll('#legend .grp')]"
                ".filter(b=>b.classList.contains('on')).map(b=>b.dataset.s)"))
            if shown != set(sel):
                print(f"FAIL  {st:<10} the page is showing {sorted(shown)}, "
                      f"not {sorted(sel)}")
                bad += 1
                continue
            n = page.evaluate("window.map.queryRenderedFeatures()"
                              ".filter(f=>f.layer.id.startsWith('x-')"
                              " && !f.layer.id.startsWith('x-bg')).length")
            ctrl = page.evaluate(
                "window.map.queryRenderedFeatures("
                "  window.map.project([-1.55,52.60]))"          # inland Warwickshire
                ".filter(f=>f.layer.id.startsWith('x-')"
                " && !f.layer.id.startsWith('x-bg')).length")
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
    # SAY WHICH NUMBER IS WHICH. This printed "FAILED: 4/5" where 4 was the number that
    # PASSED, so the label and the figure disagreed about what was being counted.
    print(f"\n{len(stages)-bad} of {len(stages)} drew"
          + (f"; {bad} FAILED" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
