"""The data model. Keep it small: PLAN.md §3 asks for four tables and no more.

`link`, `node`, `basin`, `correction` are those four. The others here exist for one
reason each, and each is a direct answer to something that went wrong before:

* **Nothing is deleted to correct it** (`retirement`). A retired link is how a reader
  tells a correction from an omission.
* **Two graphs over one geometry cannot be reconciled after the fact** (§8), so there
  is exactly one routing graph — `edge` — and every traversal reads it. It is derived
  from `link` plus the corrections, and it is the only place a reversal exists: *a
  reversal moves no geometry and changes no published attribute.*
* **One stage rebuilt a table another had written columns into** (§2). So no stage
  adds a column to another stage's table. Scope, reachability and basin membership
  are their own narrow tables keyed on `link_id`, and the exporter joins them.
* **A source set shaped by an implementation detail is not the specification's**
  (`sea_entry`). §10's sea network serves every mouth *and every river blocked at the
  coast*, and the blocked ones are absent from the `terminus` layer by construction —
  their terminus is not tidal, which is what makes them blocked. This table records
  which mouths were offered to the sea, which reached it, and how far each moved to do
  so, so that a mouth the sea could not take is a named finding rather than a silent
  omission. It is the same defect as D-048 one turn later, and it was caught only
  because the count was compared against §10's words rather than against another count.
* **A share is not a per-link answer** (`link_sea_reach`). The audit published what
  proportion of the network reaches the sea; nothing carried the answer for a single
  link. So the connector proposer could not ask the one question that would have stopped
  it inventing geometry: *does the sea already drain this?* The flag is a filter on the
  crawl's own result — reaches tidal water, and the terminus it drains to is in a system
  the sea can take — which makes it a subset by construction, and the same computation
  the audit reports rather than a second one that happens to agree.
* **A sea route must be a `link` in one network, not a second graph** (`sea_link`).
  §10 is explicit that sea segments do not get a routing graph of their own, and §8
  records what happened last time two graphs were held over one geometry. This is the
  working record from which those links are built — carrying the shallowest depth on
  each route, so the clearance the network was constructed to respect can be checked
  against the geometry rather than assumed from the parameter that produced it.

Geometry is EPSG:27700 throughout; EPSG:4326 only at export (AGENTS.md).
"""

from __future__ import annotations

from . import db

# --------------------------------------------------------------------------
# The four tables of PLAN.md §3
# --------------------------------------------------------------------------

LINK_DDL = """
CREATE TABLE link (
    link_id         VARCHAR NOT NULL,     -- stable across editions (rewt.ids)
    publisher_id    VARCHAR,              -- the survey's own id; NULL if we made it
    source_id       VARCHAR NOT NULL,     -- an id in conf/sources.yml
    origin          VARCHAR NOT NULL,     -- survey | connector | skeleton
    form            VARCHAR,              -- inlandRiver | lake | tidalRiver | canal
    name            VARCHAR,
    name_alt        VARCHAR,
    -- Stored ALREADY ORIENTED: from_node is upstream, to_node downstream, whatever
    -- the source said. OS encodes direction relative to the digitised line, and in
    -- the earlier work four separate places had to remember to flip it.
    from_node       VARCHAR NOT NULL,
    to_node         VARCHAR NOT NULL,
    -- What the survey shipped, kept so the flip stays inspectable.
    digitised_from  VARCHAR NOT NULL,
    digitised_to    VARCHAR NOT NULL,
    flow_direction  VARCHAR,              -- as published; NULL where it said nothing
    oriented_flip   BOOLEAN NOT NULL,     -- true where load reversed the digitised sense
    direction_known BOOLEAN NOT NULL,     -- false where the survey declined to say
    length_m        DOUBLE NOT NULL,      -- measured from the geometry, not copied
    published_length_m DOUBLE,            -- what the survey stated, for comparison
    geom            GEOMETRY NOT NULL     -- EPSG:27700, in digitised order always
)
"""

