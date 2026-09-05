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

**Software GL — and on THIS machine it turns out not to be needed, which I only found
out by testing a claim I had been repeating.** The received wisdom, from whg3-9a by way
of rewt-e8, is that headless chromium has no GPU, so a WebGL map never resolves its
sources, `map.loaded()` stays false and `idle` never fires — every run then timing out
on a working page and a broken one alike, which is a harness that discriminates nothing.
That is a real failure and worth knowing.

It does not happen here. Measured: with `GL = []` the whole suite still passes — 22 of
33 style layers drew, 17,590 sightline cells rendered, the synthetic click landed. The
bundled chromium is 147.0.7727.15 and already reports
`ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)` with
no flags at all, so the trio below is asking for what it is already doing.

They stay, because they cost nothing, because a different chromium build or a machine
with a real GPU and no display may behave differently, and because a harness that works
by accident of a default is one upgrade from not working. But the comment now says
which of those it is. I had been passing "the flags are load-bearing" to another
session as fact when it was something I had inherited and never run.

**Wait on the page's own flag, never the library's.** `map.on('load')` fires when the
STYLE is loaded — long before the sources, the tiles, or the page's own fetches.
`viewer.js` sets `window.rewt.ready` as the last statement of its boot, behind `?debug`,
and that is what this waits on.

  THE `?debug` READ IS CONTINGENT AND HAS BEEN MEASURED. london-customs-accounts-dd
  injects their flag with `add_init_script` instead, because their app calls
  `updateURLFromFilterState` and throws the query away before `init()` reads it — so
  `?debug` never arrives. This viewer also rewrites its URL, in `writeHash`, which is
  the same shape of hazard. Measured rather than assumed: `history.replaceState(null,
  '', '#' + parts)` resolves a bare fragment against the current URL, so path and query
  both survive, and after four camera moves `location.search` still carries `debug` and
  `window.rewt.ready` is still true. It is NOT changed to an init script, because
  adopting another page's fix for a fault this page does not have is the same error as
  inheriting their flags. But if `writeHash` ever writes a whole URL instead of a
  fragment, this harness goes dark with no symptom but a timeout, and the fix is
  `add_init_script`, theirs. Every wait here is bounded and a timeout is REPORTED, not
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


def wait_ready(page, timeout_ms: int, errors=None) -> dict:
    """Wait for the viewer's OWN completion flag. Bounded; a timeout is a result.

    AND THE RESULT HAS TO SAY ENOUGH TO TELL A SLOW PAGE FROM A DEAD ONE, which is
    london-customs-accounts-dd's refinement and it is earned: their page loads 46
    gzipped volumes into IndexedDB before its table exists, they set the deadline at
    120s and then 300s, and read the timeout as a broken page. It was not — at 300s the
    progress bar was at 20% and climbing, and a cold headless boot there is 5 to 8
    minutes. The bounded wait saved them only because the report happened to carry a row
    count; it did not carry the progress, so their first reading of it was still wrong.

    So the report carries what MOVED as well as what is missing: this viewer's own
    progress line, sampled at the start and at the end of the wait, and the console
    errors seen. A page whose progress text has changed is slow; one where it has not,
    with an error in the console, is dead. "A timeout is a result" is only worth
    anything if the result can distinguish those two.
    """
    # THE BOUND IS ONLY CHECKED BETWEEN ITERATIONS, so one blocking evaluate makes the
    # deadline a suggestion. london-customs-accounts-dd's loop overshot its own by 280
    # seconds and reported a timeout the page had not earned. Mine has the same
    # structure, so the elapsed time and any overshoot are recorded and reported: a
    # wait that ran long is then visible as a fact about the harness rather than
    # attributed to the page.
    #
    # Their other question — whether the poll itself is expensive — I measured rather
    # than assumed, because theirs was awaiting two IndexedDB counts against a database
    # the boot was bulk-writing. Mine calls `isStyleLoaded()` and `loaded()` four times
    # a second, which walk the style's source caches. Median 4.5 ms against a 250 ms
    # sleep, and a cheap `ready`-only probe measures 3.8 ms: no difference worth having.
    # The first run of either shows a ~300 ms maximum, which is browser warm-up and
    # swaps to whichever probe runs first — I had that backwards until I reversed the
    # order. So the poll is NOT split here. Copying their fix would have been the same
    # fault as copying the GL flags: a true finding about another page.
    started = time.time()
    deadline = started + timeout_ms / 1000
    first_progress = page.evaluate(
        "() => (document.querySelector('#loading-what') || {}).textContent || null")
    while time.time() < deadline:
        state = page.evaluate("""() => ({
            ready: !!(window.rewt && window.rewt.ready),
            hasMap: typeof window.map === 'object' && window.map !== null,
            styleLoaded: !!(window.map && window.map.isStyleLoaded && window.map.isStyleLoaded()),
            loaded: !!(window.map && window.map.loaded && window.map.loaded()),
            hidden: document.hidden,
        })""")
        if state["ready"]:
            state["waited_s"] = round(time.time() - started, 1)
            return state
        time.sleep(0.25)
    state["timedOut"] = True
    state["waited_s"] = round(time.time() - started, 1)
    # THE BUDGET BESIDE THE ELAPSED, and the overshoot only when it is material.
    # Recording a 0.1 s overrun on a 0.4 s budget is noise that trains a reader to skip
    # the field; london-customs-accounts-dd's version flags at a second and says what to
    # suspect. Theirs would have turned an 880 s "timeout" into "ran 280 s past its own
    # 600 s deadline", and they would have looked at their loop instead of concluding
    # the site would not load.
    state["budget_s"] = round(timeout_ms / 1000, 1)
    over = time.time() - deadline
    if over > 1.0:
        state["overshot_s"] = round(over, 1)
        state["harness_note"] = (f"this wait ran {round(over, 1)} s past its own "
                                 f"{state['budget_s']} s budget, which means a single "
                                 f"probe blocked for that long. Suspect the harness "
                                 f"before the page.")
    state["progressAtStart"] = first_progress
    state["progressNow"] = page.evaluate(
        "() => (document.querySelector('#loading-what') || {}).textContent || null")
    state["progressMoved"] = state["progressNow"] != first_progress
    state["consoleErrors"] = (errors or [])[:5]
    if state["styleLoaded"] and not state["loaded"]:
        state["note"] = ("styleLoaded true with loaded false: the map is getting no "
                         "animation frames. Software GL missing, or a hidden tab.")
    elif state["progressMoved"]:
        state["note"] = (f"the progress line moved during the wait "
                         f"({first_progress!r} -> {state['progressNow']!r}), so this is a "
                         f"SLOW page and not a dead one: raise --timeout rather than hunt "
                         f"a bug.")
    elif state["progressAtStart"] is not None:
        # A NAMED STAGE IS EVIDENCE EVEN WITHOUT MOVEMENT. The app booted far enough to
        # say what it is doing, so it is alive and stopped HERE — which is a different
        # report from one that never got as far as a progress line. Two samples over a
        # short wait cannot see movement at all, so the stage name is what carries the
        # information when the deadline is tight.
        state["note"] = (f"the page booted and is at {state['progressAtStart']!r}. It did "
                         f"not move during a {timeout_ms} ms wait, which at that length "
                         f"tells you nothing about whether it is slow or stuck — run it "
                         f"again with a longer --timeout before concluding either.")
    elif not state["consoleErrors"]:
        state["note"] = ("no progress line at all and nothing in the console: the page "
                         "never reached the point of saying what it was doing.")
    return state


