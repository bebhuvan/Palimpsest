# The year dossier

A year dossier answers "what was happening" for one year, from that year's Wikipedia coverage. It
is generated, disclosed and unreviewed, and it is built so that most of what a reader gets was
never written by anything.

## Three layers, and only the middle one is composed

| Layer | What it is | Where it comes from |
| --- | --- | --- |
| Lede | The year's three most-written-about records, in the sources' own words | assembled |
| Overview | Counts, themes, wars in progress, who held office; one paragraph naming the threads | assembled + one written paragraph |
| Anchors | Six to eight happenings given room: paragraph, records, quotation, picture, cross-links | one written paragraph each; everything around it assembled |
| Sweep | One paragraph per lens, moving fast across the rest | written |
| Made | Books, poems, paintings the year records, by kind | assembled + a gloss each |
| People | Who was born and who died, with a face and a sentence | assembled + a gloss each |
| Register | Every event, dated, attributed, linked, with its other wordings | assembled |
| Doors | Every other year this one names, and the lives that reach them | assembled |

The split is the whole design, and it follows from the one failure this tier cannot detect.

## Why the split

The containment check proves that every name and number in the prose came from the evidence. It
cannot prove the *relationship* asserted between them. Two true facts can be joined into a false
third and pass everything:

> "Nicolaus Copernicus published his heliocentric model **on his deathbed**"

The records say the book was printed on 21 March in Nuremberg and that he was presented a copy on
his deathbed on 24 May. Every name contained, every citation resolving, and the sentence is wrong.
Call it a **fusion**.

Nothing mechanical detects a fusion; if it could, the check would already reject it. What can be
controlled is how many chances there are to commit one, and that is a product of two things: how
many sentences get written, and how many facts are in front of the writer when it writes each one.

So depth comes from assembly wherever assembly can carry it. The register is exhaustive because
exhaustiveness costs nothing there. The lede is assembled because the first sentence on the page
is the one a reader is least able to check. The incumbent rows and the war list are rendered, not
narrated. What is left for prose is the part that genuinely needs a writer.

## The closed world is per block, not per year

Every block — the overview, each anchor, each section — is checked twice:

1. against the whole year, which catches anything invented outright;
2. against **its own evidence alone**, which catches a paragraph borrowing a name from a record it
   is not about.

The second check is the new one and it is the one that bites. A section used to be checked against
the whole chronicle, so any name from any of a hundred and ninety-three records could legitimately
appear in any sentence. Now the religion section cannot reach for a name that belongs to the
science section.

This still does not detect fusion. It reduces the set of facts that *can* be fused, which is the
only lever available without a reader.

### What a block's evidence is

Scoping a block to its own records exactly turned out to be too tight to write from, and a block
too thin to write from does not make the prose safer — it makes the rejection systematic. So a
block's evidence is:

- its own records, dates rendered back out;
- the leads of every article those records link to;
- the year's **other records about the same subjects**, by Wikidata identifier or by wikilink.

That last rule is the source's own statement that two entries concern one thing. Without it, the
religion section of 1492 held the papal conclave beginning on 8 August and not the election of
Alexander VI three days later, which the year files under another lens; five attempts running were
rejected for finishing the conclave. Without it, Columbus's voyage split across three anchors —
the crossing, the landfall on Hispaniola, the wreck of the *Santa María* — and each reached for the
other two.

## Anchors

An anchor is one happening given a section of its own. It is chosen by how many language editions
cover its subject, one subject at most, and it must clear two gates:

- it needs an article behind it, or a paragraph has nothing to add to the register;
- its records must amount to at least 200 characters. **This gate came out of the audit below.**
  Both confirmed fusions in the first audited dossier were in the same anchor: the one whose
  records were two short lines and whose background was a full biography. With little to say from
  the record and a great deal available from the article, the writing fills the gap from the
  article and joins the two. The threshold started at 120 and was raised after a one-record anchor
  on the Index Librorum Prohibitorum spent four attempts trying to say the Index banned *De
  revolutionibus* — same year, and not true until 1616. The check refused it every time, which is
  the check working; the anchor should not have existed.

