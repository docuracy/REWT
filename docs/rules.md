# The rules

**Every general rule this project works to, in the order they apply to the network.**
This page is generated from `conf/rules.yml` — the file the build itself reads — so it
cannot say the build does something the build does not do. Nothing here is typed by hand.

**It is not in the navigation, deliberately.** The rules are working material rather than
an argument, and the pages that make the argument — [Methodology](methodology) above all —
link to individual rules by identifier. This is where those links land.

## Why there is a list at all

**A defect found at one place is repaired everywhere or it is not repaired.** The
temptation with a network of this size is the targeted fix: the junction is wrong, so mend
the junction. That produces a network which is correct at every place anybody has looked
and unexamined everywhere else, and it leaves no way to tell the two apart afterwards.

So an observation becomes a *rule*, stated generally, applied across the network, and
recorded with the reasoning that produced it. What was observed stays in `rules/` in the
words of whoever observed it, and is never edited to match the rule it produced — the
intake and the conclusion are different things and each is worth keeping.

**A rule carries no threshold.** Where a rule needs a number it names the parameter by its
path into `conf/params.yml` and the number lives there, once. A threshold written in two
files is a threshold that will eventually disagree with itself, which is the same argument
that makes this page a projection rather than a copy.

**A rule holds no judgement about a particular river.** Those live in `data/curated/`, as
diffable files with a reason in words and evidence naming a place, a source, or a person
and the date they looked. What is here is the general rule such a judgement is an instance
of.

## What the statuses mean

**`status` says what is true of the build now, not what anybody intends.** A rule is
`implemented` only when the module that applies it is named and the audit can show where.
Of the {{ site.data.rules.count }} rules below, {{ site.data.rules.implemented_count }}
{% if site.data.rules.implemented_count == 1 %}is{% else %}are{% endif %} implemented.

{% for s in site.data.rules.status_vocabulary %}
**{{ s.term }}**
: {{ s.meaning }}
{% endfor %}

And `kind` says what applying a rule would change:

{% for k in site.data.rules.kind_vocabulary %}
**{{ k.term }}**
: {{ k.meaning }}
{% endfor %}

## The order is the sequence, not a ranking

**Rules apply to the network in the order below**, which is not the order they were raised
and is not a priority. R-01 redefines the sea before any connector is invented, because a
connector built against the wrong sea is wrong in a way no later rule can detect. Where
the order does not matter the numbers still run consecutively.

## The rules

{% for r in site.data.rules.rules %}
### {{ r.id }} · {{ r.title }}

*{{ r.kind }} · {{ r.status }}{% if r.stage %} · applies at the `{{ r.stage }}` stage{% endif %}{% if r.evidence_count > 0 %} · stands on {{ r.evidence_count }} named row{% if r.evidence_count != 1 %}s{% endif %} of evidence{% else %} · **no evidence rows named**{% endif %}*

{{ r.statement }}

**Why.** {{ r.why }}
{% if r.needs %}
**Waits on.**{% for n in r.needs %} {{ n }}{% endfor %}
{% endif %}{% if r.supersedes %}
**Supersedes.** {{ r.supersedes }}
{% endif %}{% if r.superseded_by %}
**Superseded by.** {{ r.superseded_by }}
{% endif %}{% if r.raised %}
*Raised {{ r.raised }}{% if r.raised_by %} by {{ r.raised_by }}{% endif %}{% if r.source %}, from `{{ r.source }}`{% endif %}.*
{% endif %}
{% endfor %}

## What this page does not carry

**Each rule names the rows it was raised from**, because an aggregate is worth nothing
until it can name one, and a rule whose examples no longer resolve has either been fixed
or was never right. Those identifiers are in `conf/rules.yml` rather than here: a reader
cannot resolve `rewt:basin/54261d5c6c` and the count is the part that bears on whether to
believe the rule. The same goes for the modules a rule is implemented by and the
parameters it reads.

`conf/rules.yml` also carries {{ site.data.rules.instance_count }} *instance*{% if site.data.rules.instance_count != 1 %}s{% endif %} — a
specific feature someone has claimed is wrong, with the rules it is an instance of. An
instance is not a rule and does not become one by being reported; it is the raw material a
rule is generalised from.
