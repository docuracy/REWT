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
 * ── HOW WELL IT WORKS, ON ONE TRACE AT ONE PLACE ───────────────────────────────────
 *
 * On a hand trace of THE CUT at Ware, six-inch second edition, at the sheet's native z17:
 * **4 of 7 vertices handled** — two centred by 0.4 m, one by 0.7 m, one already central —
 * with widths of 11.8, 15.5, 25.1 and 26.6 m as the navigation widens toward the wharves.
 * Of the three refusals, one was on ink and two were where the width changes by 9–11 m
 * over a few metres, which at that end of the reach is the basins opening out and is
 * arguably the right answer.
 *
 * Against a free-direction probe of the same ground — every eighth pixel, four directions,
 * accept if any succeeds — **11.8% on the six-inch and 3.9% on the 25-inch**. That probe
 * overstates: it shops for a direction, and a contributor does not.
 *
 * **This is calibration on a single trace of a single reach, and it should be read as
 * provisional.** Nothing here has been tested against a body of sheets or a second pair of
 * hands, and the numbers above are the only evidence any of these constants rest on.
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
 * TWO KINDS OF SOURCE, BECAUSE NOT EVERY SHEET HAS A URL. An ordinary layer is a
 * `{z}/{x}/{y}` template and an `Image` load. The composited first edition has no address
 * at all: it is assembled in a canvas from up to three county mosaics, each masked to its
 * own Historic Counties polygon, and exists only in memory. MapLibre reaches it through a
 * registered `firsted://` protocol — **which is MapLibre's scheme and not the browser's**,
 * so `img.src = 'firsted://…'` fetches nothing and this reader would have seen blank paper,
 * classified the sheet unusable, and refused every vertex for a reason having nothing to do
 * with the sheet. So a source may instead be a function returning an ImageBitmap, and the
 * compositor is called directly rather than through a URL that does not exist.
 *
 * Small on purpose: this is read at the moment a vertex is placed, not kept warm.
 */
export async function loadPatch({ template, tile, zoom, lon, lat, radiusPx = 160 }) {
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
  /* Unfetched ground must read as PAPER, not as transparent black, or every gap becomes
     the cheapest route on the board for the livewire. */
  ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h);

  const jobs = [];
  for (let tx = x0; tx <= x1; tx += 1) {
    for (let ty = y0; ty <= y1; ty += 1) {
      const get = tile ? tile(zoom, tx, ty) : loadImage(tileUrl(template, zoom, tx, ty));
      jobs.push(Promise.resolve(get).then((img) => {
        if (img) ctx.drawImage(img, (tx - x0) * TILE, (ty - y0) * TILE);
        return Boolean(img);
      }).catch(() => false));
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

/**
 * Blue water ink, as an ORDERING test rather than a hue window.
 *
 * Scanned County Series paper is cream to sepia, so red >= green >= blue across the whole
 * sheet. Printed blue water ink inverts that ordering. Testing the ordering needs no white
 * balance and survives the yellowing that varies from sheet to sheet, where a hue window
 * has to be retuned for every scan. Carried across from the scoping exercise, where it was
 * measured against this series.
 */
export function isBluePixel(r, g, b) {
  return b - r > 20 && b - g > 8 && b > 55;
}

/**
 * Is this sheet coloured, and is it a sheet at all? Decided per patch, at use.
 *
 * THE THRESHOLDS ARE THE MEASURED ONES. An earlier version of this function used numbers
 * I had chosen by eye — 0.005 for colour and 0.0005 for usable — when the scoping exercise
 * had already measured them over this series and written down why. Replaced with the
 * measured pair, which is the same mistake as reading the nearest label: a plausible answer
 * to a question somebody had already answered properly.
 */
export function classifyPatch(patch) {
  const d = patch.data.data;
  let blue = 0; let ink = 0; const n = patch.width * patch.height;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i]; const g = d[i + 1]; const b = d[i + 2];
    if (isBluePixel(r, g, b)) blue += 1;
    if ((r + g + b) / 3 < 170) ink += 1;
  }
  const blueFraction = blue / n;
  const inkFraction = ink / n;
  return {
    blueFraction,
    inkFraction,
    /* 0.2% sits in the empty middle of a bimodal distribution: measured coloured sheets run
       to several percent, monochrome ones to exactly zero. Roughly one sheet in twenty is a
       coloured printing, so monochrome is the normal case. Anything near the threshold is a
       sheet with very little water on it, where snapping will be poor either way. */
    coloured: blueFraction > 0.002,
    /* BLANK PAPER IS NOT A SHEET. Tiles that 404, fall outside coverage, or are refused all
       leave the mosaic white, and white classifies quite happily as "monochrome" —
       whereupon the tracer announces it is snapping to printed ink, runs a shortest path
       over a uniform field, and marks the vertices it invents as machine-placed. Every one
       of those statements is false, and the provenance recorded in the annotation would be
       false with them. An unusable sheet has to be recognised as unusable and said so. */
    usable: inkFraction > 0.005,
  };
}

