# Seshat integration

Palimpsest uses selected public Seshat Global History Databank variables to add structured,
dated context to reviewed Cliopatria polities. It does not copy Seshat into a second editable
database, ask an AI model to interpret raw API responses, or replace the source data with generated
prose.

## Where visitors see it

Seshat evidence appears on the main map route after a visitor selects a reviewed polity, either by
clicking its geometry or choosing it in search. The right-hand reading surface places **Structured
sourced facts** after the thematic reading and before the longer primary reading.

Only assertions whose interval contains the active map year are shown. Each fact presents, in
order:

1. the variable name and structured value;
2. confidence, date range, evidence type, and a visible Seshat publisher link;
3. a plain-English restatement when an accepted one exists, clearly labelled with its model;
4. an expandable **Evidence and uncertainty** section containing the rationale, uncertainty,
   original Seshat explanation, references named by Seshat, record link, and licence.

Population, territory, and administrative-level estimates remain ranges. The interface never
turns them into a midpoint or a falsely exact value. A categorical coding is displayed as the
source value. If no matching assertion exists, the section is absent; this means the current
release has no matching coding, not that the thing did not exist.

The rendering component is
[`src/lib/components/RecordStructuredFacts.svelte`](../src/lib/components/RecordStructuredFacts.svelte),
mounted in the selected-record reading surface in
[`src/routes/+page.svelte`](../src/routes/+page.svelte).

## Data flow

```text
Seshat API pages + terms
          |
          v
checksummed raw snapshots
          |
          v
typed EvidenceAssertion records
          |
          +---- exact SeshatID join ----> reviewed Cliopatria features
          |
          +---- optional DeepSeek job --> checksum-bound restatement sidecar
          |
          v
immutable assertion index and shards
          |
          v
selected-year reading surface
```

There is no request-time Seshat or DeepSeek call. Fetching and restatement happen during editorial
build work. The browser receives only immutable, checksummed release artifacts and contains no
model credential.

## Acquisition and normalization

The `seshat_api` source is configured in
[`config/pipeline.yml`](../config/pipeline.yml). The adapter snapshots every paginated response and
the governing terms page under `data/raw/seshat_api/`. Raw snapshots are excluded from Git but
their checksums and attribution are carried into the release.

[`history_pipeline/adapters/seshat.py`](../history_pipeline/adapters/seshat.py) currently ingests:

| Seshat endpoint | Published predicate | Representation |
| --- | --- | --- |
| `sc/polity-populations` | `polity_population` | numeric range in people |
| `sc/polity-territories` | `polity_territory` | numeric range in square kilometres |
| `sc/administrative-levels` | `administrative_level` | numeric range in levels |
| `sc/written-records` | `written_record` | categorical value |
| `sc/roads` | `road` | categorical value |
| `sc/markets` | `market` | categorical value |
| `sc/ports` | `port` | categorical value |

For each accepted observation the adapter retains:

- Seshat record and polity identifiers;
- lower and upper date bounds, using the project chronology with no year zero;
- lower and upper numeric values or the categorical value;
- units;
- uncertainty and dispute flags;
- the original explanation and its SHA-256 checksum;
- references embedded in the explanation;
- exact record URL, API-page snapshot checksum, retrieval time, citation, and licence.

Malformed dates, reversed ranges, observations without a polity, and values with no usable coding
are rejected rather than guessed.

## Joining Seshat to map records

The API polity code first enters the pipeline as an acquisition-only identifier such as
`seshat-polity:EgOldK`. It is published only when it exactly matches the `SeshatID` property already
carried by an accepted Cliopatria feature.

The join is implemented in
[`history_pipeline/pipeline.py`](../history_pipeline/pipeline.py). A successful join replaces the
temporary identifier with the feature's canonical entity and feature IDs. Unmatched assertions are
not published. The pipeline does not use name similarity, geography, or an AI model to infer a
match.

## DeepSeek restatements

