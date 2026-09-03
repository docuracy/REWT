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


def fetch_wcs(source_id: str, *, force: bool = False) -> Acquisition:
    """Fetch a WCS coverage over a declared window, in tiles, and pin the bytes.

    The service serves ONE seamless coverage subsettable to any window, so the tiling
    here is about request size and nothing else — there is no mosaicking problem of the
    kind Terrain 50 has, where the publisher's own tiles have to be reconciled.

    **The pin is the bytes, and it has to be.** `emodnet__mean` is whatever release is
    current; the dated coverage ids are PAST releases and there is no `_2024`, so asking
    for a dated id would silently take older data rather than freezing the current one.
    The identifier cannot express "the release I built against", so the digest does —
    the same shape as OS Open Rivers' `frozen_issue` (D-054), arrived at from the
    opposite direction.

    The manifest digest is over the sorted `name:sha256` of every window, so it moves if
    any window's bytes move and does not depend on the order they were fetched in.
    """
    src = config.source(source_id)
    p = config.params()
    west, south, east, north = [float(v) for v in p("sea.extent_wgs84")]
    step = float(p("sea.window_deg"))
    if not (east > west and north > south):
        raise AcquisitionError(
            f"sea.extent_wgs84 is not a window: {west},{south} to {east},{north}"
        )

    dest = paths.ROOT / src.get("cache_path")
    dest.mkdir(parents=True, exist_ok=True)
    coverage = src.get("coverage_id")
    wcs = src.get("wcs") or {}

    lats = _steps(south, north, step)
    lons = _steps(west, east, step)
    windows = [(la, lo) for la in lats for lo in lons]
    log.info(
        f"{src.title}: {len(windows)} windows of {step}\u00b0 over "
        f"{west},{south} to {east},{north}"
    )

    digests: list[str] = []
    fetched = skipped = 0
    for lat0, lon0 in windows:
        lat1, lon1 = min(lat0 + step, north), min(lon0 + step, east)
        name = f"emodnet_{lat0:+06.2f}_{lon0:+07.2f}.tif".replace("+", "p").replace("-", "m")
        out = dest / name
        if out.exists() and not force:
            skipped += 1
        else:
            params = {
                "service": "WCS",
                "version": wcs.get("version", "2.0.1"),
                "request": "GetCoverage",
                "coverageId": coverage,
                "format": wcs.get("format", "image/tiff"),
            }
            url = (
                f"{src.raw['url']}?"
                + "&".join(f"{k}={v}" for k, v in params.items())
                + f"&subset=Lat({lat0},{lat1})&subset=Long({lon0},{lon1})"
            )
            resp = requests.get(url, timeout=_TIMEOUT)
            if resp.status_code != 200 or not resp.content:
                raise AcquisitionError(
                    f"{source_id}: window Lat({lat0},{lat1}) Long({lon0},{lon1}) "
                    f"returned HTTP {resp.status_code}, {len(resp.content)} bytes. "
                    "Named rather than skipped: a missing window is a hole in the cost "
                    "surface, and a least-cost path routes through a hole without "
                    "saying so."
                )
            if not resp.content.startswith((b"II", b"MM")):
                raise AcquisitionError(
                    f"{source_id}: window Lat({lat0},{lat1}) Long({lon0},{lon1}) is not "
                    f"a TIFF. WCS reports failure as a 200 with an XML body, so the "
                    f"first bytes are checked rather than the status: {resp.content[:200]!r}"
                )
            out.write_bytes(resp.content)
            fetched += 1
        digests.append(f"{name}:{sha256_file(out)}")

    manifest = hashlib.sha256("\n".join(sorted(digests)).encode("utf-8")).hexdigest()
    total = sum((dest / d.split(":")[0]).stat().st_size for d in digests)

    # THE PIN BITES HERE, or it is only a comment. The coverage id cannot name the
    # release we built against — `emodnet__mean` is whatever is current — so the
    # digest is the only thing that can, and a digest nothing compares is provenance
    # theatre. Same reasoning as OS Open Rivers' frozen_issue (D-054): fail rather
    # than warn, because a reissue is a rare event nobody is present for.
    declared = src.get("checksum", default=None)
    if declared and declared != manifest:
        raise AcquisitionError(
            f"{source_id} is pinned to manifest {declared[:16]}\u2026 and what was "
            f"fetched hashes to {manifest[:16]}\u2026. The published coverage has "
            "moved under the pin.\n\n"
            "This is a decision, not a refresh: the cost surface, every sea route and "
            "every figure measured against them come from these bytes. Either restore "
            "the pinned windows, or take the decision to move the pin and record what "
            "changed in DECISIONS.md."
        )
    log.done(
        f"{len(digests)} windows ({fetched} fetched, {skipped} already held), "
        f"{total / 1e6:,.0f} MB, manifest {manifest[:16]}"
    )

    acq = Acquisition(
        source_id=source_id,
        # WHAT THE PUBLISHER CALLED IT, AND WHEN WE TOOK IT — not a shortened digest.
        #
        # This field said `manifest[:16]`, on the reasoning that the bytes are the pin
        # because EMODnet's coverage ids cannot name a release. The pinning reasoning is
        # right and the field was the wrong place for it: `issue` is read as a version,
        # it appeared as one in provenance.json, ATTRIBUTION.md and published/README.md,
        # and sixteen hex characters are meaningless as a version. Worse, it HID the
        # thing that makes the source reproducible — a reader would look for a release
        # that does not exist instead of matching the digest.
        #
        # The full sha256 is carried in `sha256` below and is printed beside this in
        # every record, so nothing is lost by saying here what was actually asked for
        # and when. Found by rewt-86 reading the release rather than the code.
        issue=f"{coverage}, acquired "
              f"{datetime.now(timezone.utc).date().isoformat()}",
        file_name=f"{len(digests)} windows under {src.get('cache_path')}",
        url=f"{src.raw['url']} coverageId={coverage}",
        bytes=total,
        md5=None,
        sha256=manifest,
        acquired_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        extracted_to=paths.rel(dest),
        members=len(digests),
    )
    ledger = _load_ledger()
    ledger[source_id] = acq.to_dict()
    _save_ledger(ledger)
    return acq


