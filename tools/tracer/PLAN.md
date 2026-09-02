# The Tracer — a plan

A single-page application, served from GitHub Pages, in which invited contributors trace
old watercourses off historic Ordnance Survey sheets. Every edit is appended to a JSONL
log committed to this repository as it is made, or held locally and flushed when the
network returns.

Written by rewt-2b ("Tracer"), 1 Sep 2026. **This is a plan, not an implementation.**
Section 10 lists the four decisions that must be taken before any of it is built, two of
which are not mine to take.

---

## 1. What this is, and the one thing it is not

`docs/scale.md` divides the work into what can be finished in house and what cannot, and
the second column is the larger one:

| strand | places | who |
|---|---:|---|
| *Old Course* / *New Cut* traces | ~274 | in house, ~6 days |
| reservoir valleys | 165 impounding reservoirs inventoried (England and Wales); 316 more on the Welsh register | in house or volunteers, months |
| mill channels | 4,068 | volunteers, or publish undated |

**This tool exists for the third row.** The first two are a few weeks of work for one
person and would not justify building anything; the third is an order of magnitude larger
than everything above it and has no route to completion that does not involve many hands.
The tool is the machinery for distributing it. That it also makes the first two rows
faster is a by-product.

**It is Stage 2 and later, and it says so.** Stage 1 is a repaired modern network making
no historical claim at all, and `CLAUDE.md`'s rule — *if a task requires knowing what year
it is, it is not Stage 1* — is exactly what this tool requires. It touches no part of the
Stage 1 build: it does not read `db/rewt.ddb`, it writes nothing into `rewt/`, `conf/`,
`data/curated/` or `published/`, and it cannot block a build. Nothing in this plan needs
to happen before the first edition ships, and none of it should.

**What it is not.** It is not a general-purpose editor of the network, and it must not
become one. A contributor draws a channel that a sheet shows and says what it replaces;
they do not move, delete or re-attribute anything in the modern network. Corrections to
the modern network are a different tool with a different failure mode — `docs/scale.md`
names it separately, and conflating the two would put a volunteer's mouse on Stage 1's
output.

---

## 2. The licence position, stated plainly

The standing instruction is that **gating the tool to authorised users for research
purposes may be assumed to satisfy the licensing requirements on distribution and
publication of the maps and the derived data.** The plan proceeds on that basis. What
follows is what that assumption does and does not reach, because a gate that is believed
to do more than it does is worse than no gate.

**D-037 is the entry this crosses.** It records the NLS position on the tilesets:
`redistribution: not_established` — NLS publish a per-layer re-use table listing **29 of 34
layers as CC-BY, and the England-and-Wales six-inch and one-inch are not on it**, with no
term stated anywhere else, which is precisely the sheets a tracing tool for England and
Wales needs — their stated condition that re-use is *"intended within
a desktop or local environment"* with public websites directed to the Historic Maps API or
to contacting them — and the finding that **the Historic Maps API carries no first-edition
six-inch at all**, which is the layer two in five reservoir valleys need. `AGENTS.md`
forbids silently reversing a recorded decision. So this requires **a new, dated DECISIONS
entry written by rewt-d3**, saying in as many words that a gated research tool is being
treated as inside the condition, and naming the assumption as an assumption. It should not
be inferred from the existence of the code.

**What the gate actually controls, and what it does not:**

- **It does control who uses the tool** — and therefore whose browser fetches sheets from
  the NLS host at all.
- **It does control where the traces go.** Contributed geometry is derived from those
  sheets, so it is written to a branch of this private repository and read back through
  the authenticated GitHub API. **It never touches `docs/`.** See §3 for why that
  distinction is not cosmetic.
- **It does not control access to the sheets themselves.** The NLS S3 host is keyless and
  public; anyone who wants those tiles can have them without going through us. Our gate is
  on the tool, not on the tiles, and no design can make it otherwise.
- **It does not make the interface private.** GitHub Pages serves `docs/` publicly even
  from a private repository — verified in the scoping exercise: an anonymous request for
  `docs/data/` returns 200 while the same request against the repository returns 404.
  Private Pages is an Enterprise feature and is not available here. The app shell is
  therefore public and **inert**: it renders a sign-in wall and requests no historic tile
  and no project data until a token has been validated.

**The recommendation that goes with the assumption:** write to NLS, name the gate, and
ask. rewt-86 has already recommended it to Stephen and will draft it — writing to a third
party on his behalf is his to do, not an agent's — and would fold three questions into one
letter: the England-and-Wales six-inch and one-inch layers, the County Series dates page
(terms unstated and *already in public use*, which makes it the most pressing), and the
sheet register behind the maps viewer. The answer changes what the tool may offer, not
whether it works.

**The maps and the derived data are two questions, and the derived data is on much firmer
ground.** This is rewt-86's argument and it is the most useful thing anyone has said about
the licence position. The six-inch first edition was surveyed in the 1840s–90s and **the
underlying Ordnance Survey mapping is out of Crown copyright**. What NLS holds is over
their *scans and georeferencing*, not over the survey. A line a contributor draws after
looking at a scan is a new record **about the ground** — not a reproduction of the scan.
That is the same principle that unblocked the Satchell deposit: the finding travels, the
file does not.

**So the rule the tool is built to, whatever NLS answer: log the trace and the sheet
citation, never the tile.** No tile bytes are stored, cached to the repository, committed,
or redistributed by anything in this plan — see §4, where it changes a design choice.

**Both questions are settled and recorded as D-043**, from Stephen directly rather than
through a relay: *"Nothing in the NLS documentation suggests restrictions on derivatives
like this. Assume that they are freely allowed"*, and *"My instruction stands: gating
satisfies all of the limitations."* The entry records them **as readings rather than
findings**, per D-025's treatment, attributed and dated, and carries the three caveats
below unchanged — because none of them is altered by the ruling.

**AND THE REPOSITORY IS NOW PUBLIC, WHICH RETIRES THE GATE THIS PLAN WAS BUILT AROUND.**
1 Sep 2026: Zenodo will not mint a DOI for a private repository — verified, not taken from
the notice — so a release meant public or no release. Stephen overrode his own earlier
ruling that traces stay private until published, knowingly and naming the reversal.

Three consequences, and the first two are improvements:

* **The token ask narrows from `repo` to `public_repo`** — read and write to public
  repositories only, and no access to any private repository of the contributor's or of
  ours. While the repository was private nothing narrower could reach it. That is the whole
  of the PAT problem this plan spent a section on, resolved by a decision taken for an
  unrelated reason.
* **The gate is now on the tool and on nothing else.** It never restricted the sheets, which
  NLS serve keyless; it now does not restrict the traces either. What remains is that a
  contributor must be a collaborator to write, which is access control and not concealment.
* **The moment of contribution is the moment of publication**, and that is a real cost. The
  earlier ruling rested on rewt-6a's asymmetry — private to public is one click, public to
  private is impossible — which was correct and is now spent. Working notes, withdrawn
  traces and a contributor's false starts are world-readable as they are committed. **The
  sign-in says so before it is true rather than after**, which is the only remedy available.

**Is a traced line a derivative of the tile? Settled: no — traces are open output.**
rewt-d3, rewt-6a and rewt-1d each reached this question independently on the day the plan
was written, because D-037 permits *citing what a sheet shows* and is silent on *tracing
geometry from it*, having been written before anyone proposed tracing. **Stephen's ruling,
1 Sep 2026, is the permissive reading**: a traced line is a new record about the ground,
the survey beneath it is out of Crown copyright, and contributed geometry therefore reaches
`data/curated/` and publishes openly. Phase 6 exists.

**It is a ruling on a reading, and the plan is built so it can be revisited.** rewt-6a put
the asymmetry precisely: if the permissive reading is right and we built the cautious tool,
we lose some geometry; if the cautious reading is right and we built the permissive one,
the repository cannot go public without unpicking every contribution. So the log keeps
every trace's sheet citation and provenance as first-class fields rather than derived ones
(§6), which means the cautious product — evidence without geometry — remains extractable
from the same log without re-contacting a single contributor. That is the whole mitigation
and it costs nothing to keep.

**One question stays open and is nobody here's to answer.** Whether systematic tracing at
scale engages database right in NLS's *georeferencing* is a separate matter from copyright
in the survey. rewt-86 raises it and declines to answer it, correctly. It is the strongest
reason to send the letter rather than reason further.

**Two rules inherited unchanged, because each cost someone a day:**

- **No URL written into a contributed record may carry a credential.** These files are
  committed; tile templates arrive with keys already substituted in; a key in a repository
  intended to become public is unrecoverable. Cite the published sheet URL. Refuse loudly
  rather than sanitise quietly — a caller passing a keyed URL has made a mistake worth
  seeing.
- **Coordinates are CRS84 and must say so.** A course whose CRS is unstated is a course
  whose numbers mean nothing, and assuming WGS 84 because they look like degrees is how a
  dataset acquires a silent offset. `conformsTo` is required, not defaulted.

---

## 3. Architecture

There is no server. Everything is a static file plus the GitHub API.

```
docs/trace/                      PUBLIC — served by Pages to anyone
  index.html                     the shell: inert until signed in
  js/                            modules (§7)
  data/
    base_network.pmtiles         OS Open Rivers derived — OGL, openly publishable
    tasks.json                   the work queue, GB1900-derived — CC0
    backdrops.json               copied from tools/viewer/ at deploy (§4)

branch `traces`                  PRIVATE — reached only with a token
  traces/<login>/<batch>.jsonl   the edit log, one file per contributor per batch
```

