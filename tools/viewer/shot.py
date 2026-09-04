#!/usr/bin/python3
"""Headless checks of the deployed viewer. No browser window, no foreground tab.

    /usr/bin/python3 tools/viewer/shot.py                 # every check
    /usr/bin/python3 tools/viewer/shot.py --check panel
    /usr/bin/python3 tools/viewer/shot.py --prove-it-fails
    /usr/bin/python3 tools/viewer/shot.py --serve         # start docs/ itself

Run from the repository root. Exits non-zero if any check fails.

WHY THIS EXISTS. Every check I made on this viewer for a day was made by driving
Stephen's own Chrome: it needs his window in the foreground, it is his machine's browser
and not mine, and it cannot run unattended. Stephen asked for Playwright instead. The
recipe is whg3-9a's, by way of rewt-e8, and rewt-c7 got there first with
`tools/router/shot.py` — this is the same shape pointed at the viewer, and where the two
agree it is because I copied them.

SYSTEM PYTHON, DELIBERATELY. playwright is installed for /usr/bin/python3, not in the
project's .venv, and not in requirements.txt. Putting it in the shared venv would set the
environment and the manifest at odds — the exact gap that has been reported twice in this
repository this week. This is a development instrument outside the build.

THREE THINGS THAT ARE LOAD-BEARING, and I got each of them wrong first:

**Software GL, or nothing works and nothing says so.** Headless chromium has no GPU, so
a WebGL map never resolves its sources, `map.loaded()` stays false and `idle` never
fires. Every run then times out on a working page and a broken one alike, which is a
harness that discriminates nothing.

**Wait on the page's own flag, never the library's.** `map.on('load')` fires when the
STYLE is loaded — long before the sources, the tiles, or the page's own fetches.
`viewer.js` sets `window.rewt.ready` as the last statement of its boot, behind `?debug`,
and that is what this waits on. Every wait here is bounded and a timeout is REPORTED, not
raised: "never" is a result, and the report names `styleLoaded` true with `loaded` false,
which is the signature of no-GPU or a hidden tab.

**A check that cannot fail is not a check.** `--prove-it-fails` points the whole harness
at a real page with no map, and every check must fail. Not a flag the page cooperates
with: a page that politely declines to draw is a different subject from one that cannot.
Each content check also carries its own control in the same run — an assertion that
something is ABSENT is worthless unless the same call found something PRESENT (D-082).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "http://127.0.0.1:8021/viewer/?debug"
OUT = ROOT / "docs" / "viewer" / "shots"
GL = ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"]

# Berkhamsted, the Grand Union Canal dead end with two inflows and no outflow that
# Stephen reported in rules/0001.md. Every popup check happens here because it is the
# case the popup work exists for, and a harness aimed at a place nobody cares about
# tests the harness.
NODE = "os:node/7D63F86E-1FBE-4AC3-AEFE-B28073CDAF05"
NODE_AT = (-0.557454, 51.760481)


def wait_ready(page, timeout_ms: int) -> dict:
    """Wait for the viewer's OWN completion flag. Bounded; a timeout is a result."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        state = page.evaluate("""() => ({
            ready: !!(window.rewt && window.rewt.ready),
            hasMap: typeof window.map === 'object' && window.map !== null,
            styleLoaded: !!(window.map && window.map.isStyleLoaded && window.map.isStyleLoaded()),
            loaded: !!(window.map && window.map.loaded && window.map.loaded()),
            hidden: document.hidden,
        })""")
        if state["ready"]:
            return state
        time.sleep(0.25)
    state["timedOut"] = True
    if state["styleLoaded"] and not state["loaded"]:
        state["note"] = ("styleLoaded true with loaded false: the map is getting no "
                         "animation frames. Software GL missing, or a hidden tab.")
    return state


# ── the checks ───────────────────────────────────────────────────────────────
# Each returns (ok, detail). Each carries its own control, because an absence is only
# evidence when the same call has found a presence in the same run.

def check_panel(page) -> tuple[bool, str]:
    """Every figure the panel prints, against published/audit/audit.json."""
    audit = json.loads((ROOT / "published" / "audit" / "audit.json").read_text())
    s = audit["sections"]
    sea = s.get("reachability_tested_against_the_sea", {})
    want = {
        "#f-share": f"{sea.get('reaches_the_sea_share', s['reachability']['in_scope_share']) * 100:.2f}%",
        "#f-defects": f"{s['dead_ends']['defects']:,}",
    }
    got = page.evaluate("""(sel) => Object.fromEntries(
        sel.map(s => [s, (document.querySelector(s) || {}).textContent]))""",
        list(want))
    bad = [f"{k}: page {got.get(k)!r} vs audit {v!r}" for k, v in want.items()
           if got.get(k) != v]
    # CONTROL: the selectors must be able to disagree. A missing element reads as None
    # and would fail above, but an element that is simply never written reads as the
    # placeholder — so check the page is not still showing it.
    if any(got.get(k) in (None, "—", "") for k in want):
        return False, f"the panel never filled: {got}"
    return not bad, "; ".join(bad) or f"{got['#f-share']} and {got['#f-defects']} match the audit"


def check_layers(page) -> tuple[bool, str]:
    """Turn every offered overlay on, and require each to draw something somewhere."""
    res = page.evaluate("""async () => {
        const rows = [...document.querySelectorAll('#layers .switch input')];
        for (const b of rows) { if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); } }
        await new Promise(r => setTimeout(r, 12000));
        const m = window.map;
        const drawn = {}, ids = [];
        for (const l of m.getStyle().layers) ids.push(l.id);
        for (const id of ids) {
            try { drawn[id] = m.queryRenderedFeatures({ layers: [id] }).length; } catch (e) {}
        }
        return { drawn, layerCount: ids.length };
    }""")
    drawn = res["drawn"]
    live = {k: v for k, v in drawn.items() if v > 0}
    # CONTROL: if NOTHING drew, the harness is measuring a blank page rather than a map.
    if not live:
        return False, f"no layer drew anything at all, of {res['layerCount']} in the style"
    return True, f"{len(live)} of {res['layerCount']} style layers drew; network={drawn.get('network', 0)}"


def check_popup(page) -> tuple[bool, str]:
    """R-10/R-11 at Stephen's node: one popup, both links, halo on all three."""
    res = page.evaluate("""async ([lon, lat, nodeId]) => {
        const m = window.map;
        m.jumpTo({ center: [lon, lat], zoom: 17 });
        await new Promise(r => setTimeout(r, 4000));
        m.fire('click', { lngLat: { lng: lon, lat }, point: m.project([lon, lat]),
                          originalEvent: new MouseEvent('click') });
        await new Promise(r => setTimeout(r, 800));
        const pops = document.querySelectorAll('.maplibregl-popup');
        const text = pops[0] ? pops[0].innerText : '';
        const hit = window.rewt.split(window.rewt.hits(m.project([lon, lat])));
        // CONTROL, same run: 300 m away over open ground must find nothing.
        const away = m.project([lon + 0.004, lat + 0.002]);
        const none = window.rewt.split(window.rewt.hits(away));
        return { popups: pops.length, hasNode: text.includes(nodeId),
                 links: hit.links.length, marks: hit.marks.length,
                 halo: (m.getSource('click-halo')._data.features || []).length,
                 controlLinks: none.links.length, controlMarks: none.marks.length };
    }""", [NODE_AT[0], NODE_AT[1], NODE])
    if res["controlLinks"] or res["controlMarks"]:
        return False, f"the control found features over open ground: {res}"
    ok = (res["popups"] == 1 and res["hasNode"] and res["links"] == 2 and res["halo"] == 3)
    return ok, (f"one popup={res['popups'] == 1}, node named={res['hasNode']}, "
                f"links={res['links']} (want 2), halo={res['halo']} (want 3); "
                f"control found nothing")


