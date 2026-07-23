from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from shapely.geometry import shape
from shapely.validation import explain_validity

from history_pipeline.models import FeatureKind, HistoricalFeature, SpatialMeaning


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    feature_id: str
    code: str
    severity: Severity
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue]
    checked_features: int

    @property
    def error_count(self) -> int:
        return sum(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == Severity.WARNING for issue in self.issues)


def validate_feature(feature: HistoricalFeature) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    geometry = shape(feature.geometry)
    if geometry.is_empty:
        issues.append(_issue(feature, "geometry.empty", Severity.ERROR, "Geometry is empty"))
        return issues
    if not geometry.is_valid:
        issues.append(
            _issue(
                feature,
                "geometry.invalid",
                Severity.ERROR,
                f"Invalid geometry: {explain_validity(geometry)}",
            )
        )
    min_x, min_y, max_x, max_y = geometry.bounds
    if min_x < -180 or max_x > 180 or min_y < -90 or max_y > 90:
        issues.append(
            _issue(
                feature,
                "geometry.bounds",
                Severity.ERROR,
                f"Geometry exceeds WGS84 bounds: {geometry.bounds}",
            )
        )
    if feature.spatial_meaning == SpatialMeaning.LOCATION and geometry.geom_type not in {
        "Point",
        "MultiPoint",
    }:
        issues.append(
            _issue(
                feature,
                "semantics.location_geometry",
                Severity.WARNING,
                f"Location semantics use {geometry.geom_type} geometry",
            )
        )
    if feature.spatial_meaning == SpatialMeaning.ROUTE and geometry.geom_type not in {
        "LineString",
        "MultiLineString",
    }:
        issues.append(
            _issue(
                feature,
                "semantics.route_geometry",
                Severity.WARNING,
                f"Route semantics use {geometry.geom_type} geometry",
            )
        )
    if feature.review_status == "verified" and all(
        confidence.grade in {"C", "D", "unknown"}
        for confidence in (
            feature.temporal_confidence,
            feature.spatial_confidence,
            feature.interpretive_confidence,
        )
    ):
        issues.append(
            _issue(
                feature,
                "review.low_confidence_verified",
                Severity.WARNING,
                "Verified feature has no A or B confidence axis",
            )
        )
    if feature.review_status == "contested" and not feature.dispute_group:
        issues.append(
            _issue(
                feature,
                "review.contested_without_group",
                Severity.WARNING,
                "Contested feature has no dispute_group linking alternate reconstructions",
            )
        )
    if (
        feature.spatial_uncertainty
        and feature.spatial_uncertainty.method == "multiple_reconstructions"
        and not feature.dispute_group
    ):
        issues.append(
            _issue(
                feature,
                "uncertainty.multiple_without_group",
                Severity.WARNING,
                "Multiple reconstructions require a dispute_group for comparison",
            )
        )
    if (
        feature.spatial_meaning == SpatialMeaning.TERRITORIAL_CLAIM
        and not feature.perspective
    ):
        issues.append(
            _issue(
                feature,
                "semantics.claim_without_perspective",
                Severity.WARNING,
                "Territorial claim does not identify whose perspective it represents",
            )
        )
    if feature.kind == FeatureKind.MOBILE_GROUP and feature.spatial_meaning in {
        SpatialMeaning.LEGAL_BOUNDARY,
        SpatialMeaning.TERRITORIAL_CONTROL,
    }:
        issues.append(
            _issue(
                feature,
                "semantics.mobile_group_hard_boundary",
                Severity.WARNING,
                "Mobile groups should normally use mobility, seasonal-use, or network semantics",
            )
        )
    return issues


def validate_collection(features: Iterable[HistoricalFeature]) -> ValidationReport:
    materialized = list(features)
    issues: list[ValidationIssue] = []
    identifiers = Counter(feature.feature_id for feature in materialized)
    for feature_id, count in identifiers.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    feature_id,
                    "identifier.duplicate",
                    Severity.ERROR,
                    f"Feature ID occurs {count} times",
                )
            )
    for feature in materialized:
        issues.extend(validate_feature(feature))
    return ValidationReport(issues=issues, checked_features=len(materialized))


def _issue(
    feature: HistoricalFeature, code: str, severity: Severity, message: str
) -> ValidationIssue:
    return ValidationIssue(feature.feature_id, code, severity, message)