def _steps(lo: float, hi: float, step: float) -> list[float]:
    out, v = [], lo
    while v < hi - 1e-9:
        out.append(round(v, 6))
        v += step
    return out


def fetch(source_id: str, *, force: bool = False) -> Acquisition:
    """Fetch one declared source by whatever route its declaration names."""
    src = config.source(source_id)
    api = src.get("api")
    if api == "os_downloads":
        return fetch_os_downloads(source_id, force=force)
    if api == "arcgis":
        return fetch_arcgis(source_id, force=force)
    if api == "wcs":
        return fetch_wcs(source_id, force=force)
    if src.get("wcs") or src.get("tile_index"):
        raise AcquisitionError(
            f"{source_id} is fetched per section, never nationally (PLAN.md §4, D-006). "
            "It has no bulk acquisition; use rewt.lidar."
        )
    raise AcquisitionError(f"{source_id}: conf/sources.yml declares no way to fetch it")


def verification(source_id: str) -> dict:
    """What this repository can actually say about a source's bytes.

    `conf/sources.yml` carries a `status:` field which nothing wrote — five genuinely
    acquired sources said "unverified" and the only two saying "verified" were the two
    nothing here had ever derived. A populated field in the right-looking place that
    nobody maintains is the shape of defect this project keeps finding, so the claim is
    computed here and the field is checked against it rather than believed.

    "verified" means one thing only: **this repository digested the bytes it holds and
    they match the declared checksum.**
    """
    src = config.source(source_id)
    declared = src.get("checksum")
    acq = acquisition(source_id)
    cached = None
    if acq and acq.file_name and not acq.file_name.startswith("["):
        candidate = src.dir / "archive" / acq.file_name
        if candidate.exists():
            cached = candidate
    if cached is None:
        for pattern in ("*.zip", "*.gpkg"):
            hits = sorted(src.dir.rglob(pattern))
            if hits:
                cached = hits[0]
                break

    state = {
        "source_id": source_id,
        "declared_checksum": declared,
        "acquired": acq is not None,
        "issue": acq.issue if acq else None,
        "file": paths.rel(cached) if cached else None,
        "computed": None,
        "status": "unverified",
        "why": "",
    }
    if cached is None:
        state["why"] = "nothing cached to digest"
        return state
    state["computed"] = sha256_file(cached)
    if not declared:
        # The four OS products declare no checksum in conf/sources.yml because the
        # publisher's own md5 is checked at fetch and the sha256 is recorded in
        # data/raw/acquisitions.json instead. That record is this repository's own
        # derivation, so it is evidence — just held elsewhere.
        if acq and acq.sha256:
            same = state["computed"] == acq.sha256
            state["status"] = "verified" if same else "MISMATCH"
            state["why"] = (
                f"matches the digest recorded at acquisition ({acq.issue})"
                if same
                else f"recorded {acq.sha256[:16]}… at acquisition but the cached file "
                f"now digests to {state['computed'][:16]}… — data/raw/ is meant to be "
                "immutable"
            )
            return state
        state["why"] = "no checksum declared and none recorded at acquisition"
        state["status"] = "acquired"
        return state
    if state["computed"] == declared:
        state["status"] = "verified"
        state["why"] = "the cached bytes match the declared checksum"
    else:
        state["status"] = "MISMATCH"
        state["why"] = (
            f"declared {declared[:16]}… but the cached file digests to "
            f"{state['computed'][:16]}… — a wrong checksum fails on a good file and "
            "nobody can tell which end is broken"
        )
    return state


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


