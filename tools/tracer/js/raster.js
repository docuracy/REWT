/**
 * Reading the sheet underneath the map: tile mosaic, cost surface, livewire.
 *
 * WHY NOT READ THE MAP'S OWN CANVAS. MapLibre renders through WebGL, and getting
 * pixels back means `preserveDrawingBuffer: true` — a real cost on every frame, for
 * every user, to serve a feature almost nobody has switched on. Fetching the tiles
 * separately costs nothing when idle, gives native resolution rather than whatever
 * the screen happens to be, and yields the backdrop alone with no river lines drawn
 * over the thing we are trying to follow. MapTiler serves the NLS layers with
 * `access-control-allow-origin: *`, so the pixels are readable.
 *
 * WHY A COST SURFACE AND NOT A BLUE MASK. The obvious idea is to detect the blue
 * water ink and follow it. Measured on this series (40 tiles each centred on an
 * in-scope river link, so water is present in every one): the median blue fraction
 * is 0.000% and the 90th percentile is 0.000%. Roughly one sheet in twenty is
 * coloured; the rest are monochrome outline editions, and on those a blue detector
 * finds nothing at all.
 *
 * What makes it tractable anyway is that the distribution is BIMODAL — a tile reads
 * either exactly zero or several percent, with nothing in between — so which kind of
 * sheet you are on can be decided from the pixels with near-perfect reliability, at
 * runtime, per sheet. Hence: classify first, then follow blue where it exists and
 * ink darkness where it does not.
 *
 * THE DANGER ON A MONOCHROME SHEET is that ink darkness describes roads, railways,
 * contours and parish boundaries just as well as rivers, so a shortest path will
 * cheerfully set off down a turnpike. The corridor constraint is what makes it
 * usable: the search is confined to a band around the straight line between the
 * vertex you have placed and the cursor, so the algorithm may only choose among ink
 * you have already pointed at. It is an assistant, not an interpreter.
 */

const TILE = 256;

/* ── Web Mercator ─────────────────────────────────────────────────────────── */

export function lonLatToWorld(lon, lat, zoom) {
  const scale = TILE * 2 ** zoom;
  const s = Math.sin((lat * Math.PI) / 180);
  return {
    x: ((lon + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * scale,
  };
}

export function worldToLonLat(x, y, zoom) {
  const scale = TILE * 2 ** zoom;
  return {
    lon: (x / scale) * 360 - 180,
    lat: (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / scale))) * 180) / Math.PI,
  };
}

/* ── The mosaic ───────────────────────────────────────────────────────────── */

async function fetchTile(template, z, x, y) {
  const url = template
    .replace('{z}', z).replace('{x}', x).replace('{y}', y);
  try {
    const resp = await fetch(url, { mode: 'cors', credentials: 'omit' });
    if (!resp.ok) return null;
    return await createImageBitmap(await resp.blob());
  } catch {
    /* A missing tile is normal at the edge of coverage: leave the paper blank and
       let the cost surface treat it as impassable, rather than failing the trace. */
    return null;
  }
}

/**
 * Assemble the tiles covering `bounds` into one readable canvas.
 *
 * @param {object} o
 * @param {string} o.template  tile URL with {z}/{x}/{y}
 * @param {number} o.zoom
 * @param {[number,number,number,number]} o.bounds  [west, south, east, north]
 * @param {number} [o.maxTiles]  refuse rather than fetch half the county
 * @returns {?object} sheet, or null if the area needs more tiles than allowed
 */
