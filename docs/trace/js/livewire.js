/**
 * Following the printed ink: a cost surface, and a cheapest path confined to a corridor.
 *
 * THIS IS THE OPERATION THE SIX-INCH AFFORDS. Where the surveyor drew a watercourse as a
 * single stroke — a leat, a brook, a narrow cut, which is most of the network — there is no
 * middle to find and the honest assist is to follow the line he drew. Centring (`ink.js`)
 * is the other operation, for where he drew two banks. Which applies is a property of the
 * reach and not of the sheet, and both live on the six-inch.
 *
 * ── WHY A COST SURFACE AND NOT A BLUE MASK ──────────────────────────────────────────
 *
 * The obvious idea is to detect the blue water ink and follow it. Measured over this
 * series, on 40 tiles each centred on an in-scope river link so that water is present in
 * every one: **the median blue fraction is 0.000% and the 90th percentile is 0.000%.**
 * Roughly one sheet in twenty is a coloured printing; the rest are monochrome outline
 * editions, and on those a blue detector finds nothing at all.
 *
 * What makes it tractable is that the distribution is **bimodal** — a tile reads either
 * exactly zero or several per cent, with nothing in between — so which kind of sheet you
 * are on can be decided from the pixels at runtime, per patch, with near-perfect
 * reliability. Classify first, then follow blue where it exists and ink darkness where it
 * does not.
 *
 * ── THE DANGER, AND THE ONE THING THAT MAKES THIS USABLE ────────────────────────────
 *
 * On a monochrome sheet, ink darkness describes roads, railways, contours, hachures and
 * parish boundaries exactly as well as it describes rivers. A shortest path across such a
 * sheet will set off down a turnpike without hesitation and produce a confident, wrong,
 * machine-placed line — the same failure the centring assist has, in a form that covers
 * distance rather than a single vertex.
 *
 * **The corridor is what makes it an assistant rather than an interpreter.** The search is
 * confined to a band around the straight line between the vertex just placed and the one
 * being placed, so the algorithm may only choose among ink the contributor has already
 * pointed at. It cannot leave the corridor, so it cannot go somewhere the person did not
 * indicate. Where the ink runs out, forks, or is crossed by a road, the corridor is what
 * bounds how wrong it can be — and the contributor's remedy is to click more often, which
 * narrows the corridor by shortening it.
 */

import { isBluePixel, classifyPatch, metresPerPixel, patchPixel, patchLonLat } from 'ink';

export const LIVEWIRE_DEFAULTS = {
  /* IN METRES, like everything else here that describes the world. This is how far from
     the straight line the channel is allowed to wander between two clicks — a fact about
     rivers and about how often a person clicks, not about the raster. In pixels it would
     mean 27 m on the six-inch at z17 and 13 m on the 25-inch at z18, so the same click
     pair would be answered differently on the two sheets for no reason anybody chose.
     That error has been made three times in this directory already. */
  corridorM: 26,

  /* Beyond this the corridor covers a large area for a segment whose ends the tracer
     cannot see at once, and the honest answer is a straight line and a suggestion to click
     more often. */
  maxSegmentM: 400,

  /* Ramer–Douglas–Peucker tolerance. A livewire path has one vertex per pixel; this is how
     much of that is worth keeping. About the width of a drawn line, which is ~0.7 m at any
     one scale (see `bankThicknessM` in ink.js), so a metre keeps every real bend and
     discards raster noise. For comparison, D-046 measures OS Open Rivers as keeping bends
     down to about 9 m of amplitude and essentially nothing below — a traced course is
     entitled to be finer than the survey it corrects, but not to carry scanner grain. */
  simplifyM: 1,
};

/**
 * Per-pixel traversal cost. Low is attractive.
 *
 * Cubed rather than linear in luminance, so black ink is emphatically cheaper than grey
 * halftone and paper is prohibitive. A linear ramp lets a path drift across open paper
 * whenever that is geometrically shorter, which is exactly the failure that makes naive
 * shortest-path tracing feel useless.
 */
