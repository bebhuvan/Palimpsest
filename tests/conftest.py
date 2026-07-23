from __future__ import annotations

from datetime import UTC, datetime

import pytest

from history_pipeline.models import (
    Confidence,
    ConfidenceGrade,
    DatePrecision,
    FeatureKind,
    HistoricalFeature,
    HistoricalTheme,
    ReviewStatus,
    SourceReference,
    SpatialMeaning,
)


@pytest.fixture
def source_reference() -> SourceReference:
    return SourceReference(
        source_id="test-source",
        record_id="record-1",
        title="Test source",
        publisher="Test publisher",
        url="https://example.org/record-1",
        license_id="CC-BY-4.0",
        retrieved_at=datetime.now(UTC),
        checksum_sha256="a" * 64,
        citation="Test citation",
    )


@pytest.fixture
def historical_feature(source_reference: SourceReference) -> HistoricalFeature:
    confidence = Confidence(grade=ConfidenceGrade.B, rationale="Fixture evidence")
    return HistoricalFeature(
        feature_id="test-source:polity:-100:100:abcdef",
        kind=FeatureKind.POLITY,
        spatial_meaning=SpatialMeaning.TERRITORIAL_CONTROL,
        names={"en": "Example polity"},
        valid_from=-100,
        valid_to=100,
        date_precision=DatePrecision.RANGE,
        geometry={
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        },
        temporal_confidence=confidence,
        spatial_confidence=confidence,
        interpretive_confidence=confidence,
        review_status=ReviewStatus.PROVISIONAL,
        source_refs=[source_reference],
        themes=[HistoricalTheme.POWER],
        wikidata_ids=["Q1"],
        wikipedia_titles={"en": "Example"},
    )