**The split is the whole design.** Openly licensed inputs are public because they may be,
and because a public file is fetched by the ordinary HTTP cache instead of re-downloaded
and re-authenticated on every page load. Everything derived from a sheet whose re-use is
not established is private, and GitHub — not JavaScript — performs the access control,
against real collaborator status. A token check in JavaScript over files sitting in
`docs/` would gate the interface and not the data, which looks like protection while the
files sit at guessable URLs.

**No sheet tile is ever committed, to either side of that line.** `docs/` is world-readable,
so a mosaic of NLS tiles committed there is republication of NLS's tiles by any reading —
which is the thing the whole licence position is trying not to do. rewt-1d caught this in
the first version of this plan, where §4 proposed pre-baking a first-edition composite; it
is corrected there. Tiles are fetched from NLS at use, read, and discarded.

**The traces branch, not `main`.** Pages rebuilds on a push to `main` under `docs/**`. A
contributor saving every few minutes would fire a site rebuild each time, queue them
serially, and bury `main`'s history under thousands of commits. A dedicated branch costs
nothing and avoids both.

### Tokens: what works, and what it costs the contributor

**`docuracy` is a user account, not an organisation** — confirmed from the repository's
owner node id. That single fact settles the token design, and it is the thing most likely
to be got wrong twice:

- **Fine-grained tokens (`github_pat_…`) cannot reach this repository at all.** They only
  ever reach repositories the token's own account owns. A collaborator's fine-grained
  token is not under-scoped; it is inapplicable.
- **GitHub answers 404, not 403, for a private repository a token cannot see.** So a
  wrong-kind token looks exactly like a missing file or a missing branch. Two people lost
  an afternoon to that in the London Customs Accounts editors. **The sign-in must detect
  `^github_pat_` and say so in words**, rather than reporting a 404.
- **The only token that works is a classic token with the `repo` scope.** That scope is
  broad: it grants read and write across every repository the contributor can reach. The
  risk is theirs rather than ours, but we are the ones asking, so the sign-in dialogue must
  say plainly what is being asked for and why nothing narrower is available.

**Two upgrade paths, both better, neither required to ship:**

1. **Move the contribution repository under an organisation.** An organisation owner can
   approve fine-grained tokens scoped to one repository with `Contents: write` and nothing
   else. This is the correct end state and is a repository-administration change, not a
   code change.
2. **A GitHub App with the device flow.** A public client needs no secret and therefore
   no server; the contributor authorises once, and the token is short-lived and scoped to
   the installation. Best security and best experience, most work, and it can replace the
   PAT path without touching anything else in this plan.

**"Authorised by us" means added as a collaborator.** GitHub is the gate. An allow-list
file in the repository is still worth having — but for assigning work and attributing it,
not for security, and it must not be described as security.

---

## 4. The four flows

### In: the base network

The tracer needs the modern network under the cursor — to bind a trace to the link it
replaces, and to show what has already been covered. `published/` is gitignored and
`*.pmtiles` and `*.gpkg` with it.

**My first answer was to ask for a `.gitignore` exception, and rewt-1d was right to refuse
it.** `.gitignore` opens with the repository's own rule — *nothing acquired, derived or
built is committed; inputs are declared and fetched; outputs are reproducible from them* —
and PMTiles built from OS Open Rivers are a derived build artefact by any reading. The
objection is not tidiness: **a committed artefact silently stops matching the inputs it was
built from, and nobody notices, because it looks like data.** That is a failure mode this
project has already been bitten by, and it would land on the one screen where a contributor
is binding a historical claim to a line.

**So the tiles are built at deploy and never committed.** rewt-d3 adds the export as a flag
on the existing exporter rather than a separate stage, so it cannot drift from the
GeoPackage: `link` and `node` vector tiles carrying `link_id` and `node_id` through to the
tile. The Pages workflow fetches the current published network and unpacks it as part of the
deploy, so the served site has it and the repository does not.

**As built, it lands in `docs/viewer/data/` and the tracer reads it from there.** This
section said `docs/trace/data/`, and the plan was the thing that was wrong: the viewer's
archive already carries a `link` layer with `link_id`, and a second copy of a 318 MB build
under a different path would be two artefacts that can disagree — the failure this whole
arrangement exists to avoid, reintroduced for the sake of a tidier URL. Verified on the
deployed site rather than assumed: `viewer/data/rewt.pmtiles` answers a Range request with
206, and its metadata declares `link` at z5–14 carrying `link_id`, `basin_id`, `name`,
`form`, `parent_link_id` and `superseded_by`.

**So this dependency is met, and phase 6 is not blocked on it.** Two things it does not
settle. The link layer stops at z14 while tracing happens at the sheet's native zoom, so
the geometry drawn under the cursor is generalised and only the identifiers are exact —
adequate for binding, and to be measured rather than assumed for anything else. And the
fingerprint comparison is now partly in `pages.yml` — rewt-d3 landed it at `767def5`,
comparing the release's `provenance.json` against the unpacked `summary.json` and failing
the deploy on a mismatch.

**That check is worth having and it is not the one the rule below asks for, so it should
not be recorded as satisfying it.** Both halves it compares come out of the same build, so
on a D-049-style change they agree with each other and are wrong together; what it catches
is a *mispackaged* asset, the tar ninety minutes older than the tiles that rewt-6a found.
Nor would comparing against the checked-out tree help: `config_fingerprint` digests
`conf/`, which advances past every release by design, and the export stage's fingerprint
covers the transitive closure of its imports, which does the same. Either would fail
routine deploys, and a check that is routinely overridden is worse than none.

**The leg that is narrow enough to compare against the tree is the identifier scheme, and
it is mine.** `gen_ids.py` generates `ids.js` from `rewt/ids.py` and `check_ids.py`
asserts parity, so the tracer already fails if its identifier code drifts from the
exporter's. What is missing is whether the identifiers in the *deployed archive* match
that scheme — one assertion over a tile fetched from the live site, indifferent to what
`conf/` did, and firing on exactly the event that should fire it. It belongs with
bind-to-link, because that is when a trace first takes an identifier out of those tiles;
written before then it would be a check with no consumer. History stays small, the rule stays intact, and the tiles cannot drift from the
network they claim to draw.

**A release asset is the vehicle, and rewt-d3 has agreed it.** A full Stage 1 build in an
Action is not viable — Terrain 50 alone settles that — so the workflow fetches the
*published* network rather than rebuilding it: versioned, fingerprinted, outside git
history, and already the thing a consumer of this project gets. If it ever turns out not to
work, the fallback is a committed archive with a fingerprint beside it and the drift risk
accepted explicitly rather than by default.

**And the fingerprint is compared, not merely recorded.** rewt-d3's `rewt sources --verify`
digests what the repository holds and fails if `status:` disagrees **in either direction**,
and CI must do the same to the fetched asset. A recorded fingerprint that nothing checks is
the `status:` field nothing wrote — and it is the same failure as the committed artefact
this whole arrangement exists to avoid, arriving one layer further in. The check belongs in
the deploy, and a mismatch fails the deploy rather than warning in a log nobody reads.

**And a digest is not enough on its own, which D-049 established the hard way.** A stage's
fingerprint was hashing only its own function body and not the modules it called, so
`ids.publisher` could change from `os:link:{id}` to `os:link/{id}` — one character,
deliberate — without any fingerprint moving. The database went on holding 195,689 links
identified in a scheme the source no longer produced, and the build exited 0 with every
figure intact. **Nothing that read the database could have caught it, because the database
was internally consistent**: every identifier in it agreed with every other one, so a
consistency check passes. It was caught by a unit test comparing `ids.publisher(...)`
against a literal — and only because that test imports the module rather than querying the
build.

**The rule that follows, and it applies in three places in this tool:** *a check that reads
only the artefact cannot tell you the artefact was built by the code you have.*

- **The release asset carries its producing build's fingerprint, not only its own digest.**
  A digest says the file is intact; it says nothing about whether the exporter that made it
  is the exporter in the tree. CI compares both, and fails on either.
- **The JSONL is validated against the schema module, not against itself.** A contributed
  corpus can be internally consistent and wrong in exactly D-049's way — every line agreeing
  with every other line, in a shape the tool no longer emits. rewt-6a's identifier test is
  already the right shape because it resolves against the database rather than counting; the
  schema validator must import the definition rather than infer it from the rows.
