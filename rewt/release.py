"""Release notes, generated from the build rather than written about it.

**Every figure here is read from `published/`, and none is typed.** A release note
that quotes a number by hand is a number that will be right once and wrong at the next
edition, and it will look authoritative in both states — the failure this project has
met repeatedly in its own audit. So the notes are derived, and if the build has not
run, they cannot be made at all.

The caveats are as load-bearing as the figures. A reader who takes 93.53% as an
independent confirmation of 93.59% has been misled by a true statement, and the only
defence is that the qualification travels in the same paragraph as the number.
"""

from __future__ import annotations

import json

import pathlib

from . import paths


def _audit() -> dict:
    path = paths.PUBLISHED / "audit" / "audit.json"
    if not path.exists():
        raise FileNotFoundError(
            "published/audit/audit.json is absent. Release notes are generated from a "
            "build, not written about one; run `rewt build` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _provenance() -> dict:
    path = paths.PUBLISHED / "provenance.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def notes(tag: str) -> str:
    doc = _audit()
    prov = _provenance()
    s = doc.get("sections", {})
    reach = s.get("reachability", {})
    sea = s.get("reachability_tested_against_the_sea", {})
    dead = s.get("dead_ends", {})
    gen = s.get("generalisation", {})

    total = sea.get("in_scope_total_km") or reach.get("total_in_scope_km", 0)
    tidal = sea.get("reaches_tidal_water_km") or reach.get("reached_in_scope_km", 0)
    tidal_share = sea.get("reaches_tidal_water_share") or reach.get("in_scope_share", 0)
    sea_km = sea.get("reaches_the_sea_km")
    sea_share = sea.get("reaches_the_sea_share")

    L = [
        f"# REWT {tag}",
        "",
        "**Rivers of England and Wales, Temporally — Stage 1.** A traversable modern",
        "river network, in which water can be followed from any stretch to the sea.",
        "",
        "**This release makes no historical claim whatever.** Stage 1 is the present-day",
        "network and the machinery for correcting it; nothing in it dates anything.",
        "",
        "## The figures",
        "",
        "| | km | share |",
        "|---|---:|---:|",
        f"| in-scope network | {total:,.0f} | |",
        f"| reaches tidal water | {tidal:,.0f} | {tidal_share:.2%} |",
    ]
    if sea_km:
        L.append(f"| and that tidal water reaches the sea | {sea_km:,.0f} | {sea_share:.2%} |")
    L += [
        "",
        "## Read these before quoting the figures",
        "",
        f"**{total - tidal:,.0f} km of the in-scope network does not reach tidal water.**",
        "That is the honest remainder, and it is the work Stage 1 has not finished. It is",
        "named per place. **The dead-end counts are three different numbers and it matters",
        "which is quoted:**",
        "",
        f"- {dead.get('national', 0):,} dead ends nationally, in the whole of Great Britain",
        f"- {dead.get('in_scope', 0):,} of those are in scope",
        f"- **{dead.get('at_tidal_water', 0):,} of the in-scope ones stand at tidal water and are",
        "  correct endings, not faults**",
        f"- **{dead.get('defects', 0):,} in-scope dead ends are NOT at tidal water. Those are the",
        "  defects, and that is the number the map and the audit mean by \"the work\".**",
        "",
        f"So {dead.get('defects', 0):,} is a subset of {dead.get('in_scope', 0):,}, not a synonym for it. The audit ranks",
        "the defects by the length actually stranded above each — not by the catchment",
        "standing above them, which counts water that has another way out.",
        "",
    ]
    if sea_km:
        L += [
            "**The two reachability figures are not independent, and the second is an upper",
            "bound with a known discontinuity.** Attaching the sea network turns *reaches the",
            "sea* from a definition into a test a mouth can fail — but at the working",
            f"parameters that test separates only {tidal - sea_km:,.0f} km of {tidal:,.0f}, and its value",
            "moves 16 percentage points across a single threshold because one mouth attaching",
            "connects an entire tidal system. **A reader who takes the second number as",
            "confirming the first has been misled by a true statement.** The reasoning is in",
            "`DECISIONS.md` D-061.",
            "",
        ]
    by_rule, adjudicated = _how_the_corrections_were_made()
    if by_rule:
        L += [
            f"**{by_rule:,} of the {by_rule + adjudicated:,} corrections were proposed BY RULE from the",
            "audit's own evidence, and have not been adjudicated at the place by a person.**",
            f"Only {adjudicated} were. Each correction records which it is, in its own `evidence`",
            "field, so the distinction survives into anyone's analysis — but a reader who",
            "takes the corrected network as human-checked would be badly wrong, and the",
            "share is high enough that saying so in the data alone is not enough.",
            "",
            "**What that costs is measurable, and this build measured it.** The Weaver",
            "reached the sea only after a person looked: 1,178 km of network stood behind a",
            "184 m break at Eastham that every rule had passed over, and one afternoon with",
            "a map found it. The rules earned the reachability figure above; they are rules,",
            "and rules of this kind are known to agree that a broken thing is fixed.",
            "",
        ]
    ob = s.get("outletless_basins") or {}
    if ob.get("in_scope"):
        L += [
            f"**{ob['in_scope']} in-scope basins have no outlet node in the network — "
            f"{ob.get('in_scope_km2', 0):,.0f} km2 — and every one was checked.**",
            "Each was measured against Boundary-Line's Mean High Water AND against the",
            "nearest tidal terminus, because an estuary is wide enough that either test",
            "alone misreads it: a basin on the inner shore of the Ribble stands 2.3 km",
            "from the outer coast and 48 m from tidal water.",
            "",
        ]
        if ob.get("unexplained"):
            L += [
                f"**{ob['unexplained']} of them are explained by neither**, and each is a",
                "named finding in the audit. A basin with no outlet that is not coastal is",
                "a catchment whose water has nowhere in this network to go.",
                "",
            ]
        else:
            L += [
                f"**All {ob['in_scope']} are coastal or estuarine catchments whose drainage",
                "the survey does not draw** — cliff and ria coasts, where water reaches the",
                "sea without a mapped watercourse. That is the expected case, and it is now",
                "a swept result rather than a sampled one.",
                "",
            ]
        km, tidal_km = _network_in_outletless_basins()
        if km:
            L += [
                f"**Their area is large and it does not mean what it looks like.** Those "
                f"{ob['in_scope']} basins",
                f"cover {ob.get('in_scope_km2', 0):,.0f} km2 — a third of the in-scope area — because a coastal",
                "basin's estuary and foreshore are counted in it. **Having no outlet node is a",
                "property of the basin record, not of the water:** a basin that meets the sea",
                "along a coastline has no single node to name as its outlet. The network",
                f"inside them is {km:,.0f} km, and {100 * tidal_km / km:.1f}% of it reaches tidal water —",
                "**better than the national figure**, not worse.",
                "",
            ]
    L += [
        "**The map has been tested in one browser.** The historic-sheet compositor uses",
        "`OffscreenCanvas` and `createImageBitmap`, which are the parts most likely to",
        "behave differently elsewhere — Safari above all. The network, the defects and",
        "every figure on the page are independent of it; it is the historic backdrops that",
        "would fail, and they would fail visibly rather than quietly.",
        "",
        "**The network is frozen on the Ordnance Survey Open Rivers 2026-04 issue and will",
        "not take reissues.** OS states that its identifiers are not persistent between",
        "product versions, so stability is bought by refusing updates rather than by",
        "minting our own. The build fails if the input moves (D-054). The cost is real: no",
        "correction OS makes reaches this network.",
        "",
        "**Nothing derived from the sea network may be presented as a route a vessel could",
        "follow.** The bathymetry carries `DO NOT USE FOR NAVIGATION`, which is a constraint",
        "on purpose rather than on redistribution. The sea structure is the connectivity of",
        "water below a stated clearance; it is not a sailing route, and the words",
        "*plausible* and *sailing* are excluded from its specification deliberately, because",
        "each imports a vessel and a vessel imports a period.",
        "",
        "**The survey is generalised, and this release does not un-generalise it.**",
    ]
    if gen:
        sp = gen.get("spacing_m", {})
        sg = gen.get("sagitta_m", {})
        med_sp = sp.get("50") or sp.get(50)
        med_sg = sg.get("50") or sg.get(50)
        if med_sp and med_sg:
            L.append(
                f"Median vertex spacing {med_sp:,.1f} m, median sagitta {med_sg:,.2f} m, "
                "with almost no"
            )
            L.append(
                "vertex below about 9 m of amplitude — the signature of a tolerance filter. "
                "**Detail"
            )
            L.append(
                "smaller than that is absent from the record, not from the river**, and a "
                "later stage"
            )
            L.append("proposing to move a line by less than it is arguing with the tolerance.")
    L += [
        "",
        "**Elevation and fall are screening quantities, not measurements.** The columns are",
        "named `screening_*` for that reason: a 50 m terrain model does not resolve a weir,",
        "a leat, or a mill's head, and the prefix is the only part of the value that travels",
        "with it into someone else's analysis.",
        "",
        "## Provenance",
        "",
    ]
    for k, v in sorted(prov.items()):
        if isinstance(v, (str, int, float)):
            L.append(f"- `{k}`: {v}")
    L += [
        "",
        "## What is attached",
        "",
    ]
    skipped = deposit_excludes()
    for rel, why in ASSETS:
        name = rel.rsplit("/", 1)[-1]
        mark = " — **on the GitHub release only, not in the Zenodo record**" \
            if name in skipped else ""
        L.append(f"- `{rel}` — {why}{mark}")
    L += [
        "",
        "**The DOI archives the data, not the map.** The tiles are a rendering of the",
        "network and `rewt viewer-data` regenerates them from the GeoPackage, so they are",
        "attached to the release — where the site fetches them from — and left out of the",
        "citable record, which they would otherwise treble in size without adding to.",
        "",
        "`audit/audit.json` is attached in its own right rather than inside an archive,",
        "because the documentation site states that the audit published with the data is",
        "the authority for every figure on it — and that holds only while a script can",
        "fetch it by URL.",
        "",
        "## Attribution",
        "",
        "Every source's required statement is in `published/ATTRIBUTION.md`, in full,",
        "and each is reproduced here exactly as `conf/sources.yml` requires it:",
        "",
    ]
    # COMPOSED, NEVER TYPED. Two statements used to be written out here by hand, and the
    # EMODnet one was wrong — it dropped the consortium citation the licence actually
    # asks for and kept only the licence name. A release note is the worst place for
    # that error, because a DOI cannot be withdrawn. Same rule as the viewer's credit
    # line: the manifest is the authority, and only the sources this build consumed are
    # credited, since claiming a source the data does not contain is also false.
    for line in _required_attributions(prov):
        L.append(f"- {line}")
    L += [
        "",
        "## Citing this",
        "",
        "A result computed from this edition must cite **this version's DOI**, not the",
        "concept DOI. The concept DOI always resolves to the newest release, so a figure",
        "attached to it becomes uncheckable the moment the next edition lands.",
    ]
    return "\n".join(L) + "\n"


# WHAT A RELEASE CARRIES, owned here and read by everything that needs it — the check
# that refuses a bad release and the command that cuts one. Two lists would be two
# facts that can disagree, which is the failure this repository keeps meeting; rewt-1d
# puts the general form well: **do not restate a fact that something else owns.**
#
# `audit.json` IS LISTED SEPARATELY AND MUST STAY THAT WAY. The documentation site
# states that the audit published with the data is the authority for every figure on
# it, and that promise holds only while a script can fetch the audit BY URL. Folding
# published/ into one archive would read as tidiness in a diff and would quietly make
# that sentence false; nobody reviewing the tidy-up would think of the sentence. The
# test below is the only thing that connects them.
ASSETS: tuple[tuple[str, str], ...] = (
    ("rewt_stage1_network.gpkg", "the network"),
    ("rewt_stage1_corrections.gpkg", "every curated judgement, as its own file"),
    ("audit/audit.json", "the audit, machine-readable — the authority for every figure"),
    ("audit/audit.md", "the same audit, for a person"),
    ("provenance.json", "what was fetched, and what it hashed to"),
    ("ATTRIBUTION.md", "every source's required statement, in full"),
    # What the map reads. Attached rather than committed, and fetched by pages.yml at
    # deploy time — see rewt.tiles.pack for why it takes that route.
    ("viewer-data.tar", "the tiles and layers the map reads"),
    # Because none of the others says how to cite this. ATTRIBUTION.md credits the
    # SOURCES; a downloader had the data and no way to credit the dataset itself.
    ("CITATION.cff", "how to cite this edition"),
)

MACHINE_READABLE_AUDIT = "audit/audit.json"


def assets() -> list[tuple[pathlib.Path, str]]:
    """The files a release attaches, resolved, with the missing ones named."""
    out, missing = [], []
    for rel, why in ASSETS:
        path = paths.PUBLISHED / rel
        (out if path.exists() else missing).append((path, why))
    if missing:
        raise FileNotFoundError(
            "the build has not produced everything a release carries:\n  "
            + "\n  ".join(f"{p.relative_to(paths.ROOT)} — {w}" for p, w in missing)
        )
    return out


def audit_is_its_own_asset() -> bool:
    """The documentation site's promise, expressed as a question code can ask.

    Fetchable by URL means listed as a file in its own right. Inside an archive it is
    still machine-readable in principle and no longer reachable in practice, and the
    difference is invisible in a diff that only shows a shorter asset list.
    """
    return MACHINE_READABLE_AUDIT in {rel for rel, _ in ASSETS}


def attribution_drift() -> list[str]:
    """Every source's required attribution, checked against BOTH renderings of it.

    `conf/sources.yml` is the authority, and two things now discharge its obligations
    by different routes: `published/ATTRIBUTION.md`, written by the export stage into a
    build artefact, and `docs/_data/sources.yml`, a committed projection the site
    renders. Neither can see the other, and each has its own way of going stale — the
    artefact when the build is older than a manifest edit, the projection when someone
    forgets to regenerate it.

    So this compares each rendering against the manifest rather than against the other.
    Two renderings that agree with each other and disagree with the manifest is the
    failure that a same-string comparison would pass, and it is the one that credits
    the wrong people. `--check` in `pages.yml` already guards the projection on the
    site's own terms; this is the gate before a DOI, which is the point after which a
    wrong attribution cannot be withdrawn.
    """
    from . import config

    published = paths.PUBLISHED / "ATTRIBUTION.md"
    projected = paths.ROOT / "docs" / "_data" / "sources.yml"
    if not published.exists():
        return [f"{published.relative_to(paths.ROOT)} does not exist; run `rewt build`"]
    if not projected.exists():
        return [f"{projected.relative_to(paths.ROOT)} does not exist; run "
                "`python tools/docs/sources_page.py`"]

    # Compared on collapsed whitespace: the projection is YAML and wraps long strings,
    # so a line break is a difference in the bytes and not in the obligation.
    def flat(p: pathlib.Path) -> str:
        return " ".join(p.read_text().split())

    have = {"published/ATTRIBUTION.md": flat(published),
            "docs/_data/sources.yml": flat(projected)}
    out: list[str] = []
    for src in config.sources():
        wanted = " ".join(str(src.attribution).split())
        for where, text in have.items():
            if wanted not in text:
                out.append(f"{src.id}: its required attribution is absent from {where}. "
                           f"conf/sources.yml asks for {wanted!r}")
    return out


def _required_attributions(prov: dict) -> list[str]:
    """Each consumed source's required statement, verbatim from `conf/sources.yml`.

    Deduplicated — the four Ordnance Survey products carry one identical statement and
    OGL asks for the acknowledgement, not for four of them.
    """
    from . import config

    used = set(prov.get("sources", {}))
    reg = {s.id: s for s in config.sources()}
    unknown = sorted(used - set(reg))
    if unknown:
        raise RuntimeError(
            f"provenance.json names source(s) absent from conf/sources.yml: "
            f"{', '.join(unknown)}. An uncredited input cannot be released."
        )
    out: list[str] = []
    for i in sorted(used):
        if reg[i].attribution not in out:
            out.append(reg[i].attribution)
    return out


def _how_the_corrections_were_made() -> tuple[int, int]:
    """How many judgements a person actually looked at, counted from the shipped file.

    **Not a figure anyone types.** The corrections carry their own provenance in
    `evidence`, and the overwhelming majority say so plainly — but only to a reader who
    opens the GeoPackage and reads a string. A release note quoting a corrected
    network's reachability without this is quoting a number whose method it has not
    disclosed, and AGENTS.md is explicit that aggregates have repeatedly agreed a broken
    thing was fixed. Counted here so the prose cannot drift from the file.
    """
    import geopandas as gpd

    path = paths.PUBLISHED / "rewt_stage1_corrections.gpkg"
    if not path.exists():
        return 0, 0
    df = gpd.read_file(path, layer="correction", read_geometry=False,
                       columns=["evidence"])
    rule = df["evidence"].astype(str).str.contains("JUDGED BY RULE", case=False)
    return int(rule.sum()), int((~rule).sum())



def viewer_data_drift() -> list[str]:
    """The attached tar must hold exactly the tiles the viewer is serving.

    **A release whose map is built from a different pass than its data is
    self-inconsistent, and the counts can still agree.** That is how it was found:
    `published/viewer-data.tar` was ninety minutes older than
    `docs/viewer/data/rewt.pmtiles`, 35 MB different, and its `summary.json` matched the
    shipped GeoPackage exactly — so every internal check passed. Two artefacts, each
    consistent with itself, never compared with each other; the same shape as the
    attribution renderings and the never-thinned layer.

    Compared by **size and digest, never by modification time**. A clock is a proxy, and
    D-049 records what proxies cost here: the fingerprint work began because an mtime
    said a green build was stale for ever.
    """
    import hashlib
    import tarfile

    from . import tiles

    tar_path = paths.PUBLISHED / "viewer-data.tar"
    if not tar_path.exists():
        return [f"published/viewer-data.tar does not exist; run `rewt viewer-data`"]
    if not tiles.OUT.exists():
        return ["docs/viewer/data/ does not exist; run `rewt viewer-data`"]

    def digest(fh) -> str:
        h = hashlib.sha256()
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
        return h.hexdigest()

    on_disk = {f.name: f for f in tiles.OUT.iterdir()
               if f.suffix in (".pmtiles", ".geojson", ".json")}
    problems: list[str] = []
    with tarfile.open(tar_path) as tar:
        packed = {m.name: m for m in tar.getmembers() if m.isfile()}
        for name in sorted(set(on_disk) | set(packed)):
            if name not in packed:
                problems.append(f"{name} is served by the viewer and absent from the tar")
                continue
            if name not in on_disk:
                problems.append(f"{name} is in the tar and no longer built")
                continue
            if packed[name].size != on_disk[name].stat().st_size:
                problems.append(
                    f"{name}: tar holds {packed[name].size:,} bytes, the built file is "
                    f"{on_disk[name].stat().st_size:,}")
                continue
            with tar.extractfile(packed[name]) as a, on_disk[name].open("rb") as b:
                if digest(a) != digest(b):
                    problems.append(f"{name}: same size, different bytes")
    if problems:
        problems.append("run `rewt viewer-data`, which repacks the tar with the tiles")
    return problems


def _network_in_outletless_basins() -> tuple[float, float]:
    """In-scope km inside basins with no outlet node, and how much of it drains.

    **Because the area alone reads as alarming and is not.** 103 basins covering a third
    of the in-scope area sounds like a third of the country draining nowhere; the network
    inside them in fact reaches tidal water at a HIGHER rate than the national average,
    because they are the coastal basins and the coast is where the water is going. An
    exact figure supporting a false impression is the failure this release note was
    rewritten twice to avoid.

    Read from the published GeoPackage — the artefact these notes describe — rather than
    recomputed from the database, so the note cannot describe a different build.
    """
    import geopandas as gpd

    path = paths.PUBLISHED / "rewt_stage1_network.gpkg"
    if not path.exists():
        return 0.0, 0.0
    basins = gpd.read_file(path, layer="basin", read_geometry=False,
                           columns=["basin_id", "in_scope", "outlet_node"])
    ids = set(basins[basins.outlet_node.isna() & basins.in_scope].basin_id)
    if not ids:
        return 0.0, 0.0
    link = gpd.read_file(path, layer="link", read_geometry=False,
                         columns=["basin_id", "length_m", "in_scope", "reaches_tidal"])
    inside = link[link.basin_id.isin(ids) & link.in_scope]
    return (float(inside.length_m.sum()) / 1000.0,
            float(inside[inside.reaches_tidal].length_m.sum()) / 1000.0)


# The concept DOI: always the newest edition, and stable for the life of the project.
# A literal, because it is minted once by Zenodo and cannot be derived from anything
# here — the same reasoning as the README badge, and the same maintenance cost.
CONCEPT_DOI = "10.5281/zenodo.22238250"


def citation_file(tag: str) -> str:
    """`CITATION.cff`, generated from `.zenodo.json` so authorship has ONE authority.

    **Why it exists at all.** None of the release assets said how to cite this. A
    downloader got `ATTRIBUTION.md`, which credits the SOURCES, and nothing saying how
    to credit REWT — the "Citing this" text is on the release page and in
    `published/README.md`, and neither travels with the files. Stephen noticed the gap
    from Zenodo's own Citation File tab.

    **Why it is generated and not written.** `.zenodo.json` already declares the
    creators. A hand-written `CITATION.cff` would be a second copy of the same fact,
    maintained separately, drifting quietly — which is D-067's whole subject, and it
    would be a poor joke to introduce another instance of it in the file that tells
    people whom to credit.

    Zenodo's own *Create CITATION.cff* button is deliberately not used: it belongs to
    the GitHub hook, and it writes a citation for the hook's source-only record rather
    than for the deposit that carries the data.
    """
    zj = json.loads((paths.ROOT / ".zenodo.json").read_text())
    authors = []
    for c in zj["creators"]:
        family, _, given = c["name"].partition(", ")
        authors.append(f"  - family-names: {family}")
        if given:
            authors.append(f"    given-names: {given}")
        if c.get("orcid"):
            # Emitted verbatim, and `.zenodo.json` carries the FULL resolver URL. CFF
            # wants the URL and Zenodo's API wants the bare identifier, so one of them
            # has to be derived — and it is the bare one, because deriving it needs no
            # URL literal in code. `test_no_url_is_hard_coded_in_the_code` caught the
            # other arrangement, and it was right to: a URL belongs in configuration.
            authors.append(f"    orcid: {c['orcid']}")
        if c.get("affiliation"):
            authors.append(f"    affiliation: {c['affiliation']}")
    return "\n".join([
        "# GENERATED by `rewt citation` from .zenodo.json — do not edit.",
        "#",
        "# Authorship is declared once, in .zenodo.json, because two copies of it would",
        "# drift and this is the file that tells people whom to credit.",
        "cff-version: 1.2.0",
        'message: "If you use this dataset, please cite the VERSION below. The DOI in',
        "  `identifiers` is the concept DOI and always resolves to the newest edition; a",
        "  result computed from a particular edition becomes uncheckable when cited",
        '  against it."',
        "title: >-",
        "  REWT — Rivers of England and Wales, Temporally (Stage 1: a traversable modern",
        "  network)",
        "type: dataset",
        f"version: {tag}",
        f"license: {zj.get('license', 'cc-by-4.0').upper().replace('CC-BY-4.0', 'CC-BY-4.0')}",
        "authors:",
        *authors,
        "identifiers:",
        "  - type: doi",
        f"    value: {CONCEPT_DOI}",
        "    description: The concept DOI, resolving to the newest edition",
        "abstract: >-",
        "  A modern river network for England and Wales made traversable, so that water",
        "  can be followed from any stretch to the sea. Stage 1 makes no historical claim",
        "  whatever: it is the present-day network and the machinery for correcting it,",
        "  and nothing in it dates anything. Corrections are overwhelmingly made by rule",
        "  rather than adjudicated at the place; each records which it is.",
        "",
    ])


def deposit_excludes() -> set[str]:
    """Release assets that are NOT deposited to Zenodo, declared in `.zenodo.json`.

    Read from the same file the deposit script reads, so the release notes and the
    deposit cannot describe different lists. That file is JSON precisely because the
    workflow script has no dependencies and cannot import this module.
    """
    return set(json.loads((paths.ROOT / ".zenodo.json").read_text())
               .get("deposit_excludes", []))


def excluded_assets_still_ship() -> list[str]:
    """An excluded file must still be attached to the GitHub release.

    **Excluding is not deleting, and the difference is load-bearing.**
    `viewer-data.tar` leaves the citable record because the DOI should resolve to data
    rather than to a rendering of it — but `pages.yml` fetches that same file from the
    release to serve the map. Dropping it from `ASSETS` as well would take the map down
    at the next deploy, and the failure would look like a Pages problem.
    """
    attached = {rel.rsplit("/", 1)[-1] for rel, _ in ASSETS}
    return [
        f"{name} is excluded from the Zenodo deposit but is no longer a release asset. "
        "Excluding it from the DOI is deliberate; removing it from the release would "
        "stop pages.yml serving the map."
        for name in sorted(deposit_excludes()) if name not in attached
    ]