NODE_DDL = """
CREATE TABLE node (
    node_id         VARCHAR NOT NULL,
    publisher_id    VARCHAR,
    source_id       VARCHAR NOT NULL,
    origin          VARCHAR NOT NULL,     -- survey | split | connector
    category        VARCHAR,              -- the survey's own: source|junction|outlet
    -- The terminus classification of PLAN.md §3: sea, boundary of scope, or neither.
    -- Decided from the survey's own `form`, never from a coastline (§5) — a coastline
    -- decides the question by distance from a modern shore and is wrong at exactly the
    -- estuaries where the answer matters.
    --
    -- 'boundary' is declared and never assigned. PLAN.md §1 is explicit that an exit at
    -- the edge of the study area is not a legitimate terminus but a defect: scope is
    -- whole basins and every basin drains to a coast. The audit reports such a node as
    -- a defect; the loader may not quietly classify it as an ending.
    terminus        VARCHAR NOT NULL,     -- tidal | inland   ('boundary' is a defect)
    easting         DOUBLE NOT NULL,
    northing        DOUBLE NOT NULL,
    geom            GEOMETRY NOT NULL
)
"""

BASIN_DDL = """
CREATE TABLE basin (
    basin_id        VARCHAR NOT NULL,
    label           VARCHAR,              -- a name for reading, from the outlet's river
    outlet_node     VARCHAR,              -- the node the basin drains to
    area_km2        DOUBLE NOT NULL,
    in_scope        BOOLEAN NOT NULL,
    scope_reason    VARCHAR NOT NULL,     -- why, in words: this is a decision, not a flag
    england_wales_area_km2 DOUBLE,
    provisional     BOOLEAN NOT NULL,     -- true before repair, false after (§4.1)
    geom            GEOMETRY NOT NULL
)
"""

CORRECTION_DDL = """
CREATE TABLE correction (
    correction_id   VARCHAR NOT NULL,
    kind            VARCHAR NOT NULL,     -- connector | reversal | junction | exclusion | mode
    subject         VARCHAR NOT NULL,     -- the identifier it acts on, as authored
    resolved_to     VARCHAR,              -- what it resolved to in this build
    applied         BOOLEAN NOT NULL,
    skip_reason     VARCHAR,              -- named, never silent (AGENTS.md)
    reason          VARCHAR NOT NULL,     -- in words: why this judgement was made
    evidence        VARCHAR NOT NULL,     -- a place, a source, or a person and a date
    detail          VARCHAR NOT NULL,     -- the row's remaining fields, as authored
    author          VARCHAR,
    dated           VARCHAR,
    source_file     VARCHAR NOT NULL,     -- the diffable file it came from
    source_row      INTEGER NOT NULL,
    easting         DOUBLE,
    northing        DOUBLE,
    geom            GEOMETRY
)
"""

# --------------------------------------------------------------------------
# Derived, each owned by exactly one stage
# --------------------------------------------------------------------------

EDGE_DDL = """
-- THE routing graph. One graph over one geometry. A reversal exists here and nowhere
-- else; the published geometry and attributes are untouched by it (§5).
CREATE TABLE edge (
    edge_id         VARCHAR NOT NULL,
    link_id         VARCHAR NOT NULL,
    from_node       VARCHAR NOT NULL,     -- upstream
    to_node         VARCHAR NOT NULL,     -- downstream
    mode            VARCHAR NOT NULL,     -- downstream | both  (a canal summit pound)
    length_m        DOUBLE NOT NULL,
    form            VARCHAR,
    origin          VARCHAR NOT NULL,
    reversed        BOOLEAN NOT NULL,     -- against the orientation `link` holds
    reversed_by     VARCHAR               -- the correction id that did it
)
"""

RETIREMENT_DDL = """
-- Never delete a geometry to correct it. Retire it with a reason and keep it.
CREATE TABLE retirement (
    link_id         VARCHAR NOT NULL,
    reason          VARCHAR NOT NULL,
    superseded_by   VARCHAR,              -- comma-separated child link ids, if any
    correction_id   VARCHAR
)
"""

LINK_SCOPE_DDL = """
-- Written by the scope stage and by nothing else. Nothing is deleted: out-of-scope
-- links are flagged, so the rule can be changed without re-reading the source (§4.1).
CREATE TABLE link_scope (
    link_id         VARCHAR NOT NULL,
    basin_id        VARCHAR,
    in_scope        BOOLEAN NOT NULL,
    scope_rule      VARCHAR NOT NULL      -- basin | country | neither
)
"""

