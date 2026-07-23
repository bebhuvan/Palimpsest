from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import HttpUrl, ValidationError

from history_pipeline.models import (
    Confidence,
    ConfidenceGrade,
    HistoricalMapMetadata,
    HistoricalMapRendering,
    ReleaseRightsApproval,
    RightsReference,
    RightsScope,
    SourceReference,
    TransformationStep,
)

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)


def map_payload() -> dict[str, object]:
    refs = [
        SourceReference(
            source_id=f"map_source_{index}",
            record_id=f"record-{index}",
            title=f"Map source {index}",
            publisher="Example Archive",
            url=HttpUrl(f"https://example.org/maps/{index}"),
            license_id="CC0-1.0",
            retrieved_at=NOW,
            citation=f"Example Archive, map source {index}",
        )
        for index in (1, 2)
    ]
    return {
        "map_id": "map:fedcba9876543210",
        "manifest_id": "https://example.org/manifest",
        "canvas_id": "https://example.org/canvas",
        "annotation_id": "https://example.org/georeference",
        "label": "Example map",
        "depicted_date": "1750",
        "providers": ["Example Archive"],
        "required_statement": "Example Archive attribution",
        "metadata_rights": RightsReference(
            scope=RightsScope.METADATA,
            license_id="CC0-1.0",
            attribution="Example Archive",
        ),
        "image_rights": RightsReference(
            scope=RightsScope.MEDIA,
            license_id="PDM-1.0",
            attribution="Example Archive",
        ),
        "georeference_rights": RightsReference(
            scope=RightsScope.GEOREFERENCE,
            license_id="CC-BY-4.0",
            attribution="Example georeferencer",
        ),
        "georeference_confidence": Confidence(
            grade=ConfidenceGrade.C,
            rationale="Three reviewed control points; residual error is not published.",
        ),
        "source_refs": refs,
        "lineage": [
            TransformationStep(
                operation="extract",
                tool="test",
                tool_version="1",
                input_record_ids=["record-1", "record-2"],
            )
        ],
    }


def approvals() -> list[ReleaseRightsApproval]:
    return [
        ReleaseRightsApproval(
            scope=scope,
            status="approved",
            decision_id=f"rights:example:{scope.value}",
            reviewed_by="Example editor",
            reviewed_at=NOW,
            rationale=f"{scope.value} rights separately reviewed.",
        )
        for scope in (
            RightsScope.METADATA,
            RightsScope.MEDIA,
            RightsScope.GEOREFERENCE,
        )
    ]


def rendering() -> HistoricalMapRendering:
    return HistoricalMapRendering(
        image_path="historical-maps/example.png",
        image_checksum_sha256="a" * 64,
        coordinates=[(10, 20), (11, 20), (11, 19), (10, 19)],
    )


def test_metadata_only_iiif_record_remains_backward_compatible_and_disabled() -> None:
    historical_map = HistoricalMapMetadata.model_validate(map_payload())
    assert historical_map.rendering is None
    assert historical_map.release_rights_approvals == []


def test_rendering_requires_three_separate_release_rights_approvals() -> None:
    payload = {
        **map_payload(),
        "known_limitations": ["Georeference residual error is unknown."],
        "rendering": rendering(),
    }
    with pytest.raises(ValidationError, match="separately ordered"):
        HistoricalMapMetadata.model_validate(payload)

    payload["release_rights_approvals"] = approvals()[:2]
    with pytest.raises(ValidationError, match="separately ordered"):
        HistoricalMapMetadata.model_validate(payload)


def test_renderable_map_requires_limitations_and_release_local_image() -> None:
    payload = {
        **map_payload(),
        "release_rights_approvals": approvals(),
        "rendering": rendering(),
    }
    with pytest.raises(ValidationError, match="known limitations"):
        HistoricalMapMetadata.model_validate(payload)

    with pytest.raises(ValidationError, match="String should match pattern"):
        HistoricalMapRendering(
            image_path="https://visitor.example/map.png",
            image_checksum_sha256="a" * 64,
            coordinates=[(10, 20), (11, 20), (11, 19), (10, 19)],
        )

    payload["known_limitations"] = ["The scan is a depiction, not authority."]
    historical_map = HistoricalMapMetadata.model_validate(payload)
    assert historical_map.rendering
    assert historical_map.rendering.protocol == "iiif-georeference-maplibre-image-v1"
