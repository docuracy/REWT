# The Router — a plan

A cost surface for coastal navigation: an H3 grid over the waters of the British Isles,
banded by decreasing resolution with distance from the coast, and the links that join the
river network's tidal termini to it.

Written by rewt-c7 ("router"), 3 September 2026, from `rules/H3.md`. **This is a plan, not
an implementation.** Section 10 lists the decisions that must be taken before any of it is
built, three of which are not mine to take.

Every figure below names the file or the command it came from. A figure with no file behind
it is a rumour (D-076).

---

## 1. What this is, and what it is not

**The deliverable is a graph, not a route.** Cells, their adjacency, their depth, and the
attachment of the river network to them. Running Dijkstra over the result is a few lines and
belongs to whoever wants a journey; the hard and reusable part is the surface.

**It is Stage 1, and the argument is Stephen's in `rules/H3.md`:** the cost surface "will be
valid at all dates across our temporal window, including 2026". A hexagon in the Irish Sea
does not know what year it is. Nothing in the grid, the land/sea decision, the depths, or
the attachment of a river mouth requires a date, and so nothing here trips `CLAUDE.md`'s
rule.

**What is deferred, on Stephen's explicit instruction: the weights.** Wind, current, wave,
seasonality, daylight, vessel draught and sail geometry — everything in the predecessor's
`vesselParameters` — encode how a particular kind of ship behaved in a particular period.
They are the part that knows what year it is. The grid is built so they can be attached
later; none is computed now. **If this plan is ever found computing a weight, it has
drifted, and the right response is to stop and say so.**

**The sightline does *not* defer with them.** It was planned to, and Stephen overruled that
on 3 September 2026. §8 records the reversal and the line now drawn: the visibility geometry
is built, the penalty coefficient is not.

**It does not touch the Stage 1 build.** It reads `published/` and `data/raw/`. It never
opens `db/rewt.ddb`, which the implementer holds and which a second connection would block.
It writes only under `tools/router/` and `docs/router/`.

**It is not a chart and must never be read as one.** `conf/sources.yml` carries
`use_constraint: "DO NOT USE FOR NAVIGATION"` on the bathymetry, and that constraint travels
to everything derived from it.

---

## 2. The licence position

`AGENTS.md` is the governing text and it is blunt: the repository has been **public since 31
August 2026**, there is no window before exposure, and a licence question is settled before
the commit or it is settled in public.

**The predecessor is `CC BY-NC 4.0`.** Verified from the raw README, line 240, not from a
summary of it — a summarising tool can return a licence field it has invented. Stephen holds
the copyright and has stated he can relicense it under any terms he wishes, so the *code* is
not an obstacle. It is read for its reasoning regardless, per `AGENTS.md`, and none of it is
imported.

**The third-party data in that repository is not his to relicense, and one item of it would
have reached this design.** The predecessor cuts land from sea using **OSM coastlines**,
which are ODbL. A grid cut against them is a derived database under a share-alike term, on a
dataset intended to be open and academic-grade. This plan does not use them. §4 is the
alternative, and it is better on the merits as well as on the licence.

**Settled, 3 September 2026.** `rules/route_871973361ffffff_871874addffffff.geojson` was an
output of the CC BY-NC project, placed in the working tree to show this session what a route
looks like. Stephen's instruction was that it is not to be committed, and it has been
deleted. It was never tracked, so nothing of it survives in history. Its metadata is quoted
in this file where it is evidence; nothing else of it is retained.

**No new source is proposed.** Everything this plan needs is already registered, fetched and
checksummed. That is the single most useful finding of the day and it was not expected.

---

## 3. Inputs

| what | source id | licence | status |
|---|---|---|---|
| the GB coastline, at high water | `os_boundary_line`, layer `high_water` | OGL | on disk, 1.8 GB gpkg |
| land/sea beyond GB; all depths | `emodnet_bathymetry` | CC BY 4.0 | `verified`, 120 windows cached |
| the drying zone (§6, candidate) | `ea_lidar_composite_dtm_1m`, `nrw_lidar_dtm_1m` | OGL v3 | registered; D-085 is fetching them |
| the river termini | `published/rewt_stage1_network.gpkg` | — | build output |

**One library to add: `h3`.** Installed here as 4.5.0 on Stephen's instruction; the pin
`h3==4.5.0` belongs in `requirements.txt`, which is not mine to edit. Proposed to the
implementer.

---

## 4. Two coastlines, chosen rather than blundered into

This is the central design decision and it took a measurement to see.

**Boundary-Line is Great Britain only.** Deduped `high_water` spans lon −8.65 to +1.76, lat
49.87 to 60.86; `country_region` holds exactly England, Scotland and Wales. There are no
segments near the Republic, the Isle of Man or the Channel Islands, and none in Northern
Ireland — the four that fell inside a Northern Ireland test box are `ARGYLL_AND_BUTE`, the
Mull of Kintyre. Deduping on `Global_Link_ID` takes 32,850 rows to **13,002** geometries,
2.53×, and their total length is **34,792 km**. Both figures reproduce rewt-16's
independently.

**EMODnet covers everything else, and is already registered.** Its own notes record it as a
merged land-and-sea surface — *land POSITIVE, sea NEGATIVE* — at 1/16 arc-minute. Its
`DescribeCoverage` envelope is **lat 11°N–90°N, lon 70.5°W–43°E**: Ireland, the whole
continental seaboard, and far beyond any plausible area of interest.

Probing its land side at known summits, in a 0.12° window around each:

| site | true | read | error | nodata |
|---|---:|---:|---:|---:|
| Snowdon | 1085 m | 1057 | −2.6% | 0% |
| Cross Fell | 893 m | 891 | −0.2% | 0% |
| Carrauntoohil (IRL) | 1038 m | 1015 | −2.2% | 0% |
| Brittany | 384 m | 379 | −1.2% | 0% |
| Harz (DEU) | 1141 m | 1143 | +0.1% | 0% |

The Snowdon reading reproduces the project's own probe recorded in `conf/sources.yml`
exactly. Inland windows over Birmingham, the Irish midlands and inland France return **0%
nodata**, so the land surface is continuous well beyond any coastal buffer this work needs.
(A sixth probe, Wicklow, read 12.6% low; the coordinate I used is not the summit I named it
for, so that row is my error and is excluded rather than quietly kept.)

**But its zero is not the same zero.** `conf/sources.yml` already warns that *"a value read
across the coastline changes datum without saying so… It will matter to anyone reading a
height off it."* Reading a coastline off it is precisely that, at precisely the
discontinuity. Depths are referenced to **Lowest Astronomical Tide**, so an EMODnet-derived
coastline is a **low water** line. Boundary-Line's is a **high water** line.

**The decision: use both, deliberately, and record the seam.**

- **Boundary-Line `high_water`** defines the coast for Great Britain and for the terminus
  end of the join. R-01 makes it canonical for the river network, and the grid must not
  disagree with the network about where the land stops.
- **EMODnet's zero crossing** defines land for Ireland, the Isle of Man, the Channel
  Islands, Northern Ireland and the continent, and is the land mask for the sea grid
  everywhere.

**And LAT is the better line for a sea grid anyway.** A ship cannot cross a bank that dries.
A low water land mask makes drying ground impassable by construction, which is what a
navigational surface should do — the same argument `conf/sources.yml` makes for §10's
clearance test, that land is impassable for free.

**The two lines disagree, and the disagreement is measurable.** Classifying all 2,246 tidal
termini against both:

| | above LAT | below LAT |
|---|---:|---:|
| **landward of HWM** | 1,218 | **326** |
| **seaward of HWM** | **445** (drying ground) | 257 (open water) |

