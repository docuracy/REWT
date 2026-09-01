# Sources

**Every dataset registered for use here, who made it, and the credit its licence
requires.** This page is generated from `conf/sources.yml` — the file the code itself
reads — so it cannot fall behind what the build is declared to use. Nothing is typed
here by hand.

**An unregistered source is a hard error rather than a warning.** A stage that reaches for
data with no declaration in the manifest fails; it does not proceed with a note in a log.
That rule exists because unattributed provenance is not provenance, and because a
credit added later is a credit that was owed in the interval.

**Registered is not the same as used**, and the difference is worth stating rather than
leaving in a column. {{ site.data.sources.count }} sources are declared;
{{ site.data.sources.verified_count }} have been fetched and pinned so far. A declaration
comes first — the licence researched, the attribution recorded, the terms settled — and the
fetch follows, sometimes by months. So this is the list of what may be used and on what
terms, not a claim that every line of it is in the current build.

What each source can and cannot say — a different question, and the interesting one — is
argued on [Evidence](evidence).

## The credit each source requires

**These strings are obligations, not courtesies.** Where a licence specifies the wording of
an attribution, the wording is reproduced exactly as the publisher requires it, and it
travels with every derived file rather than living only on this page.

**What a given release actually owes is narrower than this list**, and is published with the
data as `published/ATTRIBUTION.md` — restricted to the sources that release's build genuinely
consumed, because crediting a registered-but-unused source is itself a false statement about
where the data came from. Both are generated from the same manifest, and each is checked
against it rather than against the other: two renderings that agree with one another and
disagree with the manifest is exactly the case that credits the wrong people.

{% for s in site.data.sources.sources %}{% if s.attribution %}
**{{ s.title }}**
: {{ s.attribution }}{% if s.attribution_constructed %} *(Assembled by this project from the
  publisher's citation guidance rather than quoted from a stated attribution string — so it
  is our reading of what is required, and a correction to it is welcome.)*{% endif %}
{% endif %}{% endfor %}

## Every registered source

| Source | Made by | Licence | Terms |
|---|---|---|---|
{% for s in site.data.sources.sources %}| [{{ s.title }}]({{ s.homepage | default: s.url }}){:target="_blank"}{% if s.doi %}<br>[doi:{{ s.doi }}](https://doi.org/{{ s.doi }}){:target="_blank"}{% endif %} | {% if s.author %}{{ s.author }}{% if s.year %} ({{ s.year }}){% endif %}<br>{% endif %}{{ s.publisher }} | {{ s.licence }} | {{ s.access }}, redistribution **{{ s.redistribution_label }}**{% if s.use_constraint %}<br>*{{ s.use_constraint }}*{% endif %} |
{% endfor %}

## What the terms mean here

**Redistribution is the field that matters**, because it governs the only thing this project
does that a reader sees: publishing a derived file. *Permitted* means a dataset built on that
source can be released openly under this project's own terms, with the attribution above
carried through. *Not established* means it cannot — the source may be read and worked
against, but nothing derived from it may be published until a term is found or granted.

{% if site.data.sources.unsettled_count > 0 %}
**{{ site.data.sources.unsettled_count }} of the {{ site.data.sources.count }} {% if site.data.sources.unsettled_count == 1 %}is not settled{% else %}are not settled{% endif %}**, and the manifest says so rather than leaving it to be discovered:

{% for s in site.data.sources.unsettled %}
- **{{ s.title }}.** {{ s.licence }}
{% endfor %}

Until that is resolved, such a source is usable for reading the ground and unusable for
anything published — a distinction the
[Evidence](evidence#licensing-and-why-this-repository-is-structured-as-it-is) page sets out
in full, because it shapes how this repository is arranged rather than merely what it ships.
{% else %}
**Every registered source may be redistributed**, with its attribution carried through.
{% endif %}

**`use_constraint` is narrower than a licence and is not one.** Where it appears, the
publisher permits redistribution but forbids a *purpose* — the bathymetry carries
`DO NOT USE FOR NAVIGATION`, which is why the sea structure built from it is named for the
clearance it was measured at rather than for anything a vessel could do with it.

**Status is about this project, not about the source.** *Verified* means these bytes have
been fetched here and their checksum recorded, so a rebuild gets the same input or fails
loudly. *Unverified* means the declaration has been researched and the fetch has not yet
happened — the terms are established, the file is not yet pinned.

## Why the list is short

**It is short on purpose.** Every source here is one whose licence permits an open derived
release, and several obvious candidates were rejected on exactly that test rather than on
quality: share-alike gazetteers that would carry their terms into everything downstream, and
a national navigation dataset that can be read and measured but whose derivatives cannot be
shared. The reasoning for each is recorded on [Evidence](evidence), including the ones this
project would have liked to use.

---

*Generated from `{{ site.data.sources.generated_from }}` by `{{ site.data.sources.generator }}`.
To correct an attribution, edit the manifest and regenerate — an edit to the page is
overwritten at the next build.*

---

| | |
|---|---|
| [Evidence](evidence) | what each source can and cannot say, and on what terms |
| [Methodology](methodology) | how they are assembled, and why the order matters |
| [The scale of the work](scale) | what the sources cover, and what they leave to volunteers |
