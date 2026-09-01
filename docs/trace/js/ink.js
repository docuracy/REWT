/**
 * Reading the printed sheet under the map, and finding the middle of a channel.
 *
 * WHY NOT READ THE MAP'S OWN CANVAS. MapLibre renders through WebGL and getting pixels
 * back means `preserveDrawingBuffer: true` — a cost on every frame for every user, to
 * serve a feature almost nobody switches on. Fetching the tiles separately costs nothing
 * when idle, gives the sheet's native resolution rather than whatever the screen happens
 * to be, and yields the backdrop ALONE with no river lines drawn over the thing we are
 * trying to follow. The NLS bucket sends `Access-Control-Allow-Origin: *` on GET — though
 * not on HEAD, so `curl -I` will tell you otherwise — hence the pixels are readable.
 *
 * ── CENTRING: MAXIMISE THE MINIMUM DISTANCE TO INK ──────────────────────────────────
 *
 * At 1:2,500 a watercourse of any size is drawn as **two bank lines with white between
 * them**, so following ink — which is what a cost-surface livewire does — locks onto
 * whichever bank is nearer or darker and returns a course offset by half the channel
 * width, consistently, in a direction nobody chose. It looks like a good trace.
 *
 * The remedy is to put the vertex in the middle of the channel rather than on a bank —
 * the medial axis, which is the same answer PLAN.md §5 reaches for water bodies the survey
 * draws as areas, taken locally at one vertex instead of globally over a polygon.
 *
 * **HOW THE MIDDLE IS FOUND, AND THE VERSION THAT WAS TRIED FIRST AND DISCARDED.** The
 * obvious formulation is to maximise the minimum distance to ink in two dimensions. That
 * was built and measured, and it fails in a way worth recording: over a 512 px patch of
 * Ware at 1:2,500 it moved 150 of 400 probe points and gave them a median half-width of
 * **3.7 m** — which is not a channel, it is the gap between malt-houses, and the yards and
 * streets of a town are full of them. **Maximising clearance in two dimensions finds the
 * middle of any open blob**, and nothing in the pixels says which blobs are water.
 *
 * What separates them is information the tracer already has and that formulation threw
 * away: **the direction the contributor is travelling.** So the search is confined to a
 * transect **perpendicular to the line from the previous vertex** — walk out to each side
 * until ink is met, and put the vertex at the midpoint of the span. A yard cannot capture
 * it, because the transect only looks across the channel the person is already following.
 * It is the corridor constraint of a livewire, reduced to one dimension: the algorithm may
 * only choose among ink the contributor has already pointed at.
 *
 * The span is the **channel width**, measured rather than inferred, which `docs/scale.md`
 * notes is the by-product medial-axis work yields and which later stages want.
 *
 * **AND IT IS WRONG WHEREVER THE CHANNEL IS A SINGLE LINE.** On a six-inch sheet an
 * ordinary brook is one stroke of ink; maximising distance from ink walks *away* from it,
 * into the nearest field, and returns a confident vertex in the wrong place. So this
 * refuses rather than obliges, on three tests, each of which is a real case and not a
 * defensive flourish:
 *
 *   - **the click is on ink** — a single-line channel. Centring is meaningless; say so.
 *   - **no ink within the window** — blank paper, outside coverage, or a refused tile. A
 *     uniform field has a maximum everywhere and none of them mean anything.
 *   - **the clearance is too large** — the white is not a channel but a field, a park or
 *     the sea. A channel has a bank on both sides within a plausible width.
 *
 * The clearance at the accepted point is the channel's **half-width in pixels**, which
 * converts to metres and is worth keeping: `docs/scale.md` notes that width falls out of
 * medial-axis work as a by-product, and later stages want it.
 *
 * ── WHAT IT CANNOT DO, MEASURED ────────────────────────────────────────────────────
 *
 * **It cannot tell a channel from a railway, and no local test of the pixels can.** A
 * railway at 1:2,500 is two parallel lines of very nearly constant separation; so is a road
 * with both edges drawn, and so is a canal. Probing every sixth pixel of a 768 px patch of
 * Ware in four directions, the accepted points fall on the wharves and the New River — and
 * also along the railway through the goods yard, correctly by its own test and wrongly by
 * any useful one.
 *
 * That is not a defect to be tuned out. It is the boundary of the method, and it decides
 * what the mode IS: **an assist, not a detector.** The contributor supplies the knowledge
 * that this is a watercourse — from the label, the context, the task they were given — and
 * the algorithm supplies the placement they cannot do accurately by hand. Given a free
 * choice of direction it finds a plausible cross-section almost anywhere, which is exactly
 * why the direction is taken from the trace and never searched for.
 *
 * The selectivity the discriminators buy, on that patch: **39% of probes accepted without
 * the width-agreement test, 0.9% with it.** Both figures are of a test allowed to shop for
 * a direction, so both overstate what a real trace would accept.
 *
 * EXPERIMENTAL, and the failure it guards against is the one it could itself produce: a
 * vertex placed with more apparent authority than it has earned. Every vertex it moves is
 * recorded as `centred`, distinctly from `clicked`, and the interface says which while
 * tracing — because a provenance field only a later reader sees does nothing for the
 * person deciding, in the moment, whether to trust the line.
 */

