from __future__ import annotations

from history_pipeline.models import (
    EntityCoordinate,
    HistoricalEntity,
    HistoricalFeature,
    SourceReference,
)
from history_pipeline.region_time import build_region_time_buckets, cell_for_point


def test_region_time_indexes_dated_coordinates_but_not_undated_entities(
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    feature = historical_feature.model_copy(update={"entity_ids": ["wikidata:Q1"]})
    dated = HistoricalEntity(
        entity_id="wikidata:Q2",
        entity_type="event",
        names={"en": "Dated event"},
        valid_from=50,
        valid_to=60,
        coordinates=[EntityCoordinate(latitude=12, longitude=22)],
        source_refs=[source_reference],
    )
    undated = HistoricalEntity(
        entity_id="wikidata:Q3",
        entity_type="event",
        names={"en": "Undated event"},
        coordinates=[EntityCoordinate(latitude=12, longitude=22)],
        source_refs=[source_reference],
    )
    non_earth = HistoricalEntity(
        entity_id="wikidata:Q4",
        entity_type="event",
        names={"en": "Non-Earth event"},
        valid_from=50,
        valid_to=60,
        coordinates=[
            EntityCoordinate(
                latitude=12,
                longitude=22,
                globe="http://www.wikidata.org/entity/Q111",
            )
        ],
        source_refs=[source_reference],
    )

    buckets, bands = build_region_time_buckets(
        [feature],
        [dated, undated, non_earth],
        [],
        minimum_year=-3400,
        maximum_year=2026,
    )

    entries = [entry for bucket in buckets for entry in bucket.entries]
    assert any(entry.entry_id == "entity:wikidata:Q2" for entry in entries)
    assert not any(entry.entry_id == "entity:wikidata:Q3" for entry in entries)
    assert not any(entry.entry_id == "entity:wikidata:Q4" for entry in entries)
    assert bands[0].valid_from == -3400
    assert cell_for_point(180, 90)[0] == "g10:35:17"