- **The tracer gets an `ids.js`, and it gets one before the code that would scatter
  identifiers, not after.** D-051 found `ids.py`'s rule broken twice because it was a
  sentence rather than a test, both times in an f-string that a separator change went
  straight past. I ran rewt-d3's crude test — grep every module but the owner for a composed
  scheme literal — against the three lifted files, and it says something useful: **`anno.js`
  does not own its identifier scheme at all.** It takes `identifying` as an opaque
  `{source, label}`, and the predecessor composes the URN in its *caller*:
  `` `urn:premodern-rivers:replaces:${replaces}` ``, one template literal, 1,885 lines into
  a UI module. That is D-051's exact shape in JavaScript, and **a wrong separator in a URN
  stays a legal URN and stops resolving** — the `basin-unanchored:1002` failure, in a format
  where nothing will complain.

  So: one module owns every `urn:` and every `w3id.org` URI the tracer emits, and a grep
  test fails any other module that composes one. **The rule is tighter on the JS side than
  on the Python side, not looser**, precisely because a URN has nothing to fail against.

  **`ids.js` is generated from `rewt/ids.py` and the generated file is committed**, with a
  build check that regenerating produces no diff. My first instinct was an equality test
  asserting the two agree on the same inputs, and rewt-d3 is right that this is a net under
  a hazard nobody has to create: two implementations agree only while someone remembers to
  change both, and an equality test passes for every input it happens to enumerate. **That
  is the enumeration problem, not the equality problem.** Generating turns the failure mode
  into a dirty tree in CI, which is loud. Keep the equality test as well — it costs nothing
  and it catches the case where the *generator* is wrong.

  **And this does not breach the rule that nothing derived is committed**, which is worth
  saying before someone reads it as backsliding. That rule exists because *a committed
  artefact silently stops matching its inputs and nobody notices, because it looks like
  data*. A generated file whose regeneration is checked on every build is the one case where
  the drift is made loud rather than silent — it is the rule's reason satisfied, not evaded.
  A committed artefact nothing regenerates would be the violation, and `.gitignore`'s
  sentence would be better if it said so.

  **Two conditions, both rewt-1d's, and the first is the one that makes it honest.** The
  regeneration diff runs **in CI on every build** — not in a pre-commit hook, not in a
  script somebody remembers. A check that runs only where its author happens to run it is a
  sentence again, and it would be a poor outcome to fix a hazard caused by a convention with
  a convention of the same kind. And the symmetry: **the file is committed only for as long
  as the check that guards it runs.** If that check is ever disabled or moved out of CI, the
  file reverts to being an ordinary derived artefact and goes back into `.gitignore`.

- **The served build is stamped and checked.** The London Customs Accounts editors carry a
  `BUILD` constant that must match the `?v=` on the script tag, because browsers keep
  serving a cached file and the page then reports the behaviour of code that is no longer
  deployed. Same family, at the browser end: the artefact a contributor is running may not
  be the artefact CI built.

**That check has a precondition, and it was not satisfied until today.** A fingerprint is
only worth comparing if the thing producing it is deterministic; otherwise the check fails
on an honest rebuild and **teaches everyone to ignore it**, which is worse than not having
it — the same shape as a wrong checksum being worse than no checksum. The build was not
deterministic: WhiteboxTools' breach gave three different rasters from three threaded runs
on identical input, and the verification that appeared to prove otherwise had the terrain
stage cached in both builds compared, so the non-deterministic step never ran. Pinned to one
process it is exact and costs a second (D-039). **So this plan depends on D-039 holding**,
and if determinism ever regresses, the honest response is to disable the comparison and say
so rather than let a failing check train people past it.

**Two attributes are a condition of that export, and they are rewt-d3's condition rather
than my request: `origin` and `routing_reversed`.** 1,204 of the links are this project's
own geometry rather than Ordnance Survey's, and a contributor deciding what a traced course
replaces must be able to tell survey from correction without reading the code. A reversal
moves no geometry, so without the flag the most error-prone correction in the build is
invisible on the very screen where someone is about to bind a historical claim to it. The predecessor commits 17–29 MB of
PMTiles to `docs/data/` and it works: Pages supports range requests, which is the whole
premise of the format. OS Open Rivers is OGL, so this is public with no gate and no
argument.

**A link id is stable because of a policy, not because of a property of the string, and a
trace that stores one inherits the policy.** The `identifier-scheme` card came back
*rejected* — *"Freeze on the 2026-04 issue"* — so the project keeps OS's own GUIDs and pins
the input rather than minting ids from geometry. OS states its identifiers are not
persistent *between product versions*; with exactly one version there is no second version
to be inconsistent with, so the stability §10 asks for is bought by **refusing reissues**.
That is the cleaner answer and it is fine for an annotation target — but the durability an
annotation inherits is the pin's, not the identifier's, and a trace stored today against
`os:link/...` is stable for exactly as long as that freeze holds. Record the issue the trace
was made against, not only the id.

**And the pin protects against the publisher, not against us.** rewt-d3's correction of its
own note: freezing closes OS moving node ids underneath us, and closes nothing about our own
scheme changing — which is what turned `rewt:basin/d5921800ed` into `rewt:basin/000e9ed6b8`
this morning. Only the one-owner rule and its test protect against that, which is why the
`ids.js` work above is unaffected by the freeze and is not made redundant by it.

Carry a **fingerprint** with the archive either way, as the predecessor does, and record it
on every trace. A network the app cannot name cannot be reconciled with a trace made
against it, and the traces will outlive several rebuilds.

### In: the work queue

One task is **one place**: a point, a class, the sheet and edition to reach for, and what
the trace is expected to bind to. Built from the **CC0 GB1900 raw dump**, never the
published gazetteers — they are CC-BY-SA, share-alike would propagate into this project's
own exports, and the abridgement drops every string occurring 300 or more times nationally,
which is exactly the mill and towing-path vocabulary.

The clustering is already described and measured in `docs/scale.md`: labels collapsed to
places at a kilometre, taking 139 *Old Course* labels to 126 places and 224 *New Cut* to
209 — 361 labels at some 274 places for the two classes together; 4,996 mill-channel
labels to 4,068 places.

**It does not need redoing and it is already committed.** rewt-86 rebuilt the chain from
the CC0 dump; rewt-1d landed it as `tools/gb1900/measure.py` with a README (82299d4), and
it reproduces every published figure exactly. The work queue is one command (a96fdef):

    .venv/bin/python tools/gb1900/measure.py --places out/
      mill_channel_places.csv   4,068
      old_course_places.csv       126
      new_cut_places.csv          209
      towing_path_places.csv    1,724

`place_id,text,labels,easting,northing` in EPSG:27700, one row per place under the same
1 km single-linkage rule `docs/scale.md` publishes.

**The queue arithmetic differs from the page, both are right, and the tool wants the
page's number.** 126 + 209 = 335 is per-class clustering by caption; the page's **274** is
*Old Course* and *New Cut* clustered together on position alone, because the two captions
describe the same event from either side and frequently sit on the same reach. **Unioning
the two files would send two contributors to opposite ends of one channel and get it traced
twice** — which is precisely the double-work the queue exists to prevent, and it would
arrive as an accident rather than as §8's deliberate overlap, contaminating the one
measurement the tool exists to make possible. So the assertion queue is
`assertion_places.csv` — **274 places**, clustered on position across both classes, ids
`as00000…` (3a81de8). Its `text` carries the distinct captions in each cluster joined by
`; `, so a contributor sees both sides of the assertion where both were transcribed: the
first row reads *NEW CUT; New Cut Bridge; New Cut Bridge (Draw)* — five labels at one
place, which is the case for merging in miniature.

**The 274 are not yet 274 assertions, and how much they are not took two attempts.**
rewt-86 noticed that *New River* is a name as well as a description — the Jacobean aqueduct
that still supplies London — and asked whether the pattern was collecting it. It is. The
measured breakdown:

| in `assertion_places.csv` | places | |
|---|---:|---|
| the channel itself is lettered | 258 (94.2%) | trace it |
| only a structure **on** it is lettered | 8 (2.9%) | weaker evidence, still worth looking at |
| New River Company estate, no channel implied | 8–9 (~3%) | not a task |

They are `NEW RIVER STREET`, `NEW RIVER WALK`, `New River Head`, `New River Gate; New River
Gate House`, two reservoirs, a ponds pair, a pumping station and a well — **the New River
Company's built estate rather than its channel**, which is one step broader than the
aqueduct rewt-86 predicted.

**Eight or nine, and the difference is a judgement rather than a discrepancy.** rewt-1d
classified all 274 independently and reached nine; the disagreement is whether *New River
Head* is estate or the head of the channel. `docs/scale.md` says nine and says the boundary
is a judgement in a handful of cases, which is the honest form of a number that cannot be
exact. Two rows — *Old River Bed* and *Old Course of Bridge Dike* — were flagged wrongly by
**both** classifiers, each catching a genuine channel on a structure word.

**The first number I published for this was 18, and it was wrong by more than double.** I
counted a place as contaminated if *any* caption in its merged cluster matched a structure
word — but the clusters are merged, so `NEW CUT; New Cut Bridge; New Cut Bridge (Draw)`
contains one and is a perfectly good task: the surveyor lettered the channel *and* the
bridge over it. The right test is whether **no** caption in the cluster describes a channel.
It is recorded here because the error has a structural cause and a structural fix.
**A merged cluster is a set of statements, and testing it as one string will keep producing
this** — *any caption matches* against *no caption describes*. rewt-1d's own classifier made
the identical mistake on two rows, which places the fault in the field rather than in
anyone's attention. So `assertion_places.csv` grows a **`captions` column carrying the list**
rather than only the `; `-joined string, and the test becomes hard to get wrong instead of
merely done carefully once. rewt-1d is adding it.

**The middle row is not contamination and should not be filtered.** A bridge lettered *New
Cut Bridge*, a farm lettered *Old River Farm* — the surveyor is naming a structure after
the channel beside it, which **locates a channel that was not itself lettered**. Weaker
evidence than a lettered channel, and not nothing: a task with a caveat rather than a
rejection. One of the eight, *Old Course of Bridge Dike*, is a genuine channel my own
pattern caught on the word *Bridge*.

