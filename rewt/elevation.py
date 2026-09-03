"""The 1 m elevation sweep: one reading per node, from the two registered sources.

D-085. PLAN.md §5 specifies these two DEMs as a **per-section** instrument, explicitly
against a national sweep; this overrides that, and the reason is that §5 rejected the
sweep assuming a fetch per node. The fetch is per kilometre SQUARE — 51,892 of them hold
an in-scope node, at a median of 2 nodes each — which is about half the requests, and
both services align on the OSGB kilometre grid so it costs nothing to arrange.

**The node is the unit, not the link.** 197,734 nodes against 195,568 links with two ends
each: sampling per node and reusing the value at both ends of every incident link is
197,734 samples rather than 391,136.

**THE COVERAGE GUARD IS THE WHOLE OF THE CORRECTNESS ARGUMENT.** Asked for a point in
Wales the English service returns HTTP 200 and a structurally valid GeoTIFF in which every
cell is 0.0 and no nodata is declared. Measured live on 3 September 2026 at
os:node/04C2FAE8: the English service says 0.00 m, the Welsh tile for the same node says
498.10 m. Nothing in the English response says the data is absent, so:

* coverage is decided by COUNTRY, from Boundary-Line, and never inferred from nodata —
  whose value differs between the services (-3.4e38 against -9999) and is absent in
  exactly the failing case;
* and the reading is then confirmed: an all-zero box is refused rather than recorded.

A refusal is a reading of `None` with a reason, never a 0.0. D-077: unknown must fail
towards the visible fault, and a node with no elevation is visibly missing where a node at
sea level is not.

**Provenance is per tile**, because a 51,892-tile cache is not a checksummable artefact.
The manifest records, for every square, the source, the request, a digest of the bytes,
the publisher's own survey date where it gives one, and when we fetched it. That is what
`conf/sources.yml`'s `checksum: null` on these two entries has to become.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from . import config, paths
from .report import log

MANIFEST = paths.RAW / "elevation_sweep.json"


class CoverageRefused(RuntimeError):
    """The square is not covered by the service that was asked, and said so silently."""


@dataclass(frozen=True)
class Square:
    """One OSGB kilometre square, the unit of fetching."""

    e: int          # easting of the south-west corner
    n: int          # northing of the south-west corner
    country: str    # 'England' or 'Wales' — decides which service answers

    @property
    def key(self) -> str:
        return f"{self.e}_{self.n}"

    def bounds(self, buffer_m: float = 0.0) -> tuple[float, float, float, float]:
        size = float(config.param("terrain.sweep.square_m"))
        return (self.e - buffer_m, self.n - buffer_m,
                self.e + size + buffer_m, self.n + size + buffer_m)


@dataclass
class TileRecord:
    """One row of the manifest. Everything needed to fetch this tile again."""

    key: str
    country: str
    source_id: str
    request: str
    path: str
    sha256: str
    bytes: int
    fetched: str
    survey_date: Optional[str] = None
    note: str = ""


def squares_for(points: Iterable[tuple[float, float]], country_of) -> list[Square]:
    """The distinct kilometre squares holding any of these points.

    `country_of` answers 'England', 'Wales' or None for a coordinate. A square whose
    points are in neither country is dropped here rather than fetched and refused: the
    sweep covers the two countries it has sources for, and says so.
    """
    size = int(config.param("terrain.sweep.square_m"))
    seen: dict[tuple[int, int], str] = {}
    skipped = 0
    for e, n in points:
        cell = (int(math.floor(e / size) * size), int(math.floor(n / size) * size))
        if cell in seen:
            continue
        country = country_of(e, n)
        if country is None:
            skipped += 1
            continue
        seen[cell] = country
    if skipped:
        log.info(f"{skipped:,} node(s) lie outside England and Wales; no 1 m source covers them")
    return [Square(e, n, c) for (e, n), c in sorted(seen.items())]


# -- fetching ------------------------------------------------------------------

def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_england(square: Square, session) -> tuple[bytes, str]:
    """A WCS window over the square plus the sampling buffer.

    The English service will serve any window, so the square is requested with the
    window's half-width added on every side and a node anywhere inside has its full box
    in one raster. That is why the 40 m edge case PLAN.md §5 warns about never arises.
    """
    src = config.source("ea_lidar_composite_dtm_1m")
    base = src.require("wcs", "base")
    x0, y0, x1, y1 = square.bounds(float(config.param("terrain.sweep.fetch_buffer_m")))
    query = (
        f"{base}?service=WCS&version={src.require('wcs', 'version')}"
        f"&request=GetCoverage&coverageId={src.require('wcs', 'coverage')}"
        f"&format={src.require('wcs', 'format')}"
        f"&subset=E({x0},{x1})&subset=N({y0},{y1})"
    )
    response = session.get(query, timeout=int(config.param("terrain.sweep.timeout_s")))
    response.raise_for_status()
    return response.content, query


def welsh_tile_url(square: Square, session) -> tuple[Optional[str], Optional[str]]:
    """Ask the NRW catalogue which GeoTIFF covers this square.

    Returns the URL and the publisher's own survey date, which the catalogue gives per
    tile and which is the provenance `checksum: null` cannot supply.
    """
    # ASK AT THE CENTRE, NOT OVER THE SQUARE. WFS `bbox` is INTERSECTS, and a square's
    # own bounds touch its eight neighbours at the corners and edges: querying the full
    # square returns NINE tiles and `features[0]` is the diagonally opposite one. That is
    # not a hypothetical — it is what this function did on its first run, and the sweep
    # then sampled a node that was not in the raster it had fetched. It was caught only
    # because the sampler refused an empty window rather than defaulting; had it taken a
    # nearest cell it would have returned a plausible elevation from a kilometre away.
    src = config.source("nrw_lidar_dtm_1m")
    size = float(config.param("terrain.sweep.square_m"))
    cx, cy = square.e + size / 2.0, square.n + size / 2.0
    srs = src.require("tile_index", "srs")
    params = {
        "service": "WFS", "version": src.require("tile_index", "version"),
        "request": "GetFeature", "typeNames": src.require("tile_index", "type_name"),
        "outputFormat": "application/json", "srsName": srs,
        "bbox": f"{cx - 1},{cy - 1},{cx + 1},{cy + 1},{srs}",
    }
    response = session.get(src.require("tile_index", "wfs"), params=params,
                           timeout=int(config.param("terrain.sweep.timeout_s")))
    response.raise_for_status()
    features = response.json().get("features") or []
    if not features:
        return None, None
    if len(features) > 1:
        log.warn(f"NRW catalogue returned {len(features)} tiles for the centre of "
                 f"square {square.key}; taking the first and verifying its bounds")
    props = features[0]["properties"]
    url = props.get(src.require("tile_index", "url_field"))
    if url and not url.startswith("http"):
        url = "https://" + url
    return url, props.get("date")


def fetch_wales(square: Square, session) -> tuple[bytes, str, Optional[str]]:
    url, survey_date = welsh_tile_url(square, session)
    if url is None:
        raise CoverageRefused(f"NRW catalogue holds no DTM tile for square {square.key}")
    response = session.get(url, timeout=int(config.param("terrain.sweep.timeout_s")))
    response.raise_for_status()
    if not covers(response.content, square):
        raise CoverageRefused(
            f"NRW tile {url.rsplit('/', 1)[-1]} does not cover square {square.key}; "
            "the catalogue named a tile that does not contain the ground asked for"
        )
    return response.content, url, survey_date


# -- sampling ------------------------------------------------------------------

def covers(payload: bytes, square: Square) -> bool:
    """Does this raster actually contain the square it was fetched for?

    A catalogue row is a claim; the raster's own bounds are the thing. Checked because
    the first version of `welsh_tile_url` returned a neighbouring tile and nothing but
    an empty sample window said so.
    """
    import rasterio

    x0, y0, x1, y1 = square.bounds()
    with rasterio.open(io.BytesIO(payload)) as dataset:
        b = dataset.bounds
    return b.left <= x0 and b.bottom <= y0 and b.right >= x1 and b.top >= y1


def sample(payload: bytes, easting: float, northing: float) -> tuple[Optional[float], str]:
    """The low percentile of the window around one point, or None and a reason.

    Never returns 0.0 as a measurement where the box is entirely zero: that is the
    English service's silent answer for ground it does not cover, and it is refused.
    """
    import rasterio

    half = float(config.param("terrain.sweep.window_half_m"))
    pct = float(config.param("terrain.sweep.percentile"))
    floor = int(config.param("terrain.sweep.min_valid_cells"))

    with rasterio.open(io.BytesIO(payload)) as dataset:
        row, col = dataset.index(easting, northing)
        size = int(round(half / abs(dataset.res[0])))
        window = rasterio.windows.Window(col - size, row - size, 2 * size, 2 * size)
        box = dataset.read(1, window=window, boundless=True,
                           fill_value=dataset.nodata if dataset.nodata is not None else np.nan)
        box = box.astype("float64")
        nodata = dataset.nodata

    valid = box[np.isfinite(box)]
    if nodata is not None:
        valid = valid[valid != nodata]
    # Both services use a large negative sentinel; -3.4e38 survives an != comparison
    # against a float32-widened value, so bound it rather than trusting equality.
    valid = valid[valid > -1000.0]

    if valid.size < floor:
        return None, f"only {valid.size} valid cell(s) in the window, floor is {floor}"
    if bool(config.param("terrain.sweep.refuse_all_zero_box")) and not np.any(valid != 0.0):
        return None, "every cell in the window is 0.0 — the service answered for ground it does not cover"
    return float(np.percentile(valid, pct)), ""


# -- the manifest --------------------------------------------------------------

def load_manifest() -> dict[str, TileRecord]:
    if not MANIFEST.exists():
        return {}
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {k: TileRecord(**v) for k, v in raw.get("tiles", {}).items()}


def save_manifest(tiles: dict[str, TileRecord]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(
            {
                "note": (
                    "Per-tile provenance for the 1 m elevation sweep (D-085). A cache of "
                    "tens of thousands of tiles is not one checksummable artefact, so the "
                    "digest is recorded per tile alongside the request that produced it "
                    "and the publisher's own survey date where it gives one."
                ),
                "config_fingerprint": config.config_fingerprint(),
                "tiles": {k: asdict(v) for k, v in sorted(tiles.items())},
            },
            indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )


def cache_path_for(square: Square) -> Path:
    src = "ea_lidar_1m" if square.country == "England" else "nrw_lidar_1m"
    return paths.RAW / src / f"{square.key}.tif"


# -- the sweep ------------------------------------------------------------------

def country_lookup():
    """A point-in-country test for England and Wales, from Boundary-Line.

    Prepared once. Used on SQUARE CENTRES rather than on nodes — 51,892 tests instead of
    197,734, and a kilometre square is small enough that its centre picks the right
    service. Where it does not, at the border, `fetch_square` falls back to the other
    service on a refusal rather than recording nothing: the guard turns a wrong guess
    into a retry instead of into a silent zero.
    """
    import shapely
    from .basins import country_polygon

    eng = country_polygon(["England"])
    wal = country_polygon(["Wales"])
    shapely.prepare(eng)      # in place; returns None
    shapely.prepare(wal)

    def of(easting: float, northing: float) -> Optional[str]:
        point = shapely.Point(easting, northing)
        if shapely.contains(eng, point):
            return "England"
        if shapely.contains(wal, point):
            return "Wales"
        return None

    return of


def fetch_square(square: Square, session) -> tuple[Optional[bytes], Optional[TileRecord], str]:
    """Fetch one square, from the service its country implies, with a border fallback.

    Returns (payload, record, why-not). The fallback exists because the country test is
    applied to the square's CENTRE: a square straddling the border may be assigned to the
    service that does not hold it, and the English service answers that case with a valid
    all-zero raster. So a refusal is retried against the other country before it is
    accepted as a refusal.
    """
    from datetime import datetime, timezone

    order = ["England", "Wales"] if square.country == "England" else ["Wales", "England"]
    last = ""
    for attempt, country in enumerate(order):
        try:
            if country == "England":
                payload, request = fetch_england(square, session)
                source_id, survey = "ea_lidar_composite_dtm_1m", None
            else:
                payload, request, survey = fetch_wales(square, session)
                source_id = "nrw_lidar_dtm_1m"
        except CoverageRefused as exc:
            last = str(exc)
            continue
        except Exception as exc:                      # network, HTTP, malformed raster
            last = f"{type(exc).__name__}: {exc}"
            continue

        # THE READING CONFIRMS THE COVERAGE. A square fetched from the wrong service comes
        # back HTTP 200 and structurally valid, so the only evidence that it is wrong is
        # that every cell is zero. Test it here, once, rather than per node.
        probe, why = sample(payload, square.e + 500, square.n + 500)
        if probe is None and "0.0" in why:
            last = f"{country} service answered for ground it does not cover"
            continue

        note = "" if attempt == 0 else f"fell back to {country} after: {last}"
        record = TileRecord(
            key=square.key, country=country, source_id=source_id, request=request,
            path=paths.rel(cache_path_for(Square(square.e, square.n, country))),
            sha256=_digest(payload), bytes=len(payload),
            fetched=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            survey_date=survey, note=note,
        )
        return payload, record, ""
    return None, None, last or "no service covered this square"


def fetch_england_window(easting: float, northing: float, session) -> tuple[bytes, str]:
    """An 80 m window around one node. THE English unit of work.

    D-086: 25.4 KB and 0.45 s against 9.44 MB and 2.16 s for the square that contains it.
    The median kilometre square holds two nodes, so a square fetch is mostly waste.
    """
    src = config.source("ea_lidar_composite_dtm_1m")
    half = float(config.param("terrain.sweep.window_half_m"))
    query = (
        f"{src.require('wcs', 'base')}?service=WCS"
        f"&version={src.require('wcs', 'version')}&request=GetCoverage"
        f"&coverageId={src.require('wcs', 'coverage')}"
        f"&format={src.require('wcs', 'format')}"
        f"&subset=E({easting - half},{easting + half})"
        f"&subset=N({northing - half},{northing + half})"
    )
    response = session.get(query, timeout=int(config.param("terrain.sweep.timeout_s")))
    response.raise_for_status()
    return response.content, query


@dataclass
class Reading:
    node_id: str
    elevation_m: Optional[float]
    source_id: Optional[str]
    country: Optional[str]
    why_not: str = ""


def _retrying(fn, *args, **kwargs):
    """Public services fail transiently. Retry, then give up loudly rather than quietly."""
    import time as _time

    attempts = int(config.param("terrain.sweep.retries"))
    base = float(config.param("terrain.sweep.backoff_base_s"))
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except CoverageRefused:
            raise                      # not transient; the service does not hold this ground
        except Exception as exc:
            last = exc
            # GEOMETRIC, not linear. A 403 from the EA service is rate limiting and
            # clears on its own, but 1.5/3.0/4.5 s retries land back inside the same
            # window and convert a transient refusal into a permanent one.
            _time.sleep(base * (2 ** i))
    raise last if last else RuntimeError("retry loop ended with no error")