A bibliography row — an author, a dash and a title — is refused as an anchor even when it ranks
high, because the record says nothing about the year and the article says everything about a life.

Around the paragraph, all assembled: the heading is the subject's own title, the records are
listed verbatim, a quotation comes from whichever background article the record actually names,
and a Commons picture appears if one cleared the licence policy.

## People and works

Births and deaths were a prose section once. Asked for as paragraphs they came back as *"Other
births included Charles III, Duke of Lorraine (18 February), Domenico Fontana (1543), Federico
Zuccari (1543)"* — a list with commas standing in for sentences, which is what the register
already is and does better. So is a catalogue of books and paintings: the author-dash-title form
that is ranked last everywhere else in this dossier, because it reads badly in a paragraph, is
exactly right as a row.

Both are rendered now. Each person carries a face where a Commons file cleared the licence, the
date, the source's own description, and **the year at the other end of their life as a link** —
born 1543, died 1616, one tap away.

### The gloss, and the line it does not cross

The prominent dozen carry one restated sentence saying who they were, and each book or painting
that has an article of its own carries one saying what it is. This is the narrowest closed world
in the artifact: **one revision-pinned article lead, one sentence, checked against that and
nothing else.** It is a restatement rather than a synthesis, which is the tier whose failure rate
has actually been measured, and that is the whole reason a gloss can be offered at all.

What it says is what somebody did and when. What it does not say is why it mattered.

That distinction needs one rule that breaks the pattern of every other check here. Everywhere else
the deny list is closed-world: a phrase is refused only when the model introduced it, because
carrying the source's own wording across is restatement, not invention. **For a gloss, significance
language is refused absolutely, even when the article uses it.** Wikipedia is free to say Hans
Holbein is considered one of the greatest portraitists of the sixteenth century — it said exactly
that, and it passed containment. This tier has no reader who could stand behind repeating it, so
`_DENIED_GLOSS_PHRASES` refuses it and the correction tells the model to say what was done instead.

A gloss also has its repeated subject trimmed: the name is already set in bold directly above it,
and the instruction not to repeat it is followed about half the time. Removing a prefix is safe in
a way that rewriting one is not — it only ever deletes.

### What is not there

A work gets no picture. The subject of "Titian — Ecce Homo" resolves to Titian, so the only image
available is a portrait of the painter, and a portrait of Titian captioned *Ecce Homo* is a caption
that lies. Showing the work needs the work's own Wikidata item, which the chronicle does not carry
yet.

Most work records cannot be glossed either, for a plain data reason: a year article names a
painting without linking it. 1543 has fourteen works and two of them have an article of their own.
1492 has none at all, because its art and literature companion pages do not exist — a thin year
reads as a short dossier, which is the intended behaviour rather than a failure.

## Quotation

A quotation asserts nothing beyond having been said, so it is the one way to add length at no
risk. Two things disqualify a passage:

- the definitional opener. The first sentence of a Wikipedia lead is a name, a bracketed
  pronunciation, a pair of life dates and a job title, and it looks broken beside prose;
- irrelevance. A lead that never mentions the year and never mentions anything the records link to
  is about the subject in general — "Hungary is a landlocked country in Central Europe" is true,
  sourced, and no use to a reader standing in 1543. Present-day administrative furniture is
  refused the same way.

An anchor with no quotation is not a broken anchor.

## Pictures

Commons hosting is not a licence. Every candidate is a `P18` on the subject's Wikidata item, and
each file is cleared from its own `extmetadata`: a recognised licence, no explicit restriction, no
non-free marker. The licence is then judged by `config/pipeline.yml`'s own `license_policy`, the
same `enforce_license` that governs every other source in the build — a picture is not a separate
rights regime because it is a picture. Jurisdiction ports (`cc-by-sa-3.0-de`) are identified as
the licence they are and then judged like any other.

Refusals are recorded with their reason, so a thin picture set reads as a licensing outcome rather
than as missing coverage. In the 1492 run three files were refused: two `CC-BY-SA-3.0` and one
`CC-BY-2.5`, none of which the open-core profile allows.

