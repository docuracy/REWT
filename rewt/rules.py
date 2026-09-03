"""The canonical rule list.

`rules/0001.md` asked for "a canonical machine+human-readable ordered list of rules".
`conf/rules.yml` is that list and this module is the only way to read it, on the same
argument as `config.sources()`: if there is one way in, a rule invented in a function is
visible as a rule invented in a function.

**What this module refuses.** A duplicate id, a gap or a tie in `order`, a status or
kind outside the declared vocabulary, a rule claiming `implemented` with nothing in
`implements`, a `supersedes` or `needs` pointing at an id that does not exist, and a
parameter path that `conf/params.yml` does not declare. All of them are errors and none
is a warning — a rule list that quietly disagrees with itself is worse than no list,
because it reads as agreement (D-067).

**Thresholds are not here.** A rule names its parameters by dotted path and the values
stay in `conf/params.yml`. `Rule.parameters()` resolves them on demand, and raises for a
path that is declared in a rule and missing from the parameters — which is the failure
this arrangement exists to make loud.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from . import config, paths


class RuleError(ValueError):
    """conf/rules.yml does not describe a usable rule list."""


class UnknownRule(KeyError):
    """Asked for a rule id the list does not declare."""


@dataclass(frozen=True)
class Evidence:
    """An identifier the rule was raised from.

    Rules name rows because an aggregate is worth nothing until it can name one
    (D-074), and because a mistyped identifier does nothing while the stage reports
    success (AGENTS.md). `kind` says what table to look in; `point` is an easting and
    northing rather than a row, and resolves against geometry.
    """

    kind: str
    id: str
    note: str = ""

    @property
    def is_point(self) -> bool:
        return self.kind == "point"

    @property
    def coordinates(self) -> tuple[float, float]:
        if not self.is_point:
            raise RuleError(f"evidence {self.id!r} is a {self.kind}, not a point")
        easting, _, northing = self.id.partition(",")
        return float(easting), float(northing)


@dataclass(frozen=True)
class Rule:
    id: str
    order: int
    kind: str
    title: str
    statement: str
    why: str
    status: str
    stage: str
    implements: tuple[str, ...]
    params: tuple[str, ...]
    needs: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    supersedes: tuple[str, ...]
    raised: str
    raised_by: str
    source: str
    owner: str = "implementer"
    superseded_by: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_binding(self) -> bool:
        """Does the build owe anything to this rule yet?

        `proposed` is a thing somebody has said, not a thing the build must do. Only
        `accepted` and `implemented` bind, which is the distinction that keeps this
        file from becoming a wish list that reads like a specification.
        """
        return self.status in ("accepted", "implemented")

    @property
    def changes_the_network(self) -> bool:
        return self.kind in ("specification", "repair")

    def parameters(self) -> dict[str, Any]:
        """The rule's thresholds, resolved from conf/params.yml.

        Raises for a path this rule names and the parameter file does not declare.
        A rule whose threshold has gone missing must not fall back to a literal.
        """
        out: dict[str, Any] = {}
        for path in self.params:
            try:
                out[path] = config.param(path)
            except KeyError as exc:
                raise RuleError(
                    f"{self.id} names parameter {path!r}, which conf/params.yml does "
                    "not declare. A rule states no numbers of its own."
                ) from exc
        return out

    def unresolved_parameters(self) -> list[str]:
        """Paths this rule names that conf/params.yml does not yet declare.

        Not an error while the rule is `proposed` — a rule may be written before its
        thresholds are chosen. It is an error the moment it binds, which `RuleSet`
        enforces.
        """
        missing = []
        for path in self.params:
            try:
                config.param(path)
            except KeyError:
                missing.append(path)
        return missing


class RuleSet:
    """The list. Ordered, validated, and read from the file."""

    def __init__(self, doc: dict[str, Any]):
        self._doc = doc
        self._vocab = doc.get("vocabulary", {})
        statuses = set(self._vocab.get("status", {}))
        kinds = set(self._vocab.get("kind", {}))
        if not statuses or not kinds:
            raise RuleError(
                "conf/rules.yml declares no vocabulary. A status or kind that is not "
                "declared is a typo, and a typo that is accepted is a new category."
            )

        self._rules: dict[str, Rule] = {}
        for entry in doc.get("rules", []):
            missing = [
                k
                for k in ("id", "order", "kind", "title", "statement", "why",
                          "status", "stage", "raised", "raised_by", "source")
                if k not in entry
            ]
            if missing:
                raise RuleError(
                    f"rule {entry.get('id', '<no id>')!r} in conf/rules.yml is missing "
                    f"required field(s): {', '.join(missing)}"
                )
            rule = Rule(
                id=entry["id"],
                order=int(entry["order"]),
                kind=entry["kind"],
                title=" ".join(str(entry["title"]).split()),
                statement=" ".join(str(entry["statement"]).split()),
                why=" ".join(str(entry["why"]).split()),
                status=entry["status"],
                stage=entry["stage"],
                implements=tuple(entry.get("implements") or ()),
                params=tuple(entry.get("params") or ()),
                needs=tuple(entry.get("needs") or ()),
                evidence=tuple(
                    Evidence(kind=e["kind"], id=str(e["id"]),
                             note=" ".join(str(e.get("note", "")).split()))
                    for e in (entry.get("evidence") or ())
                ),
                supersedes=tuple(entry.get("supersedes") or ()),
                raised=str(entry["raised"]),
                raised_by=entry["raised_by"],
                source=entry["source"],
                owner=entry.get("owner", "implementer"),
                superseded_by=entry.get("superseded_by"),
                raw=entry,
            )
            if rule.id in self._rules:
                raise RuleError(f"duplicate rule id {rule.id!r} in conf/rules.yml")
            if rule.status not in statuses:
                raise RuleError(
                    f"{rule.id} has status {rule.status!r}, which the vocabulary does "
                    f"not declare. Declared: {', '.join(sorted(statuses))}"
                )
            if rule.kind not in kinds:
                raise RuleError(
                    f"{rule.id} has kind {rule.kind!r}, which the vocabulary does not "
                    f"declare. Declared: {', '.join(sorted(kinds))}"
                )
            if rule.status == "implemented" and not rule.implements:
                raise RuleError(
                    f"{rule.id} is 'implemented' and names no module in `implements`. "
                    "Status says what is true of the build, not what is intended."
                )
            if rule.status == "superseded" and not rule.superseded_by:
                raise RuleError(f"{rule.id} is 'superseded' and names no successor")
            self._rules[rule.id] = rule

        # ORDER IS SEMANTIC, so it is checked rather than assumed. R-01 redefines the
        # sea before any connector is invented; a tie or a gap means somebody inserted
        # a rule without deciding where in the sequence it belongs.
        orders = sorted(r.order for r in self._rules.values())
        if orders != list(range(1, len(orders) + 1)):
            dupes = {o for o in orders if orders.count(o) > 1}
            raise RuleError(
                "conf/rules.yml `order` must run 1..n with no gaps and no ties; got "
                f"{orders}" + (f" (repeated: {sorted(dupes)})" if dupes else "")
            )

        # Cross-references, before anything reads one and gets None.
        for rule in self._rules.values():
            for other in (*rule.supersedes, *( [rule.superseded_by] if rule.superseded_by else [] )):
                if other not in self._rules:
                    raise RuleError(f"{rule.id} references unknown rule {other!r}")
            if rule.is_binding:
                unresolved = rule.unresolved_parameters()
                if unresolved:
                    raise RuleError(
                        f"{rule.id} is {rule.status!r} and names parameter(s) "
                        f"{', '.join(unresolved)} that conf/params.yml does not "
                        "declare. A binding rule may not carry an unresolved threshold."
                    )

    # -- reading -----------------------------------------------------------
    def __getitem__(self, rule_id: str) -> Rule:
        try:
            return self._rules[rule_id]
        except KeyError:
            raise UnknownRule(
                f"{rule_id!r} is not in conf/rules.yml. Declared: "
                f"{', '.join(self.ids)}"
            ) from None

    def __iter__(self):
        """In `order`, always. The sequence is part of what the file says."""
        return iter(sorted(self._rules.values(), key=lambda r: r.order))

    def __len__(self) -> int:
        return len(self._rules)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self._rules

    @property
    def ids(self) -> list[str]:
        return [r.id for r in self]

    def by_status(self, *statuses: str) -> list[Rule]:
        return [r for r in self if r.status in statuses]

    def by_stage(self, stage: str) -> list[Rule]:
        return [r for r in self if r.stage == stage]

    def by_owner(self, owner: str) -> list[Rule]:
        return [r for r in self if r.owner == owner]

    @property
    def binding(self) -> list[Rule]:
        return [r for r in self if r.is_binding]

    @property
    def instances(self) -> list[dict[str, Any]]:
        """Judgements about particular places, kept as instances of a general rule."""
        return list(self._doc.get("instances") or ())

    def evidence_ids(self, kind: str) -> list[str]:
        """Every evidence identifier of one kind, across the list.

        What the build's identifier test validates against the database.
        """
        return sorted({e.id for r in self for e in r.evidence if e.kind == kind})

    @property
    def doc(self) -> dict[str, Any]:
        return self._doc


@lru_cache(maxsize=1)
def rules() -> RuleSet:
    paths.check_root()
    if not paths.RULES_YML.exists():
        raise RuleError(
            f"{paths.rel(paths.RULES_YML)} not found. The canonical rule list is not "
            "optional; rules/ is the intake and this file is the list."
        )
    with paths.RULES_YML.open(encoding="utf-8") as fh:
        return RuleSet(yaml.safe_load(fh))


def rule(rule_id: str) -> Rule:
    """The only way to reach a rule. Unknown is an error."""
    return rules()[rule_id]
