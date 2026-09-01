"""The identifier scheme, designed once, here (PLAN.md §10).

Later stages add courses and epochs, and **a stretch present in two published editions
must carry the same id in both**. That rules out anything derived from iteration order
or from a row number. Two rules, and nothing else:

* A feature that came from a publisher keeps the publisher's identity, prefixed so a
  reader can see whose it is: ``os:<publisher id>``.
* A feature this project created is identified by **what it is**, not when it was
  made: a digest of its own defining geometry, rounded to the millimetre. Rebuild the
  database and a connector between the same two places gets the same id again.

The second rule is also why a connector is defined by its geometry and not by a link
id (§5): the geometry is the stable thing, and resolving it onto the network is the
build's job every time.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Sequence

PREFIX = "rewt"
_PLACE_DP = 3          # millimetre; far below the survey's own precision

# ONE COLON, THEN SLASHES. `rewt` is a registered w3id prefix bound to
# https://w3id.org/rewt/, and a CURIE expands by plain CONCATENATION of namespace and
# reference. So `rewt:basin/4385554389` expands to https://w3id.org/rewt/basin/4385554389,
# which is the URI w3id actually routes, while `rewt:basin:4385554389` would expand to
# https://w3id.org/rewt/basin:4385554389 — a legal URI that resolves to nothing.
#
# The failure would be silent and total. The moment this data is serialised as JSON-LD —
# which D-027 already points at, LPF `when` objects being JSON-LD — a context binding the
# prefix expands every identifier by concatenation, produces the wrong form, and reports
# no error. Nothing in the pipeline would notice and every URI would be wrong at once.
# Found by rewt-86 on the day the namespace went live, which is the only window in which
# changing it is free (§10).


def _digest(kind: str, payload: str, length: int = 12) -> str:
    h = hashlib.sha256(f"{kind}|{payload}".encode("utf-8")).hexdigest()[:length]
    return f"{PREFIX}:{kind}/{h}"


def publisher(kind: str, publisher_id: str) -> str:
    """``os:link/...`` — a feature that is the publisher's, and says so."""
    return f"os:{kind}/{publisher_id}"


def _round(value: float) -> str:
    return f"{round(float(value), _PLACE_DP):.{_PLACE_DP}f}"


def point(easting: float, northing: float, kind: str = "node") -> str:
    """A node created by this project, identified by where it is."""
    return _digest(kind, f"{_round(easting)},{_round(northing)}")


def line(coords: Sequence[Sequence[float]], kind: str = "link") -> str:
    """A line created by this project, identified by the line itself.

    Direction-independent: the same geometry digitised either way is the same feature,
    because a reversal moves no geometry (§5).
    """
    fwd = ";".join(f"{_round(x)},{_round(y)}" for x, y in coords)
    rev = ";".join(f"{_round(x)},{_round(y)}" for x, y in reversed(list(coords)))
    return _digest(kind, min(fwd, rev))


def derived(parent_id: str, kind: str, discriminator: str) -> str:
    """A child of an existing feature — one side of a link cut at a junction.

    The discriminator is the child's own geometry, so the pair does not depend on
    which side was processed first.
    """
    return _digest(kind, f"{parent_id}|{discriminator}")


def correction(kind: str, subject: str, detail: str = "") -> str:
    """A curated judgement, identified by what it acts on and what it does."""
    return _digest(f"correction-{kind}", f"{subject}|{detail}", length=10)


def basin(outlet_node_id: str) -> str:
    """A basin is identified by its outlet, which is the thing that defines it."""
    return _digest("basin", outlet_node_id, length=10)


def basin_unanchored(raster_id) -> str:
    """A basin whose outlet node could not be found (D-013).

    Keyed on the raster id, and prefixed so nobody mistakes it for something stable
    across a re-delineation. It lived as an f-string in `basins.py` until the
    identifier scheme moved to slashes and left it behind, still emitting
    ``rewt:basin-unanchored:1002`` — which expands to
    ``https://w3id.org/rewt/basin-unanchored:1002``, a legal URI that resolves to
    nothing. **An identifier minted outside this module does not get the module's
    corrections**, which is the whole reason for the module.
    """
    return f"{PREFIX}:basin-unanchored/{raster_id}"


def is_publisher(identifier: str) -> bool:
    return identifier.startswith("os:")


def is_ours(identifier: str) -> bool:
    return identifier.startswith(f"{PREFIX}:")


def publisher_id_of(identifier: str) -> str | None:
    """The publisher's own id back out of ours, or None if we made the feature."""
    if not is_publisher(identifier):
        return None
    return identifier.split("/", 1)[1] if "/" in identifier else None
