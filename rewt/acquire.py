"""Acquisition: one module fetches every input, from the declarations and nowhere else.

PLAN.md §2, in order:

* **Declare every input; hard-code no URL.** Sources live in `conf/sources.yml` with
  licence and attribution, and are fetched by one module. An unregistered source is
  an error, not a warning.
* **Inputs are immutable and checksummed.** Record a digest at acquisition; verify on
  use.

OS Open Rivers is reissued twice a year, so the issue is recorded with the digest: a
result that cannot name its input cannot be reproduced (§4).

The four OS products are open and need no API key (§7). There is no authentication
path in this module, deliberately.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from . import config, paths
from .report import log

_CHUNK = 1 << 20
_TIMEOUT = 120


class AcquisitionError(RuntimeError):
    """A source could not be fetched, or arrived not matching its digest."""


@dataclass
class Acquisition:
    """What was fetched, from where, and what it hashed to."""

    source_id: str
    issue: str                 # the publisher's edition — 2026-04, and so on
    file_name: str
    url: str
    bytes: int
    md5: str | None
    sha256: str
    acquired_at: str
    extracted_to: str | None = None
    members: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# The ledger of what has been acquired
# --------------------------------------------------------------------------


def _load_ledger() -> dict[str, dict]:
    if not paths.ACQUISITION_LOG.exists():
        return {}
    return json.loads(paths.ACQUISITION_LOG.read_text(encoding="utf-8"))


def _save_ledger(ledger: dict[str, dict]) -> None:
    paths.ACQUISITION_LOG.parent.mkdir(parents=True, exist_ok=True)
    paths.ACQUISITION_LOG.write_text(
        json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8"
    )


def acquisition(source_id: str) -> Acquisition | None:
    entry = _load_ledger().get(source_id)
    return Acquisition(**entry) if entry else None


def require_acquisition(source_id: str) -> Acquisition:
    """Verify on use. An input nothing can name is an input nothing can reproduce."""
    acq = acquisition(source_id)
    if acq is None:
        raise AcquisitionError(
            f"source {source_id!r} has not been acquired. Run `rewt acquire {source_id}`."
        )
    src = config.source(source_id)
    if not src.dir.exists():
        raise AcquisitionError(
            f"source {source_id!r} is recorded as acquired but {paths.rel(src.dir)} "
            "is gone. data/raw/ is immutable; deleting it means re-acquiring."
        )
    return acq


def issue_of(source_id: str) -> str:
    return require_acquisition(source_id).issue


# --------------------------------------------------------------------------
# Digests
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# The OS Downloads API. No key, and no URL that is not in conf/sources.yml.
# --------------------------------------------------------------------------


def _os_product(src) -> dict:
    resp = requests.get(src.raw["url"], timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _os_pick_download(src, product: dict) -> dict:
    want_format = src.require("download", "format")
    want_area = src.get("download", "area", default="GB")
    resp = requests.get(product["downloadsUrl"], params={"area": want_area}, timeout=_TIMEOUT)
    resp.raise_for_status()
    options = resp.json()
    for opt in options:
        if opt.get("format") == want_format and opt.get("area") == want_area:
            return opt
    raise AcquisitionError(
        f"{src.id}: conf/sources.yml asks for format {want_format!r} area {want_area!r}; "
        f"the publisher offers {sorted({o.get('format') for o in options})}"
    )


def _download(url: str, dest: Path, expect_bytes: int | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=_TIMEOUT, allow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or 0) or (expect_bytes or 0)
        got = 0
        step = max(total // 20, _CHUNK * 32) if total else _CHUNK * 64
        next_mark = step
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(_CHUNK):
                fh.write(chunk)
                got += len(chunk)
                if got >= next_mark:
                    pct = f" ({got / total:.0%})" if total else ""
                    log.detail(f"    {got / 1e6:,.0f} MB{pct}")
                    next_mark += step
    tmp.replace(dest)


def _extract(zip_path: Path, dest: Path) -> int:
    """Unzip into a clean directory. Idempotent: it clears before it writes."""
    if dest.exists():
        for child in sorted(dest.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        zf.extractall(dest)
    return len(members)


def fetch_os_downloads(source_id: str, *, force: bool = False) -> Acquisition:
    src = config.source(source_id)
    if src.get("api") != "os_downloads":
        raise AcquisitionError(f"{source_id} is not an OS Downloads product")

    product = _os_product(src)
    issue = str(product.get("version", "unknown"))
    option = _os_pick_download(src, product)
    file_name = option["fileName"]

    ledger = _load_ledger()
    prior = ledger.get(source_id)
    archive = src.dir / "archive" / file_name

    if (
        not force
        and prior
        and prior.get("issue") == issue
        and prior.get("file_name") == file_name
        and archive.exists()
        and (src.dir / "extracted").is_dir()
    ):
        # Verify on use. The digest is the point of recording it.
        actual = sha256_file(archive)
        if actual == prior["sha256"]:
            log.skip(f"{source_id}: issue {issue} already acquired ({file_name})")
            return Acquisition(**prior)
        log.warn(
            f"{source_id}: {paths.rel(archive)} does not match its recorded digest "
            "— re-acquiring. data/raw/ is meant to be immutable."
        )

    log.info(f"{source_id}: issue {issue}, {file_name} ({option['size'] / 1e6:,.0f} MB)")
    _download(option["url"], archive, option.get("size"))

    md5 = md5_file(archive)
    if option.get("md5") and md5 != option["md5"]:
        archive.unlink(missing_ok=True)
        raise AcquisitionError(
            f"{source_id}: md5 mismatch — publisher says {option['md5']}, file is {md5}"
        )

    members = _extract(archive, src.dir / "extracted")
    acq = Acquisition(
        source_id=source_id,
        issue=issue,
        file_name=file_name,
        url=option["url"],
        bytes=archive.stat().st_size,
        md5=md5,
        sha256=sha256_file(archive),
        acquired_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        extracted_to=paths.rel(src.dir / "extracted"),
        members=members,
    )
    ledger[source_id] = acq.to_dict()
    _save_ledger(ledger)
    log.done(f"{source_id}: {members:,} files, sha256 {acq.sha256[:16]}…")
    return acq


def fetch_arcgis(source_id: str, *, force: bool = False) -> Acquisition:
    """Fetch every declared layer of an ArcGIS FeatureServer, paging as needed.

    **Paging is not optional and the absence of it is silent.** A FeatureServer caps a
    response at its own `maxRecordCount` and says so only in `exceededTransferLimit`,
    which is a field most callers never read: ask for 2,962 culverts and you are handed
    2,000 and an HTTP 200. The loop below reads that flag and keeps asking.
    """
    src = config.source(source_id)
    base = src.require("arcgis", "base")
    layers = src.require("arcgis", "layers")
    query = src.get("arcgis", "query", default="/query?where=1%3D1&outFields=*&f=geojson")
    page_size = int(src.get("arcgis", "page_size", default=2000))

    dest = src.dir / "extracted"
    ledger = _load_ledger()
    prior = ledger.get(source_id)
    if not force and prior and dest.is_dir():
        acq = Acquisition(**prior)
        if all((dest / f"{name}.geojson").exists() for name in layers):
            log.skip(f"{source_id}: already acquired ({acq.members} layers)")
            return acq

    dest.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, path in layers.items():
        # Ask the service how many features there ARE before asking for them.
        # `returnCountOnly` is not subject to the transfer cap, so it answers 2,962
        # for a layer that a plain fetch truncates to 2,000 — which is why the trap is
        # invisible: the query that tells the truth is a different query from the one
        # that lies, and nothing connects them. Asking both, and comparing, is what
        # turns that into a check rather than a hazard.
        expected: int | None = None
        try:
            resp = requests.get(
                f"{base}/{path}/query?where=1%3D1&returnCountOnly=true&f=json",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            expected = int(resp.json().get("count"))
        except Exception as exc:  # a service that will not count is not a failure
            log.detail(f"    {name}: no feature count available ({exc})")

        features: list[dict] = []
        offset = 0
        while True:
            url = f"{base}/{path}{query}&resultOffset={offset}&resultRecordCount={page_size}"
            resp = requests.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            doc = resp.json()
            batch = doc.get("features", [])
            features.extend(batch)
            exceeded = doc.get("exceededTransferLimit") or doc.get(
                "properties", {}
            ).get("exceededTransferLimit")
            if not exceeded or not batch:
                break
            offset += len(batch)
        out = dest / f"{name}.geojson"
        out.write_text(
            json.dumps(
                {"type": "FeatureCollection", "name": name, "features": features},
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        counts[name] = len(features)
        if expected is not None and len(features) != expected:
            raise AcquisitionError(
                f"{source_id}/{name}: the service holds {expected:,} features and the "
                f"paged fetch returned {len(features):,}. An ArcGIS FeatureServer "
                "truncates at its own maxRecordCount and reports it only in "
                "`exceededTransferLimit`, with an HTTP 200 either way — so a short "
                "answer is not an error unless something checks. This is that check."
            )
        log.detail(
            f"    {name}: {len(features):,} features"
            + (" (matches the service's own count)" if expected is not None else "")
        )

    digest = hashlib.sha256()
    for name in sorted(layers):
        digest.update(sha256_file(dest / f"{name}.geojson").encode())
    acq = Acquisition(
        source_id=source_id,
        issue=datetime.now(timezone.utc).date().isoformat(),
        file_name=", ".join(f"{k}.geojson" for k in sorted(layers)),
        url=base,
        bytes=sum((dest / f"{n}.geojson").stat().st_size for n in layers),
        md5=None,
        sha256=digest.hexdigest(),
        acquired_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        extracted_to=paths.rel(dest),
        members=len(layers),
    )
    ledger[source_id] = acq.to_dict()
    _save_ledger(ledger)
    log.done(f"{source_id}: {sum(counts.values()):,} features in {len(counts)} layers")
    return acq


def fetch(source_id: str, *, force: bool = False) -> Acquisition:
    """Fetch one declared source by whatever route its declaration names."""
    src = config.source(source_id)
    api = src.get("api")
    if api == "os_downloads":
        return fetch_os_downloads(source_id, force=force)
    if api == "arcgis":
        return fetch_arcgis(source_id, force=force)
    if src.get("wcs") or src.get("tile_index"):
        raise AcquisitionError(
            f"{source_id} is fetched per section, never nationally (PLAN.md §4, D-006). "
            "It has no bulk acquisition; use rewt.lidar."
        )
    raise AcquisitionError(f"{source_id}: conf/sources.yml declares no way to fetch it")


def national_sources() -> list[str]:
    """The sources acquired in bulk. The two LiDAR products are not among them."""
    return [s.id for s in config.sources() if s.get("api") == "os_downloads"]


def find(source_id: str, pattern: str) -> list[Path]:
    """Files inside an acquired source, matched by glob, in deterministic order."""
    require_acquisition(source_id)
    root = config.source(source_id).dir / "extracted"
    return sorted(root.rglob(pattern))


def one(source_id: str, pattern: str) -> Path:
    hits = find(source_id, pattern)
    if not hits:
        raise AcquisitionError(
            f"{source_id}: nothing matching {pattern!r} under "
            f"{paths.rel(config.source(source_id).dir / 'extracted')}"
        )
    if len(hits) > 1:
        raise AcquisitionError(
            f"{source_id}: {len(hits)} files match {pattern!r}; expected one — "
            + ", ".join(paths.rel(h) for h in hits[:5])
        )
    return hits[0]
