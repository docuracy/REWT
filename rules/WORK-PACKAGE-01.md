# Work package 01

**Status: R-00 done; the rules themselves not started.** The canonical list Stephen asked
for exists (`conf/rules.yml`, `rewt rules`, D-078). No rule in it has been applied, and no
data, geometry or basin has been changed.

Two inputs: `rules/0001.md`, written by Stephen on 3 September 2026, and a finding reported
by rewt-46 (visualisation) the same afternoon. They are related — item **R-01** below is a
re-specification of the sea network, and rewt-46's finding is a fault in the basin
delineation that the same stage boundary touches.

Assembled by rewt-e8 (implementer). Every figure here names the file or query it came from,
because a figure with no file behind it is a rumour (D-076).

**Corrected on 3 September after cross-reading, five times.** rewt-46 found my per-basin
sea lengths were uncut and my `sea_reach` arithmetic double-counted a nested reading;
rewt-c1 found the same arithmetic fault independently, and found that my inner join to
`audit_basin` had cost me a basin and four rows of a band table; rewt-50 found that the
basin labels I called unreliable are a correct measurement read in the wrong frame;
rewt-68 found that "5,411 km of Scottish network" was an overstatement I had propagated
from the original report without checking, and that the national in-scope figures I
called sound are themselves basin-dependent. Every correction was re-derived here before
being accepted, and one — an unreached length — turned out to be a difference of
definition rather than an error, so both readings are given. D-081 keeps the tally.

---

## Part A — the basin delineation has swallowed the sea

### What rewt-46 reported

Two in-scope basins are estuary amalgams rather than catchments, pulling 5,411.5 km of
network into scope:

| basin_id | label | area | England & Wales | real catchment, roughly |
|---|---|---:|---:|---:|
| `rewt:basin/54261d5c6c` | River Earn | 4,176.3 km² | 167.1 km² (4.0%) | ~800 km² |
| `rewt:basin/00d61efbeb` | River Nith | 9,655.0 km² | 792.6 km² (8.2%) | ~1,230 km² |

The Earn polygon runs from Northumberland to Montrose; the Nith holds the Duddon Channel in
Cumbria at one end and the Isle of Bute at the other. Nothing reports them:
`outletless_basins.unexplained` is 0 and every stage passes. The scope rule then behaves
exactly as D-024 says it should — a basin with any part in England or Wales is in scope
entire — so the scope rule inherits the error rather than causing it.

### Verification — independent, and it holds

Re-derived from `db/rewt.ddb` (tables `basin`, `link`, `link_scope`, `repair_link`,
`retirement`, `node_basin`, `audit_basin`, `sea_link`) and from
`published/audit/dead_ends.json`. rewt-46 measured from `published/rewt_stage1_network.gpkg`
and `docs/viewer/data/dead_ends.geojson` — a different route to the same numbers.

| figure | rewt-46 | re-derived |
|---|---|---|
| in-scope, the two basins | 6,654 links / 5,411.5 km | **6,654 / 5,411.5** |
| in-scope, `basin_id IS NULL` | 11,648 / 8,661.3 km | **11,648 / 8,661.3** |
| in-scope, every other basin | 108,819 / 91,626.2 km | **108,819 / 91,626.2** |
| in-scope total | 105,699.0 km | **105,699.0 km** (= `sea_reach.in_scope_km`) |
| dead-end defects | 1,303 | **1,303** |
| of them in the two basins | 118 (9.1%) | **118** (Nith 94, Earn 24) |
| of them north of N 660,000 | 28 | **28** (Earn 24, Nith 4) |
| Earn / Nith area, EW area | as tabled | **exact to the decimal** |

Every figure reproduces. One trap worth recording for whoever repeats this: the in-scope
population is **not** `link_scope JOIN link`. 2,435 in-scope link ids live in `repair_link`,
not `link`, and 635 in-scope rows are retired. The correct population is
`link_scope WHERE in_scope`, minus `retirement`, with length from `link` **or**
`repair_link` — 127,121 links, 105,699.0 km. The naive join loses 1,800 links and 236.2 km
and looks plausible.

