# Lifted modules

These three files are **carried across verbatim from the scoping exercise**
(`premodern-rivers/docs/js/`), under an exemption from `AGENTS.md`'s rule that no code is
imported from it. Stephen granted it on 1 Sep 2026; the reasoning is in `../PLAN.md` §10.2.

**The `DECISIONS.md` entry is drafted and awaiting his own tick rather than a relay of it**
— rewt-d3's call, and the right one: the entry's first line records a grant in his name, and
an exemption is exactly where a rule gets quietly hollowed out, so it should carry his mark
and not a summary of it. **Nothing here is committed until it does.**

| file | lines | what it is |
|---|---:|---|
| `tracer.js` | 418 | the MapLibre tracing mode: click to place, snap between, per-vertex provenance |
| `raster.js` | 362 | tile mosaic, sheet classification, cost surface, corridor livewire |
| `anno.js` | 231 | the W3C Web Annotation profile for georeferenced traces |

## Why they are unmodified

**So the diff shows what REWT changed.** The exemption is narrow — three UI modules, no
data, no curated corrections, no network logic — and a reviewer must be able to see its
boundary. Adapting while importing would mix inherited code with new code in one commit and
make the boundary unrecoverable. This is the same reasoning as the repository's own rule
that nothing is deleted to correct it: the prior state stays, and the correction is legible
against it.

**Nothing here runs yet.** They are wired in at phases 2 and 3.

## What is known to need adapting, and when

- **`raster.js`, phase 3 — the 25-inch bank problem.** The cost surface follows ink, and at
  1:2,500 a watercourse is drawn as two bank lines with white between them, so a corridor
  livewire returns a line offset by half the channel width. The surface these modules were
  written against was the six-inch, where a channel is one line and following ink is
  correct. See `../PLAN.md` §4 and §7 for the three candidate remedies; the choice is an
  experiment, not a decision already taken.
- **`raster.js`, phase 3 — the layer catalogue.** It takes a tile template from a caller
  holding `backdrops.json`. REWT's source of fact is `tools/nls_layers.json`, whose
  `bounds` are observed at zoom 9 and are a hint rather than a containment test.
- **`anno.js`, phase 2 — the required fields.** The profile predates three of this
  repository's rules: `author` and `dated` are mandatory on a judgement, every record
  carries a coordinate, and contributed geometry is stamped `source_id = 'rewt'` with the
  sheet as a citation in `evidence` and never as a source id.
- **`anno.js`, phase 2 — the date.** It has no date model. REWT records an LPF bound
  computed from a lookup, never a year typed by a contributor, and `unknown` where a
  seamless layer has no single survey date.
- **`anno.js`, phase 2 — it does not own its identifier scheme, and must.** It takes
  `identifying` as an opaque `{source, label}` and leaves the caller to compose the URN —
  the predecessor does it in one template literal 1,885 lines into a UI module. That is
  D-051's shape, and a wrong separator in a URN stays legal and stops resolving. An
  `ids.js` owns them, a grep test enforces it, and a test asserts it agrees with
  `rewt/ids.py` string for string.
- **`anno.js`, phase 2 — the vocabulary.** `urn:premodern-rivers:replaces:` and the
  `DECISIONS.md` references in its comments are the predecessor's, and resolve to nothing
  here.

## What must not be adapted away

**The credential refusal** (`assertNoCredential`). It refuses loudly rather than
sanitising, and that is correct: a caller passing a keyed URL has made a mistake worth
seeing, and a quietly stripped key teaches nothing. `tests/` scans every tracked file for
the same thing; this is the check at the other end of the pipe.

**`conformsTo` being required rather than defaulted.** A course whose CRS is unstated is a
course whose numbers mean nothing.

**The per-vertex `clicked`/`snapped` distinction, and `snapMode: 'hand'`.** These are not
only provenance. They are the display obligation: a snapped line looks more authoritative
than a drawn one and is not, and the person most likely to over-trust it is the contributor
in the moment.
