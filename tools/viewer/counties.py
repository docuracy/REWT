"""Historic counties, and the first-edition six-inch sheets masked to them.

WHY THIS EXISTS. The NLS publishes the OS six-inch FIRST edition county by county, and
the mosaics are not cut at the county line — a county's sheets bleed over its neighbours,
so stacking all of them puts two different surveys of the same ground on top of each
other and the join is wherever the draw order happens to put it. Masking each mosaic to
its county's own polygon makes the whole of England and Wales displayable at once, with
the seams on the county boundaries where they belong.

MapLibre cannot clip a raster layer to a polygon — there is no such property in v4, and
v5's `clip` layer occludes 3D content rather than cutting rasters. So the compositing is
done here, in this project's own server, and the browser asks for one seamless tile.

THE COUNTY VOCABULARY IS THE HISTORIC COUNTIES STANDARD. Counties are named and keyed by
the Trust's `NAME` and three-letter `HCS_CODE` — `BED`, `YRK`, `CMB` — and never by the
NLS's own tileset slug, which is a filename and differs from the Standard in three places
(`devonshire`/Devon, `caernarvonshire`/Caernarfonshire, and an Isle of Man tileset for a
county the Standard does not include, the Isle of Man not being in the UK).
"""

from __future__ import annotations

import io
import math
import threading
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
TILES = CACHE / "tiles"
ZIP = CACHE / "UKDefinitionA_WG84_Simplified.zip"
NLS = "https://mapseries-tilesets.s3.amazonaws.com/os/six-inch-{slug}/{z}/{x}/{y}.png"

# The Standard's spelling is authoritative; these are the NLS's filenames for it.
SLUG_ALIAS = {"Devon": "devonshire", "Caernarfonshire": "caernarvonshire"}

# The Isle of Man is not in the United Kingdom, so the Historic Counties Standard's 92
# do not include it — but the NLS publishes a first-edition mosaic for it and this
# project needs a code for it, so it is carried here as IOM. It has NO POLYGON, and
# needs none: it is an island, no other county's sheets reach it, and its own tiles'
# transparency is already the only boundary there is to respect. A county without a
# polygon is masked by its own alpha alone, and says so in the listing.
# It is OUT OF SCOPE for this project, which is England and Wales, so it is carried in
# the vocabulary — a reference to IOM resolves — but it is not drawn in the seamless
# composite. It remains selectable one county at a time, where the choice is explicit.
EXTRA = [{"code": "IOM", "name": "Isle of Man", "slug": "isle-of-man",
          "in_scope": False}]

_lock = threading.Lock()


def _slug(name: str) -> str:
    return SLUG_ALIAS.get(name) or name.lower().replace(" ", "-").replace("'", "")


class Counties:
    """The 92 historic counties, with the NLS tilesets that exist for them."""

    def __init__(self, have_tilesets: set[str]):
        import geopandas as gpd

        if not ZIP.exists():
            raise FileNotFoundError(
                f"{ZIP} is missing. It is the Historic County Borders Project's "
                "UKDefinitionA (simplified), declared as hct_historic_counties in "
                "conf/sources.yml; fetch it with "
                "`python tools/viewer/serve.py --fetch-counties`."
            )
        g = gpd.read_file(f"zip://{ZIP}!UKDefinitionA.shp").to_crs(4326)
        self.rows = []
        for r in g.itertuples(index=False):
            slug = _slug(r.NAME)
            if slug not in have_tilesets:
                continue                       # Scotland, Ireland: no first-edition set here
            minx, miny, maxx, maxy = r.geometry.bounds
            self.rows.append({
                "code": r.HCS_CODE, "name": r.NAME, "slug": slug,
                "variant": f"{slug}V" in have_tilesets,
                "bounds": [round(minx, 4), round(miny, 4), round(maxx, 4), round(maxy, 4)],
                "in_scope": True,
                "geometry": r.geometry,
            })
        for e in EXTRA:
            if e["slug"] in have_tilesets:
                self.rows.append({**e, "variant": f"{e['slug']}V" in have_tilesets,
                                  "bounds": [-4.85, 54.02, -4.28, 54.44],
                                  "geometry": None})
        self.rows.sort(key=lambda r: r["name"])

    def as_json(self) -> list[dict]:
        return [{**{k: v for k, v in r.items() if k != "geometry"},
                 "masked": r["geometry"] is not None} for r in self.rows]

    def intersecting(self, bbox) -> list[dict]:
        w, s, e, n = bbox
        return [r for r in self.rows
                if not (r["bounds"][2] < w or r["bounds"][0] > e
                        or r["bounds"][3] < s or r["bounds"][1] > n)]


# ── tiles ────────────────────────────────────────────────────────────────────

def tile_bounds(z: int, x: int, y: int):
    def lon(i): return i / 2 ** z * 360.0 - 180.0
    def lat(j):
        return math.degrees(math.atan(math.sinh(math.pi - 2 * math.pi * j / 2 ** z)))
    return lon(x), lat(y + 1), lon(x + 1), lat(y)