export function buildCost(patch, coloured) {
  const { data } = patch.data;
  const cost = new Float32Array(patch.width * patch.height);
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    const r = data[i]; const g = data[i + 1]; const b = data[i + 2];
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    const ink = 1 + lum ** 3 * 600;
    /* On a coloured sheet follow the water itself. Ink stays passable — a channel narrows
       to a single drawn line where it is too small to fill — but four times dearer, so
       blue wins wherever blue exists. */
    cost[p] = coloured ? (isBluePixel(r, g, b) ? 1 : 4 * ink) : ink;
  }
  return { cost, width: patch.width, height: patch.height };
}

/* A binary heap, because the alternative in a hot loop is sorting an array on every pop,
   and this runs while the cursor is moving. */
class Heap {
  constructor() { this.k = []; this.v = []; }
  get size() { return this.k.length; }
  push(key, value) {
    this.k.push(key); this.v.push(value);
    let i = this.k.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.k[p] <= this.k[i]) break;
      [this.k[p], this.k[i]] = [this.k[i], this.k[p]];
      [this.v[p], this.v[i]] = [this.v[i], this.v[p]];
      i = p;
    }
  }
  pop() {
    const top = this.v[0];
    const lk = this.k.pop(); const lv = this.v.pop();
    if (this.k.length) {
      this.k[0] = lk; this.v[0] = lv;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1; const r = l + 1; let m = i;
        if (l < this.k.length && this.k[l] < this.k[m]) m = l;
        if (r < this.k.length && this.k[r] < this.k[m]) m = r;
        if (m === i) break;
        [this.k[m], this.k[i]] = [this.k[i], this.k[m]];
        [this.v[m], this.v[i]] = [this.v[i], this.v[m]];
        i = m;
      }
    }
    return top;
  }
}

/** Cheapest path from a to b, confined to a corridor around the straight line. */
export function cheapestPath({ cost, width, height }, a, b, corridorPx) {
  const ax = Math.round(a.x); const ay = Math.round(a.y);
  const bx = Math.round(b.x); const by = Math.round(b.y);
  const inside = (x, y) => x >= 0 && y >= 0 && x < width && y < height;
  if (!inside(ax, ay) || !inside(bx, by)) return null;

  /* A bounding box plus a perpendicular-distance test. The box alone would admit a large
     rectangle for a diagonal segment. */
  const minX = Math.max(0, Math.min(ax, bx) - corridorPx);
  const maxX = Math.min(width - 1, Math.max(ax, bx) + corridorPx);
  const minY = Math.max(0, Math.min(ay, by) - corridorPx);
  const maxY = Math.min(height - 1, Math.max(ay, by) + corridorPx);
  const vx = bx - ax; const vy = by - ay; const vv = vx * vx + vy * vy;
  const near = (x, y) => {
    if (vv === 0) return (x - ax) ** 2 + (y - ay) ** 2 <= corridorPx ** 2;
    let t = ((x - ax) * vx + (y - ay) * vy) / vv;
    t = Math.max(0, Math.min(1, t));
    const dx = x - (ax + t * vx); const dy = y - (ay + t * vy);
    return dx * dx + dy * dy <= corridorPx * corridorPx;
  };

  const dist = new Float64Array(width * height).fill(Infinity);
  const prev = new Int32Array(width * height).fill(-1);
  const done = new Uint8Array(width * height);
  const start = ay * width + ax; const goal = by * width + bx;
  dist[start] = 0;
  const heap = new Heap(); heap.push(0, start);
  const NEI = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];

  while (heap.size) {
    const cur = heap.pop();
    if (done[cur]) continue;
    done[cur] = 1;
    if (cur === goal) break;
    const cx = cur % width; const cy = (cur - cx) / width;
    for (const [dx, dy] of NEI) {
      const nx = cx + dx; const ny = cy + dy;
      if (nx < minX || nx > maxX || ny < minY || ny > maxY) continue;
      if (!near(nx, ny)) continue;
      const ni = ny * width + nx;
      if (done[ni]) continue;
      const nd = dist[cur] + cost[ni] * (dx && dy ? Math.SQRT2 : 1);
      if (nd < dist[ni]) { dist[ni] = nd; prev[ni] = cur; heap.push(nd, ni); }
    }
  }
  if (!Number.isFinite(dist[goal])) return null;

  const path = [];
  for (let i = goal; i !== -1; i = prev[i]) {
    path.push([i % width, Math.floor(i / width)]);
    if (i === start) break;
  }
  return path.reverse();
}

