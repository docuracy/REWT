# The viewer

    .venv/bin/python tools/viewer/server.py     # then open http://127.0.0.1:8010/

A local map of the network as currently assembled, for looking at the place behind a
number. Run from the repository root.

> **THE SERVER IS `server.py`, NOT `serve.py`, AND THE TWO ARE DIFFERENT PROGRAMS.**
> `server.py` is this viewer's own: it serves `published/` through nine `/api/*`
> endpoints on port 8010 and composites the county sheets. `serve.py` is a
> Range-honouring static server for `docs/` on port 8021, which is what the
> DEPLOYED viewer needs and has nothing to do with this one.
>
> For most of 2–3 September this tool could not be run at all: `viewer.js` asked
> for those nine endpoints and nothing in the repository served them. The server
> had been spun up ad hoc, used, and lost before it reached the index —
> `git log --diff-filter=D` over this directory is empty, so it was never even
> deleted. It is in version control now, on Stephen's ruling that it should be.

## Why it exists

`AGENTS.md` says three things that between them describe this tool:

> Looking beats measuring. When you have fixed something, go and look at the place on
> a map. Aggregates have repeatedly agreed that a broken thing was fixed.

> Report at the place, not only in the total... Every serious defect in the
> predecessor was invisible in national figures.

> A national 97% hides a basin at 40%, and the basin at 40% is the entire finding.

Everything the build publishes is a national total or a 200-row table. This serves the
geography behind them. Every list in the panel is sorted worst-first and flies the map
to the place.

## It reads `published/`, never the database

`AGENTS.md` warns that a read-only DuckDB connection blocks writers and names a served
map as exactly the long-running thing that holds one. This reads
`published/rewt_stage1_network.gpkg`, which is a file: it takes no lock, cannot block
a build, and is what a consumer of this project actually gets. **You never have to
stop this server before a build.**

It writes nothing — not to the database, not to `published/`, not to `data/`.

## What it draws

The network per viewport, coloured by whether it reaches tidal water (or by form, by
whose geometry it is, or by why it is in scope), over a keyless OpenStreetMap raster.
On top of it, every small layer served whole:

| layer | what it answers |
|---|---|
| dead ends that are the work | where water arrives and stops, sized by the length draining in |
| dead ends at tidal water | the same thing working correctly, for comparison |
| every curated judgement | what this project decided, with its `reason` and `evidence` on click |
| connectors, reversals, retired | the audit trail, entire |
| basins by share reaching the sea | the basin at 40% a national figure hides |
| the audit's own findings | the 183 in `audit.json`, click to fly |
| seeds, tidal termini | where the crawl starts and where it may end |

Reversals and the whole network can be drawn with **flow arrows**. A reversal moves no
geometry, so without them the most error-prone correction in the build is invisible.

## Two things it will not let you misread

**The thinning in force is always stated.** Below zoom 8 the map draws every link of
5,000 m and over nationally; the ladder is in `backdrops.json`. The panel says which
threshold is in force and how many links it drew of how many were there, because a
channel missing from the picture must never read as "no river here".

**Four classes are never thinned, at any zoom** — the unreached, the retired, geometry
this project added, and anything whose routing was reversed. Those are the reason to
be looking, and a defect must never be readable as "fixed" because it was too short to
draw.

## It checks itself against the audit before it serves anything

`/api/summary.json` carries a `warnings` array and the panel prints it. The one that
fires today: the audit counts **474** dead ends at tidal water and this server derives
**393** from the published network, because `node.basin_in_scope` is the only half of
the scope rule the GeoPackage carries. The layer draws the 393 it counts, and the
disagreement is on the page rather than resolved silently — a mark count that describes
a different set from the marks is the failure to avoid.

Every other count was checked against `published/audit/audit.json` and against the layer
it labels: 1,303 dead ends drawn under a count of 1,303, and the same for corrections,
seeds, tidal termini, sea routes, sea entries, connectors, reversals, retired and
findings.

> **WHAT THE REBUILT SERVER DOES NOT DO.** The paragraphs below this line describe the
> server as it was before it was lost, and two of its habits were not reconstructed
> because nothing recorded how they worked: it does **not** print a boot-time comparison
> of every recomputed dead end against the fifty in `audit.json`, and it does **not**
> probe each keyed backdrop from its own origin at boot to report what will draw. Both
> are worth having and neither is here. Said plainly rather than left to be discovered,
> because a README describing a program that does not exist is exactly what cost a day
> on 3 September.

## Backdrops and keys

**No key is needed.** OpenStreetMap raster is keyless, is the default, and is enough
for every view here. Nothing in this directory may contain a credential.

