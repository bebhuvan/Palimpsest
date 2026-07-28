# World Historical Gazetteer integration

World Historical Gazetteer (WHG) should be used by Palimpsest as a historical-place
reconciliation and authority-linking service. It complements Seshat but does not play the same
role:

- Seshat supplies dated scholarly assertions about polities.
- WHG helps determine which historical place a name refers to and which external authority records
  describe it.

The project is non-commercial, so WHG's CC BY-NC platform output can be admitted to the
`research` distribution profile with attribution. It must not enter the commercially reusable
`open_core` profile. Records originating in a named source gazetteer also retain that source's
licence and attribution requirements.

## Decision

Use WHG for a bounded reconciliation pilot after an API token is configured. Do not ingest the
entire union index, publish unreviewed candidate matches as identities, or treat returned geometry
as superior to reviewed Palimpsest geometry.

The current API advertises:

- structured place, period, dataset, collection, and area retrieval;
- Reconciliation Service API v0.2;
- exact, fuzzy, prefix, and containment-aware search;
- date, country, feature-class, type, bounds, radius, dataset, and namespace filters;
- extension properties including names, country codes, feature classes, geometry, and temporal
  ranges;
- public source-registry and attribution endpoints.

Most reconciliation and entity requests require a WHG account token. The token belongs only in the
build environment and must be sent in an `Authorization: Bearer` header. It must never enter a
request URL, raw snapshot, release artifact, browser bundle, or log.

WHG registration does not require a college, university, organization, or active academic role.
WHG uses ORCID for registration and login, but anyone can create a free ORCID iD without an
institutional affiliation. After signing in to WHG with ORCID, generate the API token from the WHG
profile page.

## What it adds

WHG can add value in four areas:

1. **Historical-name resolution.** Match an attested name against dated place candidates instead of
   guessing from a modern label.
2. **Authority bridges.** Connect a Palimpsest place to reviewed WHG, Getty TGN, Pleiades,
   Wikidata, GeoNames, OpenHistoricalMap, Trismegistos, or specialist-gazetteer identifiers.
3. **Editorial discovery.** Surface plausible records from regional gazetteers when the project has
   weak coverage, while keeping them as candidates until reviewed.
4. **Source-aware enrichment.** After a match is accepted and its underlying dataset rights are
   reviewed, import selected alternate names, place types, temporal bounds, and links with their
   original lineage.

Direct Pleiades, PeriodO, Wikidata, and Cliopatria integrations remain authoritative for their own
source records. A WHG result pointing back to one of them is useful corroboration or reconciliation
metadata, not a reason to duplicate or overwrite the direct record.

## What it must not do

- No live WHG call from the public browser.
- No API token in client-side code.
- No automatic identity decision based on a provider score.
- No fuzzy name match silently rewriting a canonical entity ID.
- No whole-index mirroring.
- No replacement of reviewed polity geometry.
- No assumption that every indexed namespace has the same licence.
- No use of a missing result as evidence that a place did not exist.
- No DeepSeek summary step for structured reconciliation results.

WHG's own registry exposes whether an indexed gazetteer is marked redistributable or downloadable.
Those flags are useful admission signals, but they do not replace a Palimpsest rights review of
the named underlying dataset.

## Deeper API audit (26 July 2026)

The live OpenAPI schema is version `1.0.0`; the reconciliation manifest identifies Reconciliation
Service API `0.2`. The available surface is broader than the initial reconciliation pilot:

| Capability | Endpoint | App decision |
| --- | --- | --- |
| Service discovery | `GET /reconcile` | Build-time compatibility check |
| Batch place and period reconciliation | `POST /reconcile` | Use for bounded editorial queues only |
| Reconciliation property catalogue | `GET /reconcile/properties` | Discover enrichment fields; parse returned JSON strings defensively |
| Place/period suggestions | `GET /suggest/entity`, `GET /reconcile/periods/suggest` | Do not use for visitor autocomplete |
| Authority dataset inventory | `GET /reconcile/authority-datasets` | Find small, relevant published collections |
| Canonical entity retrieval | `GET /entity/{type}:{id}/api` | Snapshot selected places, datasets, collections, areas, or periods at build time |
| Persistent identifiers | `https://w3id.org/whg/id/{id}` | Preserve as stable citations where supplied |
| Namespace registry and attribution | `GET /api/sources/`, `GET /api/attribution/` | Snapshot for provenance and admission review |
| Contributor hard links | `GET/POST/DELETE /api/links` | Read-only inspection at most; never mutate from this app |
| Entity create/update/delete | entity mutation endpoints | Out of scope |
| Registry, retention, and preview endpoints | registry/retention APIs and entity preview HTML | Internal or unsafe for this integration; do not use |

