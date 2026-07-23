# Canonical data contract

## Chronology

- Negative integers are BCE and positive integers are CE.
- There is no year zero. Adapters for astronomical/ISO chronologies must perform and document an
  explicit conversion.
- `valid_from` and `valid_to` describe the interval asserted by the source. They do not authorize
  interpolation between different geometries.
- `date_precision` distinguishes exact, annual, decadal, century, range, and unknown dates.
- `temporal_uncertainty` can retain separate earliest/latest start and end bounds, a `circa`
  marker, and a rationale. The bounds are an evidence envelope, not values to average;
  `valid_from`/`valid_to` remain the documented rendering interval.

Names are dated evidence, not timeless identity keys. Every canonical feature carries
`name_attestations`; each attestation has its own stable ID, text, language, optional ISO 15924
script, name kind, validity interval, precision, confidence, perspective and source references.
An adapter that supplies only the legacy `names` dictionary receives explicit
`temporal_basis: feature_interval` attestations. That basis means only that the label was inherited
from the source feature interval—it must not be described as an independently dated name.

Named periods are separate `HistoricalPeriodDefinition` records. Each retains its authority,
localized labels, original start/stop labels, normalized no-year-zero interval, spatial coverage,
bibliographic citation, relations, notes and checksummed source reference. Multiple definitions
may overlap for the same place and year; the pipeline does not select or average a winner.

## Spatial meaning

A polygon is not assumed to be a modern state. Every feature declares whether it represents a
legal boundary, reconstructed control, a claim, occupation, tributary relationship, cultural
region, influence zone, point location, route, or unknown extent.

The UI must use this field when styling a feature. Cultural regions and influence zones must not be
rendered with the same hard edge as surveyed boundaries.

The vocabulary also supports mobile groups, social groups and cultural networks, with mobility
ranges, seasonal use and network spatial meanings. Points, lines and multi-geometries are first-
class representations. A territorial claim should name its `perspective`. Spatial uncertainty can
record a source geometry, accuracy radius, bounding extent, multiple reconstruction method, or an
unknown method with a rationale.

Alternate reconstructions remain separate features joined by `dispute_group`; each keeps its own
geometry, chronology, perspective, confidence and sources. Overlapping claims are valid data, not a
topology error to dissolve.

## Thematic discovery

`themes` is a non-exclusive, derived list used to foreground records through the `power`, `belief`,
`knowledge`, `culture`, and `trade` visitor lenses. It is not a replacement for `kind` or
`spatial_meaning`. The authoritative classification is a `ThematicAssertion` emitted by the
versioned rule set. Rules use exact structured values and never words in a name, dossier or
description. See [the thematic classification contract](thematic-classification.md).

A feature can carry several themes and no theme is required. An empty list means that the release
has not classified the feature thematically; it does not mean the feature lacks cultural,
religious, political, technical, or economic significance.

## Confidence and review

Temporal, spatial, and interpretive confidence are independent A–D/unknown values with rationales.
They are categorical editorial assessments, not probability or accuracy percentages.

- A: contemporary legal/survey evidence or equivalent precision;
- B: specialist scholarly GIS or peer-reviewed reconstruction;
- C: general atlas or approximate scholarly reconstruction;
- D: approximate location/influence only;
- unknown: insufficient evidence to assign a grade.

Review status is separate: unreviewed, provisional, verified, contested, or rejected. A feature can
be carefully reviewed and still remain low-confidence because the historical evidence is limited.

## Provenance

Every feature contains at least one `SourceReference` with a stable record identifier, publisher,
URL, licence, citation, retrieval timestamp, and snapshot checksum where available. Raw downloads
are immutable inputs; derived files may be replaced only by creating a new build ID.

Build IDs are derived from configuration and checksummed inputs and outputs. Tile generation must
use a content-derived stable work path: Tippecanoe embeds its generator arguments in PMTiles
metadata, so a random temporary input or output path would make otherwise identical archives—and
therefore release IDs—differ. Two builds from the same snapshots and configuration must either
produce the same ID or fail verification.

## Public artifact loading

Consumers first request `v1/latest.json`, then its named manifest. All other paths in the manifest
are immutable and may be cached for one year. Consumers must verify schema major compatibility and
must never guess unpublished paths.

PMTiles are generated only through the configured maximum zoom (currently 7). Each era archive has
a `history` geometry layer and a separate `history_labels` representative-point layer. A place can
therefore change its displayed name without replacing or interpolating its geometry. MapLibre may overzoom
those vector tiles for closer views; this is deliberate because the global source geometries do not
justify street-scale apparent precision. Local high-confidence sources can later be published as a
separate higher-zoom layer.

`quality.json` publishes accepted, scoped, deduplicated, and rejected counts plus aggregate reason
and validation-code counts. Rejected source records remain in the private staged audit log; the
public report is sufficient to expose gaps without republishing sensitive or malformed payloads.

