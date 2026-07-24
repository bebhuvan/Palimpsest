# The world in 1543: bounded vertical-slice specification

## Purpose

This pilot must prove the History Joice experience, not imply that one year can represent the
world evenly. A visitor selecting 1543 should be able to move between source-backed map records,
people, events, institutions, works and interpretations while seeing where evidence, coverage and
perspective are limited.

The pilot is complete only when the real immutable release, rather than a browser-only fixture,
supports the full journey.

## Release acceptance criteria

- 20–30 deliberately selected map anchors distributed across at least five world regions;
- 50–100 first-class people, events, institutions, works, artifacts, routes, places and concepts;
- all five thematic lenses represented by non-exclusive, sourced classifications;
- 15–25 human-reviewed dossiers, with every historical claim linked to approved evidence;
- at least five primary-source or material-object records and five scholarly/authority records;
- one rights-approved, georeferenced historical map with separate metadata, image and
  georeference decisions;
- explicit disagreement or uncertainty in at least three stories;
- no region, polity or modern state described as a proxy for all people living there;
- a coverage report that names missing regions and themes instead of treating absence as history;
- verified joins from map feature to entities, assertions, dossiers and sources in the browser.

## Initial anchor stories

| Anchor | Geography | Primary lenses | Current status |
| --- | --- | --- | --- |
| Publication of *De revolutionibus* | Nuremberg | Knowledge, culture | Structured LOC slice, machine dossier draft and reviewed Wikimedia seed links |
| Royal cedula to Vasco de Quiroga | Valladolid → Michoacán | Power, belief | Structured LOC slice and reviewed Vasco de Quiroga Wikimedia seed |
| Firearms traditions at Tanegashima | Japan and maritime East Asia | Trade, power, knowledge | Structured MLIT slice and reviewed firearm Wikimedia seed; late-source distance is explicit and scholarly reconciliation remains pending |
| War between the Ethiopian kingdom and the Adal Sultanate | Horn of Africa | Power, belief, movement | Source selection required |
| Indian Ocean courts, ports and exchange | South Asia and the western Indian Ocean | Trade, culture, power | Anchor and source selection required |
| Ming frontier, maritime restrictions and exchange | East Asia | Power, trade | Anchor and source selection required |
| Material culture and political authority in West/Central Africa | Africa | Culture, power, trade | Object/source selection required |
| Indigenous and colonial worlds in the Americas | Americas | Power, belief, culture | First LOC administrative record admitted; Indigenous-source balance required |

These are research lanes, not predetermined narratives. A famous event is excluded or presented as
contested when its date, location, source rights or interpretation cannot pass the normal gates.

## Source and editorial rules

1. Geometry answers only “where may this record be inspected?” unless a source supports a
   different spatial meaning.
2. A source extract, a primary source, a scholarly assertion and History Joice interpretation
   remain visibly different records.
3. Wikipedia and Wikidata may provide bounded discovery context after map records are admitted;
   neither establishes borders or supplies uncited facts to generated prose.
4. LLM generation runs at build time over an approved evidence bundle. It may draft but cannot
   review or publish.
5. Human review must cover every generated claim. A reviewer name cannot be fabricated or replaced
   by a test actor in real data.
6. “The world in 1543” may include processes whose evidenced interval crosses 1543, but must not
   silently assign a single year to a broad movement or institution.

## Delivery order

1. admit and verify a small number of primary-source-backed anchors;
2. run bounded Wikimedia enrichment once a real monitored contact identifier is configured;
3. build evidence bundles and machine drafts;
4. perform named human review and publish immutable editorial dossiers;
5. select and rights-review one real IIIF historical map;
6. build the candidate release and test the complete browser journey;
7. deploy to a non-public staging origin for reader testing.