445 termini (19.8%) stand on ground that is inside the sea at high water and dry at low.
The 326 in the other off-diagonal should be near-empty if both lines were exact and
consistent — a point inside the land polygon cannot really be below the lowest tide — so
that cell is the error term, 14.5% of the population. The likely cause is EMODnet's ~115 m
pixel smearing a narrow channel into the sea class. **That is not noise to be tidied away:
it is the estuary-penetration limit of the bathymetry, showing up as a number.** §6 turns on
it.

---

## 5. The grid

### 5.1 The banding rule, which is better than banding

The predecessor does not compute distance bands and assign resolutions to them. It recurses
(`process/sea_graph.py`):

1. Cover the area of interest at the coarsest resolution that yields cells.
2. At resolution *r*, keep a cell as sea if it intersects no land **and** its centroid is
   further from the coast than `2 × edge_length(r)`.
3. Replace every other cell with its seven children at *r+1* and repeat.
4. At the finest resolution, fill the remaining littoral water entirely.

**The threshold is the cell's own size**, so the banding is emergent and self-scaling rather
than specified, and it cannot be inconsistent with the geometry it describes. The penultimate
band is widened (`× 1.5` rather than `× 2`) to soften the last step. Adopt this. It is the
part of the predecessor most worth having and the part least likely to be arrived at
independently.

The worked Newcastle–Plymouth route confirms it in the output: the outward path crosses
cells at res 3, 4, 5, 6 and 7 — 2, 11, 60, 105 and 188 of them.

### 5.2 How fine to go

`h3` 4.5.0, and the width of the finest band, which is `2 × edge(R−1)`:

| res | edge | cell area | finest band if R = this | EMODnet pixels per cell |
|---:|---:|---:|---:|---:|
| 7 | 1,406 m | 5.161 km² | 7.45 km | 623 |
| 8 | 531 m | 0.737 km² | 2.81 km | 89 |
| 9 | 201 m | 0.105 km² | 1.06 km | **12.7** |
| 10 | 76 m | 0.015 km² | 0.40 km | **1.8** |
| 11 | 29 m | 0.002 km² | 0.15 km | 0.3 |

**Refining is much cheaper than it looks, because the finest band narrows as it refines.**
Total cells in the coastal fringe, modelling each band as `coastline length × band width ÷
2` (an upper bound: it double-counts where opposite banks fall within one band, which is
exactly the estuaries):

| R | estimated fringe total | **built total** | on disk |
|---:|---:|---:|---:|
| 7 | 34,403 | **16,145** | 0.3 MB |
| 8 | 91,288 | — | — |
| 9 | **241,742** | **169,268** | **3.3 MB** |
| 10 | 639,668 | not built (§5.2) | — |

**The estimate is an upper bound and a loose one — 2.13x the built figure at R = 7 and
1.43x at R = 9.** It was labelled an upper bound when written, because the strip model
double-counts wherever opposite banks fall inside one band; what it did not say is how much
that costs, and a reader would not have guessed a factor of two. The built column is
`tools/router/cache/grid_summary.json`, measured, and supersedes it. Both are kept, and so
is the ratio: a reader who sees only the corrected figure learns nothing about the next
configuration, where a bound running 2x high is the useful thing to know.

**Both columns are totals summed over every band, not the finest band alone.** The built
grid at R = 9 is 169,268 cells in all — 8 / 84 / 608 / 2,516 / 8,410 / 33,121 / 124,521 from
res 3 to res 9 — and at R = 7 it is 16,145, of which 12,469 are the res-7 band. The two
figures sit close together and are easy to read as the same quantity; they are not.

For comparison the predecessor ships a 10.3 MB UK-Eire graph and a 71 MB Europe graph, so
none of these is a size problem. Stephen's instruction was to go finer if the estuaries
benefit *and* the size is manageable.

**The size is manageable to res 10. The benefit stops at res 9.** A res-9 cell averages 12.7
bathymetry pixels, which is a sound average; a res-10 cell averages 1.8, so the grid would
be finer than the surface it is describing and would report structure EMODnet cannot see.
The 14.5% disagreement in §4 is that limit already biting.

**So: `COASTAL_SEA_RESOLUTION = 9`, everywhere, and that is now settled.** Res 10 was held
open for estuaries pending a finer bathymetry; **Stephen closed that on 3 September 2026 —
no finer bathymetry will be registered**, so res 10 has nothing to describe and is not
built. The cells were always affordable; the depths were never earned. **Refining a grid
past its source is exactly the shape of D-077: a confident answer that was never
measured.**

### 5.3 A coverage gap arrives as exact zero, not as nodata

`tools/router/grid.py` first admitted a cell whose centre was *not land*. A nodata pixel is
not land either, so an unmeasured cell would have entered the grid as sea carrying no
measurement. That was corrected to **admit a cell only if its centre is a measured sea
pixel**, dropping and counting anything else.

**That correction relied on absence arriving as `NaN`, and it does not.** rewt-16 pressed
the point — the dataset declares no nodata value, so there is no contract that it will —
and named the precedent already in this repository: `ea_lidar_composite_dtm_1m` answers
HTTP 200 and a valid GeoTIFF of 0.00 m for Welsh ground it does not hold.

**Established against the live service rather than assumed.** Asked for windows inside
EMODnet's declared envelope but outside its coverage:

| probe | NaN | exact 0.0 | range |
|---|---:|---:|---|
| North Sea (control) | 0% | 0% | −35.3 .. −6.2 |
| Snowdonia (control) | 0% | 0% | 0.9 .. 1057.0 |
| Sahara interior | 0% | 0% | 662.5 .. 1169.9 |
| **Greenland interior, >60°N** | **0%** | **100%** | **0.0 .. 0.0** |

**A gap returns a full grid of exact zero, with no nodata and no error.** Absence rendered
as a plausible measurement *at the datum* — so `>= 0` would have classed the whole of it as
land, dropped it, and left the unmeasured counter reading zero. The guarantee would have
inverted silently: a hole in the sea that reads as a coastline.

**The separation is wide, so the guard is not finely tuned.** Genuine datum-boundary zeros
in the 120 cached windows are a thin coastal scatter — 0.092% overall, worst window 0.711%,
largest contiguous blob 4,047 pixels — against 100% for a real gap. `grid.py` therefore
refuses above 5% exact zeros, and treats any contiguous zero region above 50,000 pixels as
**no data rather than as land**.

**The guard is demonstrated to fire**, against the Greenland window as a positive control,
because a guard that has never fired is not a guard. rewt-16 reproduced the gap
independently at 72°N.

**Max-reduction makes the detector stronger exactly where the risk is.** A maximum over a
block containing anything non-zero is non-zero, so scattered datum zeros shrink under it
(101,736 to 16,548) while a solid gap survives intact. The working grid is therefore a
better gap detector than the raster it came from — a property of the reduction, not a
happy observation about this dataset.

**The 60°N question is closed, and it had to be asked.** SRTM stops at 60°N and EMODnet's
land side is partly SRTM, so ground above that latitude was a candidate for the same
failure — and this project's area of interest reaches 61.5°N. rewt-16 probed it: Ronas Hill
on Shetland at 60.53°N reads 440.5 m against a true 450 (−2.1%, and 3.2% exact zeros, which
is coastline in a coastal window and well inside the 5% refusal); Faroe at 62.30°N reads
732.2 m with 0.9% zeros. **The Greenland zeros are an absence of coverage, not a latitude
cutoff, and nothing in or near the British Isles is affected.**

**None of this changes the grid today and all of it changes the extension.** The cached
extent has no gaps, so the built grid is identical either way. The 75 further windows of
§10 item 1 reach the Atlantic margin, where EMODnet's coverage is not continuous — which is
when it would have bitten, and `conf/sources.yml` already says holes are fatal here.

