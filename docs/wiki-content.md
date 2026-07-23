# Wiki content ingestion contract

Wiki content is optional, build-time enrichment. A visitor request never reaches Wikimedia.

## Identity chain

The durable chain is:

```text
feature_id -> entity_id -> dossier_id -> related entity IDs
```

- `feature_id` identifies one spatial/temporal assertion and is copied unchanged into PMTiles.
- `entity_id` identifies the subject independently of a display name or geometry. Wikidata IDs are
  namespaced as `wikidata:Q…`; unreconciled features receive `feature:<feature_id>`.
- `dossier_id` is based on the content provider, language and canonical page ID, for example
  `wikipedia:en:12345`.
- relationships are typed Wikidata predicate assertions on an entity. Configured relation targets
  may be admitted into a capped depth-one context frontier; the pipeline never follows their edges.

The sharded selection contract is defined in `frontend-contract.md`. Bulk entity/dossier NDJSON is
for analysis and export, not map-click lookup.

## Bounded Wikidata projection

Wikidata is read through `wbgetentities`, not an open-ended SPARQL traversal. The default projection
contains labels, descriptions and aliases in configured languages; selected Wikipedia sitelinks;
Commons filename references; dates; and these explicit relation predicates:

| Predicate | Meaning |
| --- | --- |
| P31 | instance of / entity type |
| P571, P576, P580, P582, P585 | inception, dissolution, start/end and point in time |
| P569, P570 | birth and death |
| P155, P156 | predecessor and successor |
| P36 | capital |
| P17, P131, P361, P463, P527, P150 | parent, location, membership and territorial/part relationships |
| P793, P607, P710, P1344 | significant event, conflict and participation |
| P112, P19, P20, P276 | founder, birth/death place and location |
| P106, P39, P135, P136, P921, P1269 | occupations, roles, movements, genres and themes |
| P18, P373, P625 | Commons candidates, Commons category and coordinates |

Unknown configured predicates fail the build. `relationship_depth` accepts only zero or one. At
depth one, only `expansion_predicates` are followed, at most 40 targets per seed and 2,000 targets
per build by default. Targets linked by more independent seeds rank first, then numeric QID makes
ties deterministic. Depth-one entities record their seed IDs and discovery predicates. Their own
relationships are parsed for reading but never traversed. Public WDQS/SPARQL is not a production
dependency and inverse discovery is deliberately deferred until it can use a pinned dump/index.

Requests contain at most 50 QIDs. QIDs are assigned to deterministic two-hex hash buckets, then
split into stable batches; adding an ID invalidates only its bucket. Responses are conditionally
revalidated, checksummed, retained as content-addressed raw snapshots, and work offline. Wikimedia
API errors, malformed response shapes, unsupported predicates and nonzero depth fail closed. HTTP
429/5xx responses use bounded retries and `Retry-After`; requests include `maxlag=5` and the release
workflow requires a descriptive client name/version and at least one contact channel: email,
HTTP(S) project/contact page, or Wikimedia `User:Name`. A URL and email are not both required.
The value is read only by the publishing pipeline; it is not emitted into public artifacts or
browser code.

Every enrichment run writes atomic batch progress to
`data/staged/enrichment/status.json`, including its input fingerprint, current state, completed
Wikidata/Wikipedia batch keys, result counts, and a closed error record on failure. A retry with
the same configuration and admitted feature IDs reuses the checksummed raw response for every
completed batch. A changed input starts a new run rather than applying a stale checkpoint.

Wikidata times preserve their original time string, precision, calendar model, before/after values,
statement rank and statement ID. Selected date and relationship statements also retain qualifiers
and normalized reference snaks. A convenience historical year is derived with an explicit
astronomical-to-BCE/CE conversion; it never replaces the original claim.

## Feature context contract

Schema 1.5 and later publish `context/index.json` plus `context/features/{shard}.json`, keyed by exact
`feature_id`. Context candidates must be explicit relationships from that feature's depth-zero
entities and must have a fetched target entity. Ranking gives bounded weight to relationship type,
retained references, temporal overlap and configured-language sitelinks. Per-role quotas prevent a
single large class (often people) from consuming the entire result. Known out-of-period targets are
excluded except explicit predecessors and successors; unknown chronology is shown as unknown, not
invented.

Each item publishes its target entity ID, role, relationship types, date bounds, evidence strength,
selection reasons and available dossier IDs. This score is a retrieval ranking, never historical
importance or truth. The verifier checks the feature, seed entity, context entity and dossier joins
and rejects wrong hash shards. The frontend fetches the index and one feature shard only after a
selection, applies the selected-year margin, then fetches just the required entity/dossier shards.
The context layer cannot contain causal claims; those remain in the reviewed causal contract.

## Wikipedia language and revision policy

Only titles already asserted by an admitted feature or one of the admitted depth-zero/depth-one
entities' selected-language Wikidata sitelinks are fetched. Depth-zero pages are always retained;
related pages are deterministically capped at 1,500 by default. The configured language is fetched
first; `fallback_languages` defines the future ordered fallback, but the pipeline does not download
every sitelink. Adding a language means
adding a separately reviewed Wikipedia source configuration/API endpoint and preserving that
language in `dossier_id`.

Each request contains at most 20 titles and uses deterministic hash buckets. A dossier preserves:

- requested titles, the canonical title and redirect sources;
- language, page ID, revision ID and revision timestamp;
- canonical URL, raw-response snapshot checksum and extract checksum;
- publisher, citation, attribution and CC BY-SA licence;
- linked entity IDs and the `tertiary_summary` role.

Wikipedia records also carry `dossier_kind: source_extract`. This must not be changed to
`generated_editorial`, even when an editorial dossier discusses the same entity. Generated
editorial prose follows a separate evidence, review and licensing workflow and never overwrites a
Wikipedia revision.

The interface must label Wikipedia as a tertiary summary and link to the revision-attributed page.
It must not imply that its extract is project-authored interpretation or primary evidence.

## Wikisource, Commons and other encyclopedias

- A Wikisource transcription is a `primary_source` dossier and needs work identity, edition,
  transcription revision, language, page range, licence and attribution. It may link to an entity
  but must not replace an encyclopedia summary or project interpretation.
- A Commons P18 value is only a filename candidate. Publishing the image requires a separate build-
  time metadata fetch that pins the file revision and validates the individual file licence, author,
  attribution text and derivative status. That fetch is deliberately deferred.
- Another encyclopedia can be a `tertiary_summary` provider with its own namespaced page ID,
  revision/provenance and licence. Text may not be copied merely because a Wikidata sitelink exists.
