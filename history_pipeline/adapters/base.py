from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from history_pipeline.config import PipelineConfig, SourceConfig
from history_pipeline.models import (
    AuthorityMatch,
    HistoricalFeature,
    HistoricalMapMetadata,
    HistoricalPeriodDefinition,
    IndicatorObservation,
)
from history_pipeline.storage import DownloadCache, RawAsset


@dataclass
class RejectedRecord:
    source_id: str
    record_id: str
    stage: str
    reason: str


@dataclass
class AdapterResult:
    features: list[HistoricalFeature] = field(default_factory=list)
    indicators: list[IndicatorObservation] = field(default_factory=list)
    periods: list[HistoricalPeriodDefinition] = field(default_factory=list)
    authority_matches: list[AuthorityMatch] = field(default_factory=list)
    historical_maps: list[HistoricalMapMetadata] = field(default_factory=list)
    rejections: list[RejectedRecord] = field(default_factory=list)
    raw_assets: list[RawAsset] = field(default_factory=list)


@dataclass(frozen=True)
class AdapterContext:
    pipeline: PipelineConfig
    source: SourceConfig
    downloads: DownloadCache
    raw_source_dir: Path
    staged_source_dir: Path


class SourceAdapter(Protocol):
    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult: ...
