from __future__ import annotations

from history_pipeline.models import HistoricalFeature
from history_pipeline.validation import Severity, validate_collection, validate_feature


def test_valid_feature_has_no_errors(historical_feature: HistoricalFeature) -> None:
    issues = validate_feature(historical_feature)
    assert not [issue for issue in issues if issue.severity == Severity.ERROR]


def test_invalid_polygon_is_rejected(historical_feature: HistoricalFeature) -> None:
    data = historical_feature.model_dump()
    data["geometry"] = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
    }
    feature = HistoricalFeature.model_validate(data)
    issues = validate_feature(feature)
    assert any(issue.code == "geometry.invalid" for issue in issues)


def test_duplicate_feature_ids_are_rejected(historical_feature: HistoricalFeature) -> None:
    report = validate_collection([historical_feature, historical_feature])
    assert any(issue.code == "identifier.duplicate" for issue in report.issues)


def test_contested_reconstruction_requires_a_comparison_group(
    historical_feature: HistoricalFeature,
) -> None:
    feature = historical_feature.model_copy(update={"review_status": "contested"})
    issues = validate_feature(feature)
    assert any(issue.code == "review.contested_without_group" for issue in issues)
