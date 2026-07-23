# Regional and time context contract

This index answers a narrow retrieval question: “Which sourced records in this release intersect
the selected area and year?” It does not define a historical region and does not claim that nearby
subjects interacted.

## Included records

- A reviewed map feature is added to every 10-degree cell intersected by its source geometry and
  every configured time band intersected by its exact validity interval.
- An enriched Wikidata entity without a map feature is added only when it has a selected Earth
  coordinate and at least one usable date bound. Its coordinate is discovery metadata, not reviewed
  geometry.
- Undated standalone entities are excluded. Multiple or uncertain historical locations remain a
  known Wikidata limitation and are labelled by their spatial basis.

The release retains exact validity bounds on every entry and the frontend filters them again for
the selected year. At most 60 records are returned to one selection. Events and entries with saved
dossiers rank first, followed by approximate distance to the click; this is a reading order, not a
historical-importance score.

## Static lookup

```text
click longitude/latitude + selected year
  -> 10-degree cell ID + time-band ID
  -> SHA-256(<band>|<cell>) prefix
  -> region-time/buckets/{shard}.json
  -> exact-year filtering
  -> content entity/dossier shards only for the retained IDs
```

The verifier rejects wrong shards, duplicate bucket entries, missing feature/entity/dossier joins,
entries outside their band and standalone coordinates assigned to the wrong cell. Causal claims are
excluded and remain in the reviewed causal dataset.

Reviewed and live OpenHistoricalMap feature clicks can both query this static regional layer using
their actual click coordinate. OHM records remain live contributor data and are never converted into
reviewed History Joice geometry by this lookup.
