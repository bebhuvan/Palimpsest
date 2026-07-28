# Context sidebar and year-page content plan

Status: proposed
Scope: build-time content architecture, static release artifacts, and reader presentation
Applies to: map-selection sidebar and `/year` pages

## Purpose

Palimpsest should turn a selected place and year into a varied, source-backed reading
experience. The current reader can retrieve related Wikidata entities, Wikipedia dossiers,
regional records, thematic assertions, and other context, but much of that material is presented
as a flat list. A technically related record is not necessarily a useful or interesting part of a
historical reading.

This plan covers two connected products:

1. a composed context sidebar for a selected map feature and year;
2. year pages that range from an honest empty shell to a rich, machine-written dossier.

The two products should share canonical entities, assertions, source passages, media, temporal
indexes, and provenance. They should not independently fetch or reinterpret the same material.

## Decisions

### External retrieval and generation remain build-time operations

The public application remains static. A visitor request must not contact Wikimedia, another
source API, an LLM provider, or a project database.

The build pipeline is responsible for:

- fetching and revision-pinning admitted source material;
- retaining raw responses, request metadata, and checksums;
- reconciling stable entity identities;
- normalizing dates, relationships, coordinates, and source-backed assertions;
- validating source and per-file media rights;
- producing and validating any machine-written wording;
- publishing immutable, checksummed release artifacts.

The browser may load verified shards, filter dated records, apply presentation rules, and render
cards. It must not infer new historical relationships.

### Historical units are stored once

The pipeline should store reusable entities, assertions, source passages, media records, and
restatements. It should not generate a separate copy for every feature and every possible year.

The durable joins remain:

```text
feature_id -> entity_id -> assertion/dossier/media IDs
```

Names are presentation fields, not join keys.

### Years are usually filters over dated records

Palimpsest spans more than 5,000 nominal years. It is neither necessary nor desirable to
generate an LLM-written artifact for every one of them.

Most year-aware presentation should be produced by filtering records whose validity intervals
include or meaningfully approach the selected year. Exact-year artifacts are reserved for
assembled year pages and narrative dossiers where the evidence supports them.

### LLMs improve bounded wording, not the underlying graph

Canonical identity, dates, relationships, eligibility, links, and provenance come from structured
data and deterministic pipeline rules.

Good LLM tasks include:

- restating one revision-pinned source passage;
- turning one assertion and its evidence excerpt into concise reader-facing wording;
- assigning a passage to a controlled topic vocabulary;
- proposing a short title for one bounded evidence unit.

An LLM should not:

- establish a historical relationship that is absent from canonical data;
- freely combine several encyclopedia articles into a factual paragraph;
- choose sidebar content without an inspectable candidate and ranking layer;
- write URLs, source identities, dates, or citations that the pipeline can supply;
- generate content in the visitor's browser.

One generated card should normally restate one assertion or one bounded source passage. This
reduces, but does not eliminate, the risk that individually true facts are fused into a false
relationship.

## Shared content architecture

The pipeline should maintain five reusable classes of content.

### Entities

People, places, events, polities, institutions, works, artifacts, routes, and concepts have stable
identifiers independent of map geometry and display names.

### Assertions

An assertion records one source-backed statement:

```text
subject + predicate + typed object + validity interval + evidence + provenance
```

Assertions determine whether a fact or relationship is eligible for presentation. Generated prose
is never treated as an assertion.

### Source passages

Wikipedia introductions, selected Wikipedia sections, primary-source transcriptions, and material
from other admitted sources are retained with provider identity, canonical page or record ID,
revision, retrieval metadata, checksum, licence, and attribution.

Raw source responses remain in the private build data. Public releases contain only the approved
normalized records and passages needed by the reader.

### Media

A Wikidata `P18` value or other image reference is only a candidate. Publication requires an exact
file revision, a per-file licence decision, creator and attribution information, checksum, and a
release-local artifact.

### Generated restatements

Generated wording is bound to the checksum of exactly the assertion excerpt or source passage it
restates. A source change makes the wording stale. Stale or rejected wording is omitted and the
reader falls back to structured data or source text.

## Plan A: composed map-selection sidebar

### Product goal

For a selected feature and year, assemble a small historical reading rather than expose a generic
ranked list of related entities.

The initial sidebar recipe should provide these slots when supported:

1. **Identity** — what the selected feature represents, its historical name, interval, and
   spatial meaning.
2. **What happened here** — events at or closely connected to the place around the selected year.
3. **People connected to it** — people with a meaningful, preferably dated relationship.
4. **Connected places** — capitals, predecessor or successor territories, trade destinations,
   event locations, or other explicit geographic connections.
