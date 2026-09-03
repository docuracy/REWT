"""Repository-relative paths.

Everything runs from the repository root (AGENTS.md). This module is the one place
that says where things live, and it refuses to guess: if the root does not look like
this repository, that is an error rather than a silently wrong path.
"""

from __future__ import annotations

from pathlib import Path

# rewt/paths.py -> rewt/ -> repository root
ROOT = Path(__file__).resolve().parent.parent

CONF = ROOT / "conf"
SOURCES_YML = CONF / "sources.yml"
PARAMS_YML = CONF / "params.yml"
# The canonical rule list (R-00). rules/ is the raw intake; this is the list.
RULES_YML = CONF / "rules.yml"

DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
CURATED = DATA / "curated"

DB_DIR = ROOT / "db"
DB_PATH = DB_DIR / "rewt.ddb"

PUBLISHED = ROOT / "published"

# Raw acquisitions record what they are next to what they hold.
ACQUISITION_LOG = RAW / "acquisitions.json"


def check_root() -> None:
    """Fail loudly if we are not where the relative paths assume we are."""
    if not SOURCES_YML.exists():
        raise SystemExit(
            f"conf/sources.yml not found under {ROOT}. "
            "Run every command from the repository root (AGENTS.md)."
        )


def ensure_dirs() -> None:
    for d in (RAW, INTERIM, CURATED, DB_DIR, PUBLISHED):
        d.mkdir(parents=True, exist_ok=True)


def rel(path: Path | str) -> str:
    """A path as written in reports: relative to the root where it is under it."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)