export async function loadSheet({ template, zoom, bounds, maxTiles = 48 }) {
  const [w, s, e, n] = bounds;
  const nw = lonLatToWorld(w, n, zoom);
  const se = lonLatToWorld(e, s, zoom);
  const tx0 = Math.floor(nw.x / TILE);
  const ty0 = Math.floor(nw.y / TILE);
  const tx1 = Math.floor(se.x / TILE);
  const ty1 = Math.floor(se.y / TILE);
  const cols = tx1 - tx0 + 1;
  const rows = ty1 - ty0 + 1;
  if (cols * rows > maxTiles || cols < 1 || rows < 1) return null;

  const canvas = document.createElement('canvas');
  canvas.width = cols * TILE;
  canvas.height = rows * TILE;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  /* Unfetched area must read as paper, not as transparent black, or every gap
     becomes the cheapest route on the board. */
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const jobs = [];
  for (let i = 0; i < cols; i += 1) {
    for (let j = 0; j < rows; j += 1) {
      jobs.push(fetchTile(template, zoom, tx0 + i, ty0 + j).then((bmp) => {
        if (bmp) ctx.drawImage(bmp, i * TILE, j * TILE);
      }));
    }
  }
  await Promise.all(jobs);

  return {
    zoom,
    originX: tx0 * TILE,
    originY: ty0 * TILE,
    width: canvas.width,
    height: canvas.height,
    image: ctx.getImageData(0, 0, canvas.width, canvas.height),
    bounds,
  };
}

export function sheetPixel(sheet, lon, lat) {
  const p = lonLatToWorld(lon, lat, sheet.zoom);
  return { x: p.x - sheet.originX, y: p.y - sheet.originY };
}

export function sheetLonLat(sheet, x, y) {
  return worldToLonLat(x + sheet.originX, y + sheet.originY, sheet.zoom);
}

export function sheetContains(sheet, lon, lat, margin = 24) {
  if (!sheet) return false;
  const p = sheetPixel(sheet, lon, lat);
  return p.x >= margin && p.y >= margin
    && p.x < sheet.width - margin && p.y < sheet.height - margin;
}

/* ── Is this sheet coloured? ──────────────────────────────────────────────── */

/* Scanned County Series paper is cream to sepia, so red >= green >= blue across the
   whole sheet. Printed blue water ink inverts that ordering, which is why the test
   is an ordering test and not a hue window: it needs no white balance and survives
   the yellowing that varies from sheet to sheet. */
export function isBluePixel(r, g, b) {
  return b - r > 20 && b - g > 8 && b > 55;
}

export function classifySheet(image) {
  const { data } = image;
  let blue = 0;
  let ink = 0;
  const n = data.length / 4;
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    if (isBluePixel(r, g, b)) blue += 1;
    if ((r + g + b) / 3 < 170) ink += 1;
  }
  const blueFraction = blue / n;
  const inkFraction = ink / n;
  return {
    blueFraction,
    inkFraction,
    /* 0.2% sits in the empty middle of a bimodal distribution: measured coloured
       sheets run to several percent, monochrome ones to exactly zero. Anything near
       the threshold is a sheet with very little water on it, where snapping will be
       poor whichever surface is chosen. */
    coloured: blueFraction > 0.002,
    /* BLANK PAPER IS NOT A SHEET. Tiles that 404, fall outside NLS coverage, or are
       refused for a bad key all leave the mosaic white, and white classifies quite
       happily as "monochrome" — whereupon the tracer announces it is snapping to
       printed ink, runs a shortest path over a uniform field, and marks the vertices
       it invents as machine-placed. Every one of those statements is false, and the
       provenance recorded in the annotation would be false with them. An unusable
       sheet has to be recognised as unusable and said so. */
    usable: inkFraction > 0.005,
  };
}

/* ── Cost surface ─────────────────────────────────────────────────────────── */

/**
 * Per-pixel traversal cost. Low is attractive.
 *
 * Cubed rather than linear in luminance so that black ink is emphatically cheaper
 * than grey halftone and paper is prohibitive — a linear ramp lets a path drift
 * across open paper whenever that is geometrically shorter, which is exactly the
 * failure that makes naive shortest-path tracing feel useless.
 */
export function buildCost(image, coloured) {
  const { data, width, height } = image;
  const cost = new Float32Array(width * height);
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    const ink = 1 + lum ** 3 * 600;
    if (coloured) {
      /* Follow the water itself. Ink is still passable — a channel narrows to a
         single drawn line where it is too small to fill — but four times dearer, so
         blue wins wherever blue exists. */
      cost[p] = isBluePixel(r, g, b) ? 1 : 4 * ink;
    } else {
      cost[p] = ink;
    }
  }
  return { cost, width, height };
}

/* ── Livewire ─────────────────────────────────────────────────────────────── */

