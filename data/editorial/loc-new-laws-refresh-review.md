# Library of Congress catalog refresh review

Review date: 2026-07-27

Source: `loc_new_laws`
Record: `mss31013-03800`
Decision: retain the approved snapshot and require an explicit review for future refreshes.

## Compared responses

- Approved snapshot: `6a97893bb98a13ba2a0f5943aa3e5e4604a06120b5f130208c5dda14db3de2f2`
- Observed response: `49a70fc1f28fd1d4287a016b398f5f46a6a5365e0a2c69aa7c1e63f1c57e42cd`
- Additional observed response: `ca499ff71373febf72e2b8e28d01dcf67f885696aed4824245a9e6eec68c0a5f`

## Findings

The catalog evidence used by Palimpsest is unchanged:

- title, record identifier and catalog revision;
- created/published statement;
- contributor;
- notes, including the correction from 1544 to 1543;
- rights statement;
- cited resource and citation metadata.

The full API response changed because it also includes presentation and discovery data:

- request timestamps and response duration;
- search relevance scores;
- recommendation results;
- ordering of language and subject arrays.

Sorting the language and subject arrays and excluding the search score makes the
approved and newly observed `item` records equal. The cited `resources` and
`cite_this` sections are also equal. The second observed response changed again
while preserving those same substantive fields, confirming that a checksum of the
whole response is sensitive to non-evidentiary API volatility.

## Release decision

No evidence assertion, dossier, citation or source version changes are warranted.
Normal builds reuse the checksummed, reviewed snapshot. A maintainer may refresh
the live record deliberately, compare the evidence-bearing fields, update this
review, and then approve a new checksum if the catalog substance or rights have
changed.
