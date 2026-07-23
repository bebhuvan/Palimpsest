# Historical source roadmap

No open dataset supplies accurate, globally complete boundaries from the first cities to the
present. V1 therefore treats coverage and uncertainty as data rather than hiding them.

## In the open-core release profile

- [**Cliopatria v0.2.0**](https://github.com/Seshat-Global-History-Databank/cliopatria/releases/tag/v0.2.0) provides provisional worldwide polity reconstructions from 3400 BCE to
  2024 CE. It gives the map breadth, but its own maintainers describe the polygons as one version of
  contested historical territory. It is pinned to a numbered release and assigned C-grade defaults.
- [**Pleiades v4.1**](https://github.com/isawnyu/pleiades.datasets/releases/tag/v4.1)
  supplies 41,480 ancient place records from its numbered source archive. The adapter reads only
  recognized place JSON and Pleiades' own time-period vocabulary without extracting the TAR. A
  reviewed SHA-256 is enforced; points remain locations rather than borders. Disconnected
  attestation intervals become separate features instead of one false continuous occupation.
- [**PeriodO dataset-version-299**](https://perio.do/) supplies attributed scholarly period
  definitions. Its mutable canonical export is fail-closed against a reviewed SHA-256. Overlapping
  definitions are published as alternatives and linked to map entities where PeriodO supplies an
  authority identifier such as Wikidata.
- **Wikidata** supplies entity identifiers, labels, and descriptions for records already admitted by
  a geometry source. It does not establish borders.
- **Wikipedia** supplies revision-pinned introductory extracts for build-time dossiers. It does not
  establish borders, chronology, or confidence.
- **Our World in Data** supplies the configured long-run population series. Observations retain the
  publisher's geographic unit and are never silently projected onto reconstructed polities.
- **Library of Congress** catalog records supply bounded primary-source and bibliographic anchors.
  The configured records are public domain, checksum-pinned snapshots; their catalog descriptions
  remain separate from the historical documents they describe.
- **Japan Ministry of Land, Infrastructure, Transport and Tourism** multilingual cultural-site
  pages supply a reviewed Public Data License 1.0 discovery source. The Tanegashima pilot preserves
  its dependence on the much later *Teppoki* tradition instead of presenting that account as a
  contemporaneous transcript.

## Implemented but disabled by default

- **Open Context** supplies curated archaeological records. Each query requires a project-level
  rights and sensitivity review. Human-remains-related records are excluded and public coordinates
  are generalized by default.
- **Reviewed GeoJSON** accepts an editorial export from GeoLibre, QGIS, or another source only when
  its field mapping, semantics, confidence, licence, and immutable URL are explicit.
- **Linked Places Format** has a strict adapter for selected WHG/Pelagios-compatible exports. It
  requires an explicit chronology, a bounded timespan, and a single geometry attestation per row;
  ambiguous multi-geometry records must be split during review.
- **WHG/Getty authority reconciliation** has a checksummed snapshot adapter. It emits reviewable
  candidates with explicit rights, scores, decisions and transformation lineage. No live
  reconciliation endpoint or unreviewed match is published, and no WHG or Getty snapshot is
  currently selected in configuration.
- **IIIF/Allmaps historical-map metadata** has a Presentation 3/Georeference Extension adapter.
  It downloads only manifests and annotations during the build, requires separate metadata,
  georeference and per-image rights, and emits no image bytes. No institution/map pilot is
  currently selected.

## Candidate-source decision register

An adapter is not approval. This register records the current decision and the evidence that must
be revisited immediately before a source is enabled.

| Source | Scope and role | Licence / commercial redistribution | Versioning and access | Known limitations | Decision |
| --- | --- | --- | --- | --- | --- |
| [Library of Congress](https://www.loc.gov/free-to-use/) | Primary-source catalog records, digitized historical materials and bibliographic anchors; not a global event or boundary dataset. | Rights are item/collection-specific. The two configured 1543 records state public-domain/no-known-restrictions status and retain the requested credit. | Public JSON item endpoint; pin the exact response timestamp and SHA-256 because catalog records can be corrected. | Catalog descriptions are institutional metadata and may summarize, omit or revise interpretation. Image/file rights still require their own review. | Two bounded 1543 records enabled. Add records only after an item-level rights and scope review. |
| [Japan MLIT multilingual database](https://www.mlit.go.jp/tagengo-db/) | Official multilingual introductions to cultural and natural sites; useful for discovery and received historical traditions, not comprehensive scholarship. | Unless otherwise marked, MLIT website content is available under Public Data License 1.0 with attribution and disclosure of modifications. | Stable numbered page plus checksummed HTML snapshot; no numbered dataset release is advertised. | Concise tertiary interpretation. The Tanegashima account depends on a chronicle completed more than sixty years after 1543 and requires scholarly reconciliation. | One bounded Tanegashima record enabled as provisional tertiary evidence, with source distance explicit. |
| [Pleiades](https://pleiades.stoa.org/downloads) | Scholarly ancient places, names, locations and connections, strongest around the Mediterranean and Near East; not polity borders. | CC BY 3.0; commercial redistribution is allowed with attribution. | Numbered v4.1 source archive, expected SHA-256 and safe internal-path allowlist. | Representative points may be derived centroids; some places deliberately have no location; dates describe attestations rather than continuous occupation. | Enabled. Advance only through a reviewed numbered release and checksum change. |
| [OpenHistoricalMap](https://wiki.openstreetmap.org/wiki/OpenHistoricalMap/License) | Global, contributor-built historical features and local detail across periods. | Database is CC0 unless an element says otherwise; commercial reuse is allowed only for the CC0 subset. Preserve and enforce every `license=*` override. | OSM API, bounded Overpass extracts and database dumps; pin an extract checksum plus source changeset IDs. | Coverage, dating, geometry and sourcing are uneven; imports can repeat modern state assumptions. It cannot silently supersede a reviewed scholarly reconstruction. | Build a bounded regional adapter only after per-element licence and provenance tests exist. |
| [Open Context](https://opencontext.org/about/terms) | Archaeological observations and project collections worldwide; evidence and sites, not continuous political extents. | Public-domain and Creative Commons records, often CC BY; commercial reuse depends on each project/record licence. | JSON/GeoJSON API; snapshot each curated query and obey the published limit of at most three requests per second. No stable global release. | Sensitive locations, Indigenous/community interests, human remains, heterogeneous dating and project-specific rights require review and often generalisation or exclusion. | Adapter exists; keep disabled until a named project query passes rights, sensitivity and release review. |
| [World Historical Gazetteer](https://docs.whgazetteer.org/content/technical/apis.html) | Global reconciliation, alternate names, temporal attestations and selected Linked Places datasets; not a boundary authority. | WHG platform material is CC BY-NC 4.0 and contributed datasets retain dataset-specific terms. Commercial redistribution is allowed only for a specifically reviewed dataset whose own rights permit it. | Token required for most Entity/LPF API endpoints; pin a selected dataset export or response snapshot and checksum rather than the changing union index. | Reconciliation links are hypotheses; geometry and rights are dataset-specific. | Snapshot reconciliation and Linked Places adapters are implemented. No WHG dataset is selected; platform-derived output belongs only in the research profile unless a dataset-specific open licence is proved. |
| [China Historical GIS](https://chgis.fairbank.fas.harvard.edu/data/chgis/v4/) | Chinese administrative units and places, principally 222 BCE–1911 CE; valuable for correcting geographic imbalance. | Academic research only; no commercial use, resale or redistribution. | Versioned downloads (latest advertised version 6, 2016); GIS/database files. | Licence is incompatible with the public artifact contract; administrative geography does not represent all communities or territorial realities. | Research and QA reference only. Do not ingest or redistribute without new permission. |
| [al-Ṯurayyā](https://althurayya.github.io/) | More than 2,000 Arabic toponyms and route sections for the ninth–tenth-century Islamicate world; explicitly models regions through place/route networks rather than borderlines. | Repository says data are open but also says licence information still needs to be added. Commercial redistribution is therefore not established. | GitHub-hosted GeoJSON/JSON with no numbered releases. | Work in progress, fuzzy text matches, source ambiguity and no durable release or explicit data licence. | High-value model and future source; blocked on licence, release pinning and match review. |
| [PeriodO](https://perio.do/license/) | Global scholarly definitions of historical periods; vocabulary and chronology only, never geometry. | PeriodO declares the data public domain; commercial redistribution is allowed. | Canonical JSON-LD export; dataset-version-299 plus exact SHA-256 is reviewed and snapshotted. | Definitions overlap, may be unbounded, and encode scholarly/regional perspectives. | Enabled as a separate chronology artifact; 789 unbounded/invalid definitions in the reviewed snapshot are rejected rather than guessed. |
| [Getty AAT/TGN/ULAN](https://www.getty.edu/research/tools/vocabularies/obtain/) | Multilingual terminology, places, people and organizations; authority metadata and reconciliation, not historical boundary evidence. | Open Data Commons Attribution 1.0; commercial reuse is allowed with Getty and contributor/source attribution. | Monthly linked-data releases and SPARQL/OpenRefine access; pin a dated release or checksummed response snapshot. Getty retired legacy XML web services in January 2026. | TGN is not a complete historical gazetteer and matches require editorial review. | Reconciliation snapshot adapter is implemented and open-core-compatible. Selecting and pinning the first bounded TGN/AAT/ULAN input remains pending. |
| [Syriaca.org](https://syriaca.org/api-documentation/index.html) | Places, persons, saints, works and events for Syriac studies, with strong Near Eastern coverage. | Project data are CC BY 4.0; commercial reuse is allowed with attribution, subject to cited-source rights. | TEI/XML, JSON/GeoJSON APIs and OAI; snapshot a named collection/export. | Specialist scope, multiple attestations and inherited source restrictions require record-level provenance. | High-priority non-Western specialist pilot; disabled until a stable collection snapshot is selected. |
| [ORACC](https://oracc.museum.upenn.edu/doc/opendata/) | Cuneiform corpora, texts, glossaries and prosopography for ancient Mesopotamia. | Default CC BY-SA 3.0, but projects can override; commercial reuse is conditional on each project's licence and share-alike. | Project JSON downloads and APIs; pin exact project versions/checksums. | Transliteration and text assertions are primary/scholarly records, not geographic facts; licences vary by project. | Build a project-scoped primary-source adapter only after a named corpus review. |
| [DHARMA](https://erc-dharma.github.io/) | Inscriptions, documents and institutions across South and Southeast Asia, especially the first millennium CE. | CC BY 4.0 for reviewed DHARMA corpora; commercial reuse is allowed with attribution. | Versioned Git repositories/TEI editions; pin commit and corpus. | Corpus modules and image rights differ; epigraphic interpretation and uncertain findspots must remain explicit. | High-priority South/Southeast Asian pilot; select one corpus before adapter work. |
| [Nomisma.org](https://nomisma.org/data/) | Numismatic concepts, mints, hoards and type-series links across ancient and medieval worlds. | Nomisma concepts are CC BY 3.0; partner datasets retain their own licences. | Nightly bulk data and Git history; pin commit/export checksum. | Coin circulation supports networks and chronology, not automatic territorial extent. | Candidate gazetteer/network adapter; disabled pending partner-dataset selection. |
| [Metropolitan Museum Collection API](https://metmuseum.github.io/) | CC0 object metadata and public-domain images useful for material-culture dossiers. | CC0 metadata and designated public-domain images permit commercial reuse. | Public API plus dated snapshots maintained by the museum; pin a snapshot. | Collection bias and object dates/places are often ranges or interpretations; not an event feed. | Candidate object/media adapter after per-image designation is retained. |
| [OpenAlex](https://docs.openalex.org/download-all-data/openalex-snapshot) | Bibliographic discovery and citation graph for finding scholarship, not historical claims. | CC0 metadata; commercial redistribution is allowed. | Quarterly full snapshot with manifest; very large, so ingest a bounded scholarly subset. | Metadata can be incomplete and does not license the publications themselves. | Bibliography-only candidate; no full snapshot in V1. |
| [Wikimedia Commons and Wikisource](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use) | Media and primary-source transcriptions linked from entities. | Per-file/page licences vary; commercial reuse cannot be inferred at project level. | MediaWiki APIs with revision IDs and per-file ExtMetadata; use bounded build-time batches. | Must not conflate media, transcribed primary sources, encyclopedia summaries or project interpretation. | Contracts only until per-item licence/attribution and revision pinning tests exist. |

CShapes remains a possible modern-state improvement only after its non-commercial/share-alike
obligations and precedence against Cliopatria have been reviewed. It does not improve ancient or
medieval coverage.

## OHM live display and reproducible ingestion

The visitor map may use OpenHistoricalMap's live vector tiles as a clearly credited historical
context layer. That display does not make OHM part of a content-addressed History Joice release and
does not supersede reviewed Cliopatria geometry.

For reproducible ingestion, `https://planet.openhistoricalmap.org/` publishes dated OSM PBF planet
snapshots and matching state files. An adapter should pin an exact object key, record its byte size
and retrieval time, calculate its own SHA-256 rather than treating a multipart S3 ETag as a file
checksum, then derive bounded thematic or regional extracts. Normalization must retain the OSM/OHM
element type and ID, version, changeset, timestamps, source tags, `license=*`, copyright and
attribution tags before the normal licence gate runs. The global planet is an acquisition input,
not an artifact to republish or send to browsers.

## Georeferenced scanned maps

The metadata adapter for an Allmaps-compatible IIIF Presentation 3 Manifest and IIIF Georeference
Annotation is implemented. The optional MapLibre image path consumes only release-local artifacts
whose metadata, pixels and georeference have three distinct approved rights decisions; arbitrary
visitor IIIF URLs are not accepted. No institution/map is enabled in production. A deterministic
synthetic fixture exercises the browser path while selection, rights review and artifact packaging
for a real map remain deferred. Scanned sheets never become the silent default basemap or count as
agreement with OHM or a reviewed reconstruction merely because their images overlap.

## Deep-time map strategy

The configured start remains 3400 BCE because that is the earliest asserted extent in the enabled
global source, not because the software treats it as the start of history. Ancient archive bounds
now follow `minimum_year`, so a reviewed source can extend the timeline earlier without a code
change. Earlier coverage should normally arrive as dated sites, finds, routes, interaction networks,
seasonal ranges and cultural regions. It must not be converted into state polygons merely to fill
the map.

The release contract now has a historical-name spine: sourced name attestations become a separate
time-filtered reviewed label layer and remain distinct from live OHM names. Most enabled
Cliopatria names currently have `temporal_basis: feature_interval`, however; source-specific
endonyms, scripts and independently dated changes still require curated gazetteer/OHM imports.

Prioritise additions in this order:

1. pilot one DHARMA corpus and one Syriaca collection to reduce South/Southeast Asian and Near
   Eastern gaps;
2. approve small Open Context project collections with coordinate sensitivity rules;
3. add Getty authority reconciliation and one reviewed ORACC corpus;
4. add reviewed OHM extracts for well-sourced local detail;
5. use explicitly licensed WHG/Linked Places datasets for reconciliation;
6. seek redistribution permission or open alternatives for Chinese, African,
   Indigenous, steppe and Islamicate specialist datasets.

World History Encyclopedia remains deferred as links-only tertiary reading; there is no bulk
ingestion plan.

## Accuracy from day one

The accuracy promise is procedural, not “every shape is correct.” Day one includes immutable raw
snapshots, no year zero, explicit spatial meanings, independent temporal/spatial/interpretive
confidence, review status, validation reports, visible coverage gaps, alternatives for disputes,
source attribution, release checksums, and deterministic rebuilds. New sources improve coverage
only after passing those same gates.
