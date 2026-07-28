# Palimpsest

Palimpsest is an evidence-backed historical geodata pipeline and interactive public map
experience spanning 3400 BCE to the present. It does not treat every historical society as a
precisely bordered state and does not conceal uncertainty or missing coverage.

## What the backend produces

Each build emits an immutable, content-addressed release under `dist/data/builds/<build-id>/`:

- GeoParquet partitions for ancient, medieval, early-modern, and modern features;
- PMTiles v3 archives containing separate reviewed geometry and time-sensitive label layers when
  `--tiles` is enabled;
- indicator observations that retain their original geographic units;
- static revision-pinned Wiki entities and Wikipedia dossiers when `--enrich` is enabled,
  plus optional plain-English restatements of those dossiers;
- a sharded feature → entity → dossier content index for map-click lookup;
- bounded, date-aware feature context shards for related people, events, places and themes;
- a coarse region/time discovery index for nearby dated records on map selection;
- a separately reviewed, sharded causal-claim graph and curated interpretive paths;
- sharded, attributed PeriodO definitions linked by entity and selected time band;
- a public source-role registry and an observed-cell coverage-priority report;
- a lazy, immutable search index with name, time, exact-record and browse shards, plus a legacy
  bulk export, coverage matrix, complete attribution ledger, and build manifest;
- a small `dist/data/latest.json` pointer that allows atomic publication and rollback.

Canonical inputs and validation reports are retained under `data/staged/canonical/`. Downloaded
source snapshots and HTTP metadata are retained under `data/raw/` and excluded from Git.

## Quick start

```bash
make bootstrap
make check
make build-smoke
```

Smoke builds are retained under `dist/data/builds/` but deliberately use
`--no-advance-latest`, so a limited validation run cannot replace the local release pointer.

Generate vector tile archives:

```bash
make install-tippecanoe
uv run history-data build --limit 100 --tiles
```

Wikimedia enrichment requires a descriptive client name and version plus at least one valid
contact channel: an email address, an HTTP(S) project/contact page, or a Wikimedia
`User:Name`. It does not require both a URL and an email:

```bash
export WIKIMEDIA_USER_AGENT='Palimpsest/0.1 (https://example.org/palimpsest/contact)'
uv run history-data build --limit 100 --enrich
```

Enrichment progress is printed batch by batch and atomically checkpointed at
`data/staged/enrichment/status.json`. Re-running the same failed or interrupted input resumes
completed deterministic Wikidata and Wikipedia batches from their checksummed raw snapshots.
Changing the config or admitted feature set starts a new checkpointed run. This server-side
environment variable and the raw API responses are never published into browser artifacts.

Inspect available commands with `uv run history-data --help`.

## Run the interactive map

Validate the most recent generated release, then start SvelteKit:

```bash
npm install
npm run data:prepare
npm run dev
```

Open the URL printed by Vite. The interface loads the actual PMTiles, search index, manifest,
quality report, and source attribution produced by the pipeline. Vite serves `dist/data` directly
at `/data` during development, including PMTiles byte ranges; it does not copy the release into
`static/`.

Production builds require `VITE_DATA_BASE` to be the public R2 custom-domain namespace ending in
`/v1`, for example `https://data.example.org/v1`. They fail if `static/data` exists, preventing a
historical release from being bundled into the Pages artifact:

```bash
VITE_DATA_BASE=https://data.example.org/v1 npm run build
```

The map loads a compressed time-band search shard at bootstrap and a compressed two-character
n-gram shard only after a visitor searches. Exact entity/feature lookup and browse pagination use
separate immutable shards. `search.ndjson` remains a compatible bulk export but is not eagerly
downloaded by schema 1.9 clients.

The map also reads live vector tiles from OpenHistoricalMap for time-filtered local historical
detail and labels. A bundled, low-resolution Natural Earth land silhouette and neutral water sit
below that live layer as modern reference geography, so the world remains legible when remote
context is slow or unavailable; the release's reviewed
Cliopatria PMTiles remain a visibly distinct reconstruction layer above OHM detail and below OHM
labels. The layer control can isolate either source role. A network connection is therefore needed
for the live detail layer, while release artifacts remain static and checksummed.

An optional historical-map-image control can render an approved, release-local raster positioned
from IIIF/Allmaps-style georeference metadata. It appears only after metadata, image and
georeference rights receive separate release approvals. The UI exposes attribution, licences,
confidence and limitations and never treats the scan as authoritative geography. No real
institutional map is enabled in the open-core profile; the browser pilot uses a deterministic
synthetic fixture.

Selected public Seshat variables enrich Cliopatria polities at build time through the exact
`SeshatID` carried by the geometry release. Population and territory estimates remain numeric
ranges; institutional variables retain their coded value, date interval, uncertainty/dispute
flags, original explanation, named references, API snapshot checksum and CC BY-SA attribution.
An uncoded variable remains a coverage gap.