A backdrop that needs one is **not offered unless the key is present** — the
alternative is offering it, having the tile 403, and MapLibre drawing nothing at all in
silence, which cost the predecessor a day. Keys come from `CARTO_API_KEY` /
`MAPTILER_API_KEY` in the environment, or from `tools/viewer/keys.local.json`, which is
gitignored and must stay that way. The server probes each keyed backdrop from its own
origin at boot and tells you what will and will not draw.

## Attribution is a licence condition, not decoration

Every view carries *Contains OS data © Crown Copyright and database rights 2026* and
points at `published/ATTRIBUTION.md`, which is generated from `conf/sources.yml`. A
short attribution may never attribute less than that file does.

## In the browser console

`window.map` is the MapLibre map and `window.rewt.summary` is the figures payload, so
`map.flyTo({center: [lng, lat], zoom: 16})` gets you to a place somebody read out.

## Checking the DEPLOYED viewer without a browser window

    /usr/bin/python3 tools/viewer/shot.py --serve      # every check, own server
    /usr/bin/python3 tools/viewer/shot.py --prove-it-fails

`tools/viewer/shot.py` drives `docs/viewer/` headlessly through Playwright. **System
python**, not the project venv: playwright is installed for `/usr/bin/python3` and is
deliberately not a project dependency. It checks the panel's figures against
`published/audit/audit.json`, that every overlay draws, the popup at Stephen's
Berkhamsted node, and the sightline layer's three states — each with a control in the
same run, because an absence is only evidence when the same call found a presence.

**Run `--prove-it-fails` before believing a pass.** It points every check at a page with
no map and requires each to fail. A green run can otherwise mean the subject never
rendered at all.

Three things it took three attempts to get right, recorded so the next person skips them:

- **Software GL is not optional.** Headless chromium has no GPU, so a WebGL map never
  resolves its sources, `map.loaded()` stays false and `idle` never fires — every run
  then times out on a working page and a broken one alike.
- **Wait on `window.rewt.ready`, not on `load`.** `map.on('load')` fires when the STYLE
  loads, long before the sources, the tiles or the page's own fetches. The same applies
  to a hidden tab in a real browser, where `load` never fires at all: `isStyleLoaded()`
  true with `loaded()` false is that signature, and the harness reports it by name.
- **Assert the synthetic click LANDED.** `project()` before the camera settles returns a
  point for the old view, the click hits open water, and a check of the form "the ray is
  absent for a cell without a landmark" then passes for the wrong reason. The first
  version of the sightline check did exactly that.

It found a real defect on its first honest run: the sightline ray was drawn during
`describe()`, before the popup was shown, and showing the popup fires `close` on the
reused instance — which clears the ray. So it worked on the first sightline click of a
session and silently not afterwards. Hand-testing never caught it because a hand test
starts with no popup open.

## Stage 1 only

Nothing here knows what year it is. There are no dates, no old courses, no attestation
and no flow — a historic backdrop is deliberately not offered, because Stage 1 makes
no historical claim and a map is the easiest place to imply one by accident.

## Two counts on one screen that do not add up, and why

**The basin list does not account for every dead end.** A dead end is in scope because
its *arriving link* is, which is `audit.py`'s own definition, not because its node sits
in an in-scope basin. Tidal water is masked out of the DEM, so an estuarine node
belongs to no catchment — and those are exactly the ones where the answer matters. The
panel states the difference, computed from the file rather than written down: it moved
from 329 to 353 while this paragraph was being written.

**No share is ever rounded up to 100%.** The Tweed is 99.84% with 5.3 km stranded and
printed as `100%`, which was read as a completed basin. Shares floor at 99.9%; only an
exact 1.0 prints 100%.

## Historic backdrops

Stage 1 makes no historical claim, and a modern network drawn over an 1890s sheet is the
easiest place in this whole project to imply one by accident. So the backdrops are here
to read the ground against, and **the panel says so in as many words whenever one is
showing**. That notice is the condition on which they are allowed to be here.

| backdrop | key | coverage |
|---|---|---|
| OS Six-Inch, 2nd ed. 1888–1913 — seamless | **none** | England and Wales, z6–z17 |
| OS One-Inch, revised — seamless | **none** | England and Wales, z6–z16 |
| OS Six-Inch, 1st ed. 1840s–1880s — seamless | **none** | 52 historic counties, z9–z17 |
| OS Six-Inch, 1st ed. — one county, unmasked | **none** | one county at a time |
| OS One-Inch Old Series | **none** | England and Wales, **z6–z9 only** |
| Pre-Ordnance county surveys, 1771–1831 | **none** | 11 northern and midland counties, z11–z14 |
| OS Six-Inch, 2nd ed. — via MapTiler | maptiler | will 403 on localhost; see below |

