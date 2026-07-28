# Hand-off: improve the Palimpsest year dossiers

I'm building **Palimpsest** — a "portal of serendipity" for discovering history. A map is the
way in; you scroll to a place, pick a year, and get readable history rather than gazetteer prose.
Repo: `~/Documents/Bhuvan projects/Palimpsest`. Python pipeline + SvelteKit static frontend.
Read `README.md` and `docs/dossier-restatement.md` before changing anything.

I want you to **improve the generated year dossiers**. A previous session built the pipeline and
got them working; they're good but not yet what I want. Details below, including the parts that
were learned the hard way — please don't undo those.

## Run this first to see where things are

```bash
export DEEPSEEK_API_KEY=...           # in .env; provider is DeepSeek, model deepseek-v4-flash
export WIKIMEDIA_USER_AGENT="$(grep WIKIMEDIA_USER_AGENT .env | cut -d= -f2-)"

make check                            # 189 tests, ~82% coverage, must stay green
uv run history-data build-chronicle --year 1543 --output data/chronicle/1543.json
uv run history-data year-dossier --chronicle data/chronicle/1543.json \
  --lenses data/chronicle/1543-lenses.json --output data/chronicle/1543-dossier.json \
  --provider deepseek --model deepseek-v4-flash
```

Existing output to read: `data/chronicle/1543-dossier.json` and `1492-dossier.json`.

## What exists

Three content tiers, each with a different evidence standard:

| Tier | Module | What it does | Gate |
| --- | --- | --- | --- |
| Restatement | `restatement.py` | Rewrites **one** Wikipedia extract in plain English | closed-world check |
| Chronicle | `chronicle.py` | Ingests Wikipedia year pages into dated records | none — verbatim source text |
| Year dossier | `year_dossier.py` | Writes prose for one year from its chronicle | closed-world + citations |

`build-chronicle` pulls the main `1543` article **plus** topic pages (`1543 in science`, `in art`,
`in literature`, `in poetry`) and country pages (`1543 in France`, `in Japan`, …) — currently 10
pages, 196 records, 147 subject article leads (~126k chars) as context. It also fetches Wikidata
sitelink counts as a prominence signal.

`year-dossier` sends all of that to the model and gets back prose + citations, which are then
validated and linked.

## Principles that were hard-won — please keep them

1. **The model writes prose. The pipeline supplies everything else.** Section headings, lenses,
   ordering, hyperlinks, and IDs all come from data. When section `heading` and `lens` were offered
   as model output fields, it filled them with sentences.
2. **Anything tabular is rendered, not narrated.** "Who held power" asked for as prose came back as
   a row of dashes. It's now a structured strip built from records.
3. **The checks enforce the floor; the prompt aims at the ceiling.** The prompt used to be a long
   list of prohibitions that the checks already enforced — it got *shorter and better* by dropping
   them and describing what good writing looks like instead.
4. **More evidence is not less rigour.** Widening the evidence set (subject article leads, extra
   pages) improves quality without weakening any rule — the world stays closed, it's just bigger.
5. **The model never writes a URL.** It writes plain text; links are attached afterwards at
   verified character offsets from titles the pipeline already resolved.
6. **Cite with short labels (`e12`), not IDs.** The model corrupts 16-hex-char identifiers.
7. **Show every record, mark the prominent ones with `*`.** Don't hide records from the model —
   that leaves it choosing among an arbitrary subset. Caps govern what a *paragraph names*, not
   what the model *sees*.
8. **Rejections are retried, not accommodated.** Failures are stochastic. Loosening a check to
   admit a malformed name would admit real errors too.
9. **Rendering the data finds bugs no test does.** Junk records, broken markup and bad links were
   all caught by looking at a rendered page, not by the suite.

## The known, unsolved problem — read this before adding prose

The closed-world check verifies every **name and number** came from the evidence. It **cannot**
verify the **relationship** asserted between them.

A real example that passed every check:

> "Nicolaus Copernicus published his heliocentric model **on his deathbed**"

The records say the book was *printed on 21 March in Nuremberg*, and that he was *presented a copy*
on his deathbed on 24 May. Two true facts fused into a false one. Every name and date was
contained; no phrase was denied; all citations resolved.

**Therefore: more prose = more sentences = more chances to fuse.** Depth from *assembly* is free;
depth from *prose* is not. Please don't just make the sections longer.

Nobody has measured how often this happens. **That measurement would be genuinely valuable**:
sample ~20 generated sections against their cited records and count fusions. Don't ask the model
that wrote the prose to grade it.

## What I want improved, roughly in priority order

1. **A three-layer structure.** Right now the dossier is one layer of sections. I want: an
   **overview** of the year's big themes and trends → then the **big events** in depth → then the
   **timeline / register**. Currently only the last two exist and the first doesn't.
2. **Make the lede assembled rather than written.** It's the most prominent sentence on the page
   and the most likely place for a fusion error. Building it from the top three records by
   sitelink count removes that risk at no cost.
3. **`related_year` cross-links — cheapest high-value item, still unbuilt.** 54 of 96 entries carry
   the other end of a life (born 1543 → died 1616), pointing at 44 other years. It's already parsed
   and stored and nothing uses it. This is what turns a page into a place you get lost in.
4. **Wars as ongoing state.** Battles are captured; the wars they belong to are not. The
   Ethiopian–Adal War ran 1529–1543 — a Wikidata interval query (`P580`/`P582` spanning the year)
   would give "wars in progress", the counterpart to the incumbents idea.
5. **Images.** Commons `P18` for prominent subjects. Big visual gain, no claim risk — but genuine
   per-file licence checking is required; some Commons files are non-commercial or fair-use only,
   and the repo's `RightsReference` / `ReleaseRightsApproval` machinery already models this.
6. **The map join.** ~394 mapped places existed in 1543 and already have plain-English
   restatements. Connecting dossier to map is the two halves of the product becoming one.

## Constraints

- **No human review.** This is a solo project; review at scale is impossible. Dossiers are labelled
  as machine-written and unreviewed, and the disclosure is specific: *"every name and date appears
  in the records this was written from — checked, not trusted. The connections are ours."*
  Mechanical checking substitutes for review. Don't add a review gate; do strengthen the checks.
- **Nothing generated at request time.** The browser never contacts an LLM; everything is
  build-time and shipped as static artifacts. `docs/frontend-contract.md` is binding.
- **Provenance is not optional.** Every source is revision-pinned and checksummed. A dossier bound
  to a chronicle whose source has changed must go stale, not silently drift.
- `make check` must stay green. Tests live in `tests/test_chronicle.py`,
  `tests/test_year_dossier.py`, `tests/test_restatement.py`.

## How I like to work

Show me real output early — I'd rather read a generated dossier than a plan. Verify claims against
the data instead of asserting them; several confident-sounding conclusions in the last session
turned out to be wrong when actually checked. Tell me plainly when something you built doesn't
work, and flag anything you couldn't verify.