**Two things the exercise settled for the queue's design.** `New River (Old Course)` is a
caption asserting a new cut and a superseded course at once, so **nothing may assume one
class per place**. And the ten `NEW RIVER ANCHOLME; Old River Ancholme` rows are both sides
of the assertion in a single cluster — the strongest form the evidence takes, and the
argument for the merged queue rather than against it.

**A cleaning pass is phase 4 work and is now scoped rather than hoped**, with one caution
carried from rewt-86: the mill queue should be much cleaner, because `mill` must be
immediately followed by a watercourse word, so *Mill Lane* and *Millbrook* never match —
whereas *New River* and *Old River* are two ordinary words in sequence, which is how the
contamination is constructed. That is an expectation to test cheaply, not a result.

**`towing_path_places.csv` is not a queue; it is the best contextual layer the tool can
carry.** 1,724 places, nothing traced from them. Their value is twofold: they are direct
evidence that *this* channel carried traffic, on the reach in front of the contributor and
from the same survey — and they are trustworthy in that role precisely because they were the
control that behaved as it had to, 97.8% within 250 m of a navigable section against the
mill channels' 5.5%. A control that behaved as it must is one you can lean on.

**With a display rule attached, and it generalises well past the towpaths.** A towing path
proves traffic **at the survey date and nothing earlier**. On a screen where someone is
binding a historical claim to a line, a label reading *this was navigable* rather than
*navigable in 1899* is exactly the drift `docs/epochs.md` spends a paragraph guarding
against — and it is the same failure as asking a contributor to type a year (§6), as dating
a tileset from the name of its series (above), and as **a snapped trace on an outline
edition looking more authoritative than a hand-drawn one when the algorithm may be
following a road, a parish boundary or a contour** (§7). Four mechanisms, one failure:
rendered confidence read as evidential weight.

**The constraint, in its general form: anything shown to a person must carry the limit of
what it shows, at the moment they act on it.** Not in a tooltip, not in the annotation, not
in a README. The fourth instance is the one that proves it is a design constraint rather
than a documentation one — a provenance field that only a later reader sees does nothing
about over-trust, because the person over-trusting the line is the contributor, in the
moment, with the line in front of them. That is why the clicked/snapped distinction is
visible **while tracing** and not only in the file, and why `snap_mode: hand` is the honest
value when snapping is off. No bare assertions on the canvas.

**And there is a live provenance fault on it that the tool must not build over.** The
archive's sha256 does not match the checksum `conf/sources.yml` declares, and the value in
the entry was carried from the predecessor's manifest without being re-derived. The script
refuses to run without `--unverified`, and **every run producing these files so far has
printed that banner**, so no task list is built from them yet.

Be exact about which half is open, because *the counts reproduce* is not the reassurance it
sounds like. **Established:** the archive was fetched from the publisher on 1 Sep 2026, is
byte-identical to the eleven-month-old copy in the predecessor, matches the server's `ETag`
at 326,329,494 bytes, and passes CRC on all 22 members. Two independent acquisitions
agreeing is strong evidence about the *file*. **Not established:** that this is the object
`conf/sources.yml` names, because that field says something else. Until the line is
corrected, the provenance on 4,068 tasks would assert a fact nobody has checked. The fix is
one line, rewt-d3 has the evidence, and the queue waits.

**Two traps recorded so nobody falls into them twice.** `GB1900_gazetteer_abridged.zip` is
sitting on this machine, is the obvious file, and is wrong twice over: **CC-BY-SA**, whose
share-alike would reach REWT's own exports, and *abridged* — the abridgement drops every
string occurring 300 or more times nationally, which is precisely the *Mill Race* / *Mill
Pond* / *Towing Path* vocabulary the queue is made of. That is D-018. And the dump is
**re-acquired against its pinned checksum, never copied from the predecessor**: AGENTS.md
forbids importing its data, and the source entry warns that the server sends an incomplete
certificate chain, so integrity comes from the checksum and not from the chain.

**The edition is part of the task, not a preference.** Set the reservoir's completion year
against the survey date of the sheet it sits on and the task can say which edition to
open before anyone opens one — and, for 19 reservoirs in England and Wales and 87 on the
Welsh register, that **no Ordnance Survey edition shows the valley at all** and the
recourse is a pre-Ordnance-Survey county map. Knowing that before the search starts is the
difference between an afternoon and a week, and a task that does not say it will be
attempted repeatedly by different people.

### In: the sheets

**Fact and curation are being split, and rewt-fc is doing it.** A generated
`tools/nls_layers.json` becomes the shared factual catalogue — `id`, `tiles`, `zooms`,
`bounds`, and an `england_wales_share` that separates a Scottish tileset from one of ours,
across the 324 tilesets found by a machine walk of the bucket. **`zooms` and `bounds` are
observed**, from listing the keys the Library actually serves at a probe zoom, not from a
description and not from a guess.

**The catalogue carries no dates, and the tracer must not add any.** It tells you what
exists, where, and at what zooms; it does not tell you when, because the bucket does not
say. A tileset called `os/one-inch-old-series-all` invites the label *1805–1874*, and that
label comes from a person's knowledge of the series rather than from anything NLS said
about that tileset — so it belongs on a curated entry where it is a human claim someone can
be held to, and not in a machine catalogue where it would look like a discovered fact. The
trap has already caught this project once today, labelling the six-inch second edition
*1888–1913* from a different product's naming. `tools/viewer/backdrops.json` stays the
*viewer's* curation of that catalogue: which subset it offers, default, opacity, warnings.
The tracer reads the same catalogue and makes its own curation. One source of fact, two
presentations — which matters here, because the two tools must say opposite things about
the same tileset and both should say theirs loudly rather than hedge.

**The tiles are readable from a canvas, and the check that says otherwise is the wrong
check.** The NLS S3 host sends `Access-Control-Allow-Origin: *` on GET and on OPTIONS
preflight, verified against an explicit `Origin: https://docuracy.github.io` for the
seamless layers and the per-county first-edition mosaics. It does **not** attach CORS
headers to HEAD — so `curl -I` reports no CORS and is believed, which is how rewt-fc's
earlier note came out backwards. Test with GET. The canvas is untainted, `getImageData()`
works, and §7 is viable. **And the answer is one policy, not sixty-nine.** CORS is configured on the *bucket*, so
rewt-fc's first probe asked the same question 67 times and got it wrong wherever a sample
tile fell outside a layer's real coverage and 404'd. It now groups by host and tries layers
until one answers: `mapseries-tilesets.s3.amazonaws.com: canvas-readable (ACAO *) — 67
layers`. Snapping works against **any** NLS layer, including the 25-inch below. MapTiler
reports `UNKNOWN` because the origin-bound key 403s and it was therefore never checked,
which is the only true thing available to say about it.

### Two sheets, two operations — and they are not interchangeable

rewt-fc's walk of the bucket catalogued **2,016 tilesets** and turned up the layer this tool
should default to: **the OS County Series 25-inch, 1:2,500 — `25_inch/<county>`, 165
tilesets, zoom 18 and in places 19.** Verified in the catalogue: 165 items, every one
observed rather than described. At z18 that is roughly **0.6 m per pixel**, an order of
magnitude finer than the six-inch and two finer than the Old Series. The limit on a traced
line stops being the raster and becomes the georeferencing.

**And several counties carry their editions as separate tilesets** — `gloucester`,
`gloucester2nd`, `gloucester_3rd`, `gloucester_additions`. That is a before-and-after at one
place **without dropping scale**, which is exactly what an *Old Course* / *New Cut* assertion
wants: the surveyor says one channel replaced another, and two editions at 1:2,500 show it
happening.

**THE SIX-INCH IS THE ORDINARY TRACING SURFACE, AND AN EARLIER VERSION OF THIS SECTION SAID
OTHERWISE.** It was headed *the 25-inch is the tracing surface, not the six-inch*, and that
was wrong — corrected by Stephen, 1 Sep 2026. The six-inch is where the work is: the task
queue is derived from GB1900's transcription of the six-inch second edition, and the
seamless layers cover England and Wales where the 25-inch is county by county. What the
25-inch changes is not which sheet is normal but **which operations are possible**, and the
two do not transfer:

**And the distinction is per reach, not per sheet — a second correction, on top of the
first.** OS switches from one line to two at a **ground width**, so a six-inch sheet carries
both: a mill leat as a single stroke, a navigable river as a pair of banks, sometimes in one
frame. `docs/evidence.md` records the Weaver at Northwich drawn as two banks on the
six-inch. What the finer scale changes is **how many** channels fall on the two-bank side of
the threshold, not whether the distinction exists.

| | one stroke of ink | two banks with white between |
|---|---|---|
| where it happens | a leat, a brook, a narrow cut — at any scale | a navigable river, a canal; more often at 1:2,500 |
| the operation that fits | **follow the ink** (phase 3) | **find the middle between two sides** |
| centring | refuses — there is no width to find a middle of | its proper home |
| channel width | not readable | readable, and `PLAN.md` §10 wants it |