LINK_REACH_DDL = """
-- Written by the crawl and by nothing else. What the crawl did not reach IS the
-- defect list (§5), so this table is read by the audit, not appended to by it.
CREATE TABLE link_reach (
    link_id         VARCHAR NOT NULL,
    reaches_tidal   BOOLEAN NOT NULL,
    seed_node       VARCHAR,              -- the tidal terminus it drains to
    hops            INTEGER               -- links between it and that terminus
)
"""

LINK_FLAG_DDL = """
-- Flags a later stage must not have to re-derive, and that Stage 1 makes no claim
-- about beyond what they say (D-008): a schematic line across standing water is a
-- routing device, and a reservoir crossing is a modern artefact with a valley under it.
CREATE TABLE link_flag (
    link_id         VARCHAR NOT NULL,
    flag            VARCHAR NOT NULL,     -- schematic | reservoir | flat_water | canal_summit
    detail          VARCHAR
)
"""


SEA_ENTRY_DDL = """
CREATE TABLE sea_entry (
    entry_id     INTEGER NOT NULL,   -- the sea cell a mouth was snapped to
    node_id      VARCHAR NOT NULL,   -- the tidal terminus or coastal orphan
    kind         VARCHAR NOT NULL,   -- 'terminus' or 'orphan'
    snapped_m    DOUBLE,             -- how far the mouth moved to reach open water
    -- HOW FAR THE MOUTH IS FROM MEAN HIGH WATER, which is what decides whether a
    -- BLOCKED mouth may attach to the sea network. A channel ending at the sea wall
    -- discharges to the sea; one ending 200 m inland is drained by the network, and
    -- attaching it to a sea route would represent the water leaving somewhere it does
    -- not. Stephen gave four cases and this is the measurement that separates them:
    -- 4 m, 43 m and 4 m attach; 210 m does not.
    coast_m      DOUBLE,
    easting      DOUBLE,
    northing     DOUBLE
)
"""

# §10's sea network. A `link` in the published model, with a distinguishing form —
# these rows are the working record, not a second graph.
SEA_LINK_DDL = """
CREATE TABLE sea_link (
    link_id         VARCHAR NOT NULL,
    from_entry      INTEGER NOT NULL,
    to_entry        INTEGER NOT NULL,
    from_node       VARCHAR,
    to_node         VARCHAR,
    length_m        DOUBLE NOT NULL,
    min_depth_m     DOUBLE,          -- shallowest point on the route; the clearance holds
    median_depth_m  DOUBLE,
    geom            GEOMETRY
)
"""

LINK_SEA_REACH_DDL = """
-- Written by the sea_reach stage and by nothing else. The SECOND reachability reading,
-- and the one §1 actually asks for.
--
-- `link_reach.reaches_tidal` asks whether water can get to tidal water, which the
-- survey draws. This asks whether it can get to THE SEA NETWORK — the routes §10 builds
-- across open water between every mouth. Those are two different questions and the
-- second is strictly harder: a mouth that the sea could not take is blocked, and a
-- river arriving at it has reached tidal water and still cannot get out.
--
-- It exists because the sea network was built, published, drawn on the map, and absent
-- from the routing graph: 0 of 4,183 sea links were in `edge`, so no reachability
-- reading could see them. 693 mouths were recorded as blocked and 2,751 nodes had sea
-- routes attached, and none of it reached a single figure.
CREATE TABLE link_sea_reach (
    link_id         VARCHAR NOT NULL,
    reaches_sea     BOOLEAN NOT NULL,
    entry_node      VARCHAR,              -- the mouth it drains to, on the sea network
    hops            INTEGER
)
"""

# R-01. Every in-scope link against the Ordnance Survey high water line: landward of it,
# crossing it, or wholly seaward of it. `form` and `is_repair` are carried so the classes
# can be counted apart without a second join — an inlandRiver wholly below high water is
# a different finding from a tidalRiver one, even though both are retired.
HIGH_WATER_SIDE_DDL = """
CREATE TABLE high_water_side (
    link_id   VARCHAR PRIMARY KEY,
    side      VARCHAR NOT NULL,      -- landward | crossing | seaward
    length_m  DOUBLE,
    form      VARCHAR,
    is_repair BOOLEAN
)
"""