# ── the checks ───────────────────────────────────────────────────────────────
# Each returns (ok, detail). Each carries its own control, because an absence is only
# evidence when the same call has found a presence in the same run.
#
# AND EACH SETS UP ITS OWN SUBJECT, because three of these have now passed alone and
# failed in the suite — `sightline` when `layers` had not run, `missing` when it had,
# and `edges` when `missing` had disabled the switch it needed. The page is one long
# lived object and every check mutates it: layers get switched on, sources get removed,
# a fetch gets broken on purpose. A check that assumes the state it finds is a check
# whose result depends on what ran before it, and the failure mode is the worst one
# available — it goes GREEN alone, which is how it will be run while it is being
# written, and red only in the suite where somebody will read the message rather than
# the reason.
#
# The rule that survives all three: assert nothing about the state you did not
# establish in this function. Re-enable the switch, wait for VISIBLE rather than
# present. It is more code and it is the difference between a check and a coincidence.
#
# AND THE FIX FOR THAT RULE BROKE THE NEXT RUN, which is worth keeping. The first
# version dropped every layer from `loaded` so `ensure` would rebuild it — including
# layers that were still in the style, where `addLayer` throws on a duplicate id. The
# seams then drew nothing and carried no stamp, and the check reported "no seams drew,
# of None in the file": true, and entirely about my own helper. Forcing a rebuild is not
# the same as asking for one. Restore only what is actually missing.

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
    """Turn every offered overlay on at once, and require the panel to still be telling
    the truth about what is drawn.

    It does NOT require each overlay to draw: the exclusive groups make that impossible
    on purpose, since turning one member on turns its siblings off. The docstring used
    to claim it did, which was a check described as stricter than it was.

    What it does assert is that no layer is VISIBLE while its own switch reads off.
    Turning everything on in one pass is the harshest case for that, because the group
    unchecks siblings whose fetch is still in flight — and `setVisible(false)` cannot
    hide a layer that does not exist yet. This found three layers drawn with their
    switches off, which is the failure the exclusive group exists to prevent, reachable
    by hand: switch on a slow layer, change to another before it lands.
    """
    res = page.evaluate("""async () => {
        const rows = [...document.querySelectorAll('#layers .switch input')];
        for (const b of rows) { if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); } }
        await new Promise(r => setTimeout(r, 20000));
        const m = window.map;
        const drawn = {}, ids = [];
        for (const l of m.getStyle().layers) ids.push(l.id);
        for (const id of ids) {
            try { drawn[id] = m.queryRenderedFeatures({ layers: [id] }).length; } catch (e) {}
        }
        /* The panel against the map, switch by switch. `also` layers follow their
           parent, so ask only about the id the switch itself names. */
        const desync = [];
        for (const b of rows) {
            const id = b.dataset.layer;
            if (!m.getLayer(id)) continue;
            const vis = m.getLayoutProperty(id, 'visibility') !== 'none';
            if (vis !== b.checked) desync.push(`${id} box=${b.checked} visible=${vis}`);
        }
        /* NO FIELD MAY RENDER AS NONSENSE, asserted HERE because this is the only
           check with every layer switched on, so every stamp on the page has been
           rendered. Three kinds of value have reached the page as gibberish — an array
           of records as "NaN, NaN…", a nested object as "[object Object]", and
           undefined — and every one was found by reading the page rather than by a
           check. Asserting it in `stranded`, which loads one layer, would have been
           green while the coastal `coverage` object printed as [object Object]. */
        const panel = document.querySelector('#layers').innerText;
        const nonsense = (panel.match(/NaN|\[object Object\]|undefined/g) || []);
        return { drawn, layerCount: ids.length, desync, nonsense: [...new Set(nonsense)] };
    }""")
    drawn = res["drawn"]
    live = {k: v for k, v in drawn.items() if v > 0}
    # CONTROL: if NOTHING drew, the harness is measuring a blank page rather than a map.
    if not live:
        return False, f"no layer drew anything at all, of {res['layerCount']} in the style"
    if res["desync"]:
        return False, ("the panel and the map disagree: " + "; ".join(res["desync"]))
    if res["nonsense"]:
        return False, ("a stamp field rendered as nonsense on the panel: "
                       + ", ".join(res["nonsense"]))
    return True, (f"{len(live)} of {res['layerCount']} style layers drew; "
                  f"network={drawn.get('network', 0)}; every switch agrees with the map; "
                  f"no stamp field rendered as nonsense")


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


