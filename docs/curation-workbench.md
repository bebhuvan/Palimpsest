# GeoLibre curation workbench

GeoLibre is an excellent internal companion to this pipeline, but it is not the public application
or a source of historical truth. It can open GeoParquet and PMTiles locally, bind vector layers to a
time slider, inspect attributes, run DuckDB Spatial SQL, check geometry validity and topology, and
export reviewed data without uploading private files.

## Review a build

1. Run `uv run history-data build --limit 1000 --tiles` for a sample or a full offline build.
2. Open an era file from `dist/data/builds/<build-id>/features/` in GeoLibre.
3. Inspect `valid_from`, `valid_to`, `spatial_meaning`, the three confidence grades,
   `review_status`, `perspective`, the temporal/spatial uncertainty JSON, and `source_refs_json`
   together. A plausible-looking polygon is not sufficient.
4. Configure GeoLibre's Time Slider against `valid_from` and `valid_to`; compare adjacent intervals
   for gaps, overlaps, geometry jumps, and unintended interpolation.
5. Run geometry validity and topology checks. Compare disputed reconstructions as separate layers;
   never dissolve or average them into a false consensus.
6. Record decisions outside the generated build. `data/raw`, `data/staged`, and `dist` are generated
   evidence, not editorial workspaces.

## Bring reviewed edits back

Export a reviewed layer as EPSG:4326 GeoJSON, publish it at an immutable URL, and declare it with the
generic `geojson` adapter. The configuration must explicitly map the identifier, name, start year,
and end year fields and declare the feature kind, spatial meaning, confidence, review status,
licence basis, citation, and publisher. The normal validation, snapshot, checksum, and release gates
then apply.

GeoLibre projects and styles can be shared among editors, but their existence does not change a
record to `verified`. Verification is an editorial decision tied to cited evidence and should be
represented in the reviewed source export.

## Curate causal interpretations

Causal claims are edited in `data/curation/causal-claims.yml`, not inferred in GeoLibre or from
Wikipedia prose. A curator first ensures that every cause/effect entity is present in the release,
then records the mechanism, chronology, perspective, confidence, authorship and licence-reviewed
scholarly citations. A different named editor is required before a claim or path can be marked
`verified`.

Use `supporting_claim_ids` to decompose long-range syntheses and `counterclaim_ids` for competing
interpretations. Keep rejected drafts in the private review history rather than the public input
file. Run `make check` and a complete offline build before merging; graph validation rejects missing
entities, disconnected paths and incomplete long-range chains.