const TILE = 256;

/* ── Web Mercator ─────────────────────────────────────────────────────────────────── */

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

/** Ground resolution in metres per pixel at this latitude and zoom. */
export function metresPerPixel(lat, zoom) {
  return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
}

/* ── the mosaic ───────────────────────────────────────────────────────────────────── */

function tileUrl(template, z, x, y) {
  return template.replace('{z}', z).replace('{x}', x).replace('{y}', y);
}

function loadImage(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';      // required, or the canvas is tainted and unreadable
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);  // a missing tile is normal at a sheet's edge
    img.src = url;
  });
}

/**
 * Fetch the tiles covering a small box and draw them into one canvas.
 *
 * Small on purpose: this is read at the moment a vertex is placed, not kept warm. A window
 * of a couple of tiles a side is a fraction of a second and costs nothing when idle.
 */
export async function loadPatch({ template, zoom, lon, lat, radiusPx = 160 }) {
  const centre = lonLatToWorld(lon, lat, zoom);
  const x0 = Math.floor((centre.x - radiusPx) / TILE);
  const x1 = Math.floor((centre.x + radiusPx) / TILE);
  const y0 = Math.floor((centre.y - radiusPx) / TILE);
  const y1 = Math.floor((centre.y + radiusPx) / TILE);
  const w = (x1 - x0 + 1) * TILE;
  const h = (y1 - y0 + 1) * TILE;
  if (w * h > 4096 * 4096) return null;             // zoomed too far out to mean anything

  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h);

  const jobs = [];
  for (let tx = x0; tx <= x1; tx += 1) {
    for (let ty = y0; ty <= y1; ty += 1) {
      jobs.push(loadImage(tileUrl(template, zoom, tx, ty)).then((img) => {
        if (img) ctx.drawImage(img, (tx - x0) * TILE, (ty - y0) * TILE);
        return Boolean(img);
      }));
    }
  }
  const got = await Promise.all(jobs);
  if (!got.some(Boolean)) return null;              // nothing answered: outside coverage

  let data;
  try {
    data = ctx.getImageData(0, 0, w, h);
  } catch {
    return null;                                    // tainted: the host stopped sending CORS
  }
  return {
    zoom, width: w, height: h, data,
    originX: x0 * TILE, originY: y0 * TILE,
    tilesRequested: got.length, tilesReturned: got.filter(Boolean).length,
  };
}

export function patchPixel(patch, lon, lat) {
  const w = lonLatToWorld(lon, lat, patch.zoom);
  return { x: Math.round(w.x - patch.originX), y: Math.round(w.y - patch.originY) };
}

export function patchLonLat(patch, x, y) {
  return worldToLonLat(x + patch.originX, y + patch.originY, patch.zoom);
}

/* ── ink ──────────────────────────────────────────────────────────────────────────── */

