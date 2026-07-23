# Community contribution boundary

History Joice now defines contracts and lifecycle invariants for future community proposals. It
does not provide a submission endpoint, accounts, discussion UI, social features, or a
general-purpose CMS. `CommunityProposal` records are editorial inputs and are never members of the
published canonical feature, entity, name, assertion, source, or historical-map collections.

## Bounded lifecycle

```text
proposed ──submit──> in_review ──accept──> accepted ──receipt──> immutable release
                                  └─reject──> rejected
```

Accepted and rejected states are terminal. A proposal cannot skip review, and each transition
creates a new revision while retaining the complete review history. Rejected proposals cannot
receive an `AcceptedProposalRelease` receipt and therefore cannot enter a release through this
workflow. Corrections after a terminal decision are new proposals linked through `supersedes` and
`superseded_by` IDs.

The proposal contract is deliberately bounded to:

- places;
- names;
- dates;
- geometries;
- sources;
- IIIF georeferences.

Each proposal retains contributor identity and requested attribution, a contribution licence,
bounded proposed values, source evidence and citations, discussion entries, review events, and
supersession links. Evidence must point to a change in the same proposal. An acceptance receipt
pins the accepted proposal revision and checksum, final decision event, immutable release build ID,
and resulting canonical record IDs. The receipt is provenance linking the two systems; it is not a
canonical historical record.

The public schemas are:

- `CommunityProposal.schema.json`;
- `AcceptedProposalRelease.schema.json`.

The lifecycle functions and tests are implemented in `history_pipeline/contributions.py` and
`tests/test_contributions.py`. The ingestion pipeline does not read a proposals directory or
implicitly translate proposal payloads into canonical models.

## Future editorial service

Moving from these contracts to real submissions requires a separate authenticated editorial
service. That service must provide contributor and editor authentication, authorization for review
decisions, rate limiting, abuse handling, append-only audit events, licence acceptance, and
transactional lifecycle transitions. Authentication claims must be recorded by that service; a
display name in a proposal is not proof of identity.

PostGIS will be needed for server-side geometry validation, topology checks, spatial comparison,
and editor previews. Object storage will be needed for immutable evidence attachments, source
snapshots, scanned images, IIIF manifests/annotations, and their checksums. A relational store
should retain proposal revisions, discussion, decisions, supersession edges, and release receipts.
Accepted data must still pass the existing build-time licence, schema, provenance, and release
verification gates before a new content-addressed release is published.

None of that service infrastructure is implemented here. The static visitor application continues
to consume canonical immutable releases only; community proposals must not be served as an
alternate live map layer or mixed into canonical search results.
