"""Reporting: at the place, not only in the total.

AGENTS.md asks for three things of every finding, and they are all here so that no
stage has to remember them:

* **Emit a coordinate with every finding.** Every serious defect in the predecessor
  was invisible in national figures — 481 km of new holes once arrived alongside a
  network that had grown in both count and length.
* **Report per basin as well as nationally.** A national 97% hides a basin at 40%,
  and the basin at 40% is the entire finding.
* **Fail loudly.** Skips are named, by identifier.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from rich.console import Console
from rich.table import Table

_console = Console(stderr=True, highlight=False, soft_wrap=False)


class _Log:
    """Thin wrapper so every stage speaks in the same voice."""

    quiet = False

    def _emit(self, markup: str) -> None:
        if not self.quiet:
            _console.print(markup)

    def rule(self, text: str) -> None:
        if not self.quiet:
            _console.rule(f"[bold]{text}", align="left")

    def info(self, text: str) -> None:
        self._emit(text)

    def detail(self, text: str) -> None:
        self._emit(f"[dim]{text}[/dim]")

    def done(self, text: str) -> None:
        self._emit(f"[green]done[/green]  {text}")

    def skip(self, text: str) -> None:
        self._emit(f"[dim]skip[/dim]  {text}")

    def warn(self, text: str) -> None:
        self._emit(f"[yellow]warn[/yellow]  {text}")

    def error(self, text: str) -> None:
        self._emit(f"[red]error[/red] {text}")

    def finding(self, text: str, easting: float | None, northing: float | None) -> None:
        """A finding always carries a place."""
        where = f"  [{easting:.0f}, {northing:.0f}]" if easting is not None else ""
        self._emit(f"  {text}{where}")

    def table(self, title: str, columns: Iterable[str], rows: Iterable[Iterable[Any]]) -> None:
        if self.quiet:
            return
        t = Table(title=title, title_justify="left", header_style="bold")
        for c in columns:
            t.add_column(str(c))
        for r in rows:
            t.add_row(*[_fmt(v) for v in r])
        _console.print(t)

    def frame(self, title: str, frame, max_rows: int = 25) -> None:
        if self.quiet or frame is None or len(frame) == 0:
            if not self.quiet and (frame is None or len(frame) == 0):
                self.detail(f"{title}: nothing to report")
            return
        head = frame.head(max_rows)
        self.table(
            f"{title}  ({len(frame):,} rows"
            + (f", first {max_rows}" if len(frame) > max_rows else "")
            + ")",
            list(head.columns),
            head.itertuples(index=False, name=None),
        )


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


log = _Log()


# --------------------------------------------------------------------------
# Machine-readable findings
# --------------------------------------------------------------------------


@dataclass
class Finding:
    """One defect, with a place. Never a total without one of these behind it."""

    kind: str
    subject: str                 # the identifier it is about (node id, link id, basin)
    detail: str
    easting: float | None = None
    northing: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    basin_id: int | None = None

    def to_row(self) -> dict:
        """For a database column, where metrics must be one value."""
        d = asdict(self)
        d["metrics"] = json.dumps(d["metrics"], sort_keys=True, default=str)
        return d

    def to_json(self) -> dict:
        """For the report, where the file is already JSON.

        Encoding a dict as a string inside a JSON document makes a consumer parse it
        twice, and a map style expression cannot see into it at all — the viewer had
        to flatten it server-side. A report is not a table.
        """
        return asdict(self)


class Report:
    """An accumulating, writable report. Machine-readable and human-readable (§7)."""

    def __init__(self, name: str):
        self.name = name
        self.created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.sections: dict[str, Any] = {}
        self.findings: list[Finding] = []

    def add(self, key: str, value: Any) -> None:
        self.sections[key] = value

    def finding(self, f: Finding) -> None:
        self.findings.append(f)

    def to_dict(self) -> dict:
        """The report's CONTENT, and deliberately not when it was made.

        PLAN.md §9 asks for the same output twice from the same inputs. A build
        timestamp inside every artefact makes that impossible to demonstrate while
        telling a reader nothing they cannot get from `published/provenance.json`,
        which is where it now lives. Everything here is a function of the inputs.
        """
        return {
            "report": self.name,
            "sections": self.sections,
            "findings": [f.to_json() for f in self.findings],
        }

    def write_json(self, path: Path) -> Path:
        """Write the report, refusing to emit anything that is not JSON.

        **`allow_nan=False` is the point of this method.** Python's encoder emits a
        bare `NaN` by default and its own decoder accepts it back, so a NaN
        round-trips perfectly here and is invalid JSON everywhere else — RFC 8259 has
        no such literal, and `JSON.parse` rejects the whole document. One missing
        value then fails an entire payload in a browser while reading cleanly from
        Python, which is the worst arrangement available: the producer cannot see the
        defect and the consumer cannot use the file.

        Found by rewt-fc, whose map broke on `terminus.inflow_length_m` — NaN for the
        10,784 termini the crawl did not seed from, correct in the GeoPackage and
        fatal once it reached a JSON encoder. Nothing this project publishes carries a
        bare NaN today; that is luck rather than design, and this makes it a failure at
        write time instead of a defect discovered by whoever tries to read it.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            body = json.dumps(
                self.to_dict(), indent=2, sort_keys=True, default=str, allow_nan=False
            )
        except ValueError as exc:
            raise ValueError(
                f"{path.name}: the report holds a value JSON cannot express ({exc}). "
                "NaN and Infinity are not JSON, and a bare NaN fails the whole "
                "document for any reader that is not Python. Use None."
            ) from exc
        path.write_text(body, encoding="utf-8")
        return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def km(metres: float | None) -> float:
    return round((metres or 0.0) / 1000.0, 3)