/* A binary heap, because the alternative in a hot loop is sorting an array on every
   pop and this runs on mouse-move. */
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
    const lk = this.k.pop();
    const lv = this.v.pop();
    if (this.k.length) {
      this.k[0] = lk; this.v[0] = lv;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1;
        const r = l + 1;
        let m = i;
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

/**
 * Cheapest path from `a` to `b` through the cost surface, confined to a corridor
 * around the straight line between them.
 *
 * @returns {?Array<[number,number]>} pixel positions, or null if nothing was reachable
 */
export function livewire({ cost, width, height }, a, b, corridorPx = 36) {
  const ax = Math.round(a.x);
  const ay = Math.round(a.y);
  const bx = Math.round(b.x);
  const by = Math.round(b.y);
  const inside = (x, y) => x >= 0 && y >= 0 && x < width && y < height;
  if (!inside(ax, ay) || !inside(bx, by)) return null;

  /* Corridor as a bounding box plus a perpendicular-distance test. The box alone
     would admit a large rectangle for a diagonal segment. */
  const minX = Math.max(0, Math.min(ax, bx) - corridorPx);
  const maxX = Math.min(width - 1, Math.max(ax, bx) + corridorPx);
  const minY = Math.max(0, Math.min(ay, by) - corridorPx);
  const maxY = Math.min(height - 1, Math.max(ay, by) + corridorPx);
  const vx = bx - ax;
  const vy = by - ay;
  const vv = vx * vx + vy * vy;
  const near = (x, y) => {
    if (vv === 0) return (x - ax) ** 2 + (y - ay) ** 2 <= corridorPx ** 2;
    let t = ((x - ax) * vx + (y - ay) * vy) / vv;
    t = Math.max(0, Math.min(1, t));
    const dx = x - (ax + t * vx);
    const dy = y - (ay + t * vy);
    return dx * dx + dy * dy <= corridorPx * corridorPx;
  };

  const dist = new Float64Array(width * height).fill(Infinity);
  const prev = new Int32Array(width * height).fill(-1);
  const done = new Uint8Array(width * height);
  const start = ay * width + ax;
  const goal = by * width + bx;
  dist[start] = 0;
  const heap = new Heap();
  heap.push(0, start);

  const NEI = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
  while (heap.size) {
    const cur = heap.pop();
    if (done[cur]) continue;
    done[cur] = 1;
    if (cur === goal) break;
    const cx = cur % width;
    const cy = (cur - cx) / width;
    for (const [dx, dy] of NEI) {
      const nx = cx + dx;
      const ny = cy + dy;
      if (nx < minX || nx > maxX || ny < minY || ny > maxY) continue;
      if (!near(nx, ny)) continue;
      const ni = ny * width + nx;
      if (done[ni]) continue;
      const step = dx && dy ? Math.SQRT2 : 1;
      const nd = dist[cur] + cost[ni] * step;
      if (nd < dist[ni]) {
        dist[ni] = nd;
        prev[ni] = cur;
        heap.push(nd, ni);
      }
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

/* ── Simplification ───────────────────────────────────────────────────────── */

/* A livewire path has one vertex per pixel. Ramer–Douglas–Peucker in PIXEL space,
   before any conversion: the tolerance is then a statement about the drawn line's
   own width rather than about degrees, and stays meaningful at every latitude. */
export function simplify(points, tolerance = 1.6) {
  if (points.length < 3) return points.slice();
  const keep = new Uint8Array(points.length);
  keep[0] = 1;
  keep[points.length - 1] = 1;
  const stack = [[0, points.length - 1]];
  while (stack.length) {
    const [i0, i1] = stack.pop();
    const [x0, y0] = points[i0];
    const [x1, y1] = points[i1];
    const dx = x1 - x0;
    const dy = y1 - y0;
    const len = Math.hypot(dx, dy) || 1;
    let worst = -1;
    let worstD = tolerance;
    for (let i = i0 + 1; i < i1; i += 1) {
      const [px, py] = points[i];
      const d = Math.abs(dy * px - dx * py + x1 * y0 - y1 * x0) / len;
      if (d > worstD) { worstD = d; worst = i; }
    }
    if (worst !== -1) {
      keep[worst] = 1;
      stack.push([i0, worst], [worst, i1]);
    }
  }
  return points.filter((_p, i) => keep[i]);
}