def resolve_declared_urls() -> list[dict]:
    """Request every `url` in the manifest and report what it answers.

    **Here and not in the CLI, because this fetches declared sources.**
    `test_only_one_module_may_do_it` holds that no module but this one may reach the
    network for a source, so that an unregistered source is an error rather than a quiet
    download. The first version of this check lived in `rewt/cli.py` and tripped that
    invariant; rewt-c1 declined to widen the rule to fit the new caller and offered the
    choice, which was the right way round. A HEAD from the CLI is not a download, but it
    *is* a request to a declared source, and the rule's reason covers it.

    **Why it exists.** `conf/sources.yml` stopped being only a build input the day
    `docs/_data/sources.yml` became a projection of it: every `url` is now a link on the
    published Sources page. Two were wrong at once — an invented data.gov.uk slug that
    404s for want of a uuid segment, and a bare `spatialdata.gov.scot` that 403s without
    its www — and both were plausible enough that no human would click them and no test
    would exercise them. Suggested by rewt-16: the failure was invisible by construction.

    **Two kinds of url are asked different questions**, because the first version of this
    reported three failures and two were its own. A bare GET on a WCS endpoint returns
    500 where `GetCapabilities` returns 200; and a tile template with `{layer}/{z}/{x}/{y}`
    is not an address at all. A check that cries wolf teaches the reader to skip the line.
    """
    import requests

    out: list[dict] = []
    with requests.Session() as session:
        for src in sorted(config.sources(), key=lambda s: s.id):
            url = src.raw.get("url")
            row = {"id": src.id, "url": url, "status": "—", "note": "", "ok": True}
            if not url:
                row["note"] = "no url declared"
                out.append(row)
                continue
            if "{" in url:
                row["note"] = "a tile template, not an address"
                out.append(row)
                continue
            # Detected from the entry's own declaration rather than by sniffing the path,
            # so a service that fails to declare itself is still checked as a page.
            service = next(
                (s for s in ("wcs", "wfs", "wms")
                 if isinstance(src.raw.get(s), dict) or f"/{s}" in url.lower()),
                None,
            )
            params = {"service": service.upper(), "request": "GetCapabilities"} if service else None
            try:
                reply = session.get(url, params=params, timeout=40, allow_redirects=True)
                row["status"] = str(reply.status_code)
                notes = []
                if not reply.ok:
                    notes.append("does not resolve")
                    row["ok"] = False
                if service:
                    notes.append(f"as a {service.upper()} service")
                if reply.history:
                    notes.append(f"via {len(reply.history)} redirect(s)")
                row["note"] = " ".join(notes) or "ok"
            except Exception as exc:
                row["note"] = type(exc).__name__
                row["ok"] = False
            out.append(row)
    return out