### 5.4 One reduction is not three: a land mask that ate the coast

`grid.py` reduced the raster with a single `nanmax`, copied across from `sightline.py`
where a maximum is right because it preserves peaks. **For a land/sea mask it is quietly
destructive: the maximum over a block containing any land is land, so land dilates and the
sea is eroded by up to a pixel along every coast** — precisely where estuary penetration
lives. The same operation is correct for one purpose and wrong for the other, and nothing
about it looks wrong.

It was found from the outside. §6 measured the median terminus as 143 m from water existing
at the lowest tide, and §7's first run found only 220 of 2,246 termini inside a grid cell,
median 472 m from the nearest cell centre. **The inference in §6 — that at res 9 the grid
would reach most termini directly — was drawn from a measurement of the waterline and
applied to the grid, which is a different object.** That is what exposed it.

Now three independent reductions: `has_land`, `has_sea`, and `all_zero` for the gap guard.
**A block can legitimately be both land and sea — that is what a coastline is** — and the
single reduction made that unrepresentable by forcing land to win every tie.

| | before | after |
|---|---:|---:|
| res-9 cells | 124,521 | **169,861** |
| total grid | 169,268 | **214,608** |

The offshore bands are unchanged at 8 / 84 / 608 / 2,516 / 8,410 / 33,121, which is the
signature to expect: the fault was only ever at the waterline.

**And the outcome ledger caught the consequence within the hour.** Allowing a block to be
both made `keep` and `drop` overlap at the terminal resolution, and the SUM stopped
balancing — 586,347 against 541,007 tested. The check §9 added because rewt-16 found it
missing had existed for about an hour before it earned its place.

### 5.5 Area of interest

The predecessor's `UK-Eire` box is `(−11.0, 49.5, 2.0, 61.0)`. Two problems: Muckle Flugga
is at 60.85°N, so the north edge has 15 km of margin, and the cached EMODnet windows stop at
**−8.0**, holding none of Ireland's Atlantic coast — which is where `rules/H3.md` says the
optimal routes run. Proposed `(−11.5, 49.0, 2.5, 61.5)`: **195 one-degree windows against
the 120 cached, so 75 new**, about 301 MB on top of the present 481 MB. That is the
implementer's fetch and it re-pins the manifest (§10).

---

## 6. The intertidal crossing — the hard part, and smaller than feared

`rules/H3.md` identifies this: the demonstration's cells are too coarse to penetrate
estuaries, so linking rivers to the grid needs bathymetry and a path-to-centre algorithm.

**The gap is real but short.** Distance from each tidal terminus to the nearest EMODnet
pixel below LAT, over the cached windows, all 2,246 resolved with none unreached:

| | median | mean | 90th | 95th | max |
|---|---:|---:|---:|---:|---:|
| all 2,246 | 143 m | 220 m | 432 m | 624 m | 9,605 m |
| in-scope 474 | 138 m | 295 m | 558 m | 847 m | 9,605 m |

93.4% of all termini, and 89.7% in scope, are within one res-8 edge of water that exists at
the lowest tide; 99% are within a res-7 edge. **At res 9 the grid reaches most termini
directly and the "algorithm to compute paths to cell centres" is needed for a minority, not
for the population.** That inverts the shape of the problem as stated.

**The tail is the whole content.** Ten in-scope termini lie beyond 3.7 km and one at 9.6 km.
Those are the deep estuary heads, and they are the cases where a path must be traced rather
than a neighbour taken. Report them individually with coordinates, per `AGENTS.md` — *report
at the place, not only in the total*.

**The 445 termini standing on drying ground are the interesting population**, because the
ground between high and low water is neither sea for the grid nor land for the network.
Crossing it needs a surface, and **the surfaces may already be registered**:
`ea_lidar_composite_dtm_1m` and `nrw_lidar_dtm_1m` are 1 m DTMs that D-085 is already
fetching nationally, and coastal LiDAR is commonly flown at low water, so the drying banks
may be described there at 1 m where EMODnet describes them at 115 m or not at all. **This is
a candidate, not a finding.** It needs a coverage probe over a known drying bank before it
goes anywhere near a design, and the probe is cheap.

**Holes are fatal here, and more so than for a contour.** The source entry says it: an
accumulation "routes confidently through a gap and reports the track as measured". A router
does worse — it prefers the gap, because a hole costs nothing. Masking by the
`emodnet:quality_index` and `emodnet:source_references` WFS polygons is a requirement of
this construction, not a refinement, and an unmasked run must be impossible rather than
merely discouraged.

---

## 7. Joining the network to the grid

For each tidal terminus, in order, stopping at the first that succeeds:

1. **The terminus is already in a sea cell.** Attach to that cell's centre.
2. **A sea cell lies within one cell edge.** Attach to the nearest, recording the distance.
3. **Neither.** Trace a least-cost path from the terminus to the nearest sea cell centre
   across the drying zone, preferring depth, and attach along it.

**Every join carries its provenance** — which rule fired, the distance, the depth at the
attachment, and the mask verdict — because a join made by rule 3 is an inference and a join
made by rule 1 is an observation, and a reader must be able to tell them apart.

**Nothing is deleted to make a join work.** A terminus that cannot be joined is reported as
unjoined, with its coordinate, and stays in the output. `AGENTS.md`: *fail loudly*, and
*name every skip*.

### 7.1 Built

`tools/router/join.py`, against the 214,608-cell grid:

| rule | all 2,246 | in scope 474 | |
|---|---:|---:|---|
| 1 — already in a grid cell | 735 (32.7%) | 171 (36.1%) | observation |
| 2 — adjacent to a grid cell | 1,097 (48.8%) | 210 (44.3%) | short inference |
| 3 — needs a traced path | **414 (18.4%)** | **93 (19.6%)** | inference, NOT YET TRACED |

**So 81.6% attach by observation or adjacency, and the estuary problem is 414 termini** —
93 of them in scope, median 663 m, 90th percentile 1,517 m, worst 16.0 km. Every one is
named with its coordinate in `tools/router/cache/join_summary.json`; that listing answers
"is there anything else" and is never truncated.

**Rule 2 is adjacency, and H3 states it exactly — there is no distance threshold.** The
first version used "within one cell edge", which is roughly *inside* the cell, so it fired
only where rule 1 had just missed: every rule-2 distance piled up against the 201 m edge
like a wall while rule 3's median sat at 340 m. That is the shape of a mis-specified test,
not of the data. `h3.grid_disk(cell, 1)` asks the question the rule means — is the terminus
in a cell next door to the grid — and needs no tuned radius. The rule-2 distances now reach
522 m, which emerged from the tiling rather than being imposed on it.

### 7.2 Tracing the 414, and what stops the rest

`tools/router/trace.py`. Least-cost path on the EMODnet grid, 8-connected: **1 per pixel in
water whatever its depth, `1 + height in metres` on ground above the lowest tide, impassable
above 5 m.** One parameter, with a reason. Preferring deep water over shallow would be a
vessel judgement and this makes none — the same line §8 draws for the sightline.

**372 of 414 traced (89.9%); 42 fail, 12 of them in scope.**

| | |
|---|---|
| detour against the straight line | median 1.10×, 90th 1.49×, max 3.47× |
| fraction of path on drying ground | **median 0.83**, max 0.99 |
| traces staying entirely below the lowest tide | **2 of 372** |

**That middle row is the finding.** These paths are not routes through water that the grid
happened to miss; they are overwhelmingly crossings of ground that is sea at high water and
dry at low. §6 predicted the intertidal zone would be the hard part and this measures it:
the median traced path spends 83% of its length there.