/* ── centring on a transect ───────────────────────────────────────────────────────── */

export const CENTRE_DEFAULTS = {
  /* ── EVERY QUANTITY ABOUT THE GROUND IS IN METRES. ────────────────────────────────
     This was got wrong twice, the second time because the first fix was applied to the
     instance rather than to the class.
     
     The first version put the width limits in pixels, so 30 px was 22 m at z17 and 11 m
     at z18 and the same click on the same channel was accepted at one zoom and refused at
     the next. Those were converted to metres — and `transectOffsets` was left in pixels,
     where it did exactly the same thing one level down: [-4, 0, 4] spans 3 m on the
     25-inch at z18 and **6 m on the six-inch at z17**, so changing sheet doubled the
     length of river the three transects sample. Over 6 m an outer transect falls off the
     reach through a bridge, a gate or a bend, fails to find both banks, and the
     all-must-agree rule then refuses the vertex. Measured on a real six-inch trace of THE
     CUT at Ware: **0 of 5 vertices centred as shipped; 1 moved and 2 already central once
     the offsets were in metres.** Neither of the other two rules was the blocker.
     
     The rule that follows: if a constant describes the world it is in metres; if it
     describes the raster it is in pixels, and it says so. */
  maxWidthM: 30,          // wider than this and it is not a channel being traced by hand
  minWidthM: 1.5,         // narrower and the two banks are one line
  minTravelM: 4,          // below this the previous vertex gives no reliable bearing
  /* ── BASELINE AND QUORUM ARE SEPARATE KNOBS, AND CONFLATING THEM MADE IT UNTUNABLE ──
     What discriminates a channel from a gap between buildings is measuring the SAME width
     over a decent LENGTH of river. What breaks that measurement is a bridge, a gate, a
     lock, or a label crossing the channel — any one of which stops a single transect
     finding both banks.
     
     Requiring every transect to succeed ties those together, and the result cannot be
     tuned. Measured on a real six-inch trace of THE CUT at Ware against a free-direction
     probe of the same sheet, varying only the baseline:
     
        baseline   vertices handled   probe falsely accepting
          2.4 m         4 of 7                 26.5%
          4.8 m         3 of 7                 15.0%
          8.0 m         2 of 7                  8.7%
         16.0 m         0 of 7                  3.9%
     
     Monotonic, with no setting that is both usable and selective. A QUORUM separates them:
     span a long baseline for discrimination, and let a minority of transects fail for the
     bridge. */
  transectSpacingM: 2,    // how far apart the parallel transects sit ALONG the channel
  transectCount: 7,       // 12 m of river
  transectQuorum: 5,      // how many must find a cross-section — not all of them

  /* THE THIRD INSTANCE OF THE SAME CLASS ERROR, and this time the metre version predicts
     the pixel values rather than merely replacing them.
     
     This was a constant 2 px, on the reasoning that a bank's thickness is a property of
     the engraving and not of the ground. Half right: it is a property of the DRAWN LINE,
     which is a roughly constant width on paper — and a constant width on paper is a
     constant width in METRES at any one map scale, because the scale is what converts
     them. Measured at each sheet's native resolution, a bank is 1 px on the six-inch at
     0.738 m/px and 2 px on the 25-inch at 0.37 m/px. Both are 0.74 m.
     
     So one number in metres reproduces both, and the constant in pixels did not: at 2 px
     it stepped straight over every one-pixel six-inch bank and refused every vertex on a
     real trace of THE CUT at Ware. Floor of 1 px, because a bank cannot be thinner than
     the raster can show. */
  bankThicknessM: 0.7,

  /* THE DISCRIMINATOR THAT MAKES THIS SELECTIVE AT ALL. A channel has very nearly the same
     width a metre further along; a gap between buildings, a field corner or the space
     beside a road does not. Probing a 768 px patch of Ware at 1:2,500 in four directions
     at every sixth pixel, without this test the transect accepted **39% of the whole
     sheet**; with it, 0.9%. */
  widthAgreementM: 2.5,
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
  if (!Number.isFinite(travel) || travel * mPerPx < o.minTravelM) {
    return {
      moved: false, code: 'no-bearing',
      why: 'there is no direction of travel yet — centring measures the channel ACROSS the '
        + 'way you are going, so it needs a previous vertex far enough back to give a '
        + 'bearing. Place this one by hand.',
    };
  }
  if (isInk(patch, Math.round(px), Math.round(py))) {
    return {
      moved: false, code: 'on-ink',
      why: 'that point is on ink, so the channel here is drawn as a single line. There is '
        + 'no width to find a middle of, and the vertex is already on the feature.',
    };
  }

  const ux = dx / travel; const uy = dy / travel;
  const nx = -uy; const ny = ux;              // unit normal: across the direction of travel

  /* Spread the parallel transects over a fixed distance of RIVER, whatever the scale. At
     least one pixel apart, or on a coarse sheet they collapse onto the same row and the
     agreement test becomes a test of nothing. */
  const spacingPx = Math.max(1, o.transectSpacingM / mPerPx);
  /* A bank cannot be thinner than the raster can show it. */
  const runPx = Math.max(1, Math.round((o.bankThicknessM ?? 0.7) / mPerPx));
  const half = (o.transectCount - 1) / 2;
  const alongs = [];
  for (let i = -half; i <= half; i += 1) alongs.push(i * spacingPx);

  const offsets = []; const widths = [];
  for (const along of alongs) {
    const ox = px + ux * along;
    const oy = py + uy * along;
    if (isInk(patch, Math.round(ox), Math.round(oy))) continue;
    const plus = firstBank(patch, ox, oy, nx, ny, maxHalfPx, runPx);
    const minus = firstBank(patch, ox, oy, -nx, -ny, maxHalfPx, runPx);
    if (plus === null || minus === null) continue;   // open on one side: no cross-section
    offsets.push((plus - minus) / 2);
    widths.push(plus + minus);
  }

  /* A QUORUM, not unanimity — see CENTRE_DEFAULTS. Too few and a field corner qualifies;
     all of them and a single bridge disqualifies a real reach. */
  const quorum = Math.min(o.transectQuorum, alongs.length);
  if (offsets.length < quorum) {
    return {
      moved: false, code: 'no-banks',
      why: `only ${offsets.length} of ${alongs.length} cross-sections found a bank on both `
        + `sides within a channel's width — this is open ground, or the channel runs a `
        + 'different way from the one you are tracing.',
      transectsAgreeing: offsets.length,
    };
  }

  const widthPx = median(widths);
  const widthM = widthPx * mPerPx;
  const spreadM = (Math.max(...widths) - Math.min(...widths)) * mPerPx;

  if (widthM > o.maxWidthM) {
    return { moved: false, code: 'too-wide', widthM,
             why: `that opening is ${widthM.toFixed(0)} m across — too wide for a channel `
               + 'being traced by hand. A field, a park, or open water.' };
  }
  if (widthM < o.minWidthM) {
    return { moved: false, code: 'too-narrow', widthM,
             why: 'the two banks are too close together to be distinct' };
  }
  if (spreadM > o.widthAgreementM) {
    return {
      moved: false, code: 'width-disagrees', widthM, spreadM,
      why: `the width changes by ${spreadM.toFixed(1)} m over a few pixels, so these are `
        + 'not two banks of one channel — more likely a gap between buildings, or a '
        + 'boundary crossing at an angle.',
    };
  }

  const shift = median(offsets);
  return {
    moved: Math.abs(shift) >= 0.5,
    code: Math.abs(shift) >= 0.5 ? 'moved' : 'central',
    x: px + nx * shift,
    y: py + ny * shift,
    widthPx, widthM, spreadM,
    movedPx: Math.abs(shift),
    movedM: Math.abs(shift) * mPerPx,
    transectsAgreeing: offsets.length,
    why: Math.abs(shift) < 0.5 ? 'already in the middle' : undefined,
  };
}