**So the tool must not choose by sheet.** A version of this did, disabling centring off the
25-inch, and it would have been wrong on every wide river — which is precisely where the
navigation evidence lives. **The per-vertex refusal decides it correctly and from the
pixels**, and needed nothing added: *that point is on ink, so the channel here is drawn as a
single line.*

**The bank problem, stated for the scale it belongs to.** At 1:2,500 a corridor livewire
minimising ink cost would lock onto whichever bank is darker or nearer and produce a trace
offset by half the channel width, consistently, in a direction nobody chose. It would look
like a good trace.

Three ways out, and the choice is a phase 3 experiment rather than a decision to take here:

- **Snap to the medial axis of the enclosed white** rather than to the ink — the same answer
  `PLAN.md` §5 reaches for water bodies OS draws as areas, and for the same reason. It is
  the correct line and it is more work.
- **Trace a bank deliberately and record which**, since `vertex_origin` already carries
  provenance per vertex and a bank is an honest thing to have traced.
- **Fall back to the six-inch for wide channels**, where one line is what the surveyor drew.

What must not happen is snapping to ink at 1:2,500 and calling the result a centreline.
That is §4's rule again — rendered confidence read as evidential weight — arriving through
a new mechanism, which is now five.

**The survey date is not an attribute of the backdrop, and planning it as one is a mistake
I had already made.** Two reasons, both rewt-fc's. A *seamless* layer is a composite of
many sheets of different dates and therefore has **no single survey date at all**. And the
per-sheet dates live in Stephen's `markets` OS sheet register, which is a witness this
project may quote but not ingest — its own source row records `licence: "not stated"`,
`redistributable: 0`. D-037 separately records that NLS state no date spans for these
layers and that the figures in circulation come from a different product's naming.

So **provenance records which tileset, at which coordinate**, which is a fact the tool
holds with certainty, and the date is a **separate lookup** rather than a field copied off
the backdrop. For the per-county first edition the county is known and its sheet date can
be looked up; for a seamless layer it cannot, and the trace records a date bound of
`unknown`. An unknown bound is a publishable fact (`docs/epochs.md`); an invented one is
the error D-023 exists to prevent, pointed at a date.

**One problem I cannot solve on Pages, and it is the expensive half of the work.** The NLS
publishes the first edition county by county, with mosaics that bleed across the county
line, and MapLibre cannot clip a raster to a polygon. rewt-fc's server composites the tile
itself, masked to Historic Counties Standard polygons. A static site has no server to do
that in, and **two in five reservoir valleys need the first edition** — 14 first-edition
only, 26 surveyed while the dam was building, out of 165 impounding reservoirs. Two
routes: pre-bake the composite as a PMTiles archive at deploy time, or do the masking in a
canvas client-side from the county polygons.

**Pre-baking is ruled out, and the reason is §3's rule rather than storage.** A baked
composite is a mosaic of NLS tiles; committing it to `docs/` republishes them to the open
internet, which is the clearest possible case of the thing NLS's stated condition asks us
not to do. rewt-fc reached the same conclusion independently and more sharply.

**Client-side masking, and it is cheaper than it sounds.** For a tile, find the counties
whose bounds intersect it — `tools/viewer/nls_counties.json` carries HCS code, name, NLS
slug and derived bounds for the 53 the Historic Counties Standard could match, with the
in-scope and masked flags. **Masking reads that file and not the catalogue**, which carries
all 71 `os/six-inch-<county>` tilesets and does not know which polygon belongs to which
mosaic. The two disagree by design: one is the wider inventory, the other is the one that
can mask.

**And the catalogue's `bounds` are a hint, never a containment test.** They are derived from
a listing at zoom 9, so a box is snapped to about 78 km and several counties genuinely
contain any given point. For *masking* that over-selection is safe — the polygon does the
real work and the cost is a few wasted fetches. For *deciding which sheet covers this
coordinate* it is not: rewt-fc's viewer picks the smallest box containing the centre and
lands on Cheshire at Northwich, where picking the first landed on `Shrop_Derby` and drew one
tile in fifty-seven. **If the tracer needs to know what actually covers a point, it asks the
bucket for the tile.** For each, draw its tile to an offscreen
canvas, then `globalCompositeOperation = 'destination-in'` with the county polygon filled.
That is a mask in two operations and **no per-pixel work**; the polygons are already
simplified, so filling them per tile is cheap. Composite the results and discard.

Two rules from rewt-fc's server that are not obvious and that I would otherwise have got
wrong: take a pixel only where the county **owns the ground** *and* **its own tile has
alpha there** — the first stops a mosaic bleeding past its boundary, the second keeps a
mosaic's internal white margins from painting over its neighbour — and skip counties
flagged out of scope. Their compositor is server-side because a served tile can be cached
to disk and reused across sessions and users, not because the client cannot do it. For one
person tracing, that difference is small.

### Out: the edit log

§5.

---

## 5. The edit log

**Append-only, event-sourced, and the reason is `AGENTS.md`'s own rule.** *Never delete a
geometry to correct it — retire it with a reason and keep it. The audit trail is part of
the product, and a retired link is how a reader tells a correction from an omission.* That
rule is written about the network; it applies with more force to work contributed by
someone who cannot run the build and cannot see what their edit did. So the file is a log
of what happened, not a picture of the current state, and the current state is a fold over
the log.

**One line per committed act**, not per mouse movement: a trace finished, a trace revised,
a trace withdrawn with a reason, a task skipped as impossible with a reason, a note
attached. A skip is data — *this reservoir has no pre-dam sheet* is a finding, and a tool
that only records successes throws it away.

Each event carries a UUID, a monotonic local sequence, the contributor's login, an
ISO timestamp, the task id, and the payload. **Events are idempotent by UUID**, which is
what makes both offline flushing and conflict recovery trivial.

**And the fold's order is stated in the format, not left to whoever reads the files.**
PLAN.md §2 requires deterministic ordering wherever a result depends on iteration order,
and this is such a place: two contributors' files merged on a branch have no inherent
order, and *revised* then *withdrawn* is a different final state from the reverse. The
total order is `(timestamp, login, local sequence)` with the tie-break named in the spec,
so the fold is reproducible rather than dependent on which file was read first. rewt-6a's
point, and it is a sentence in the spec now or a bug that appears only when two people work
the same task.

### Writing it

One file per contributor per batch, so two contributors can never touch the same path and
no merge logic is needed. The GitHub Contents API has no append: a save is a `PUT` of the
whole file with the previous `sha`. That is fine at this size, and it forces the
partitioning that avoids conflicts anyway.

Four things learned expensively in the London Customs Accounts editors, all of which
apply here unchanged:

- **`btoa` needs a binary string, and `String.fromCharCode(...bytes)` passes every byte as
  a separate argument** — so past roughly a hundred thousand bytes the call blows the JS
  argument stack. This stopped saving once one annotator's file passed 360 kB. Chunk the
  encode at 32 kB and it scales.
- **`/contents` refuses to return a file over 1 MB.** Read through the tree and blob APIs
  instead; the tree call also yields the `sha` needed for the next write.
- **Ask the tree whether the file exists before requesting it.** Going straight to
  `/contents` works but logs a red 404 on a first run, which means *you have not started
  yet* and reads as a fault. It gets reported as one.
- **A 409 is a conflict, not a failure.** Pull, union by event UUID, order by
  `(created, uuid)`, retry.

Cadence: flush every N events or after M seconds idle, whichever comes first, plus a
`keepalive` push on `beforeunload`. Ten events or sixty seconds is the proven pair.

### Offline

Every event is written to **IndexedDB first**, marked unsynced, and only then queued for
push. The flusher runs on `online`, on a timer, and on demand. Because a save rewrites the
whole file and events are idempotent, coming back after a day offline is the same code
path as an ordinary save.

**Two guarantees the interface must make visibly**, because a contributor who does not
trust the tool will re-do work:

- The header states, at all times, how many events are held locally and when the last
  successful push was. Not a spinner — a count and a time.
- **An export button that downloads the JSONL**, always available and working when signed
  out, offline, or refused by GitHub. A failure message that says *your work is safe in
  this browser, and Export saves it to a file* is the difference between an annoyance and
  a lost evening.

---

## 6. What a trace records

The predecessor's W3C Web Annotation profile is the right shape and should be adopted
rather than reinvented — the target is a region of a map and the body says what that
region is, which is precisely the Web Annotation data model. It follows GB-STAMP's
profile so a tracer and a text-spotter emit compatible records, with two departures forced
by the subject: **the target is a place, not a canvas** — the same channel may be drawn on
four editions, and a course in canvas pixels is meaningless to anything but one scan — and
**there is no standard geo selector**, so the profile defines `GeoJSONSelector` explicitly
rather than overloading `FragmentSelector`, which expresses a box and not a course.

The event payload for a finished trace carries:

| field | what it is |
|---|---|
| geometry | LineString, CRS84, `conformsTo` stated |
| `vertex_origin` | per vertex: `clicked` or `snapped` |
| `snap_mode` | `hand`, `monochrome` or `coloured` — see below |
| sheet | backdrop id, the **published** sheet URL, zoom; never the keyed template |
| `replaces` | the `link_id` this course supersedes, or an explicit `adds` |
| `when` | LPF timespan derived from the sheet's survey date |
| creator | GitHub login; `generator` names the tool and its build |
| confidence, notes | the contributor's own words, including doubt |
| `reason`, `evidence`, `author`, `dated` | the four fields every judgement in this repository carries |
| a coordinate | on every line, without exception |