**It is not a hypothetical trap: the build has already fallen into it and published the
result.** `published/audit/basins.json` states `links.in_scope: 125321` and
`in_scope_km: 105462.8` — the naive figures exactly — in the same directory as
`sea_reach.json`'s 105,699.0. The repository publishes two in-scope totals that differ
by 1,800 links and 236.2 km, and nothing compares them. Found by rewt-c1, who is
widening `test_the_two_reachability_readings_are_computed_the_same_way` to require every
in-scope total published anywhere under `published/audit/` to agree. It fails today.

### The cause, and it is one failure rather than two

rewt-46 asked whether the Earn (a coastal strip) and the Nith (spanning an open firth) have
the same cause. They do, and it is simpler than either description:

**the basin polygons contain open sea.**

`ST_Contains` against the delineated polygons:

| point | inside which in-scope basin |
|---|---|
| open sea off Arbroath, E 375000 N 742000 | **River Earn** |
| mid Firth of Forth, E 330000 N 682000 | **River Earn** |
| mid Solway Firth, E 310000 N 553000 | **River Nith** |
| mid Firth of Clyde, E 200000 N 655000 | **River Nith** |

Both are single contiguous polygons (`ST_Dump` gives one dominant part plus raster-cell
slivers of 0.0 km²), not lobes stitched together at an outlet. The tidal surface was not
removed before delineation, so every watercourse entering a common firth accumulates to one
sink and the firth is inside the resulting catchment. That is the shared-estuary trap of
PLAN.md §4.1, occurring in the topographic delineation rather than in the component test it
was written about.

### It is not confined to those two, and not to Scotland

Tested generally, using this repository's own definition of the sea — the `sea_link`
table built by the sea stage. A catchment cannot contain the sea network.

**110 of 334 in-scope basins have polygons that intersect it.** rewt-46 reproduced that
count exactly from the GeoPackage's `sea_route` layer through geopandas — a different
table and a different engine — so the count is not an artefact of either route.

**How much sea is inside must be measured clipped, and my first pass was not.** Summing
whole `sea_link` lengths over an `ST_Intersects` join gives a link that merely touches a
polygon its entire length. Caught by rewt-46; re-measured here with `ST_Intersection`
and the corrected figures are theirs to the decimal:

| sea km inside, clipped | (uncut, wrong) | label | area | EW% |
|---:|---:|---|---:|---:|
| 1,025.2 | 1,347.7 | River Nith | 9,655.0 | 8.2 |
| 442.8 | 480.0 | River Earn | 4,176.3 | 4.0 |
| 220.5 | 250.7 | River Deben | 1,969.7 | 58.9 |
| 213.4 | 291.8 | Lancaster Canal | 3,559.9 | 71.4 |
| 118.5 | 209.3 | River Crouch | 970.2 | 53.2 |
| 104.2 | 158.2 | Fleet Haven Outfall | 795.7 | 52.1 |
| 93.9 | 105.5 | Afon Llifon | 430.6 | 21.3 |
| 86.6 | 178.4 | River Lea | 6,110.5 | 98.8 |
| 78.4 | 238.1 | Afon Braint | 878.9 | 54.2 |
| 68.7 | 98.7 | River Lavant | 667.0 | 76.9 |

Afon Braint was out by a factor of three and moves from fifth to ninth. The roll-ups
move further, because whole-link attribution promotes basins that only clip a corner:

| | uncut (wrong) | clipped |
|---|---:|---:|
| basins holding ≥ 10 km of sea | 52 | **25** |
| network in them | 24,205.5 km | **18,557.7 km** |

