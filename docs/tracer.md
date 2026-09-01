# The tracer

**The tool that lets a reader draw a channel off a Victorian sheet, and the reasons it is
built the way it is.** [The scale of the work](scale) says why it has to exist: the
labelled mill channels alone are some 4,068 places, an order of magnitude larger than
everything above them on that page, and there is no route to finishing them that does not
involve many hands.

> **Part-built and not deployed.** What exists: a contributor signs in, a historic sheet is
> drawn, a line can be traced on it by hand, and what they record arrives as an append-only
> log in this repository's own history. **Both assists are working** — one centres a vertex
> in the channel and reports its width, the other follows the printed ink inside a corridor
> the contributor drew — and each shows its own work while tracing.
>
> **What does not exist:** the work queue, the basin hold, and — the one that matters —
> **the paired blind trace that measures whether two people produce the same line.** That
> machinery exists and the measurement does not, which is the gap to watch, because the
> argument for pooling contributed geometry rests on the measurement rather than on either
> assist. There is no public address to visit.
>
> This site has had to correct a sentence that described tooling as existing when it existed
> somewhere else, and then a sentence that went on denying tooling after it was built.
> Overstating in the other direction is the same fault. Where a section below describes
> something not yet built, it says so.

## What a contributor actually does

One place, one sheet, one channel. The tool hands out a task from a [work
queue](scale#old-courses-the-victorian-surveyors-labelled) — a place where the Ordnance
Survey lettered *Old Course*, *New Cut* or a mill leat — shows the historic sheet for that
place, and asks for two things: the line the sheet draws, and a statement of what it
replaces.

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

The obvious approach does not work. **On these sheets the median blue fraction is 0.000%**
— roughly one in twenty is a coloured printing and the rest are monochrome outline
editions, where a blue-water detector finds nothing at all. What makes it tractable is that
the distribution is *bimodal*: a tile reads either exactly zero or several per cent, with
almost nothing between, so the sheet type can be decided from the pixels at the moment of
use and the right method chosen — follow blue where it exists, follow ink darkness where it
does not.

**On a monochrome sheet, ink darkness describes roads, railways, contours and parish
boundaries just as well as it describes rivers.** A shortest path across such a sheet will
set off down a turnpike without hesitation. What makes it usable is a **corridor**: the
search is confined to a band around the straight line between the vertex just placed and
the cursor, so the algorithm may only choose among ink the contributor has already pointed
at.

**And a finer sheet is not automatically a better one to follow.** On the
[25-inch](evidence#the-25-inch-is-not-a-better-six-inch) a channel above a modest width is
drawn as two banks with the water between them, so ink-following locks to one bank and
returns a line half a channel-width out — sharper raster, systematically wrong answer. Where a
sheet is coloured the water can be segmented on hue instead — but **which sheets are coloured
cannot be predicted from the scale**, and varies in both directions between the two series,
so that too has to be decided from the pixels rather than assumed.

<figure class="sheet-figure narrow">
  <div class="frames">
    <img src="{{ '/assets/maps/tracer-lea-at-ware.jpg' | relative_url }}"
         alt="The tracer on the six-inch second edition at Ware: fourteen vertices along the Lea past the wharves, ten solid pink where a hand placed them and four hollow and cyan-ringed where centring moved them, with the message: moved 0.4 m to the middle, the channel is 25.8 m wide here, measured across 7 transects.">
  </div>
  <figcaption><strong>Both operations, in one line, chosen vertex by vertex.</strong> The Lea
  at Ware past the wharves, on the six-inch. Fourteen points: <strong>ten left where the hand
  put them</strong>, four moved to the middle and drawn hollow. The tool decides from the ink
  under each vertex, not from which sheet is loaded — and the ratio is the honest part. A
  frame in which every vertex had been centred would be a frame of a tool that had stopped
  discriminating. Traced by a contributor, not staged for the photograph.
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

**What the assist is calibrated on is one trace of one reach**, and it says so in its own
code. The constants that decide when a corridor counts as a channel rest on that single
piece of evidence, so they are a starting point rather than a measurement — and the first
thing a second reach may do is move them.

**And here is the limit, which is not a bug to be tuned away.** Two roughly parallel lines a
constant distance apart are a channel — and are also a lane, a gap between terraces, a
railway. **No test of the local pixels separates them.** Asked for the strongest such feature
anywhere in Ware on the 25-inch, the assist returns the railway between the goods shed and the
signal posts: 206 accepted points, a continuous 500 m run, a median width of 17.4 m, and
correct about the geometry in every particular. What supplies the missing knowledge is the
contributor, who knows they are following a watercourse. Nothing in the raster does.

**It is an assistant, not an interpreter**, and the interface says so rather than leaving it
to be inferred. Three consequences follow, and they are design rules and not caveats:

- **Snapping is a separate switch from tracing.** Ink runs out, forks, and is crossed by
  roads. Where it does, the only honest line is one a person draws, and the tool must let
  them draw it without pretending otherwise.
- **Blank paper is never snapped to.** Outside coverage, or where a tile is refused, a
  uniform field produces a confident-looking line and a false account of how it was made.
  The classifier refuses rather than obliges.
- **Which vertices were placed by hand and which by the algorithm is visible while
  tracing**, not only recorded in the file. A machine-placed vertex looks more authoritative
  than a drawn one and is not — it is a reading of ink in a corridor a person pointed at. The
  person most likely to over-trust it is the contributor, in the moment, and a provenance
  field only a later reader sees does nothing for them. **This one is built**, and it
  distinguishes three origins rather than two: a vertex a hand placed draws solid, one moved
  to the middle of the channel draws hollow, and one the ink-following produced draws hollow
  and **smaller** — deliberately, because a run of thirty vertices laid down in one step was
  nobody's decision and should not carry the visual weight of a judgement. A line of text
  says how far a vertex moved and how wide the channel was found to be.

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
