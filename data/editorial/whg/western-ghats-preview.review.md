# Western Ghats monastery preview review

Status: **non-production research preview**

Retrieved: 26 July 2026
WHG dataset: `dataset:693`
WHG DOI: `10.60681/whg-dataset-693`
Original dataset DOI: `10.5281/zenodo.998080`
Creator: Gethin Rees
Preview: 10 of 55 records, deterministically sorted by title and source ID
Provider checksum: `2c8fc283f1d4afff5ebed4684c08b14eb1df79f63a961e163f8d66e21cc0b2ad`

## Rights decision

The original Zenodo record identifies the dataset as Creative Commons Attribution-NonCommercial
4.0 International. WHG applies the same CC BY-NC 4.0 platform overlay unless otherwise specified.
This is compatible with Palimpsest's non-commercial `research` profile. It is not eligible for
the `open_core` profile or commercial redistribution.

Required attribution:

> Gethin Rees, “Early Buddhist rock-cut monasteries of the Western Ghats: Locations,” Zenodo,
> version 1, 2017, https://doi.org/10.5281/zenodo.998080; normalized via World Historical
> Gazetteer dataset 693, https://doi.org/10.60681/whg-dataset-693.

Any published transformation must indicate that Palimpsest normalized the data and must link
to the CC BY-NC 4.0 licence.

## Preview observations

- All ten records have geometry: six `MultiPoint` and four `Point` records.
- All ten have at least one name and a short description.
- Six have external authority links; four have none.
- Nine records use the range 100 BCE–449 CE; Chaul uses 100–449 CE.
- Descriptions identify nearby valleys, settlements, or passes, but are short catalogue notes
  rather than reader-ready historical accounts.
- WHG geometry can cite an authority different from the original fieldwork dataset. Preserve both
  the WHG augmentation and original dataset lineage.

## Blocking chronology issue

The repeated 100 BCE–449 CE interval appears to express the collection's inclusion scope, not a
site-specific claim that every monastery was constructed, occupied, or continuously active
throughout that entire period. Publishing those ranges as ordinary feature validity would
overstate the evidence.

Before admission, choose and document one of these treatments:

1. obtain site-specific dates from the cited research and publish them as evidence-backed
   intervals;
2. display the sites in a timeless research collection with the statement “included because caves
   were cut between the second century BCE and early fifth century CE,” without activating each
   site across the full interval; or
3. model the broad range as a dataset-selection assertion rather than feature chronology.

Option 2 is the safest initial presentation.

## App recommendation

Do not add these records to the ordinary year-filtered polity/site layer yet. Build a compact
curated collection titled **Early Buddhist rock-cut monasteries of the Western Ghats**, with:

- a distinct site symbol;
- an explicit non-polity/context-layer label;
- the collection-level date caveat;
- original and WHG citations;
- external authority links where present;
- source descriptions shown unchanged;
- optional plain-language explanations shown as labelled editorial or AI-assisted restatements.

DeepSeek must not infer site dates, functions, patrons, affiliations, or identities. If used, it
may only restate the supplied description, with the original text and checksum retained.