TABLES = {
    "high_water_side": HIGH_WATER_SIDE_DDL,
    "link": LINK_DDL,
    "node": NODE_DDL,
    "basin": BASIN_DDL,
    "correction": CORRECTION_DDL,
    "edge": EDGE_DDL,
    "retirement": RETIREMENT_DDL,
    "link_scope": LINK_SCOPE_DDL,
    "link_reach": LINK_REACH_DDL,
    "link_sea_reach": LINK_SEA_REACH_DDL,
    "link_flag": LINK_FLAG_DDL,
    "sea_entry": SEA_ENTRY_DDL,
    "sea_link": SEA_LINK_DDL,
}


def create(*names: str) -> None:
    """Create tables, dropping first: every stage clears what it wrote (§2)."""
    con = db.get()
    for name in names:
        if name not in TABLES:
            raise KeyError(f"no DDL for table {name!r}; declare it in rewt/schema.py")
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(TABLES[name])


def index(*specs: tuple[str, str]) -> None:
    """Indexes, named after what they cover so a rebuild replaces rather than adds."""
    con = db.get()
    for table, column in specs:
        name = f"idx_{table}_{column.replace(', ', '_').replace(',', '_')}"
        con.execute(f"DROP INDEX IF EXISTS {name}")
        con.execute(f"CREATE INDEX {name} ON {table} ({column})")

# THE IN-SCOPE POPULATION, DEFINED ONCE.
#
# D-079: establishing what is in scope looks like a join and is not.
# `link_scope JOIN link WHERE in_scope` gives 125,321 links and 105,462.8 km. The
# correct population is 127,121 links and 105,699.0 km, and the difference is two rules
# that compose into a third nobody owned:
#
#   * a retired link is KEPT in `link`, never deleted, because the audit trail is part
#     of the product (AGENTS.md) — so it must be excluded here rather than by absence;
#   * a repair link lives in `repair_link` and NOT in `link` — 2,435 in-scope ids do —
#     so an inner join to `link` silently drops every synthetic connector.
#
# Each rule is documented on its own and the population that satisfies both was stated
# nowhere, so every consumer re-derived it and the obvious derivation is wrong. It
# reached `published/audit/basins.json`, where 105,462.8 km sat beside four other files
# saying 105,699.0 and nothing compared them (found by rewt-c1, confirmed by rewt-46).
#
# So there is one definition and it is this view. Read it; do not rebuild it.
IN_SCOPE_LINK_DDL = """
CREATE VIEW in_scope_link AS
SELECT s.link_id,
       s.basin_id,
       s.scope_rule,
       COALESCE(l.length_m, r.length_m)   AS length_m,
       COALESCE(l.form,     r.form)       AS form,
       COALESCE(l.name,     r.name)       AS name,
       COALESCE(l.from_node, r.from_node) AS from_node,
       COALESCE(l.to_node,   r.to_node)   AS to_node,
       -- `r.link_id IS NOT NULL`, NOT `l.link_id IS NULL`. The two agree for every row
       -- that exists in one table or the other, and differ for a row in NEITHER — which
       -- the second would label a repair link and the first labels nothing. rewt-c1
       -- found that while reading the view rather than running it; the guard they wrote
       -- catches such a row arriving, and this stops it being mislabelled if it does.
       r.link_id IS NOT NULL              AS is_repair
FROM link_scope s
LEFT JOIN link        l USING (link_id)
LEFT JOIN repair_link r USING (link_id)
WHERE s.in_scope
  AND NOT EXISTS (SELECT 1 FROM retirement t WHERE t.link_id = s.link_id)
"""


def in_scope_view() -> None:
    """(Re)create `in_scope_link`. Cheap, idempotent, and safe to call before use."""
    con = db.get()
    con.execute("DROP VIEW IF EXISTS in_scope_link")
    con.execute(IN_SCOPE_LINK_DDL)
