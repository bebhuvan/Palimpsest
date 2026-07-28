# Frontend data contract

The visitor-facing application is static. It needs no database, server function, API secret, or
request-time call to Wikimedia, OWID, or an AI provider.

## Bootstrap

1. Fetch `<data-base>/v1/latest.json` with normal revalidation.
2. Reject an unsupported major `schema_version`.
3. Fetch the relative manifest named by `manifest` and verify `manifest_checksum_sha256` before
   trusting its artifact paths.
4. Resolve every artifact relative to `<data-base>/v1/builds/<build_id>/`; do not invent paths.
5. Cache immutable artifacts freely. A new release changes only `latest.json`.

The frontend should expose the build timestamp, `quality.json`, `coverage.json`, and
`attribution.json` somewhere discoverable. Missing coverage must look different from a claim that
no polity or event existed.

## Historical map layer

Each era PMTiles archive contains two vector layers:

- `history` contains the reviewed source geometry;
- `history_labels` contains representative points for reviewed historical-name attestations.

The `history` public properties are:

- `feature_id`, `name`, and `kind`;
- non-exclusive reviewed `themes` used for thematic discovery;
- `valid_from` and `valid_to` using BCE-negative/CE-positive years with no zero;
- `spatial_meaning`;
- independent `temporal_confidence`, `spatial_confidence`, and `interpretive_confidence`;
- `review_status`, `dispute_group`, `perspective`, `wikidata_id`, and `min_display_zoom`;
- `primary_entity_id` and `content_shard`, which are stable content joins;
- boolean `temporal_uncertainty` and `spatial_uncertainty` flags. Full rationales remain outside
  vector tiles.

Select the era archive from the chosen year, then filter features where
`valid_from <= selectedYear && valid_to >= selectedYear`. Moving from 1 BCE to 1 CE must skip zero.
MapLibre may overzoom the global archive beyond its generated maximum zoom, but the UI should not
imply extra precision. Later local-detail archives can be additional sources.

Filter `history_labels` by the same validity rule and by `primary == true` for the default label
mode. Labels carry `label_id`, language, optional script, name kind, their independent date
precision and confidence, and a `temporal_basis`. `attested` means the source independently dates
the name; `feature_interval` means the adapter only supplied a feature-level display name. The UI
must disclose that distinction. Reviewed labels are rendered above reviewed geometry and remain
separate from OHM labels.

Geometry with `spatial_meaning=location` must not be styled as territorial fill. Pleiades
settlements and archaeological sites use the representative points in `history_labels`, appearing
as restrained marks and labels from zoom 6 onward. A source location extent or precision envelope
must never read as a bordered polity.

## Live OpenHistoricalMap context

The default map composition is, from bottom to top:

1. bundled, low-resolution Natural Earth land plus quiet, label-free physical water, labelled as
   modern reference geography;
2. live OpenHistoricalMap contributor detail;
3. an optional rights-approved historical map image, disabled by default;
4. the release's reviewed Palimpsest PMTiles reconstruction;
5. OpenHistoricalMap historical labels.

OpenHistoricalMap is context, not a source in the immutable Palimpsest release. Its geometry
must not be merged with the reviewed PMTiles or used to overwrite canonical confidence,
interpretation, dispute or provenance fields. The layer control exposes `Combined`, `Historical
detail`, and `Reviewed reconstructions`; combined is the default.

The thematic lens control is separate from this source-role control. It exposes `All`, `Power`,
`Belief`, `Knowledge`, `Culture`, and `Trade`, with `All` as the default. Lens state is encoded in
the URL. OHM context may be filtered using explicit vector feature types, but never by matching
words in a feature name. A filtered-out or empty lens must be described as missing classified
coverage, not historical absence. Records may belong to more than one lens.

Every schema 1.8-or-newer release declares `theme_index_path`. When a reviewed feature is selected,
the reader loads its feature adjacency shard and only the assertion shards it names. The panel shows
why the record was classified, the exact matched structured values, rule ID, confidence, review
state and source links. If the active lens has no assertion, the baseline feature may remain visible
but the interface explicitly says that it is not classified in that lens.

Every schema 1.10-or-newer release also declares `assertion_index_path` and
`layer_catalog_path`. The assertion index is loaded lazily by selected feature. The reading
surface composes labels from its structured predicate and typed object, labels the records as
sourced facts rather than narrative, and exposes confidence and source links. It must not turn
these records into causal claims.

An assertion object may also be a `number_range`, with independently optional lower and upper
bounds plus a required unit. Do not collapse a range to its midpoint or present either bound as a
precise measurement.

