# Context sidebar and year-page audit and revised plan

Status: audit complete; implementation proposed
Audit date: 2026-07-27
Scope: map-selection reading surface, year pages, their release artifacts, and the joins between
them

## Executive finding

The current reader has four different problems, and they must not be treated as one ranking
problem:

1. **Release capability regression** — the inspected release with year pages has almost no
   enrichment, while the enriched release has no year pages.
2. **Join correctness** — some feature-to-entity links are conceptually or temporally unsuitable
   for reader-facing prose.
3. **Temporal semantics** — entity lifetimes, relationship dates, source attestation periods, and
   historical activity are currently used too interchangeably.
4. **Composition and hierarchy** — even good historical material is placed below classification,
   geometry, naming, and provenance apparatus.

The proposed composed sidebar remains the correct product direction, but composition must be the
fourth step, not the first. A better composer would otherwise make wrong or irrelevant content
more persuasive.

The first milestone should produce a single release that contains both enrichment and year pages,
passes semantic and temporal join gates, and renders six reader-first sidebar examples without
new generated prose.

## Implementation checkpoint — 27 July 2026

The first release and reader-safety work from this plan is now implemented and verified in full
tile-enabled build `bd97e0a95685bc5e`:

- one build contains 51,440 feature links, 10,696 entities, 10,848 dossiers, and the 1492 and
  1543 year dossiers;
- 23,597 features have enriched entities and 25,553 have linked dossiers, clearing the declared
  40% and 45% publication floors;
- every feature-to-entity join now publishes an auditable reading-eligibility decision;
- 1,896 decisions are rejected for an explicit interval conflict, 40,859 remain ineligible
  because their interval is unresolved, and 38,205 Pleiades joins are retained as unverified
  place continuity rather than treated as unqualified historical identity;
- 3,778 joins are labelled as broader topics after a feature/entity kind mismatch, and 6,981
  features currently have an eligible primary entity reading;
- British Africa at 1930, Roman Empire at 100, and Ugernum at 100 all receive the intended
  ineligible decisions in the release data;
- the sidebar suppresses ineligible prose, moves useful sourced facts ahead of lens apparatus,
  hides unresolved relationship targets, applies relationship date qualifiers, and collapses
  coarse geographic discovery to three suggestions;
- aggregate Seshat facts remain attached to parent polities but are no longer fanned out to
  component geometries that merely repeat the parent's Seshat identifier;
- the Copernicus publication carries an explicit curated adjacency to the 1543 year dossier;
- exact feature source records are now carried into map tiles, avoiding the former
  source-level representative-record error.

The build contains 4,782 artifacts and all four era PMTiles and became the local
`dist/data/latest.json` release after its publication gates passed. The remaining
first-milestone work is a visual six-selection review and refinement of the adaptive composition,
especially for the two Timurid dates and a sparse unreconciled Pleiades record.

## What was audited

The audit used:

- current local release `77588322d9cc5afd`, generated 2026-07-25;
- enriched local release `78823c0b088a2ff2`, generated 2026-07-24;
- the published content, context, assertion, theme, region-time, search, and year artifacts;
- the Python builders and TypeScript loading paths that produce the rendered reading surface;
- headless rendered selections against the enriched release;
- the existing 1492 and 1543 year dossiers.

No live Wikimedia request or new model generation was used. The enriched release was rendered by
intercepting only the local `latest.json` pointer; its immutable artifacts were not modified.

The diagnostic selections were:

| Selection | Year | Why it was included |
| --- | ---: | --- |
| British Africa | 1930 | The reported empty-dossier experience |
| British Africa, enriched build | 1930 | Same feature with source content available |
| Timurid Empire | 1400 / 1507 | Repeated polity geometry and an enrichment boundary |
| Roman Empire | 100 | Long-lived polity with multiple identities and dossiers |
| Ugernum | 100 | Ancient place linked to a modern administrative article |
| Publication of *De revolutionibus* | 1543 | Strong structured-evidence pilot |
| Damery | 100 | Sparse Pleiades record with no reconciled entity |
| Year pages | 100, 1492, 1543 | Empty shell, narrative pages, and map joins |

This is a diagnostic audit, not a statistically representative content-quality sample. The
release-wide counts below show whether the observed failure classes are isolated or systemic.