/* Ramer–Douglas–Peucker in PIXEL space, before any conversion to degrees: the tolerance is
   then a statement about the drawn line rather than about degrees, and stays meaningful at
   every latitude. The caller converts a metre tolerance to pixels. */
export function simplify(points, tolerancePx) {
  if (points.length < 3) return points.slice();
  const keep = new Uint8Array(points.length);
  keep[0] = 1; keep[points.length - 1] = 1;
  const stack = [[0, points.length - 1]];
  while (stack.length) {
    const [i0, i1] = stack.pop();
    const [x0, y0] = points[i0]; const [x1, y1] = points[i1];
    const dx = x1 - x0; const dy = y1 - y0;
    const len = Math.hypot(dx, dy) || 1;
    let worst = -1; let worstD = tolerancePx;
    for (let i = i0 + 1; i < i1; i += 1) {
      const [px, py] = points[i];
      const d = Math.abs(dy * px - dx * py + x1 * y0 - y1 * x0) / len;
      if (d > worstD) { worstD = d; worst = i; }
    }
    if (worst !== -1) { keep[worst] = 1; stack.push([i0, worst], [worst, i1]); }
  }
  return points.filter((_p, i) => keep[i]);
}

/**
 * Snap one segment to the ink: from a placed vertex to where the contributor is pointing.
 *
 * @returns {object} always. `{snapped:false, why}` when it declines, so the interface can
 *          say why rather than silently drawing a straight line and leaving the person to
 *          wonder whether the feature is on.
 */
export function snapSegment(patch, fromLonLat, toLonLat, opts = {}) {
  const o = { ...LIVEWIRE_DEFAULTS, ...opts };
  const mPerPx = metresPerPixel(toLonLat[1], patch.zoom);

  const info = patch.classification || (patch.classification = classifyPatch(patch));
  if (!info.usable) {
    return { snapped: false, why: 'this is blank paper — outside the sheet\'s coverage, or '
      + 'the tiles were refused. There is no ink here to follow, and a path across a '
      + 'uniform field would be invented rather than found.' };
  }

  const a = patchPixel(patch, fromLonLat[0], fromLonLat[1]);
  const b = patchPixel(patch, toLonLat[0], toLonLat[1]);
  const spanM = Math.hypot(b.x - a.x, b.y - a.y) * mPerPx;
  if (spanM > o.maxSegmentM) {
    return { snapped: false, spanM,
      why: `that is ${Math.round(spanM)} m in one step. Over that distance the corridor `
        + 'covers too much ground to be a constraint — click more often and the ink can be '
        + 'followed between the clicks.' };
  }

  if (!patch.costed) patch.costed = buildCost(patch, info.coloured);
  const corridorPx = Math.max(4, o.corridorM / mPerPx);
  const path = cheapestPath(patch.costed, a, b, corridorPx);
  if (!path || path.length < 2) {
    return { snapped: false, why: 'no route through the ink inside the corridor' };
  }

  const simplified = simplify(path, Math.max(1, o.simplifyM / mPerPx));
  return {
    snapped: true,
    coordinates: simplified.map(([x, y]) => {
      const ll = patchLonLat(patch, x, y);
      return [ll.lon, ll.lat];
    }),
    /* Which surface was followed, so the annotation can say. `coloured` is the lucky case;
       roughly one sheet in twenty. */
    mode: info.coloured ? 'coloured' : 'monochrome',
    corridorM: o.corridorM,
    pixels: path.length,
    vertices: simplified.length,
  };
}
