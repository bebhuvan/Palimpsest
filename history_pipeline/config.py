from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from history_pipeline.models import (
    CommercialRedistribution,
    ConfidenceGrade,
    DatePrecision,
    FeatureKind,
    ReviewStatus,
    SourceRole,
    SpatialMeaning,
)


class SourceDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FeatureKind
    spatial_meaning: SpatialMeaning
    date_precision: DatePrecision
    temporal_confidence: ConfidenceGrade
    spatial_confidence: ConfidenceGrade
    interpretive_confidence: ConfidenceGrade
    review_status: ReviewStatus = ReviewStatus.PROVISIONAL
    min_display_zoom: float = Field(default=0, ge=0, le=24)


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    enabled: bool = True
    adapter: Literal[
        "cliopatria",
        "owid",
        "geojson",
        "linked_places",
        "pleiades",
        "open_context",
        "periodo",
        "wikidata",
        "wikipedia",
        "curated",
    ]
    title: str
    publisher: str
    url: HttpUrl
    license_id: str
    license_reviewed: bool = False
    license_notes: str | None = None
    roles: list[SourceRole] = Field(default_factory=list)
    commercial_redistribution: CommercialRedistribution = (
        CommercialRedistribution.UNREVIEWED
    )
    expected_checksum_sha256: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    temporal_scope: str | None = None
    geographic_scope: str | None = None
    release_policy: str = "Snapshot every response before normalization."
    limitations: list[str] = Field(default_factory=list)
    citation: str
    version: str | None = None
    member_name: str | None = None
    indicator_slug: str | None = None
    defaults: SourceDefaults | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_license_review_note(self) -> SourceConfig:
        if self.license_reviewed and not self.license_notes:
            raise ValueError("license_reviewed sources must document the review basis")
        if len(self.roles) != len(set(self.roles)):
            raise ValueError("Source roles must be unique")
        if not self.roles:
            defaults = {
                "cliopatria": [SourceRole.HISTORICAL_GEOMETRY, SourceRole.SCHOLARLY_ASSERTION],
                "geojson": [SourceRole.HISTORICAL_GEOMETRY],
                "linked_places": [SourceRole.GAZETTEER],
                "open_context": [SourceRole.PRIMARY_SOURCE, SourceRole.GAZETTEER],
                "owid": [SourceRole.INDICATOR],
                "periodo": [SourceRole.CHRONOLOGY, SourceRole.SCHOLARLY_ASSERTION],
                "pleiades": [SourceRole.GAZETTEER, SourceRole.HISTORICAL_GEOMETRY],
                "wikidata": [SourceRole.AUTHORITY_METADATA],
                "wikipedia": [SourceRole.TERTIARY_SUMMARY],
                "curated": [SourceRole.PRIMARY_SOURCE, SourceRole.SCHOLARLY_ASSERTION],
            }
            self.roles = defaults[self.adapter]
        return self


class LicensePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["noncommercial", "commercial"] = "noncommercial"
    allowed: list[str]
    denied: list[str] = Field(default_factory=list)
    require_explicit_license: bool = True


class TileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_zoom: int = Field(default=0, ge=0, le=14)
    maximum_zoom: int = Field(default=7, ge=0, le=14)
    simplification: float = Field(default=2.0, gt=0)

    @model_validator(mode="after")
    def validate_zoom_range(self) -> TileConfig:
        if self.minimum_zoom > self.maximum_zoom:
            raise ValueError("minimum_zoom cannot exceed maximum_zoom")
        return self


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_year: int = -3400
    maximum_year: int = 2026
    raw_dir: Path = Path("data/raw")
    staged_dir: Path = Path("data/staged")
    cache_dir: Path = Path("data/cache")
    dist_dir: Path = Path("dist/data")
    causal_claims_path: Path | None = None
    theme_rules_path: Path | None = None
    curated_records_path: Path | None = None
    user_agent_env: str = "WIKIMEDIA_USER_AGENT"
    tiles: TileConfig = Field(default_factory=TileConfig)
    sources: list[SourceConfig]
    license_policy: LicensePolicy

    @model_validator(mode="after")
    def validate_release_scope(self) -> PipelineConfig:
        if self.minimum_year == 0 or self.maximum_year == 0:
            raise ValueError("The configured timeline cannot use year zero")
        if self.minimum_year >= self.maximum_year:
            raise ValueError("minimum_year must be earlier than maximum_year")
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Source IDs must be unique")
        return self


def load_config(path: Path) -> PipelineConfig:
    with path.open("rb") as handle:
        raw = yaml.safe_load(handle)
    return PipelineConfig.model_validate(raw)