/**
 * Ink, as luminance below a threshold.
 *
 * A DELIBERATE THRESHOLD RATHER THAN A CLEVER ONE. These are scans of engraved sheets:
 * paper sits near white, ink near black, and the histogram between them is thin. Otsu or
 * an adaptive local threshold would be defensible and would also make the answer depend on
 * what else happens to be in the window — a block of hachured buildings would drag the
 * threshold and change where a channel's centre appears to be. A fixed cut is wrong in the
 * same way everywhere, which is the kind of wrong that can be seen and corrected.
 */
export const INK_LUMINANCE = 150;

export function isInk(patch, x, y, threshold = INK_LUMINANCE) {
  if (x < 0 || y < 0 || x >= patch.width || y >= patch.height) return true;  // off-patch counts as a wall
  const i = (y * patch.width + x) * 4;
  const d = patch.data.data;
  return (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) < threshold;
}

/** Is the sheet coloured, or a monochrome outline edition? Decided per patch, at use. */
export function classifyPatch(patch) {
  const d = patch.data.data;
  let blue = 0; let ink = 0; const n = patch.width * patch.height;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i]; const g = d[i + 1]; const b = d[i + 2];
    if (b > r + 25 && b > g + 15) blue += 1;
    if (0.299 * r + 0.587 * g + 0.114 * b < INK_LUMINANCE) ink += 1;
  }
  return {
    blueFraction: blue / n,
    inkFraction: ink / n,
    /* Measured over this series: roughly one sheet in twenty is a coloured printing and
       the rest are monochrome outline editions, where a blue-water detector finds nothing
       at all. The distribution is bimodal, so this decides reliably at runtime. */
    coloured: blue / n > 0.005,
    usable: ink / n > 0.0005,
  };
}

/* ── centring on a transect ───────────────────────────────────────────────────────── */

export const CENTRE_DEFAULTS = {
  /* IN METRES, NOT PIXELS. The first version set these in pixels, which made the mode
     behave differently at every zoom — 30 px is 22 m at z17 and 11 m at z18, so the same
     click on the same channel would be accepted at one zoom and refused at the next, and
     nothing would say why. A channel's width is a fact about the world. */
  maxWidthM: 30,        // wider than this and it is not a channel a contributor is tracing
  minWidthM: 1.5,       // narrower and the two banks are one line
  minTravelPx: 6,       // below this the previous vertex gives no reliable bearing
  inkRunPx: 2,          // consecutive ink pixels needed to count as a bank
  transectOffsets: [-4, 0, 4],
  /* THE DISCRIMINATOR THAT MAKES THIS SELECTIVE AT ALL, and it was missing from the first
     version. A channel has very nearly the same width a few pixels further along; a gap
     between buildings, a field corner or the space beside a road does not. Measured over a
     768 px patch of Ware at 1:2,500, probing four directions at every sixth pixel: without
     this the transect test accepted **39% of the whole sheet** — fields, yards, the goods
     yard, everything. Requiring the parallel transects to agree on the width is what
     separates a channel from an opening that merely happens to have ink on both sides. */
  widthAgreementM: 2.5, // spread across the parallel transects
};

/** First index t>=1 along (dirX,dirY) from (x,y) where ink persists for `run` pixels. */
function firstBank(patch, x, y, dirX, dirY, limit, run) {
  let consecutive = 0;
  for (let t = 1; t <= limit + run; t += 1) {
    const sx = Math.round(x + dirX * t);
    const sy = Math.round(y + dirY * t);
    if (isInk(patch, sx, sy)) {
      consecutive += 1;
      if (consecutive >= run) return t - run + 1;
    } else {
      consecutive = 0;
    }
  }
  return null;
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};

