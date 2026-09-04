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

## 20. Four toggles, not three stages

Stephen asked for the cell-centre link network beside the cells rather than instead of them,
and for the /check control to become individual toggles: **cells, sea network, traces,
joins**, in that order.

Once two layers can be on together the exclusive control is the wrong instrument. The
question the edges layer exists to answer — *does a join land on a cell the network actually
reaches* — cannot be asked one stage at a time. Declaration order is also paint order: cells
beneath, joins on top. The active layers' legends stack, their notes stack, and the figures
table is the union of their rows. A bookmarked `stage=` URL still opens somewhere sensible.

**The check areas grew from six to nine.** The first six were chosen for hard trace cases —
the multi-threaded Severn, Loch Etive's severance, the drying ground of the Wash. The edges
layer poses a different question, and the six contained **8 of 59 seams**, with thames,
loch-etive and mersey-dee containing none at all. An instrument keeps answering the question
it was built for. Cornwall, Cardigan and the Solent are added from where the seams actually
fall, and `export_edges.py` now prints the coverage every run and says so out loud when
most seams are not viewable. Coverage is 45 of 59.

Two faults of my own, in the hour after warning visualisation against exactly them:

- **The figures panel read `links drawn 415,520`** — the res-7 graph, when the layer draws
  49,080 aggregated. A figure beside a picture must count what is in the picture. It now
  reads from the drawn layer's own properties, not from `edge_summary.json`.
- **`shot.py` asserted the subject by comparing one name.** With a set of toggles that
  passed every single-layer shot and failed only the composite — a check that agrees with
  you until the moment it matters. It compares sets now.

All 59 seams touch a res-6 cell that contains refinement, which is the invariant: a seam
exists only where the banding actually changes resolution.

## 21. A node whose centre is on land is not a node

Stephen found res-7 cells off Portland whose centres sit inland, with joins reaching them
across a beach. He was right that they were supposed to be excluded, and they were not.

A cell was created because it **contains** kept sea. That is the right rule for a cell and
the wrong one for the point that represents it: the routing node is the centre, joins attach
to the centre, and the travelling surface runs centre to centre. So a cell could hold water
in one corner and put its node on a hill. The land test already existed for **links**;
`grid2.py` now applies the same test to the **node the links run between**, reading the same
232 m mask. **510 base cells dropped. The routing grid now has 0 cells whose centre is not in
water, from 284.** The graph stays one component, 0 isolated; joins move 86/178/125 to
84/180/125 and traces are unchanged at 102.

**The published edges layer had the same fault in a worse form.** It drew a line between two
res-6 **parent** centres — endpoints that are not nodes at all, and a res-6 cell is kept for
containing sighted sea, so its centre lands on a beach far more often: 511 of 17,599, 2.90%.
The aggregation is now a **thinning rather than a construction**: for each pair of published
cells the **shortest real res-7 edge** between their children is drawn, and `routing_edges`
says how many it stands for. Every line is an actual routing edge and both endpoints are
routing nodes.

Endpoints on land across all 49,054 drawn links: **1**, and it is a publishing artefact —
the node is in water, and rounding the coordinate to 4 decimal places moved it **1.4 m**
across a pixel boundary near Brest. Left as it is: chasing it would mean publishing more
precision than the 232 m mask has.

**And the legend became the control.** A separate row of buttons said the same thing twice
and put the switch furthest from the swatch it governs. Every layer is listed whether on or
off, so the panel says what EXISTS as well as what is showing — a control that hides its off
state cannot be read. `shot.py` asserts the subject by reading the same thing a person does.

## 22. Closing short blind hops

Stephen found small pockets of sea just out of sight of land which a navigator would cross
without difficulty, the largest mid-Channel, and proposed closing anything within about a
three-cell hop. His justification is the whole of the case and it is sound in three parts:
the visibility test is approximate, what can actually be seen depends on the weather in any
case, and **a short blind hop is not the same proposition as a blind passage**.

**It does not reopen blind sailing.** A uniform buffer grows the frontier outward
everywhere, which is what he ruled out in section 14. This fills only water that is
**enclosed**: a pocket qualifies when no point in it is more than `close_hop_cells`
cell-widths from water that does see land, so the open ocean beyond the sighted zone can
never qualify however large the threshold is set.