Selected Seshat assertions can carry an original `source_excerpt`, references named inside that
excerpt, and an optional `restatement`. The restatement modernizes and shortens only that one
explanation. Render the structured value first, identify the generating model, and keep the
original explanation reachable in the same record. Ignore a restatement whose
`source_excerpt_checksum_sha256` differs from its assertion. Missing Seshat assertions mean
“not coded in this release,” never that the institution or technology was historically absent.

Map-source controls, thematic lenses and evidence overlays remain separate controls. A confidence
overlay styles one declared confidence axis; a provenance overlay styles source identity/licence.
Neither changes the active thematic lens, source visibility, chronology or underlying data.

The historical-map-image control is another map-source control, not a thematic or evidence
overlay. It lists only `HistoricalMapMetadata` records from the immutable release that have three
distinct approved rights decisions, a release-local image artifact with a matching checksum,
explicit render coordinates and known limitations. The UI exposes depicted date, provider,
attribution, metadata/image/georeference licences, georeference confidence and limitations.
Scanned depictions are not selectable canonical geometry and must not intercept reviewed/OHM map
clicks. No URL supplied by a visitor may become a map source.

Lens rendering never replaces source geometry. Matching polygons retain their sourced extent,
matching routes retain their line geometry, and matching places/events retain a representative
point. Selecting a lens strongly dims other published history, applies a lens-specific colour,
marker and line pattern to matches, and reports the number of classified release records active at
the selected date. A zero count is an explicit thematic coverage gap, not historical absence.

The official source contracts are `https://vtiles.openhistoricalmap.org/maps/ohm.json`,
`osm_land.json`, and `ne.json`. The frontend embeds the tile templates and zoom bounds advertised
by those documents so browser startup does not depend on cross-origin access to the TileJSON
documents. The style must retain OpenHistoricalMap and Natural Earth attribution.

Every rendered OHM layer is filtered for the selected no-year-zero Palimpsest year. A feature
is visible when `start_decdate` is absent or no later than the selected year and `end_decdate` is
absent or no earlier than it. Filters update without replacing the source when the year changes.
Labels prefer `name` and use `name_en` only when `name` is absent. Low zoom is reserved for major
historical administrative entities and regions; regional places, settlements, routes, physical
features, buildings and local features enter progressively with zoom.

The live vector-tile contract exposes OHM element IDs and temporal/name fields, but it is not a
complete archival or per-element licence record. A future curated adapter must recover the full
element metadata and preserve element type and ID, source and source reference, licence,
copyright, attribution, changeset and retrieval date.

OHM detail and label features are selectable. Their reading surface must say that they are live
contributor context, show the vector source layer, element ID and whatever date/source/licence tags
the tile actually supplies, and disclose missing per-element provenance. An OHM click must never be
sent through the Palimpsest feature-content join or presented with canonical confidence grades.

## Search and reading

`integrations/index.json` declares the immutable authority-match artifact and its expected record
count. The client verifies both files against the release manifest and accepts only
`review_status=accepted` records whose relation is `exact_match` or `close_match` and whose rights
scope is metadata. Proposed candidates, rejected candidates, and unlicensed links never reach the
reader.

When a reviewed record is selected, match `subject_id` against its feature ID, entity ID,
Wikidata ID, primary entity, and linked entities. Display resulting links in the record drawer
under **Authority connections**, after structured facts and before the primary reading. Each entry
links to the direct authority record and shows the authority namespace and ID, reviewed relation,
attribution, and licence. The explanatory copy must state that these links identify related
records and do not replace the release's dates or geometry. The browser pilot contains an accepted
synthetic link so this complete release-to-reader join remains covered by an end-to-end test.

`search.ndjson` remains the compatible bulk entity export with names, dated `name_attestations`,
year range, representative point, non-exclusive themes, related feature IDs, dossier IDs and a
content shard. Each compact name attestation identifies its feature, language/script, kind,
validity, confidence, temporal basis and source IDs. It is not eagerly fetched by schema 1.9
clients. `entities.ndjson` and `dossiers.ndjson` likewise remain optional bulk exports.

Every schema 1.9 release declares `search_index_path`. `search/index.json` describes only paths
already declared and checksummed in the build manifest:

- gzip-compressed two-character Unicode-normalized n-gram shards for substring name lookup;
- gzip-compressed bounded time-band shards for the current map year;
- SHA-256-prefix exact entity-record and feature-to-entity shards;
- gzip-compressed stable browse pages.

