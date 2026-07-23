from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from history_pipeline.models import (
    CausalDataset,
    HistoricalEntity,
    HistoricalFeature,
    ReviewStatus,
)


def load_causal_dataset(path: Path | None) -> tuple[CausalDataset, str | None]:
    """Load the reviewed causal layer and return its deterministic source checksum input."""

    if path is None:
        return CausalDataset(), None
    if not path.is_file():
        raise FileNotFoundError(f"Configured causal claim file is missing: {path}")
    payload = path.read_bytes()
    value = yaml.safe_load(payload) or {}
    dataset = CausalDataset.model_validate(value)
    rejected = [
        claim.claim_id
        for claim in dataset.claims
        if claim.review_status == ReviewStatus.REJECTED
    ]
    if rejected:
        raise ValueError(
            "Rejected causal claims belong in the private review history, not a release input: "
            f"{rejected}"
        )

    return dataset, hashlib.sha256(payload).hexdigest()


def validate_causal_entities(
    dataset: CausalDataset,
    features: list[HistoricalFeature],
    entities: list[HistoricalEntity],
) -> None:
    """Fail closed when a public claim points to an entity absent from this release."""

    known = {entity.entity_id for entity in entities}
    known.update(entity_id for feature in features for entity_id in feature.entity_ids)
    known.update(
        f"wikidata:{qid}" for feature in features for qid in feature.wikidata_ids
    )
    referenced = {
        entity_id
        for claim in dataset.claims
        for entity_id in (*claim.cause_entity_ids, *claim.effect_entity_ids)
    }
    missing = sorted(referenced - known)
    if missing:
        raise ValueError(
            "Causal claims reference entities absent from the release: " + ", ".join(missing)
        )