**The discriminator is not a threshold I chose.** Of the enclosed absences in the layer,
one has a sea fraction of **1.00** and every other is **0.43 or less** — because the others
are Shetland, Orkney, the Outer Hebrides, Islay, Man, Arran and Wight. They are islands, not
holes. There is nothing between 0.43 and 1.00, and Stephen's "I see no others" is exactly
what the data says. The ring depth is equally insensitive: with the sea test applied the
answer is **stable from 3 rings to 6** and collapses only at 2, so 3 is both his proposal
and the smallest value that works.

Measured, the mid-Channel pocket is **1,187 km², deepest point 10.4 km from sighted water,
median depth 3.9 km**. At 3 cells (19.4 km, derived from the H3 edge length, not typed) the
rule closes **330 of 702 blind pockets, 3,218 km², 22 published cells**.

**The filled cells are not marked visible.** They carry `closed_hop` and render amber. They
are blind water we accept crossing, and a rule that quietly promoted them would leave the
map claiming land is in sight where it is not.

## 23. One adjacency, after one land test was not enough

Closing the holes moved the sightline, and **7 isolated cells and 14 components came back** —
the exact defect section 16 was supposed to have fixed. The shared land test was only half
of it: `grid2.py` and `edges.py` also **built** the neighbour set differently, two
hand-written walks over `grid_disk`, ancestors and descendants. So "connected" still meant
two things and the disagreement waited for the inputs to move.

`adjacency.py` is now the single builder. Both import it. **0 isolated, 1 component, all
143,095 cells.** Two copies of a predicate is two chances to disagree, and the disagreement
is invisible while both copies are internally consistent.

## 24. The network drawn where the cells are

Stephen: *the cell-centre links do not join the cell centres.* True, and I had done it
deliberately — section 21 changed the drawn geometry to the shortest real res-7 edge so that
no endpoint sat on land. Both complaints are right and **they cannot both be answered at
res 6**: the routing nodes are res-7, and a res-6 picture of them is a schematic whichever
way it is drawn.

So the aggregated layer draws **centre to centre of the cells it is shown beside** — the
picture is at least internally consistent — and the **true lattice** goes out per named area
at its own resolution, as a fifth toggle, where cells and links agree and a link does join
two centres. The endpoints-on-land question belongs to res-6 centres, not to the network:
`grid2.py` guarantees every routing node is in water.

**And the drawn chord is land-trimmed too**, which Stephen had to point out. The res-7 graph
was already trimmed; the res-6 chord between two parent centres is a different line and can
run over a headland the res-7 route goes round. Same test, same mask: **1,347 links not
drawn**.

A fadable OSM basemap sits under everything, attributed, development use only, and
cross-fades with the synthetic coastline so the two backdrops do not fight.

## 25. The land test was right; it was not looking often enough

Stephen found three drawn links crossing the Uists. There was nothing wrong with the rule.

`landtest.py` took a **fixed 12 samples** along every link. On a 6.2 km res-6 chord that is
**517 m apart, against a 232 m mask pixel** — so the test stepped clean over any island
narrower than its own stride, and the Uists are full of them. The three links Stephen saw
crossed 3, 3 and 1 pixels of land respectively: real islands, invisible to a stride twice
their width.

Sampling every half pixel along the LINE caught those and left **78 links grazing a land
pixel**, because half a pixel along a diagonal is less than half a pixel along either axis.
The count is now taken from the **dominant axis in pixel units**, eight samples per pixel,
which cannot skip a pixel the segment passes through.

**The residual is 6 of 47,372, and it is asymptotic rather than a defect.** Each touches
exactly ONE 232 m pixel, at a corner, out of 31–36 traversed. No finite point sampling
closes that class — a line can always clip a corner between two samples — and what is left
is smaller than the coastline this mask is able to describe. Eight per pixel costs about a
minute on a full run. Near the Uists: 186 links drawn, none crossing land.

## 26. What a resolution band is, and a selector to see it

Stephen asked what "crosses a resolution band" means and whether there are other
resolutions to illustrate. **There are, and the answer is more interesting than the legend
was letting on.** The routing grid is res 7 nearly everywhere, res 8–9 in the refined
estuaries, and **res 6 where sight is lost** — the closed blind hops of section 22 are
binned coarse, so a band boundary is the edge of water you cannot see across. The grid
changes scale exactly where the evidence changes.

That could not be seen at one resolution, so /check now has a **maximum-resolution
selector** driving cells and network together, from one matched pair of files per
resolution so the two can never disagree:

