# REWT

**Rivers of England and Wales, Temporally.**

A reconstruction of the river network of England and Wales as it stood at a series of
dated cross-sections between Domesday and 1900 — built so that the water in it can
actually get to the sea.

It starts from the river as it is **today**. The base network is the current Ordnance
Survey product, reissued twice a year, and the first thing built from it is a modern
network in which water can be followed from any stretch to the tide. That carries no
historical claim whatever. The historic cross-sections are then worked *backwards* from
it against dated evidence — so 1900 is where the map record begins, not where the
dataset stops.

---

## What this is

Most historical river mapping draws lines. This draws a **network**: every channel joined
to the next, every stretch carrying a modelled flow, and the whole thing routable from
any headwater to the tide. That distinction turns out to matter more than it sounds, and
[the methodology](methodology) explains why.

A network rather than a set of lines is what makes the interesting questions askable at
all. Because every reach carries a modelled flow, a fall and — where the evidence allows — a
[dated navigability](evidence#navigation), the same dataset answers *where could water be made
to work* and *what could be carried, from where, at what cost*. Those are questions about
milling, settlement and industrialisation rather than about rivers, and no open dataset has
been able to put them on the same lines.

It is assembled from open, evidenced sources — the modern [Ordnance Survey](https://www.ordnancesurvey.co.uk/products/os-open-rivers){:target="_blank"}
network, [GB1900](http://www.gb1900.org/){:target="_blank"} volunteer transcriptions of Victorian map labels, [historic sheets](https://maps.nls.uk/os/6inch-england-and-wales/){:target="_blank"}
traced by hand, and the documentary record of drainage and navigation works — with **every
line carrying what it rests on**. Where the evidence runs out, the map is meant to show that it has run
out.

## Why it is difficult

The modern hydrographic network of lowland England is largely an artefact of the last
four centuries. Channels have been straightened, embanked, cut anew, diverted for mills
and navigation, and in the Fens and the Humberhead Levels very largely **replaced** — the
water sent an entirely different way. Recovering the older courses means treating the
modern survey as the *least* reliable evidence in exactly the places where most has
changed.

## Where to start

| | |
|---|---|
| [Aims](aims) | what this will produce, for whom, and in what order |
| [Methodology](methodology) | how the network is built, and why the order of work is the finding |
| [Evidence](evidence) | the sources, what each can and cannot say, and their licences |
| [The rebuilt landscapes](regions/) | the Fens, the Humber, Somerset and the rest — where the modern channel is worthless, and what records survive |
| [Temporality](epochs) | which dates get published, and why an epoch is a build rather than a filter |
| [The scale of the work](scale) | how much can be done in house, and where volunteers become necessary |
| [The tracer](tracer) | the tool contributors will draw with, and why it is built that way |
| [Background](background) | the proof-of-concept that preceded this, and what it established |

## Status

**What exists is recorded with the releases**, on [the repository](https://github.com/docuracy/REWT){:target="_blank"}, and not restated here — a
page that describes the state of a thing is wrong from the first time the thing changes, and
goes on looking authoritative while it is. The shape of the plan is [editions and
epochs](epochs): the first edition is the modern survey repaired into a network water can be
followed through, and it makes no historical claim at all.

**The same applies to every figure on these pages.** Each is of the build it was taken from
and says so; the audit published with the data is the authority. A number written into a page
drifts, and drifting while looking authoritative is this project's own recurring failure — not
one to reproduce in its documentation.

It was built from a clean sheet after a scoping exercise that established the approach and,
more usefully, [what goes wrong](background).

---

*Stephen Gadd, [Docuracy Ltd](https://docuracy.co.uk).*
