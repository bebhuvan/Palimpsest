from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from pydantic import HttpUrl

from history_pipeline.config import SourceConfig
from history_pipeline.models import Confidence, ConfidenceGrade, SourceReference
from history_pipeline.storage import RawAsset


def verify_expected_checksum(source: SourceConfig, asset: RawAsset) -> None:
    """Fail closed when a reviewed mutable or tag-based release changes bytes."""

    expected = source.expected_checksum_sha256
    if expected and asset.checksum_sha256 != expected:
        raise ValueError(
            f"Source {source.id} checksum changed: expected {expected}, "
            f"got {asset.checksum_sha256}"
        )


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "unnamed"


def stable_feature_id(
    source_id: str, record_name: str, valid_from: int, valid_to: int, geometry_bytes: bytes
) -> str:
    digest = hashlib.sha256(geometry_bytes).hexdigest()[:12]
    return f"{source_id}:{slugify(record_name)}:{valid_from}:{valid_to}:{digest}"


def confidence(grade: ConfidenceGrade, source_title: str, axis: str) -> Confidence:
    return Confidence(grade=grade, rationale=f"Source default for {axis}: {source_title}")


def source_reference(
    source: SourceConfig,
    asset: RawAsset,
    record_id: str,
    *,
    url: str | None = None,
    title: str | None = None,
    retrieved_at: datetime | None = None,
) -> SourceReference:
    return SourceReference(
        source_id=source.id,
        record_id=record_id,
        title=title or source.title,
        publisher=source.publisher,
        url=HttpUrl(url or str(source.url)),
        license_id=source.license_id,
        retrieved_at=retrieved_at or asset.retrieved_at,
        version=source.version,
        checksum_sha256=asset.checksum_sha256,
        citation=source.citation,
    )


def clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if value != value:  # NaN and pandas NA
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value
