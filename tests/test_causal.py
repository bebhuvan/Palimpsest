from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import orjson
import pytest
from pydantic import ValidationError

from history_pipeline.artifacts import build_artifacts, content_shard
from history_pipeline.causal import load_causal_dataset, validate_causal_entities
from history_pipeline.models import (
    CausalClaim,
    CausalDataset,
    CausalPath,
    CausalSourceReference,
    HistoricalEntity,
    HistoricalFeature,
    SourceReference,
)
from history_pipeline.verify import _verify_causal_contract


def _source(record_id: str = "chapter-1") -> CausalSourceReference:
    return CausalSourceReference(
        source_id="historian-book",
        record_id=record_id,
        title="A reviewed historical study",
        publisher="Example University Press",
        url=f"https://example.org/{record_id}",
        license_id="CC-BY-4.0",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        citation=f"Historian, Study, {record_id}",
        source_kind="scholarship",
        license_reviewed=True,
        license_review_notes="Publisher marks this edition CC BY 4.0",
    )


def _claim(
    claim_id: str,
    cause: str,
    effect: str,
    cause_period: tuple[int, int],
    effect_period: tuple[int, int],
    **updates: object,
) -> CausalClaim:
    values: dict[str, object] = {
        "claim_id": claim_id,
        "cause_entity_ids": [cause],
        "effect_entity_ids": [effect],
        "relationship": "contributed_to",
        "mechanism_type": "institutional_change",
        "mechanism_summary": {
            "en": "A cited institutional mechanism links these historical developments."
        },
        "cause_period": {
            "valid_from": cause_period[0],
            "valid_to": cause_period[1],
            "precision": "range",
            "rationale": "Dates follow the cited study",
        },
        "effect_period": {
            "valid_from": effect_period[0],
            "valid_to": effect_period[1],
            "precision": "range",
            "rationale": "Dates follow the cited study",
        },
        "evidence_basis": "scholarship",
        "confidence": {"grade": "B", "rationale": "Supported by specialist research"},
        "perspective": "institutional-history",
        "source_refs": [_source()],
        "authored_by": "curator:one",
        "review_status": "provisional",
    }
    values.update(updates)
    return CausalClaim.model_validate(values)


def test_long_range_claim_requires_connected_intermediate_claims() -> None:
    first = _claim(
        "claim:first",
        "wikidata:Q1",
        "wikidata:Q2",
        (1500, 1500),
        (1600, 1750),
    )
    second = _claim(
        "claim:second",
        "wikidata:Q2",
        "wikidata:Q3",
        (1600, 1750),
        (1751, 1800),
    )
    parent = _claim(
        "claim:synthesis",
        "wikidata:Q1",
        "wikidata:Q3",
        (1500, 1500),
        (1800, 1800),
        long_range_synthesis=True,
        supporting_claim_ids=[first.claim_id, second.claim_id],
    )

    dataset = CausalDataset(
        claims=[first, second, parent],
        paths=[
            CausalPath(
                path_id="path:institutional-change",
                titles={"en": "An interpretive pathway"},
                summaries={"en": "A reviewed sequence of two connected claims."},
                claim_ids=[first.claim_id, second.claim_id],
                perspective="institutional-history",
                authored_by="curator:one",
            )
        ],
    )
    assert dataset.claims[-1].long_range_synthesis


def test_long_range_claim_without_intermediates_fails() -> None:
    with pytest.raises(ValidationError, match="century-spanning"):
        _claim(
            "claim:unsupported",
            "wikidata:Q1",
            "wikidata:Q3",
            (1500, 1500),
            (1800, 1800),
        )


