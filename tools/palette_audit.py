#!/usr/bin/env python3
"""Measure the viewer's palette for colour vision deficiency.

    python tools/palette_audit.py

Kept because the palette was CHOSEN by this, not checked by it afterwards, and the next
person to add a colour needs the same instrument rather than the same argument. It found
two things eyes had not: the `form` theme collapsing to one colour under deuteranopia
(canal against tidal river, dE 2.5), and the basin ramp running red to green, where
"none of it reaches the sea" and "99% does" measured dE 1.4 — an inverted meaning rather
than a merged one.

It also found the limit that decided the design. Of a 2,149-colour pool, ZERO clear both
the fixed form colours and all five hues that already carry meaning here, at dE > 20
under all four vision types; the constraint only becomes satisfiable at dE > 12, too
weak for a two-pixel line. The map had run out of hue, so provenance moved to pattern —
which is why connectors are dashed, reversals carry arrows and retirements are offset.



Viénot, Brettel & Mollon (1999) for protanopia and deuteranopia; Brettel's
tritanopia plane. Separation is CIEDE2000, which is perceptual rather than
Euclidean-in-RGB — the whole point being that RGB distance says nothing about
whether two lines can be told apart.
"""
import numpy as np, itertools

def hex2rgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i+2], 16) for i in (0, 2, 4)], float) / 255

def lin(c):  return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def unlin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)

# sRGB linear -> LMS (Hunt-Pointer-Estevez, normalised to D65)
RGB2LMS = np.array([[0.31399022, 0.63951294, 0.04649755],
                    [0.15537241, 0.75789446, 0.08670142],
                    [0.01775239, 0.10944209, 0.87256922]])
LMS2RGB = np.linalg.inv(RGB2LMS)

SIM = {
 'protan': np.array([[0, 1.05118294, -0.05116099], [0, 1, 0], [0, 0, 1]]),
 'deutan': np.array([[1, 0, 0], [0.9513092, 0, 0.04866992], [0, 0, 1]]),
 'tritan': np.array([[1, 0, 0], [0, 1, 0], [-0.86744736, 1.86727089, 0]]),
}

def simulate(hexcol, kind):
    if kind == 'normal': return hex2rgb(hexcol)
    lms = RGB2LMS @ lin(hex2rgb(hexcol))
    return unlin(LMS2RGB @ (SIM[kind] @ lms))

def to_lab(rgb):
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = M @ lin(np.clip(rgb, 0, 1)) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])

def de2000(l1, l2):
    L1, a1, b1 = l1; L2, a2, b2 = l2
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7))) if Cb > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dhp = 0.0 if C1p * C2p == 0 else (h2p - h1p + 540) % 360 - 180
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp) / 2)
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0: hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180: hbp = (h1p + h2p) / 2
    else: hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = (-2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
          * np.sin(np.radians(60 * np.exp(-(((hbp - 275) / 25) ** 2)))))
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                   + Rt * (dCp / Sc) * (dHp / Sh))

def sep(h1, h2, kind): return de2000(to_lab(simulate(h1, kind)), to_lab(simulate(h2, kind)))

def audit(name, items, threshold=15.0):
    print(f"\n{name}")
    bad = []
    for (n1, c1), (n2, c2) in itertools.combinations(items, 2):
        worst_kind, worst = min((( k, sep(c1, c2, k)) for k in
                                 ('normal', 'protan', 'deutan', 'tritan')), key=lambda t: t[1])
        if worst < threshold:
            bad.append((worst, worst_kind, n1, c1, n2, c2))
    if not bad:
        print("  every pair separated by more than %.0f under all four" % threshold)
    for w, k, n1, c1, n2, c2 in sorted(bad):
        print(f"  dE {w:5.1f} ({k:6}) {n1} {c1}  vs  {n2} {c2}")
    return bad


PALETTE = {
    'reach': '#1b9ce6', 'canal': '#bb631b', 'lake': '#c6cce7', 'tidal': '#66ffcc',
    'outscope': '#7f8b9c', 'unreached': '#ff2d55', 'add': '#ffd21e', 'rev': '#39e08b',
    'retiredc': '#ff5cf0', 'seed': '#ffffff', 'warn': '#ff9f1c',
}
# Only pairs that can share a screen matter. The themes are mutually exclusive — you
# pick one — so each is audited on its own, against the overlays that sit on top of it.
CO_OCCURRING = {
    "theme 'reach'": ['reach', 'unreached', 'outscope'],
    "theme 'form'": ['reach', 'canal', 'lake', 'tidal', 'add'],
    "theme 'scope'": ['reach', 'canal', 'outscope', 'warn'],
    "theme 'lake'": ['lake', 'warn'],
    "the provenance overlays": ['add', 'rev', 'retiredc'],
}
BASIN_RAMP = ['#ff2d55', '#ff6b35', '#ffb03b', '#ffe066', '#86c8e8', '#1b9ce6']

# Pairs that measure close and are correct anyway, each with the channel that separates
# them instead. Listed rather than silently excluded: an exception nobody can see is
# indistinguishable from a defect nobody noticed.
ACCEPTED = {
    ('add', 'rev'): "connectors are DASHED, reversals are solid with ARROWS — "
                    "pattern separates them, and hue is the redundant second signal",
    ('seed', 'tidal'): "seeds are circles, tidal rivers are lines; the seed layer is "
                       "also off by default",
    ('canal', 'unreached'): "canals are lines; dead-end marks are circles sized by the "
                            "length stranded above them, so shape and size both separate",
}

if __name__ == "__main__":
    unexplained = []
    for name, keys in CO_OCCURRING.items():
        for w, kind, n1, _, n2, _ in audit(name, [(k, PALETTE[k]) for k in keys]):
            if tuple(sorted((n1, n2))) not in {tuple(sorted(k)) for k in ACCEPTED}:
                unexplained.append((name, w, kind, n1, n2))

    # ADJACENT RAMP STOPS ARE SUPPOSED TO BE CLOSE — that is what makes it a ramp rather
    # than a set of categories. Only non-adjacent stops are a finding, and the ends are
    # the whole point of the scale.
    print("\nbasin ramp — non-adjacent stops only")
    for i, j in ((a, b) for a in range(len(BASIN_RAMP)) for b in range(a + 2, len(BASIN_RAMP))):
        w = min(sep(BASIN_RAMP[i], BASIN_RAMP[j], k)
                for k in ('normal', 'protan', 'deutan', 'tritan'))
        if w < 12:
            unexplained.append(("basin ramp", w, "?", f"stop {i}", f"stop {j}"))
            print(f"  dE {w:5.1f}  stop {i} vs stop {j}")
    else:
        print("  every non-adjacent pair above dE 12")

    print("\nThe distinction that matters most on the ramp — its two ends:")
    for k in ('normal', 'protan', 'deutan', 'tritan'):
        print(f"  none reaches vs all reaches, {k:7}: dE "
              f"{sep(BASIN_RAMP[0], BASIN_RAMP[-1], k):5.1f}")

    print("\nAccepted, with the channel that carries the distinction instead:")
    for (a, b), why in ACCEPTED.items():
        print(f"  {a} / {b}: {why}")

    if unexplained:
        print(f"\n{len(unexplained)} UNEXPLAINED pair(s) below threshold:")
        for name, w, kind, n1, n2 in unexplained:
            print(f"  {name}: {n1} vs {n2}, dE {w:.1f} ({kind})")
        raise SystemExit(1)
    print("\nNothing unexplained.")