def check_edges(page) -> tuple[bool, str]:
    """The routing graph, its seams, and that it SWITCHES with the cells rather than
    adding to them.

    Stephen asked for a control that switches the sea cells to the routing edges. Two
    things must hold: turning the graph on turns the cells off, and the seams — 59 of
    49,080, 0.12% — actually draw, because a feature that rare is one styling mistake
    from being invisible and nothing else on the page would say so.
    """
    res = page.evaluate("""async () => {
        /* SELF-SUFFICIENT, because this check runs after `missing`, which deliberately
           breaks the sightline fetch and leaves that switch unchecked AND DISABLED with
           its layer removed. Passing alone and failing in the suite is the third time
           an order-dependency has bitten a check I wrote — so this one restores what it
           needs rather than assuming a state, and waits for the layer to be VISIBLE
           rather than merely present. */
        const on = async (label) => {
            const row = [...document.querySelectorAll('#layers .switch')]
                .find((r) => r.textContent.includes(label));
            if (!row) return null;
            const b = row.querySelector('input');
            b.disabled = false;
            /* Drop it from `loaded` ONLY when the layer is genuinely gone — which is
               the state `missing` leaves behind. Doing it unconditionally made `ensure`
               re-run against a layer still in the style, and `addLayer` throws on a
               duplicate id: the seams then drew nothing and carried no stamp, and the
               check reported "no seams drew, of None in the file", which was true and
               was about my own helper. Forcing a rebuild is not the same as asking for
               one. */
            if (!window.map.getLayer(b.dataset.layer)) {
                window.rewt.loaded.delete(b.dataset.layer);
            }
            if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); }
            const vis = () => window.map.getLayer(b.dataset.layer)
                && window.map.getLayoutProperty(b.dataset.layer, 'visibility') !== 'none';
            for (let i = 0; i < 80 && !vis(); i++) {
                await new Promise((r) => setTimeout(r, 500));
            }
            return b.dataset.layer;
        };
        const cells = await on('can be seen from the sea');
        await new Promise((r) => setTimeout(r, 3000));
        const cellsOnFirst = !!window.map.getLayer('sightline')
            && window.map.getLayoutProperty('sightline', 'visibility') !== 'none';
        const graph = await on('routing graph');
        await new Promise((r) => setTimeout(r, 6000));
        const seams = await on('Seams');
        await new Promise((r) => setTimeout(r, 4000));
        window.map.jumpTo({ center: [-4.5, 54.0], zoom: 6 });
        await new Promise((r) => { const t = setTimeout(r, 20000);
            window.map.once('idle', () => { clearTimeout(t); r(); }); });
        const vis = (id) => window.map.getLayer(id)
            && window.map.getLayoutProperty(id, 'visibility') !== 'none';
        return {
            cellsOnFirst,
            cellsOffAfter: !vis('sightline'),
            graphOn: vis('edges'),
            edgesDrawn: window.map.queryRenderedFeatures({ layers: ['edges'] }).length,
            seamsDrawn: window.map.queryRenderedFeatures({ layers: ['edges-seam'] }).length,
            seamsInFile: (window.rewt.stamps.get('edges-seam') || {}).crossing_a_band,
            saysNotARoute: (document.querySelector('#note-edges') || {}).innerText
                ? /ADJACENCY, not a track/.test(document.querySelector('#note-edges').innerText)
                : false,
        };
    }""")
    if not res["cellsOnFirst"]:
        return False, "the cells layer never came on, so the switch proves nothing"
    bad = []
    if not res["cellsOffAfter"]:
        bad.append("turning the graph on did not turn the cells off")
    if not res["graphOn"] or res["edgesDrawn"] == 0:
        bad.append(f"the graph drew {res['edgesDrawn']} links")
    if res["seamsDrawn"] == 0:
        bad.append(f"no seams drew, of {res['seamsInFile']} in the file")
    if not res["saysNotARoute"]:
        bad.append("the panel does not carry the file's 'adjacency, not a track' sentence")
    if bad:
        return False, "; ".join(bad)
    return True, (f"{res['edgesDrawn']:,} links and {res['seamsDrawn']} seams drawn of "
                  f"{res['seamsInFile']} in the file; the cells went off when the graph "
                  f"came on; the panel carries the file's own sentence")


