"""Deposit a release to Zenodo, with its data, and fail rather than guess.

The plain GitHub-Zenodo hook archives the source zipball. This puts the built
network in the record too, so the DOI resolves to the rivers and not only to the
method that made them.

**Everything this asserts about the deposit is checked against Zenodo's own reply.**
A deposition that reports success and holds no files is the failure mode worth
guarding: it looks archived, it has a DOI, and it is empty.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://zenodo.org/api"
TOKEN = os.environ["ZENODO_TOKEN"]
TAG = os.environ.get("TAG", "untagged")
BODY = os.environ.get("BODY", "")


def call(method: str, url: str, data=None, headers=None, raw: bytes | None = None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    payload = raw
    if data is not None:
        payload = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, payload) as r:
            text = r.read().decode()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:600]
        # Never echo the token: it is in the header, not the body, but a careless
        # dump of the request would put it in a public Actions log for ever.
        raise SystemExit(
            f"Zenodo refused {method} {url.split('?')[0]} with HTTP {exc.code}: {detail}"
        )


def main() -> None:
    zj_early = json.loads((ROOT / ".zenodo.json").read_text())
    # WHAT THE RELEASE CARRIES AND WHAT THE DOI ARCHIVES ARE NOT THE SAME LIST.
    # `viewer-data.tar` is 312 MB of vector tiles — a rendering of the network, which
    # `rewt viewer-data` regenerates from the GeoPackage beside it. Archiving it makes
    # the citable record three times larger and no more complete. It stays on the GitHub
    # release because `pages.yml` fetches it from there to serve the map.
    excludes = set(zj_early.get("deposit_excludes", []))
    assets = sorted(p for p in pathlib.Path("assets").iterdir()
                    if p.name not in excludes)
    for name in sorted(excludes):
        print(f"  not deposited (release asset only): {name}")
    if not assets:
        raise SystemExit("no assets to deposit")

    # A NEW VERSION OF ONE RECORD, NOT A NEW RECORD.
    #
    # This called POST /deposit/depositions unconditionally, which mints a fresh
    # deposition with its own concept DOI. v0.1.0-alpha and v0.1.1-alpha therefore
    # became two unrelated datasets — concepts …22238250 and …22248272 — rather than two
    # versions of one, and the badge naming the first will never resolve to the newest
    # edition. That is the promise the release notes make about a concept DOI, and it
    # was false for this project from the second release onward.
    #
    # `.zenodo.json` now names the concept to extend. The latest version under it is
    # asked for by the API rather than stored, so the chain has one declared anchor and
    # one derived head — storing the head would go stale at every release.
    concept = zj_early.get("concept_recid")
    if concept:
        # `/records/{concept}/versions` DOES NOT EXIST in this API and returned 404 on
        # the first release that used it. A search on `conceptrecid` does, and returns
        # the versions newest first — verified against the public API before use, since
        # a wrong endpoint here fails after the upload rather than before it.
        versions = call(
            "GET",
            f"{BASE}/records?q=conceptrecid:{concept}"
            "&all_versions=true&sort=-version&size=1",
        )
        hits = versions.get("hits", {}).get("hits", [])
        if not hits:
            raise SystemExit(
                f"concept {concept} has no versions. Either the recid in .zenodo.json is "
                "wrong, or the record was removed; a new deposition here would silently "
                "start a third lineage, which is the fault this exists to prevent."
            )
        latest = hits[0]["id"]
        dep = call("POST", f"{BASE}/deposit/depositions/{latest}/actions/newversion")
        # The action answers with the OLD deposition and a link to the new draft.
        dep = call("GET", dep["links"]["latest_draft"])
        print(f"deposition {dep['id']} created as a new version of {latest} "
              f"(concept {concept})")
        # A new version inherits the previous version's files. They are the previous
        # edition's data and must not be republished as this one's.
        for f in call("GET", f"{BASE}/deposit/depositions/{dep['id']}/files"):
            call("DELETE", f"{BASE}/deposit/depositions/{dep['id']}/files/{f['id']}")
            print(f"  cleared inherited {f['filename']}")
    else:
        dep = call("POST", f"{BASE}/deposit/depositions", data={})
        print(f"deposition {dep['id']} created as a NEW CONCEPT — .zenodo.json names "
              "no concept_recid, so this starts its own lineage")
    dep_id = dep["id"]
    bucket = dep["links"]["bucket"]

    for path in assets:
        size = path.stat().st_size
        print(f"  uploading {path.name} ({size / 1e6:,.1f} MB)")
        with path.open("rb") as fh:
            call("PUT", f"{bucket}/{path.name}", raw=fh.read(),
                 headers={"Content-Type": "application/octet-stream"})

    # AUTHORSHIP COMES FROM `.zenodo.json`, WHICH IS WHY THIS DEPOSIT FAILED ONCE.
    #
    # Zenodo requires `metadata.creators` and refuses to publish without it. The first
    # attempt uploaded all 523 MB successfully and then returned HTTP 400 on the publish
    # call — so the failure looked like a transfer problem and was a metadata one, and
    # every file was already sitting in a draft that could never be published.
    #
    # `.zenodo.json` is Zenodo's own standard file, so authorship is edited in an obvious
    # place rather than inside this script; the fields below that describe THIS BUILD
    # (title, version, description, notes) stay here, because they are generated.
    zj = json.loads((ROOT / ".zenodo.json").read_text())
    if not zj.get("creators"):
        raise SystemExit(
            ".zenodo.json declares no creators. Zenodo will accept every file and then "
            "refuse to publish, which is the most expensive way to discover it."
        )

    # Zenodo wants the bare identifier; `.zenodo.json` holds the full resolver URL
    # because CITATION.cff needs that form. Derived here, so neither file guesses.
    creators = []
    for c in zj["creators"]:
        c = dict(c)
        if c.get("orcid"):
            c["orcid"] = c["orcid"].rstrip("/").rsplit("/", 1)[-1]
        creators.append(c)

    meta = {
        "metadata": {
            "creators": creators,
            "title": f"REWT {TAG} — Rivers of England and Wales, Temporally (Stage 1)",
            "upload_type": zj.get("upload_type", "dataset"),
            "description": BODY.replace("\n", "<br>") or "See the repository.",
            "version": TAG,
            "license": zj.get("license", "cc-by-4.0"),
            "keywords": zj.get("keywords", []),
            "notes": (
                "Stage 1 makes no historical claim. Nothing derived from the sea "
                "network may be presented as a route a vessel could follow: the "
                "bathymetry carries DO NOT USE FOR NAVIGATION, which is a constraint "
                "on purpose rather than on redistribution."
            ),
        }
    }
    call("PUT", f"{BASE}/deposit/depositions/{dep_id}", data=meta)

    published = call("POST", f"{BASE}/deposit/depositions/{dep_id}/actions/publish")

    # Verify against Zenodo's own reply rather than assuming the calls took.
    files = published.get("files", [])
    if not files:
        raise SystemExit(
            f"deposition {dep_id} published with NO FILES. It has a DOI and it is "
            "empty, which is worse than not having been archived at all."
        )
    print(f"published: {published.get('doi_url') or published.get('doi')}")
    print(f"  {len(files)} file(s):")
    for f in files:
        print(f"    {f.get('filename')}  {f.get('filesize', 0) / 1e6:,.1f} MB")
    concept = published.get("conceptdoi")
    if concept:
        print(f"  concept DOI (always newest): {concept}")
        print("  cite the VERSION doi above for a result computed from this edition")


if __name__ == "__main__":
    sys.exit(main())
