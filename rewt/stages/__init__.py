"""The stages of the build, each declaring what it reads and what it writes.

Importing this package registers every stage with `rewt.pipeline.PIPELINE`, which is
what enforces the order. Nothing here decides the order by hand.
"""

from __future__ import annotations

from . import (  # noqa: F401  (imported to register)
    acquire_stage,
    load,
    census,
    high_water,
    terrain,
    basins,
    structures,
    water,
    curated_stage,
    repair,
    screen,
    flags,
    crawl,
    sea,
    sea_reach,
    audit,
    export,
    check,
)