/**
 * Put a vertex in the middle of the channel it is being traced along.
 *
 * @param patch          from `loadPatch`
 * @param px, py         where the contributor clicked, in patch pixels
 * @param fromX, fromY   the previous vertex — this is what gives the direction of travel
 * @param opts.mPerPx    ground resolution, required: the thresholds are in metres
 *
 * @returns always an object. `{moved:false, why}` when it refuses, so the interface can say
 *          why rather than doing nothing silently. **Refusing is the common case and is not
 *          a failure**: most of a sheet is not a channel drawn as two banks.
 *
 * IT IS AN ASSIST, NOT A DETECTOR. It improves a vertex a person has already placed in a
 * channel; it cannot tell you whether you are in one. Given a free choice of direction it
 * will find a plausible cross-section almost anywhere, which is why the direction is taken
 * from the trace rather than searched for.
 */
export function centreOnTransect(patch, px, py, fromX, fromY, opts = {}) {
  const o = { ...CENTRE_DEFAULTS, ...opts };
  const mPerPx = o.mPerPx;
  if (!Number.isFinite(mPerPx) || mPerPx <= 0) {
    throw new Error('centreOnTransect: mPerPx is required — the thresholds are in metres');
  }
  const maxHalfPx = (o.maxWidthM / mPerPx) / 2;

  const dx = px - fromX;
  const dy = py - fromY;
  const travel = Math.hypot(dx, dy);
  if (!Number.isFinite(travel) || travel < o.minTravelPx) {
    return {
      moved: false,
      why: 'there is no direction of travel yet — centring measures the channel ACROSS the '
        + 'way you are going, so it needs a previous vertex far enough back to give a '
        + 'bearing. Place this one by hand.',
    };
  }
  if (isInk(patch, Math.round(px), Math.round(py))) {
    return {
      moved: false,
      why: 'that point is on ink, so the channel here is drawn as a single line. There is '
        + 'no width to find a middle of, and the vertex is already on the feature.',
    };
  }

  const ux = dx / travel; const uy = dy / travel;
  const nx = -uy; const ny = ux;              // unit normal: across the direction of travel

  const offsets = []; const widths = [];
  for (const along of o.transectOffsets) {
    const ox = px + ux * along;
    const oy = py + uy * along;
    if (isInk(patch, Math.round(ox), Math.round(oy))) continue;
    const plus = firstBank(patch, ox, oy, nx, ny, maxHalfPx, o.inkRunPx);
    const minus = firstBank(patch, ox, oy, -nx, -ny, maxHalfPx, o.inkRunPx);
    if (plus === null || minus === null) continue;   // open on one side: no cross-section
    offsets.push((plus - minus) / 2);
    widths.push(plus + minus);
  }

  /* EVERY transect must find a cross-section, not a majority. One or two is what a field
     corner produces. */
  if (offsets.length < o.transectOffsets.length) {
    return {
      moved: false,
      why: 'no bank on both sides within a channel\'s width, all the way along — this is '
        + 'open ground, or the channel runs a different way from the one you are tracing.',
      transectsAgreeing: offsets.length,
    };
  }

  const widthPx = median(widths);
  const widthM = widthPx * mPerPx;
  const spreadM = (Math.max(...widths) - Math.min(...widths)) * mPerPx;

  if (widthM > o.maxWidthM) {
    return { moved: false, widthM,
             why: `that opening is ${widthM.toFixed(0)} m across — too wide for a channel `
               + 'being traced by hand. A field, a park, or open water.' };
  }
  if (widthM < o.minWidthM) {
    return { moved: false, widthM, why: 'the two banks are too close together to be distinct' };
  }
  if (spreadM > o.widthAgreementM) {
    return {
      moved: false, widthM, spreadM,
      why: `the width changes by ${spreadM.toFixed(1)} m over a few pixels, so these are `
        + 'not two banks of one channel — more likely a gap between buildings, or a '
        + 'boundary crossing at an angle.',
    };
  }

  const shift = median(offsets);
  return {
    moved: Math.abs(shift) >= 0.5,
    x: px + nx * shift,
    y: py + ny * shift,
    widthPx, widthM, spreadM,
    movedPx: Math.abs(shift),
    movedM: Math.abs(shift) * mPerPx,
    transectsAgreeing: offsets.length,
    why: Math.abs(shift) < 0.5 ? 'already in the middle' : undefined,
  };
}
