# Build-time editorial dossier pipeline

## Boundary and trust model

An LLM may arrange approved evidence into draft prose. It is never the source of a historical
claim. The only allowed historical context is an `ApprovedEvidenceBundle` built from the schema
1.10 entity, feature and `EvidenceAssertion` contracts. Network retrieval, model memory and
uncited background are outside that boundary.

Generation runs only through the Python publishing CLI. Nothing under `src/` imports an LLM client,
contains an API credential or makes a generation request. Automated tests ingest saved output or
use an in-memory HTTP transport, so they never need network access or an API key.

Generated prose and its editorial records live under `data/editorial/`, separate from the
MIT-licensed application and pipeline source. Moving a reviewed dossier into a public data release
is an editorial publishing decision, not a code deployment side effect.

## Contracts

The checked-in JSON schemas are:

- `ApprovedEvidenceBundle`: revision-pinned sources, exact source-field text, JSON Pointer field
  paths and approved character ranges, plus copies of the schema 1.10 assertions;
- `DossierDraftContent`: the strict payload a model may return;
- `DossierDraft`: the payload plus prompt version and checksum, model identifier, evidence-bundle
  checksum, output checksum, generation timestamp and optional provider response ID;
- `PublishedEditorialDossier`: a human-approved, immutable editorial data record with evidence
  sources and a separate licence for the generated prose.

Every draft claim names all of its entity IDs, an exact historical interval and precision,
supporting assertion IDs, and one or more citations. A citation contains the source ID, approved
passage ID, full-document character offsets and exact quoted text.

Validation fails the operation unless all of the following hold:

- entity, feature and assertion IDs resolve to the configured curated records;
- the bundled assertion is byte-for-byte equivalent to the reviewed assertion;
- the claim interval and precision exactly match every supporting assertion;
- the claim's entity set exactly matches the entities in those assertions;
- every supporting assertion is covered by a passage from one of its own sources;
- every citation lies within its approved passage and its quoted text matches the source document;
- every pilot passage and source revision resolves through its recorded JSON Pointer to the exact
  value in the checksummed source snapshot;
- source revision, snapshot checksum, licence and attribution remain unchanged;
- bundle and output hashes, and the derived draft ID, recompute exactly.

This deterministic layer establishes traceability and rejects structurally unsupported claims. It
cannot decide whether arbitrary prose is a faithful semantic paraphrase. A named human reviewer
must make that determination before publication, and must review every claim. This limitation is
why successful machine validation never promotes a draft automatically.

## Editorial states

| State | Meaning | Can publish? |
| --- | --- | --- |
| `machine_drafted` | Schema-valid output has passed deterministic evidence validation. | No |
| `human_reviewed` | A named reviewer has checked every claim and recorded notes and a timestamp. | Yes |
| `rejected` | Editorial staff retained the rejection reason; the prose is not publishable. | No |
| `published` | A reviewed draft was converted into a content-addressed editorial dossier. | Already published |

`no_evidence` is valid only for an empty approved bundle. `conflicting_evidence` must identify at
least two genuinely contradictory assertions with citations covering every side. Neither terminal
result can be promoted to human-reviewed or published prose.

Publishing derives the dossier ID from the reviewed content and publication metadata. The CLI
opens the final JSON file in exclusive-create mode and refuses to overwrite it. Correcting prose,
review metadata, evidence or licensing therefore creates a different immutable dossier.

## Copernicus pilot

`data/editorial/copernicus-1543/` contains:

- `evidence-bundle.json`, retaining Library of Congress item `92516339`, its source revision,
  PDM licence, attribution and snapshot checksum, with exact values from `/item/title`,
  `/item/creators/0/title`, `/item/notes/0/note` and `/item/created_published`;
- `model-output.json`, a deterministic schema-constrained output fixture;
- `draft.json`, a validated `machine_drafted` record with no review metadata.

The build reads `data/raw/loc_copernicus/catalog-record.json`, verifies its SHA-256 checksum, pins
the provider revision from `/item/modified`, and rejects any extracted passage that differs from
its recorded source field. Assertion rationales remain editorial metadata and are never represented
as verbatim Library of Congress text. The ignored raw snapshot must be restored from the private
snapshot store before rebuilding the pilot. Run:

