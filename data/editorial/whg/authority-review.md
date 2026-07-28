# WHG-discovered authority-link review

Status: **direct-source verified and configured; awaiting a clean research release**

Reviewed: 26 July 2026

## Decision boundary

WHG was used to discover candidates. Identity and rights were then checked against the official
Pleiades, Getty TGN, and OpenStreetMap APIs. A WHG score or provider `match` flag was not treated as
evidence of identity.

The five surviving links are all `close_match`. None is an `exact_match`, because each authority
describes a related modern place or physical feature while the Pleiades subject describes an
ancient site.

## Verified recommendations

| Pleiades subject | Direct authority | Relation | Direct evidence | Reason |
| --- | --- | --- | --- | --- |
| `305770200` Montagna di Gildone | OSM node `2552149251` | `close_match` | Identical name and representative point; OSM identifies a 902 m natural peak and links Wikidata `Q31621445` | Pleiades describes fortifications and Samnite tombs on the mountain, not the peak as a physical feature |
| `452370` Longobucco | TGN `1045130` | `close_match` | Getty identifies Longobucco as an inhabited place; Pleiades uses the same name 0.455 km away | Modern inhabited place and ancient atlas place may overlap but are not temporally identical entities |
| `540765` Erateini | TGN `7236380` | `close_match` | Getty identifies Eratiní as an inhabited place 0.415 km from the Pleiades representative point | Name and location align; Pleiades has no name attestation establishing continuous identity |
| `79765` Wingham | TGN `1031160` | `close_match` | Getty identifies the village Wingham and records the variant `Wingheham`; it is 0.757 km from the Pleiades point | Useful historical-name and modern-place bridge but not proof that both authority records delimit the same entity |
| `148027` Cabellio | TGN `1032455` | `close_match` | Getty identifies Cavaillon and supplies `Cabellio` and `Cabelio` as names; the Pleiades record also names Cabellio and Cavaillon | Strong continuity evidence; the modern inhabited-place authority still should not replace the ancient place record |

## Rights and attribution

- Getty TGN Linked Open Data is ODC-By 1.0. Public display must use Getty's requested TGN
  attribution and retain the record URI.
- OpenStreetMap data is ODbL 1.0. Display must identify OpenStreetMap and link its copyright/licence
  page.
- WHG's CC BY-NC 4.0 terms apply to the retained discovery snapshot and audit evidence, but the
  visitor-facing authority records should be sourced directly from Getty or OpenStreetMap.
- Pleiades remains the source of the Palimpsest subject and retains its CC BY 3.0 attribution.

## Publication implementation

The current WHG reconciliation snapshot is not converted directly into visitor authority matches.
Its canonical WHG IDs hide the underlying Getty dataset for four records and cannot express
separate WHG and underlying-source rights cleanly.

Implemented:

1. the five direct authority records are acquired and checksum/content-checksum validated;
2. the adapter creates four Getty-sourced and one OSM-sourced `AuthorityMatch` records;
3. every match uses the direct TGN/OSM identifier and URL;
4. WHG appears only in lineage as the discovery route;
5. all five normalize as reviewed `close_match` connections.

The app reader already supports accepted authority links. A complete research release is pending
because the independently configured Library of Congress `loc_new_laws` source changed checksum.
That unrelated record needs its own source review before the release gate may advance.