The Entity API's most useful capability is complete dataset retrieval. A `dataset:{id}` request can
return an LPF `FeatureCollection` with a dataset citation, DOI, platform licence notice, and all
features. WHG currently nests dataset-feature names, dates, links, types, relations, and
descriptions under `properties`, unlike the simpler top-level LPF place response. The
`linked_places` adapter now supports both forms. A dataset remains disabled until its own rights,
historical semantics, checksum, and attribution have been reviewed.

The property-extension API advertises alternate-name arrays and summaries, WKT/GeoJSON geometry,
centroids and bounding boxes, temporal objects and years, country codes, feature classes, AAT
types, dataset identity, and the full LPF feature. Period extensions additionally advertise
chrononyms, authority, temporal bounds, spatial coverage, PeriodO identifiers, and editorial
notes. Live responses sometimes put structured values inside JSON-encoded `str` fields, so they
must be parsed twice and schema-checked; extension output must not be passed straight to the UI.

### Live reliability findings

- A 50 km reconciliation query returned same-named candidates in Australia and Canada. Local
  Haversine validation is mandatory and is implemented in acquisition.
- WHG's `match: true` can describe a distant same-name result. It is a ranking signal, not an
  identity decision.
- Generic entity suggestions produced unrelated high-scoring places for `Pataliputra`, even with
  namespace filters. This endpoint is unsuitable for public search or autocomplete.
- Exact containment and date filters substantially improve results, but still return different
  entity types and historical interpretations that need review.
- The canonical Patna entity provides useful exact/close links to TGN, Wikidata, Library of
  Congress, VIAF, and GeoNames, but its historic temporal evidence is sparse. WHG is strongest as
  an authority bridge here, not as the only source of historical dates.
- Period results use different identifiers and score behavior across suggestion, reconciliation,
  and entity responses. Palimpsest already integrates PeriodO directly, so WHG periods are not
  admitted.
- Preview URLs accept the token in the query string. The app never uses previews because this risks
  placing the credential in logs, browser history, and rendered markup.

### Specialist datasets worth considering

The authority-dataset inventory exposed 48 collections during the audit, 47 marked public and
published, representing about 228,918 listed places. These are not one homogeneous source. The
best app candidates are small scholarly layers with a clear historical question:

| Dataset | Observed coverage | Potential use | Admission caveat |
| --- | --- | --- | --- |
| Buddhist monasteries of the Western Ghats (`dataset:693`) | 55 sites; 54 dated; all located; descriptions and 39 authority-linked records | Compact archaeology and belief collection for western India | Original Zenodo record is CC BY-NC 4.0; repeated broad dates appear to be collection scope rather than site-specific activity |
| Voyage Around the Erythraean Sea (`dataset:1165`) | 31 described, located places | Ancient maritime itinerary and possible identifications | Intervals such as 50–2022 conflate ancient mention with modern identification; needs source-specific date semantics |
| Journey of Faxian (`dataset:1354`) | 18 places dated 399–414 | Traveller itinerary/context | 11 of 18 records have no geometry |
| Benjamin of Tudela (`dataset:1365`) | 215 returned places dated 1166–1171 | Traveller itinerary/context | 85 records have no geometry; API citation reports 217, so the count discrepancy must be resolved |
| Pre-Colonial African Subregions (`dataset:1155`) | 34 mostly dated, described regional geometries | Scholarly regional context that improves African coverage | Interpretive subregions, not polity borders; preserve the author's definitions and perspective |
| Old World Trade (`dataset:12`) | 4,117 places, 2,280 dated | Large trade-network discovery corpus | Too broad for a first import; names are often titles only and records need a bounded use case |

