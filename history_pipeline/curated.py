from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from history_pipeline.models import EvidenceAssertion, HistoricalEntity, HistoricalFeature


class CuratedRecords(BaseModel):
    """Small reviewed canonical inputs maintained with the publishing code."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    authored_by: str = Field(min_length=1)
    reviewed_by: list[str] = Field(default_factory=list)
    features: list[HistoricalFeature] = Field(default_factory=list)
    entities: list[HistoricalEntity] = Field(default_factory=list)
    assertions: list[EvidenceAssertion] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> CuratedRecords:
        feature_ids = {feature.feature_id for feature in self.features}
        entity_ids = {entity.entity_id for entity in self.entities}
        if len(feature_ids) != len(self.features):
            raise ValueError("Curated feature IDs must be unique")
        if len(entity_ids) != len(self.entities):
            raise ValueError("Curated entity IDs must be unique")
        assertion_ids = {assertion.assertion_id for assertion in self.assertions}
        if len(assertion_ids) != len(self.assertions):
            raise ValueError("Curated assertion IDs must be unique")
        for feature in self.features:
            missing = set(feature.entity_ids) - entity_ids
            if missing:
                raise ValueError(
                    f"Curated feature {feature.feature_id} references missing entities: "
                    + ", ".join(sorted(missing))
                )
        for assertion in self.assertions:
            linked_entities = set(assertion.subject_entity_ids)
            if assertion.object.entity_id:
                linked_entities.add(assertion.object.entity_id)
            missing_entities = linked_entities - entity_ids
            if missing_entities:
                raise ValueError(
                    f"Curated assertion {assertion.assertion_id} references missing entities: "
                    + ", ".join(sorted(missing_entities))
                )
            missing_features = set(assertion.feature_ids) - feature_ids
            if missing_features:
                raise ValueError(
                    f"Curated assertion {assertion.assertion_id} references missing features: "
                    + ", ".join(sorted(missing_features))
                )
        return self


def load_curated_records(path: Path | None) -> tuple[CuratedRecords, str | None]:
    if path is None:
        return CuratedRecords(authored_by="Palimpsest", features=[], entities=[]), None
    if not path.is_file():
        raise FileNotFoundError(f"Configured curated record file is missing: {path}")
    payload = path.read_bytes()
    records = CuratedRecords.model_validate(yaml.safe_load(payload) or {})
    return records, hashlib.sha256(payload).hexdigest()