def check_sightline(page) -> tuple[bool, str]:
    """The three states, counted from the file, and the ray only where there is a hill."""
    res = page.evaluate("""async () => {
        const m = window.map;
        /* TURN IT ON HERE RATHER THAN RELY ON `layers` HAVING RUN. The overlay is off by
           default, so `--check sightline` alone would find no source and report the
           layer missing — a check that passes or fails on the ORDER of the run is a
           check that lies when somebody runs one part of it. */
        if (!m.getSource('sightline')) {
            const row = [...document.querySelectorAll('#layers .switch')]
                .find((r) => /seen from the sea/.test(r.textContent));
            const box = row && row.querySelector('input');
            if (box && !box.checked) { box.checked = true; box.dispatchEvent(new Event('change')); }
            for (let i = 0; i < 40 && !m.getSource('sightline'); i++) {
                await new Promise((r) => setTimeout(r, 500));
            }
        }
        const src = m.getSource('sightline');
        if (!src) return { missing: true };
        const fs = src._data.features;
        const n = { visible: 0, unknown: 0, negative: 0 };
        for (const f of fs) {
            n[f.properties.visible ? 'visible'
              : f.properties.known === false ? 'unknown' : 'negative'] += 1;
        }
        const cen = (g) => { const r = g.coordinates[0];
            return [r.reduce((a, c) => a + c[0], 0) / r.length,
                    r.reduce((a, c) => a + c[1], 0) / r.length]; };
        /* WAIT FOR THE MOVE, NOT FOR A GUESS AT HOW LONG IT TAKES. `project()` before
           the camera has settled returns a screen point for the old view, the synthetic
           click lands on empty water, and BOTH halves of this check then agree — the ray
           is absent for the visible cell and absent for the negative one, which reads as
           a half pass and is really a total miss. That is the failure D-082 is about,
           committed inside the check written to avoid it. So: wait on `idle`, bounded,
           and then assert the click actually HIT the cell before reading the ray. */
        const settle = () => new Promise((res) => {
            const t = setTimeout(res, 15000);
            m.once('idle', () => { clearTimeout(t); res(); });
        });
        const rays = {}, hits = {};
        for (const [label, pick] of [['visible', (f) => f.properties.visible],
                                     ['negative', (f) => !f.properties.visible]]) {
            const f = fs.find(pick);
            const c = cen(f.geometry);
            m.jumpTo({ center: c, zoom: 8 });
            await settle();
            const pt = m.project(c);
            const found = window.rewt.split(window.rewt.hits(pt)).marks
                .filter((x) => x.d.o && x.d.o.id === 'sightline');
            hits[label] = found.length;
            m.fire('click', { lngLat: { lng: c[0], lat: c[1] }, point: pt,
                              originalEvent: new MouseEvent('click') });
            await new Promise(r => setTimeout(r, 600));
            rays[label] = (m.getSource('sightline-ray')._data.features || []).length;
        }
        return { n, rays, hits, total: fs.length };
    }""")
    if res.get("missing"):
        return False, "the sightline layer is not in the style"
    n, rays, hits = res["n"], res["rays"], res["hits"]
    # THE CLICK MUST HAVE LANDED, or "no ray" means "no cell" and the check is measuring
    # empty water. Reported first, because it is the reading that invalidates the rest.
    if hits["visible"] != 1 or hits["negative"] != 1:
        return False, (f"the click missed the cell: sightline features under the point "
                       f"were {hits} (want 1 and 1). The ray readings {rays} say nothing.")
    ok = n["visible"] > 0 and rays["visible"] == 1 and rays["negative"] == 0
    return ok, (f"{res['total']:,} cells: {n['visible']:,} in sight, "
                f"{n['negative']:,} out of sight, {n['unknown']:,} not known; "
                f"both clicks hit their cell; ray drawn for the visible one="
                f"{rays['visible'] == 1}, absent for the other={rays['negative'] == 0}")