def check_coast(page) -> tuple[bool, str]:
    """The two unaggregated coastal layers draw, AND they exclude each other.

    `layers` counts how many of the style's layers drew; it does not say WHICH, so it
    went green on a build where I had not yet established either of these draws at all.
    Measuring them by name found what a count cannot: my first attempt turned the cells
    on, then the edges, then asked how many cells drew, and got 0 — because the two are
    siblings in the exclusive group and `setVisible` hides rather than removes, so
    `getLayer` still said the layer was there. The layer was present and invisible, and
    the count was my own doing. Hence: one layer on at a time, and the sibling state
    asserted rather than assumed.
    """
    res = page.evaluate("""async () => {
        const solo = async (want) => {
            /* Establish the state this measurement needs — every switch off, then the
               one we are asking about. `missing` may have left a switch disabled with
               its layer removed, so restore both, and only drop from `loaded` when the
               layer is genuinely gone (addLayer throws on a duplicate id). */
            const rows = [...document.querySelectorAll('#layers .switch input')];
            for (const b of rows) {
                if (b.checked) { b.checked = false; b.dispatchEvent(new Event('change')); }
            }
            const box = rows.find((b) => b.dataset.layer === want);
            if (!box) return { error: 'no switch for ' + want };
            box.disabled = false;
            if (!window.map.getLayer(want)) window.rewt.loaded.delete(want);
            box.checked = true; box.dispatchEvent(new Event('change'));
            const vis = () => window.map.getLayer(want)
                && window.map.getLayoutProperty(want, 'visibility') !== 'none';
            for (let i = 0; i < 80 && !vis(); i++) {
                await new Promise((r) => setTimeout(r, 500));
            }
            if (!vis()) return { error: want + ' never became visible' };
            /* The Crouch: inside the 5 km band, and far enough from the Thames that a
               view full of features would not prove the coastal file drew them. */
            window.map.jumpTo({ center: [0.75, 51.62], zoom: 9 });
            await new Promise((r) => { const t = setTimeout(r, 25000);
                window.map.once('idle', () => { clearTimeout(t); r(); }); });
            const others = ['sightline', 'edges', 'coast-cells', 'coast-edges']
                .filter((id) => id !== want && window.map.getLayer(id)
                    && window.map.getLayoutProperty(id, 'visibility') !== 'none');
            const src = window.map.getSource(want);
            return {
                drawn: window.map.queryRenderedFeatures({ layers: [want] }).length,
                inFile: (src && src._data && src._data.features || []).length,
                siblingsVisible: others,
            };
        };
        const cells = await solo('coast-cells');
        const edges = await solo('coast-edges');
        /* THE FAMILY RULE, both directions. Two LINE layers may draw together — that is
           the comparison that shows what the aggregation costs, and rewt-c7 argued for
           it — while a CELL layer clears them, which is the switch Stephen asked for in
           those words. Asserting only the first half would pass on a viewer with no
           rule at all. */
        const on = async (id) => {
            const b = [...document.querySelectorAll('#layers .switch input')]
                .find((x) => x.dataset.layer === id);
            b.disabled = false;
            if (!window.map.getLayer(id)) window.rewt.loaded.delete(id);
            if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); }
            const vis = () => window.map.getLayer(id)
                && window.map.getLayoutProperty(id, 'visibility') !== 'none';
            for (let i = 0; i < 80 && !vis(); i++) await new Promise((r) => setTimeout(r, 500));
            return vis();
        };
        const vis = (id) => !!window.map.getLayer(id)
            && window.map.getLayoutProperty(id, 'visibility') !== 'none';
        await on('coast-edges');
        await on('edges');
        const linesTogether = vis('edges') && vis('coast-edges');
        await on('sightline');
        const cellClearedLines = !vis('edges') && !vis('coast-edges');
        const note = document.querySelector('#note-coast-cells');
        const txt = note ? note.innerText : '';
        const panel = document.querySelector('#layers').innerText;
        /* READ THE SENTENCE FROM THE FILE, DO NOT TYPE ITS NUMBER HERE. This asked for
           the literal "32 connected components" — rewt-c7's figure frozen in my check,
           the exact fault I had just warned them about. It survived their rebuild by
           luck: the count happened to still be 32. The file now supplies the sentence
           and the check asserts the page is carrying it, so a rebuild that changes the
           number passes and a page that stops printing it fails. */
        const norm = (t) => t.replace(/\s+/g, ' ').trim();
        const props = (await (await fetch('../router/data/cells_r7_coast.geojson')).json())
            .properties || {};
        const band = props.this_layer_is_a_band_not_a_surface || '';
        const ext = props.extent_deliberately_differs || '';
        return { cells, edges, linesTogether, cellClearedLines,
            bandSentenceInFile: !!band,
            saysComponents: !!band && norm(panel).includes(norm(band)),
            saysExtentDiffers: !!ext && norm(panel).includes(norm(ext)) };
    }""")
    bad = []
    for name in ("cells", "edges"):
        r = res[name]
        if r.get("error"):
            bad.append(f"{name}: {r['error']}")
            continue
        if r["drawn"] == 0:
            bad.append(f"{name} drew nothing, of {r['inFile']:,} in the file")
        if r["siblingsVisible"]:
            bad.append(f"{name} left {', '.join(r['siblingsVisible'])} visible beside it, "
                       "so the group does not switch")
    if not res["linesTogether"]:
        bad.append("the aggregated graph and the coastal lattice will not draw together, "
                   "so the comparison the note invites is impossible")
    if not res["cellClearedLines"]:
        bad.append("turning a cell layer on left the line layers drawn, so a hexagon and "
                   "the lines between hexagon centres are on the map at once")
    if not res["bandSentenceInFile"]:
        bad.append("the coastal file no longer carries `this_layer_is_a_band_not_a_surface`, "
                   "so there is no sentence to check the page against")
    elif not res["saysComponents"]:
        bad.append("the panel does not carry the file's own 'band not a surface' sentence")
    if not res["saysExtentDiffers"]:
        bad.append("the panel does not carry the file's `extent_deliberately_differs`")
    if bad:
        return False, "; ".join(bad)
    c, e = res["cells"], res["edges"]
    return True, (f"{c['drawn']:,} cells of {c['inFile']:,} and {e['drawn']:,} links of "
                  f"{e['inFile']:,} drew on the Crouch; two line layers draw together, a "
                  f"cell layer clears them; the panel carries both of the file's own "
                  f"caveats verbatim")