**None of the historic backdrops needs a key.** They come from the National Library of
Scotland's own tile host, `mapseries-tilesets.s3.amazonaws.com`, which serves them free
for non-commercial and research use with attribution and a link. The MapTiler entry is
kept only so the boot probe reports the state of the key: MapTiler's free plan allows one
active key, and this project's is bound to `docuracy.github.io`, so it 403s here. The
probe says so at boot rather than letting MapLibre draw nothing in silence.

### The first edition is not seamless, so this server makes it so

The NLS publishes the first edition **county by county**, and the mosaics are not cut at
the county line — each bleeds over its neighbours, so stacking them puts two different
surveys of the same ground on top of each other with the join wherever the draw order
happens to fall. MapLibre cannot clip a raster to a polygon: there is no such property in
v4, and v5's `clip` layer occludes 3D content rather than cutting rasters.

So `/backdrop/six-inch-first/{z}/{x}/{y}.png` composites the tile here — every county
covering it, each masked to its own Historic Counties Standard polygon — and the browser
asks for one seamless layer. Source tiles and finished tiles are cached under
`tools/viewer/cache/`, which is gitignored. The first pan over new ground is slow; after
that it is a file read. Nothing below zoom 9, where a composite would fetch hundreds of
county tiles for a picture nobody can read.

A pixel is taken only where the county **owns the ground** and its own sheet **has
something to say there**. Both conditions matter: the first stops a mosaic bleeding past
its boundary, the second keeps its internal margins transparent instead of painting them
over a neighbour.

### Counties are named by the Historic Counties Standard

`NAME` and the three-letter `HCS_CODE` — `BED`, `YRK`, `CMB` — are this project's county
vocabulary, never the NLS's tileset filename, which is a filename and differs from the
Standard in three places (`devonshire`/Devon, `caernarvonshire`/Caernarfonshire, and an
Isle of Man mosaic for a county the Standard excludes, the UK not including the Island).

**IOM is carried so that a reference to it resolves, and is out of scope.** REWT is
England and Wales. It has no polygon in the Standard and needs none — it is an island, no
other county's sheets reach it — so it is masked by its own transparency alone, is
excluded from the seamless composite, and remains selectable one county at a time where
the choice is explicit. The picker labels it, and every unmasked or out-of-scope county,
as such.

### The polygons are a declared source

`tools/viewer/sources.json` declares the Historic County Borders Project's UK Definition A
with its licence, its checksum and the attribution it asks for, because AGENTS.md's rule
that an unregistered source is a hard error does not stop at the build's edge.
`conf/sources.yml` remains the authority for anything the build reads, and a short
attribution may never attribute less than it does.

Acquire the polygons with:

    .venv/bin/python tools/viewer/server.py --fetch-counties

They are free for personal, educational, non-commercial **and commercial** use, no
permission required, acknowledgement requested — which is why they can be used in a
repository intended to become public. Every view carries that acknowledgement.


## The catalogue: what is in the bucket, discovered rather than assumed

`tools/nls_layers.json` is a machine walk of the National Library of Scotland's public
tile bucket — every tileset, its zoom range, and its extent, all **observed** from the
keys the Library actually serves rather than taken from a description. `ListBucket` is
public, which is what makes this possible. Each entry carries `england_wales_share`, the
fraction of the layer's own extent inside England and Wales, which is what separates the
Scottish-only sets (`os/6inchfirst`, `os/one-inch-first-bart38`, `os/1inch_1st-bart38` —
all of which draw nothing here) from the ones that serve this project.

**The catalogue carries no dates, and that is deliberate.** The bucket does not hold
them. A tileset named `os/one-inch-old-series-all` invites the label "1805–1874", and
that label would come from the author's knowledge of the series rather than from
anything NLS said about this tileset. Dates therefore live only on the hand-written
entries in `backdrops.json`, where they are a claim someone can be held to, and never in
the generated catalogue, where they would look like a discovery. This trap has already
caught this project once: the six-inch second edition was labelled "1888–1913" from
MapTiler's naming of a different product.

The catalogue is shared with `tools/tracer/`, which makes its own curation of it.
`backdrops.json` is *this viewer's* curation — which subset it offers, in what order,
at what opacity, with which warnings.

## Can a canvas read a backdrop's pixels?

The boot probe answers this per layer, because a tool that snaps a traced line to
printed ink has to read pixels back, and a canvas that has drawn a tile from a host
without `Access-Control-Allow-Origin` is tainted — `getImageData` throws.

**Check it with GET, never HEAD.** S3 attaches the header to GET and OPTIONS and not to
HEAD, so `curl -I` reports no CORS on a host that has it, and the failure reads as a
fault in the wrong component. That mistake was made here and corrected; the probe exists
so it is not made again.

## Why this tool checks itself against the audit