## Wars in progress

A year article records battles. It does not record that a war was under way, and the second is the
reading that explains the first. `build-year-context` asks Wikidata for items that are wars whose
`P580`/`P582` interval spans the year.

Intervals longer than 150 years are dropped. Wikidata dates "Anglo-French Wars" from 1109 to 1815,
which is a true statement about a label and a false one about a war in progress; shown beside the
Ethiopian–Adal War it would teach a reader to distrust the strip. The span filter is the honest way
to say the two cannot be told apart mechanically: it drops the class rather than ranking within it.

A war that began or ended in the selected year is flagged. "The Ethiopian–Adal War ended this year"
is the single best door out of a page that this artifact produces.

## Doors: `related_year`

Every birth record carries the year of the death and every death record the year of the birth. Both
were already parsed and stored and nothing used them. 1543 names 44 other years across 54 records;
1492 names 32. Following one leads somewhere the reader had no reason to expect and did not choose,
which is what a portal of serendipity is for.

## Retries

A rejection is retried, never accommodated. Three things make the retry converge instead of
resampling:

- **the check's own output goes back to the model.** It only ever says *remove*, the evidence is
  unchanged, and every check runs again on whatever comes back. Feeding a check's output back is
  not the same as relaxing it;
- **the previous answer goes back with it**, so the repair is an edit rather than a rewrite, at a
  low temperature. The first attempt keeps its range;
- **blocks are named in the model's own vocabulary.** The report names an anchor by the identifier
  the pipeline substituted afterwards, which the model has never seen. A 1492 run burned five
  attempts on one number because every correction addressed a block by a name that did not exist
  for the reader of the correction.

For an unsupported name the note also carries the source's spelling, found by edit distance. The
commonest rejection is not an invention but a word-form variant — the source writes "Chantz" and
the model writes "Chants" — and told only to remove the word, the model removed the sentence and
wrote the same spelling again on the next attempt.

### The last resort

When the attempts are exhausted and the only faults left are unsupported names or numbers, the
offending **sentences are deleted** and every check is run again on what remains.

This is not a relaxation, and it is worth being precise about why. Deletion can only shrink what
the dossier claims; nothing is admitted that would not have been admitted before; the checks are
unchanged. What it buys is coverage — without it, one archaic spelling in one clause costs a
reader the whole year, and at this scale there is nobody to intervene. It refuses rather than
mangles: a block that would fall below two sentences is left alone and the year fails, because a
paragraph cut to its last line can end up resting on an antecedent that went with the deletion.
Anything removed is recorded in `removed_sentences`.

## Measured fusion rate

This is the measurement the previous hand-off asked for. It was made by reading generated
sentences against the evidence their block was allowed to use, using `scripts/fusion-audit.py`,
which lays one out beside the other. **The grading was done by a different model from the one that
wrote the prose** — which is the stated requirement, and is still weaker than an independent human
reader. Read the numbers as an order of magnitude.

About 100 sentences were read across two generated 1543 dossiers and the anchors of a 1492 dossier.

| | Confirmed fusions | Unlicensed characterisations |
| --- | --- | --- |
| 1543, first audited run (70 sentences) | 2 | 3 |
| 1543, after the anchor-substance gate (30 sentences) | 2 | 1 |
| 1492 anchors and overview (~25 sentences) | 0 confirmed | not exhaustively verified |

**Roughly four in a hundred sentences**, then, with everything below as caveat.

The confirmed fusions were:

- *"Luther also published Vom Schem Hamphoras, a further anti-Jewish work."* The evidence has the
  bare title, and separately says that two of his later works were antisemitic. Joining them is a
  claim the evidence does not make. (It is also true, which is exactly why this class is hard.)
- *"…writing that Christians 'are at fault in not slaying them.'"* The source says "He **also seems
  to advocate** murder of Jews, writing '[W]e are at fault…'". The hedge is dropped and "we" is
  re-attributed to "Christians".
- *"After a 16-day bombardment, Nice fell on 22 August."* The evidence says the siege lasted 16
  days and, separately, that the city fell after a long bombardment. The siege's length is
  attached to the bombardment.