def check_joins(page) -> tuple[bool, str]:
    """The joins layer draws BOTH its geometries, and the counts agree two ways.

    This is the file rewt-c7's own check page drew as a line layer, losing all 230 of
    its points — Stephen read the gap as missing joins on the Crouch. It is also where
    a published summary said 45/115/229 while the file held 44/115/230, because the
    land-crossing demotion ran after the counts were taken. Both faults are invisible
    from one view of the data, so this takes two: by `rule` and by geometry type, which
    must agree.
    """
    res = page.evaluate("""async () => {
        const row = [...document.querySelectorAll('#layers .switch')]
            .find((r) => /joined to the sea grid/.test(r.textContent));
        if (!row) return { missing: true };
        const b = row.querySelector('input');
        b.disabled = false;
        if (!window.map.getLayer('joins')) window.rewt.loaded.delete('joins');
        if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); }
        for (let i = 0; i < 80 && !window.map.getSource('joins'); i++) {
            await new Promise((r) => setTimeout(r, 500));
        }
        const m = window.map;
        const src = m.getSource('joins');
        if (!src) return { missing: true };
        const fs = src._data.features;
        const byRule = {}, byGeom = {};
        for (const f of fs) {
            byRule[f.properties.rule] = (byRule[f.properties.rule] || 0) + 1;
            byGeom[f.geometry.type] = (byGeom[f.geometry.type] || 0) + 1;
        }
        m.jumpTo({ center: [-2.5, 53.5], zoom: 5 });
        await new Promise((r) => { const t = setTimeout(r, 25000);
            m.once('idle', () => { clearTimeout(t); r(); }); });
        return { byRule, byGeom, total: fs.length,
                 pointLayer: m.queryRenderedFeatures({ layers: ['joins'] }).length,
                 lineLayer: m.getLayer('joins-line')
                     ? m.queryRenderedFeatures({ layers: ['joins-line'] }).length : null };
    }""")
    if res.get("missing"):
        return False, ("the joins layer never loaded. A source that MapLibre rejects "
                       "produces no layer and no visible error — check the console and "
                       "the source spec, not the data")
    r, g = res["byRule"], res["byGeom"]
    if r.get("3") != g.get("Point") or (r.get("1", 0) + r.get("2", 0)) != g.get("LineString"):
        return False, (f"the two views disagree: by rule {r}, by geometry {g} — a "
                       f"published summary already got this wrong once")
    if not res["pointLayer"] or not res["lineLayer"]:
        return False, (f"only one geometry drew: {res['pointLayer']} points and "
                       f"{res['lineLayer']} lines. This is the fault that lost 230 joins.")
    return True, (f"{res['total']} joins, by rule {r} and by geometry {g} — the two views "
                  f"agree; {res['pointLayer']} points and {res['lineLayer']} lines drawn")


