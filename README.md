# History Joice

History Joice is an evidence-backed historical geodata pipeline and interactive public map
experience spanning 3400 BCE to the present. It does not treat every historical society as a
precisely bordered state and does not conceal uncertainty or missing coverage.

## What the backend produces

Each build emits an immutable, content-addressed release under `dist/data/builds/<build-id>/`:

- GeoParquet partitions for ancient, medieval, early-modern, and modern features;
- PMTiles v3 archives containing separate reviewed geometry and time-sensitive label layers when
  `--tiles` is enabled;
- indicator observations that retain their original geographic units;
- static revision-pinned Wiki entities and Wikipedia dossiers when `--enrich` is enabled;
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
export WIKIMEDIA_USER_AGENT='HistoryJoice/0.1 (https://example.org/history-joice/contact)'
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
below that live layer, so the world remains legible when remote context is slow or unavailable; the release's reviewed
Cliopatria PMTiles remain a visibly distinct reconstruction layer above OHM detail and below OHM
labels. The layer control can isolate either source role. A network connection is therefore needed
for the live detail layer, while release artifacts remain static and checksummed.

Build the deterministic schema 1.10 browser pilot and exercise place selection end to end:

```bash
make build-browser-pilot
npm run test:browser
```

The pilot is an immutable, verifier-checked release under `tests/browser/fixtures/data`. It contains
one revision-pinned enriched record and bounded context plus one deliberate missing-enrichment
record, so browser tests cover map selection, search selection, successful joins, and honest
missing-dossier states without live Wikimedia requests or generated prose.

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
retains its upstream source and licence. The default configuration permits non-commercial sources;
removing that constraint requires a complete source-by-source licence audit.
