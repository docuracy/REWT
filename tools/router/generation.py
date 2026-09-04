"""One generation id per pipeline run, stamped into every artefact.

Two artefacts, each consistent with itself, never compared with each other — rewt-e8 has
recorded that shape three times, and rewt-68 hit it here: for about a minute mid-run,
`reach_summary.json` carried the blind-sailing pair while the sightline layer still
described the sighted pair. Each file was honest about itself. A generator reading both
would have projected a contradiction with nothing to warn it, because nothing compared
them and nothing could.

A mixed read is not detectable from the contents. It is detectable from a stamp:
`generation()` returns the same value for every artefact written by one run, taken from
the environment when the runner sets it and from the clock otherwise. A consumer that
reads two files and finds two generations knows it caught the surface mid-stride.
"""
from __future__ import annotations

import datetime as _dt
import os


def generation() -> str:
    g = os.environ.get("REWT_ROUTER_GENERATION")
    if g:
        return g
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