```bash
make build-dossier-pilot
```

The command recomputes only the evidence bundle and machine draft. It never creates review
metadata, applies an editorial licence or publishes prose. Tests exercise review, rejection and
publication transitions with an explicitly named simulated reviewer and temporary output paths;
those records are not fixtures and cannot enter a production release.

## Real generation and offline ingestion

Real generation uses the OpenAI Responses API with strict Structured Outputs, `store: false`, no
tools, and the complete canonical evidence bundle in the input. The model is deliberately required
on the command line; changing it is recorded in the draft rather than hidden behind an unversioned
default. The request removes only JSON Schema keywords the provider does not support; the returned
payload is then validated against the complete checked-in Pydantic/JSON Schema contract before it
can become a machine draft.

```bash
uv run history-data dossier-generate \
  --bundle data/editorial/copernicus-1543/evidence-bundle.json \
  --prompt prompts/dossier-draft-v1.txt \
  --prompt-version dossier-draft-v1 \
  --model MODEL_ID \
  --output data/editorial/copernicus-1543/new-draft.json
```

This command alone requires an `OPENAI_API_KEY` (or the explicitly named `--api-key-env`
variable). The visitor application, deterministic pilot, review, publication and test suite do
not.

Output obtained from an approved provider or an offline fixture can instead be ingested:

```bash
uv run history-data dossier-ingest \
  --bundle data/editorial/copernicus-1543/evidence-bundle.json \
  --model-output data/editorial/copernicus-1543/model-output.json \
  --prompt prompts/dossier-draft-v1.txt \
  --prompt-version dossier-draft-v1 \
  --model fixture:deterministic-dossier-v1 \
  --generated-at 2026-07-23T07:05:00Z \
  --output /tmp/copernicus-draft.json
```

Review is explicit:

```bash
uv run history-data dossier-review \
  --bundle data/editorial/copernicus-1543/evidence-bundle.json \
  --draft /tmp/copernicus-draft.json \
  --reviewed-by "EDITOR NAME" \
  --reviewed-at 2026-07-23T07:30:00Z \
  --notes "Every claim checked against its cited passage." \
  --output /tmp/copernicus-reviewed.json
```

An editor can instead retain a closed rejection with `dossier-reject`; the command requires
`--rejected-by`, `--rejected-at` and `--reason` and does not modify the machine draft.

Publication requires the generated prose's own licence and attribution:

```bash
uv run history-data dossier-publish \
  --bundle data/editorial/copernicus-1543/evidence-bundle.json \
  --reviewed-draft /tmp/copernicus-reviewed.json \
  --editorial-license-id CC-BY-4.0 \
  --editorial-attribution "History Joice editorial team" \
  --published-at 2026-07-23T08:00:00Z \
  --output-dir /tmp/published-dossiers
```

Published editorial dossiers are not yet automatically added to the global History Joice release
artifacts. A future release-integration step must preserve the separate dossier kind, evidence and
editorial licensing fields and pass the normal immutable-release verifier; until then, publication
creates only the explicitly requested editorial dossier file.

## Licensing and attribution workflow

Upstream evidence is never relicensed. Each evidence document preserves its `SourceReference`,
including record and revision IDs, URL, retrieval time, checksum, licence and citation. Exact
passages remain associated with that source.

Generated editorial prose has a separate `editorial_license_id` and
`editorial_attribution`. Before public publication, an editor must confirm that History Joice has
the right to apply that licence, that any quoted material is permitted, and that provider terms
allow the intended use. The machine-only pilot applies no editorial licence and publishes nothing;
the Library of Congress source remains `PDM-1.0`.

Source extracts and generated dossiers also remain machine-distinguishable:
`HistoricalDossier.dossier_kind` is `source_extract` (including existing Wikipedia records), while
a `PublishedEditorialDossier` is `generated_editorial` with
`content_role: project_interpretation`. A generated dossier's evidence sources support its claims;
the model identifier is provenance, never a historical citation.