**The goal was wrong before it was right, and the fix was not a tuning.** The first version
aimed at the nearest grid cell centre by straight-line distance and failed 89 times. A
minimax-path diagnostic showed 34 of those could reach open water perfectly well at the same
5 m limit — they simply could not reach *that cell*. **Aiming at a point when the
requirement is "reach the network" invents an obstacle out of the choice of target.** The
goal is now any pixel lying in a cell the grid holds, and 47 of the 89 resolved without
touching a threshold.

**The 41 that remain are a resolution limit, and the number says so.** For each, the lowest
barrier between the terminus and open water:

| percentile | 10th | 25th | 50th | 75th | 90th | max |
|---|---:|---:|---:|---:|---:|---:|
| barrier | 0.6 m | 3.0 m | **6.1 m** | 9.8 m | 17.7 m | 25.2 m |

**A tidal river is at sea level by definition, so a 6 m ridge across one is not terrain — it
is a 115 m grid bridging a channel it cannot see.** Raising `impassable_above_m` to 30 would
"reach" all 85, and would be inventing a route through ground the instrument never resolved:
D-077's shape, a confident answer that was never measured. The threshold stays at 5 m and
the 41 are reported as unreached, with coordinates.

**This is the case for the intertidal surface §6 names.** `ea_lidar_composite_dtm_1m` and
`nrw_lidar_dtm_1m` are 1 m, already registered, already being fetched nationally by D-085,
and coastal LiDAR is commonly flown at low water. A 6 m artefact barrier does not survive a
1 m surface. That remains a candidate needing a coverage probe over a known drying bank — it
is now a candidate with a measured motive.