5. **Life, society, and institutions** — population ranges, institutions, belief, language,
   technology, economy, or material culture where appropriate sources support them.
6. **Works and artifacts** — relevant texts, images, buildings, objects, or creative works.
7. **An interesting thread** — one bounded anecdote, name change, contemporary account, or
   unexpected but explicit connection.
8. **Explore next** — a deliberately varied set of nearby, relational, thematic, and
   geographically distant contemporary records.

A slot may remain empty. Weak material must not be promoted merely to fill the layout.

### Why the current result can feel random

The existing feature-context pipeline has valuable foundations: bounded relationship expansion,
temporal filtering, source-strength signals, role quotas, sharded joins, and lazy loading.
However, its score describes relationship strength under generic rules. It does not represent
historical importance, reader interest, or the quality of a composed set.

In particular:

- candidates enter through a shared one-hop relationship frontier;
- maximum role quotas prevent overflow but do not guarantee variety;
- a broad feature interval can be less specific than the visitor's selected year;
- a Wikipedia sitelink is a useful availability signal but a weak prominence measure;
- coarse regional discovery is useful for serendipity but not sufficient evidence of local
  influence;
- flat rendering exposes retrieval results instead of an editorial composition.

### Context candidate contract

Each retrieval strategy should emit a typed `ContextCandidate` with enough information to audit
eligibility and ranking:

```json
{
  "candidate_id": "ctx-candidate:...",
  "feature_id": "source:feature",
  "subject_entity_ids": ["wikidata:Q..."],
  "candidate_kind": "person",
  "eligible_slots": ["connected_people"],
  "valid_from": 1535,
  "valid_to": 1558,
  "relationship_path": [
    {
      "subject_id": "wikidata:Q...",
      "predicate": "position_held",
      "object_id": "wikidata:Q..."
    }
  ],
  "source_strength": "referenced_statement",
  "source_refs": ["source:..."],
  "reason_codes": [
    "direct_relationship",
    "active_in_selected_interval"
  ],
  "score_components": {
    "temporal": 30,
    "spatial": 0,
    "relationship": 35,
    "evidence": 20,
    "prominence": 10
  }
}
```

The exact schema should use the project's existing typed source references and confidence models.
The example illustrates the required semantics rather than fixing field names.

### Candidate generation strategies

Candidate generation should remain separate by intent:

- direct entity relationships;
- dated events and participation;
- dated offices and institutional roles;
- reviewed feature geometry and dated entity coordinates;
- predecessor, successor, and name continuity;
- thematic and evidence assertions;
- works and artifacts;
- bounded source passages;
- rights-approved media;
- regional contemporaries;
- geographically distant contemporaries for serendipity.

Each strategy supplies explicit reason codes. A single opaque relevance score is not an adequate
provenance record.

### Slot-specific ranking

Eligibility and ranking differ by slot.

For a person:

- require a meaningful relationship to the selected entity or event;
- prefer a role that overlaps the selected year;
- prefer referenced statements over unreferenced metadata;
- distinguish direct participation from broad membership or occupation;
- penalize repeated occupations or several people with effectively identical relevance.

For an event:

- prefer exact or overlapping chronology;
- prefer supported location or participant relationships;
- preserve annual versus approximate precision;
- avoid filling the sidebar with several episodes of the same conflict;
- distinguish an ongoing event from something that occurred in the selected year.

For a connected place:

- require an explicit relationship or supported spatial discovery reason;
- distinguish a capital, parent polity, event location, and grid-cell neighbour;
- never describe a coarse discovery-grid result as local influence.

Scores should preserve their components, such as temporal relevance, spatial relevance,
relationship strength, evidence quality, prominence, and diversity adjustment.

### Composition

After ranking within slots, a deterministic composition step should:

- enforce a small maximum number of cards;
- guarantee content-type variety when eligible material exists;
- suppress duplicate subjects and near-duplicate relationships;
- avoid excessive repetition of a single source, theme, polity, or conflict;
- prefer different paths for the "Explore next" choices;
- retain an inspectable reason for every displayed card.

The browser may run this final deterministic composition from verified candidate shards. The
pipeline may also precompute a default composition for testing and stable presentation. It should
not materialize every possible feature/year/lens combination.

### Context card contract

A displayed `ContextCard` should carry:

```json
{
  "card_id": "ctx:...",
  "slot": "connected_person",
  "subject_entity_ids": ["wikidata:Q..."],
  "valid_from": 1535,
  "valid_to": 1558,
  "title": "A ruler connected to this place",
  "body": {
    "kind": "single_source_restatement",
    "text": "...",
    "source_content_checksum_sha256": "...",
    "model_identifier": "..."
  },
  "why_shown": [
    "Held this position during the selected year",
    "Directly connected to the selected polity"
  ],
  "source_refs": ["source:..."],
  "media_id": null
}
```