def check_stranded(page) -> tuple[bool, str]:
    """The thirty river mouths with no way to the sea, and the answer they belong to.

    Stephen's expectation is that the sea grid, the joins, the traces and the inland
    network form ONE D8 network. rewt-c7 measured it instead of asserting it, and the
    answer is "not yet" — 81.72% of in-scope river nodes reach the sea. This asserts the
    map draws exactly the population the file names, and that the page carries the
    answer rather than my summary of it.

    The count is read from the file in the SAME RUN, not written here: thirty is today's
    number and rewt-c7 says in `provisional` that it moves when R-01 lands. A check that
    froze it would fail on a correct rebuild.
    """
    res = page.evaluate("""async () => {
        const b = [...document.querySelectorAll('#layers .switch input')]
            .find((x) => x.dataset.layer === 'stranded');
        if (!b) return { error: 'no switch for the stranded layer' };
        b.disabled = false;
        if (!window.map.getLayer('stranded')) window.rewt.loaded.delete('stranded');
        if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); }
        for (let i = 0; i < 80 && !window.map.getLayer('stranded'); i++) {
            await new Promise((r) => setTimeout(r, 500));
        }
        if (!window.map.getLayer('stranded')) return { error: 'the layer never appeared' };
        /* The whole of Great Britain, so every stranded terminus is in view at once and
           a count of what is drawn can be compared with the file's own list. */
        window.map.jumpTo({ center: [-3.0, 54.5], zoom: 4.4 });
        await new Promise((r) => { const t = setTimeout(r, 25000);
            window.map.once('idle', () => { clearTimeout(t); r(); }); });
        const net = await (await fetch('../router/data/network_summary.json')).json();
        const drawn = window.map.queryRenderedFeatures({ layers: ['stranded'] });
        const ids = new Set(drawn.map((f) => f.properties.node_id));
        const listed = new Set((net.stranded || []).map((x) => x.node_id));
        const panel = document.querySelector('#layers').innerText;
        return {
            listed: listed.size,
            drawnDistinct: ids.size,
            notListed: [...ids].filter((i) => !listed.has(i)).length,
            /* The file's own answer, not mine. */
            saysAnswer: panel.includes(net.answer),
            saysPct: panel.includes(String(net.in_scope_pct_reaching_the_sea)),
            saysProvisional: /R-01 unbuilt/.test(panel),
            /* NO FIELD MAY RENDER AS NONSENSE. Three kinds of value have reached
               the page as gibberish rather than as a number: an array of records as
               "NaN, NaN…", a nested object as "[object Object]", and undefined. Each
               was found by reading the page, never by a check, so the check is here
               now and it is about the whole panel rather than one layer's field. */
            noNaN: !/NaN|\[object Object\]|undefined/.test(panel),
        };
    }""")
    if res.get("error"):
        return False, res["error"]
    bad = []
    if res["drawnDistinct"] != res["listed"]:
        bad.append(f"{res['drawnDistinct']} stranded termini drew, of {res['listed']} "
                   "the file lists")
    if res["notListed"]:
        bad.append(f"{res['notListed']} drawn termini are not in the file's list")
    if not res["saysAnswer"]:
        bad.append("the panel does not carry the file's own answer to the one-network question")
    if not res["saysPct"]:
        bad.append("the panel does not carry the percentage reaching the sea")
    if not res["saysProvisional"]:
        bad.append("the panel does not say the population is provisional on R-01")
    if not res["noNaN"]:
        bad.append("a stamp field rendered as nonsense (NaN, [object Object] or undefined)")
    if bad:
        return False, "; ".join(bad)
    return True, (f"{res['drawnDistinct']} of {res['listed']} stranded termini drawn and "
                  f"none unlisted; the panel carries the file's answer, its "
                  f"percentage and its R-01 caveat")


def check_generations(page) -> tuple[bool, str]:
    """Two router layers from different passes must SAY SO on the page.

    rewt-c7 stamps every artefact with a generation precisely so a reader holding two of
    them can tell whether they came from one run, and the viewer is the only place two
    are ever open at once. The mechanism has caught its author twice — once on two
    layers an hour and a half apart, once on a stamp held still across a partial re-run
    while the bytes moved underneath it.

    Today the honest state is three stamps: the sightline surface is legitimately behind
    because nothing it depends on has moved. Both of us know that, and that is exactly
    why the warning is not suppressed — a reader who knows neither of us should still be
    told. A warning nobody can see is worth nothing, so this asserts it appears and
    names both generations rather than trusting that it would.

    The generations are read from the files in the same run. Writing today's stamps in
    here would be the frozen-constant fault this check exists alongside.
    """
    res = page.evaluate("""async () => {
        const on = async (id) => {
            const b = [...document.querySelectorAll('#layers .switch input')]
                .find((x) => x.dataset.layer === id);
            if (!b) return false;
            b.disabled = false;
            if (!window.map.getLayer(id)) window.rewt.loaded.delete(id);
            if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); }
            for (let i = 0; i < 80 && !window.map.getLayer(id); i++) {
                await new Promise((r) => setTimeout(r, 500));
            }
            return !!window.map.getLayer(id);
        };
        const gen = async (f) => ((await (await fetch('../router/data/' + f)).json())
            .properties || {}).generation;
        const [a, b] = [await gen('sightline2_r6.geojson'), await gen('traces.geojson')];
        const bothOn = (await on('sightline')) && (await on('traces'));
        await new Promise((r) => setTimeout(r, 3000));
        const note = document.querySelector('#router-generations');
        const warn = document.querySelector('#warn');
        const text = note ? note.innerText : '';
        return { a, b, bothOn,
            differ: !!a && !!b && a !== b,
            shown: !!note && !!warn && !warn.hidden,
            namesBoth: text.includes(a || '\u0000') && text.includes(b || '\u0000') };
    }""")
    if not res["bothOn"]:
        return False, "could not get both layers on, so the comparison proves nothing"
    if not res["differ"]:
        # A LEGITIMATE STATE, not a pass by default: say which it was.
        return True, (f"both layers carry {res['a']}, so there is nothing to warn about "
                      "— the warning was not exercised")
    if not res["shown"]:
        return False, (f"{res['a']} and {res['b']} are loaded together and the page says "
                       "nothing about it")
    if not res["namesBoth"]:
        return False, "the warning appears but does not name both generations"
    return True, (f"{res['a']} and {res['b']} loaded together; the page warns and names "
                  "both")