DeepSeek is an optional readability layer over one original explanation. It never receives the
whole database and never produces the structured value.

The command reads staged `EvidenceAssertion` records, selects Seshat assertions with a source
explanation, and asks for one or two short plain-English sentences:

```bash
export DEEPSEEK_API_KEY='...'
RESTATE_LIMIT=25 make restate-seshat
```

`RESTATE_LIMIT=0` processes every eligible explanation not already accepted for the same assertion
and source checksum. Accepted outputs are appended to
`data/editorial/seshat-restatements.ndjson`. Provider failures and validation rejections are not
published.

The prompt is [`prompts/seshat-restate-v1.txt`](../prompts/seshat-restate-v1.txt), and the provider
workflow is implemented in
[`history_pipeline/assertion_restatement.py`](../history_pipeline/assertion_restatement.py).

Every accepted restatement records:

- assertion ID;
- exact source-explanation checksum;
- prompt version and checksum;
- provider and actual model identifier;
- generation timestamp and provider response ID.

Local source-bound validation rejects wording that introduces a number or proper noun absent from
the source, exceeds the source length, or fails the required JSON shape. During a later build, a
restatement is attached only when its assertion ID and source checksum still match. A stale,
rejected, failed, or missing restatement simply falls back to the original explanation.

Changing a prompt is an editorial version change. To compare a new prompt without mixing accepted
outputs, run `history-data restate-assertions` with a new `--output` path and explicitly select the
reviewed sidecar in `assertion_restatements_path`.

## Build and release procedure

An online build fetches or reuses the configured Seshat snapshots and writes normalized staged
assertions:

```bash
uv run history-data build --no-advance-latest
```

After generating or reviewing optional restatements, rebuild from the saved snapshots and advance
the local release pointer:

```bash
uv run history-data build --offline
```

Verify that local release before publishing it:

```bash
uv run history-data verify-build
```

Use `--no-advance-latest` for a candidate that must remain isolated. That candidate does not become
the default target of `verify-build`; CI or an operator must verify it through a temporary release
root whose pointer names the candidate manifest. For a production release, use the repository's
normal `build-release`, verification, and publication workflow. Restatement generation is
deliberately not part of `build-release`: model cost and editorial review remain explicit actions.

The build writes `EvidenceAssertion` records into lazy assertion shards declared by
`assertion_index_path`. Selection loads the feature-adjacency shard and only the referenced record
shards. The complete dataset is not downloaded when a visitor opens the site.

## Licensing and attribution

The source registry records Seshat public data as CC BY-SA 4.0 with attribution, change disclosure,
and share-alike conditions. The release snapshots the terms page configured by the source, marks
normalized records as modified where applicable, and includes Seshat in the attribution ledger.

The original data, the source explanation, and generated wording remain distinguishable in the
interface. Generated restatements do not relicense or replace Seshat material. Before changing the
variables or distribution profile, review the current
[Seshat User Agreement](https://seshat-db.com/terms/current/) and update the recorded licence
decision if necessary.

## Failure and fallback behaviour

| Condition | Result |
| --- | --- |
| API unavailable during an online fetch | build fails; no partial live release is advanced |
| Cached snapshot used with `--offline` | exact saved bytes are reused |
| Observation cannot join by exact `SeshatID` | assertion is omitted |
| Invalid or empty coding | source record is rejected |
| DeepSeek call fails | original Seshat explanation remains available |
| Restatement violates source-bound checks | restatement is rejected |
| Source explanation changes | old restatement checksum no longer matches and it is omitted |
| Assertion is outside the selected year | fact is hidden for that year |
| No assertion exists | UI communicates no release coverage, never historical absence |

## Verification

Automated coverage includes adapter normalization, range validation, exact joins, generated-text
rejection, resume behaviour, assertion contracts, immutable artifact hashes, and frontend type
checking. A release must also pass `history-data verify-build`, which checks artifact checksums,
source snapshots, attribution, shard references, and assertion-to-feature/entity links.