Schema 1.4 adds `chronology/index.json`, `source-registry.json`, and
`coverage-priorities.json`. The chronology index uses the same two-character SHA-256 prefix
contract as content. It has definition shards, entity-to-period shards, and bounded time-band ID
lists. Coverage priorities cover only cells with at least one observed feature; their explicit
warning prevents unobserved ocean/land cells from becoming a fabricated coverage score.

Schema 1.5 adds `context/index.json` and feature context shards. These are a bounded discovery
projection from explicit Wikidata statements, not a general knowledge-graph crawl and not a causal
graph. All referenced feature/entity/dossier IDs are verified against the content index.

Schema 1.7 adds `region-time/index.json`. It partitions reviewed feature intersections and dated,
coordinate-bearing enriched entities into a declared 10-degree discovery grid and bounded time
bands. Grid cells are retrieval partitions, never historical regions. Feature entries retain their
exact source interval; standalone entities without dates are excluded rather than projected across
all history. Entity, feature and dossier joins are release-verified.

Schema 1.8 adds `themes/index.json`, with assertion shards and feature-to-assertion adjacency
shards. Every assertion retains its rule, matched structured values, dates, confidence, review
state, rationale and source references. Release verification checks shard placement and both sides
of the feature/assertion join.

Schema 1.9 adds `search/index.json`. It retains `search.ndjson` as a bulk compatibility export while
publishing immutable gzip-compressed name n-gram, time-band and browse-page shards plus exact
SHA-256-prefix entity and feature lookup shards. Release verification checks page coverage, exact
joins, band intersections, n-gram coverage, artifact identity and deterministic ordering. This
changes delivery granularity only; it does not alter historical records, name evidence, dates,
themes, provenance or licences.

Schema 1.10 adds `assertions/index.json` and `layers/index.json`. Evidence assertions are
structured subject–predicate–object facts with typed objects, bounded chronology, confidence,
review state and source references. Their constant representation explicitly separates them from
generated or tertiary prose. Entity and feature adjacency shards are release-verified against the
content index. The layer catalog declares map sources, thematic lenses, confidence overlays and
provenance overlays as orthogonal roles; selecting one role must not silently change another.
See [the entity, event, assertion and layer architecture](entity-event-layer-architecture.md).

Schema 1.10 builds may also contain the additive, build-time-only `integrations/index.json`,
`integrations/authority-matches.ndjson`, and `integrations/historical-maps.ndjson` artifacts.
Older 1.10 consumers may ignore them. They are listed in the existing manifest `artifacts` array;
no manifest field or browser requirement was added.

Authority matches retain the internal subject, authority record ID and namespace, provider score,
confidence rationale, explicit editorial status, source version, retrieval date, checksum,
licence, attribution and normalization lineage. A proposed match is not an identity assertion.

Historical-map metadata retains the IIIF Manifest, Canvas and georeference Annotation identifiers,
depicted date, provider and required attribution. Metadata, image and georeference rights are
separate fields. The artifact contains no image pixels and is not a browser-side proxy for a IIIF
service.

## Stable identity and content roles

Every admitted feature has one or more namespaced `entity_ids`. A reconciled Wikidata entity uses
`wikidata:Q…`; an unreconciled record uses `feature:<feature_id>`. Display names are never identity
keys. Wikipedia and Wikidata redirects remain aliases of the canonical page or entity ID.

`HistoricalEntity.entity_kind` supplies a stable product-level class for people, events,
institutions, works, artifacts, routes, places, polities and concepts. The legacy `entity_type`
remains the unmodified source vocabulary. A mapped event or route has a separate
`HistoricalFeature` for each evidenced spatial-temporal claim; entity identity never manufactures
geometry.

Reading records declare a content role. Wikipedia and other encyclopedias are
`tertiary_summary`; Wikisource or transcribed archival documents are `primary_source`; authored
History Joice analysis is `project_interpretation`. The pipeline and interface must not present one
role as another. Commons file names are media references on an entity and are not publishable images
until the individual file licence, attribution and revision metadata have been ingested.

`HistoricalDossier.dossier_kind: source_extract` makes existing revision-pinned Wikipedia and
other source dossiers structurally distinct from a
`PublishedEditorialDossier.dossier_kind: generated_editorial`. Generated editorial dossiers are
created only by the separate build-time, human-reviewed workflow; their evidence sources support
the cited claims but do not license the generated prose. See
[the editorial dossier pipeline](editorial-dossier-pipeline.md).

## Causal and historiographical claims

Factual entity relationships and historical causal arguments are different datasets. Wikidata may
assert that a person participated in an event; it cannot establish that one event caused another.
A `CausalClaim` is therefore a human-authored, attributed interpretation with separate cause and
effect periods, a named mechanism, perspective, confidence rationale, review status and reviewed
scholarly sources.

The strong relationship `caused` requires independent verification and two distinct sources.
Claims spanning more than a century require an explicit synthesis flag and at least two connected
intermediate claims. Curated paths must be ordered and entity-connected. Competing claims remain
separate through `counterclaim_ids`; the build never averages them into consensus.

Wikidata statement IDs, qualifiers and references are retained on selected date and relationship
claims. Their presence strengthens provenance but does not make a community-authored claim a
reviewed History Joice interpretation.
