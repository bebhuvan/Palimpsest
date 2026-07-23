# Source configuration

`pipeline.yml` is the reviewed source and licence allowlist. A source is never fetched merely
because an adapter knows how to fetch it: it must be declared here with an explicit licence,
citation, and confidence defaults.

`pipeline.yml` is explicitly the `open_core` profile. Its enabled sources must be commercially
redistributable, and its allowlist excludes non-commercial licences. `research-overlay.yml`
inherits the effective core configuration with `extends: pipeline.yml`, changes the profile to
`research`, and permits reviewed non-commercial sources. Source entries in future overlays are
merged by `id`; all other lists replace the inherited list. The build ID fingerprints the merged
effective configuration, so a base-policy change also changes overlay build IDs.

`distribution_tier: research_only` is an enforceable exclusion from open-core builds.
`commercial_redistribution: conditional` requires explicit `redistribution_conditions` when the
licence review is complete. Research overlays do not bypass the licence allowlist or review gate.

Live upstream versions are permitted only for local exploration or API acquisition. Prefer a
numbered release URL whenever the publisher offers one. Every release records and privately
publishes the exact raw response with its checksum; changing a configured source URL invalidates
the local cache and requires a fresh reviewed snapshot.

`curated_records_path` is reserved for small, reviewed canonical slices maintained with the
publishing code. Every embedded `SourceReference` must match a declared source ID and licence in
`pipeline.yml`. Its configured authority URL is still snapshotted by the `curated` adapter and
must be checksum-pinned. The curated file checksum also participates in the build ID, so adding it
is not a bypass around source, licence, chronology or release verification.

For scoped integration records, a `SourceReference` may carry the separately reviewed
georeference licence declared under that same source's `rights`; it must not be treated as the
metadata or image licence.

Authority reconciliation and IIIF map sources additionally require scoped `rights`. Dataset
metadata rights, per-item media allowlists, and georeference-annotation rights are distinct
decisions. See the [integration framework](../docs/source-integration-framework.md).