## Release-wide results

### The current release does not carry the enrichment needed by the sidebar

The current release contains:

| Artifact | Count |
| --- | ---: |
| Mapped features | 51,440 |
| Enriched entities | 18 |
| Source dossiers | 0 |
| Restatements | 0 |
| Feature context projections | 3 |
| Year dossiers | 2 |

Only 3 of 51,440 feature links have an available entity. All 51,440 links report at least one
missing entity, and 51,437 have no available entity at all.

The empty British Africa dossier is therefore representative of this release. No ranking or UI
change can manufacture a historical reading from it.

### The enriched release and year release are currently separate products

The enriched release contains:

| Artifact | Count |
| --- | ---: |
| Mapped features | 51,440 |
| Enriched entities | 10,723 |
| Source dossiers | 11,400 |
| Feature context projections | 23,795 |
| Year dossiers | 0 |

The later release contains the two year pages but regresses from 10,723 to 18 entities and from
11,400 to zero dossiers. The inspected releases never combine the two halves of the intended
product.

Publication must therefore distinguish a deliberately thin development build from a reader
release. A build that adds year pages must not silently remove nearly all place reading content
when it advances `latest.json`.

### Even the enriched release has limited useful context coverage

Of 51,440 mapped features in the enriched release:

- 23,795 have a context projection;
- 7,770 of those projections are empty;
- 16,025 features, about 31%, have at least one context item;
- 27,645 features have no available canonical entity;
- 25,722 have at least one source dossier.

The 46,799 context items are heavily concentrated:

| Role | Items | Share |
| --- | ---: | ---: |
| Polity | 18,437 | 39.4% |
| Institution | 11,806 | 25.2% |
| Other | 7,156 | 15.3% |
| Place | 5,852 | 12.5% |
| Event | 3,244 | 6.9% |
| Person | 224 | 0.5% |
| Theme | 80 | 0.2% |

Role quotas cap overflow but have not produced a varied reading layer. Almost two thirds of
context items come from polity and institution classifications; people are effectively absent.

### Evidence strength and chronology are too weak for year-specific claims

Of the 46,799 context items:

- 29,933, or 64%, are unreferenced Wikidata statements;
- 15,813, or 34%, have no temporal bounds;
- only 18,799 have both a start and an end.

The underlying enriched entities contain 83,488 relationships. There are 10,594 relationships
with a start, end, or point-in-time qualifier, but the context builder does not normalize those
qualifiers into the context interval. It instead compares the target entity's broad interval with
the mapped feature interval.

Consequently, the current artifacts may support “this person is connected to this office,” but
not necessarily “this person held the office in the selected year.”

### Related targets frequently degrade to raw identifiers

Feature links contain 247,518 related-entity occurrences. In the enriched release, 139,954 of
those occurrences, or 57%, refer to entities not present in the content collection.

The current rendering falls back to strings such as `wikidata:Q2353647`. A raw identifier is
useful debugging information but is not a reader-facing historical connection.

### Regional discovery is geographic retrieval, not composed context

The region-time index contains 198,173 entry occurrences:

- 197,577 are mapped-feature/grid intersections;
- 596 are standalone dated Wikidata entities.

This explains the rendered result: a selected record receives up to 60 things whose geometries
intersect the same 10-degree cell and time band. The list is valuable as a retrieval substrate,
but it is not evidence of historical connection and cannot occupy the same editorial position as
an explicit event or relationship.

The 1930 British Africa selection showed archaeological sites, water features, settlements, and a
polity in one long list. The 1543 Copernicus selection showed remote Italian sites and duplicate
Holy Roman Empire-related geometries. The caveat is accurate, but the volume and placement still
make the list feel like content rather than a coarse discovery fallback.

### Search and discovery inherit broad source periods

The search export contains 36,485 records:

- 19,102 archaeological sites;
- 15,974 settlements;
- 1,406 polities;
- 3 events.

It also contains 3,561 records displayed as “Untitled.” There are 3,279 duplicated display-name
groups containing 10,812 records. Some duplication is legitimate historical homonymy, but the
current result list cannot always distinguish repeated geometry slices from distinct places.