The client verifies each compressed artifact's byte length and SHA-256 before decompressing it.
Search may match names from any period, but the displayed result name must be the attestation active
in the selected year. A missing search result is never evidence of historical absence. The map
must not prefetch every n-gram, time band, exact-record shard, page, or the legacy bulk export.

Every schema 1.2 release declares `content_index_path`. The index fixes the sharding algorithm to
SHA-256 over UTF-8 identifiers with the first two hexadecimal characters as `{shard}`. It lists the
available shards and these path templates:

- `content/links/{shard}.json`, keyed by exact `feature_id`;
- `content/entities/{shard}.json`, keyed by namespaced `entity_id`;
- `content/dossiers/{shard}.json`, keyed by `dossier_id`;
- `content/restatements/{shard}.json`, keyed by the `dossier_id` each entry restates.

On map selection, use the tile's `content_shard` to fetch one feature-link shard. Do not scan a bulk
NDJSON collection. A link has this public shape:

```json
{
  "feature_id": "source:stable-feature-id",
  "primary_entity_id": "wikidata:Q123",
  "entity_ids": ["wikidata:Q123"],
  "available_entity_ids": ["wikidata:Q123"],
  "missing_entity_ids": [],
  "dossier_ids": ["wikipedia:en:456"],
  "related_entity_ids": ["wikidata:Q789"]
}
```

`feature_id` must match PMTiles exactly. `available_entity_ids` and `missing_entity_ids` are disjoint
and together equal `entity_ids`, so absent enrichment cannot masquerade as a broken join. Hash each
available entity/dossier ID to fetch only the additional shards needed. Dossiers use canonical page
IDs namespaced by project and language, preserve requested/redirected titles, and carry revision,
timestamp, URL, extract checksum, licence and attribution. Never join by title.

The `restatements` collection is optional and absent from releases built before the tier existed;
a reader must treat a missing collection as "show the source extract", never as an error. A
restatement is keyed by the dossier it restates, so it needs no additional shard lookup beyond the
dossier shard a reader already fetched. It carries `content_role: source_restatement`,
`dossier_kind: restatement`, a `headline`, `text`, an ordered `timeline`, the source revision it is
bound to, and the closed-world validation report.

A restatement is Palimpsest wording, not the source's. The reader must label it as such, name
the generating model, and keep the original extract reachable in the same panel. It may never be
presented as a quotation, and its licence is not the source's licence. Restated prose is generated
once per source revision and is deliberately year-agnostic; year-awareness comes from anchoring the
`timeline` against the selected year in the client, not from refetching prose. A restatement whose
`source_content_checksum_sha256` does not match its published dossier must be ignored.

The frontend verifies the SHA-256 and byte length declared in the manifest for the content index,
each fetched search shard, quality and every fetched content shard. PMTiles are range-read and are protected by the
checksummed immutable manifest/object identity rather than downloaded in full for browser hashing.

## Map-linked Wiki context

Every schema 1.5-or-newer release declares `wiki_context_index_path`. `context/index.json` uses the same
SHA-256 UTF-8 two-character sharding contract and declares
`context/features/{shard}.json`. On selection, hash the exact `feature_id`, fetch that single shard,
filter its already-ranked items for the selected year using the declared temporal margin, then fetch
only the referenced content entity/dossier shards. Predecessor and successor links remain visible
outside the margin as explicitly labelled continuity links; unknown dates remain unknown.

The reading panel groups bounded results as people, events, institutions, polities, places, themes
or other. It must label the relationship and evidence strength, distinguish a saved Wikipedia
introduction from Wikidata metadata, and state that a relation is not causation. Ranking scores are
retrieval mechanics and must not be presented as historical significance. No visitor-time Wikimedia
request is permitted.

## Regional and temporal discovery

Every schema 1.7-or-newer release declares `region_time_index_path`. The index specifies a
10-degree global grid, time bands, a result cap and `region-time/buckets/{shard}.json`. For a map
selection, calculate the cell from the actual click longitude/latitude, select the band containing
the chosen year, hash `<band_id>|<cell_id>`, and fetch one immutable shard. Filter every returned
entry again against the exact selected year; bands are partitions, not date claims.

Feature entries mean that their reviewed geometry intersects the cell. Standalone entity entries
mean only that Wikidata supplied a coordinate and a usable date. The interface must call the result
“in this area,” disclose the grid size, and must not label the cell as a historical region or infer
influence, residence or causation. Undated standalone entities are absent by contract.

## Place-linked chronology

