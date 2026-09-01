"""Three checks on the tracer's identifiers. Exit non-zero on any failure.

    python tools/tracer/check_ids.py

Intended to be invoked from the test suite (`tests/` is rewt-6a's), so the guarantee is
enforced by something that runs rather than by a sentence somebody remembers. D-051 found
`ids.py`'s one-module rule broken twice precisely because it was the second kind.

1. FRESHNESS  — the committed `ids.js` matches a fresh generation from `rewt/ids.py`.
2. PARITY     — the JS and the Python return byte-identical strings for the same inputs.
                Generation should make this impossible to fail; it is kept because it
                catches the case generation cannot: **the generator itself being wrong.**
3. SHAPE      — no module but `ids.js` composes an `os:` or `rewt:` identifier.
                Deliberately crude, and that is the point: it catches the SHAPE of the
                mistake without understanding the code. Reading has now failed to find
                three instances — two in `rewt/`, and `anno.js`, which does not own its
                scheme at all and looks *more* disciplined than it is. Reading is worst at
                absences.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rewt import ids as py  # noqa: E402

JS_DIR = ROOT / "docs/trace/js"
IDS_JS = JS_DIR / "ids.js"

# Adversarial as well as ordinary: a publisher id is an opaque string and this project
# does not get to assume it is tidy.
CASES = [
    ("link", "1234567890"),
    ("node", "id-with-hyphen"),
    ("link", "id/with/slashes"),
    ("link", "id:with:colons"),
    ("basin", ""),
    ("link", "Ünïcøde"),
    ("link", "trailing "),
]


def fail(msg: str) -> None:
    print(f"FAIL  {msg}", file=sys.stderr)


def check_fresh() -> bool:
    r = subprocess.run([sys.executable, "tools/tracer/gen_ids.py", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        fail(r.stderr.strip() or "ids.js is stale")
    return r.returncode == 0


def check_parity() -> bool:
    script = f"""
      import {{ publisher, isPublisher, isOurs, publisherIdOf, PREFIX }} from '{IDS_JS.as_posix()}';
      const cases = {json.dumps(CASES)};
      console.log(JSON.stringify({{
        prefix: PREFIX,
        publisher: cases.map(([k, i]) => publisher(k, i)),
        isPublisher: cases.map(([k, i]) => isPublisher(publisher(k, i))),
        isOurs: cases.map(([k, i]) => isOurs(publisher(k, i))),
        publisherIdOf: cases.map(([k, i]) => publisherIdOf(publisher(k, i))),
        oursIsOurs: isOurs(PREFIX + ':basin/abc'),
        oursIdOf: publisherIdOf(PREFIX + ':basin/abc'),
      }}));
    """
    r = subprocess.run(["node", "--input-type=module", "-e", script],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        fail("node could not evaluate ids.js: " + r.stderr.strip()[:400])
        return False
    js = json.loads(r.stdout)

    ok = True
    if js["prefix"] != py.PREFIX:
        fail(f"PREFIX: js {js['prefix']!r} vs py {py.PREFIX!r}"); ok = False
    for i, (kind, pid) in enumerate(CASES):
        expected = py.publisher(kind, pid)
        if js["publisher"][i] != expected:
            fail(f"publisher({kind!r}, {pid!r}): js {js['publisher'][i]!r} vs py {expected!r}"); ok = False
        if js["isPublisher"][i] != py.is_publisher(expected):
            fail(f"is_publisher disagrees on {expected!r}"); ok = False
        if js["isOurs"][i] != py.is_ours(expected):
            fail(f"is_ours disagrees on {expected!r}"); ok = False
        if js["publisherIdOf"][i] != py.publisher_id_of(expected):
            fail(f"publisher_id_of({expected!r}): js {js['publisherIdOf'][i]!r} "
                 f"vs py {py.publisher_id_of(expected)!r}"); ok = False
    ours = f"{py.PREFIX}:basin/abc"
    if js["oursIsOurs"] is not py.is_ours(ours):
        fail("is_ours disagrees on one of ours"); ok = False
    if js["oursIdOf"] != py.publisher_id_of(ours):
        fail("publisher_id_of should be null for one of ours"); ok = False
    return ok


# An identifier composed anywhere but the owning module. A literal `os:` or `rewt:`
# followed by a word and a separator is the shape; a comment or a URL is not.
COMPOSED = re.compile(r"""(['"`])(os|rewt):[a-z-]*[:/]""", re.I)


def check_shape() -> bool:
    ok = True
    for path in sorted(JS_DIR.glob("*.js")):
        if path.name == "ids.js":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith(("*", "//", "/*")):
                continue                      # a comment may discuss the scheme
            if COMPOSED.search(line):
                fail(f"{path.relative_to(ROOT)}:{n} composes an identifier outside ids.js: "
                     f"{line.strip()[:90]}")
                ok = False
    return ok


def main() -> int:
    results = {"freshness": check_fresh(), "parity": check_parity(), "shape": check_shape()}
    for name, passed in results.items():
        print(f"{'ok  ' if passed else 'FAIL'}  {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