**The set of termini is not frozen.** R-01 is unbuilt as of this writing (`conf/rules.yml`
gives it `status: proposed`; `rules/WORK-PACKAGE-01.md` opens "R-00 done; the rules
themselves not started"). It will change which watercourses have termini and will truncate
those crossing the high water line. The implementer will land it in **two** passes — retiring
wholly-seaward links first, truncating the crossers at the line second — and this population
moves under both, so it is re-derived after the second and not the first. Note that
retirement does not only remove termini: a node left with no outflow when a link retires
**becomes** one, so the set changes in both directions at once. It will **not** move them
far: the median terminus is already 48 m from `high_water` (96 m in scope) and 95% are within 500 m, well inside one
res-9 cell. So the algorithm is stable under R-01 and the population is not. Build against
today's termini; re-derive every table when R-01 lands.

---

## 8. The sightline, brought forward

**Stephen's ruling, 3 September 2026: the sightline comes forward, overruling this
section's original argument that it defers with the weights.** That argument is left
stated here because `AGENTS.md` requires a reversal to be recorded rather than made
silently: it held that the sightline enters the predecessor's model as
`invisibleLandPenalty`, a cost multiplier, and so belonged with the vessel parameters.

**What comes forward is the geometry; the coefficient stays behind.** *Which land is
visible from which sea cell, and out to what range* is a fact about elevation and the
curvature of the earth, true in 1450 and in 2026 alike. *How much a master would detour to
keep it in sight* is a behavioural claim about a period, and it sits inside the vessel
parameter set already deferred. The grid will carry visibility; the penalty attaches to it
later. If that split is not what was meant, it is one line to change and it should be
changed here.

### 8.1 The algorithm

From `process/sea_graph.py` and `process/parquet_line_of_sight.py`, and sound:

1. Retain land cells within a buffer of the coast, at a coarse resolution
   (`COASTAL_LAND_DEM_RESOLUTION = 5` in the predecessor).
2. Keep the **maximum** elevation in each such cell.
3. Compute a horizon distance for each from Earth curvature.
4. From each sea node, compare radially outward and stop at the first visible landmass
   inside the horizon radius.

Step 4 is the good idea: it gets a visibility field without ray-casting, which is what
makes the whole thing affordable.

### 8.2 One correction to the predecessor's parameters

**Its 50 km buffer truncates visibility from high ground.** Horizon range is
`sqrt(2 R k h)`, which for the refraction coefficient this work uses (`k = 1.13`,
`CONFIG["refraction_k"]`) is **`3.79 x sqrt(h)`** kilometres for `h` in metres, against
`3.57 x sqrt(h)` for pure geometry. **The constant is derived from the parameter and must
not be written independently of it:** this line first said `3.86`, which is a widely quoted
value corresponding to `k = 1.17` and did not match the code beneath it. The table below was
always computed from `k = 1.13`; only the prose was wrong, and it was rewt-16's bracketing
of a result that exposed it.

| land height | geometric | with refraction | |
|---:|---:|---:|---:|
| 50 m | 25 km | 27 km | 14 nm |
| 200 m | 51 km | 54 km | 29 nm |
| 500 m | 80 km | 85 km | 46 nm |
| 1,085 m (Snowdon) | 118 km | 125 km | 67 nm |

Snowdon is theoretically visible from 125 km offshore and Ben Nevis from further. A 50 km
buffer discards the high ground that is visible furthest, which is exactly the ground a
master steered by. **Set the buffer from the maximum land elevation in the area of
interest, not from a round number** — about 140 km for the British Isles. That is more
land cells, but they are res-5 cells (9.9 km edge) and there are few of them.

### 8.3 The DEM, and what rewt-16 established about it

The predecessor uses Mapzen Terrarium tiles, which **D-085 rejected** — no licence at
tileset level. I proposed EMODnet's land side instead, and probing it holds up: 0% nodata
inland across Britain, Ireland and the continent, and summits within ~3%.

**But my first framing of that argument was wrong and rewt-16 corrected it.** I called it
"one product, one licence, one instrument, uniform". The first two are right; the last two
are not. EMODnet's own product page describes the land coverage as a blend of **ASTER GDEM
(30 arc-second), SRTM3 (90 m), EU-DEM, and a global water body map**. That is the same kind
of object as terrarium: several DEMs of differing provenance and resolution, seamed
together.

**The argument that survives is "one licence, adequate for the purpose", and it is
sufficient.** What disqualified terrarium in D-085 was not that it was a composite — it was
that it has *no licence at tileset level*, leaving the user to research each upstream
provider. EMODnet carries one CC BY 4.0 licence over the whole product and one attribution
string, already registered and already published. That is the real difference, and stating
it as uniformity instead would have put something untrue in this file that a reader could
disprove from the publisher's own description.

**Its provenance layers do not cover land at all.** rewt-16 queried
`emodnet:source_references` and `emodnet:quality_index` at seven land points: zero features
at every one, against 10 and 4 features at a North Sea control run in the same pass. So one
cannot ask which of ASTER, SRTM3 or EU-DEM produced a given land cell. Terrarium, for all
its licence mess, answers that per tile. **On auditability EMODnet is the worse product,
and that is a known limitation of this grid rather than a thing nobody checked.**

### 8.4 Three rules that follow, each of which would otherwise be learned the hard way

**Sample the maximum over a cell, never a point.** On a ~115 m grid a point near a sharp
summit lands on the shoulder and reads far low. This is step 2 of the algorithm and it is
not an optimisation.

**The error is systematic, and in the safe direction.** Every summit probed reads low, none
high, which is what a coarse grid does to peaks. For a sightline that is conservative: it
under-estimates how far a ship could see. And the sensitivity is mild, because range goes as
the square root of height — a 3% height shortfall is a 1.5% range shortfall, 1.3 km in 85.

**Never difference a land height against a sea depth.** `conf/sources.yml` warns that the
land is on "some land datum the record does not name" while depths are on Lowest
Astronomical Tide, so a value read across the coastline changes datum silently. For horizon
geometry this does not matter — a datum offset of a metre or two against summits of hundreds
is far below the 1.5% already accepted. For anything that subtracts one from the other it
matters completely. Treat land heights as relative until the datum is established.

### 8.5 The use constraint, recorded as a judgement rather than left implicit

`conf/sources.yml` carries `use_constraint: "DO NOT USE FOR NAVIGATION"`, and the
publisher's lineage text repeats it in capitals. This work builds a router.

**The judgement taken here: reconstructing where a premodern ship could see land is not
"navigation" in the sense the constraint means** — that constraint exists so that nobody
steers a real vessel by this data. It is a use constraint and not a licence bar, so it does
not touch redistribution. It is written down because it is a judgement, and the alternative
is that it is never noticed. Anything derived from this grid carries the same warning
forward, and no output of it may be presented as a chart.

---

## 9. How this will be checked

Per `TEAM.md`, and because the build will not catch any of it:

- **Confirm the land selector excludes something** (D-070). Print land cells against total
  cells at each resolution. `517 of 517` says it at once; a plausible percentage does not.
- **Ask the grid to name a row** (D-074). Every count of cells, joins or unreached termini
  resolves to identifiers and coordinates on demand, or it is not reported.
- **Cross-derive the coastline two ways.** The HWM length and the EMODnet zero contour
  measure the same coast by different instruments; where they disagree by more than the
  intertidal width, one of them is wrong.
- **Look at the places.** Ten estuaries on a map, chosen as the worst cases from §6's tail
  and not as a sample of the median. *Looking beats measuring* — aggregates have repeatedly
  agreed that a broken thing was fixed.
- **Report per basin as well as nationally.** A national join rate of 97% hides an estuary
  at 40%, and the estuary at 40% is the finding.
- **Never truncate a completeness check.** Any listing that answers "is there anything else"
  runs to the end.
- **A check must be able to fail.** The grid's first check was *"zero kept cells whose
  centre reads as land"* — but cells are kept **by** that test, so it returns zero whether
  the surface is right, wrong, inverted or absent. It is D-070 exactly: a predicate that
  cannot fail, reported as though it had been at risk, and it is the sentence a reader would
  have taken as the reassurance. rewt-16 caught it. It is replaced by three that can fail:
  the proportions kept and excluded, with a loud finding if either direction excludes
  nothing; a count of unmeasured centres; and **named rows in both directions** — Rannoch
  Moor and Salisbury Plain must be absent from the grid, Dogger Bank, the Minch and the
  Irish Sea off Anglesey must be present. The places are chosen from a map, not from the
  output, which is what makes them an anchor rather than an echo.
- **Name every outcome, and make them sum.** The replacement check first reported "kept
  39.9%, dropped as land 45.8%", which reads as though the two were complementary. One cell
  in seven fell into neither: 60,530 subdivided parents and 56 off-grid. `grid.py` now
  prints every outcome with an explicit SUM against the total tested, and states that
  "tested" is not a population at all — a subdivided cell is counted again as its children,
  so percentages against it are meaningless. rewt-16 found the 14.3% and guessed its cause
  correctly from the outside.

---

## 10. Decisions that are not mine

1. **Extend the EMODnet cache west and south** to `(−11.5, 49.0, 2.5, 61.5)` — **75 further
   windows**, ~301 MB, taking the cache to 195 windows and ~782 MB. **Implementer.** It re-pins `checksum`, which is a digest over the sorted
   `name:sha256` of all windows, so this is a deliberate manifest change and not an
   addition. Until it happens, nothing west of −8.0 can be planned against, and that
   excludes Ireland's Atlantic coast.
2. **`h3==4.5.0` in `requirements.txt`.** **Implementer.** Installed here already, on
   Stephen's instruction; the pin keeps the build reproducible.
**Three that were on this list are now settled, all by Stephen on 3 September 2026, and are
kept here with their outcomes rather than deleted:**

3. **Whether the sightline comes forward.** ~~§8 argues it should not.~~ **It comes forward.**
   §8 is rewritten accordingly and states which half stays deferred.
4. **Whether res 10 is ever built in estuaries.** **No** — no finer bathymetry will be
   registered, so res 9 is final. §5.2.
5. **The CC BY-NC route file.** **Not to be committed; deleted.** §2.

**Still open, and both the implementer's:** items 1 and 2 above.

---

## 11. References to carry into the documentation

`rules/H3.md` asks that the predecessor's references and data sources be linked from this
project's documentation. They are at
<https://github.com/docuracy/Historical_Sea_Routing#references-and-data-sources>, and the
attribution owed to EMODnet is already written in `conf/sources.yml` and must not be
attributed less fully anywhere it is repeated — provenance travels as a pointer.

---

## 12. The sightline layer, built

`tools/router/sightline.py`, run from the repository root. Maximum land elevation per H3
cell from EMODnet's land side, a refracted curvature horizon `sqrt(2 x 1.13 R x h)` per land
cell, and then for each sea cell whether any land cell reaches it.

**Output, in `docs/router/data/`:**

| file | |
|---|---|
| `sightline_r6.geojson` | 15,861 res-6 sea cells, 6.2 MB. Per cell: `visible`, and where visible the governing landmark's height, distance, margin, and position — so a viewer can draw the sightline itself, not just the zone. |

**Measured over the cached extent (−8.0, 49.5) to (2.0, 61.0):** 10,280 land cells and
15,861 sea cells at res 6; the tallest land cell reads 1,342 m and reaches 139.0 km;
**8,113 sea cells (51.2%) can see land, 7,748 cannot.**

**Verified against something outside the dataset**, because agreement inside it proves
nothing (D-067). The furthest sightlines resolve to identifiable mountains, and the readings
carry the systematic-low bias §8.4 predicts and nothing else:

| governing landmark, from its position | read | true | error |
|---|---:|---:|---:|
| Ben More, Mull — 56.4024 N, 6.0363 W | 946 m | 966 m | −2.1% |
| Ben Hope, Sutherland — 58.4057 N, 4.6089 W | 921 m | 927 m | −0.6% |
| tallest cell (Ben Nevis) | 1,342 m | 1,345 m | −0.2% |

The longest is 116.5 km, from west of Barra to Ben More on Mull. Every one is low, none
high, and a gazetteer is outside this data entirely.

**Three properties of the drawing, which belong in its legend and not only here.**

- **The hole must render as a third state.** West of longitude −8 there is no cached data,
  so Ireland's Atlantic coast computes as "no land visible" when the truth is "not known".
  There is no longer an unknown state to bound — see section 14. **Unknown must fail towards the visible
  fault** (D-077), and a blank sea is the invisible one.
- **Observer height is 10 m** — a masthead lookout, after Alvarez-Palau and Dunn (2019)
  as reported by Litvine et al. (2024). It was 0 m; Stephen overruled that, because a
  height of zero is not the assumption-free choice it looks like — nobody observes
  from the waterline. Ranges here are therefore NOT floors: a deck observer at 2 m
  would see 6.6 km LESS than what is drawn. The observer term is
  12.0 km — NOT 12.2, which is the 3.86 coefficient again, and which this
  document stated while the paragraph beside it warned against 3.86.
- **It is curvature only.** No occlusion by intervening land, no weather, no refractive
  variation. That is what "theoretically be seen" means and it will look more authoritative
  than it is.

**`docs/viewer/` is rewt-46's**, so the rendering is theirs and the format is their call;
this session writes only under `docs/router/`.

**What it changes about §5.** The land maxima this computes are the same object the grid's
land mask needs, at the same resolution, from the same raster pass — so the sightline work
turns out to have built half of the grid's input rather than competing with it.

### 12.1 Which of these figures can be attacked from outside

rewt-16's point, and it is worth stating before any of this reaches a page: of the two
headline numbers, **one has an external anchor and one has none.**

- **The 116.5 km longest sightline can be bracketed by anyone in one line.** Ben More is
  966 m; pure geometry gives `3.57 x sqrt(966)` = 110.9 km and this model's `k = 1.13` gives
  117.9 km. The computed 116.5 km sits just under the latter, and the shortfall is the
  −2.1% height bias (EMODnet reads 946, whose reach is 116.7 km). A reader can check every
  step of that without this repository.
- **The 51.2% of sea cells that see land cannot be checked from outside at all.** It is a
  property of the chosen extent, the chosen resolution and the observer height, and it would
  move if any of the three moved. It is reportable but it is not evidence, and it must never
  be quoted as though it were a measurement of the sea.

**A bracket is not a confirmation when the bounds are wide.** rewt-16 bracketed 116.5 km
between 111.0 and 120.0 km and read it as agreement; the upper bound used `k = 1.17` where
this model uses 1.13, so the interval was wide enough to admit the answer regardless. The
check was still worth everything — it is what found the constant above — but the agreement
it appeared to show was looser than it looked.

### 12.2 The H3 version rule, and why the two versions disagree

An H3 figure recalled rather than computed is probably v3, and **v3 edge lengths are short
by about 13%**. Measured against an actual `h3==3.7.7` install in an isolated environment.
Practically that is the whole rule: **recompute from the library, never scale back**, since
the shortfall drifts from 12.75% to 13.54% across the sixteen resolutions.

Both of the wrong figures this session put into peers' hands (a res-8 edge of 461 m, a res-7
edge of 1.22 km) are exact v3 constants. rewt-16 proposed that diagnosis as a labelled
hypothesis against my own harsher reading of it as invention, and was right.