| max res | cells | links | not drawn: over land |
|---|---:|---:|---:|
| 4 | 550 | 864 | 362 |
| 5 | 2,936 | 6,535 | 975 |
| 6 | 17,590 | 47,372 | 1,699 |

Res 7 is not offered for the whole extent — 416,635 edges, 80 MB. The routing-detail toggle
gives 7 and finer for a named area. Aggregation follows `sightline2`'s own fold: **any**
child that sees land makes the parent visible, and `gov_h_m` is the **maximum**.

## 27. Why not Shapely — no good reason, and it was hiding real crossings

Stephen asked why the intersection test was not simply a geometric one. There was no good
answer. The land definition lives in a raster — `fine_sea` at 232 m, the same surface the
traces walk and the node-in-water rule reads — so I stayed in raster space by reflex. **That
is a reason to polygonise the mask once, not a reason to sample it a million times.**

**The sampler was not merely inelegant; it was wrong, and I had written the error up as a
tolerance.** Section 25 called the last 6 links "asymptotic rather than a defect… smaller
than the coastline this mask is able to describe". An exact test finds those same 6 and they
are real crossings — my eight-samples-per-pixel test caught **1 of the 6**. Every version of
this test had a rate I kept raising and a residual I kept excusing.

**Polygonising costs 1.7 s and gives 5,825 polygons, 192,120 vertices in total.** The naive
version was slow — 133 s for 47,372 links — because a handful of rings hold most of those
vertices and every query pays for the whole European mainland. Clipped to a 50 km grid the
largest piece has 1,468 vertices:

| method | correct? | 47,372 links |
|---|---|---:|
| 8 samples per pixel | no — misses 5 of 6 | 1.94 s |
| Shapely, whole polygons | yes | 132.58 s |
| Shapely, clipped to 50 km | yes | **0.14 s** |

So the exact test is **950× faster than the naive geometric one and 14× faster than the
sampler it replaces**. There was never a speed argument for sampling; I had simply not
measured the alternative.

**The mask stays the authority.** These polygons *are* `fine_sea`, so the link test still
agrees with the traces, the node-in-water rule and the sea-connectivity fill. Substituting a
vector coastline from another source — Boundary-Line, say — would have made this one test
disagree with everything else in the pipeline, which is the failure of section 16 in a new
costume.

**Crossings now, exact, on the published geometry: 0 of 47,367 drawn links, 0 of 6,534 at
res 5, 0 of 864 at res 4, and 0 of 416,588 in the routing graph itself.** The first time this
has been provably clean rather than under a threshold.

One further find on the way. The first exact run still showed **1 of 47,367**, because the
exporter tested the exact cell centre and published it **rounded to 4 dp** — up to 11 m,
enough to move a drawn line across a headland the tested line missed. The exporters now
round first and test what they draw. Same lesson as the figures panel: measure the thing you
are actually showing.

A `channel` check area is added over the closed mid-Channel hop, where coarse cells sit
inside a fine grid; seam coverage goes from 25 of 187 to **132 of 187**.

## 28. Two coastlines, because one of them is better where it exists

Stephen's third land-crossing report, at Knapdale. The test was working exactly as written —
**0 of 10 links there cross land according to the mask** — and the mask was wrong. EMODnet at
232 m does not resolve the Taynish peninsula, so a link over it is, to that surface, open
water. The tool was fixed; the evidence was not.

**OS Boundary-Line `high_water` is an OGL vector coastline at about 1:10,000, already
registered, already drawn on /check.** Measured against it, **158 of the 28,977 drawn links
inside GB cross land the mask calls sea** — 0.55%. GB is now tested against both, and a link
is refused if either says land.

**The asymmetry has to be stated rather than hidden.** A link in Argyll is judged against a
1:10,000 coastline, one in Brittany against a 232 m raster, so the network is slightly more
permissive outside GB than inside it. That is a real bias in any route comparison across the
two. It is accepted for Stage 1 because the alternative — throwing away the better source
where we have it — makes the answer worse everywhere instead of evenly wrong, and no
equivalent open vector coastline is registered for Ireland or the continent.

**The node rule needed nothing: 0 of 143,077 routing nodes fall on OS land.** The two
sources already agree about where the cell centres are; they disagree only about what lies
between them.

