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


class ReviewedRights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_id: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    rights_uri: HttpUrl | None = None
    review_notes: str = Field(min_length=1)


class ItemRightsPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_explicit_license: Literal[True] = True
    allowed: list[str] = Field(min_length=1)


class SourceRights(BaseModel):
    """Separate dataset metadata, per-item media, and derived annotation rights."""

    model_config = ConfigDict(extra="forbid")

    metadata: ReviewedRights
    media: ItemRightsPolicy | None = None
    georeference: ReviewedRights | None = None


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
        "authority_reconciliation",
        "iiif_maps",
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
    distribution_tier: Literal["open_core", "research_only"] = "open_core"
    redistribution_conditions: list[str] = Field(default_factory=list)
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
    rights: SourceRights | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_license_review_note(self) -> SourceConfig:
        if self.license_reviewed and not self.license_notes:
            raise ValueError("license_reviewed sources must document the review basis")
        if self.rights and self.rights.metadata.license_id != self.license_id:
            raise ValueError("metadata rights must match the source license_id")
        if self.adapter == "authority_reconciliation" and self.rights is None:
            raise ValueError("authority reconciliation requires scoped metadata rights")
        if self.adapter == "iiif_maps":
            if (
                self.rights is None
                or self.rights.media is None
                or self.rights.georeference is None
            ):
                raise ValueError(
                    "IIIF maps require separate metadata, media, and georeference rights"
                )
        if (
            self.commercial_redistribution == CommercialRedistribution.CONDITIONAL
            and self.license_reviewed
            and not self.redistribution_conditions
        ):
            raise ValueError(
                "conditional commercial redistribution requires documented conditions"
            )
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
                "authority_reconciliation": [SourceRole.AUTHORITY_METADATA],
                "iiif_maps": [SourceRole.PRIMARY_SOURCE],
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
    distribution_profile: Literal["open_core", "research"] = "research"
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
        if self.distribution_profile == "open_core":
            if self.license_policy.mode != "commercial":
                raise ValueError("open_core requires the commercial licence policy")
            for source in self.sources:
                if not source.enabled:
                    continue
                if source.distribution_tier != "open_core":
                    raise ValueError(
                        f"{source.id}: research_only source cannot be enabled in open_core"
                    )
                if source.commercial_redistribution in {
                    CommercialRedistribution.PROHIBITED,
                    CommercialRedistribution.UNREVIEWED,
                }:
                    raise ValueError(
                        f"{source.id}: open_core requires reviewed commercial redistribution"
                    )
        elif self.license_policy.mode != "noncommercial":
            raise ValueError("research profile requires the noncommercial licence policy")
        return self


def _merge_config(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key == "sources" and isinstance(value, list):
            base_sources = {
                item["id"]: dict(item)
                for item in merged.get("sources", [])
                if isinstance(item, dict) and "id" in item
            }
            order = list(base_sources)
            for item in value:
                if not isinstance(item, dict) or "id" not in item:
                    raise ValueError("Overlay sources must be objects with an id")
                source_id = str(item["id"])
                if source_id in base_sources:
                    base_sources[source_id] = _merge_config(base_sources[source_id], item)
                else:
                    base_sources[source_id] = dict(item)
                    order.append(source_id)
            merged[key] = [base_sources[source_id] for source_id in order]
        elif (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_raw_config(path: Path, seen: frozenset[Path] = frozenset()) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in seen:
        raise ValueError(f"Configuration inheritance cycle at {resolved}")
    with resolved.open("rb") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must be a YAML object: {resolved}")
    parent = value.pop("extends", None)
    if parent is None:
        return value
    if not isinstance(parent, str) or not parent:
        raise ValueError("extends must be a non-empty relative path")
    parent_path = (resolved.parent / parent).resolve()
    return _merge_config(
        _load_raw_config(parent_path, seen | {resolved}),
        value,
    )


def config_fingerprint_bytes(path: Path) -> bytes:
    """Return deterministic effective configuration bytes, including inherited files."""

    return yaml.safe_dump(
        _load_raw_config(path),
        sort_keys=True,
        allow_unicode=True,
    ).encode()


def load_config(path: Path) -> PipelineConfig:
    return PipelineConfig.model_validate(_load_raw_config(path))