**The mechanism is fully established, and it is two independent conventions, both rewt-16's
findings, neither of them an error by anyone.**

1. **v3 publishes the APOTHEM, v4 the SIDE.** v3's "edge length" is `sqrt(3)/2` times the
   regular-hexagon side implied by its own area — the centre-to-edge-midpoint distance, not
   the side. Tested at all sixteen resolutions, agreeing to between six and eleven
   significant digits. It is not a different sphere or projection; it is a different segment
   of the same hexagon.
2. **v3's area is a NOMINAL area, v4's a measured one.** v3's is the sphere's surface
   divided by a nominal cell count that treats each of the twelve pentagons as five-sixths
   of a hexagon. The true ratio is about 0.588, so the convention overstates the divisor and
   understates the area — by 2.45% at res 0, 0.42% at res 1, 0.064% at res 2, and away to
   nothing as the pentagons become a vanishing fraction of the cells.

**Together they account for the discrepancy completely.** With `reg4` as the ratio of v4's
true mean edge to the regular-hexagon edge implied by v4's own area — v4 cells are not quite
regular, and the deviation drifts with resolution:

    v3_edge / v4_edge  =  (sqrt(3)/2) / reg4 x sqrt(A3 / A4)

reproduces the measured shortfall at **all sixteen resolutions to within 0.00005 percentage
points**, which is float rounding. There are no residual exceptions.

**Two claims of mine that this overturned, both stated here because they were wrong in the
direction of over-confidence.** I wrote that v3 and v4 areas are "identical to better than
0.01% at res 2–12": res 2 differs by 0.0644%, six times that, and the correct statement
begins at res 3. And I wrote that the band prediction "holds at res 1–13" with res 0 and
res 14–15 as explained exceptions — there are no exceptions; my model was simply incomplete,
and the divergences I attributed to bad inputs were the second convention showing through.

I also conceded to rewt-16 that the identity at res 14–15 was a tautology, because v3's area
constants there carry only one or two significant figures. **That concession was wrong.** If
v3's edge had been computed from anything other than its own stored area constant, a rounded
area would not reproduce the published edge to six digits. It does, at every resolution. The
identity is informative at sixteen of sixteen.

---

## 13. The H3-002 rebuild

`rules/H3-002.md`, Stephen, 4 September 2026. Five items. What follows is what each
became, including the two where my first answer was wrong.

### 13.1 The sightline is computed from the land outwards

The first version asked each of 15,861 sea cells whether anything stood within its
horizon. Turned round, each parcel of land illuminates a disc of its own horizon and the
visible zone is their union.

**Banded by REACH, not by height.** Range goes as the square root of height, so equal
steps in height give wildly unequal steps in range. 70 bands of 2 km, descending, each
one distance transform over the whole raster — O(pixels), independent of how much land
is in the band. Crediting a band with its lower bound makes the quantisation
conservative: a cell is never claimed visible on a reach it does not have.

Stephen suggested coarse-to-fine over H3 land cells. This is the same idea in the form
the data is already in, and it needs no hierarchy.

**Cross-checked against the method it replaces:** 98.92% agree. 164 cells gained
visibility, which is expected — this tests every sea *pixel* where the old one tested
the cell *centre*. Only 7 lost, all with margins of 0.1–1.3 km against a 3.38 km budget
of band, CRS and pixel.

### 13.2 The bound is measured, and it is not Scandinavia

Probing every coast that could cast a sightline in:

| coast | height | reach | distance | reaches in? |
|---|---:|---:|---:|:---|
| W Norway | 1,484 m | 146 km | 430 km | no |
| Iceland | 1,436 m | 144 km | 700 km | no |
| Faroe | 885 m | 113 km | 290 km | no |
| Denmark | 89 m | 36 km | 290 km | no |
| **Ben Nevis** | **1,345 m** | **139 km** | — | **sets the maximum** |
| Kerry | 1,015 m | 121 km | inside | yes |
| Brittany / Boulogne / Normandy | 379 / 219 / 188 m | 74 / 56 / 52 km | 60 / 10 / 15 km | yes |

### 13.3 The distance transform runs in a projected CRS

The first inversion used one east-west pixel size taken at the mid-latitude across 11.5°
of latitude: **12% short at 49.5 N and 18% long at 61 N**, 14.07% worst against the
geodesic. Overstating in the north loses real visibility and shows up as a
disagreement; understating in the south **claims visibility that is not there** and
shows up as nothing at all. It was found only because the safe half was visible.

Measured over the extent: UTM 30N 0.33% worst, LAEA Europe 0.61%, LCC Europe 3.43%. UTM
30N is 453 m on a 139 km reach, inside the band quantisation. **Validated against exact
WGS84 geodesics**: 250 random sea points, 246 agree, and all four disagreements are
conservative.

Stephen's instinct was that sightlines need angular geometry and should be worked in
WGS84. The curvature is already inside `sqrt(2Rkh)`; what is left is pure distance, and
working *in degrees* is what breaks it. That changes if occlusion is ever modelled —
ray-casting needs azimuths, and conformality would become the criterion.

### 13.4 The trim, and the blind-sailing buffer

Cells beyond sight plus a buffer are **absent**, not coloured, so the layer shows only
in sight or out of sight. The unknown state is gone by construction rather than by being
explained.

**The buffer is measured.** How deep does a real crossing go out of sight?

| crossing | deepest blind |
|---|---:|
| Holyhead–Dublin, Orkney–Shetland, Kintyre–Antrim, Fair Isle–Shetland | **0.0 km** |
| Scilly–Brittany | 12.1 km |
| Land's End–Cork | **56.4 km** |

That four coastwise routes never leave sight of land at all is a check on the model, not
just on the buffer. 60 km covers the deepest that lies wholly within the British Isles.

It is a **routing decision, not a horizon and not a coast**, and it is in the published
stamp as its own field — rewt-46 asked for that, because a trimmed edge on a map reads
as something real.

### 13.5 A buffer must reach water that is IN SIGHT

