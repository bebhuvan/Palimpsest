from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from history_pipeline.curated import CuratedRecords, load_curated_records
from history_pipeline.dossiers import (
    canonical_sha256,
    generate_with_openai,
    ingest_model_output,
    publish_reviewed_draft,
    read_json_model,
    reject_draft,
    review_draft,
    validate_draft,
    validate_evidence_document_snapshot,
    validate_published_dossier,
    write_json,
)
from history_pipeline.models import (
    ApprovedEvidenceBundle,
    AssertionObject,
    DossierDraft,
    DossierDraftResult,
    EditorialState,
    EvidenceDocument,
    EvidencePassage,
    HistoricalDossier,
)

PILOT = Path("data/editorial/copernicus-1543")
CURATED = Path("data/curation/knowledge-1543.yml")
PROMPT = Path("prompts/dossier-draft-v1.txt")


def _pilot() -> tuple[ApprovedEvidenceBundle, CuratedRecords, DossierDraft]:
    curated, _checksum = load_curated_records(CURATED)
    bundle = read_json_model(PILOT / "evidence-bundle.json", ApprovedEvidenceBundle)
    draft = read_json_model(PILOT / "draft.json", DossierDraft)
    return bundle, curated, draft


def _ingest(
    raw: dict[str, Any],
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
) -> DossierDraft:
    prompt = PROMPT.read_text(encoding="utf-8")
    return ingest_model_output(
        raw,
        bundle,
        curated,
        prompt_version="dossier-draft-v1",
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        model_identifier="fixture:test",
        generated_at=datetime(2026, 7, 23, 7, 5, tzinfo=UTC),
    )


def test_copernicus_pilot_is_machine_only_and_source_pinned() -> None:
    bundle, curated, draft = _pilot()
    validate_draft(draft, bundle, curated)
    assert draft.generation.evidence_bundle_sha256 == canonical_sha256(bundle)
    assert draft.generation.output_sha256 == canonical_sha256(draft.content)
    assert draft.generation.prompt_version == "dossier-draft-v1"
    assert draft.generation.model_identifier == "fixture:deterministic-dossier-v1"
    [document] = bundle.sources
    assert document.source_revision_id == document.source_ref.version
    assert document.source_revision_field_path == "/item/modified"
    assert document.source_ref.license_id == "PDM-1.0"
    assert document.attribution == document.source_ref.citation
    exact_fields = {
        passage.source_field_path: passage.text for passage in document.passages
    }
    assert exact_fields == {
        "/item/title": (
            "[Title page of De revolutionibus orbium coelstium, with statement that "
            "the sun, and not the earth, is the center of our universe]"
        ),
        "/item/creators/0/title": "Copernicus, Nicolaus, 1473-1543.",
        "/item/notes/0/note": (
            "Title page in: De revolutionibus orbium coelestium / Nicolaus Copernicus. "
            "Norimbergae : Apud I. Petreium, 1543."
        ),
        "/item/created_published": "[published 1543]",
    }
    assert all(
        assertion.confidence.rationale not in document.text
        for assertion in bundle.assertions
    )
    assert not (PILOT / "reviewed-draft.json").exists()
    assert not list((PILOT / "published").glob("*.json"))


def test_invalid_citation_span_fails_closed() -> None:
    bundle, curated, draft = _pilot()
    raw = draft.content.model_dump(mode="json")
    raw["claims"][0]["citations"][0]["quote"] = "Unsupported replacement"
    with pytest.raises(ValueError, match="quote does not match"):
        _ingest(raw, bundle, curated)


def test_source_field_provenance_must_match_the_revision_pinned_snapshot() -> None:
    bundle, _curated, _draft = _pilot()
    document = bundle.sources[0]
    passages = {passage.source_field_path: passage.text for passage in document.passages}
    snapshot = json.dumps(
        {
            "item": {
                "title": passages["/item/title"],
                "creators": [{"title": passages["/item/creators/0/title"]}],
                "notes": [{"note": passages["/item/notes/0/note"]}],
                "created_published": passages["/item/created_published"],
                "modified": document.source_revision_id,
                "summary": "",
            }
        },
        separators=(",", ":"),
    ).encode()
    raw = document.model_dump(mode="json")
    raw["source_ref"]["checksum_sha256"] = hashlib.sha256(snapshot).hexdigest()
    exact_document = EvidenceDocument.model_validate(raw)
    validate_evidence_document_snapshot(exact_document, snapshot)
    raw["passages"][0]["source_field_path"] = "/item/summary"
    wrong_field = EvidenceDocument.model_validate(raw)
    with pytest.raises(ValueError, match="differs from exact source field"):
        validate_evidence_document_snapshot(wrong_field, snapshot)


