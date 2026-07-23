# Entity, event, assertion and layer architecture

Status: accepted for schema 1.10  
Migration scope: additive; existing 1.x releases remain readable

## Decisions

### Identity is separate from map geometry

`HistoricalEntity` is the stable identity record. Its normalized `entity_kind` is one of:
`person`, `event`, `institution`, `work`, `artifact`, `route`, `place`, `polity`,
`concept`, or `other`.

The existing `entity_type` field remains as the source-specific type string. It is not removed or
rewritten because downstream users may rely on values such as `human`, `historical_country`, or a
Wikidata QID. When an older record has no `entity_kind`, the model derives a conservative kind
from known legacy values and otherwise uses `other`.

`HistoricalFeature` remains the spatial claim. An event, route, institution, work, or artifact
appears on the map only when a source supports a geometry and interval for a separate feature
linked through `entity_ids`. An entity does not acquire a point merely because a modern authority
record has a coordinate.

### Events and routes have two representations when mapped

An event entity describes the event's identity and evidence. An event feature describes the
source-backed place and time at which the release can render it. A route entity identifies the
route; one or more route features may retain different dated paths, source reconstructions, or
perspectives. The pipeline never collapses these into a timeless line.

Works and artifacts are distinct. A `work` is an intellectual or creative work; an `artifact` is
a physical object or surviving copy. Institutions are organizations rather than the buildings
they occupy. These distinctions prevent a book, one copy of that book, its printer, and the place
of printing from becoming one overloaded map record.

### Facts are structured assertions, not generated prose

`EvidenceAssertion` records one structured subject–predicate–object statement. The object is
either another entity, a text value, or a historical year. Every assertion has:

- one or more subject entity IDs and optional supporting feature IDs;
- a controlled, machine-readable predicate;
- a typed object;
- a no-year-zero validity interval and date precision;
- optional temporal uncertainty;
- a confidence rationale, review status, evidence basis, and source references.

The constant representation value `structured_sourced_assertion` prevents assertion text from
being confused with a generated narrative. Human-readable sentences are assembled in the client
from the predicate and entity labels. Wikipedia extracts and authored narrative remain
`HistoricalDossier` records with an explicit content role; they are never evidence assertions.

The evidence index is sharded independently from thematic and causal claims:

```text
assertions/index.json
assertions/records/{shard}.json
assertions/entities/{shard}.json
assertions/features/{shard}.json
```

Thematic assertions answer “why is this feature in this discovery lens?” Causal claims represent
attributed historiographical arguments. Evidence assertions record bounded facts or source
statements. One class cannot substitute for another.

### Map sources, lenses, and overlays are orthogonal

`layers/index.json` declares four layer roles:

| Role | Changes | Does not change |
| --- | --- | --- |
| `map_source` | which source geometry is visible | thematic classification or confidence |
| `thematic_lens` | which sourced records are foregrounded | source geometry or provenance |
| `confidence_overlay` | styling by one declared confidence axis | review status or source identity |
| `provenance_overlay` | styling by source identity/licence | confidence or historical meaning |

The layer catalog is descriptive release metadata, not a MapLibre style. The client may render
controls from a stable local vocabulary while using the catalog to verify semantics. Combining a
Knowledge lens with a provenance overlay therefore means “foreground Knowledge-classified
records, then expose their sources”; it does not create a new synthetic historical layer.

## Schema 1.9 to 1.10 migration

1. Continue accepting 1.9 `HistoricalEntity` records. Derive `entity_kind` without changing
   `entity_type`.
2. Add optional entity chronology metadata (`date_precision`, `temporal_uncertainty`,
   `temporal_confidence`, and `review_status`). Older records retain null/default values.
3. Add `assertion_index_path` and `layer_catalog_path` to the build manifest. Consumers must gate
   these paths on schema version 1.10 and must not guess them for older releases.
4. Add assertion and layer artifacts to content-addressed builds. Verification checks shard
   placement, counts, and every feature/entity join.
5. Add `source_id` and `license_id` tile properties as display shortcuts. Full source records
   remain authoritative in the manifest/content artifacts.
6. Keep `themes/index.json`, `content/index.json`, PMTiles source-layer names, and all earlier
   paths unchanged.

No published build is edited in place. Rebuilding curated data creates a new immutable build ID,
and `latest.json` advances only after the new manifest and artifacts verify.

## Initial bounded slice

The first curated slice is the publication of Nicolaus Copernicus's *De revolutionibus orbium
coelestium* in Nuremberg in 1543. It intentionally contains only:

- Copernicus as a person;
- the publication as an event;
- Johannes Petreius's printing workshop as an institution;
- *De revolutionibus* as a work;
- one event-location feature;
- structured authorship, publication-place, printing, and subject assertions.

The map point means “the evidenced publication event occurred in Nuremberg”; it does not mean
Copernicus was personally present there. The year is annual precision, not an invented day. The
slice is a contract test and a useful Knowledge-lens record, not the start of global ingestion.
