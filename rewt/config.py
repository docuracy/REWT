"""The source registry and the parameter file.

Two rules from AGENTS.md, both enforced here rather than by care:

* **Every input is declared in `conf/sources.yml`. No URL is ever hard-coded.**
  Asking for a source that is not declared raises; it does not warn.
* **Thresholds and parameters live in configuration too.** `params()` is the only
  way to read one, so a literal in a function is visible as a literal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from . import paths


class UnregisteredSource(KeyError):
    """Asked for a source that conf/sources.yml does not declare."""


class UnlicensedSource(RuntimeError):
    """A source whose licence does not permit what is being asked of it."""


@dataclass(frozen=True)
class Source:
    """One declared input, with its licence and the attribution it requires."""

    id: str
    title: str
    publisher: str
    licence: str
    attribution: str
    access: str
    redistribution: str
    cache_path: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    # -- licence gates -----------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self.access == "open"

    @property
    def is_redistributable(self) -> bool:
        return self.redistribution == "permitted"

    def require_redistributable(self) -> None:
        """The exporter's gate. Keep it; do not work around it (AGENTS.md)."""
        if not (self.is_open and self.is_redistributable):
            raise UnlicensedSource(
                f"source '{self.id}' is access={self.access!r} "
                f"redistribution={self.redistribution!r} and may not be exported. "
                "conf/sources.yml is the authority."
            )

    # -- acquisition -------------------------------------------------------
    @property
    def dir(self):
        return paths.ROOT / self.cache_path

    def get(self, *keys: str, default: Any = None) -> Any:
        """Read a nested key out of the declaration, e.g. src.get('wcs', 'base')."""
        node: Any = self.raw
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def require(self, *keys: str) -> Any:
        value = self.get(*keys)
        if value is None:
            raise UnregisteredSource(
                f"source '{self.id}' declares no {'.'.join(keys)} in conf/sources.yml"
            )
        return value


class Sources:
    """The registry. There is exactly one, and it is read from the file."""

    def __init__(self, doc: dict[str, Any]):
        self._doc = doc
        self._by_id: dict[str, Source] = {}
        for entry in doc.get("sources", []):
            missing = [
                k
                for k in (
                    "id",
                    "title",
                    "publisher",
                    "licence",
                    "attribution",
                    "access",
                    "redistribution",
                    "cache_path",
                )
                if k not in entry
            ]
            if missing:
                raise ValueError(
                    f"source {entry.get('id', '<no id>')!r} in conf/sources.yml is "
                    f"missing required field(s): {', '.join(missing)}. "
                    "A source without a licence and an attribution is not declared."
                )
            src = Source(
                id=entry["id"],
                title=entry["title"],
                publisher=entry["publisher"],
                licence=entry["licence"],
                attribution=" ".join(str(entry["attribution"]).split()),
                access=entry["access"],
                redistribution=entry["redistribution"],
                cache_path=entry["cache_path"],
                raw=entry,
            )
            if src.id in self._by_id:
                raise ValueError(f"duplicate source id {src.id!r} in conf/sources.yml")
            self._by_id[src.id] = src

    def __getitem__(self, source_id: str) -> Source:
        try:
            return self._by_id[source_id]
        except KeyError:
            raise UnregisteredSource(
                f"'{source_id}' is not declared in conf/sources.yml. "
                "An unregistered source is an error, not a warning (PLAN.md §2). "
                f"Declared: {', '.join(sorted(self._by_id))}"
            ) from None

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._by_id

    def __iter__(self):
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    @property
    def ids(self) -> list[str]:
        return sorted(self._by_id)

    def attribution_block(self) -> str:
        """Every source's required statement, in full.

        Provenance travels as a pointer: a short attribution may never attribute less
        than this does (AGENTS.md).
        """
        lines = []
        for src in sorted(self._by_id.values(), key=lambda s: s.id):
            lines.append(f"{src.title} ({src.publisher})")
            lines.append(f"    licence:     {src.licence}")
            lines.append(f"    attribution: {src.attribution}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


_MISSING = object()


class Params:
    """Nested parameter lookup, by dotted path, with no silent defaults."""

    def __init__(self, doc: dict[str, Any]):
        self._doc = doc

    def __call__(self, path: str, default: Any = _MISSING) -> Any:
        node: Any = self._doc
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                if default is not _MISSING:
                    return default
                raise KeyError(
                    f"conf/params.yml declares no {path!r}. "
                    "Thresholds live in configuration, not in a function (AGENTS.md)."
                )
            node = node[part]
        return node

    def section(self, path: str) -> dict[str, Any]:
        value = self(path)
        if not isinstance(value, dict):
            raise KeyError(f"conf/params.yml {path!r} is not a section")
        return value

    @property
    def doc(self) -> dict[str, Any]:
        return self._doc


@lru_cache(maxsize=1)
def sources() -> Sources:
    paths.check_root()
    with paths.SOURCES_YML.open(encoding="utf-8") as fh:
        return Sources(yaml.safe_load(fh))


@lru_cache(maxsize=1)
def params() -> Params:
    paths.check_root()
    with paths.PARAMS_YML.open(encoding="utf-8") as fh:
        return Params(yaml.safe_load(fh))


def source(source_id: str) -> Source:
    """The only way to reach a source. Unregistered is an error."""
    return sources()[source_id]


def param(path: str, default: Any = _MISSING) -> Any:
    """Shorthand for a single parameter, e.g. param('topology.coincidence_tolerance_m')."""
    if default is _MISSING:
        return params()(path)
    return params()(path, default)


def config_fingerprint() -> str:
    """A digest of the configuration that produced an artefact.

    PLAN.md §2: no cached intermediate is ever preferred to the configuration that
    produced it without a recorded fingerprint of that configuration. A corrected
    setting once sat unused for a month behind a cached raster and nothing said so.
    """
    payload = json.dumps(
        {"sources": sources()._doc, "params": params().doc},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fingerprint_of(obj: Any) -> str:
    """A digest of any JSON-able subset of the configuration."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
