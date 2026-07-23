# Source configuration

`pipeline.yml` is the reviewed source and licence allowlist. A source is never fetched merely
because an adapter knows how to fetch it: it must be declared here with an explicit licence,
citation, and confidence defaults.

Live upstream versions are permitted only for local exploration or API acquisition. Prefer a
numbered release URL whenever the publisher offers one. Every release records and privately
publishes the exact raw response with its checksum; changing a configured source URL invalidates
the local cache and requires a fresh reviewed snapshot.

`curated_records_path` is reserved for small, reviewed canonical slices maintained with the
publishing code. Every embedded `SourceReference` must match a declared source ID and licence in
`pipeline.yml`. Its configured authority URL is still snapshotted by the `curated` adapter and
must be checksum-pinned. The curated file checksum also participates in the build ID, so adding it
is not a bypass
around source, licence, chronology or release verification.