**Faroe was admitted on a bad rule and my own arithmetic said so.** I wrote that two
60 km buffers cover a 97 km gap. Two blind zones touching is not a route. Stephen's
correction: a landmass is admitted only when its buffer reaches cells that are in sight.

And it is a rule about **landmasses, not extents** — clipping the box at 62.12 N left
Faroe's southern islands inside it casting a sliced-off zone. So the visible zone is
split into components, the walk starts from Liverpool Bay, and a component joins only
when the gap to an admitted one is within the buffer. Faroe is rejected by its own
figure: 62,798 px of sight, 97 km from anything in sight.

### 13.6 A spike is not an island

EMODnet has **six pixels reading +126 m** in the Faroe–Shetland Channel, standing in a
seabed whose median is −1,429 m for 50 km around with no shoaling. It was casting 40 km
of sightline over 150 cells and about 1,300 km² of open ocean.

**Area cannot separate that from a real mark** — Rockall is 0.001 km² and matters. What
separates them is that Rockall stands on a bank at about −200 m and this stands on
nothing. A land speck below 40 px is tested against the seabed it sits in.

### 13.7 The extent is declared, and two of its edges cannot be derived

| edge | value | basis |
|---|---:|---|
| west | −13.24 | derived: Kerry 1,015 m, 121 km + 60 |
| north | 62.12 | derived: Ronas Hill 450 m, 80 km + 60 |
| **south** | **44.50** | **declared: the Gironde** |
| **east** | **9.50** | **declared: the Elbe** |

**Geometry does not bound this area.** Every destination that matters to England and
Wales is reached coastwise, not by open crossing — Kent to the Scheldt is 88 km blind
direct but never blind hugging Calais, Ostend and Zeeland. The continental shore is
continuous, so the surface keeps connecting for as long as land is in the extent: it
would run to the Baltic and round Iberia.

**Stephen's criterion (option C): include coasts where coastwise sailing is how the
voyage was made; exclude those reached by an open crossing this surface cannot
represent.** Northern Spain is excluded on that ground and not on cost — it is 52 more
windows. Biscay is 281 km blind, so including Spain would add land the router could only
reach by going round the whole French coast: a confidently wrong answer rather than an
absent one. If it is wanted, it needs an explicit deep-sea leg, which is a different
mechanism and a separate decision.

432 windows, ~1.7 GB.

### 13.8 Finer resolution in estuaries: still overruled, and now with evidence

Item 5 asked whether res 10 was overruled. It was, and two findings since support it
rather than merely inherit it: the 41 untraceable termini are walled in by a median
6.1 m barrier, and Loch Etive is severed because EMODnet reads **+6.8 m at the Connel
narrows** — a 200 m channel averaged into land. Finer H3 cells over a 115 m surface
would subdivide an instrument that already cannot see the channel. **Res 10 needs finer
bathymetry, not finer cells.**

---

## 14. No blind sailing, and what it revealed

Stephen, 4 September 2026: keep the no-blind-sailing rule. The blind-sailing buffer is
zero. A cell is in the surface only if land is in sight from it, and a landmass joins
only when its sighted water TOUCHES sighted water already admitted.

**698 of 699 sight-components are rejected**, leaving one: Britain and everything whose
sighted water meets Britain's. Sea kept falls from 50.1% to 24.1%.

| rejected | sighted pixels | gap to anything in sight |
|---|---:|---:|
| Norway | 73,904 | **21 km** |
| Faroe | 31,033 | 136 km |
| Heligoland Bight | 2,536 | 7 km |
| IJsselmeer | 1,603 | 25 km |

Norway had been admitted because 60 km of buffer bridged a 21 km blind gap in the
Skagerrak — a gap nothing in the counts would have shown.

**It also disposes of a question rather than answering it.** Stephen found a dead zone in
the German Bight where "entering it gives no additional access to land". Under this rule
it is simply not there: blind water, kept only by the buffer. Its uselessness and its
blindness were the same fact.

### 14.1 The rule makes two independent attested voyages agree

This is the strongest evidence for it and it was not looked for.

| | buffered surface | no blind sailing |
|---|---:|---:|
| London – Skagen | 940 km | **1,271 km** |
| Falmouth – Bordeaux | 633 km | **1,195 km** |
| disagreement | **48%** | **6%** |

Both are given as about a week in July by eRutter. On a buffered surface the router was
free to cut across open water that was never sailed, and the two voyages implied wildly
different distances per day. Forced to keep land in sight, they converge.

**I first called this the anchor outside the set that D-067 asks for. It is not, and
Stephen corrected me.** eRutter is explicitly approximate and is better for comparing
routes than for definitive times. Both anchors are soft, both are "about a week", and two
approximate durations implying similar distances is not an independent test — the
agreement is between two soft numbers.

**What survives is narrower and still worth having.** The convergence is a real change in
the geometry: the same two routes, measured on two surfaces, go from 48% apart to 6%
apart. That is consistent with coastwise sailing being the right constraint. It is not
evidence for it, and the distinction matters because a soft anchor dressed as a hard one
is exactly the false corroboration this file keeps recording elsewhere.

### 14.2 A week's sailing, applied

The bound is 1,271 km of route distance, taken as the larger anchor so both voyages fall
inside, and measured ON THE NAVIGABLE SURFACE. **It is an order of magnitude, not a
threshold** — see 14.1 — and it should be described as "roughly a week" wherever it
appears — an earlier version measured through open
water and put Bergen nearer than the Denmark anchor, contradicting the model it was meant
to bound.

| | route | |
|---|---:|---|
| Esbjerg, west Denmark | 907 km | in |
| Skagen, the anchor | 1,268 km | in |
| **Aarhus, east Denmark** | **1,499 km** | out |
| Copenhagen | unreachable | out |

**And it was computed for some time without being applied.** `reach.py` wrote the bound
and nothing consumed it, so the east coast of Denmark sat in a layer a week's sailing does
not reach. A measurement nothing acts on is not a trim. 15,888 cells to 14,991.

### 14.3 Britain's sightlines are far broader than the continent's

Stephen's observation, quantified from the layer:

| coast | cells in sight | median governing land | median reach |
|---|---:|---:|---:|
| **British Isles** | 10,881 | **871 m** | **112 km** |
| north France and Brittany | 923 | 188 m | 52 km |
| Low Countries, Germany, Denmark | 747 | **34 m** | **22 km** |

Britain's sighted water reaches **five times further** than the Low Countries', and
Britain accounts for **73% of the whole in-sight surface**. The tallest land each coast
can offer differs by a factor of six: 1,323 m against 218 m.

**This is a navigational fact, not a cartographic one.** A master coasting Britain keeps
land in view across 112 km of open water; off Zeeland he loses it at 22 km and must
either hug the shore or accept a blind passage. It is a plain reason why the two sides of
the North Sea were sailed differently, and it falls out of elevation and the curvature of
the earth alone — no history is assumed to reach it.

## 15. In scope means near England or Wales, not inside it

The joins and traces were reaching up the Tay. The basin attribution said those termini
were in an English or Welsh basin, and the basin attribution was wrong — D-080's estuary
amalgams put the Nith and the Earn on the English/Welsh side of a line they do not belong
on. That delineation is the implementer's and it is still open. What follows is a guard,
not a fix, and the comment in `join.py` and `grid2.py` says so.

**The obvious test is wrong.** 194 of the 474 in-scope termini fall outside England and
Wales, and most of those sit in basins that are 99–100% English — the Gannel, the Welland,
the Dart. A tidal terminus lies *seaward of the high water line* by definition, and the
country polygon is bounded by that same line. A point-in-polygon test would reject
precisely the features it exists to keep.