It recomputes the dead ends and sums the published link layer per basin, and compares
both with `published/audit/audit.json` at every boot. That is not defensive
housekeeping: **an outside reader summing the published file must reach the project's
own number, or one of the two is lying about the same rivers.**

It has earned its place once already. A 0.2% per-basin difference — 15 basins of 200,
worst 14.9 km on a 6,917 km basin — was small enough to look like a property of the data
and consistent enough to look deliberate. It was neither. The audit attributed a link to
a basin by its *oriented* downstream node; the GeoPackage's `basin_id` used the
*digitised* one, and for a reversed link those are opposite ends. 64 links and 94.3 km
sat in different basins in the two files, 56 of them reversed.

The shape is worth remembering: **too small to notice, too consistent to look like
noise.** Two explanations were offered and both were comfortable — that it was retired
links, and that it was two figures legitimately computed differently. Accepting either
would have left it in place.

## Reading a file a build is writing

`published/` is rewritten by one `export` stage, several times an hour while the build
session is working, and `provenance.json` is written in the same stage. So the boot
check reads provenance, does its work, reads provenance again, and discards the whole
load if the fingerprint moved.

Without that it will compare a half-written GeoPackage against an audit from a different
build and report the difference as a finding — which it did, and cost another session an
investigation into a number that was about timing rather than data. The staleness banner
cannot help here: it tells a reader the file changed, which is no use to a check that has
already run.

## The view is in the URL

Every view has a link. The hash carries where you are, how close, which backdrop and
which sheet under it, how strongly, what the network is coloured by, which overlays are
on, and the findings filter:

    #17.00/50.99935/-2.57745&b=nls_25_inch&i=somerset&o=100&t=form&l=connectors,corrections

`#zoom/lat/lon` leads because that is the convention every other slippy map uses and a
person can edit it by hand. Written with `replaceState`, not `pushState`: panning is not
navigation, and three hundred intermediate viewports make the back button useless for
leaving. **Copy a link to this view** in the footer is only a convenience — the address
bar already holds it.

Three things it took a working round trip to get right, each of which would have shipped
a link that looked fine and was not:

- **The opening style never carries a collection.** A collection's tile URL holds an
  `{item}` placeholder only `applyBackdrop` can fill, and that cannot run before the map
  loads. Putting one in the initial style produced `.../25_inch//{z}/…`, MapLibre
  rejected the style, **`load` never fired and nothing initialised** — no network layer,
  no restore, and no error a reader would connect to the cause. A link naming a county
  sheet did exactly this.
- **Nothing writes the hash until the hash has been read and applied.** `moveend` fires
  during the restore, and a write from it replaced the link the reader had just opened
  with the half-restored state. A link that destroys itself on opening is worse than no
  link.
- **One layer's failure must not silence the rest.** An `await` that rejects inside the
  restore loop abandons every layer after it, and the reader gets a link that restored
  half of what it named with nothing said about the other half.

A backdrop named in a link that this reader cannot have — a keyed one, or one since
removed — falls back rather than failing, because a shared link should still land you in
the right place with the wrong sheet.

## Two palettes, and when they may meet

The network is a **surface** coloured by a theme; the overlays are **marks** drawn on
it. The first version gave three overlays the same hue as a form category — connectors
were canal-yellow, reversals lake-teal, retired tidal-violet — so the legend and the
layer list showed one colour against two meanings, and a reader had no way to tell which
they were looking at. That is the map asserting a relationship that does not exist.

The rule now:

> **An overlay shares a theme's colour only where it means the same thing, and must
> differ everywhere else.**

Three overlaps are therefore deliberate and are kept: connectors *are* the form theme's
"added by this project"; the dead-end layer *is* the network's "does not reach tidal
water"; tidal termini *are* its tidal water. The legend says so where it is not obvious.
Everything else is separated. Theme colours are a cool family, because every one of them
is water the survey drew; overlay colours are warm or bright, because none of them is.

Three supporting decisions, each of which was a real fault first:

- **Overlay lines carry a dark casing.** Colour alone cannot say "on top": the network
  is drawn in whatever the current theme says, and a reader switching themes should not
  have to relearn which lines are the survey's and which are this project's marks on it.
- **A layer coloured by its data gets a band of the colours it actually uses**, pulled
  out of its own paint expression, with them listed in the tooltip. Showing white for
  such a layer made judgements, findings, refused crossings and seeds carry the same
  blank swatch — which reads as a key and is not one.
- **The whole network's flow arrows are neutral; only the reversals' are green.** They
  had shared one sprite, so turning on flow direction painted the entire network in the
  colour that means *this one was reversed*.

A check worth re-running after any palette change: collect every swatch in the legend
and the layer list, and assert that no two entries share a colour unless the overlap is
one of the three above.
