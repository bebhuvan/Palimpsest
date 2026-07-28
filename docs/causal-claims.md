# Causal claims contract

Palimpsest publishes causal explanations as attributed historiographical arguments, not facts
derived from Wikidata, Wikipedia links, temporal sequence or spatial proximity.

## Public graph

The build materializes three immutable collections:

```text
selected feature
  -> entity ID
  -> incoming and outgoing causal claim IDs
  -> claim and curated path shards
  -> cause/effect entities and cited sources
```

`causal/index.json` declares SHA-256, UTF-8, two-hex-prefix sharding and exact record counts. Claims,
entity adjacency and paths live under `causal/claims`, `causal/entities` and `causal/paths`. The
manifest declares every shard's byte length and checksum. The verifier reconstructs the graph and
checks that adjacency is complete in both directions.

## Claim semantics

Permitted relationships are `caused`, `contributed_to`, `enabled`, `constrained`, `accelerated`,
`triggered`, `response_to` and `feedback_with`. Prefer a qualified relationship over `caused`.
Every claim requires:

- one or more cause and effect entity IDs already present in the release;
- separate, no-year-zero temporal anchors with precision rationales;
- a controlled mechanism type and multilingual human-authored explanation;
- an evidence basis containing scholarship, perspective and confidence rationale;
- one or more source records with explicit licence review notes;
- an accountable author and review status.

Wikipedia and Wikidata may help discover candidate entities and literature, but neither is accepted
as the sole scholarly basis of a causal claim. No AI-generated historical explanation is admitted
as a substitute for cited human scholarship.

## Review invariants

- `verified` requires a reviewer different from the author.
- `caused` additionally requires two distinct sources.
- A gap greater than 100 years requires `long_range_synthesis: true`, two or more supporting claims,
  and a directed supporting route from the stated cause entities to the effect entities.
- Ordered path claims must connect: each claim's effect must be a cause of the next claim.
- Self-causation is rejected except for an explicitly reciprocal `feedback_with` process.
- Missing claims, paths, release entities and source licence review are fatal build errors.
- Rejected drafts remain private and are not valid release inputs.

## Editorial input

The configured input is `data/curation/causal-claims.yml`. It is included in the deterministic build
checksum. Generated NDJSON copies under `data/staged/canonical/` are inspection artifacts and must
not be edited. The checked-in file starts empty because the infrastructure must not manufacture a
demonstration claim that could be mistaken for reviewed history.

The visitor UI loads this graph only after a map selection and presents it as “Interpretive
pathways,” including its sources, authorship, perspective and uncertainty. Empty results mean that
this release contains no reviewed claim for the entity, not that the event had no causes or effects.