CHECKS = {"panel": check_panel, "layers": check_layers,
          "popup": check_popup, "sightline": check_sightline}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="append", choices=list(CHECKS))
    ap.add_argument("--url", default=None)
    ap.add_argument("--port", type=int, default=8021,
                    help="where docs/ is served; --serve starts one here")
    ap.add_argument("--timeout", type=int, default=120_000)
    ap.add_argument("--serve", action="store_true",
                    help="start tools/viewer/serve.py on 8021 for the run and stop it after")
    ap.add_argument("--shot", action="store_true", help="also write a PNG per check")
    ap.add_argument("--prove-it-fails", action="store_true",
                    help="point every check at a page with no map, and require each to fail")
    a = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print(f"playwright is not importable from {sys.executable}. "
              f"Run this with /usr/bin/python3, which has it.", file=sys.stderr)
        return 2

    a.url = a.url or f"http://127.0.0.1:{a.port}/viewer/?debug"
    server = None
    if a.serve:
        # Its OWN port by default, because another session's preview server may already
        # hold 8021 and borrowing it makes this run depend on somebody else's process.
        server = subprocess.Popen([sys.executable, "tools/viewer/serve.py",
                                   "--port", str(a.port)],
                                  cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

    # A real mapless page. The point is to exercise the failure path on a subject that
    # genuinely cannot draw, not on one that has been asked nicely not to.
    url = "data:text/html,<title>no map here</title><h1>no map here" if a.prove_it_fails else a.url
    # A SHORT WAIT WHEN FAILURE IS THE POINT. The mapless page can never become ready,
    # so the full timeout would be two minutes spent confirming what the flag asserts —
    # and a check that is tedious to run is a check that stops being run.
    if a.prove_it_fails:
        a.timeout = min(a.timeout, 8_000)
    names = a.check or list(CHECKS)
    OUT.mkdir(parents=True, exist_ok=True)
    results, rc = [], 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=GL)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(url, wait_until="domcontentloaded")
            state = wait_ready(page, a.timeout)
            if not state["ready"]:
                print(f"the page never became ready: {json.dumps(state)}")
                if not a.prove_it_fails:
                    browser.close()
                    return 1
            for name in names:
                try:
                    ok, detail = CHECKS[name](page)
                except Exception as e:                       # noqa: BLE001
                    ok, detail = False, f"{type(e).__name__}: {e}"
                if a.prove_it_fails:
                    ok = not ok        # on a mapless page, every check MUST fail
                    detail = f"failed as required — {detail}"
                results.append((ok, name, detail))
                if not ok:
                    rc = 1
                if a.shot and not a.prove_it_fails:
                    page.screenshot(path=str(OUT / f"{name}.png"))
            browser.close()
    finally:
        if server:
            server.terminate()

    for ok, name, detail in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {name:10s} {detail}")
    if a.prove_it_fails:
        print("\n--prove-it-fails: every check above was required to FAIL on a page with "
              "no map.\nA green line here means the check can detect its own subject "
              "being absent.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
