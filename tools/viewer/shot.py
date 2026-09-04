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
        /* THE RAY IS GONE, and the check follows the data rather than the other way
           round. The layer computed from the land outwards knows the governing HEIGHT
           of the band that reached a cell, not which summit — so there is no position
           to draw a line to. What is checkable now is that a click lands on a cell and
           the popup names the height that holds it, and says the reach is derived from
           it rather than measured separately. */
        /* A cell that is visible AND not flagged unknowable. Picking merely `visible`
           found one of the 57 cells that are both, whose popup correctly leads with NOT
           KNOWN and never names a height — so the check failed on the viewer doing the
           right thing. */
        const f = fs.find((x) => x.properties.visible && x.properties.known !== false);
        const c = cen(f.geometry);
        m.jumpTo({ center: c, zoom: 8 });
        await settle();
        const pt = m.project(c);
        const found = window.rewt.split(window.rewt.hits(pt)).marks
            .filter((x) => x.d.o && x.d.o.id === 'sightline');
        m.fire('click', { lngLat: { lng: c[0], lat: c[1] }, point: pt,
                          originalEvent: new MouseEvent('click') });
        await new Promise(r => setTimeout(r, 600));
        const pop = document.querySelector('.maplibregl-popup');
        const text = pop ? pop.innerText : '';
        /* CONTROL in the same run: the same probe over land, where the layer has no
           cells at all, must find nothing. Without it "the popup named the height"
           could be true of a page that renders one cell and nothing else. */
        const control = window.rewt.split(window.rewt.hits(m.project([-1.9, 52.5]))).marks
            .filter((x) => x.d.o && x.d.o.id === 'sightline').length;
        return { n, total: fs.length, hit: found.length, control,
                 /* The popup prints the height through `fmt`, which groups thousands:
                    "1,563 m", not "1563 m". Comparing a raw number against formatted
                    text failed on the first cell whose governing land is a kilometre
                    high, and passed for a day on cells under 1,000 m — a check that
                    works on most of the data and not on the interesting end of it. */
                 namesHeight: text.includes(f.properties.gov_h_m.toLocaleString('en-GB') + ' m'),
                 saysDerived: /not\s+a second measurement/.test(text),
                 govHeights: new Set(fs.map((x) => x.properties.gov_h_m)).size };
    }""")
    if res.get("missing"):
        return False, "the sightline layer is not in the style"
    # These keys are THIS check's tally, computed in the page above — not the overlay's
    # `states` labels, which read "in sight" / "out of sight" / "NOT KNOWN". Two tallies
    # of one thing under two vocabularies; reading the wrong one raised a KeyError, which
    # was luck. The same slip against a dict that happened to contain the key would have
    # been a silent zero.
    n = res["n"]
    # THE CLICK MUST HAVE LANDED, or everything after it is a reading of empty water.
    if res["hit"] != 1:
        return False, (f"the click missed: {res['hit']} sightline cells under the point "
                       f"(want 1). Nothing after this means anything.")
    if res["control"] != 0:
        return False, (f"the control found {res['control']} sightline cells over inland "
                       f"Warwickshire, where the layer has none")
    # NOT "all cells are in sight". That was true of the 14,991-cell file for about an
    # hour and false of the 27,130-cell one, and a check that asserts today's shape fails
    # when the shape legitimately changes — the same fault as the hardcoded count it was
    # written beside. What must hold whatever the shape: the layer loaded, the click
    # landed on a cell, the popup named the height that holds it, and it said the reach
    # is derived rather than measured. The composition is REPORTED, not asserted.
    ok = res["total"] > 0 and n["visible"] > 0 and res["namesHeight"] and res["saysDerived"]
    return ok, (f"{res['total']:,} cells: {n['visible']:,} in sight, {n['negative']:,} out, "
                f"{n['unknown']:,} not known, "
                f"{res['govHeights']} distinct governing heights; click named the "
                f"height={res['namesHeight']}, said the reach is derived="
                f"{res['saysDerived']}; control over land found nothing")


def check_mobile(page) -> tuple[bool, str]:
    """Below the breakpoint the map gets the whole screen and the panel is a drawer.

    Measured because "the UI needs better mobile support" is not a specification. Before
    this existed, at 400 px the panel held its fixed 360 px and the map was inset by it:
    15 px of map on an iPhone SE, 4% of the screen, with a legend covering twelve times
    the map's area. There was no `@media` rule in the stylesheet except one for reduced
    motion.

    Against the CLIENT area, not `innerWidth` — the latter includes the scrollbar gutter
    and reported a map that filled the page as 94%, which reads as a bug and is
    arithmetic.
    """
    sizes = [("iPhone SE", 375, 667), ("Pixel 7", 412, 915)]
    out, bad = [], []
    for name, w, h in sizes:
        page.set_viewport_size({"width": w, "height": h})
        page.wait_for_timeout(1200)
        m = page.evaluate("""() => {
            const cw = document.documentElement.clientWidth;
            const r = (s) => { const e = document.querySelector(s);
                return e ? e.getBoundingClientRect() : null; };
            const mp = r('#map'), lg = r('#legend');
            const t = document.querySelector('#panel-toggle');
            const tr = t ? t.getBoundingClientRect() : null;
            return { share: mp ? Math.round(mp.width / cw * 100) : 0,
                     legendShare: (lg && mp) ? Math.round(lg.width * lg.height
                                                          / (mp.width * mp.height) * 100) : null,
                     drawer: !!(t && !t.hidden && getComputedStyle(t).display !== 'none'),
                     touch: tr ? Math.round(Math.min(tr.width, tr.height)) : 0 }; }""")
        out.append(f"{name} {m['share']}% map, legend {m['legendShare']}%, "
                   f"drawer={m['drawer']}, target {m['touch']}px")
        if m["share"] < 95:
            bad.append(f"{name}: the map is {m['share']}% of the screen")
        if not m["drawer"]:
            bad.append(f"{name}: no drawer handle")
        if m["touch"] < 44:
            bad.append(f"{name}: the handle is {m['touch']}px, under a 44px touch target")
        if m["legendShare"] is not None and m["legendShare"] > 25:
            bad.append(f"{name}: the legend covers {m['legendShare']}% of the map")

    # CONTROL, same run: above the breakpoint the desktop layout must come back, or
    # "the map fills the screen" would be true of a viewer that had lost its panel.
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(1200)
    wide = page.evaluate("""() => {
        const cw = document.documentElement.clientWidth;
        const mp = document.querySelector('#map').getBoundingClientRect();
        const t = document.querySelector('#panel-toggle');
        return { share: Math.round(mp.width / cw * 100),
                 drawerHidden: !t || getComputedStyle(t).display === 'none' }; }""")
    if wide["share"] > 90 or not wide["drawerHidden"]:
        return False, (f"at 1400px the desktop layout did not return: map {wide['share']}% "
                       f"of the screen, drawer hidden={wide['drawerHidden']}")
    return not bad, ("; ".join(bad) if bad
                     else " / ".join(out) + f"; at 1400px the panel is back "
                                            f"({wide['share']}% map)")


def check_stamp(page) -> tuple[bool, str]:
    """Every sentence the layer's file carries must reach the page.

    The layer comes from outside the release, so the panel's build fingerprint does not
    cover it and its own properties are the only provenance a reader gets. Those
    properties are rewt-c7's to change and they changed three times today — so this
    asserts the RULE (nothing is dropped) rather than a list of the keys I know about,
    which is the coupling that went stale twice already.
    """
    res = page.evaluate("""async () => {
        const st = window.rewt.stamps.get('sightline');
        if (!st) return { missing: true };
        const note = document.querySelector('#note-sightline');
        const shown = note ? note.innerText : '';
        /* EVERY string the file carries, with no length threshold — the viewer's
           threshold was a number chosen from one day's file, and a short caveat is
           still a caveat. `use_constraint` is checked separately below because it is
           rendered in bold rather than as a sentence. */
        const prose = Object.entries(st)
            .filter(([k, v]) => typeof v === 'string' && k !== 'use_constraint')
            .map(([k, v]) => [k, v]);
        const absent = prose.filter(([, v]) => !shown.includes(v.slice(0, 40))).map(([k]) => k);
        /* AND EVERY NON-STRING MEMBER, by key. The prose rule was fixed once and left
           this half open — numbers and arrays were carried by the file and shown
           nowhere, which is the same hole in the other type. Checked by KEY appearing,
           since a value like 0 or 2 would match half the page by accident. */
        /* A CURATED FIELD RENDERS ITS LABEL, NOT ITS KEY — "furthest any land reaches,
           km" rather than `max_reach_km` — so looking for the key reported five members
           as missing that were on the page all along. The label map comes from the
           viewer itself rather than being restated here, or this check would need
           updating every time a label is reworded, which is the coupling it exists to
           catch. A member is accounted for by its key OR by its label. */
        const labels = new Map(window.rewt.STAMP_FIELDS);
        const scalars = Object.entries(st).filter(([, v]) => typeof v !== 'string');
        const scalarsAbsent = scalars
            .filter(([k]) => !shown.includes(k) && !shown.includes(labels.get(k) || '\u0000'))
            .map(([k]) => k);
        return { prose: prose.length, absent,
                 scalars: scalars.length, scalarsAbsent,
                 constraint: !st.use_constraint || shown.includes(st.use_constraint),
                 // CONTROL: a sentence the file does NOT carry must not be found, or
                 // "everything is shown" would be true of a page showing anything.
                 controlFound: shown.includes('a sentence this file does not contain') };
    }""")
    if res.get("missing"):
        return False, "the sightline layer carries no stamp at all"
    if res["controlFound"]:
        return False, "the control string was found; the match is not discriminating"
    if not res["constraint"]:
        return False, "the file's use_constraint is not on the page"
    if res["scalarsAbsent"]:
        return False, ("members carried by the file and shown nowhere on the page: "
                       + ", ".join(res["scalarsAbsent"]))
    ok = not res["absent"]
    return ok, (f"{res['prose']} prose and {res['scalars']} other members in the file, "
                + (f"all printed on the page" if ok
                   else f"NOT printed: {', '.join(res['absent'])}"))


def check_missing_layer(page) -> tuple[bool, str]:
    """A layer whose file has gone must SAY so, not sit ticked over empty water.

    The sightline layer changed file once today and its predecessor is being deleted, so
    a rename is a live path. Simulated at the fetch, which is the code's own decision
    point, rather than by moving a file somebody else owns.
    """
    res = page.evaluate("""async () => {
        const real = window.fetch;
        window.fetch = (u, o) => (String(u).includes('sightline')
            ? Promise.resolve(new Response('gone', { status: 404 })) : real(u, o));
        const row = [...document.querySelectorAll('#layers .switch')]
            .find((r) => /seen from the sea/.test(r.textContent));
        const box = row.querySelector('input');
        /* RESET FIRST, because `ensure` returns early on a layer it has already loaded —
           so in a full run, where `layers` has switched everything on, the failure path
           never executes and this check passes on nothing having happened. It passed
           when run alone and failed in the suite, which is the order-dependency I fixed
           for the sightline check and then wrote again here an hour later. `window.rewt`
           exposes `loaded` for exactly this. */
        window.rewt.loaded.delete('sightline');
        for (const id of ['sightline', 'sightline-edge']) {
            if (window.map.getLayer(id)) window.map.removeLayer(id);
        }
        if (window.map.getSource('sightline')) window.map.removeSource('sightline');
        box.checked = false;
        // CONTROL, first: with the layer OFF and unbroken, the switch must be usable.
        const before = { checked: box.checked, disabled: box.disabled };
        box.checked = true; box.dispatchEvent(new Event('change'));
        await new Promise((r) => setTimeout(r, 6000));
        window.fetch = real;
        const warn = document.querySelector('#warn');
        return { before,
                 after: { checked: box.checked, disabled: box.disabled },
                 saysWhy: /could not be loaded/.test(row.parentElement.innerText),
                 banner: warn && !warn.hidden && /sightline/.test(warn.innerText),
                 onMap: !!window.map.getLayer('sightline') };
    }""")
    if res["before"]["disabled"]:
        return False, "the switch was already disabled before the failure was injected"
    ok = (not res["after"]["checked"] and res["after"]["disabled"]
          and res["saysWhy"] and res["banner"] and not res["onMap"])
    return ok, (f"switch went back to off={not res['after']['checked']}, "
                f"disabled={res['after']['disabled']}, said why={res['saysWhy']}, "
                f"named in the banner={res['banner']}, nothing on the map="
                f"{not res['onMap']}")


CHECKS = {"panel": check_panel, "layers": check_layers,
          "popup": check_popup, "sightline": check_sightline,
          "stamp": check_stamp, "missing": check_missing_layer,
          "mobile": check_mobile}


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
