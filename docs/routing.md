# Routing

**A cost surface for coastal navigation: where a vessel could go, on the water, between
the mouths of the rivers.** It is the sea half of a network whose other half is the
[modern drainage](methodology), and it exists so that *port to port* is computable — down
one river, along the coast, and up another.

**It makes no historical claim, and that is a rule rather than a caveat.** A hexagon in the
Irish Sea does not know what year it is. What has been built is geometry, depth, and what
can be seen from where; weights, seasons, hulls and dates are all
[deferred](epochs) to later stages. Nothing on this page requires knowing when.

Every figure below is printed from the router's own artefacts rather than typed here — the
files under `docs/router/data/` carry their method in their own properties, and this page
is generated from them.

## Sight of land decides the surface

**A cell is in the network only if land can be seen from it.** Not preferred, not
penalised — *included*. Water out of sight of land is not part of the surface at all, so
there is no third state to explain and no threshold anyone can tune: a route either keeps
land in view or it does not exist.

The range at which land drops below the horizon is `sqrt(2Rkh)`, which for the refraction
coefficient this uses is

**{{ site.data.routing.horizon.constant_km_per_sqrt_m }} × √(height in metres) kilometres**, with a refraction coefficient of
{{ site.data.routing.horizon.refraction_k }}.

**Not {{ site.data.routing.horizon.common_wrong_constant }}**, which is the figure most
readers will supply from memory and which corresponds to a refraction coefficient of
{{ site.data.routing.horizon.common_wrong_refraction_k }}. The difference is small and it is
systematic, which is the combination that survives a sanity check. The constant on this page
is read out of the layer's own formula string when the page is built, and checked against
`sqrt(2Rk)` for the coefficient it names, so the prose here cannot drift from the code that
drew the map — and if the two ever disagree, the build stops rather than publishing either.

**Every range here is a floor.** The observer is at
{{ site.data.routing.layer.observer_height_m }} m — an eye at sea level, the one height that
assumes nothing about a vessel. A lookout {{ site.data.routing.horizon.illustrative_eye_m }} m
up adds {{ site.data.routing.horizon.illustrative_eye_adds_km }} km to every one of them, and
a masthead more. That is an illustration and not a claim about any ship: choosing a real
height means choosing a real vessel, and a vessel implies a period.

**What each cell records is the tallest land that reaches it** — {{ site.data.routing.layer.gov_h_m_definition }}
So the surface is not a buffer round a coastline. A high headland projects sight much further
than the flat shore beside it, and the reach of a stretch of water is set by the highest thing
that can see it.

## What two voyages do and do not show

Two passages carry the calibration — **London to Skagen**, at the northern tip of Denmark,
and **Falmouth to Bordeaux** — each described as about a week's sailing in July, from
[eRutter](https://docuracy.github.io/Historical_Sea_Routing/){:target="_blank"}.

**Measured on a surface that permitted a stretch of blind sailing, the two came out 48%
apart. Measured on a surface where land must stay in sight, they agree to 6%.** The same two
routes, the same two durations, and a difference that is entirely a change in the geometry
they were measured over.

**That is consistent with the rule and is not evidence for it**, and the distinction is worth
keeping sharp because the stronger claim is the tempting one. eRutter says of itself that it
is approximate — better for comparing routes than for settling times — so these are not two
independent measurements converging. They are two soft figures, each "about a week", implying
similar distances. Two approximate durations agreeing tests very little. What has actually
been shown is that a constraint changes the geometry in the direction coastwise sailing would
predict, which is a reason to keep the constraint rather than a reason to believe it.

**And the week is an order of magnitude, not a threshold.** The surface is trimmed at roughly
a week's sailing of England and Wales — *roughly*, in the same breath as the trim, because a
rounded estimate of a voyage becomes a boundary condition the moment it is written without
that word. Nothing here computes duration:
{{ site.data.routing.reach.time_not_computed }}

**A week is also measured along the water.**
{{ site.data.routing.reach.not_a_radius }}

**And the two anchors still disagree, which is kept rather than averaged away.**
{{ site.data.routing.reach.anchors_disagree }}

## What is not published here, and why

**No percentage of "sea that can see land".** Such a figure moves with the extent of the
model, the resolution of its grid and the height of its observer, without anything about the
world changing — it is a property of the model rather than a measurement of the sea. It is
deliberately absent from the map's own panel for the same reason.

**No cell, join or trace counts.** The grid's banding changed recently and the joins depend on
work not yet landed, so those numbers are still moving. They live in the artefacts, where a
reader can fetch today's, rather than in a sentence that will be quoted back in a month.

**And nothing here is a route a vessel could follow.** The bathymetry beneath it is research
data published `{{ site.data.routing.layer.use_constraint }}` — a constraint on purpose, not on
redistribution. A topological surface is not navigation, and the naming of everything built on
it is chosen to keep that boundary rather than merely to acknowledge it.

## How it was checked

**{{ site.data.routing.layer.validated_against }}**

The distances are computed in {{ site.data.routing.layer.distance_crs }}, whose worst
projection error over this extent is {{ site.data.routing.layer.distance_crs_worst_error_pct }}%
— smaller than the {{ site.data.routing.layer.band_km }} km bands the surface is built in, so
it cannot move a cell from one band to another.

**Cells beyond sight are absent rather than shaded.** A thing that is not there is visibly not
there; a thing drawn in a colour meaning *unknown* looks like an answer. That is the same rule
the [audit](methodology) works to — an unknown must fail towards the visible fault.

**So what is the edge of the surface?** A boundary drawn on a map asserts that something
changes there, and it is worth being exact about what changes at this one. The layer says so
about itself: *{{ site.data.routing.layer.buffer_basis }}*

**No blind sailing at all, then** — the edge is the limit of sight and nothing else, and a
landmass enters the network only where its sighted water touches sighted water already in it,
because two blind zones meeting is not a route. The consequence is concrete and worth stating
because it is the kind a reader would otherwise assume away: **Land's End to Cork is not in
this surface.** A crossing that goes 56 km out of sight of land is not a passage this network
can make, whoever in fact made it.

## Looking at it

**[The sightline surface on the map]({{ '/viewer/#5.5/54.5/-4&l=sightline' | relative_url }}){:target="_blank" rel="noopener"}** — that
link opens the viewer on this layer alone, with the river network and every other overlay
switched off, because the default view does not illustrate anything on this page.

The map draws the same file this page is generated from, so a figure quoted here and a cell
clicked there cannot disagree. What the map adds is the thing prose is worst at: the *shape*
of the surface — where sight reaches far out and where it clings to the shore — which is one
picture and several paragraphs.

---

*{{ site.data.routing.layer.attribution }}*

*Generated from `{{ site.data.routing.generated_from }}` by `{{ site.data.routing.generator }}`.
To correct a figure, correct the artefact and regenerate — an edit to this page is overwritten
at the next build.*

---

| | |
|---|---|
| [Methodology](methodology) | how the river network is made traversable, and why the sea is a test rather than a definition |
| [The rules](rules) | every general rule the build works to, in the order they apply |
| [Evidence](evidence) | what each source can and cannot say, and on what terms |