**The last two rows are rewt-6a's requirement and they are not boilerplate.** `author` and
`dated` have just been made mandatory on curated judgements, because a contribution that
does not say who made it and when cannot be weighed a year later — and a contributed trace
is the case where that bites hardest, since the person who made it cannot run the build and
may never be reachable again. And **332 corrections in the current build turned out to
carry neither geometry nor easting/northing**, so nobody could go and look at them. A skip
or a note has no line geometry of its own; it still gets a coordinate. *Report at the
place, not only in the total* applies to a contribution exactly as it applies to a
finding.

**`creator` versus `generator` is doing real work here.** W3C's separation of who is
responsible from what software serialised it turns out to express the thing a
semi-automatic tracer most needs to record: which vertices a person put down and which the
algorithm chose. A trace where every vertex was computed is a different evidential object
from one placed by eye, and downstream work is entitled to tell them apart. So the
provenance is carried from the moment it arises rather than reconstructed later — and it
is **visible while tracing**, clicked vertices solid and snapped ones hollow, not only
afterwards in the file.

**`snap_mode: hand` is the honest value when snapping is off.** With snapping disabled no
vertex came from the cost surface, and naming the sheet's colour mode would imply a
machine read one when none did.

**The date is a bound, never a year.** `docs/epochs.md` sets out why: a model that requires
a start date forces every source to invent the half it does not have. A channel labelled on
a sheet surveyed in 1899 is `start: {latest: 1899}, end: {earliest: 1899}`; a reservoir
completed in 1869 gives the drowned channel `end: {in: 1869}`; a valley drawn as river on
the first edition and water on the second is `end: {earliest: 1854, latest: 1894}`. **The
contributor never types a year.** The tool computes the bound from the task and the sheet
and shows it back in words — *this says the channel existed in 1899 and nothing about when
it began* — because a contributor who is asked for a date will supply one.

---

## 7. The tracing surface

**Snap-to-ink is the feature, and it is why this is a tool and not a form.** A traced
segment is fitted to the printed ink of the sheet rather than clicked freehand, so two
people tracing the same channel produce substantially the same line. Without it,
contributed geometry is not comparable and the agreement measurement in §8 has nothing to
measure.

How it works, and why not the obvious way:

- **Do not read the map's own canvas.** MapLibre renders through WebGL and getting pixels
  back means `preserveDrawingBuffer: true` — a cost on every frame for every user, to serve
  a feature almost nobody switches on. Fetch the tiles separately: free when idle, native
  resolution rather than whatever the screen happens to be, and the backdrop alone with no
  river lines drawn over the thing being followed. This requires
  `access-control-allow-origin: *` on the tile host; the NLS S3 host serves it.
- **A cost surface, not a blue mask.** Measured over 40 tiles each centred on a river link,
  the median blue fraction is 0.000% and the 90th percentile is 0.000% — roughly one sheet
  in twenty is coloured and the rest are monochrome outline editions, where a blue detector
  finds nothing. What makes it tractable is that the distribution is **bimodal**: a tile
  reads either exactly zero or several percent, with nothing between, so the sheet type can
  be decided from the pixels at runtime with near-perfect reliability. Classify first, then
  follow blue where it exists and ink darkness where it does not.
- **The corridor constraint is what makes it usable.** On a monochrome sheet, ink darkness
  describes roads, railways, contours and parish boundaries as well as rivers, and a
  shortest path will cheerfully set off down a turnpike. Confining the search to a band
  around the straight line between the last vertex and the cursor means the algorithm may
  only choose among ink the contributor has already pointed at. **It is an assistant, not
  an interpreter**, and the interface should say so.
- **Blank paper must not be snapped to.** Outside coverage, or where tiles are refused, a
  uniform field produces a confident-looking line and a false claim about how it was made.
  Classify, and refuse.
- **Snapping is a separate switch from tracing.** The ink runs out, forks, or is crossed by
  a road, and there the only honest line is one a person draws. Conflating the two made the
  predecessor's tool unusable exactly where it was most needed.

### The survey's own tolerance, and the three places it applies

D-046 measures OS Open Rivers' generalisation and finds a **knee rather than a taper**:
median vertex spacing 56.7 m, median sagitta 15.6 m, but sagitta is 0.18 m at the 0.1st
percentile and only 0.25% of vertices fall below 1 m, while the 10th percentile is already
8.99 m. That is the signature of a tolerance filter. **The survey keeps bends down to about
9 m of amplitude and essentially nothing below.**

rewt-d3 offered it as a parameter for the livewire. It is more useful than that and it
belongs in different places than the obvious one, because **it is a property of OS Open
Rivers and not of the sheets being traced.** A 25-inch sheet at z18 carries detail an order
of magnitude finer than 9 m; the tracer is not reading the modern network.

- **Not the corridor width.** That is measured in sheet pixels and constrains where the
  livewire may search on the raster. Nothing about the modern survey's tolerance bears on
  it.
- **Yes, the binding tolerance.** When a trace is resolved onto the network — which link it
  supersedes, which node it meets — the match must be generous relative to ~9 m, or courses
  that genuinely are the same line will fail to bind because the survey smoothed a bend the
  sheet drew.
- **Yes, and this is the one that matters: whether a trace has demonstrated divergence at
  all.** A contributed course that differs from the modern channel by less than the survey's
  own tolerance **has not shown an old course; it has redrawn the current one.** That is a
  quality rule for phase 6 and it is the difference between a finding and a redrawing.
  `docs/scale.md` already reasons this way about the navigable corpus — 2.3% of it drawn on
  a course the modern survey does not carry, *and that figure is a floor because improvement
  generally followed the river*. Below the tolerance, geometry cannot tell the two apart.
- **Emphatically not the agreement threshold.** Phase 7 asks whether two people tracing the
  same channel produce the same line. They are both reading a 25-inch sheet, and can
  legitimately agree far below 9 m — so importing the modern survey's tolerance as the
  pass mark would make the test lax by an order of magnitude and it would pass whatever
  happened. That threshold is set by the sheet's resolution and its georeferencing, and by
  nothing else.

**Where this code comes from is a decision, not a detail — see §10.**

---

## 8. Assigning the work, and measuring agreement

**Assignment by link, not by a claims file.** A claims file in a repository with no server
is a race; the London Customs Accounts editors solved this with a URL fragment —
`#from=0&n=20` — that a coordinator hands out, and it has worked across a corpus of
thousands. The fragment rather than the query string, because it never reaches the server
and so cannot interact with Pages caching. Two people can be pointed at exactly the same
tasks by sharing one link, which is the next point.

**A slice narrows what you work on, not what you have done.** Everything already
contributed stays visible and stays in the log; the slice is a view, not a partition of
the output.

### The basin lock

**A contributor takes a temporary lock on the basin they are working in.** Stephen's
design, and having argued against it I was wrong on both counts.

**Wrong about the unit.** I said the basin was too coarse because two traces in one basin
do not interact the way two network repairs do, which is true and is not the point. The
basin is the right unit for **the person**, not for the collision radius: a contributor
working one basin learns its drainage pattern, the mill vocabulary of its county, and which
sheets cover it — and that local knowledge is most of what makes the second hour faster
than the first. Handing out a basin hands out a coherent body of work. Handing out scattered
places hands out forty unrelated ten-minute puzzles.

**Wrong about the mechanism, and this is the substantive correction.** I said a serverless
lock could only be advisory, stale by up to a minute, with two people able to claim
simultaneously and each learn of the other afterwards. That is true of a *claim file that
is read before it is written*, and it is not how this has to work. **The GitHub Contents
API gives a real compare-and-swap: a `PUT` with no `sha` creates a file and fails with 422
if one already exists.** So acquiring a lock is a single atomic create, and the loser is
told by the API rather than by a stale read. That is not advisory. *(Verify against the
live API before building on it — it is documented behaviour and this project's habit is not
to trust documented behaviour it has not seen.)*

**The design:**

- `locks/<basin_id>.json` on the `traces` branch, holding `{login, acquired_at,
  heartbeat_at, expires_at}`.
- **Acquire** by create-without-`sha`. 422 means somebody else holds it, and the file says
  who and until when.
- **Heartbeat** by `PUT` with `sha` on the flush cadence the event log already runs on, so
  it costs one small extra request and nothing new to schedule.
- **A long timeout — 30 minutes from the last heartbeat.** §8's duty-cycle problem is real:
  the drawing is quick and the deciding is slow, and a timeout tuned to the drawing would
  steal a lock from somebody reading a sheet. Thirty minutes is longer than any single act
  of tracing and shorter than an abandoned session.
- **Expiry is takeable, and the takeover is an event.** A contributor may claim a lapsed
  lock; the event log records the takeover with the previous holder named, so an abandoned
  basin resolves itself without an administrator and the record shows it happened.
- **Release** on finishing the basin and on `beforeunload`.

**The lock is honest about what it is**, per §4: the interface says *held by <login>, expires
in 12 minutes*, which is a true statement about a file, and never a bare *locked*.

**Three things the lock does not replace.**

1. **Assignment still comes first.** Disjoint basins handed out by a coordinator means the
   lock is never contended in the ordinary case. A lock that fires often is a symptom of
   bad assignment.
