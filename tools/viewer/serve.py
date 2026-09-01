#!/usr/bin/env python3
"""A local preview server for docs/, with the one feature the stdlib's lacks: Range.

`python -m http.server` answers a Range request with 200 and the WHOLE file. For the
viewer that is not a slow preview but a different program: a PMTiles archive is read by
issuing byte-range requests for the tiles in view, and against a server that ignores
them the browser downloads 322 MB to draw one tile. The map then appears to work
locally and to be broken everywhere else, or the reverse, and neither tells you which.

GitHub Pages honours Range, so this makes local preview behave as the deployed site
does. It is a development tool: no caching, no compression, and it serves whatever is
under docs/ to localhost only.

**It does NOT run Jekyll**, so anything with front matter is served as its template
rather than as its output. `docs/epochs.json` is the one the viewer reaches for, and
against this server the epoch control falls back to dates without their rationales and
says so on the page. That is the fallback working, not the viewer failing — but it
means a local preview cannot confirm the epoch rationales, and only a deploy can.

    python tools/viewer/serve.py            # http://127.0.0.1:8021/viewer/
    python tools/viewer/serve.py --port N
"""

from __future__ import annotations

import argparse
import http.server
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs"
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def end_headers(self):
        # Pages sends both, and a PMTiles read needs to know Range is honoured.
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        header = self.headers.get("Range")
        if not header:
            return super().send_head()
        m = RANGE.match(header.strip())
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path):
            return super().send_head()

        size = os.path.getsize(path)
        first, last = m.group(1), m.group(2)
        if first == "":                      # bytes=-N — the final N bytes
            start, end = max(0, size - int(last)), size - 1
        else:
            start = int(first)
            end = int(last) if last else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        # SimpleHTTPRequestHandler copies to EOF, so hand it only the slice.
        return _Slice(f, end - start + 1)

    def log_message(self, fmt, *args):  # one line per request, not three
        code = args[1] if len(args) > 1 else ""
        print(f"  {code} {self.path}")


class _Slice:
    """A read-only window on an open file, so copyfile stops at the range's end."""

    def __init__(self, f, remaining: int):
        self._f, self._left = f, remaining

    def read(self, n: int = -1) -> bytes:
        if self._left <= 0:
            return b""
        n = self._left if n < 0 else min(n, self._left)
        data = self._f.read(n)
        self._left -= len(data)
        return data

    def close(self):
        self._f.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8021)
    args = ap.parse_args()
    if not (ROOT / "viewer" / "index.html").exists():
        raise SystemExit(f"{ROOT}/viewer/index.html not found — run from the repository root")
    data = ROOT / "viewer" / "data" / "rewt.pmtiles"
    print(f"docs/ from {ROOT}")
    print("tiles: " + (f"{data.stat().st_size / 1e6:,.0f} MB" if data.exists()
                       else "ABSENT — run `rewt viewer-data`"))
    print(f"http://127.0.0.1:{args.port}/viewer/   (Ctrl-C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