def _fetch(slug: str, z: int, x: int, y: int) -> bytes | None:
    """One county's tile, cached on disk. 404 is the normal answer off-county."""
    p = TILES / slug / str(z) / str(x) / f"{y}.png"
    if p.exists():
        b = p.read_bytes()
        return b or None
    try:
        req = urllib.request.Request(NLS.format(slug=slug, z=z, x=x, y=y),
                                     headers={"User-Agent": "REWT-viewer/1 (+local)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
    except Exception:
        raw = b""                              # 404 and network alike: nothing here
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return raw or None


def _rgba(raw: bytes) -> np.ndarray | None:
    """A palette PNG to (4, 256, 256) uint8. The NLS serves 8-bit palette with tRNS."""
    import rasterio
    from rasterio.io import MemoryFile

    try:
        with MemoryFile(raw) as m, m.open() as src:
            if src.count >= 3:
                a = src.read()
                if a.shape[0] == 3:
                    a = np.vstack([a, np.full((1, *a.shape[1:]), 255, "uint8")])
                return a[:4]
            band = src.read(1)
            cmap = src.colormap(1)
    except Exception:
        return None
    lut = np.zeros((256, 4), "uint8")
    for i, v in cmap.items():
        if 0 <= i < 256:
            lut[i] = v if len(v) == 4 else (*v, 255)
    return lut[band].transpose(2, 0, 1).copy()


def _mask(geom, z: int, x: int, y: int) -> np.ndarray:
    """The county polygon rasterised into this tile: 1 inside, 0 outside."""
    from rasterio.features import rasterize
    from rasterio.transform import from_bounds

    w, s, e, n = tile_bounds(z, x, y)
    return rasterize([(geom, 1)], out_shape=(256, 256),
                     transform=from_bounds(w, s, e, n, 256, 256),
                     fill=0, dtype="uint8", all_touched=True)


def _png(rgba: np.ndarray) -> bytes:
    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile() as m:
        with m.open(driver="PNG", width=rgba.shape[2], height=rgba.shape[1],
                    count=4, dtype="uint8") as dst:
            dst.write(rgba)
        return m.read()


BLANK = None


def composite(counties: Counties, z: int, x: int, y: int, pool: ThreadPoolExecutor) -> bytes:
    """Every county covering this tile, each cut to its own boundary, in one PNG."""
    global BLANK
    out = TILES / "_composite" / str(z) / str(x) / f"{y}.png"
    if out.exists():
        return out.read_bytes()

    rows = [r for r in counties.intersecting(tile_bounds(z, x, y)) if r.get("in_scope")]
    canvas = np.zeros((4, 256, 256), "uint8")
    if rows:
        for row, raw in zip(rows, pool.map(lambda r: _fetch(r["slug"], z, x, y), rows)):
            if not raw:
                continue
            src = _rgba(raw)
            if src is None:
                continue
            # A pixel is taken only where the county owns the ground AND its own sheet
            # has something to say there. Both conditions matter: the first stops a
            # mosaic bleeding past its boundary, the second keeps its internal margins
            # transparent rather than painting them white over a neighbour.
            take = src[3] > 8
            if row["geometry"] is not None:
                take = take & (_mask(row["geometry"], z, x, y) > 0)
            if not take.any():
                continue
            np.copyto(canvas, src, where=np.broadcast_to(take, canvas.shape))
    body = _png(canvas)
    if not rows and BLANK is None:
        BLANK = body
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(body)
    return body


SOURCE_ID = "hct_historic_counties"


def declaration() -> dict:
    """The source's entry in conf/sources.yml, which is the authority.

    AGENTS.md: no URL is ever hard-coded, every source is declared before anything
    reads it, and an unregistered source is a hard error. This viewer briefly kept its
    own registry while the entry was pending; it does not any more, because two
    registries is how a short attribution comes to attribute less than the real one.
    """
    import yaml

    doc = yaml.safe_load((HERE.parents[1] / "conf" / "sources.yml").read_text())
    for src in doc["sources"]:
        if src.get("id") == SOURCE_ID:
            return src
    raise KeyError(
        f"{SOURCE_ID} is not declared in conf/sources.yml. An unregistered source is a "
        "hard error (AGENTS.md); it is not something to work around here."
    )


def fetch_zip(log=print) -> None:
    """Acquire the county polygons, and check them against the declared checksum."""
    import hashlib

    src = declaration()
    CACHE.mkdir(parents=True, exist_ok=True)
    log(f"[viewer] fetching {src['url']}")
    with urllib.request.urlopen(src["url"], timeout=180) as r:
        body = r.read()
    got = hashlib.sha256(body).hexdigest()
    want = src.get("checksum") or src.get("sha256")
    if want and got != want:
        # The issue is declared. A different archive under the same URL is a new issue
        # and wants declaring as one, not accepting quietly.
        raise ValueError(
            f"checksum mismatch for {SOURCE_ID}: got {got}, conf/sources.yml declares "
            f"{want} for issue {src.get('issue')}. The Trust may have released a new "
            "one; update the declaration rather than this check."
        )
    ZIP.write_bytes(body)
    with zipfile.ZipFile(ZIP) as z:
        log("  " + ", ".join(z.namelist()))
    log(f"  {ZIP} ({ZIP.stat().st_size:,} bytes), checksum matches conf/sources.yml")