Every schema 1.4 release declares `chronology_index_path`. PeriodO and later chronology sources are
kept separate from dossiers and map geometry because a named period is an attributed scholarly
definition, not a universal date label. The index declares:

- `chronology/entities/{shard}.json`, mapping an authority entity ID to period IDs;
- `chronology/definitions/{shard}.json`, containing the cited definitions;
- `chronology/time/band-XX.json`, listing definitions intersecting a bounded release time band.

On selection, intersect the selected feature's `entity_ids` with the time band containing the
selected year, then fetch only the resulting definition shards. The frontend implements this
lazily and shows overlapping definitions together. It must preserve authority citation, source
URL, original start/stop labels and spatial scope; it must not rename the selected year as if one
periodization were globally authoritative.

Schema 1.4 also declares `source_registry_path` and `coverage_priorities_path`. The source registry
distinguishes evidentiary roles and commercial-redistribution status. Coverage priorities are a
curation report for observed 30-degree cells only and must never be interpreted as proof that an
unlisted location lacks history.

## Interpretive pathways

Every schema 1.3 release declares `causal_index_path`, even when it contains no claims. Its three
SHA-256-prefix collections are:

- `causal/entities/{shard}.json`: incoming/outgoing claim IDs and path IDs by entity;
- `causal/claims/{shard}.json`: source-backed causal claims;
- `causal/paths/{shard}.json`: ordered, curated interpretive pathways.

After resolving a selected feature's `entity_ids`, fetch only their entity-adjacency shards, then
only the named claim and path shards. The current frontend does this lazily and labels the result
“Interpretive pathways.” It must show the mechanism, perspective, confidence, authorship, review
and sources. It must not call the material a definitive causal chain.

Indicator observations remain attached to `original_geographic_unit`. Only render one against a
map geometry when `spatial_mapping_valid` is true; otherwise use charts or a clearly labelled
context panel.

## Year pages

A release may carry one dossier per year. It is optional: a release without any is complete, not
degraded, and the interface must work when `years/index.json` is absent.

- `years/index.json`: every year the release carries, in chronological order. One fetch, small
  enough to hold. Fetch it before offering a year anywhere in the interface;
- `years/{year}.json`: the page for one year, addressed by the year itself. The key is a small
  integer the reader already has, because it came from the time slider, so there is no shard
  lookup and no second index.

### Assembled and generated are different things and must look different

Most of a year page was never written by anything. These parts are the sources' own words,
rearranged, and carry no generated claim:

`lede` and `headlines`, `register_entries`, `works`, `related_years`, `incumbents`, `conflicts`,
`overview.months`, and every `anchors[].records` list and `anchors[].quote`.

These parts are machine-written prose: `overview.prose`, `anchors[].prose`, `sections[].prose`,
and every `gloss` on a register entry or a work.

The disclosure applies to the second set and must not be applied to the first. `lede_kind` is
`assembled` precisely so a reader's warning can be accurate rather than uniform: a sentence
nobody generated should not carry the same warning as one somebody did. The disclosure wording is
fixed:

> This dossier was written by a machine and has not been read by a person. Every name and date in
> the prose appears in the records it was written from — checked, not trusted. The connections are
> ours.

### Links are offsets, not text

Every `links` and `gloss_links` array holds character offsets into its sibling prose string, with
the exact substring in `text`. Slice at the offsets. Do not re-tokenise, re-match by string, or
re-flow the prose before slicing: the offsets were verified against that exact string at build
time and any transformation invalidates them. `text` must equal the slice; if it does not, render
the prose unlinked rather than guessing.

### Doors must not lead nowhere

`related_years` is every other year this one names, parsed from the records. A year in that list
is only reachable if it also appears in `years/index.json`. Cross-reference the two and render an
unavailable year as plain text, not as a link. Do not fetch a year page to discover whether it
exists.

### Pictures carry their licence with them

Every image carries `attribution`, `license_id` and `descriptor_url`. Render the attribution
visibly and link the descriptor. Cropping the credit out of the layout is not a styling decision;
a file is redistributable on the terms attached to it and on no others.

### What the browser may not do

Nothing on a year page is generated at request time, and no part of this contract may be
satisfied by asking a model. `removed_sentences` records prose the evidence check could not
support, deleted before publication; it is inspectable and needs no reader-facing treatment.

## Accessibility and performance budget

Timeline state must be keyboard operable and encoded in the URL, and its supported bounds must
match the manifest. Provide a list/text route to every map-selected item. Load one era archive
at a time, delay content shards until selection, parse bulk NDJSON as a stream or worker task, and
never ship GeoParquet to the ordinary map view.