2. **Presence within a basin.** One basin can hold two contributors legitimately — see
   below — so a heartbeat with a coordinate still drives a *someone is working within 2 km,
   last seen 40 s ago* notice. Advisory, and labelled as such.
3. **Detection after the fact.** Every event carries a coordinate and a task id, so a fold
   over the log finds two traces of one place whatever the locking did. A collision that
   was not a chosen pair is a flag for adjudication — and it feeds the agreement measurement
   rather than being wasted. Locks prevent the common case; detection catches the rest,
   which is this project's own crawl-from-the-sea principle applied to people.

### One contributor's name on another contributor's screen

rewt-1d noticed this in the lock design and it is worth settling before it is a screen: the
hold is **the first thing in the tool that describes contributors in relation to each
other** rather than to the work. *Held by <login>*, and a takeover naming who it was taken
from, is a small privacy decision hiding inside a provenance feature.

**Three things are being conflated and they should not be.**

- **Attribution in the record is not negotiable and is a good deal.** `author` and `dated`
  are mandatory on every contributed line (rewt-6a), and `docs/aims.md` promises that
  contributed work appears under its contributor's name at the next edition. Nobody should
  want to change that.
- **The lock file is readable by anyone with repository access.** So not rendering a name in
  the interface is a courtesy, not a protection — the same lesson as the gate: a check in
  JavaScript over a file at a guessable path gates the interface and not the data. **It must
  never be described as privacy**, because that would be the display rule broken in the
  place it would do most harm.
- **What a contributor actually needs in order to act is not a name.** It is *someone holds
  this, and for how long*. The name is useful in a small named cohort, where the answer to a
  contended basin is to message the person; it is exposure in a large volunteer pool of the
  GB1900 kind, where it discloses membership of the group to everyone in it.

**So: record the login always, render it by cohort, and say so at sign-in.** The interface
shows *another contributor* by default and the login where the cohort is small and named —
a setting decided by whoever runs the cohort, not emergent from what was easiest to code.
And the sign-in says plainly, in the same breath as the token warning, that **a GitHub
username is recorded on every contribution and is visible to everyone with access to this
repository.** That is consent, which is the real remedy; suppression in the UI is only
politeness on top of it.

**And the blind overlap needs an explicit exemption, which is the one thing to get right.**
§8 assigns a proportion of tasks twice, blind, to test whether snap-to-ink actually produces
agreeing lines. Those pairs must bypass the lock — but as a **property of the assignment,
decided in advance by whoever hands the work out**, never as a runtime override a
contributor can reach. An exemption a person can invoke is where locks go wrong; an
exemption baked into the link is one nobody has to think about.

**Deliberate overlap is a feature.** `docs/scale.md` claims that snap-to-ink makes two
tracings of the same channel substantially the same line. That claim is currently
untested, and it is the load-bearing claim under the whole volunteer strand — if it is
false, contributed geometry cannot be pooled. So a proportion of tasks is assigned twice,
**blind**, and blindness is fixed by the link rather than by a checkbox: an unanchored
agreement figure is worthless if half the contributors forgot to tick the box. The
resulting distance distribution between paired traces is a publishable result and a
precondition for trusting any of the rest.

**And agreement is not accuracy, which is the trap this measurement is most likely to fall
into.** The instance that makes it concrete is one of this plan's own: measuring
contamination in the mill queue (§4) returned **98.3%**, a figure that is stable,
reproducible, and reports the pattern I wrote rather than anything about the data — the
pattern contained the word `mill`, and so does every row by construction. Run it again and
it returns 98.3% again. **Reproducibility was no part of its being right, and a number that
never varies gives you no signal that it is wrong.**

The same is available here. If two contributors' snapped traces agree closely, that may be because
snap-to-ink follows the channel, or because **both followed the same artefact of the
algorithm** — the same darker bank, the same turnpike, the same generalisation of the
corridor. Consistency is what a deterministic algorithm produces whether or not it is right,
and a high agreement figure would be the most reassuring possible form of no evidence.

**So the measurement needs a control, and it is the same control `docs/scale.md` used to
make its own mill-channel finding credible.** Pair the tasks three ways, not one:

| pairing | what it measures |
|---|---|
| snapped against snapped | the number people will quote — and on its own, uninterpretable |
| **hand against hand**, snapping off | how much two people agree *without* the algorithm |
| **snapped against hand** | whether the algorithm moves the line toward the ink or away from it |

If snapped pairs agree far more tightly than hand pairs, that gap is the algorithm's
self-consistency and not its accuracy. If snapped and hand traces of the same reach differ
systematically in one direction — half a channel width, say, on a 25-inch sheet — that is
the bank problem showing up as a number rather than as a suspicion. **The third row is the
one that can falsify the tool**, and it is the one a study designed only to produce a
reassuring headline would omit.

---

## 9. Getting it back into the build

A later stage, deliberately unspecified here beyond its contract, because it is Stage 2
work and Stage 1 is not finished.

`python -m rewt contributions` reads the `traces` branch, folds each contributor's event
log into current state, validates, and writes `data/curated/traces/*.json` — hand-authored
files in the repository's existing idiom, diffable, each carrying a `reason` in words and
`evidence`. From there the ordinary rules apply: **never delete a geometry to correct it**,
and a trace supersedes rather than replaces — the old line stays, with `superseded_by`
pointing at the new one.

**Two of the three already exist.** rewt-6a has committed a credential scan over every
git-tracked file (df35ff4) — three shapes, placeholders allowed because a template showing
where a key would go is documentation and not a leak, and the patterns assembled from
fragments so the test file does not exempt itself from its own scan. And the exporter's
licence gate has been moved and strengthened: a source that may not be redistributed must
be marked for a later stage, declared by no stage, and say in words what is unknown about
it, and the gate is now tested against the real NLS source rather than a synthetic one.
**The practical consequence is that the machinery will let the tool cite those sheets and
will refuse to let anything derived from them reach an export.** Whether that is a
constraint or a description depends entirely on §10.1.

Three validations, the first of which is still to write once the schema is fixed, and all
of which must **fail the build, not warn**:

- **Every identifier validated against the database.** `AGENTS.md` records that a mistyped
  id does nothing while the stage reports success, that this happened twice in the
  predecessor, and once through a column nothing read so the error was invisible. A
  contributor's `replaces` field is that failure mode with a wider aperture and no way for
  the person who typed it to notice.
- **CRS stated, and no credential in any URL.** §2.
- **Every skip named.** A contributed trace whose target does not exist must be reported by
  identifier and by contributor, never silently dropped. Eleven of twenty-five corrections
  once did nothing silently in the predecessor, including the largest single defect in the
  country.

**Two fields phase 6 sets, both of which the build will enforce whether or not they were
set deliberately** — rewt-6a's, and they are the ruling expressed correctly rather than
accidentally:

- **`source_id = 'rewt'`, never the NLS source.** The exporter's gate exempts exactly one
  value — this project's own geometry, on the grounds that a feature we made has no
  publisher — and calls `require_redistributable()` on everything else. A traced line
  stamped `rewt` publishes; the same line stamped `nls_historic_map_tilesets` is refused
  with `UnlicensedSource`, because that entry is still `redistribution: not_established`
  and **Stephen's ruling was about the trace, not about the tiles**. The sheet is a
  citation in `evidence`, which is a fact and restricted by nothing; it must not become a
  `source_id`.
- **A fourth `origin` value, declared deliberately.** The published set is `survey |
  connector | skeleton`, and a traced course is none of those three. Adding a value is
  rewt-d3's call; what must not happen is a trace inheriting `connector` because the field
  was already there. rewt-6a's test asserts the set, so an undeclared value fails the
  build — which is the prompt rather than the obstacle.

**Binding is by name where possible and by geometry only as a fallback, and ambiguity is
reported rather than guessed.** If two candidate reaches match a trace's endpoints, nothing
is applied and the report says so.

---

## 10. Four decisions to take before any code

**Two are not mine.**

1. **~~The licence entry.~~ Recorded as D-043**, from Stephen's own words rather than a
   relay, with both rulings marked as readings and the three caveats carried unchanged. D-037
   is departed from explicitly rather than by silence. **A further entry describing the gate
   as built is still owed**, once phase 1 exists; I draft it, rewt-d3 lands it.

2. **~~Whether the predecessor's tracer may be lifted.~~ Granted, 1 Sep 2026.** Stephen's
   ruling: lift the three modules, record it as a decision, and adapt them where it makes
   sense. `AGENTS.md` says *do not import code or data from* the scoping exercise and D-001
   says carry across no code — but D-001's reasoning is about the audit, *an audit handed
   its answers is not an audit*, and **a drawing tool carries no answers**. The exemption is
   narrow: `tracer.js`, `raster.js`, `anno.js` — three UI modules whose own header says they
   know nothing about rivers. No data, no curated corrections, no network logic.

   **The entry is drafted and waits on Stephen's own tick**, not on a relay of it: its first
   line records a grant in his name, and an exemption is where a rule gets hollowed out, so
   a later reader should find his mark rather than someone's summary. The files are on disk
   and nothing is committed until then.

   **They are lifted unmodified, and adapted in a separate pass.** The exemption has a
   boundary and a reviewer must be able to see it; adapting while importing would mix
   inherited code with new in one commit and make that boundary unrecoverable. It is the
   repository's own rule that nothing is deleted to correct it, applied to an import. What
   needs adapting is already known and recorded in `js/README.md` — the 25-inch bank
   problem, the layer catalogue, the required fields, the date model, and the predecessor's
   own vocabulary — and none of it is done before the phase that needs it.