- The overview reporting the deathbed presentation of *De revolutionibus* flatly, where the record
  it came from says "according to legend".

Two findings matter more than the rate.

**The hedge is the thing that gets lost.** Three of the four are a dropped qualification rather
than an invented connection. That is a narrower target than fusion in general and might be
mechanically detectable — a check that required a hedge in the evidence to survive into any
sentence using the same names would have caught two of these. It is not built.

**Two-thirds of what looked like a fusion was not one.** Four sentences that read as unsupported
turned out to be supported once the linked article leads were actually read: "the first iron
cannon in England", "leading to eight years of conflict known as the Rough Wooing", "ending the
Ethiopian–Adal War", and the purpose of the Secret Bond are all in the background, verbatim.
Anybody quoting a fusion rate from a quick read without checking the evidence will overstate it
by a factor of three, which is the same mistake the restatement tier's rejection analysis records.

### What could not be verified

- 1492 was spot-checked rather than read exhaustively; its number is a floor, not a rate.
- Whether the rate is stable across years, models or providers. Two years and one model is not a
  sample.
- Whether the anchor-substance gate actually reduced the rate. It removed the anchor that produced
  both fusions in the first run, which is suggestive and is not evidence — the second run produced
  two of its own elsewhere.

## Commands

```bash
uv run history-data build-chronicle --year 1543 --output data/chronicle/1543.json
uv run history-data build-year-context --year 1543 \
  --chronicle data/chronicle/1543.json --output data/chronicle/1543-context.json
uv run history-data year-dossier --chronicle data/chronicle/1543.json \
  --lenses data/chronicle/1543-lenses.json --context data/chronicle/1543-context.json \
  --output data/chronicle/1543-dossier.json --provider deepseek --model deepseek-v4-flash
```

Then look at it, because rendering the data finds bugs no test does:

```bash
uv run python scripts/render-year-dossier.py \
  --dossier data/chronicle/1543-dossier.json --output build/1543.html
uv run python scripts/fusion-audit.py --year 1543 --output build/audit-1543.md
```

`scripts/year-dossier-probe.py` makes one request and keeps the prompt, the payload, the raw
output and the validation report, so a systematic rejection can be told from a stochastic one by
looking at it rather than by guessing.

## Publication

A build picks up whatever year dossiers are ready. `year_dossiers_path` in `config/pipeline.yml`
names the directory; an absent or empty one is not an error, and a release that carries no year
pages is complete rather than degraded.

- `years/{year}.json` — one file per year, addressed by the year. No shard lookup: the key is a
  small integer the reader already has, because it came from the time slider;
- `years/index.json` — every year the release carries, with enough per year to tell a live
  cross-link from a dead one without fetching anything.

Two things are re-proved at publication rather than trusted from generation.

**Every picture is cleared again** against the release's own `license_policy`, by the same
`enforce_license` that governs every other source in the build. It was cleared once when it was
fetched, but a release is the thing that redistributes it, and a check that only ran at fetch time
cannot speak for an artifact assembled months later from a file on disk.

**`verify-build` re-proves the year contract from the release alone**, without the config: the
index lists exactly the year files present, each file validates and still matches its own
checksum, each is labelled `machine_generated` with an `assembled` lede, the index agrees with
each dossier about which years it reaches, and every picture carries a licence the pipeline
recognises and an attribution. A year file edited after the build fails here rather than in a
browser.

The frontend side of this — what to fetch, how to slice prose links, and why the assembled parts
must not carry the generated parts' disclosure — is in the
[frontend data contract](frontend-contract.md).

## The disclosure

> This dossier was written by a machine and has not been read by a person. Every name and date in
> the prose appears in the records it was written from — checked, not trusted. The connections are
> ours.

The assembled layers are not covered by that sentence and should not be: the lede, the register,
the incumbent rows, the war list and the cross-links are the sources' own words and numbers,
rearranged. `lede_kind` records that the lede was assembled so a reader's warning can be accurate
rather than uniform. The content checksum covers generated prose only.