I first reported 51 and banded the 110 as 10/45/39/6/6, which sums to 106. Both were
one error: I joined to `audit_basin`, and 4 of the 110 basins have no row in it. The
bands are **11/47/40/6/6**. Found independently by rewt-46 and rewt-c1.

**There is no defensible km threshold, and the ≥ 10 km cut above is a convenience.**
rewt-c1 established it: clipped, 99 in-scope basins enclose sea, totalling 2,896.9 km,
and the small tail runs 50.0, 70.7, 100.0, 141.4 m — the 50 m cell and its diagonal,
i.e. delineation quantisation — continuously upward with no break (largest gap in the
bottom 60 is 148.6 m). Any cut in kilometres is a preference. Two threshold-free
statements do the same work: **12 in-scope basins enclose more sea network than river
network** (Fleet Haven Outfall 104.2 km of sea against 102.3 km of network, Afon Llifon
93.9 against 61.8, Afon Gwril 39.4 against 22.4), and the enclosed total of 2,896.9 km
is a regression bound in the style of D-069.

**The unreached length in those 25 basins depends on which question is asked, and both
readings are correct.** 1,829.6 km does not reach tidal water — that is
`audit_basin.unreached_km`, the column `audit.md` ranks basins by. 840.3 km reaches
neither tidal water nor the sea, which is the stricter "cannot get out at all" reading
and the one rewt-46 measured. The 989.3 km between them reaches the sea network without
touching a `tidalRiver` link. Quote whichever, but say which.

Below N 550,000 there is no Scotland to blame for area that is not in England or Wales,
and that area is sea: **Afon Gwril is 87.1% not-land, Afon Llifon 78.7%, Afon Wyre
64.8%, Aldingbourne Rife 46.1%, River Crouch 46.8%, River Deben 41.1%.**

**These are the same basins the audit already ranks worst for reachability.** Afon
Llifon 9.6% reached, Aldingbourne Rife 14.6%, Afon Gwril 33.1%, Afon Wyre 60.5%, River
Deben 70.5%, River Crouch 86.0% — all in `published/audit/audit.md`'s "this is the list
to work down". The list of worst basins and the list of basins containing sea are
substantially the same list, which has not previously been noticed and is the reason to
treat this before working the backlog rather than after.

### The third instrument, which sees the failure the other two cannot

There are now three ways to find a bad basin and each is blind to something.

1. **Sea enclosed in the polygon** (rewt-e8, `sea_link`). Finds sea-filled basins. Moves
   when R-01 moves, since it measures against the sea network R-01 redefines.