The title and body may instead be deterministically assembled. Generated wording must be
identified, checksum-bound, and replaceable by a safe fallback.

### Sidebar artifact strategy

Publish reusable indexes rather than complete annual sidebars:

```text
feature -> candidate entities and assertions
entity -> dossiers, relationships, and restatements
region + time band -> dated records
theme -> classified records
media ID -> approved local media
```

The existing sharded content, context, region-time, assertion, thematic, and chronology artifacts
should be extended rather than replaced where their semantics already fit.

## Plan B: tiered year pages

### Product goal

Every selectable year should open honestly, but only evidence-rich years should receive
machine-written narrative.

Year pages have three levels.

### Level 1: year shell

A shell is available for every selectable year and does not require an exact-year artifact or an
LLM call. It can show:

- the selected year;
- map and browse links for records active in that year;
- release coverage information;
- nearby years with assembled or narrative pages;
- an explicit sparse-coverage message.

The absence of a dossier is a coverage state, not evidence that nothing happened.

### Level 2: assembled year

When sufficient structured material exists, the pipeline builds an exact-year artifact without
requiring an LLM. Depending on available evidence, it can contain:

- exactly dated and approximately dated events;
- births and deaths;
- wars and other processes in progress;
- rulers, offices, and institutions active during the year;
- works created, published, or completed;
- mapped places and entities active during the year;
- thematic and geographic counts;
- source-backed, rights-approved images;
- a chronological register;
- cross-links to related years.

These sections are filtered, grouped, and rendered from data. The pipeline controls their labels,
ordering, links, dates, and relationships.

### Level 3: narrative dossier

An assembled year with sufficiently rich and diverse evidence may receive bounded machine-written
sections:

- an overview of major themes;
- short treatments of prominent events;
- carefully bounded historical strands;
- limited transitions that make the structured material easier to read.

The mechanically assembled page remains the fallback. Rejected or stale generated sections are
omitted rather than accommodated by weakening validation.

### Year coverage profile

Before invoking an LLM, build a `YearCoverageProfile`:

```json
{
  "year": 1543,
  "exact_events": 96,
  "ongoing_events": 8,
  "people": 42,
  "works": 11,
  "places": 57,
  "regions_represented": 9,
  "source_pages": 10,
  "source_diversity": 3,
  "dated_records": 54,
  "rights_approved_images": 6,
  "coverage_grade": "rich"
}
```

The eventual schema should record the inputs behind each count and the policy version that
produced the grade.

Initial coverage states are:

```text
insufficient -> year shell
usable       -> assembled year
rich         -> eligible for a narrative dossier
```

Eligibility must consider more than record count:

- geographic breadth;
- thematic breadth;
- source diversity;
- event and entity-type diversity;
- date precision and uncertainty;
- usable source text;
- duplication;
- imbalance toward one region or elite political biography;
- rights-approved media availability, without requiring it.

Thresholds should be conservative and calibrated against rendered pages.

### Narrative build process

For an eligible year:

```text
1. Build the complete structured year packet.
2. Hash its evidence and source revisions.
3. Assemble all safely renderable sections.
4. Divide remaining prose into bounded tasks.
5. Generate each section from its own evidence packet.
6. Validate each section against that packet.
7. Retry rejected stochastic failures without weakening the contract.
8. Publish accepted sections with the assembled page and input fingerprint.
```

The evidence packet for a block about a publication should not include unrelated wars, births, or
political transitions merely because they occurred in the same year. Narrow packets reduce the
opportunity to fuse unrelated facts.

The prominent lede should remain assembled from source material or structured records wherever
possible. The model should write only the prose that adds enough reading value to justify its
additional risk.

### Incremental year generation

Year artifacts should be independently buildable and reusable:

```text
build coverage profile for one year
build assembled artifact for one year
generate or refresh narrative for one year
batch eligible years by coverage and a stated limit
```

Each dossier fingerprint should include at least:

- chronicle checksum;
- structured year-context checksum;
- relevant source revision IDs;
- prompt version and checksum;
- model identifier;
- generation and validation policy checksum.

An unchanged fingerprint reuses the accepted artifact. Changed evidence makes the narrative stale;
it does not silently drift.

The long-term release may contain assembled pages for many years and narrative dossiers for a
smaller subset. Completeness means that unsupported years are handled honestly, not that every
year contains generated prose.

## Storage and publication

A conventional request-time database is not required.

Local build storage continues to distinguish:

```text
data/raw/                 downloaded source snapshots
data/cache/               reusable acquisition cache
data/staged/canonical/    normalized canonical records
data/editorial/           generated and editorial intermediates
dist/data/builds/         immutable public releases
```

A build-time DuckDB database or equivalent analytical projection may be used for temporal,
relational, and geographic joins. It should be reproducible from canonical inputs and should not
become an undocumented source of truth.

Production publication continues to use immutable release artifacts in object storage:

```text
latest.json
builds/<build-id>/manifest.json
builds/<build-id>/context/...
builds/<build-id>/content/...
builds/<build-id>/region-time/...
builds/<build-id>/years/...
```

A request-time service should be reconsidered only if the product later requires immediate source
updates, personalized recommendations, arbitrary graph queries, accounts, saved journeys, or
continuous editing outside the release process.

## Implementation phases

### Phase 1: define contracts

Specify and schema:

- `ContextCandidate`;
- `ContextCard`;
- the composition policy and slot vocabulary;
- `YearCoverageProfile`;
- assembled-year content;
- year-index entries that distinguish `shell`, `assembled`, and `narrative`.

Prefer additive schema changes so existing 1.x releases remain readable.

### Phase 2: audit current output

Select a diagnostic matrix containing:

- a polity;
- an ancient settlement;
- a medieval or early-modern city;
- an event;
- an institution, work, or artifact;
- a record with little enrichment.

Inspect each near the beginning, middle, and end of its active interval, plus one outside year
where appropriate.

For every current sidebar item, record:

- its admission path;
- temporal appropriateness;
- relationship correctness;
- evidence strength;
- reader value;
- duplication;
- which slot, if any, it should occupy.

For year pages, include a modern year, a nineteenth-century year, a medieval year, an ancient
year with approximate evidence, and an intentionally sparse year alongside the existing pilots.

### Phase 3: build the candidate layer

Split candidate generation by intent, preserve explicit reason codes and score components, and
publish verified reusable shards.

### Phase 4: implement deterministic sidebar composition

Add slot-specific eligibility, temporal filtering against the selected year, duplicate
suppression, diversity rules, and honest empty states. Render real examples before expanding
source acquisition.

### Phase 5: improve source coverage selectively

Use the audit to prioritize:

- additional useful Wikidata predicates;
- controlled inverse relationships from a pinned local projection;
- selected Wikipedia sections;
- ongoing event intervals;
- office and role chronology;
- specialized historical datasets;
- Commons metadata and per-file rights decisions.

Do not broaden ingestion merely to increase candidate counts.

### Phase 6: add bounded wording

Generate reusable restatements for one assertion or source passage at a time. Bind every output to
its input checksum and preserve a deterministic fallback.

### Phase 7: implement assembled year pages

Build coverage profiles and deterministic pages for a small, historically varied pilot set.
Render and inspect them before defining production eligibility thresholds.

### Phase 8: generate eligible narratives

Generate a limited batch of evidence-rich years. Measure relationship or fusion errors against
each block's cited records, then adjust packet boundaries, prompting, and validation before
scaling.

### Phase 9: publish and evaluate

Verify manifests, shard placement, joins, source checksums, generated-content freshness, media
rights, page-level indexes, and browser fallbacks.

## Evaluation

### Sidebar measures

- temporal relevance to the selected year;
- correctness of every displayed relationship;
- variety across people, events, places, institutions, works, and themes;
- source diversity;
- duplicate and near-duplicate rate;
- percentage of cards with a clear, accurate "why shown" explanation;
- proportion of empty slots versus weakly filled slots;
- useful navigation to another map record or year.

### Year-page measures

- geographic and thematic coverage balance;
- citation and link completeness;
- relationship-fusion error rate;
- proportion of the page assembled versus generated;
- generation rejection and retry rate;
- stale-artifact rate;
- sparse-year honesty;
- correctness of ongoing-state intervals and related-year links.

Automated validation establishes a floor. Rendered inspection remains necessary because poor
selection, awkward repetition, misleading emphasis, and broken reading flow may satisfy every
schema.

## First milestone

The first milestone is:

> Produce strong deterministic sidebars for five representative map records and strong assembled
> year pages for seven historically varied years, without adding new LLM prose.

After that milestone, add bounded machine-written wording and compare whether it materially
improves clarity and discovery. This establishes what retrieval and composition solve before
committing to large-scale generation.

## Non-goals

This plan does not:

- generate a narrative dossier for every year in advance;
- introduce a request-time LLM or Wikimedia dependency;
- treat Wikipedia prose as structured evidence;
- infer that a coarse geographic neighbour was locally influential;
- make absence from a sidebar or year page evidence of historical absence;
- add a mandatory human-review gate;
- replace immutable releases with a mutable production database.