WHG also lists collections on African ports and settlements, Poland in the sixteenth century,
Indigenous place names in North America, Roman stone quarries, Libyan heritage, Chinese historical
administration, archaeological surveys, and historical journeys. Inventory status and
`downloadable`/`redistributable` flags are discovery hints, not proof of downstream rights.

### First specialist-dataset preview

The first authenticated dataset preview retrieved 10 of the 55 Western Ghats monastery records in
deterministic title/source-ID order. It is stored at
[`data/editorial/whg/western-ghats-preview.json`](../data/editorial/whg/western-ghats-preview.json)
with the provider feature count, retrieval time, source endpoint, and checksum of the complete
provider response. The token is not serialized.

The original [Zenodo dataset](https://zenodo.org/records/998080) explicitly uses CC BY-NC 4.0.
This confirms research-profile compatibility but not open-core or commercial eligibility. The
preview's repeated 100 BCE–449 CE range appears to encode the collection's inclusion criteria,
rather than site-specific construction or continuous occupation. It therefore remains
non-production. The detailed review and proposed timeless-collection treatment are recorded in
[`western-ghats-preview.review.md`](../data/editorial/whg/western-ghats-preview.review.md).

Regenerate the bounded preview with:

```bash
make acquire-whg-western-ghats
```

Override only the preview size when needed:

```bash
WHG_DATASET_LIMIT=25 make acquire-whg-western-ghats
```

The general acquisition command is `history-data acquire-whg-dataset --dataset-id ID --output
PATH --limit N`. It is deliberately a preview command; it does not enable a pipeline source or
publish records.

## Proposed visitor placement

WHG reconciliation should not appear as a new map layer. It appears only after an editorial match
has been accepted. A separately reviewed specialist dataset may later become a clearly labelled
context layer.

In the selected-record reading surface:

- accepted identifiers belong in a **Names and identifiers** or **Authority connections** section;
- a dated alternate name may join the existing name-attestation display only when the source
  record independently supports its wording and interval;
- each connection should show the authority label, namespace, relation (`exact match` or
  `close match`), confidence rationale, source link, attribution, and licence;
- WHG should be identified as the reconciliation route, while the underlying gazetteer remains
  named as the record source.

Proposed, ambiguous, and rejected candidates belong in the curation workbench, not in ordinary
visitor reading. A future coverage view may report how many records are unmatched or awaiting
review, but it must not plot reconciliation candidates as historical locations.

The frontend reads the checksummed `integrations/authority-matches.ndjson` artifact and renders
only `accepted` `exact_match` or `close_match` records in **Authority connections**. Proposed and
rejected candidates fail closed at the reader boundary. The current artifact is small; if accepted
coverage grows materially, replace the bulk file with subject-ID lookup shards.

## Acquisition workflow

The live acquisition job should:

1. select a bounded queue of Palimpsest subjects;
2. construct one query per subject using its attested name, active date range, representative
   location or bounds, feature class, and an explicit namespace allowlist;
3. POST a bounded batch to `https://whgazetteer.org/reconcile`;
4. fetch `/api/attribution/` for every namespace present in the response;
5. snapshot the OpenAPI schema version, query body, response, attribution response, retrieval time,
   and checksums without the token;
6. wrap the result in the existing reviewed reconciliation envelope;
7. normalize each candidate as an `AuthorityMatch` with status `proposed`;
8. require an editor to accept or reject the relation;
9. publish only accepted matches to the visitor-facing lookup.

A useful first pilot is 25–50 records with poor alternate-name or authority coverage, not the
entire feature collection. Each query should request at most five candidates. Date, location, and
namespace filters should be as restrictive as the source evidence permits.

For a Pleiades pilot, exclude the `pl` namespace from the query. Palimpsest already has the
direct Pleiades record, so a Pleiades-to-Pleiades result proves plumbing but adds no authority
connection. The default acquisition command searches `whg,gn,tgn,wd,osm,ohm`.

WHG currently does not consistently enforce the submitted radius: a real 50 km test returned
same-named candidates on other continents. The acquisition code therefore recalculates geodesic
distance from every returned `repr_point`, admits only candidates inside the configured radius,
and retains excluded responses with `outside_requested_radius` in the audit snapshot. Provider
`score` and `match` values cannot bypass this local gate.

The live API uses a provider-defined score. The acquisition wrapper must declare and normalize its
scale before the existing adapter receives it; the adapter contract uses `0–100`. Provider scores
rank candidates but never establish identity.

## Existing implementation

Palimpsest already contains:

- a disabled `whg_reconciliation` source in
  [`config/research-overlay.yml`](../config/research-overlay.yml);
- an [`authority_reconciliation` adapter](../history_pipeline/adapters/reconciliation.py) for
  checksummed, rights-wrapped, editorially reviewed snapshots;
- the `AuthorityMatch` schema with source, rights, confidence, review status, relation, and
  transformation lineage;
- immutable integration artifacts and attribution handling;
- an app loader and selected-record **Authority connections** component that expose accepted
  matches only;
- a Linked Places adapter that understands both ordinary LPF and WHG dataset-entity nesting;
- tests that reject missing rights, undeclared namespaces, invalid scores, and accepted matches
  without an explicit relation.

The normalization adapter intentionally does not call WHG. The separate `acquire-whg` command makes
authenticated requests, sanitizes the result, and produces the immutable review input. Keeping
acquisition separate from normalization prevents a changing live service or a secret from entering
deterministic offline builds.

## Configuration and credentials

The pilot belongs in `config/research-overlay.yml`, which is already a non-commercial distribution
profile. The source should remain disabled until the first real snapshot has:

- a bounded query set;
- a declared schema/provider version;
- a SHA-256 checksum;
- WHG platform attribution;
- attribution and licence metadata for every returned namespace;
- an editorial review state;
- an explicit namespace allowlist.

The acquisition command should read:

```bash
export WHG_API_TOKEN='...'
export WHG_USER_AGENT='Palimpsest/0.1 (project contact URL or email)'
```

Neither value is published. WHG also asks API clients to send a suitable user agent.

To obtain the token:

1. create a free [ORCID iD](https://orcid.org/register) if needed;
2. [sign in to WHG](https://whgazetteer.org/accounts/login/) with ORCID;
3. open the WHG profile page and generate an API token;
4. store it locally as `WHG_API_TOKEN`, never in Git or frontend configuration.

Once configured, generate the bounded pilot with:

```bash
make acquire-whg
```

Override its bounds explicitly when needed:

```bash
WHG_LIMIT=50 WHG_CANDIDATES=3 make acquire-whg
```

The command reads the token from the process environment or the Git-ignored local `.env`, writes
`data/editorial/whg/reconciliation-pilot.json` atomically, and never serializes the credential.
It also writes `data/editorial/whg/reconciliation-pilot.review.csv`, with blank `decision`,
`relation`, and `reviewer_note` columns. Reviewers work in that sheet rather than changing the
source snapshot. Every surviving candidate remains `proposed` until a reviewer records an explicit
decision and the reviewed snapshot is admitted through the reconciliation adapter.

## App data flow

```text
WHG token in local build environment
        ↓
bounded acquire-whg request + local spatial validation
        ↓
sanitized snapshot + review CSV (no credential)
        ↓
editor accepts exact/close identities
        ↓
checksummed AuthorityMatch release artifact
        ↓
app displays Authority connections for the selected Palimpsest record
```

Visitor devices never contact WHG. If WHG is unavailable, the released app keeps working. For a
future specialist dataset, the analogous path is dataset Entity API → pinned LPF snapshot →
dataset-specific rights/date review → `linked_places` normalization → ordinary release artifacts.

## Current pilot

The first authenticated pilot was retrieved on 26 July 2026 against WHG API schema `1.0.0`. It
selected 25 deterministic Pleiades settlements or archaeological sites lacking Wikidata links and
searched cross-authority namespaces within 50 km:

- 14 subjects received at least one locally valid candidate;
- 18 candidates survived local spatial and namespace validation;
- 16 carried a WHG provider match flag;
- 49 same-name or similar-name results were retained only as out-of-radius discards;
- surviving candidates were 17 canonical WHG records and one OpenStreetMap-namespaced record;
- the farthest admitted candidate was 18.122 km from the source point;
- no identity was accepted.

The pilot demonstrates why review is essential. Some subjects have two same-named candidates at
nearly the same point, and provider flags alone cannot decide which entity is the appropriate
authority connection. The sanitized evidence snapshot is checksum-ready for admission; rerunning
acquisition creates a new timestamped evidence state and therefore a new checksum.

An entity-level audit then found that 13 of the 18 candidates are WHG-hosted
`Pleiades (partial)` mirrors with the same Pleiades source ID as the query subject. They are
circular duplicates and are recommended for rejection. The five genuine cross-authority
candidates are:

- the OpenStreetMap mountain-peak node used as Montagna di Gildone's representative point;
- Getty TGN close matches for Longobucco, Eratini, Wingham, and Cavaillon/Cabellio.

These five are recommendations, not published identities. Their decisions, proposed relations,
and evidence notes are recorded in `reconciliation-pilot.review.csv`. This establishes a new
review rule: a `whg` namespace result must be inspected for its underlying dataset and source ID
before acceptance, because namespace filtering alone does not exclude WHG-hosted mirrors of the
input authority.

Direct-source verification changed the Montagna di Gildone relation from `exact_match` to
`close_match`: Pleiades describes fortifications and Samnite tombs on the mountain, while OSM
describes the mountain peak as a physical feature. The four Getty records also represent modern
inhabited places related to ancient Pleiades places. All five links are therefore `close_match`.

The `direct_authority` adapter now fetches the four official Getty Linked.Art JSON records and the
versioned OSM node directly, validates their reviewed identifiers and labels, and emits accepted
authority links with per-source rights. WHG remains in transformation lineage as the discovery
route; it is not presented as the source of the Getty or OSM identity.

The research profile contains:

- four Getty TGN records under ODC-By 1.0 with Getty's requested attribution;
- one OpenStreetMap record under ODbL 1.0 with OpenStreetMap attribution;
- per-record raw or canonical-content checksums;
- direct authority URLs and explicit close-match rationales.

An isolated live adapter run validated all five records. During the complete research-release
test, the Library of Congress `loc_new_laws` API response changed its whole-response checksum.
Review found that its evidence-bearing catalog fields were unchanged while request timestamps,
recommendations, search scores, and array ordering were volatile. Routine builds now reuse the
approved snapshot; live refresh remains an explicit editorial review. The comparison and release
decision are recorded in `data/editorial/loc-new-laws-refresh-review.md`.

## Licensing

WHG's API attribution endpoint currently describes its platform overlay as CC BY-NC 4.0. This is
compatible with Palimpsest's declared non-commercial research profile, subject to attribution
and the licence terms. Underlying indexed datasets have separate rights: examples include CC BY,
ODC-By, ODbL, CC0, non-commercial, and restricted material.

For every accepted match, preserve:

- WHG attribution and CC BY-NC notice;
- the underlying namespace and source citation;
- the underlying dataset licence and link;
- an indication that Palimpsest normalized and reviewed the response;
- the retrieval date and snapshot checksum.

If the project later becomes commercial, WHG-derived platform output must be excluded or separately
relicensed. Records acquired directly from an underlying open dataset can remain only if their
direct-source lineage and independent rights review are complete.

Review the current [WHG API documentation](https://docs.whgazetteer.org/content/technical/apis.html),
[interactive OpenAPI schema](https://whgazetteer.org/api/schema/swagger-ui/), and
[WHG licence](https://docs.whgazetteer.org/content/license.html) before enabling a new snapshot.

## Verification and fallback

| Condition | Result |
| --- | --- |
| Token is absent or rejected | acquisition stops; offline builds remain usable |
| API response or attribution is incomplete | snapshot is not admitted |
| Namespace is outside the allowlist | candidate is rejected |
| Dataset rights are unknown or restricted | no visitor-facing enrichment |
| Score is high but editorial review is absent | candidate remains proposed |
| Accepted match lacks an exact/close relation | validation fails |
| Snapshot checksum changes | build fails pending review |
| WHG is unavailable to a visitor | no effect; the site uses release-local artifacts |

The pilot is successful if it improves historical-name and authority coverage without creating
false identities. Measure accepted exact/close matches, reviewer rejection rate, newly sourced
name attestations, namespace and regional distribution, and unresolved cases. Do not measure
success by raw candidate count.