def test_unknown_assertion_and_entity_or_date_mismatch_fail_closed() -> None:
    bundle, curated, draft = _pilot()
    raw = draft.content.model_dump(mode="json")
    raw["claims"][0]["supporting_assertion_ids"] = ["assertion:not-approved"]
    with pytest.raises(ValueError, match="unsupported assertion"):
        _ingest(raw, bundle, curated)

    raw = draft.content.model_dump(mode="json")
    raw["claims"][0]["entity_ids"] = ["historyjoice:person:nicolaus-copernicus"]
    with pytest.raises(ValueError, match="entity IDs"):
        _ingest(raw, bundle, curated)

    raw = draft.content.model_dump(mode="json")
    raw["claims"][0]["valid_from"] = 1542
    with pytest.raises(ValueError, match="chronology"):
        _ingest(raw, bundle, curated)


def test_explicit_no_evidence_result_requires_an_empty_bundle() -> None:
    bundle, curated, _draft = _pilot()
    empty = ApprovedEvidenceBundle.model_validate(
        {
            **bundle.model_dump(mode="json"),
            "bundle_id": "evidence-bundle:copernicus-no-evidence",
            "assertions": [],
            "sources": [],
        }
    )
    content = {
        "result": "no_evidence",
        "title": None,
        "language": "en",
        "claims": [],
        "no_evidence_reason": "No approved passages or assertions were supplied.",
        "conflicts": [],
    }
    draft = _ingest(content, empty, curated)
    assert draft.content.result == DossierDraftResult.NO_EVIDENCE

    with pytest.raises(ValueError, match="requires an empty"):
        _ingest(content, bundle, curated)


def test_explicit_conflicting_evidence_is_verified_not_resolved() -> None:
    bundle, curated, _draft = _pilot()
    original = curated.assertions[-1]
    conflict = original.model_copy(
        update={
            "assertion_id": "assertion:de-revolutionibus-subject-conflict",
            "object": AssertionObject(kind="text", value="geocentric astronomy"),
        }
    )
    expanded_curated = CuratedRecords.model_validate(
        {
            **curated.model_dump(mode="json"),
            "assertions": [
                *[item.model_dump(mode="json") for item in curated.assertions],
                conflict.model_dump(mode="json"),
            ],
        }
    )
    [document] = bundle.sources
    conflict_text = "A conflicting approved record assigns a different main subject."
    start = len(document.text)
    expanded_document = EvidenceDocument.model_validate(
        {
            **document.model_dump(mode="json"),
            "text": document.text + conflict_text,
            "text_sha256": hashlib.sha256(
                (document.text + conflict_text).encode("utf-8")
            ).hexdigest(),
            "passages": [
                *[item.model_dump(mode="json") for item in document.passages],
                EvidencePassage(
                    passage_id="passage:subject-conflict",
                    source_field_path="/test/subject-conflict",
                    assertion_ids=[conflict.assertion_id],
                    start_char=start,
                    end_char=start + len(conflict_text),
                    text=conflict_text,
                    text_sha256=hashlib.sha256(conflict_text.encode("utf-8")).hexdigest(),
                ).model_dump(mode="json"),
            ],
        }
    )
    expanded_bundle = ApprovedEvidenceBundle.model_validate(
        {
            **bundle.model_dump(mode="json"),
            "bundle_id": "evidence-bundle:copernicus-conflict",
            "assertions": [
                *[item.model_dump(mode="json") for item in bundle.assertions],
                conflict.model_dump(mode="json"),
            ],
            "sources": [expanded_document.model_dump(mode="json")],
        }
    )
    existing = next(
        passage
        for passage in document.passages
        if original.assertion_id in passage.assertion_ids
    )
    content = {
        "result": "conflicting_evidence",
        "title": None,
        "language": "en",
        "claims": [],
        "no_evidence_reason": None,
        "conflicts": [
            {
                "conflict_id": "conflict:main-subject",
                "assertion_ids": [original.assertion_id, conflict.assertion_id],
                "explanation": "The approved assertions assign different main subjects.",
                "citations": [
                    {
                        "source_id": document.source_ref.source_id,
                        "passage_id": existing.passage_id,
                        "start_char": existing.start_char,
                        "end_char": existing.end_char,
                        "quote": existing.text,
                    },
                    {
                        "source_id": document.source_ref.source_id,
                        "passage_id": "passage:subject-conflict",
                        "start_char": start,
                        "end_char": start + len(conflict_text),
                        "quote": conflict_text,
                    },
                ],
            }
        ],
    }
    draft = _ingest(content, expanded_bundle, expanded_curated)
    assert draft.content.result == DossierDraftResult.CONFLICTING_EVIDENCE
    with pytest.raises(ValueError, match="cannot be published"):
        review_draft(
            draft,
            expanded_bundle,
            expanded_curated,
            reviewed_by="Simulated test reviewer",
            reviewed_at=datetime.now(UTC),
            notes="Conflict retained.",
        )