Pleiades intervals are explicitly source attestation intervals. They are nevertheless used by
search, “elsewhere in this year,” and region-time filtering in ways that read like historical
activity. An archaeological place attested in Pleiades's modern period can therefore appear as
`1700–2100` in a 1930 discovery list. This is not necessarily false, but it answers “the source
attests this place in this period,” not “this was historically active in 1930.”

The contracts need an explicit distinction between:

- historical activity or existence;
- source attestation;
- observation or modern identification;
- a geometry version or rendering interval.

## Rendered-selection findings

### British Africa, current release, 1930

The reading surface contains:

- lens classification;
- shape semantics;
- name evidence;
- an explicit missing-dossier message;
- confidence and provenance;
- coarse regional and distant contemporaries.

The failure is primarily missing enrichment, followed by hierarchy. The page correctly refuses
to invent content, but the remaining technical apparatus becomes the main experience.

### British Africa, enriched release, 1930

The enriched feature is joined to Wikidata `Q179848`, “Scramble for Africa.” The Wikidata entity
has an interval of 1885–1914, while the selected mapped feature is 1930–1931 and the map's “British
Africa” sequence continues to 1960.

The reader therefore receives:

- a Wikidata description of late nineteenth- and early twentieth-century colonisation;
- a full “Scramble for Africa” Wikipedia introduction;
- no composed context items;
- three connected records rendered only as Wikidata identifiers;
- a long regional list.

This is more content but not a better result. The entity association may be useful source
metadata, but it is not eligible for an unqualified place-at-1930 reading. This proves that
content availability and content eligibility must be separate fields.

### Timurid Empire

The enriched search contains a reconciled Timurid Empire entity for the 1375–1506 feature
sequence and separate feature-only “Timurid Empire” records for 1507 onward. A search for the name
can surface multiple visually identical options; the audited interaction selected the 1507–1511
record even though the page year was 1400.

The later feature has no dossier and falls back to the metadata-heavy empty state. The case shows
that:

- repeated feature slices need a stable entity-aware presentation;
- search must prefer the record active in the chosen year;
- an enrichment boundary should not look like the history itself abruptly lost identity.

### Roman Empire, 100

The selected feature is named “Roman Empire,” but its entity presentation includes “Byzantine
Empire” and “Eastern Roman Empire,” describes a Late Antique and medieval state, and renders both
the Byzantine Empire and Roman Empire introductions in full.

The first source extract begins 939 pixels down the scroll surface. The context section begins at
4,409 pixels, after two long encyclopedia introductions. Context then includes successors whose
intervals start centuries after the selected year. They are explicitly labelled successors, but
the set is not composed around the visitor's question about 100 CE.

This case combines identity ambiguity, year-agnostic source text, oversized source passages, and
flat relationship rendering.

### Ugernum, 100

The ancient place is linked to the current commune of Beaucaire. The reader receives a modern
administrative description and a Wikipedia introduction whose second paragraph discusses a 2020
town-and-villages award.

The entity link may be correct as place continuity, but the passage is not useful historical
reading for 100 CE. The existing dossier-restatement architecture was designed to put history
first, but no restatements are published in the inspected enriched releases.

This selection also exposed a provenance display bug. The exact feature source is “Pleiades:
Ugernum,” but the browser obtains the manifest's one source-level representative and displays
“Pleiades: Mysia II (province)” as the geometry source. A source registry record must be generic,
or the feature must expose its exact source reference; a representative record cannot stand in
for every feature.

### Publication of *De revolutionibus*, 1543

This is the strongest audited selection. It has five precise structured assertions from Library
of Congress metadata and a short, relevant Wikipedia extract.

Even here:

- two lens explanations occupy the first 444 pixels after the header;
- structured sourced facts start at 641 pixels;
- the source reading starts at 1,766 pixels;
- regional discovery supplies 60 results and contains duplicates;
- the selection has no direct route to its corresponding 1543 year-page entry.

The case proves that the project already possesses useful material. The immediate need is to move
it above the machinery and connect it to the rest of the product.

### Sparse Pleiades records

Records such as Damery have a mapped feature but no reconciled entity or dossier. They cannot
support a rich local reading without further acquisition. Their safe experience should be:

