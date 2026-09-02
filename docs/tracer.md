# The tracer

**The tool that lets a reader draw a channel off a Victorian sheet, and the reasons it is
built the way it is.** [The scale of the work](scale) says why it has to exist: the
labelled mill channels alone are some 4,068 places, an order of magnitude larger than
everything above them on that page, and there is no route to finishing them that does not
involve many hands.

> **Deployed, and part-built.** A contributor signs in at
> [the tracer](https://docuracy.github.io/REWT/trace/), a historic sheet is drawn, and a line
> can be traced on it — by hand, or with either of two assists that **choose themselves from
> what the surveyor drew**: centring a vertex where the channel is a pair of banks, following
> the ink where it is a single stroke, and **neither where the pixels support neither**, which
> leaves the straight line the contributor drew. Each shows its own work while tracing, and what is
> recorded arrives as an append-only log in this repository's own history — public the moment
> it is saved.
>
> **What does not exist:** the work queue, the basin hold, and the binding of a trace to the
> network link it supersedes. That last is a dependency rather than an omission: the field
> takes a publisher's identifier typed by hand, because the base network is not fetchable
> until it ships as a release asset.
>
> **And the measurement that matters has not been made** — a proportion of tasks assigned
> twice, blind, to test whether two people produce substantially the same line. **Every
> argument on this page for pooling contributed geometry rests on that measurement rather
> than on the tool existing**, and the tool now existing does not advance it.
>
> This site has had to correct a sentence describing tooling as existing when it existed
> somewhere else, and then a sentence still denying tooling after it was built. Both are the
> same fault. Where a section below describes something not yet built, it says so.

## What a contributor actually does

One place, one sheet, one channel. A task is a place where the Ordnance Survey lettered
*Old Course*, *New Cut* or a mill leat; the tool shows the historic sheet for it and asks for
two things: the line the sheet draws, and a statement of what that line replaces. **The
handing out is the part not yet built** — the [work
queue](scale#old-courses-the-victorian-surveyors-labelled) that turns those labelled places
into tasks is phase 4, and until it exists a contributor arrives at a place rather than being
sent to one.

**It is not an editor of the modern network, and must never become one.** A contributor
draws a channel that a sheet shows. They cannot move, delete or re-attribute anything in
the network the first edition publishes. Correcting the modern survey is a different job
with a different failure mode and a different tool, and conflating the two would put a
volunteer's mouse on the output of a stage that makes no historical claim at all.

**Nobody types a year.** The tool computes the bound the evidence actually supports — a
sheet surveyed in 1885 establishes that a channel was there *by* 1885, and nothing about
when it began — and shows that back in words before recording it: *this says the channel
existed by 1885, and nothing about when it began.* A free-text year field invites a guess,
and a guess is indistinguishable from evidence once it is in the file.
[How a date is recorded](epochs#how-a-date-is-recorded) is the model behind that.

**Where the sheet has no survey year, it says so rather than saying nothing.** That is the
normal case for the seamless layers, which are composites of many sheets and so carry no
single survey date, and it matters because the two silences are different: an absent bound
reads as *deliberately unbounded*, and what is true here is *nobody knows*. The tool records
an explicit unknown.

**And a computed date is not automatically an honest one.** Taking the typing away removes
one failure and opens another, in the direction nobody watches: not a contributor inventing
a date, but the tool inventing one on their behalf and presenting it as measured. A missing
survey year that coerces to zero yields a perfectly well-formed bound asserting the channel
existed by the year nought — plausible in shape, checkable by nothing, and far more
convincing on a screen than a guess a person typed. The refusals have to be tested, not
designed.

## Why snapping exists, and what it is not

**So that two people tracing the same channel produce substantially the same line.** That
is the whole reason the tool is a tool rather than a form. Without it, contributed geometry
from different hands is not comparable and cannot be pooled.

**That is a claim, and it is currently untested.** It is also the load-bearing claim under
the entire volunteer strand, so the tool is built to test it rather than assert it: a
proportion of tasks is assigned twice, **blind**, and the distance between the resulting
pairs of traces is measured. Blindness is arranged by how the work is handed out rather
than by asking people to tick a box, because an agreement figure is worthless if half the
contributors forgot. That distribution is a publishable result in its own right, and a
precondition for trusting anything else contributed.

## Two people, one basin

**This section describes a design, not an artefact.** The basin hold is phase 4, alongside
the queue that would hand the basins out; what follows is the shape it is specified to take
and the reasoning that fixed it, which is worth writing down before it is built rather than
after.

Work is handed out **a basin at a time**, and a contributor holds it while they are in it.

The basin is the unit because it is the unit a *person* learns: its drainage pattern, the
sheets that cover it, the local vocabulary for a mill channel. The second hour in a basin is
faster than the first, and scattering somebody across the country throws that away — forty
places in forty valleys are forty unrelated ten-minute puzzles, where forty places in one
valley are an afternoon's work in a landscape you have come to know.

**The hold is a real one rather than a courtesy.** It is taken atomically, so two people
cannot both believe they have it, and it **lapses after thirty minutes without activity**.
The timeout is deliberately long: the drawing is quick and the deciding is slow, and a
timeout tuned to the drawing would take a basin away from someone in the middle of reading a
sheet. A lapsed hold can be claimed by anyone, and the record says who took it from whom, so
an abandoned basin resolves itself without anybody administering it.

Whether the screen shows a **name** or only *someone else* is a setting, and the honest thing
to say about it is that showing less is a **courtesy and not a protection**: the record is
readable by anyone with access to the repository, so not rendering a name changes what is
polite and not what is disclosed. What a contributor needs in order to act is *someone holds
this, and for how long* — the name is useful in a small named group and is exposure in a large
one.

**The interface never says *locked*.** It says who holds it and how long is left, because
that is what is actually known.

**And two people in one basin is sometimes correct.** The hold prevents *accidental*
double-work; it does not prevent the deliberate kind, which is [how the agreement between
two tracings is measured](#why-snapping-exists-and-what-it-is-not) and is arranged when the
work is handed out rather than by anyone overriding anything. A reader who meets the hold
without meeting the overlap would conclude the tool forbids two people on one channel. It
does not — it arranges that on purpose, blind, and reports the distance between what they
draw.

## How the ink is followed

**Most of these sheets are monochrome outline editions**, so a detector looking for blue
water finds nothing on them. The tool therefore decides which method applies **from the
pixels in front of it rather than from the sheet's name** — and on a monochrome sheet the ink
it follows describes roads, railways and parish boundaries just as readily as rivers, which
is why it may only search among ink the contributor has already pointed at. It is confined
to what a person indicated; it does not go looking.

<figure class="sheet-figure narrow">
  <div class="frames">
    <img src="{{ '/assets/maps/tracer-lea-at-ware.jpg' | relative_url }}"
         alt="The tracer on the six-inch second edition at Ware: a traced line along the Lea past the wharves, seven of its vertices drawn solid where a hand placed them and six drawn hollow where the tool moved them to the middle of the channel, each ringed in white so it stays legible where it falls on printed ink.">
  </div>
  <figcaption><strong>Both operations, in one line, chosen vertex by vertex.</strong> The Lea
  at Ware past the wharves, on the six-inch. <strong>Seven vertices are left where the hand put
  them; six are moved to the middle and drawn hollow.</strong> That split is the honest part —
  a frame in which every vertex had been moved would be a frame of a tool that had stopped
  discriminating. The clicks are the ones already recorded in the paired traces, replayed
  rather than composed for the photograph, and the line under the map is the tool's own
  account of what it just did. Every marker carries a white ring, which is why the ones
  crossing the lettering of <em>Wharves</em> can still be read.
  <span class="credit">Reproduced with the permission of the National Library of
  Scotland.</span></figcaption>
</figure>

**Both operations belong on the six-inch**, then, chosen per reach rather than per sheet:
Ordnance Survey draws a channel as one line below a certain *ground* width and as two banks
above it, so a single sheet carries both — a leat as one stroke, a navigable river as a pair
of banks. A tool that decided between them by which sheet was loaded would be wrong on every
wide river.

**Two reasons the six-inch is the surface**, and neither is about resolution. The
[work queue](scale#old-courses-the-victorian-surveyors-labelled) is a transcription of the
six-inch's *own* labels, so every task points at something lettered on those sheets — send a
contributor to a different survey and they are hunting for a caption that is not there. And
the six-inch is served seamlessly across England and Wales where the 25-inch is county by
county, so a national queue meets a national sheet. **Finer is the wrong axis; the sheet that
carries the task is the right one.**

The interface says as much where a contributor will read it: *a leat is a single stroke and a
navigable river is a pair of banks, often on the same sheet.*

**And here is the limit, which is not a bug to be tuned away.** Two roughly parallel lines a
constant distance apart are a channel — and are also a lane, a gap between terraces, a
railway. **No test of the local pixels separates them.** Asked for the strongest such feature
anywhere in Ware, the assist returns a railway — and is correct about the geometry in every
particular. What supplies the missing knowledge is the
contributor, who knows they are following a watercourse. Nothing in the raster does.

**It is an assistant, not an interpreter**, and the interface says so rather than leaving it
to be inferred. Three consequences follow, and they are design rules and not caveats:

- **Snapping is a separate switch from tracing.** Ink runs out, forks, and is crossed by
  roads. Where it does, the only honest line is one a person draws, and the tool must let
  them draw it without pretending otherwise.
- **Blank paper is never snapped to.** Outside coverage, or where a tile is refused, a
  uniform field produces a confident-looking line and a false account of how it was made.
  The tool refuses rather than obliges.
- **Which vertices were placed by hand and which by the algorithm is visible while
  tracing**, not only recorded in the file. A machine-placed vertex looks more authoritative
  than a drawn one and is not — it is a reading of ink a person pointed at. The
  person most likely to over-trust it is the contributor, in the moment, and a provenance
  field only a later reader sees does nothing for them. **This one is built**: a hand's
  vertex, a moved one and a followed one each draw differently, and a machine-laid run is
  drawn to look like less of a judgement than a placed point, because that is what it is.

## What the gate is, and what it is not

Access to the tool is controlled: invited contributors, and their traces recorded to this
project under their own names — which is the point, since [contributed work appears under its
contributor's name](aims#publication), and is also a disclosure. **A contribution records a
GitHub username, and that record is visible to everyone with access to this repository.** It
is said at sign-in rather than discovered afterwards, because consent is the remedy and
concealment would not be one.

**How a contributor is admitted is not settled**, and this
page will say what it actually asks of them when it is — including the cost, if there is
one. It should not be read as *sign in with an account you already have* until it says so.

**It does not restrict access to the maps.** The historic sheets are served by the National
Library of Scotland and anyone at all can fetch them, without a key and without asking us.
The gate governs **who uses this tool and where the traces go** — nothing more. A page
implying that the gate protects the sheets would be false, and it is the easiest false
thing to imply by accident on a page about a tool that shows them.

The terms on which those sheets are served [could not be traced](evidence#maps-that-show-the-valley-before-the-dam),
and what this project does about that is recorded rather than assumed.

## What a trace carries

Every contributed line records the sheet it was read from, which vertices a hand placed and
which the algorithm did, who drew it, and when. That is partly so a reader can weigh it —
and partly because [this project's reading of what a traced line
is](evidence#licensing-and-why-this-repository-is-structured-as-it-is) is a ruling rather
than a settled question, and those fields are what would let a source-restricted version of
the dataset be extracted later without re-tracing anything.

Contributions reach the dataset as [curated files](methodology#principles) in the
repository's existing idiom — diffable, each with a reason in words and its evidence — and
under the ordinary rule: **nothing is deleted to correct it.** A trace supersedes; the line
it replaces stays in the record, marked as superseded, because a reader has to be able to
tell a correction from an omission.

---

| | |
|---|---|
| [The scale of the work](scale) | why the tool exists, and how much there is |
| [Evidence](evidence) | what the sheets can say, and on what terms |
| [Temporality](epochs) | how a date is recorded, and why nobody types one |
