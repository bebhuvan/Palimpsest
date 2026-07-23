# Thematic classification

The map's lenses are views over sourced assertions, not mutually exclusive boxes for places.
The authoritative release input is `data/curation/theme-rules.yml`; the authoritative release
output is the sharded `themes/index.json` contract. The short `themes` array on a feature is derived
from those assertions solely to make map tiles and search fast.

## Decision rule

For each accepted, time-bounded feature, the pipeline evaluates every reviewed rule:

1. Every selector supplied by a rule must match. Source, feature kind, spatial meaning and property
   selectors are therefore conjunctive.
2. Property values come only from structured fields such as `properties.place_types` or
   `properties.event_types`.
3. Property matching is exact after case and punctuation normalization. It is not substring search.
4. Names, descriptions, Wikipedia extracts and other prose are never scanned to assign a lens.
5. Every match creates a deterministic `ThematicAssertion` carrying the subject, dates, theme,
   subtheme, role, rule ID, matched values, confidence, review status, rationale and source records.
6. Primary and secondary assertions are materialized into the feature's `themes` array. Contextual
   assertions can support reading but do not highlight the map.

An assertion is multi-label by design. For example, an event whose own structured type is
`publication` may produce both a Knowledge assertion and a Culture assertion. A related palace,
temple or market does not cause the event to inherit Power, Belief or Trade.

## Initial vocabulary

| Lens | Structured evidence currently accepted |
| --- | --- |
| Power | Polity feature kind; explicit political/conflict event types; selected Pleiades authority or conflict place types |
| Belief | Explicit religious event types; selected Pleiades religious, sacred and funerary place types |
| Knowledge | Explicit knowledge-production event types; selected Pleiades academy, library, school, university and observatory types |
| Culture | Cultural/social feature kinds; explicit cultural event types; selected Pleiades performance and commemoration types |
| Trade | Explicit exchange route and event types; selected Pleiades market and transport infrastructure types |

Generic settlements, archaeological sites and routes do not automatically receive a theme. A
record with no assertion remains on the baseline map and should be described as unclassified in
this release—not as evidence that the theme was historically absent.

On the map, a lens is an emphasis layer rather than a new geography. Non-matching records are
dimmed, while matching source polygons, lines and points receive the lens colour, marker and line
pattern. The interface reports an empty state when no assertion is active at the selected date.

## Adding a rule

A new rule needs a stable `theme-rule:*` ID, structured selectors, a theme and subtheme, a role,
classification basis, confidence rationale, editorial rationale and public review status. Add or
change rules only with an editorial review of the upstream vocabulary. Changes alter the rule-file
checksum and therefore the content-addressed build identity.

The tests enforce deterministic IDs, exact matching, multi-label events, lack of prose inference and
the rule that a generic route does not automatically mean trade.