- a compact identity and spatial description;
- an explicit coverage state;
- a small number of clearly labelled nearby or contemporary routes;
- collapsed technical evidence.

They should not expand metadata merely to fill the sidebar.

## Reading-order finding

For the audited enriched selections, the first reader-facing source material begins after:

| Selection | First useful material | Scroll offset |
| --- | --- | ---: |
| British Africa | Wikidata description | 752 px |
| Roman Empire | Wikidata description | 752 px |
| Copernicus publication | Structured assertions | 641 px |

The current order is approximately:

```text
identity
classification
shape semantics
name apparatus
source reading
context
confidence and provenance
regional discovery
elsewhere
```

The desired order is:

```text
identity at the selected year
best supported historical reading
events / people / institutions / works
small set of explicit and varied connections
explore next
collapsed map interpretation, classification, confidence, and provenance
```

Provenance must remain reachable and precise. It does not need to precede the history it supports.

## Year-page findings

### Only shell and narrative currently exist

The frontend has:

- an honest “no dossier” state;
- complete narrative dossier rendering for 1492 and 1543.

It does not have the proposed assembled-only middle tier. A year such as 100 shows no active map
records, chronology, counts, or discovery paths even though 3,300 search records overlap that year
under the current interval rules.

The year index only describes narrative dossiers; it has no `shell`, `assembled`, or `narrative`
status.

### The narrative architecture is already substantially complete

The two dossiers already contain assembled ledes, overviews, anchors, registers, ongoing wars,
images, incumbents, related-year links, and block-scoped generated prose. The fusion audit and
release verification also exist.

The next year-page work is therefore:

- coverage profiling;
- assembled-only pages;
- historically safe use of mapped records;
- map/entity joins;
- broader calibration.

It is not a rewrite of the narrative dossier pipeline.

### The map-to-year join is nearly absent

The 1492 register contains 100 distinct Wikidata-tagged subjects. Three have a mapped search
record active in that year.

The 1543 register contains 148 distinct Wikidata-tagged subjects. Four have a mapped search
record active in that year.

The year UI links subjects to source articles, not to mapped features. The map UI does not link
the Copernicus publication event to its matching year anchor or register record.

The IDs needed for a bounded join mostly exist, but no release artifact publishes the
year-entry-to-feature adjacency.

## Revised product rules

### A useful primary card must say something historical

A primary sidebar card must communicate a source-backed proposition beyond:

- the name;
- the mapped interval;
- the feature type;
- its lens classification;
- its confidence grade;
- its source or licence.

Those fields remain essential apparatus, but they do not count as historical reading.

### Availability is not eligibility

A source passage, dossier, relationship, or image may be present in the release and still be
ineligible for a selected feature and year.

Eligibility requires:

- a defensible identity relation;
- compatible temporal semantics;
- a source role appropriate to the claim;
- a displayable target;
- enough content to improve the reading.

### A missing insight is better than a misleading one

Empty slots remain valid. If no historical insight clears the gates, the interface should state
the coverage limitation and offer a few honest navigation routes. It should not promote generic
metadata, raw IDs, modern administrative prose, or coarse grid neighbours to fill space.

### Technical evidence supports the reading

Shape meaning, lens rules, confidence axes, licences, exact source records, and validation
evidence should remain in the page, grouped under a collapsed “About this map record” section.
Warnings that materially change interpretation may remain visible near the relevant claim.

## Revised implementation plan

### Phase 0: make a complete reader release reproducible

Add a declared release capability profile:

```text
map
search
enrichment
source dossiers
context
assertions
restatements
year pages
approved media
```

For the reader/publication profile:

- assemble enrichment and year artifacts in the same build;
- publish counts and coverage percentages in the manifest or a linked report;
- fail publication when required capabilities are absent;
- prevent `latest.json` advancement when critical reader coverage regresses beyond an explicit
  policy threshold;
- keep smoke and diagnostic builds non-advancing;
- verify that an offline rebuild reuses valid staged enrichment rather than silently dropping it.

Acceptance:

- one verified release contains the existing enriched place content and both year dossiers;
- the publication check detects the 10,723 → 18 entity and 11,400 → 0 dossier regression.

### Phase 1: gate feature-to-content joins

Extend the feature-content link with an eligibility decision, not a second canonical identity:

