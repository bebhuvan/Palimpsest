from __future__ import annotations

import pytest
from pydantic import ValidationError

from history_pipeline.models import (
    AssertionObject,
    AssertionObjectKind,
    EntityKind,
    HistoricalEntity,
    HistoricalFeature,
    HistoricalName,
    HistoricalTheme,
    SourceReference,
    TemporalUncertainty,
)


def test_historical_feature_rejects_year_zero(
    historical_feature: HistoricalFeature,
) -> None:
    data = historical_feature.model_dump()
    data["valid_from"] = 0
    with pytest.raises(ValidationError, match="year zero"):
        HistoricalFeature.model_validate(data)


def test_historical_feature_rejects_reversed_interval(
    historical_feature: HistoricalFeature,
) -> None:
    data = historical_feature.model_dump()
    data["valid_from"] = 200
    data["valid_to"] = 100
    with pytest.raises(ValidationError, match="valid_from"):
        HistoricalFeature.model_validate(data)


def test_historical_feature_requires_source(historical_feature: HistoricalFeature) -> None:
    data = historical_feature.model_dump()
    data["source_refs"] = []
    with pytest.raises(ValidationError):
        HistoricalFeature.model_validate(data)


def test_historical_feature_supports_multiple_unique_themes(
    historical_feature: HistoricalFeature,
) -> None:
    feature = historical_feature.model_copy(
        update={"themes": [HistoricalTheme.POWER, HistoricalTheme.CULTURE]}
    )
    assert feature.themes == [HistoricalTheme.POWER, HistoricalTheme.CULTURE]

    data = historical_feature.model_dump()
    data["themes"] = ["power", "power"]
    with pytest.raises(ValidationError, match="themes must be unique"):
        HistoricalFeature.model_validate(data)


def test_temporal_uncertainty_rejects_false_precision() -> None:
    with pytest.raises(ValidationError, match="year zero"):
        TemporalUncertainty(
            earliest_start=-10,
            latest_start=0,
            rationale="Only a bounded scholarly estimate is available",
        )


def test_feature_materializes_a_sourced_name_attestation(
    historical_feature: HistoricalFeature,
) -> None:
    [name] = historical_feature.name_attestations
    assert name.text == "Example polity"
    assert name.valid_from == -100
    assert name.valid_to == 100
    assert name.temporal_basis == "feature_interval"
    assert name.primary is True
    assert name.source_refs == historical_feature.source_refs


def test_historical_name_rejects_year_zero(
    historical_feature: HistoricalFeature,
) -> None:
    data = historical_feature.name_attestations[0].model_dump()
    data["valid_from"] = 0
    with pytest.raises(ValidationError, match="year zero"):
        HistoricalName.model_validate(data)


def test_feature_rejects_a_name_outside_its_geometry_interval(
    historical_feature: HistoricalFeature,
) -> None:
    data = historical_feature.model_dump()
    name = historical_feature.name_attestations[0].model_copy(
        update={"valid_from": 200, "valid_to": 300}
    )
    data["name_attestations"] = [name.model_dump()]
    with pytest.raises(ValidationError, match="overlap"):
        HistoricalFeature.model_validate(data)


def test_historical_entity_derives_normalized_kind_without_rewriting_source_type(
    source_reference: SourceReference,
) -> None:
    entity = HistoricalEntity.model_validate(
        {
            "entity_id": "wikidata:Q1",
            "entity_type": "human",
            "names": {"en": "Example person"},
            "source_refs": [source_reference],
        }
    )
    assert entity.entity_kind == EntityKind.PERSON
    assert entity.entity_type == "human"


def test_assertion_object_requires_exactly_one_typed_value() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        AssertionObject(
            kind=AssertionObjectKind.ENTITY,
            entity_id="palimpsest:person:example",
            value="duplicate",
        )


def test_assertion_object_supports_numeric_ranges() -> None:
    value = AssertionObject(
        kind=AssertionObjectKind.NUMBER_RANGE,
        value_from=1000,
        value_to=1500,
        unit="people",
    )
    assert value.value_from == 1000
    assert value.value_to == 1500

    with pytest.raises(ValidationError, match="lower bound"):
        AssertionObject(
            kind=AssertionObjectKind.NUMBER_RANGE,
            value_from=1500,
            value_to=1000,
            unit="people",
        )