After a build has staged those assertions, DeepSeek Flash can make the explanatory notes easier to
read:

```bash
make restate-seshat
uv run history-data build --offline --enrich
```

This changes wording, not data. Each one- or two-sentence restatement is derived from exactly one
Seshat explanation, checked so it introduces no new number or proper noun, and bound to the source
text's checksum. The selected-year panel shows the structured value first, labels the generated
wording with its actual model, and keeps the original Seshat explanation and references available.
A failed or stale restatement is omitted. See the complete
[Seshat integration guide](docs/seshat-integration.md) for its screen placement, data flow,
supported variables, operational commands, fallbacks, and licensing rules.

World Historical Gazetteer serves a different purpose: historical-name reconciliation and
reviewed authority links rather than polity facts or replacement geometry. Because Palimpsest
is non-commercial, a bounded WHG pilot can live in the separate research distribution profile
after authenticated responses, per-namespace attribution, checksums, and editorial decisions are
captured. With a local `WHG_API_TOKEN`, run `make acquire-whg`; all returned identities remain
proposed until review. Run `make acquire-whg-western-ghats` to refresh the bounded,
non-production ten-record specialist-dataset preview. It does not enable or publish the layer.
See the [WHG integration decision](docs/whg-integration.md).

Build the deterministic schema 1.10 browser pilot and exercise place selection end to end:

```bash
make build-browser-pilot
npm run test:browser
```

The pilot is an immutable, verifier-checked release under `tests/browser/fixtures/data`. It contains
one revision-pinned enriched record and bounded context plus one deliberate missing-enrichment
record, so browser tests cover map selection, search selection, successful joins, and honest
missing-dossier states without live Wikimedia requests or generated prose. It also contains the
synthetic rights-approved historical-map fixture used to test image rendering.

Wikipedia leads answer "what is this now, administratively". A visitor standing on a map at a
chosen year asked something else. The restatement tier re-serves one revision-pinned extract in
plain English with the history first, and publishes it beside the original rather than instead of
it:

```bash
uv run history-data restate-dossiers \
  --dossiers data/staged/canonical/dossiers.ndjson \
  --output data/editorial/restatements.ndjson \
  --provider deepseek --model deepseek-v4-flash --limit 25
```

A restatement combines nothing and adds no claim, so it needs no per-claim human review. What it
needs instead is mechanical proof that it stayed inside its source: every number and proper noun in
the output must already appear in the input, a deny list rejects unlicensed evaluative register,
and the output may not be longer than the source. Failures are dropped and the reader falls back to
the source extract, so a false positive costs coverage and never correctness. A restatement is
bound to one source checksum and disappears from the release when that revision changes. Like real
dossier generation, this is an explicit build-time action needing an API key and a named `--model`;
the browser application contains no LLM client or credential. OpenAI and DeepSeek are both
supported; a provider that cannot enforce a response schema receives the contract in the prompt
and is validated locally instead. See the
[restatement tier](docs/dossier-restatement.md).

A year page answers a different question again: not "what is this place" but "what was happening".
`build-chronicle` ingests a Wikipedia year article and its topic and country companions as dated
records; `build-year-context` adds what the year article does not know about itself, namely which
wars Wikidata records as running across the year and which Commons pictures clear the release
licence policy file by file; `year-dossier` writes the prose:

```bash
uv run history-data build-chronicle --year 1543 --output data/chronicle/1543.json
uv run history-data build-year-context --year 1543 \
  --chronicle data/chronicle/1543.json --output data/chronicle/1543-context.json
uv run history-data year-dossier --chronicle data/chronicle/1543.json \
  --lenses data/chronicle/1543-lenses.json --context data/chronicle/1543-context.json \
  --output data/chronicle/1543-dossier.json --provider deepseek --model deepseek-v4-flash
```

Most of a year dossier is not written. The lede is assembled from the year's three
most-written-about records in the sources' own words, the register carries every record verbatim,
the offices held, the wars in progress and the cross-links to the 44 other years a single year
names are all rendered rather than narrated, and who was born, who died and what was made are
shown as faces and rows rather than as paragraphs of commas. The prominent few carry one restated
sentence saying who or what they were — never why they mattered, which is the claim an unreviewed
tier cannot earn.

A build publishes whatever years are ready as `years/{year}.json` plus a `years/index.json`, and
`verify-build` re-proves them from the release alone: every picture cleared again against the
release licence policy, every file still matching its own checksum, and the index agreeing with
each dossier about which other years it reaches. What is left for prose is checked twice: once against
the whole year and once against each block's own evidence, so a paragraph cannot borrow a name
from a record it is not about. Render one and read it with
`scripts/render-year-dossier.py`. See the [year dossier](docs/year-dossier.md), which also records
the measured rate at which two true facts get fused into a false one, and what that measurement
does and does not support.