Cost and effect: dedupe on `Global_Link_ID` first — 32,850 rows hold 13,002 distinct
geometries, the same 2.53× duplication recorded elsewhere in this project — then subdivide
to 10 km, giving 14,610 pieces and **2.9 µs per link**. The grid loses 94 cells
(143,077 → 142,983), traces 99 → 98, and `grid2` now refuses 2,734 directed links rather
than 1,780.

**Crossings on the published geometry, against BOTH coastlines: 0.** Drawn links 47,206;
res 5, 6,497; res 4, 859; the routing graph itself, 416,102; nodes on land, 0 of 142,983.

One process note. My first OS comparison returned "0 of 10 cross land" and I nearly reported
it. It had read **0 rows**: I passed a lat/lon bbox to a layer in EPSG:27700. A check that
examines nothing agrees with whatever you already believe, which is the fault this file has
now recorded in four different costumes — a vacuous selector, a summary over an unexamined
population, a stale artefact, and now a bounding box in the wrong units. **The row count is
what caught it, which is why the count gets printed.**

## 29. The joins were never land-tested, and the drawn graph was never connected

Three faults from one look at north Kent, plus one that is not mine.

**Joins crossed land: 125 of 267 drawn lines, 47%.** The links were land-tested from the
start and the joins never were. Rules 1 and 2 ASSERT a direct connection — *it is in this
cell*, *it is next door* — and a straight line over a headland is neither. A candidate whose
line crosses land is no longer eligible for them and the terminus falls through to **rule 3**,
which is the rule that says a path has to be worked out. The claim weakens from observation
to inference rather than the join quietly staying wrong. **32 rule-1 attachments and 110
rule-2 neighbourhoods refused; rule 3 goes 122 → 224 and traces 98 → 195.**

One join survived that check and still crossed land in the file. Rather than reason about
which of the two evaluations was right, `join.py` now re-tests **the line the file will
contain**, after rounding and after the frame is reassembled, and demotes what fails. It
caught exactly 1. The published artefact is the thing that has to pass — the same rule as
the exporters testing rounded geometry.

**The drawn network was disconnected: 9 components, 22 cells outside the largest.** The
ROUTING graph is guaranteed one component, because `grid2` drops what its own adjacency
cannot reach. The DRAWN layer is a different graph — its chords are land-trimmed separately,
and trimming one can strand a pocket the res-7 routing graph still reaches round the
headland. So it needs its own connectivity pass, after the land trim. Stephen asked whether
the simplest thing is to drop everything but the biggest connected set; it is, and nothing
cleverer is needed, because the routing graph beneath has already answered the hard version.
**18 links in 8 fragments dropped at res 6, 1 at res 5, 0 at res 4. Every layer is now one
component and 0 lines cross land.**

**No join targets a res-5 cell.** They are res 7 (341), res 8 (43), res 6 (5) — the res-6
ones being the closed blind hops. What Stephen saw was the resolution selector moving the
CELLS while the joins stayed put, so a join crossing a coarse hexagon read as attaching to
it. The panel now says so whenever the selector is off res 6.

## 30. The trim deletes nothing — a conclusion of mine, withdrawn

**The heading of this section used to read "The high water trim is what the traces exist to
undo". That was wrong, and the error is worth keeping visible because it is the one this
file keeps recording in new costumes.**

`rewt/stages/high_water.py` truncates watercourses at the OS High Water Mark. Stephen
proposed trimming at low water instead, and asked whether that would dissolve the ambiguity
in my joins. I measured the 389 in-scope termini against both lines and reported this:

| | to HIGH water (where cut) | to LOW water |
|---|---:|---:|
| rule 1 — already in a cell | 109 m | **3 m** |
| rule 2 — adjacent | 90 m | **12 m** |
| rule 3 — needs a traced path | 110 m | **1,300 m** (90th: 14.4 km) |

**The table is correct. The inference from it was not.** I measured those distances on
`published/rewt_stage1_network.gpkg`, which is the OUTPUT of the trim. Of course its termini
sit at the trim line. **I measured the consequence and called it the cause** — the same
family as a check that examines nothing, arrived at from the other direction.

**THE MEASUREMENT THAT SETTLES IT IS ON THE RAW SURVEY.** `data/raw/os_open_rivers`, before
any trim, 11,539 links with `form = tidalRiver`, downstream end of each against `high_water`:

| median | 75th | 90th | max | >500 m | >2 km |
|---:|---:|---:|---:|---:|---:|
| **39 m** | 115 m | 290 m | 7,212 m | 541 | 39 |