**Distance works, and the data chose the threshold.** Measured to the union of the England
and Wales `country_region` geometries:

| percentile | distance |
|---|---:|
| 50th | 0.00 km (inside) |
| 75th | 0.01 km |
| 90th | 95.75 km |
| max | 167.91 km |

Nothing lies between 10 m and 96 km. Any cut from 1 km to 90 km gives the same partition,
which is the difference between measuring a boundary and tuning one. The configured
`scope_max_m_from_ew` is 1,000 m: a hundred times the observed offset of a legitimate
terminus, and two orders below the nearest thing it excludes.

**What moved.** 474 termini to 389. All 85 removals are Nith or Earn; nothing else changed
hands. The rule proportions are unchanged — 22.1% / 45.8% / 32.1% before and after — which
is what a contaminant looks like when it leaves, and not what a population looks like when
it is cut. Traces now stop at 54.98 N on the Solway. The northernmost join is at 55.76 N,
which is Berwick-upon-Tweed, in England.

If the basins are ever corrected the guard becomes a no-op rather than a second hidden
rule, because it excludes nothing that a correct delineation would have kept.

## 16. One land test, and the 220 cells that fell between two passes

Building the edges layer found a defect of a shape this repository has seen before.

`grid2.py` decided which cells were connected to the sea network using bare `grid_disk`.
`edges.py` then built the routing graph with `grid_disk` **and** a test that refuses a link
whose straight line crosses land. Each pass was internally correct and the two disagreed,
so **220 cells whose every neighbour lay across a spit survived the first and were isolated
by the second** — and one join had attached a terminus to a cell with no route out of it.
They are in fjords and estuary mouths narrower than a res-7 cell: the Sognefjord, the
Limfjord, Swansea Bay, Bridgwater Bay, Start Bay.

The test is now one function in `landtest.py`, imported by both. The Fens again: a rule
applied in one place and not the other, invisible while both places are self-consistent.

After the fix `edges.py` reports **0 isolated cells** and **one component** holding all
142,976. Land rejections in `edges.py` fell from 3,000 to 1,684, because most of them were
the doomed cells' links. Traces went from 101 to 102: the terminus that had been attached
to a dead cell now reaches the network.

## 17. The edges layer, and why the published one is aggregated

Stephen asked to see the travelling surface rather than the cells carrying it. I built
exactly that first — 415,520 res-7 edges — and then measured it: **80 MB**, roughly a
gigabyte once a browser has parsed it. So `docs/router/data/edges.geojson` is that graph
**aggregated to the res 6 of the published sea cells**: two cells are linked where any
res-7 edge joins a child of one to a child of the other, and `routing_edges` counts how
many. 49,080 links, 11.1 MB. Nothing is invented; every link is backed by real edges. But
**the drawn centres are res-6 centres, which no route uses**, and the layer says so.

The true lattice goes out unaggregated per named check area — severn 569 edges, thames 128,
wash 283, solway 388, loch-etive 43, mersey-dee 53 — which is where to look at it.

Two things a reader must not be allowed to miss, so both ride in the layer's own
properties rather than in a legend that can drift away from the geometry:

- `an_edge_is_not_a_route` — a drawn edge is an **adjacency**, not a track.
- `aggregation` — the drawn centres are not the centres a route uses.

Read together they say the picture is a schematic of a graph, not anything anybody sailed.

Aggregation lifts a res-6 cell into view as soon as **one** of its seven res-7 children is
in the grid, so it spilled a ring of 4,504 cells past the published layer — all perimeter.
Those 12,054 links are clipped out so the two halves of the toggle cover the same ground,
and the count is a property rather than a silent loss.

`crossing_a_band` counts features **in this layer**: 59. The res-7 graph behind it has 321,
because several edges collapse into one drawn link. Both are published, named apart.

## 18. An export does not mint a generation

I told visualisation that the edges layer and the cells layer "came from one pass". They
did not: 20260904T101447Z against 20260904T092019Z. Their cross-layer check — reading my
files — caught my own claim. Two things were wrong, and the one they found was the smaller.

**`export_edges.py` minted a fresh stamp every time it ran.** I re-rendered the same edges
an hour later to fix a property name, and the stamp moved, so two artefacts of one pass
disagreed about which pass they belonged to. **A generation belongs to the run that
COMPUTED the data; re-rendering it is not a new run.** The exporter now takes its stamp
from `edge_summary.json` and falls back to `generation()` only if there is none. It is
idempotent: run it twice and the file is byte-identical.

**And joins.geojson and traces.geojson carried no generation at all.** Their summaries did;
the layers a viewer actually loads did not. So the check could compare the only two layers
that happened to be stamped and was blind to the other two — the gap being invisible
precisely because the stamped pair is what got tested. Both are stamped now, re-run under
the pass's own generation, reproducing identically: 86 / 178 / 125 by rule, 102 traced.

`sightline2_r6.geojson` at 092019Z is genuinely an earlier pass and correctly says so. It
was not rebuilt because nothing it depends on changed, and the 220-cell drop orphaned none
of its cells. **Two of its 17,599 cells have no routing cell beneath them** — off Wexford
and off Caithness, sighted sea the graph never enters — and that is now a counted property
of the edges layer, `published_cells_with_no_edge`, rather than two hexes for a reader to
notice.

`sightline_extent.geojson` is deleted. It was published data that no current script wrote,
describing "the rectangle within which the answer is known" — a concept that stopped
existing when the unknown state went (section 14). `shot.py` used it as a deliberately
mapless page and now points at a summary instead. **A stale artefact nothing regenerates is
worse than an unstamped one: it reads as current and has no run behind it.**

## 19. A check that reports agreement over an unexamined population

Visualisation's cross-layer generation check compared the layers that HAD a generation. Two
of mine had none, so it would have reported "no disagreement" across a set of four where
two were never in the comparison at all. They named it correctly: **D-082 with the polarity
reversed** — the familiar fault is a negative result with no positive control, an absence
that means nothing; this is a positive result with an unexamined population, an agreement
that means nothing because the disagreeing members were not in the set.

That generalises past their check, so I audited my own published strings for claims of
agreement or absence that do not name their denominator. It found three, all in text rather
than in figures, and all of the same kind: **a sentence that outlived the number it
described.**

**`coast_summary.json` said "every range is a FLOOR: an eye at sea level, which is the one
value that assumes nothing"** — sitting immediately beside `observer_height_m: 10.0`. True
when the height was 0 m, and left standing when Stephen overruled that. It is the exact
sentence he objected to on the published site, still being written by `coasts.py` after the
change. The primary note is now taken FROM THE LAYER rather than restated, so it cannot
drift again, and a second note records that the old one was withdrawn rather than quietly
edited.

**`gov_reach_km` excludes the observer term and did not say so.** Admission used
`K·√h_land + 12.0 km`; the published per-cell reach and the per-coast medians use only
`K·√h_land`. So the sighted zone reaches 12.0 km further than the number a reader sees.
Britain's 112.0 km against the Low Countries' 28.0 km remains a like-for-like comparison of
the land, which is the claim it supports — but neither figure is the distance at which a
cell was admitted, and now both definitions say so.

**"a deck observer at 2 m would see 5.4 km less" was wrong, in the layer and in PLAN.md.**
5.4 km is that observer's OWN horizon; the difference from a 10 m masthead is 6.6 km. I then
copied the error into the note I had just written to fix the first one. And the same
paragraph said a masthead "adds 12.2 km" — that is 3.86·√10, the coefficient this document
warns against two paragraphs earlier. Correct is 12.0.

Three sentences, none of which any test could have failed, because **prose is the part of an
artefact that nothing recomputes.** The figures were checked; the sentences about them were
not, and they went out beside the numbers that contradicted them.
