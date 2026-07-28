# Plain-English restatement

## Why this is a separate tier

The [editorial dossier pipeline](editorial-dossier-pipeline.md) governs prose that asserts
something new: a claim synthesised across sources. It demands per-claim citations with character
offsets, byte-exact assertion matching, and a named human who has read every claim. That is the
right standard for synthesis, and it deliberately does not scale.

Restatement is a different act. It takes one revision-pinned source extract and re-serves it in
plain English, history first. It combines nothing and asserts nothing the source did not already
assert. Because the claim is weaker, the gate can be weaker — and mechanical.

|  | Source extract | Restatement | Editorial dossier |
| --- | --- | --- | --- |
| `dossier_kind` | `source_extract` | `restatement` | `generated_editorial` |
| `content_role` | `tertiary_summary` | `source_restatement` | `project_interpretation` |
| Sources combined | one | one | one or more |
| May add a claim | n/a | no | yes, if cited |
| Gate | ingestion validation | closed-world check | per-claim human review |
| Scales to a full corpus | yes | yes | no, by design |

## The closed-world check

`history_pipeline/restatement.py` refuses to publish a restatement unless all of the following
hold against the exact source text:

- every digit run in the output also appears in the source. This rejects invented dates, and it
  also rejects a century or decade derived from a source year, because deriving one is a new claim;
- every capitalised token outside a small function-word list resolves to the source vocabulary,
  allowing singular/plural, possessive, and demonyms built on a stem the source already contains
  ("a Thracian town" for "a town of Thrace"). This rejects invented people, peoples, places,
  dynasties and works. The demonym rule runs one way only: writing "Rome" where the source says
  "Roman" is rejected, because any threshold loose enough to accept it also accepts "Romania";
- a capital at the start of a sentence is read as grammar rather than as a name, but only for
  words the corpus shows English writes in lower case. See the lexicon below;
- no parenthetical unit conversion survives. Two numbers standing for one quantity both exist in
  the source, so the set-based number check cannot tell a correct pair from a recombined one;
  requiring the conversion to be dropped removes the class instead of trying to detect it;
- no phrase from the deny list appears **that the source did not use first**. The list covers
  claims the source never licensed (significance, legacy, destiny) and the stock cadences that
  make generated prose recognisable — but Wikipedia writes "played a pivotal role" and "at the hub
  of" in its own voice, and carrying such a phrase across is restatement, not invention. Only
  register the model introduced counts. A deny list that is not itself closed-world punishes the
  model for being faithful, which is the opposite of what this tier is for;
- the body does not open by deferring — "This", "Located in", "Known for", "One of the";
- the restatement is not longer than the source it restates.

Present-day administrative statistics — population rank, tier, census, transport notes — are
recorded in `validation.retained_furniture` but do **not** block publication. Keeping a population
count makes a restatement worse at its job; it does not make it untrue. Only faithfulness blocks.
Two different questions were sharing one gate, and separating them is what keeps the rejection
signal meaningful.

The check runs at generation, again at release build, and again in `verify-build`. A failure is
never fatal to a build: the restatement is dropped and the reader is shown the source extract. A
false positive therefore costs coverage, never correctness.

The check is a containment proof, not a semantic one. It cannot detect a restatement that uses only
source words to say something the source did not mean. That residual risk is the reason a
restatement is labelled as Palimpsest wording and keeps its source one tap away in the reader,
and the reason this tier may not be used to combine sources.

The number rule is set membership, not pairing: it proves every number came from the source, not
that each was kept beside the right thing. This was found in a live run, where a source reading
"90 kilometres (56 mi) west of Byzantium" came back as "90 kilometres (22 mi)" — and passed,
because `22` appeared elsewhere in the same extract as part of a different measurement. Detecting
recombination in general is not possible with a containment check, since faithful restatement
reorders text freely. The measurement rules above close the observed vector by removing the
material rather than policing it; the residual risk is any other pair of numbers the source binds
together. Prefer deleting quantitative furniture over restating it.

## The common-word lexicon

A capital only signals a name when the writer chose it. English forces one at the start of every
sentence, so "Construction began in 1892" was being read as a claim about somebody called
Construction. Exempting every sentence-initial word would reopen the hole the name check exists to
close, so the exemption is limited to words that are demonstrably common nouns.

`history_pipeline/common-words.txt` holds those words. It is derived from the dossier corpus by
counting only **lower-case** occurrences and keeping words that appear in at least 50 documents. A
proper noun is essentially never written lower case in running prose, which is what separates the
two classes: `construction`, `settlement`, `fortress` and `notable` are in the list, while
`Gandharan`, `Erechtheion`, `Mauryan`, `Thracian` and `Byzantium` are not, at any threshold tested.

The list is checked in rather than computed at validation time, so the check stays hermetic and a
release does not depend on whichever corpus happens to be on disk. Regenerate it with:

```bash
uv run history-data build-lexicon --dossiers data/staged/canonical/dossiers.ndjson
```

The exemption applies at sentence-initial position only. The same word used mid-sentence was
capitalised by choice and is still checked, so "opposite the Gulf and Taxila" is still rejected
when the source does not mention a gulf.

## Timeline invariants

Each entry carries `year_text` exactly as the source wrote it, and `sort_year` as a signed number.
Two rules apply:

- an era marker and its sign must agree. `"77 BCE"` with `sort_year: 77` is rejected, because a
  sign slip moves a record a full era on the reader's timeline;
- entries are sorted into chronological order rather than rejected for arriving out of order.
  Models list events as the source narrates them, and presentation order is not an evidence claim.
  The truth of each `sort_year` is guarded by the era-sign rule and the number check instead.

## Binding to one revision