**OS Open Rivers already ends its tidal rivers at essentially the high water line.** The trim
is not discarding a tidal channel, because there is no tidal channel in the source to
discard: the survey does not map watercourses across tidal flats. 11,637 published tidalRiver
links against 11,539 raw — the trim barely changes the population, and the difference is
truncation splitting links rather than removal.

So both proposals gain almost nothing, for one reason. *Do not trim tidal rivers* would move
a terminus a median **39 m**. A low-water trim line would have nothing to keep between the
two lines. **The 1,300 m gap is in the world's data, not in the stage.**

**AND THE ADMINISTRATIVE LOW-WATER LINE FAILS SEPARATELY**, which is worth recording whatever
becomes of the rest. Probing `country_region` up four estuaries, it does not follow a
low-water line inland — **it closes across the mouth**. At Gravesend a point lies 23.4 km from
the country_region boundary and 0.64 km from high water; at Sharpness, 13.3 km against 0.19 km. The polygon swallows the whole tidal Thames and the whole tidal Severn.
`high_water.py`'s "the administrative area runs to the low-water limit" holds on OPEN COAST —
the Solway probe sits 50 m from the boundary and 4.8 km from high water — and does not hold
in an estuary, which is exactly where anyone would reach for it.

**What is actually true, as far as I can show it.** The river stops at the landward edge of
the intertidal because that is where OS stops surveying it; the sea grid stops at the seaward
edge because that is where there is water at every state of tide. **Nothing maps the channel
between.** The traced paths reconstruct unmapped channel and are labelled rule 3, inference,
which is the right label. The gap is honest and a different trim line does not close it.

R-01 stands where it stood: nothing here argues for changing the seeding rule, only that one
specific reason for changing it does not exist.

## 31. Three reported failures, all of them in the picture

Stephen reported joins that attach to nothing off the Exe, no network through the north
Solent, and missing joins on the Crouch and the Blackwater. **All three are presentation.
The routing graph was right in every case**, which is worth stating plainly because two of
them looked like routing failures and one of them looked like a missing algorithm.

**225 of the 389 joins had never been drawn.** Rule 3 emits a **Point** — deliberately,
because there is no straight line to assert; the path is stage 4's business — and the layer
was a `line` layer. MapLibre draws nothing for a Point on a line layer and reports no error.
So 58% of the joins were invisible, and the Crouch had 4 of them and the Blackwater 10.
Sheppey has joins at both ends, as Stephen suspected it should: the north-west one is a
line, the south-east one was a dot nobody drew. A `circle` layer filtered on geometry type
now draws them.

**The other two are one fault: a res-6 chord cannot represent a res-7 route.** Where the
water between two cell centres is narrower than the cells are wide, the straight chord
crosses land and was dropped — so the picture claimed the channel was impassable. The res-7
routing graph goes through it perfectly well: **Hurst to Cowes Roads is 20.0 km routed
against 18.4 km straight, a ratio of 1.08.** Rather than drop such a link, the exporter now
walks the res-7 path between the two cells and draws THAT. The search is restricted to the
res-7 children of the two parents — at most fourteen nodes — so it answers the local
question cheaply. **1,844 links are now drawn along their route instead of being dropped**,
in green, and the isolated-fragment drop falls from 18 links in 8 pieces to 1 in 1.

The Exe join that appeared to land in open water attaches to a cell whose res-6 parent had
no drawable chord. It has one now.

**What resolution threads what channel**, since Stephen asked. A link needs both centres in
water AND the chord in water, so a channel much narrower than the centre spacing is threaded
only by luck of alignment:

| res | edge | centre-to-centre | channel it can thread |
|---:|---:|---:|---:|
| 5 | 9.85 km | 17.07 km | ~17 km |
| 6 | 3.72 km | 6.45 km | ~6.5 km |
| 7 | 1.41 km | 2.44 km | **~2.4 km** |
| 8 | 0.53 km | 0.92 km | ~0.9 km |
| 9 | 0.20 km | 0.35 km | ~0.3 km |

The routing grid is res 7, so it threads down to about 2.4 km reliably and the Solent only
just qualifies. **Nothing is severed today — the graph is one component — so this is a
question of detour, not of connectivity**, and the detours measured here are 1.08x and 1.19x.
Extending the estuary refinement rule to subdivide wherever a link is refused for crossing
land is the natural next step and is NOT done: it should be justified by measured detours,
not by the fact that it is possible.