def test_long_range_claim_rejects_disconnected_support() -> None:
    first = _claim(
        "claim:disconnected-first",
        "wikidata:Q9",
        "wikidata:Q10",
        (1500, 1500),
        (1600, 1600),
    )
    second = _claim(
        "claim:disconnected-second",
        "wikidata:Q10",
        "wikidata:Q11",
        (1600, 1600),
        (1700, 1700),
    )
    parent = _claim(
        "claim:disconnected-synthesis",
        "wikidata:Q1",
        "wikidata:Q3",
        (1500, 1500),
        (1800, 1800),
        long_range_synthesis=True,
        supporting_claim_ids=[first.claim_id, second.claim_id],
    )
    with pytest.raises(ValidationError, match="do not connect"):
        CausalDataset(claims=[first, second, parent])


def test_strong_caused_wording_requires_review_and_two_sources() -> None:
    with pytest.raises(ValidationError, match="two distinct sources"):
        _claim(
            "claim:strong",
            "wikidata:Q1",
            "wikidata:Q2",
            (1500, 1500),
            (1501, 1501),
            relationship="caused",
            review_status="verified",
            reviewed_by=["curator:two"],
        )


def test_causal_source_requires_explicit_license_review() -> None:
    data = _source().model_dump()
    data["license_reviewed"] = False
    with pytest.raises(ValidationError, match="licence review"):
        CausalSourceReference.model_validate(data)


def test_causal_artifacts_are_sharded_by_claim_and_entity(
    tmp_path: Path, historical_feature: HistoricalFeature
) -> None:
    claim = _claim(
        "claim:short",
        "wikidata:Q1",
        "wikidata:Q2",
        (-100, -50),
        (-49, 1),
    )
    dataset = CausalDataset(claims=[claim])
    output = tmp_path / "build"

    artifacts = build_artifacts(
        [historical_feature], [], [], [], output, causal=dataset
    )

    paths = {artifact.path for artifact in artifacts}
    assert "causal/index.json" in paths
    claim_payload = orjson.loads(
        (output / f"causal/claims/{content_shard(claim.claim_id)}.json").read_bytes()
    )
    assert claim_payload[claim.claim_id]["relationship"] == "contributed_to"
    cause_payload = orjson.loads(
        (output / "causal/entities" / f"{content_shard('wikidata:Q1')}.json").read_bytes()
    )
    assert cause_payload["wikidata:Q1"]["outgoing_claim_ids"] == [claim.claim_id]

    _verify_causal_contract(output, "causal/index.json", paths)
    cause_payload["wikidata:Q1"]["outgoing_claim_ids"] = []
    cause_path = output / "causal/entities" / f"{content_shard('wikidata:Q1')}.json"
    cause_path.write_bytes(orjson.dumps(cause_payload))
    with pytest.raises(ValueError, match="Incomplete outgoing"):
        _verify_causal_contract(output, "causal/index.json", paths)


def test_causal_loader_and_entity_validation_fail_closed(
    tmp_path: Path, historical_feature: HistoricalFeature
) -> None:
    path = tmp_path / "causal.yml"
    path.write_text("schema_version: 1.0.0\nclaims: []\npaths: []\n", encoding="utf-8")
    dataset, checksum = load_causal_dataset(path)
    assert dataset.claims == []
    assert checksum and len(checksum) == 64

    claim = _claim(
        "claim:missing-entity",
        "wikidata:Q1",
        "wikidata:Q999",
        (-100, -50),
        (-49, 1),
    )
    with pytest.raises(ValueError, match="absent from the release"):
        validate_causal_entities(CausalDataset(claims=[claim]), [historical_feature], [])


def test_causal_entity_can_be_supplied_by_enrichment(
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    claim = _claim(
        "claim:enriched-entity",
        "wikidata:Q1",
        "wikidata:Q2",
        (-100, -50),
        (-49, 1),
    )
    entity = HistoricalEntity(
        entity_id="wikidata:Q2",
        entity_type="event",
        names={"en": "Related event"},
        source_refs=[source_reference],
    )
    validate_causal_entities(CausalDataset(claims=[claim]), [historical_feature], [entity])
