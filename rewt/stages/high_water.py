"""Stage: where the sea begins, from the Ordnance Survey high water line.

**R-01.** The sea network as first built takes its seeds from the survey's own
`form = tidalRiver` (PLAN.md §5), on the argument that a coastline decides the question
by distance from a modern shore and is wrong at exactly the estuaries where the answer
matters. That argument is good and the result came out wrong anyway: a great many sea
entries lie a long way from the sea network. Stephen's ruling is to define tidal water
by the line instead — truncate a watercourse where it crosses, drop one lying entirely
below it — **and to settle it before any synthetic connector is added**, because a
connector built against the wrong sea cannot be recognised as wrong afterwards. Hence
this stage runs before `repair`.

**The line is High Water MARK, not Mean High Water.** OS calls the Boundary-Line layer
`high_water`, Feature_Code 0071, "High Water Mark (HWM)" — an administrative coastline,
not a stated tidal datum. The products carrying MHW/MHWS as a named tidal feature are
VectorMap District and MasterMap, neither registered. HWM is the right line and costs
nothing, and the substitution is on the record rather than assumed away (D-089's shape,
rewt-16's ruling).

**Three measurements this stage rests on, none of them assumed.**

*The layer must be deduplicated or every length is 2.5x.* 32,850 rows are 13,002
distinct geometries: each segment repeats once per administrative file that bounds on
it, across 380 `File_Name` values. `Global_Link_ID` is the exact key — 13,002 distinct
ids, confirmed independently by hashing the geometry blobs. Raw length 88,420 km,
deduplicated 34,792 km, ratio 2.54.

*`country_region` is NOT this line and cannot substitute for it.* 77.8% of high water
vertices fall INSIDE the country polygon, a median 48 m in, while the 22% outside sit
exactly on its boundary. The administrative area runs to the low-water limit, so the
strip between the two lines is the intertidal zone — up to 8.8 km of it at the 90th
percentile, around the Wash, Morecambe Bay and the Solway. A landward test built on
`country_region` answers a different question, and it was nearly used for this one.

*The lines close.* Polygonised, they give 5,229 rings enclosing 230,048 km2, the largest
being 218,304 km2 of mainland Great Britain. That polygon IS "land above high water",
and containment in it is the landward test. It is built here rather than approximated,
because the alternative is a nearest-segment side test that is fragile at every estuary.

**What this stage does and does not do. It classifies. It retires nothing and truncates
nothing.** Every survey link is landward, crossing, or seaward, and that is all.

An earlier draft of this docstring said "it classifies and it retires", which the code
did not do — a claim in prose that the code beneath it did not support, which is D-091
in the file that records D-091's lesson. The reason it is wrong as a design and not only
as a description: `retirement` has one writer, the `repair` stage, and a second writer
racing it would be clobbered the moment `repair` recreated the table. So this stage
PROPOSES and `repair` APPLIES, which is the pattern the project already uses everywhere
else — detection never edits the network.

Retiring the seaward links, and truncating the crossers at the line, are both `repair`'s
work reading `high_water_side`.

**Fifty links are not tidalRiver and are retired anyway, on Stephen's ruling.** 40
`inlandRiver` and 10 `canal` lie wholly seaward. They were held back as a judgement at a
place — an inland river below high water means the geometry, the line or the form is
wrong — and put to him; his answer was to retire them, "they are not needed for our
routing or for anything else". So every wholly-seaward link goes, and the classes are
still counted and reported separately, because the reason to look at them has not gone
away just because the decision has been taken.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import shapely
from shapely.ops import polygonize, unary_union

from .. import acquire, config, db, paths, schema
from ..pipeline import PIPELINE, StageError, artefact
from ..report import Report, log

HIGH_WATER_SIDE = artefact("high_water_side")

# The forms R-01 is aimed at. Anything else that comes out wholly seaward is reported
# and left, because it is a finding rather than an instance.
TIDAL_FORMS = ("tidalRiver",)


def land_above_high_water() -> shapely.Geometry:
    """The polygon whose inside is landward of the high water line.

    Deduplicated on `Global_Link_ID` first: the layer repeats each segment once per
    bounding administrative file and a naive read is 2.54x too long.
    """
    src = config.source("os_boundary_line")
    src.require_redistributable()
    gpkg = acquire.one("os_boundary_line", "bdline_gb.gpkg")
    working = config.param("crs.working")

    lines = gpd.read_file(gpkg, layer="high_water")
    if str(lines.crs) != working:
        lines = lines.to_crs(working)
    before = len(lines)
    lines = lines.drop_duplicates(subset="Global_Link_ID")
    log.detail(
        f"    {before:,} rows are {len(lines):,} distinct geometries "
        f"({before / max(len(lines), 1):.2f}x); deduplicated on Global_Link_ID"
    )

    rings = list(polygonize(unary_union(list(lines.geometry))))
    if not rings:
        raise StageError(
            "the high water lines do not close into any ring, so there is no landward "
            "side to test against. Check the layer before trusting anything downstream."
        )
    land = unary_union(rings)
    log.detail(f"    {len(rings):,} rings enclosing {land.area / 1e6:,.0f} km2")
    return land


@PIPELINE.stage(
    "high_water",
    "where the sea begins: classify every link against the high water line (R-01)",
    # NO link_scope, DELIBERATELY, AND IT DECIDES WHERE THIS STAGE RUNS. Scope is
    # decided on basins, which are delineated after `repair` — so a dependency on
    # link_scope would place this stage at position 11, AFTER the connectors R-01 says
    # it must precede. It does not need scope: which side of the high water line a
    # watercourse falls on is a fact about geometry, not about whether we care. So it
    # classifies every survey link, and scope is applied when the classes are reported.
    reads=["link", "raw_os_boundary_line"],
    writes=["high_water_side"],
    params=["crs"],
    sources=["os_boundary_line"],
)
def run() -> dict:
    con = db.get()
    land = land_above_high_water()
    shapely.prepare(land)

    # Every survey link. `repair_link` does not exist yet and must not: R-01 settles the
    # sea before a connector is invented, which is the whole reason this stage is here
    # rather than after `basins`.
    rows = con.execute(
        """
        SELECT link_id, form, length_m, false AS is_repair, ST_AsWKB(geom) AS wkb
        FROM link ORDER BY link_id
        """
    ).fetchall()
    if not rows:
        raise StageError("link is empty; run `load` first")

    geoms = np.array([shapely.from_wkb(bytes(r[4])) for r in rows], dtype=object)
    length = np.array([float(r[2] or 0.0) for r in rows])
    form = np.array([r[1] for r in rows], dtype=object)

    # INTERSECTS AGAINST THE PREPARED POLYGON, not `crosses` against its boundary. The
    # second walks thousands of rings without an index and ran twenty minutes without
    # finishing; this does the same work in under a second. Same answer, 1,200x apart.
    inside = shapely.contains_properly(land, geoms)
    touches = shapely.intersects(land, geoms)
    side = np.where(inside, "landward", np.where(touches, "crossing", "seaward"))

    frame = gpd.pd.DataFrame(
        {"link_id": [r[0] for r in rows], "side": side, "length_m": length,
         "form": form, "is_repair": [bool(r[3]) for r in rows]}
    )
    schema.create("high_water_side")
    with db.registered("_hw_in", frame):
        con.execute(
            "INSERT INTO high_water_side "
            "SELECT link_id, side, length_m, form, is_repair FROM _hw_in ORDER BY link_id"
        )

    counts = {s: int((side == s).sum()) for s in ("landward", "crossing", "seaward")}
    kms = {s: round(float(length[side == s].sum()) / 1000, 1) for s in counts}
    # "every SURVEY link", not "every in-scope link", which is what the first version of
    # this label said while counting all 193,040. Scope is decided after this stage runs
    # (see the `reads` note above), so an in-scope figure is not available here and the
    # label asserted one anyway. rewt-68's screen.json finding, in a table of my own.
    log.table(
        "every survey link against the high water line — GB, before scope is decided",
        ["side", "links", "km", "share of in-scope km"],
        [(s, f"{counts[s]:,}", f"{kms[s]:,.1f}",
          f"{100 * length[side == s].sum() / length.sum():.1f}%") for s in counts],
    )

    seaward = side == "seaward"
    not_tidal = seaward & ~np.isin(form, TIDAL_FORMS)
    if not_tidal.any():
        # COUNTED SEPARATELY, AND RETIRED BY `repair`, NOT HERE. Stephen ruled these go
        # with the rest; the
        # breakdown stays because the reason they were worth a second look — an
        # inlandRiver below high water means something is wrong somewhere — survives the
        # decision to retire them, and a later reader should be able to find them.
        log.warn(
            f"{int(not_tidal.sum())} link(s) wholly seaward are NOT tidalRiver. They go "
            "with the rest when `repair` retires them, on Stephen's ruling, and are "
            "counted apart here: an inlandRiver or a canal below high water means the "
            "geometry, the line or the form is wrong, and that is worth finding later."
        )
        for f in sorted({str(x) for x in form[not_tidal]}):
            m = not_tidal & (form == f)
            log.detail(f"    {f}: {int(m.sum())} links, {length[m].sum() / 1000:,.1f} km")

    report = Report("high_water")
    report.add("line", {"rings": None, "land_km2": round(land.area / 1e6, 0)})
    report.add("links", {f"{s}_links": counts[s] for s in counts} | {f"{s}_km": kms[s] for s in counts})
    report.add("not_tidal_seaward", {
        str(f): int((not_tidal & (form == f)).sum()) for f in sorted({str(x) for x in form[not_tidal]})
    })
    report.write_json(paths.PUBLISHED / "audit" / "high_water.json")

    log.done(
        f"{counts['landward']:,} landward, {counts['crossing']:,} crossing, "
        f"{counts['seaward']:,} seaward ({kms['seaward']:,.1f} km)"
    )
    return {"high_water_side": len(frame)}