## 32. What a refused link actually costs

Section 31 left refinement as a possibility and said it should be justified by measured
detours. `tools/router/detour.py` measures them.

**The object measured is the res-7 routing pair, not the res-6 drawn link.** Section 31's
1,844 routed drawings are a rendering count; the thing that costs a route anything is the
**786 adjacent res-7 pairs whose link is refused for crossing land**. For each, two
distances: `d_graph`, the shortest path through the routing graph, and `d_water`, the
shortest path between the same two points through the 232 m sea mask — the finest evidence
available, and therefore the bound on what any refinement could recover.

**The grid goes nearly twice as far as the water requires.**

| percentile | d_graph / d_water |
|---|---:|
| 50th | **1.90x** |
| 90th | 2.66x |
| 95th | 3.00x |
| worst | 9.2x |

29.5% detour more than 2x, 5.1% more than 3x, 1.3% more than 5x.

**And the thing in the way is usually small, which is what decides whether refining helps.**
`d_graph/d_water` says the grid overshoots; it does not say a finer grid could do better —
two cells either side of a real peninsula are correctly refused at any resolution. The
discriminator is `d_water/chord`: if the water runs nearly straight between the two centres
the obstruction is an islet or a spit tip, and a finer grid threads past it.

| | d_water / chord |
|---|---:|
| refused pairs, median | **1.08x** |
| refused pairs, 90th | 1.26x |
| **control — 300 pairs NOT refused** | **1.05x** median, 1.12x 90th |

**618 of 786 (78.6%) are within 15% of straight.** The control matters: without it, 1.08x
could have been an artefact of measuring water paths on a raster, and it is not — accepted
pairs measure 1.05x by the same method. So the refused pairs are almost exactly as straight
through water as the unrefused ones. The grid detours a median 1.9x to get round something
that costs the water 8%.

**So refinement is justified in principle — and mostly out of scope in practice.** The
median refused pair is **324 km from England or Wales**. Only 113 of 786 (14.4%) lie within
25 km of it, 143 within 100 km. The worst offenders are Skye, Barra, north-west Scotland,
Rogaland, Lolland, Mayo, Shetland and the Seine. **82% of the detour is in water this
project is not about.**

The mechanism is the existing estuary refinement, extended from *a cell holds land and a
join uses it* to *a link is refused and `d_water/chord` says the obstruction is small*.
It is measured and not built: 786 pairs are 0.19% of 416,102 edges, the graph is one
component without them, and the payoff concentrates in 113 pairs near the region of
interest. That is a decision about priority, and the numbers to take it with are now here
rather than in anyone's judgement.

## 33. Refining where it was measured to be worth it

Stephen's call, on section 32's numbers: refine the pairs near England and Wales, leave the
rest. `grid2.py` now does it, and the result is a count rather than a ratio.

**Refused adjacent res-7 pairs within 25 km of England or Wales: 113 → 8.** Both figures
measured the same way, on the same threshold, before and after. The grid grew by 801 cells,
0.56%, from 287 corridor cells subdivided to res 8. Nothing else moved: **0 isolated,
1 component, 0 lines crossing land on every published layer.**

**THE CORRIDOR, NOT THE ENDS.** The channel between two refused cells may run through a
third, so subdividing only the pair leaves the gap in the middle. The refinement walks the
water path from `waterpath.py` — the same function `detour.py` measures with, so the
refinement is aimed at exactly the pairs the measurement selected — and subdivides every
res-7 cell that path crosses.

**THE SURVIVORS LOOK WORSE AND THAT IS SELECTION, NOT FAILURE.** The 8 remaining near
England and Wales have a median detour of 2.81x against 1.89x for the unrefined rest. Read
carelessly that says refinement made things worse. It says the opposite: the easy cases —
small obstruction, water essentially straight past — are the ones refinement removes, so
what is left is enriched for hard geometry. **The comparison to make is 113 against 8, not
2.81x against 1.89x.** The refined-versus-unrefined split is in `detour_summary.json` with
that caveat attached to it, because the number is misleading without it.

**WHAT IT COST.** Rule 1 attachments fell 50 → 45 and rule 3 rose 224 → 229: subdividing a
cell near a terminus can move an attachment from *inside this cell* to *needs a path*. That
is a small loss of observation for a real gain in the surface, and it is recorded rather
than netted off.