`DossierRestatement.source_content_checksum_sha256` covers the exact source extract text. When an
upstream revision changes, that hash stops matching and:

- `build_artifacts` drops the restatement from the release;
- `verify-build` rejects any restatement whose source is absent or has changed;
- `restate-dossiers` sees the dossier as pending again and regenerates it.

Stale prose can therefore never be published against a revision it was not derived from.

## Providers

Generation is an explicit editorial action. It requires an API key and a named model, and no code
under `src/` contains an LLM client or credential.

| Provider | Endpoint | Schema enforcement | Key |
| --- | --- | --- | --- |
| `openai` | `/v1/responses` | strict `json_schema` | `OPENAI_API_KEY` |
| `deepseek` | `/chat/completions` | none — JSON mode only | `DEEPSEEK_API_KEY` |

DeepSeek exposes no Responses API and rejects `response_format: json_schema` outright, so it
receives JSON mode with the output contract restated inside the prompt. That is acceptable here
only because the closed-world check is the real gate: a provider that cannot promise a schema
still cannot get unsupported prose into a release, because nothing is trusted until it has passed
the same Pydantic contract and the same containment checks. `restate-dossiers` prints a warning
when the selected provider cannot enforce a schema.

DeepSeek's models reason before answering and bill those tokens against the output budget, which
buys nothing for a mechanical rewriting task, so the profile sends `thinking: {type: disabled}`.
Adding a provider means adding a `ProviderProfile`, not branching the caller.

```bash
uv run history-data restate-dossiers \
  --dossiers data/staged/canonical/dossiers.ndjson \
  --output data/editorial/restatements.ndjson \
  --provider deepseek \
  --model deepseek-v4-flash \
  --limit 25
```

The run is resumable. It reads the output file first, skips every dossier already restated from the
same source checksum, and appends as it goes, so an interrupted run costs only its current record.
Sources shorter than `--minimum-chars` (200 by default) are skipped rather than padded.

Saved output can be validated without contacting a provider, which is how the deterministic
fixtures are built:

```bash
uv run history-data restate-ingest \
  --dossiers data/staged/canonical/dossiers.ndjson \
  --dossier-id wikipedia:en:100048 \
  --model-output data/editorial/restatement-pilot/model-output-cambrai.json \
  --output data/editorial/restatement-pilot/restatements.ndjson \
  --model fixture:handwritten-gold-v1 \
  --generated-at 2026-07-25T09:00:00Z
```

Re-run every check against the current sources:

```bash
uv run history-data restate-verify \
  --dossiers data/staged/canonical/dossiers.ndjson \
  --restatements data/editorial/restatements.ndjson
```

## The prompt

`prompts/dossier-restate-v1.txt` carries the contract and three worked examples taken from real
extracts: one long source, one short source, and one that must be declined. The examples do most of
the work — a hand-written gold restatement constrains voice far better than adjectives in an
instruction. Extend them rather than adding more adjectives.

Declining is a first-class outcome. A source with no historical content — a present-day
administrative division, a statistics-only stub — returns `unsuitable`, and the reader sees the
original extract.

## Publication and the reader

Restatements ship as `content/restatements/{shard}.json`, sharded by the dossier ID they restate,
so a reader that has resolved a dossier fetches its restatement without a second index lookup. The
collection is optional; a release built without it is complete, not degraded.

The reader labels the tier honestly, names the model, states that no fact was added, and keeps the
original extract behind a disclosure. Prose is generated once per source revision and cached, not
per selected year: the year-awareness in the sidebar comes from the structured `timeline`, which
the reader re-anchors on every slider move without refetching anything.

## Measured behaviour

The same 60 uncontaminated records through `deepseek-v4-flash`, measured after each correction:

| | Restated | Declined `unsuitable` | Rejected | Failed |
| --- | --- | --- | --- | --- |
| Initial rules | 19 | 33 | 8 | 0 |
| Deny list made closed-world | 28 | 25 | 7 | 0 |
| Sentence-initial lexicon | **36** | 24 | **0** | 0 |

The decline rate is a property of the corpus, not a defect. Most enriched records are modern
settlements and physical geography whose Wikipedia lead carries no history at all; declining them
is the correct answer and the reader sees the source extract.

A zero rejection rate is not by itself evidence that the check is sound — a check that accepted
everything would also score zero. What demonstrates it still bites is the adversarial suite in
`tests/test_restatement.py`: invented dates, derived centuries, invented peoples, recombined unit
conversions, era-sign slips, and introduced register are each still rejected, and a name is still
checked in every position except the start of a sentence.

## What the rejections were

This matters more than the rate, and it was got wrong once already. A rejection here is **not**
evidence that the model invented something. Across 180 measured records, every rejection traced
back to its source turned out to be one of:

- **the deny list not being closed-world** — the source itself said "at the hub of numerous
  highways" (Troyes) or "played a pivotal role in the fall of the Assyrian Empire" (Medes), and
  the model carried the phrase across faithfully. Numbers and names were checked against the
  source but phrases were not, so the more faithful the restatement, the likelier it was to be
  rejected. Fixed;
- **sentence-initial common nouns** — "Construction began in…", "Notable buildings include…".
  Fixed by the lexicon above;
- **word-form variants of the same entity** — `Erechtheion` for a source reading `Erechtheum`,
  `Mauryas` for `Mauryan`, `Rome` for `Roman`. Deviations from "copy names exactly", but not
  inventions. These now pass or are declined upstream.

At most one case in 180 looked like a genuinely added fact, and none was confirmed. Read a
rejection as "the checker could not prove this stayed inside the source", never as "the model
lied". Quoting the rate without that distinction overstates the risk considerably.