def test_review_rejection_and_immutable_publication_states(tmp_path: Path) -> None:
    bundle, curated, draft = _pilot()
    rejected = reject_draft(
        draft,
        bundle,
        curated,
        reason="Editorially unsuitable.",
        rejected_by="Simulated test reviewer",
        rejected_at=datetime(2026, 7, 23, 7, 20, tzinfo=UTC),
    )
    assert rejected.editorial_state == EditorialState.REJECTED
    with pytest.raises(ValueError, match="human-reviewed"):
        publish_reviewed_draft(
            draft,
            bundle,
            curated,
            editorial_license_id="CC-BY-4.0",
            editorial_attribution="History Joice",
            published_at=datetime.now(UTC),
        )

    reviewed = review_draft(
        draft,
        bundle,
        curated,
        reviewed_by="Simulated test reviewer",
        reviewed_at=datetime(2026, 7, 23, 7, 30, tzinfo=UTC),
        notes="Test-only simulated review of every cited claim.",
    )
    published = publish_reviewed_draft(
        reviewed,
        bundle,
        curated,
        editorial_license_id="CC-BY-4.0",
        editorial_attribution="History Joice",
        published_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
    )
    validate_published_dossier(published)
    assert published.editorial_state == EditorialState.PUBLISHED
    assert published.dossier_kind == "generated_editorial"
    source_extract = HistoricalDossier.model_validate(
        {
            "dossier_id": "wikipedia:en:1",
            "title": "Source extract",
            "language": "en",
            "extract": "Revision-pinned text.",
            "url": "https://en.wikipedia.org/wiki/History",
            "page_id": 1,
            "content_checksum_sha256": "a" * 64,
            "source_ref": bundle.sources[0].source_ref.model_dump(mode="json"),
        }
    )
    assert source_extract.dossier_kind == "source_extract"

    path = tmp_path / "published.json"
    write_json(path, published, immutable=True)
    with pytest.raises(FileExistsError):
        write_json(path, published, immutable=True)


def test_openai_adapter_uses_structured_outputs_without_a_live_request() -> None:
    bundle, curated, draft = _pilot()
    requested: dict[str, Any] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        requested.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_fixture",
                "status": "completed",
                "model": "fixture:model-revision",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": draft.content.model_dump_json(),
                            }
                        ],
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        generated = generate_with_openai(
            bundle,
            curated,
            prompt=PROMPT.read_text(encoding="utf-8"),
            prompt_version="dossier-draft-v1",
            model_identifier="fixture:requested-model",
            api_key="test-only",
            generated_at=datetime(2026, 7, 23, 7, 5, tzinfo=UTC),
            client=client,
        )
    assert generated.generation.model_identifier == "fixture:model-revision"
    assert generated.generation.provider_response_id == "resp_fixture"
    assert requested["store"] is False
    assert requested["text"]["format"]["type"] == "json_schema"
    assert requested["text"]["format"]["strict"] is True
    provider_schema = requested["text"]["format"]["schema"]
    assert "minLength" not in json.dumps(provider_schema)
    assert set(provider_schema["required"]) == set(provider_schema["properties"])