**AND ONE PERFORMANCE NOTE THAT IS REALLY A THINKING NOTE.** The first version tested all
143,078 cells for exact distance to England and Wales *before* looking at their links. There
are only about 800 refused pairs in the entire grid. It ran for twenty minutes and was still
going. The expensive test belongs after the cheap one — and the reason I wrote it the wrong
way round is that I described the rule as "pairs near England and Wales whose link is
refused" and then implemented the clauses in the order I had said them.

## 34. What the mesh actually covers

rewt-46 measured the mesh against the implementer's `sea_route` network and got **58.1%**
of its 4,184 entries. I had told them my grid "supersedes it in function" without ever
computing a coverage figure. Their number is right and the claim was not.

**REPRODUCING IT FIRST, because a disagreement about a number is worthless until both
sides compute the same thing.** My first attempt gave 38.1%, because I took each entry's
position from `sea_entry.easting/northing` — and those are the **river mouth**, not the
entry. `sea_entry` holds 11,958 rows over 4,184 entries, one of them carrying 108 mouths,
so `drop_duplicates("entry_id")` hands back an arbitrary mouth's coordinates. Positioning
entries the way rewt-46 did — intersecting the endpoints of every route incident to an
entry, since `from_entry`/`to_entry` do not say which end is which — reproduces **2,432,
58.1%, exactly**.

**AND THEN THE QUESTION THAT MATTERS: is the gap rendering or absence?** 58.1% is against
the **published res-6 layer**. Against the **res-7 routing grid**:

| | entries | mouths |
|---|---:|---:|
| in a routing cell | 1,366 (32.6%) | 3,577 (29.9%) |
| one ring away | 1,657 (39.6%) | 4,459 (37.3%) |
| two rings away | 451 (10.8%) | 1,562 (13.1%) |
| **absent** | **710 (17.0%)** | **2,360 (19.7%)** |

**83.0% of entries are within two rings of the routing grid against 58.1% in a published
cell, so most of the gap rewt-46 measured is rendering.** A cell one hexagon from a mouth is
still a reachable coast, and the aggregation I publish — clipped to the sightline cells,
4,504 perimeter cells removed so a viewer toggle would line up — hides it. That clip was
made to satisfy a rendering requirement and nobody asked what it cost a consumer joining
against the layer.

**But 17.0% is genuinely absent, and that is a real limit of the surface**, not a drawing
problem: 710 entries with 2,360 river mouths behind them, in creek heads and narrow
estuaries the res-7 lattice cannot represent — the Cromarty firth heads, Southampton Water,
Clementsgreen Creek on the Crouch, the Clyde above Dumbarton, the Tay above Perth. The same
class as the fjords whose cells were dropped as unroutable.

**So `sea_route` does not retire on the mesh's account** and that has been said to
visualisation as my position. A surface that is provably clean over 83% of the entries and
absent from a fifth of the mouths is not a replacement for one that covers all of them.

## 35. The coastal surface, published at its own extent

rewt-46's ruling and it is the better rule: **a visible mismatch that is explained beats a
tidy picture that has silently lost the estuaries.** So `cells_r7_coast.geojson` and
`edges_r7_coast.geojson` publish the routing cells THEMSELVES over the coastal band, at res
7, at an extent that deliberately does not match the sightline layer.

**The band is chosen by what it covers, not by generosity.** Every routing cell within 5 km
of land: 21,974 of 143,879, 15.3%, 6.2 MB of cells and 8.7 MB of the 48,413 links between
them. That band captures **exactly as many sea entries as publishing all 143,879 cells
would** — 1,366 in a cell, 3,023 within one ring. Three kilometres loses ten of them; eight
adds none.

**IT IS A BAND, NOT A SURFACE, AND ITS 32 COMPONENTS ARE NOT A DEFECT.** A 5 km strip around
separate landmasses *is* separate — the water between them is simply further from land than
the band is wide. The temptation is to drop the small pieces, which is what I did to the
drawn network in section 29 and would be exactly wrong here: **the routing graph these cells
belong to is one component of 143,879, and this layer is a window onto it.** Connectivity is
a property of the graph, not of the window. The layer says so in its own properties.