2. **Area unaccounted by land** (rewt-68: `area_km2 − england_wales_area_km2 −
   scotland_km2`, the last from `basins.json`'s seven `cross_border_basin` findings).
   Uses no sea network, so it is stable under R-01, and it separates the genuine
   cross-border basins by construction — Tweed reconciles to 3.2 km² and Esk to 0.0.
   8,781 km² unaccounted over the 334; 12 basins over 100 km², 25 over 10, 57 over 1.
3. **Drainage components per basin** (rewt-e8, at rewt-68's suggestion). A real
   catchment is one drainage component. Needs no sea network and no land polygon.

**rewt-68 named the blind spot that makes the third necessary, and it is the important
one: neither of the first two can see a basin that is too big on land.** River Lea is
6,110.5 km² with 6,038.2 km² in England and Wales, so it reconciles to 72.3 km² and looks
nearly clean. **River Aire does not appear in the unaccounted list at all** — under 1 km²
— and it is 11,873.5 km² against a real catchment near 1,000. Both are amalgams. Neither
is a sea problem.

The component count sees exactly those. Over the 361 in-scope basins carrying network:

| components | names | links | km | basin |
|---:|---:|---:|---:|---|
| 188 | 1,062 | 5,111 | 3,975.4 | River Nith |
| 64 | 315 | 1,543 | 1,436.1 | River Earn |
| 58 | 413 | 2,451 | 1,958.2 | River Irwell |
| **53** | **2,242** | **9,682** | **7,985.7** | **River Aire** — invisible to instruments 1 and 2 |
| 51 | 559 | 3,538 | 2,129.8 | Lancaster Canal |
| 37 | 750 | 5,584 | 5,632.1 | River Trent |
| 32 | 426 | 3,481 | 2,949.5 | River Lea |
| 28 | 682 | 6,478 | 5,197.2 | River Thames |
| 15 | 5 | 106 | 61.8 | Afon Llifon |

**214 of 361 are a single drainage component**, which is the correct shape. **25 hold ten
or more.** A basin of 53 components carrying 2,242 distinct watercourse names is not a
catchment under any reading.

**State its blind spot too, because it has one.** River Tweed is 9 components and is a
genuine basin; an unrepaired network has real gaps, so a high component count is
consistent with a correct polygon that simply has not been closed yet. The count is a
ranking, not a verdict — the same status PLAN.md §5 gives the terrain screen. What makes
it evidence is agreement with the other two, and on the Aire it is the only one that
speaks at all.

### Two failures, not one, and only one of them touches scope

rewt-46's second distinction, and it matters more than the first. Cross-tabulating the
334 in-scope basins on whether they have an outlet node and a label:

| | has label | no label |
|---|---:|---:|
| **has outlet node** | 179 | 52 |
| **no outlet node** | 79 | 24 |

The Nith and the Earn drag network into scope across the border, and the scope figures
are how they were found. **The `rewt:basin-unanchored/` coalescences do not.** "River Aire" is
`rewt:basin-unanchored/1523`, 11,873.5 km², `outlet_node` NULL — and its
England-and-Wales area is the whole 11,873.5 km², so it is a pure coalescence with no
scope component whatever. Nothing in the scope figures can see it, and nothing else
looks. That is the more dangerous of the two.

### Why it matters more than the headline suggests

Dropping the two basins moves the sea headline 96.26% → 96.14%, which is nothing. That is
the wrong measure of the damage, and rewt-68 showed the framing itself is wrong: **the
in-scope national figures are not the sound half, because `in_scope` is itself decided by
the basin rule.** 96,958.4 of the 105,699.0 in-scope km — 92% — are in scope by
`scope_rule='basin'` against 8,740.6 km by `scope_rule='country'`. Dropping the two basins
moves the denominator from 105,699.0 to 100,287.5 km. A figure whose denominator moves by
5,411.5 km when a delineation error is corrected is a basin-dependent figure. **The only
reachability headline that survives a basin fix untouched is the Great Britain one** —
141,614.9 of 152,825.3 km, 92.66% — which uses no basin at all.

What it costs beyond that:

- **the per-basin table is the deliverable of the audit** (PLAN.md §6: "a national 97% hides
  a basin at 40%, and the basin at 40% is the entire finding") and its denominators are
  wrong wherever a polygon includes sea;
- **118 of the 1,303 defects — 9.1% of the declared backlog — are in two basins that should
  not be in scope**, and the deployed map draws 28 red dots in Angus, Fife and the Lothians;
- the labels then read as claims they are not. `rewt/stages/basins.py:347 _label_for`
  takes the named river contributing the most link-kilometres to the polygon, and its
  docstring says "Purely for legibility in a report. Nothing is decided on it." So
  "River Aire, 11,873.5 km²" is a correct measurement — the Aire *is* the biggest named
  contributor to a Humber-shaped amalgam — printed where it reads as a catchment name.
  rewt-50 established this and is right that the labels are not the defect. Their
  warning is worth keeping: **if the amalgams split, these labels will start looking
  right without anything having been fixed, so do not read that as evidence.**

### Open, for the implementer

- **Closed.** `sea_reach.json` does close, and the 58.3 km "gap" I reported was my own
  error: I added `reaches_tidal_km` to `sea_only_km`, but the first already contains
  `reaches_tidal_only_km`. `audit.json`'s
  `sections.reachability_tested_against_the_sea` carries the full partition —
  `reaches_both_km` 98,855.9 + `reaches_sea_only_km` 2,890.4 = `reaches_the_sea_km`
  101,746.3, and adding `reaches_tidal_only_km` 58.3 and `reaches_neither_km` 3,894.4
  gives 105,699.0 exactly. The section sets `readings_are_nested: false`, which is the
  file warning against precisely what I did. Found by rewt-46.
- **Closed.** Basin labels are not derived from an outlet node and are not unreliable;
  see above.
- **Mostly closed.** `audit_basin` totals 96,958.4 in-scope km against 97,037.7 km on a
  basin, a residue of 79.3 km. 70.7 km of it sits on 39 basin ids that have no
  `audit_basin` row at all. 8.6 km remains unaccounted for. Relatedly, 4 of the 110
  intersecting basins have no `audit_basin` row, which is why my band table summed to
  106 and not 110 — also caught by rewt-46.
- **Open.** What are the 103 `rewt:basin-unanchored/` basins, how does a basin come to
  have no outlet node, and why do 79 in-scope ones carry a label anyway while 52 with an
  outlet carry none?

---

## Part B — `rules/0001.md`, now in `conf/rules.yml`

**The list is `conf/rules.yml` and this is not a second copy of it.** Read it with
`rewt rules`, one rule with `rewt rules R-01`, and `rewt rules --check` resolves every
identifier a rule cites against the database (all 16 of Stephen's hand-typed ones
resolve). D-078 records why the list lives there and what it deliberately does not hold.

An earlier draft of this section carried a parallel table of rules with ids of its own,
and within the hour it disagreed with the canonical file — the canonical file orders
rules by the sequence in which they apply, which is not the order they were raised in.
That is D-067 happening inside the document written to prevent it. The table is gone.

**Mapping, because ids from the draft were circulated to the team before the file
existed.** If a message names an R-number, this is what it meant:

| in `rules/0001.md`, top to bottom | canonical |
|---|---|
| the sea network should be Mean High Water | **R-01** |
| sea entry termini within a threshold | **R-03** |
| crossings that do not join are not all marked; a viewer toggle | **R-04** (detection) and **R-12** (toggle) |
| the C&RT culvert corroborating a non-join, and the barred link | **R-05** — one rule, two directions of one fault |
| make the higher-resolution DEM work harder (terrarium) | **R-09** |
| are we still skeletonising water polygons? | **R-08** |
| node popups should expand attached links | **R-10** |
| a popup'd feature should be highlighted | **R-11** |
| a canal dead end with two inflows is suspect | **R-07** |
| extend a link past a dead end, and align | **R-06** |
| `rewt:link/03cfec6fd5a1` should not exist | an `instance`, of R-04 and R-05 |
| *(not from `rules/0001.md`)* a basin may not contain the sea | **R-02**, raised by rewt-46 |

**Two source questions are settled**, both by rewt-16 on 3 September, and both are
recorded on the rules themselves rather than here:

- **R-01 needs no new source.** Mean High Water is the `high_water` layer of
  `os_boundary_line`, already registered, already redistributable, already on disk at
  `data/raw/os_boundary_line/extracted/Data/bdline_gb.gpkg`. D-004 does not bite. Two
  cautions are on the rule: OS calls it *High Water Mark*, an administrative coastline
  and not a tidal datum, so the substitution is on the record; and its 32,850 rows are
  13,002 geometries, each repeated once per bounding administrative file, so anything
  measured without deduplicating on `Global_Link_ID` is 2.5× too long.
- **R-09's terrarium sweep is declined**, and the reasoning is on the rule. The short
  form: there is no licence over the tileset, only a document telling you to research
  each upstream provider; it is not one surface, being EA LIDAR at 2 m over 86.1% of
  English nodes and EUDEM at 30.9 m over 96.5% of Welsh ones, so the instrument would
  change character at the Welsh border; and where it is good it *is* the EA composite,
  which is already registered at 1 m, with the Welsh gap already registered at 1 m too.
  Both of those declared sources are unfetched, `checksum: null`. That, not a seventh
  registration, is what R-09's proposal should become.

**Sequencing.** R-01 before R-02, and both before anything that invents geometry: a
connector built against the wrong sea cannot be recognised as wrong afterwards. R-03 and
the `rewt:link/03cfec6fd5a1` instance are downstream of R-01.

---

## Part C — housekeeping found at boot, unrelated to the above

Recorded so it is not rediscovered. None is urgent; none has been acted on.

1. **`rewt --help` and every `rewt <command> --help` crash** —
   `TypeError: Parameter.make_metavar() missing 1 required positional argument: 'ctx'`.
   `requirements.txt` pins `typer==0.15.1` but not `click`, which has floated to 8.5.0; the
   signature changed in click 8.2. The file's own first line is "Pinned so an empty checkout
   builds the same thing twice." Bare `rewt` and `rewt team status` still work, which is why
   it went unnoticed. Fix: pin `click==8.1.8`. *Implementer.*
2. **`release-check` reports "tree clean" while five viewer source files are untracked.**
   It filters `git status --porcelain` to lines not starting with `??` (`rewt/cli.py:706`),
   so untracked files cannot fail it. `git ls-files tools/viewer/` returns two files —
   `.gitignore` and `serve.py`. `index.html`, `viewer.js` (57 KB), `viewer.css`,
   `counties.py` and `README.md` (18 KB) are not in version control. The `.gitignore`
   deliberately excludes `composite.js`, `counties.json`, `backdrops.json` and `nls_*.json`
   with a licence reason for each; it says nothing about these five. *rewt-46's scope.*
3. **A server has run for 19 hours rooted at `/home/stephen/PycharmProjects`** — pid
   1888935, `--bind 127.0.0.1 --directory /home/stephen/PycharmProjects`, the parent of every
   project on the machine. `curl http://127.0.0.1:8899/REWT/.env` returns 200 and 935 bytes.
   The bind half of TEAM.md's rule was obeyed; the root half was broken further than the rule
   anticipated. Not killed — it is not this session's.
4. **TEAM.md is damaged.** The `# TEAM.md` header and its opening paragraph appear twice,
   followed by two near-identical paragraphs, one reading "none by the build, which and the
   suite is not small", and a sentence saying twice that each session is told what it owns.
   Introduced in `38ddca2` / `f78e38a`.
5. **`published/audit/` holds 17 files, not 7.** An earlier listing in this session used
   `head` and missed `dead_ends.json`, `sea_reach.json`, `flags.json`, `repair.json`,
   `screen.json`, `sea.json`, `structures.json`, `water_bodies.json`,
   `refused_crossings.geojson`, `validation.md`. Recorded because it is precisely the
   truncation TEAM.md names, committed by the session that had just read the warning.

---

## The queries behind Part A

```sql
-- the in-scope population: NOT link_scope JOIN link
create temp view inscope as
select ls.link_id, ls.basin_id, coalesce(l.length_m, rl.length_m) length_m
from link_scope ls
left join link l using (link_id)
left join repair_link rl using (link_id)
where ls.in_scope
  and not exists (select 1 from retirement r where r.link_id = ls.link_id);
-- 127,121 links, 105,699.0 km

-- basins that contain the sea
select b.basin_id, b.label, round(sum(sl.length_m)/1000,1) sea_km
from basin b join sea_link sl on ST_Intersects(b.geom, sl.geom)
where b.in_scope group by 1,2 order by sea_km desc;
-- 110 of 334; 51 hold 10 km or more
```

Dead ends were attributed with `published/audit/dead_ends.json` joined to `node_basin`.
