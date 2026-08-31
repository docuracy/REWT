"""Stage: acquire the declared national sources.

One module fetches every input, from `conf/sources.yml` and nowhere else. The two
LiDAR products are deliberately not here: they are fetched per section, never
nationally (PLAN.md §4, D-006).
"""

from __future__ import annotations

from .. import acquire, config
from ..pipeline import PIPELINE, artefact
from ..report import log

RAW_RIVERS = artefact("raw_os_open_rivers", "dir", "data/raw/os_open_rivers/extracted")
RAW_BOUNDARY = artefact("raw_os_boundary_line", "dir", "data/raw/os_boundary_line/extracted")
RAW_TERRAIN = artefact("raw_os_terrain_50", "dir", "data/raw/os_terrain50/extracted")
RAW_OPENMAP = artefact("raw_os_open_map_local", "dir", "data/raw/os_open_map_local/extracted")


@PIPELINE.stage(
    "acquire",
    "fetch the declared national sources and record their digests",
    writes=["raw_os_open_rivers", "raw_os_boundary_line", "raw_os_terrain_50"],
    sources=["os_open_rivers", "os_boundary_line", "os_terrain_50"],
)
def run() -> dict:
    detail = {}
    for source_id in ("os_open_rivers", "os_boundary_line", "os_terrain_50"):
        acq = acquire.fetch(source_id)
        detail[source_id] = {"issue": acq.issue, "sha256": acq.sha256}
        # A result that cannot name its input cannot be reproduced (§4).
        log.info(f"  {source_id}: issue {acq.issue}, {acq.members:,} files")
    return detail


@PIPELINE.stage(
    "acquire_openmap",
    "fetch OS OpenMap - Local (3.5 GB), needed only for water-body skeletons",
    writes=["raw_os_open_map_local"],
    sources=["os_open_map_local"],
)
def run_openmap() -> dict:
    src = config.source("os_open_map_local")
    log.info(f"{src.title}: this is a large download and only §5's water-body case needs it")
    acq = acquire.fetch("os_open_map_local")
    return {"issue": acq.issue, "sha256": acq.sha256}