**One more name collision found by the harness.** The new layers were `x-coast-c` and
`x-coast-e`; `shot.py` counts drawn features by excluding ids beginning `x-coast`, which is
the dark background coastline. So the whole layer was invisible to the check and reported
NOTHING DREW while drawing 64,221 features. The fix is not to rename mine — it is that a
harness which excludes by name prefix can silently swallow a layer. The background context
is now `x-bg-land` and `x-bg-coast`, and the filter excludes `x-bg`, which cannot collide
with a subject layer by accident.

## 36. Is it one network yet? No, and here is the number

rewt-46 asked, before drawing anything that implies Stephen's single-D8-network expectation,
whether that network exists today — and asked for a file and a property to **test** rather
than a claim to repeat. `tools/router/connectivity.py` builds the whole thing and counts:
river links, sea edges, and every join that actually attaches.

**A rule-3 join attaches only if its trace succeeded.** The rule says a path has to be
worked out; an untraced rule-3 terminus has no way to the sea, and counting it as attached
would assume the thing being measured.

    combined graph          342,288 nodes, 614,307 edges
    components              4,103;  largest holds 72.6%
    termini attached        359 of 389;  30 stranded
    in-scope river nodes
      reaching the sea      104,736 of 128,170  = 81.7%

**So: not yet, and 81.7% is the honest figure.** Two reasons in order of size. Most in-scope
river nodes that do not reach the sea sit in river components that never reach an attached
terminus at all — that is the inland network's own connectivity, R-01's territory and the
implementer's, not the grid's. The rest is the 30 stranded termini: rule-3 joins whose trace
across the drying ground failed. `network_summary.json` names all 30.

**AND A STAMP THAT WAS ASSERTING A CONSISTENCY THAT DID NOT EXIST.** `trace_summary` said it
attempted **229** rule-3 termini while `joins.geojson` held **230**, both carrying generation
20260904T193156Z. `trace.py` reads the `rule3` list out of `join_summary.json`, and that list
was written *before* the land-crossing demotion — so the demoted terminus was never offered
to the trace stage, in this run or any earlier one. Fixing the demotion's position (section
34) fixed the list; re-running trace against it gives **attempted 230, traced 200, failed
30**.

The lesson is about the stamp rather than the count. **Re-running one stage under a fixed
generation preserves the stamp and can break the invariant the stamp exists to assert.** I
did that deliberately to correct a miscount, reasoning that the data had not changed — and
for the summary that was true, while for `rule3`, which is an *input to another stage*, it
was not. A stamp is a claim that the artefacts came from one consistent pass, and it is only
worth anything if re-running a stage means re-running what depends on it.

## 37. A stamp that is never reused over different bytes

Section 36 recorded the fault: `traces.geojson` held 199 features and then 200 under the
same generation, because I re-ran one stage under a fixed stamp and reasoned the data had
not changed. rewt-46 put the consequence plainly — their viewer warns when two loaded layers
disagree about their generation, and that check is worth exactly as much as the stamp's
discipline. For one file that day it was worth nothing.

They said they were not asking for a retrospective re-stamp. **That is more generous than it
should be, and the fix is two things rather than one.**

**A CLEAN PASS.** Everything downstream of the masks rebuilt under one new generation,
`20260904T202145Z` — grid, joins, traces, coasts, edges, both coastal layers, the detour
measurement and the connectivity answer. `docs/router/data` now carries three generations
and each is explicable: 12 files from that pass, 3 from `111903Z` where the sightline surface
sits because nothing it depends on has moved, and 1 from `092613Z` for the disabled lights.
No file shares a stamp with different content any more, on disk or in a consumer's cache.

**AND A LEDGER, so it cannot happen quietly again.** `tools/router/stamps.py` records
`generation -> {file: sha256}` and fails when a stamp reappears over bytes that have moved.
It does not prevent a partial re-run — sometimes that is the right thing — it prevents a
partial re-run being **silent**, which is the part that cost a consumer something.

**The check is proven rather than asserted.** I edited one field of `trace_summary.json`,
leaving its stamp alone, and it reported:

    STAMP REUSED OVER CHANGED CONTENT — the stamp is asserting a consistency that
    does not hold:
      trace_summary.json  generation 20260904T202145Z  was 0c3d7634…  now 40304363…

then passed again when the file was restored. A check that has never fired is a check nobody
has tested, which is D-082 in the form this file keeps meeting it.

**The general shape, since it is the third time today.** A stamp, a scope column, a coverage
figure — each was a claim that something held, and each was worth nothing until someone
tried to break it. The mechanisms are cheap; the discipline of firing them deliberately is
the part that keeps being skipped.
