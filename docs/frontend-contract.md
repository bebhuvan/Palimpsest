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
4. the release's reviewed History Joice PMTiles reconstruction;
5. OpenHistoricalMap historical labels.

OpenHistoricalMap is context, not a source in the immutable History Joice release. Its geometry
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

Every rendered OHM layer is filtered for the selected no-year-zero History Joice year. A feature
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
sent through the History Joice feature-content join or presented with canonical confidence grades.

## Search and reading

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
- `content/dossiers/{shard}.json`, keyed by `dossier_id`.

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

## Accessibility and performance budget

Timeline state must be keyboard operable and encoded in the URL, and its supported bounds must
match the manifest. Provide a list/text route to every map-selected item. Load one era archive
at a time, delay content shards until selection, parse bulk NDJSON as a stream or worker task, and
never ship GeoParquet to the ordinary map view.