Build the deterministic 1543 editorial-dossier pilots:

```bash
make build-1543-dossier-pilots
```

These ingest saved schema-constrained outputs without an API call, verify every claim against the
approved schema 1.10 assertions and exact, revision-pinned Library of Congress fields, and stop at
`machine_drafted`. The Copernicus publication and a royal cedula sent toward Michoacán are the
first two anchors in the bounded [world in 1543 pilot](docs/pilot-1543.md). Human review and
publication remain explicit editorial commands and are simulated only inside tests. Real
generation is an explicit build-time CLI action requiring `OPENAI_API_KEY` and a `--model`
identifier; the browser application contains no LLM client or credential. See the
[editorial dossier pipeline](docs/editorial-dossier-pipeline.md).

Reviewed labels come from first-class historical-name attestations rather than a timeless display
string. Search and map labels choose the attestation active in the selected year and disclose when
its chronology was merely inherited from the geometry interval. Clicking OHM detail opens a
separate contributor-record reading state; it is never passed off as a reviewed canonical record.

The visitor can also foreground non-exclusive historical lenses: All history, Power & governance,
Belief & ritual, Knowledge & technology, Culture & society, and Trade & movement. Reviewed records
use versioned, structured rules that emit sourced thematic assertions; tile tags are derived from
those assertions. Live OpenHistoricalMap context is filtered only through explicit feature types.
A record may appear in several lenses; missing thematic coverage is never presented as evidence
that the corresponding history did not exist. See the
[thematic classification contract](docs/thematic-classification.md).

Schema 1.10 separates first-class people, events, institutions, works/artifacts and routes from
their map geometries, publishes evidence-backed structured assertions, and declares map-source,
thematic, confidence and provenance layer roles. The initial bounded Knowledge slice maps the
1543 Nuremberg publication of Copernicus's *De revolutionibus*; it is deliberately not a global
knowledge-history import. See the
[entity and layer architecture](docs/entity-event-layer-architecture.md).

Future community contribution handling is bounded by proposal and accepted-release-receipt
contracts. Proposals remain separate from canonical records, rejected proposals cannot receive a
release receipt, and no authentication or CMS is implemented. See the
[community contribution boundary](docs/community-contributions.md).

Run `uv run history-data verify-build --require-tiles` before any publication. GitHub Actions runs
the same check, retains the build for inspection, uploads raw snapshots to a private R2 bucket,
uploads public immutable artifacts concurrently, and advances `v1/latest.json` only after every
other upload succeeds. Configure the secrets listed in the Cloudflare deployment guide before
enabling scheduled publication.

## Architectural boundary

GeoLibre or QGIS can open and review the canonical GeoParquet files. The public website must only
consume published PMTiles and static JSON/NDJSON contracts. Source-specific fields, API keys, live
queries, and geometry-repair logic never belong in the visitor-facing application.

See [the data contract](docs/data-contract.md), [source policy](docs/source-policy.md), and
[Cloudflare deployment guide](infra/cloudflare/README.md). Editors can use the
[GeoLibre curation workflow](docs/curation-workbench.md); the [source roadmap](docs/source-roadmap.md)
states what V1 covers and what it deliberately does not claim. The UI consumes only the documented
[frontend data contract](docs/frontend-contract.md).
The bounded predicate, language, redirect and content-role rules are documented in the
[Wiki content contract](docs/wiki-content.md).
The distinction between factual relationships and attributed causal arguments is defined in the
[causal claims contract](docs/causal-claims.md).

## Licensing

Pipeline source code is MIT licensed. Historical data is not relicensed: every record and artifact
retains its upstream source and licence. The default `config/pipeline.yml` is the commercially
redistributable `open_core` profile. `config/research-overlay.yml` is a separate, opt-in
non-commercial research profile; artifacts built from it must not be presented as open-core
releases.

The build-time [source integration framework](docs/source-integration-framework.md) covers reviewed
authority-reconciliation snapshots and IIIF georeference metadata. These artifacts never cause the
visitor-facing application to query WHG, Getty, Allmaps, IIIF providers, or any other third party.

Because this deployment is non-commercial, `make build-release` and the data-release workflow use
the reviewed `config/research-overlay.yml` profile. That makes accepted Getty TGN and
OpenStreetMap authority links available to the record drawer. To produce the narrower,
commercially redistributable release instead, run
`make build-release PIPELINE_CONFIG=config/pipeline.yml`; the profiles remain deliberately
separate, and the effective configuration participates in the immutable build ID.