```json
{
  "entity_id": "wikidata:Q...",
  "identity_basis": "source_asserted",
  "identity_relation": "exact_match",
  "temporal_overlap": "none",
  "reading_eligible": false,
  "reason_codes": ["entity_interval_ends_before_feature"]
}
```

Required work:

- compare feature and entity intervals without treating either as automatically authoritative;
- distinguish exact identity, place continuity, broader topic, and related concept;
- refuse a primary dossier when the relation is merely topical or temporally incompatible;
- retain rejected links for audit without rendering their prose as the feature's reading;
- add release checks for impossible or unexplained interval mismatches;
- stop rendering raw target IDs as connected-record cards;
- fix source display so it uses the feature's exact reference or a genuinely generic registry
  record.

Acceptance:

- British Africa at 1930 does not present “Scramble for Africa” as its unqualified primary dossier;
- Roman Empire at 100 does not lead with an inapplicable Byzantine identity;
- Ugernum can retain Beaucaire continuity without presenting a 2020 municipal award as ancient
  context;
- the geometry source shown for Ugernum is Ugernum, not another Pleiades record.

### Phase 2: normalize temporal semantics

Add explicit temporal basis vocabulary to reader-facing candidates:

```text
activity
existence
relationship_validity
source_attestation
modern_identification
geometry_version
unknown
```

Required work:

- normalize `P580`, `P582`, and `P585` relationship qualifiers;
- preserve date precision, uncertainty, statement rank, and references;
- score a relationship against its own interval, not merely the target entity's interval;
- reserve “during this year” for overlapping activity or relationship-validity evidence;
- label attestation-period records as attestations rather than active contemporaries;
- keep predecessor/successor navigation outside the year window, but in an explicitly separate
  continuity module;
- separate exact-year filtering from optional discovery margins.

Acceptance:

- every displayed “in this year” explanation is mechanically supported by the relevant assertion
  or relationship interval;
- the 10,594 already retained time-qualified relationships are used or explicitly rejected;
- modern Pleiades attestations do not read as evidence that an ancient site was historically
  active in 1930.

### Phase 3: create an auditable candidate projection

Build `ContextCandidate` as a projection over existing evidence, not a parallel source of truth.

It should contain:

- selected feature ID;
- subject and target entity/feature IDs;
- candidate kind;
- eligible modules;
- assertion or relationship IDs;
- normalized temporal basis and interval;
- spatial basis;
- source references and evidence strength;
- reason codes;
- score components;
- display-content IDs;
- safe fallback state.

Candidate generation remains separate for:

- precise assertions;
- dated direct relationships;
- events and participation;
- offices and institutions;
- continuity;
- works and artifacts;
- approved source passages and restatements;
- regional discovery;
- distant contemporaries.

Do not publish a generated `ContextCard` for every feature/year combination. The browser may
deterministically turn verified candidates into view models.

Acceptance:

- every candidate can be traced to existing canonical records;
- changing the composition policy does not duplicate or rewrite historical evidence;
- score components and reason codes reproduce the displayed decision.

### Phase 4: implement the reader-first sidebar

Use four adaptive modules rather than requiring eight permanent slots:

1. **At this date** — best eligible identity, source reading, or structured assertions.
2. **Happening and connected** — dated events, people, institutions, works, and explicit places.
3. **Continue the thread** — continuity, related subjects, and a bounded interesting passage.
4. **Explore the year** — a small, varied set of map and year routes.

Presentation rules:

- put the first useful proposition within the first screen after the header;
- cap the composed reading at roughly five to eight cards;
- suppress duplicate subjects, relationships, geometries, and source passages;
- cap coarse regional results at three unless the visitor expands them;
- never render an unresolved ID as a card title;
- keep grid-cell discovery visually and semantically separate from direct relationships;
- move lens rules, shape explanation, name apparatus, confidence, and provenance under “About
  this map record”;
- retain visible warnings beside claims they qualify;
- render an explicit coverage fallback when no primary insight is eligible.

Use deterministic text first. Do not add new generated sidebar wording in this phase.

Acceptance:

- the Copernicus assertions appear before lens explanations;
- British Africa's thin state is compact and offers honest next routes;
- Roman Empire does not render two full encyclopedia introductions before context;
- no primary card consists only of classification or provenance metadata.