def check_renderers(page) -> tuple[bool, str]:
    """EVERY non-scalar property rewt-c7 publishes, rendered through the viewer's own
    formatter — not just the ones on layers this harness happens to load.

    Three of their structured values reached readers as gibberish before anyone rendered
    the rest: an array of records as "NaN, NaN…", a nested object as "[object Object]",
    and a ratio of 1.895 rounded to "2". The first two announce themselves. The third
    does not, which is why this asserts precision as well as legibility — a rounded
    ratio reads as a measurement and is the only one of the three a reader would repeat.

    The population is globbed from disk here rather than named, because rewt-c7's
    artefacts are theirs to add to and a list of the keys I know about is the coupling
    that goes stale. It found 33 where their own count was 28.
    """
    import glob
    import json as _json
    import os
    pop = []
    for f in sorted(glob.glob("docs/router/data/*.json")) + \
            sorted(glob.glob("docs/router/data/*.geojson")):
        try:
            d = _json.load(open(f))
        except Exception as e:
            return False, f"{os.path.basename(f)} did not parse: {e}"
        props = d.get("properties", d if isinstance(d, dict) else {})
        if not isinstance(props, dict):
            continue
        for k, v in props.items():
            if isinstance(v, (dict, list)):
                pop.append({"file": os.path.basename(f), "key": k, "value": v})
    if not pop:
        # CONTROL: an empty population would pass every assertion below.
        return False, "no non-scalar properties found at all, so nothing was rendered"
    res = page.evaluate("""(pop) => {
        if (typeof window.rewt.stampValue !== 'function') {
            return { noRenderer: true };
        }
        const bad = [];
        /* Does this value contain a fraction THE RENDERER UNDERTAKES TO PRINT? Checked
           against the input, so the assertion is about what the file said rather than
           what came out — the direction that catches a silent rounding.

           It must mirror the renderer's own contract or it invents faults. The first
           version did: an array of RECORDS is deliberately summarised as "230 listed —
           see the map", so it has no decimal point by design, and the check called that
           lost precision on three of rewt-c7's files. A count is not a rounding. */
        const hasFraction = (v) => {
            if (typeof v === 'number') return !Number.isInteger(v);
            if (Array.isArray(v)) {
                // Records are counted, not rendered — nothing inside them is promised.
                return v.every((n) => typeof n === 'number') && v.some(hasFraction);
            }
            if (v && typeof v === 'object') return Object.values(v).some(hasFraction);
            return false;
        };
        for (const p of pop) {
            let s;
            try { s = String(window.rewt.stampValue(p.value)); }
            catch (e) { bad.push(`${p.file}:${p.key} threw ${e.message}`); continue; }
            if (/NaN|\[object Object\]|undefined/.test(s)) {
                bad.push(`${p.file}:${p.key} rendered as ${s.slice(0, 40)}`);
            } else if (s === '') {
                bad.push(`${p.file}:${p.key} rendered as nothing at all`);
            } else if (hasFraction(p.value) && !/\./.test(s)) {
                /* A fractional input that comes out with no decimal point anywhere has
                   been rounded away. rewt-c7's detour percentiles did exactly this. */
                bad.push(`${p.file}:${p.key} lost its precision: ${s.slice(0, 40)}`);
            }
        }
        return { bad, checked: pop.length };
    }""", pop)
    if res.get("noRenderer"):
        return False, "the viewer does not expose stampValue, so nothing could be rendered"
    if res["bad"]:
        return False, "; ".join(res["bad"][:4]) + (
            f" (and {len(res['bad']) - 4} more)" if len(res["bad"]) > 4 else "")
    return True, (f"{res['checked']} non-scalar properties rendered; none as NaN, "
                  f"[object Object], undefined or nothing, and none rounded away")


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


