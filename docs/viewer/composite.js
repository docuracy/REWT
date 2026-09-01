/* The OS six-inch FIRST edition, composited from the county mosaics.
 *
 * WHY THIS IS ITS OWN MODULE AND NOT PART OF THE VIEWER. `maplibregl.addProtocol`
 * registers a scheme with MapLibre, not with the browser: `img.src = 'firsted://…'`
 * fetches nothing, because no such scheme exists outside MapLibre's own tile pipeline.
 * Anything that needs the PIXELS rather than a map layer — the tracer's ink reader —
 * therefore cannot go through the protocol at all. So the compositor lives here, with
 * no side effects and nothing imported from the viewer, and the protocol handler
 * becomes a thin wrapper round it. Two compositors would disagree eventually, and the
 * disagreement would surface as a line traced against one mosaic and validated against
 * another.
 *
 * WHAT IT DOES. The Library publishes the first edition county by county and the
 * mosaics are NOT cut at the county line — each bleeds over its neighbours, so stacking
 * them puts two different surveys of the same ground on top of each other with the join
 * wherever the draw order falls. Each county is therefore masked to its own Historic
 * Counties Standard polygon before compositing.
 *
 * NO CACHING HERE, DELIBERATELY. A viewer pans and a tracer reads pixels under a
 * dragging mouse; those want different cache policies and lifetimes, and a cache in
 * here would serve neither well while looking like it served both. Put one in front.
 */

const NLS = 'https://mapseries-tilesets.s3.amazonaws.com/os/six-inch-';

let countiesPromise = null;

/** The 53 counties with a first-edition mosaic, with their mask rings. Memoised. */
export function loadCounties(url) {
  if (!countiesPromise) {
    // Resolved against THIS module rather than the page, so a caller in another
    // directory — docs/trace/ — gets the same file rather than a 404 next to itself.
    const u = url || new URL('counties.json', import.meta.url).href;
    countiesPromise = fetch(u).then((r) => {
      if (!r.ok) throw new Error(`counties.json: HTTP ${r.status}`);
      return r.json();
    });
  }
  return countiesPromise;
}

/** Web-Mercator tile bounds, [w, s, e, n] in degrees. */
export function tileBounds(z, x, y) {
  const lon = (i) => (i / 2 ** z) * 360 - 180;
  const lat = (j) => {
    const n = Math.PI - (2 * Math.PI * j) / 2 ** z;
    return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
  };
  return [lon(x), lat(y + 1), lon(x + 1), lat(y)];
}

/** Which counties could contribute ink to this tile. Bounds only — a hint, not a test. */
export function countiesFor(counties, z, x, y) {
  const [w, s, e, n] = tileBounds(z, x, y);
  return counties.filter((r) => r.in_scope && r.bounds
    && !(r.bounds[2] < w || r.bounds[0] > e || r.bounds[3] < s || r.bounds[1] > n));
}

async function countyTile(slug, z, x, y) {
  try {
    const r = await fetch(`${NLS}${slug}/${z}/${x}/${y}.png`);
    if (!r.ok) return null;
    return await createImageBitmap(await r.blob());
  } catch (e) {
    return null;
  }
}

/**
 * One composited 256×256 tile as an ImageBitmap, or null if no county drew anything.
 * Null is meaningful: it is "no sheet covers this ground", not "the fetch failed".
 */
export async function compositeTile(z, x, y, opts = {}) {
  const counties = opts.counties || await loadCounties(opts.countiesUrl);
  const here = countiesFor(counties, z, x, y);
  if (!here.length) return null;
  const [w, s, e, n] = tileBounds(z, x, y);

  const out = new OffscreenCanvas(256, 256);
  const g = out.getContext('2d');
  let drew = false;

  // Fetched together rather than in sequence: a tile straddling three counties would
  // otherwise cost three round trips end to end.
  const sheets = await Promise.all(here.map((r) => countyTile(r.slug, z, x, y)));

  for (let i = 0; i < here.length; i += 1) {
    const r = here[i];
    const img = sheets[i];
    if (!img) continue;
    const layer = new OffscreenCanvas(256, 256);
    const lg = layer.getContext('2d');
    lg.drawImage(img, 0, 0);
    if (r.mask) {
      /* A pixel is taken only where the county OWNS the ground and its own sheet HAS
         something to say there. `destination-in` against the filled polygon is the
         first condition in two operations and no per-pixel work; the sheet's own alpha
         is the second, and it is what keeps a mosaic's internal margins transparent
         rather than painting them white over a neighbour.

         A county with NO polygon is masked by its alpha alone. That is correct rather
         than a fallback: the only such county is the Isle of Man, which the Historic
         Counties Standard omits because it is not in the UK, and which no neighbour's
         sheets reach because it is an island. */
      lg.globalCompositeOperation = 'destination-in';
      lg.fillStyle = '#000';
      lg.beginPath();
      for (const ring of r.mask) {
        ring.forEach(([lo, la], k) => {
          const px = ((lo - w) / (e - w)) * 256;
          const py = ((n - la) / (n - s)) * 256;
          k ? lg.lineTo(px, py) : lg.moveTo(px, py);
        });
        lg.closePath();
      }
      lg.fill();
    }
    g.drawImage(layer, 0, 0);
    drew = true;
  }
  return drew ? out.transferToImageBitmap() : null;
}

/** The same tile as PNG bytes, which is what a MapLibre protocol handler must return. */
export async function compositeTilePNG(z, x, y, opts = {}) {
  const bmp = await compositeTile(z, x, y, opts);
  const cv = new OffscreenCanvas(256, 256);
  if (bmp) cv.getContext('2d').drawImage(bmp, 0, 0);
  const blob = await cv.convertToBlob({ type: 'image/png' });
  return new Uint8Array(await blob.arrayBuffer());
}

/** Register `firsted://{z}/{x}/{y}` with MapLibre. A wrapper, and nothing more. */
export function registerProtocol(maplibregl, opts = {}) {
  maplibregl.addProtocol('firsted', async (params) => {
    const m = params.url.match(/^firsted:\/\/(\d+)\/(\d+)\/(\d+)/);
    if (!m) return { data: null };
    const [z, x, y] = m.slice(1).map(Number);
    return { data: await compositeTilePNG(z, x, y, opts) };
  });
}