### Phase 5: improve useful source coverage selectively

Measure candidate coverage after the composer exists, then acquire only material that fills
observed reader gaps.

Priorities:

- publish valid existing dossier restatements so historical content precedes modern
  administrative material;
- retain selected history sections or bounded passages, revision-pinned like introductions;
- enrich relationship targets that are repeatedly selected but currently unresolved;
- expand people and dated-event relationships where references and qualifiers support them;
- build reusable assertion restatements only when deterministic rendering is too thin;
- continue per-file media rights checks.

Generated wording remains one assertion or one bounded passage at a time. It does not choose
content, establish joins, or invent selected-year relevance.

Acceptance:

- the share of features with at least one useful eligible insight increases;
- person and event coverage improves without increasing unreferenced filler;
- ancient places do not default to modern administrative leads when a historical passage exists.

### Phase 6: build the map-to-year join

Publish bounded adjacency:

```text
year register entry -> entity ID -> eligible feature IDs
feature/entity ID -> year register and anchor IDs
```

Verify:

- entity identity;
- feature interval and temporal basis;
- year membership;
- both sides of the adjacency;
- target year availability.

Reader behavior:

- a mapped year subject offers “Show on the map”;
- a selected map event or entity offers “Read this in 1543” when the year artifact contains it;
- a missing exact match may offer the year page generally, but must not imply that the selected
  record appears there.

Acceptance:

- the Copernicus map event opens its 1543 year treatment;
- mapped 1492/1543 subjects receive verified links;
- the join never relies on titles.

### Phase 7: add assembled-only year pages

Keep the existing narrative dossier architecture. Add:

- `YearCoverageProfile`;
- an assembled year artifact;
- year index statuses: `shell`, `assembled`, `narrative`;
- an honest shell that can show safe active/attested map records and nearby richer years.

Coverage profiles must distinguish:

- source documents;
- providers or collections;
- independent evidence authorities;
- exact, approximate, and attestation-only chronology;
- geographic, thematic, and entity-type breadth;
- duplication and concentration;
- eligible mapped joins;
- approved media.

The grade must include reason codes and policy version, not only a scalar label.

Acceptance:

- year 100 provides useful deterministic routes without generated prose;
- an assembled page remains complete when all narrative blocks are removed;
- 1492 and 1543 continue to render their existing narrative dossiers;
- source-page count is not mislabelled as independent source diversity.

### Phase 8: evaluate before scaling

Maintain a permanent diagnostic matrix containing:

- a long-lived polity;
- a disputed or broad territorial label;
- an ancient settlement with modern continuity;
- a medieval or early-modern polity;
- an event with structured assertions;
- a work or artifact;
- a sparse unreconciled record.

Inspect the beginning, middle, and end of each interval, plus an outside year where meaningful.

Track:

- percentage of selections with at least one useful primary insight;
- feature-to-content join rejection reasons;
- correctness of every year-specific relationship;
- referenced versus unreferenced candidate share;
- first-useful-content scroll offset;
- raw-ID display count;
- duplicate-card rate;
- regional discovery expansion rate;
- map-to-year link coverage;
- source and temporal-basis diversity;
- generated wording rejection, staleness, and fusion audit results.

Only after these pass should the project generate additional sidebar restatements or narrative
years at scale.

## First milestone

Build and render a deterministic six-selection reader pilot:

1. British Africa, 1930;
2. Roman Empire, 100;
3. Ugernum, 100;
4. Timurid Empire, 1400 and 1507;
5. Publication of *De revolutionibus*, 1543;
6. one sparse unreconciled Pleiades record.

The pilot must:

- use one combined enrichment-and-years release;
- gate temporally or conceptually unsuitable primary dossiers;
- use relationship qualifiers for selected-year claims;
- put useful historical content before technical apparatus;
- show no raw entity IDs;
- limit coarse discovery to three collapsed suggestions;
- provide honest coverage fallbacks;
- link the Copernicus event to the 1543 year page;
- introduce no new generated prose.

This milestone tests the product hypothesis with existing evidence. If these six examples do not
feel substantially more historical and less like data inspection, expanding acquisition or
generation would be premature.
