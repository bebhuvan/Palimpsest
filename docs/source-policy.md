# Source and editorial policy

## Admission gate

A source adapter is not permission to publish a source. Enabled sources must have:

1. an explicit compatible licence;
2. a citation and publisher;
3. a documented historical/spatial meaning;
4. confidence defaults with a rationale;
5. an immutable raw snapshot and checksum in release builds.
6. one or more explicit `roles` and a commercial-redistribution decision.
7. an `open_core` or `research_only` distribution tier.

Enabled source URLs must identify a numbered release or immutable object where the publisher
provides one. A moving `main` branch, `latest` download, or live API response is acceptable only as
an acquisition endpoint: the exact response must be snapshotted, and release configuration should
be advanced deliberately after review.

Unknown and proprietary licences are rejected. Dataset-level licences do not override per-record
licence tags. OpenHistoricalMap and Open Context therefore require licence-aware curated imports,
not indiscriminate copying.

The default open-core policy permits only reviewed, commercially redistributable sources. A
research overlay may permit non-commercial sources, but its build is a separate distribution
profile and cannot be promoted as an open-core release. Conditional redistribution requires its
conditions to be recorded in configuration.

`source-registry.json` publishes these decisions for enabled and gated sources: role, licence
review, commercial status, release policy, scope, limitations, version and expected checksum. An
entry records policy; `enabled: true` plus a matching manifest source proves actual ingestion.

## Source roles

- Cliopatria supplies global breadth and provisional reconstructed polity extents.
- CShapes may supersede global geometry for its documented modern period after its non-commercial
  and share-alike obligations are implemented in distribution.
- Pleiades and specialist gazetteers supply places and scholarly identifiers, not general polity
  borders.
- PeriodO supplies competing attributed definitions of named periods. It never supplies a
  universal chronology or geometry.
- Open Context supplies curated archaeological evidence. Sensitive and human-remains-related
  records are excluded or spatially generalized.
- Wikidata links entities; Wikipedia supplies introductory reading. Neither establishes geometry.
- Wikidata coordinates may support coarse regional discovery only when the entity also has a usable
  date. They never replace, repair or increase the precision of reviewed historical geometry.
- Wikipedia and other encyclopedias are tertiary summaries. Wikisource/archival transcriptions are
  primary sources, while project-authored interpretations are separate records. A link between
  these roles does not make them interchangeable.
- Library of Congress item records are archival catalog metadata. A catalog description can anchor
  a document and its provenance, but it is not the document's full text and does not independently
  establish every historical interpretation.
- Japan MLIT multilingual site pages are tertiary discovery sources. Received traditions derived
  from later chronicles must retain that source distance and remain provisional until reconciled
  with appropriate scholarship and, where available, contemporary evidence.
- Causal claims require at least one scholarly source with an explicit per-source licence review.
  Primary sources may support a claim but cannot replace scholarship that makes and contextualizes
  the causal argument. Wikipedia and Wikidata are discovery aids, not sufficient causal evidence.
- Our World in Data supplies contextual indicators. Values using present-day geographic units must
  not be painted onto incompatible historical polities.
- The Seshat API supplies selected polity-level scholarly assertions joined to Cliopatria only by
  exact `SeshatID`. Its numeric ranges, coded values, intervals, uncertainty, disputes,
  explanations and references must survive normalization. Generated plain-English restatements
  can simplify one explanation but cannot alter or replace its structured value.
- OpenHistoricalMap supplies contributor-built local historical detail. Per-feature `license=*` tags must survive
  normalization.
- World Historical Gazetteer is a reconciliation and linked-place source, not a global boundary
  authority. Most API endpoints require a token and its platform licence is non-commercial;
  ingest only selected datasets after checking their individual rights.
- Getty AAT/TGN/ULAN reconciliation produces reviewable authority candidates, not automatic
  identity claims. Accepted matches still retain score, editorial status, record ID and lineage.
- IIIF/Allmaps georeferences describe transformations of scanned maps. Catalog metadata,
  georeference annotations and image pixels have separate rights gates. A permitted manifest does
  not imply that its image may be copied.

## Geometry changes

Raw source geometry is never overwritten. Invalid geometry is rejected from publication unless a
separate, documented transformation creates a derived feature and marks its source reference as
modified. Differences between scholarly reconstructions remain alternatives under a shared
`dispute_group`; the pipeline does not average boundaries.

## Historical names

Names are admitted as sourced, dated attestations. Local or historical names should be primary
where the source supports that role; translations, transliterations, exonyms and conventional
English forms remain explicitly typed alternatives. If a source supplies no independent name
chronology, the adapter marks the name as inheriting the feature interval rather than inventing a
date. Display labels never become entity identifiers.

## Ethical exclusions

Do not expose exact coordinates for protected or vulnerable archaeological sites. Open Context
imports default to three decimal places and reject records flagged as related to human remains.
Project-specific restrictions can demand coarser precision or complete exclusion.

Wikimedia Commons filenames are identifiers, not permission to republish a file. A future media
adapter must validate the licence and attribution of every file revision before emitting an image
artifact.

World History Encyclopedia is not a bulk-ingest source. Individual links may be considered later
as tertiary reading only after terms, attribution and article-level use are reviewed.