3. **~~Where the app lives.~~ Settled: `docs/trace/` is granted** (rewt-1d), and it needs
   **no `_config.yml` change at all**. Jekyll runs Liquid only over files that carry YAML
   front matter and copies everything else byte-for-byte, so an `index.html` with no front
   matter is safe from `{{` and `{%` by construction. Two consequences to hold onto rather
   than rediscover: **never add front matter to any file under `docs/trace/`**, not even an
   empty `---`/`---` pair, because that is the switch that turns Liquid on; and **`exclude:`
   is the wrong tool** if anyone proposes it — it means *do not publish*, not *copy without
   processing*, and it would delete the app from the built site. The nav is an explicit
   list, so nothing appears in it unless rewt-1d adds it.

   What remains of the question is **size**, which is Stephen's: 20–40 MB of committed
   PMTiles. The licence half of it is answered — the tiles are REWT's own network from
   declared open sources, and per §3 no sheet tile is committed at all.

4. **Token strategy.** Ship on classic PATs, which is what was asked and what works, and
   state the `repo` scope plainly to contributors. **The recommendation, which rewt-1d
   endorses independently, is to move the repository under an organisation before
   contributors are invited rather than after** — it is the only route to least-privilege
   fine-grained tokens, it is an administration change rather than a code change, and it
   converts an uncomfortable ask into an ordinary one. A five-minute decision with a large
   effect.

---

## 11. Phases

Each phase ends in something usable by one person; nothing waits on the phase after it.

| | what | ends when |
|---|---|---|
| **0** | Decisions §10. Draft the DECISIONS text; agree the `docs/` path; confirm the token route. | rewt-d3 has committed the licence entry |
| **1** | The shell: sign-in wall, token validation with the `github_pat_` detection and a message in words, the event log, IndexedDB, push and flush, export, the local-count-and-last-push header. **No map.** | one contributor can sign in, emit synthetic events offline, and see them arrive on the branch |
| **2** | The map: base network PMTiles, NLS second-edition backdrop, freehand tracing with no snapping, the annotation profile, bind-to-link. `snap_mode: hand` throughout, which is truthful. | a real *New Cut* task is traced end to end and lands in the log |
| **3** | Snap to ink: mosaic fetch, sheet classification, cost surface, corridor livewire, per-vertex provenance, the visible clicked/snapped distinction. | a snapped trace and a hand trace of the same channel are both in the log and can be compared |
| **4** | The queue: GB1900-derived tasks, fragment slices, the date bound computed and shown in words, skip-with-reason. | a coordinator can hand out a link and get work back |
| **5** | First-edition coverage: client-side county masking in a canvas, no tile ever stored. | a reservoir valley needing the first edition is traceable |
| **6** | Ingest: `rewt contributions`, the three validations, `data/curated/traces/`. | a contributed trace survives a rebuild |
| **7** | The agreement measurement: blind double-assignment, paired-distance distribution. | the claim in `docs/scale.md` is either supported or withdrawn |

### Every phase reports which sentences crossed from design to artefact

`docs/tracer.md` describes a settled design. As each phase lands, some of its sentences
stop being claims about a design and become claims about a running artefact — and **the two
need checking differently**. A design claim is checked by reading the argument; an artefact
claim is checked by using the thing.

So each phase ends by handing rewt-1d the list of sentences that crossed, and it is part of
the phase rather than a courtesy afterwards. Its ask, and it is a smaller one than
re-reading the page: check those, not the whole of it. **A page that is re-read entirely is
a page nobody re-reads.**

Two already identified, both rewt-1d's:

- **"Nobody types a year"** is true of the design and not yet of the code, because phase 1
  has no date field at all. It crosses at **phase 2**, when the annotation profile arrives,
  and what is then checkable is that the bound is computed from the sheet and shown back in
  words.
- **"Which vertices were placed by hand and which by the algorithm is visible *while
  tracing*"** crosses at **phase 3** — and it is the one most likely to **survive as a field
  and quietly not as a display**. The annotation will carry `vertex_origin` whether or not
  anything renders it, so the file will look correct while the contributor sees nothing.
  That is the display obligation degrading into provenance, which is the exact failure §4's
  rule exists to prevent, and it will not announce itself.

**And the shape generalises past this page.** A claim that is true of a design and false of
its implementation is not a lie anyone tells; it is a sentence that was accurate when
written and was never re-asked. Naming the crossing point at the moment it happens is the
only cheap time to catch it.

**Phases 1–4 are the tool.** 5 is what makes the reservoir strand possible. 6 is what makes
any of it count. 7 is what makes it defensible.

---

### Phase 1, as built — 1 Sep 2026

`docs/trace/`, build `0.1.3-p1`. The `traces` branch exists (orphan, one file) and
`8af5d7b` carries the first three contributed events.

**Proven end to end:** sign-in; the tree and blob reads; the `PUT`; and the shape of what
lands. Checked against the file on the branch rather than against the tool's own report —
every required field present, `synced` absent, CRS stated on every row, a coordinate on
every row, uuids unique, and the file already in `(created, author, seq, uuid)` order.

**Phase 1 is complete.** The offline flush and the 409 merge were the last two paths and
both are proven — `f9e5e4a` and `8133b52` on the branch, the second of which records in its
own message that it merged after a conflict.

**Tested by failing the network at the app's boundary, not by unplugging anything.**
`window.fetch` was made to reject for `api.github.com` only, which is what offline actually
looks like to a page; then restored, with `online` dispatched and nothing clicked. The 409
was a synthetic stale-sha response returned to the first `PUT` and no other. That is better
than a real disconnection in three ways: it is repeatable, it isolates one dependency
instead of the whole machine, and **the conflict case cannot be produced by unplugging at
all** — it needs a second writer.

What it established, each checked against the file on the branch rather than the tool's
report: an event recorded offline is held and not lost; **the last-saved time does not
falsely advance on a failed push**, which is the one thing a contributor would use to
decide whether to redo work; the flush happens on reconnection with nothing clicked; and a
conflict loses no event and duplicates none, with fold order surviving the merge.

**Three defects found by building it, each worth more than the code.**

- **`Authorization: token …` is dead.** GitHub answers 401 *Bad credentials* to the legacy
  scheme, which is indistinguishable from an expired token and sends you to mint a new one
  that fails identically. Inherited from the London Customs Accounts editors, written when
  it worked. `Bearer` throughout, with the measurement in the comment.
- **A 404 on the branch tree has two causes and the API will not separate them** — the
  token cannot see the repository, or the repository is visible and the branch does not
  exist. The first version reported both as a token problem, which is the same
  404-is-ambiguous trap the token advice exists to avoid, one level down, and it would have
  greeted the first contributor with a message about their token when nothing was wrong
  with it.
- **The error path kept the advice and threw away the facts.** Messages written for a
  contributor say what to do, and in saying it drop the status, the URL and GitHub's own
  words. Two round trips were spent on that. Every failed request now logs one flat line:
  which call, the status, GitHub's message, the scheme, the scopes carried against the
  scopes wanted, SSO, and the rate limit.

**And a fourth that was not in the code at all.** Four times in one day a confident
negative came from a single unchecked instrument: a contamination figure that measured its
own pattern, a basin count compared against the wrong quantity, a credential condemned by a
diagnostic carrying the same bug, and a branch read as empty because the tree endpoint
served a cached view. **When a check reports that something did not happen, that is the
case needing a second and independent instrument** — absence is precisely what a stale or
misconfigured reader returns.

---

## 12. What would falsify this plan

- **Snapped traces by two people do not agree.** Then contributed geometry cannot be
  pooled, the volunteer strand collapses to *identified but not dated*, and phase 7 has
  told us so before several hundred people were recruited. This is why 7 exists and why it
  should not be last in practice even though it is last in the table.
- **NLS say no.** Then the second-edition seamless layer is unavailable to a published
  tool and the first edition with it. The tool still works against any other backdrop, and
  the question becomes which. Better to know before deployment.
- **Contributors will not create a classic `repo`-scope token.** Entirely possible, and
  reasonable of them. The mitigation is the organisation move or the GitHub App, and the
  signal will appear in phase 1 with nothing else built on top of it.
- **Client-side county masking is too slow to trace against.** Phase 5 is the only place
  this bites, and it is isolated. The fallback is not pre-baking — §3 forbids that — but
  narrowing: one county at a time, chosen explicitly, unmasked, which is what rewt-fc's
  viewer already offers and what a contributor working through a county's reservoirs
  actually wants.
- **The ruling on §2 is revisited, or NLS answer that a trace is a derivative after all.**
  Then no traced geometry may enter `data/curated/` or any published artefact — the
  exporter already enforces this and is now tested doing it — and the tool falls back to
  producing **evidence rather than geometry**: citations, observations at a place, and date
  bounds, which are facts and which no licence restricts. `docs/scale.md` already
  contemplates publishing the mill channels as *a class identified but not dated*. **This
  is survivable only because the log keeps the citation and the provenance as first-class
  fields**, so the cautious product is extractable from work already done without
  re-contacting anyone. That is a design constraint, not a consolation, and it is the
  reason those fields are not derived.
