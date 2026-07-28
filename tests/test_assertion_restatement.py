from __future__ import annotations

import hashlib

import pytest
from pytest_httpx import HTTPXMock

from history_pipeline.assertion_restatement import (
    AssertionRestatementRejected,
    append_assertion_restatement,
    completed_assertion_checksums,
    generate_assertion_restatement,
    read_assertion_restatements,
)
from history_pipeline.models import (
    AssertionEvidenceBasis,
    AssertionObject,
    Confidence,
    DatePrecision,
    EvidenceAssertion,
    SourceReference,
)


def _assertion(source_reference: SourceReference) -> EvidenceAssertion:
    excerpt = "The surviving evidence supports only an estimate of 1,000 to 1,500 people."
    return EvidenceAssertion(
        assertion_id="assertion:seshat:0123456789abcdef",
        subject_entity_ids=["wikidata:Q1"],
        feature_ids=["feature:one"],
        predicate="polity_population",
        object=AssertionObject(
            kind="number_range",
            value_from=1000,
            value_to=1500,
            unit="people",
        ),
        valid_from=-200,
        valid_to=-200,
        date_precision=DatePrecision.YEAR,
        confidence=Confidence(grade="C", rationale="Seshat marks this as uncertain."),
        evidence_basis=AssertionEvidenceBasis.SCHOLARLY_ASSERTION,
        source_refs=[source_reference],
        source_excerpt=excerpt,
        source_excerpt_checksum_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
    )


def test_deepseek_assertion_restatement_is_bound_to_source(
    source_reference: SourceReference, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        json={
            "id": "response-1",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": (
                            '{"text":"Evidence supports an estimate of '
                            '1,000 to 1,500 people."}'
                        )
                    },
                }
            ],
        },
    )

    restatement = generate_assertion_restatement(
        _assertion(source_reference),
        prompt="Use only the source.",
        prompt_version="test-v1",
        model_identifier="deepseek-v4-flash",
        api_key="test-key",
    )

    assert restatement.assertion_id == "assertion:seshat:0123456789abcdef"
    assert restatement.model_identifier == "deepseek-v4-flash"
    assert restatement.provider == "deepseek"


def test_deepseek_assertion_restatement_rejects_invented_number(
    source_reference: SourceReference, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        json={
            "id": "response-2",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"text":"The population was 2,000 people."}'},
                }
            ],
        },
    )

    with pytest.raises(AssertionRestatementRejected, match="unsupported_numbers"):
        generate_assertion_restatement(
            _assertion(source_reference),
            prompt="Use only the source.",
            prompt_version="test-v1",
            model_identifier="deepseek-v4-flash",
            api_key="test-key",
        )


def test_assertion_restatement_log_round_trips_and_resumes(
    tmp_path, source_reference: SourceReference, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url="https://api.deepseek.com/chat/completions",
        json={
            "id": "response-3",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"text":"Evidence supports only an estimate."}'},
                }
            ],
        },
    )
    restatement = generate_assertion_restatement(
        _assertion(source_reference),
        prompt="Use only the source.",
        prompt_version="test-v1",
        model_identifier="deepseek-v4-flash",
        api_key="test-key",
    )
    path = tmp_path / "restatements.ndjson"

    append_assertion_restatement(path, restatement)

    assert list(read_assertion_restatements(path)) == [restatement]
    assert completed_assertion_checksums(path) == {
        (restatement.assertion_id, restatement.source_excerpt_checksum_sha256)
    }
