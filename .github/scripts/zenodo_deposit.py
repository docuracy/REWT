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
    assets = sorted(pathlib.Path("assets").iterdir())
    if not assets:
        raise SystemExit("no assets to deposit")

    dep = call("POST", f"{BASE}/deposit/depositions", data={})
    dep_id = dep["id"]
    bucket = dep["links"]["bucket"]
    print(f"deposition {dep_id} created")

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

    meta = {
        "metadata": {
            "creators": zj["creators"],
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
