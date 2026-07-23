# Source integration and distribution profiles

## Distribution profiles

`config/pipeline.yml` is the distributable `open_core` profile. Its enabled sources must:

- be assigned `distribution_tier: open_core`;
- have a completed dataset/downstream licence review;
- be commercially redistributable (`allowed` or documented `conditional`);
- use a licence in the commercial policy allowlist.

`config/research-overlay.yml` inherits that effective configuration and changes the policy to
`research`/`noncommercial`. It may enable `research_only` sources whose reviewed licences are in
its broader allowlist. This is a distinct artifact profile, not a way to relabel non-commercial
material as open core. Both the base and inherited values participate in the build fingerprint.

## Implemented integrations

### WHG/Getty-style authority reconciliation snapshots

The `authority_reconciliation` adapter is implemented. It accepts a bounded, checksummed JSON
snapshot containing:

- the upstream source version and explicit `0-100` score scale;
- metadata licence and exact required attribution;
- internal subject/query IDs;
- provider authority ID, namespace, label and score;
- an explicit editorial status (`proposed`, `accepted`, or `rejected`);
- an explicit relation for accepted matches.

It emits `integrations/authority-matches.ndjson`. Every match carries its upstream record ID,
source version, retrieval time, payload checksum, licence, attribution, confidence rationale and
normalization lineage. Provider scores remain candidates; they never silently rewrite entity IDs.
Allowed authority namespaces are configured per source.

This contract can preserve responses from the official [WHG Reconciliation
API](https://docs.whgazetteer.org/content/technical/apis.html) and [Getty Vocabularies OpenRefine
service](https://www.getty.edu/research/tools/vocabularies/obtain/openrefine.html). Getty publishes
its vocabularies under [ODC-By 1.0 with specific attribution
guidance](https://www.getty.edu/research/tools/vocabularies/obtain/), so a bounded Getty snapshot
can qualify for open core after version/checksum review. WHG says to respect each dataset's licence;
the WHG platform documentation is CC BY-NC 4.0. Platform-derived snapshots are therefore
research-only unless a selected underlying dataset carries separately reviewed open terms.

No WHG or Getty dataset/response snapshot is enabled yet. Selecting the first bounded input,
recording its immutable checksum, and reviewing contributor/source attribution remain publication
decisions.

### Allmaps-compatible IIIF historical-map metadata

The `iiif_maps` adapter is implemented for [IIIF Presentation
3](https://iiif.io/api/presentation/3.0/) Manifests and [IIIF Georeference
Annotations](https://iiif.io/api/extension/georef/). It fetches a pinned manifest and annotation at
build time, validates their IDs and canvas relationship, and requires at least three valid ground
control points. It emits `integrations/historical-maps.ndjson` with:

- Manifest, Canvas and Annotation identifiers;
- provider, depicted date and required attribution statement;
- source versions, retrieval dates, checksums and transformation lineage;
- a conservative georeference-confidence rationale;
- separate metadata, image/pixel and georeference-annotation rights.

The adapter never downloads image pixels. A Manifest without a recognized explicit image rights
URI is rejected, as is an image licence outside both the source media allowlist and active profile.
Georeference rights are independently reviewed because the IIIF extension does not make the image
licence apply to an annotation.

No institution/map is enabled yet. Selecting a historically useful map, reviewing its manifest
metadata licence, image rights and georeference contributor terms, and pinning both checksums
remain publication decisions. Allmaps rendering and any visual map layer remain proposed; this
change does not redesign or modify the visitor UI.

## Schema 1.10 compatibility

These integrations are additive. The schema 1.10 manifest is unchanged; the new files appear in
its existing generic `artifacts` list. `integrations/index.json` describes the two NDJSON
collections. Existing 1.10 clients can ignore them, and the browser has no live dependency on WHG,
Getty, Allmaps or a IIIF image service.

The integration contracts have their own `1.0.0` schemas:

- `AuthorityMatch.schema.json`
- `HistoricalMapMetadata.schema.json`
- `IntegrationIndex.schema.json`

## Deferred sources and decisions

Only reconciliation and IIIF map metadata were implemented in this iteration. OpenHistoricalMap,
Syriaca, ORACC, DHARMA, Nomisma, museum-object/media feeds and OpenAlex remain proposals or
existing disabled adapters as identified in the source roadmap. World History Encyclopedia is
explicitly excluded from bulk ingestion.

Remaining licensing decisions are:

- choose the first bounded Getty vocabulary/reconciliation snapshot and preserve Getty plus
  contributor/source attribution;
- choose whether any WHG dataset has rights suitable for open core, otherwise keep it research-only;
- choose one IIIF historical map whose metadata, pixels and georeference annotation are all
  independently redistributable under the intended profile;
- define downstream packaging for share-alike database/media sources before enabling any new one.