def check_geometry_coverage(page) -> tuple[bool, str]:
    """Every geometry type in a source must have a layer that can draw it.

    MapLibre draws NOTHING for a geometry its layer type cannot render and reports no
    error. rewt-c7 lost 225 of 389 joins to this today — a Point layer's features on a
    line layer — and read the gap as missing data on the Crouch and the Blackwater. The
    same fault was in this viewer on `corrections`: 1,205 LineStrings and 355 Points in
    one file, drawn by a single circle layer, so two thirds of the curated judgements
    had never appeared, under a panel label reading 1,560.

    `layers` could not catch it: it asks whether a layer drew ANYTHING, and a partly
    drawn layer draws something. This asks whether every type present in the source is
    claimed by some layer reading that source.
    """
    res = page.evaluate("""async () => {
        const rows = [...document.querySelectorAll('#layers .switch input')];
        for (const b of rows) { if (!b.checked && !b.disabled) {
            b.checked = true; b.dispatchEvent(new Event('change')); } }
        await new Promise((r) => setTimeout(r, 14000));
        const m = window.map, out = [];
        const style = m.getStyle();
        for (const id of Object.keys(style.sources)) {
            const src = m.getSource(id);
            const data = src && src._data;
            if (!data || !data.features) continue;              // tiled, not GeoJSON
            const present = new Set(data.features.map((f) => f.geometry && f.geometry.type));
            const layers = style.layers.filter((l) => l.source === id);
            const drawable = new Set();
            for (const l of layers) {
                if (l.type === 'line') { drawable.add('LineString'); drawable.add('MultiLineString'); }
                if (l.type === 'fill') { drawable.add('Polygon'); drawable.add('MultiPolygon'); }
                if (l.type === 'circle') { drawable.add('Point'); drawable.add('MultiPoint'); }
                // A symbol layer can place on any geometry, so it claims whatever is there.
                if (l.type === 'symbol') for (const t of present) drawable.add(t);
            }
            const orphan = [...present].filter((t) => t && !drawable.has(t));
            if (orphan.length) {
                out.push({ source: id, orphan,
                           lost: data.features.filter((f) => f.geometry
                                 && orphan.includes(f.geometry.type)).length,
                           of: data.features.length,
                           layerTypes: layers.map((l) => l.type) });
            }
        }
        // CONTROL: the sweep must have looked at something, or an empty answer is
        // "no GeoJSON sources loaded" rather than "nothing is orphaned".
        const examined = Object.keys(style.sources)
            .filter((id) => m.getSource(id) && m.getSource(id)._data
                            && m.getSource(id)._data.features).length;
        return { orphans: out, examined };
    }""")
    if res["examined"] == 0:
        return False, "no GeoJSON source was examined, so this check measured nothing"
    if res["orphans"]:
        worst = "; ".join(f"{o['source']}: {o['lost']:,} of {o['of']:,} features are "
                          f"{'/'.join(o['orphan'])} with only {'/'.join(o['layerTypes'])} "
                          f"layers on it" for o in res["orphans"])
        return False, worst
    return True, (f"{res['examined']} GeoJSON sources examined; every geometry type "
                  f"present in each has a layer that can draw it")


def check_stamp(page) -> tuple[bool, str]:
    """Every sentence the layer's file carries must reach the page.

    The layer comes from outside the release, so the panel's build fingerprint does not
    cover it and its own properties are the only provenance a reader gets. Those
    properties are rewt-c7's to change and they changed three times today — so this
    asserts the RULE (nothing is dropped) rather than a list of the keys I know about,
    which is the coupling that went stale twice already.
    """
    res = page.evaluate("""async () => {
        /* ESTABLISH THE STATE, DO NOT INHERIT IT. This read the stamp straight out of
           `window.rewt.stamps` and reported "no stamp at all" when the layer had not
           been loaded — so it passed in the full suite only because the `sightline`
           check happens to run before it, and failed the moment the checks were run in
           a different grouping. That is the fourth order-dependency in this file and
           the same one each time: a green result that belonged to its neighbours.
           `missing` may also have left this switch disabled with its layer removed. */
        const b = [...document.querySelectorAll('#layers .switch input')]
            .find((x) => x.dataset.layer === 'sightline');
        if (!b) return { missing: true, why: 'no switch for the sightline layer' };
        b.disabled = false;
        if (!window.map.getLayer('sightline')) window.rewt.loaded.delete('sightline');
        if (!b.checked) { b.checked = true; b.dispatchEvent(new Event('change')); }
        for (let i = 0; i < 80 && !window.rewt.stamps.get('sightline'); i++) {
            await new Promise((r) => setTimeout(r, 500));
        }
        const st = window.rewt.stamps.get('sightline');
        if (!st) return { missing: true, why: 'the layer never loaded its stamp' };
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
        return False, res.get("why", "the sightline layer carries no stamp at all")
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
          "edges": check_edges, "coast": check_coast,
          "stranded": check_stranded,
          "generations": check_generations,
          "renderers": check_renderers, "mobile": check_mobile,
          "geometry": check_geometry_coverage, "joins": check_joins}


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
    # SO THAT THIS FILE RECORDS A MEASUREMENT OF ITS OWN PAGE RATHER THAN A CITATION OF
    # SOMEBODY ELSE'S. The software-GL flags came to me from whg3-9a by way of rewt-e8 as
    # "load-bearing", I passed that on as fact, and I had never run it. When I did, the
    # suite passed without them. The comment at the top of this file says so — but a
    # comment is a claim a reader must trust, and by then four sessions had relayed the
    # uncorrected version and two still held it.
    #
    # THE IDEA IS rewt-c7's AND I DID NOT KNOW IT WHEN I WROTE THIS. gotw-87 told me
    # "your --no-gl-flags switch", so I built one, believing it to be mine and new. It
    # was rewt-c7's, in tools/router/shot.py, and had been for hours; gotw-87's own
    # write-up credits them correctly and only the message to me did not. So this switch
    # is an independent implementation of somebody else's idea, made by a session who had
    # been told he already had it — the same misattribution the switch exists to prevent,
    # committed one hop away while we were all writing about it.
    #
    # A switch is the difference between a quotation and an experiment: anyone wondering
    # whether the flags matter ON THEIR MACHINE runs the suite twice and finds out in
    # four minutes, instead of believing me, or believing whg3-9a through me.
    ap.add_argument("--no-gl-flags", action="store_true",
                    help="launch with no software-GL flags, to find out whether this "
                         "machine needs them rather than taking it on trust")
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
            launch_args = [] if a.no_gl_flags else GL
            if a.no_gl_flags:
                print("launching with NO software-GL flags; if the suite passes, this "
                      "machine does not need them")
            browser = pw.chromium.launch(args=launch_args)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.goto(url, wait_until="domcontentloaded")
            state = wait_ready(page, a.timeout, errors)
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
