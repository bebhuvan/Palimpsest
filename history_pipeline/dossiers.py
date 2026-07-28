from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import orjson

from history_pipeline.curated import CuratedRecords
from history_pipeline.models import (
    ApprovedEvidenceBundle,
    DossierDraft,
    DossierDraftContent,
    DossierDraftResult,
    DossierGenerationProvenance,
    EditorialState,
    EvidenceAssertion,
    EvidenceCitation,
    EvidenceDocument,
    HumanDossierReview,
    PublishedEditorialDossier,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def canonical_json_bytes(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")

    def omit_additive_assertion_defaults(item: Any) -> None:
        """Keep old signed evidence stable as the assertion schema gains optional fields."""

        if isinstance(item, list):
            for nested in item:
                omit_additive_assertion_defaults(nested)
            return
        if not isinstance(item, dict):
            return
        if item.get("representation") == "structured_sourced_assertion":
            for key in (
                "source_excerpt",
                "source_excerpt_checksum_sha256",
                "restatement",
            ):
                if item.get(key) is None:
                    item.pop(key, None)
            if item.get("source_citations") == []:
                item.pop("source_citations", None)
            assertion_object = item.get("object")
            if isinstance(assertion_object, dict):
                for key in ("value_from", "value_to", "unit"):
                    if assertion_object.get(key) is None:
                        assertion_object.pop(key, None)
        for nested in item.values():
            omit_additive_assertion_defaults(nested)

    omit_additive_assertion_defaults(value)
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _resolve_json_pointer(value: Any, pointer: str) -> Any:
    current = value
    for raw_token in pointer.removeprefix("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ValueError(f"Evidence source field does not resolve: {pointer}")
    return current


def validate_evidence_document_snapshot(
    document: EvidenceDocument,
    snapshot_bytes: bytes,
) -> None:
    expected_checksum = document.source_ref.checksum_sha256
    if expected_checksum is None:
        raise ValueError("Evidence documents require a source snapshot checksum")
    if hashlib.sha256(snapshot_bytes).hexdigest() != expected_checksum:
        raise ValueError("Evidence document snapshot checksum does not match its source")
    snapshot = orjson.loads(snapshot_bytes)
    revision = _resolve_json_pointer(snapshot, document.source_revision_field_path)
    if revision != document.source_revision_id:
        raise ValueError("Evidence source revision field does not match its revision ID")
    for passage in document.passages:
        value = _resolve_json_pointer(snapshot, passage.source_field_path)
        if value != passage.text:
            raise ValueError(
                f"Evidence passage differs from exact source field: {passage.passage_id}"
            )


def _openai_output_schema() -> dict[str, Any]:
    """Project the full local contract onto the provider's supported JSON Schema subset."""

    schema = DossierDraftContent.model_json_schema()

    def remove_unsupported(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("minLength", None)
            for nested in value.values():
                remove_unsupported(nested)
        elif isinstance(value, list):
            for nested in value:
                remove_unsupported(nested)

    remove_unsupported(schema)
    return schema


def validate_bundle_against_curated(
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
) -> None:
    entity_ids = {entity.entity_id for entity in curated.entities}
    feature_ids = {feature.feature_id for feature in curated.features}
    missing_entities = set(bundle.subject_entity_ids) - entity_ids
    if missing_entities:
        raise ValueError(f"Evidence bundle references unknown entities: {sorted(missing_entities)}")
    missing_features = set(bundle.feature_ids) - feature_ids
    if missing_features:
        raise ValueError(f"Evidence bundle references unknown features: {sorted(missing_features)}")

    curated_assertions = {assertion.assertion_id: assertion for assertion in curated.assertions}
    for assertion in bundle.assertions:
        canonical = curated_assertions.get(assertion.assertion_id)
        if canonical is None:
            raise ValueError(
                f"Evidence bundle assertion is not in curated data: {assertion.assertion_id}"
            )
        if canonical_json_bytes(assertion) != canonical_json_bytes(canonical):
            raise ValueError(
                f"Evidence bundle assertion differs from curated data: {assertion.assertion_id}"
            )
        linked_entities = set(assertion.subject_entity_ids)
        if assertion.object.entity_id:
            linked_entities.add(assertion.object.entity_id)
        if not linked_entities <= entity_ids:
            raise ValueError(
                f"Evidence assertion has unknown entity IDs: {assertion.assertion_id}"
            )
        if not set(assertion.feature_ids) <= feature_ids:
            raise ValueError(
                f"Evidence assertion has unknown feature IDs: {assertion.assertion_id}"
            )
        for source_ref in assertion.source_refs:
            documents = [
                document
                for document in bundle.sources
                if canonical_json_bytes(source_ref)
                == canonical_json_bytes(document.source_ref)
            ]
            if not documents:
                raise ValueError(
                    f"Evidence assertion has no bundled source: {assertion.assertion_id}"
                )
            if not any(
                assertion.assertion_id in passage.assertion_ids
                for document in documents
                for passage in document.passages
            ):
                raise ValueError(
                    f"Evidence assertion has no passage in its source: {assertion.assertion_id}"
                )


def _citation_assertion_ids(
    citation: EvidenceCitation,
    bundle: ApprovedEvidenceBundle,
) -> set[str]:
    matches = [
        (document, passage)
        for document in bundle.sources
        if document.source_ref.source_id == citation.source_id
        for passage in document.passages
        if passage.passage_id == citation.passage_id
    ]
    if not matches:
        raise ValueError(f"Citation references an unknown passage: {citation.passage_id}")
    if len(matches) != 1:
        raise ValueError(f"Citation passage is ambiguous: {citation.passage_id}")
    document, passage = matches[0]
    if citation.start_char < passage.start_char or citation.end_char > passage.end_char:
        raise ValueError(f"Citation falls outside its approved passage: {citation.passage_id}")
    if citation.end_char > len(document.text):
        raise ValueError(f"Citation falls outside its source: {citation.passage_id}")
    if document.text[citation.start_char : citation.end_char] != citation.quote:
        raise ValueError(f"Citation quote does not match its evidence span: {citation.passage_id}")
    return set(passage.assertion_ids)


def _assertion_entities(assertion: EvidenceAssertion) -> set[str]:
    values = set(assertion.subject_entity_ids)
    if assertion.object.entity_id:
        values.add(assertion.object.entity_id)
    return values


def _validate_claims(
    content: DossierDraftContent,
    bundle: ApprovedEvidenceBundle,
) -> None:
    assertions = {assertion.assertion_id: assertion for assertion in bundle.assertions}
    for claim in content.claims:
        support_ids = set(claim.supporting_assertion_ids)
        unknown = support_ids - assertions.keys()
        if unknown:
            raise ValueError(f"Draft claim has unsupported assertion IDs: {sorted(unknown)}")
        supported = [assertions[assertion_id] for assertion_id in claim.supporting_assertion_ids]
        expected_entities = set().union(*(_assertion_entities(item) for item in supported))
        if set(claim.entity_ids) != expected_entities:
            raise ValueError(
                f"Draft claim entity IDs do not exactly match its assertions: {claim.claim_id}"
            )
        for assertion in supported:
            if (
                claim.valid_from,
                claim.valid_to,
                claim.date_precision,
            ) != (
                assertion.valid_from,
                assertion.valid_to,
                assertion.date_precision,
            ):
                raise ValueError(
                    f"Draft claim chronology differs from its assertion: {claim.claim_id}"
                )

        citation_coverage: set[str] = set()
        for citation in claim.citations:
            passage_assertions = _citation_assertion_ids(citation, bundle)
            covered = passage_assertions & support_ids
            if not covered:
                raise ValueError(
                    f"Draft claim citation supports none of its assertions: {claim.claim_id}"
                )
            for assertion_id in covered:
                source_ids = {
                    source.source_id for source in assertions[assertion_id].source_refs
                }
                if citation.source_id in source_ids:
                    citation_coverage.add(assertion_id)
        if citation_coverage != support_ids:
            missing = sorted(support_ids - citation_coverage)
            raise ValueError(
                f"Draft claim assertions lack matching source passages: {missing}"
            )


def _assertions_conflict(left: EvidenceAssertion, right: EvidenceAssertion) -> bool:
    return (
        set(left.subject_entity_ids) == set(right.subject_entity_ids)
        and left.predicate == right.predicate
        and left.valid_from <= right.valid_to
        and right.valid_from <= left.valid_to
        and canonical_json_bytes(left.object) != canonical_json_bytes(right.object)
    )


def _validate_conflicts(
    content: DossierDraftContent,
    bundle: ApprovedEvidenceBundle,
) -> None:
    assertions = {assertion.assertion_id: assertion for assertion in bundle.assertions}
    for conflict in content.conflicts:
        unknown = set(conflict.assertion_ids) - assertions.keys()
        if unknown:
            raise ValueError(f"Conflict has unsupported assertion IDs: {sorted(unknown)}")
        items = [assertions[assertion_id] for assertion_id in conflict.assertion_ids]
        if not any(
            _assertions_conflict(left, right)
            for position, left in enumerate(items)
            for right in items[position + 1 :]
        ):
            raise ValueError(
                f"Conflict result does not reference contradictory assertions: "
                f"{conflict.conflict_id}"
            )
        coverage: set[str] = set()
        expected = set(conflict.assertion_ids)
        for citation in conflict.citations:
            coverage.update(_citation_assertion_ids(citation, bundle) & expected)
        if coverage != expected:
            raise ValueError(
                f"Conflict citations do not cover every assertion: {conflict.conflict_id}"
            )


def validate_draft(
    draft: DossierDraft,
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
) -> None:
    validate_bundle_against_curated(bundle, curated)
    if draft.bundle_id != bundle.bundle_id:
        raise ValueError("Draft bundle_id does not match the approved evidence bundle")
    bundle_hash = canonical_sha256(bundle)
    if draft.generation.evidence_bundle_sha256 != bundle_hash:
        raise ValueError("Draft evidence-bundle hash does not match")
    output_hash = canonical_sha256(draft.content)
    if draft.generation.output_sha256 != output_hash:
        raise ValueError("Draft output hash does not match")
    expected_id = _draft_id(draft.content, draft.generation)
    if draft.draft_id != expected_id:
        raise ValueError("Draft ID does not match its generation record")

    if draft.content.result == DossierDraftResult.DRAFT:
        if not bundle.assertions:
            raise ValueError("A dossier cannot be drafted from an empty evidence bundle")
        _validate_claims(draft.content, bundle)
    elif draft.content.result == DossierDraftResult.NO_EVIDENCE:
        if bundle.assertions or bundle.sources:
            raise ValueError("A no-evidence result requires an empty approved evidence bundle")
    else:
        _validate_conflicts(draft.content, bundle)


def _draft_id(
    content: DossierDraftContent,
    provenance: DossierGenerationProvenance,
) -> str:
    digest = canonical_sha256(
        {
            "content": content.model_dump(mode="json"),
            "generation": provenance.model_dump(mode="json"),
        }
    )
    return f"dossier-draft:{digest[:16]}"


def ingest_model_output(
    output: DossierDraftContent | dict[str, Any],
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
    *,
    prompt_version: str,
    prompt_sha256: str,
    model_identifier: str,
    generated_at: datetime,
    provider_response_id: str | None = None,
) -> DossierDraft:
    content = (
        output
        if isinstance(output, DossierDraftContent)
        else DossierDraftContent.model_validate(output)
    )
    generation = DossierGenerationProvenance(
        prompt_version=prompt_version,
        prompt_sha256=prompt_sha256,
        model_identifier=model_identifier,
        evidence_bundle_sha256=canonical_sha256(bundle),
        output_sha256=canonical_sha256(content),
        generated_at=generated_at,
        provider_response_id=provider_response_id,
    )
    draft = DossierDraft(
        draft_id=_draft_id(content, generation),
        bundle_id=bundle.bundle_id,
        content=content,
        generation=generation,
    )
    validate_draft(draft, bundle, curated)
    return draft


def review_draft(
    draft: DossierDraft,
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
    *,
    reviewed_by: str,
    reviewed_at: datetime,
    notes: str,
) -> DossierDraft:
    validate_draft(draft, bundle, curated)
    if draft.editorial_state != EditorialState.MACHINE_DRAFTED:
        raise ValueError("Only a machine draft can enter human review")
    if draft.content.result != DossierDraftResult.DRAFT:
        raise ValueError("No-evidence and conflicting-evidence results cannot be published")
    review = HumanDossierReview(
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        notes=notes,
        reviewed_claim_ids=[claim.claim_id for claim in draft.content.claims],
    )
    return DossierDraft.model_validate(
        {
            **draft.model_dump(mode="json"),
            "editorial_state": EditorialState.HUMAN_REVIEWED,
            "review": review.model_dump(mode="json"),
        }
    )


def reject_draft(
    draft: DossierDraft,
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
    *,
    reason: str,
    rejected_by: str,
    rejected_at: datetime,
) -> DossierDraft:
    validate_draft(draft, bundle, curated)
    if draft.editorial_state != EditorialState.MACHINE_DRAFTED:
        raise ValueError("Only a machine draft can be rejected")
    return DossierDraft.model_validate(
        {
            **draft.model_dump(mode="json"),
            "editorial_state": EditorialState.REJECTED,
            "rejection_reason": reason,
            "rejected_by": rejected_by,
            "rejected_at": rejected_at,
        }
    )


def publish_reviewed_draft(
    draft: DossierDraft,
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
    *,
    editorial_license_id: str,
    editorial_attribution: str,
    published_at: datetime,
) -> PublishedEditorialDossier:
    validate_draft(draft, bundle, curated)
    if draft.editorial_state != EditorialState.HUMAN_REVIEWED or draft.review is None:
        raise ValueError("Only a human-reviewed dossier draft can be published")
    if draft.content.result != DossierDraftResult.DRAFT or draft.content.title is None:
        raise ValueError("Only a complete dossier draft can be published")

    claim_assertion_ids = {
        assertion_id
        for claim in draft.content.claims
        for assertion_id in claim.supporting_assertion_ids
    }
    assertion_by_id = {
        assertion.assertion_id: assertion for assertion in bundle.assertions
    }
    feature_ids = sorted(
        {
            feature_id
            for assertion_id in claim_assertion_ids
            for feature_id in assertion_by_id[assertion_id].feature_ids
        }
    )
    entity_ids = sorted(
        {entity_id for claim in draft.content.claims for entity_id in claim.entity_ids}
    )
    used_passages = {
        (citation.source_id, citation.passage_id)
        for claim in draft.content.claims
        for citation in claim.citations
    }
    documents = [
        document
        for document in bundle.sources
        if any(
            (document.source_ref.source_id, passage.passage_id) in used_passages
            for passage in document.passages
        )
    ]
    extract = "\n\n".join(claim.text for claim in draft.content.claims)
    published_values = {
        "schema_version": "1.0.0",
        "source_draft_id": draft.draft_id,
        "dossier_kind": "generated_editorial",
        "editorial_state": "published",
        "title": draft.content.title,
        "language": draft.content.language,
        "entity_ids": entity_ids,
        "feature_ids": feature_ids,
        "content_role": "project_interpretation",
        "extract": extract,
        "claims": [claim.model_dump(mode="json") for claim in draft.content.claims],
        "content_checksum_sha256": hashlib.sha256(extract.encode("utf-8")).hexdigest(),
        "evidence_sources": [
            document.source_ref.model_dump(mode="json") for document in documents
        ],
        "evidence_attributions": [document.attribution for document in documents],
        "editorial_license_id": editorial_license_id,
        "editorial_attribution": editorial_attribution,
        "generation": draft.generation.model_dump(mode="json"),
        "review": draft.review.model_dump(mode="json"),
        "published_at": published_at,
    }
    candidate = PublishedEditorialDossier.model_validate(
        {
            "dossier_id": "palimpsest:editorial:0000000000000000",
            **published_values,
        }
    )
    normalized = candidate.model_dump(mode="json")
    normalized.pop("dossier_id")
    publication_hash = canonical_sha256(normalized)
    dossier = candidate.model_copy(
        update={"dossier_id": f"palimpsest:editorial:{publication_hash[:16]}"}
    )
    validate_published_dossier(dossier)
    return dossier


def validate_published_dossier(dossier: PublishedEditorialDossier) -> None:
    if dossier.extract != "\n\n".join(claim.text for claim in dossier.claims):
        raise ValueError("Published dossier extract does not match its reviewed claims")
    if (
        hashlib.sha256(dossier.extract.encode("utf-8")).hexdigest()
        != dossier.content_checksum_sha256
    ):
        raise ValueError("Published dossier content checksum does not match")
    expected_entities = sorted(
        {entity_id for claim in dossier.claims for entity_id in claim.entity_ids}
    )
    if dossier.entity_ids != expected_entities:
        raise ValueError("Published dossier entity IDs do not match its claims")
    if dossier.evidence_attributions != [
        source.citation for source in dossier.evidence_sources
    ]:
        raise ValueError("Published dossier evidence attribution differs from its sources")
    values = dossier.model_dump(mode="json")
    values.pop("dossier_id")
    expected_id = f"palimpsest:editorial:{canonical_sha256(values)[:16]}"
    if dossier.dossier_id != expected_id:
        raise ValueError("Published dossier ID does not match its immutable content")


def write_json(path: Path, value: Any, *, immutable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value) + b"\n"
    mode = "xb" if immutable else "wb"
    with path.open(mode) as handle:
        handle.write(payload)


def read_json_model(path: Path, model: type[Any]) -> Any:
    return model.model_validate_json(path.read_bytes())


def generate_with_openai(
    bundle: ApprovedEvidenceBundle,
    curated: CuratedRecords,
    *,
    prompt: str,
    prompt_version: str,
    model_identifier: str,
    api_key: str,
    generated_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> DossierDraft:
    validate_bundle_against_curated(bundle, curated)
    if not api_key:
        raise ValueError("An OpenAI API key is required for real dossier generation")
    request = {
        "model": model_identifier,
        "store": False,
        "instructions": prompt,
        "input": (
            "Approved evidence bundle (the only allowed historical context):\n"
            + canonical_json_bytes(bundle).decode("utf-8")
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "palimpsest_dossier_draft",
                "strict": True,
                "schema": _openai_output_schema(),
            }
        },
    }
    owns_client = client is None
    active_client = client or httpx.Client(timeout=120)
    try:
        response = active_client.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request,
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            active_client.close()
    if payload.get("status") != "completed":
        raise ValueError(f"OpenAI response did not complete: {payload.get('status')}")
    output_texts = [
        part.get("text")
        for item in payload.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text" and isinstance(part.get("text"), str)
    ]
    if len(output_texts) != 1:
        raise ValueError("OpenAI response must contain exactly one structured output")
    try:
        output = json.loads(output_texts[0])
    except json.JSONDecodeError as error:
        raise ValueError("OpenAI structured output is not valid JSON") from error
    actual_model = payload.get("model")
    if not isinstance(actual_model, str) or not actual_model:
        raise ValueError("OpenAI response omitted its model identifier")
    response_id = payload.get("id")
    if response_id is not None and not isinstance(response_id, str):
        raise ValueError("OpenAI response ID is malformed")
    return ingest_model_output(
        output,
        bundle,
        curated,
        prompt_version=prompt_version,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        model_identifier=actual_model,
        generated_at=generated_at or datetime.now(UTC),
        provider_response_id=response_id,
    )


def api_key_from_environment(variable: str = "OPENAI_API_KEY") -> str:
    value = os.environ.get(variable)
    if not value:
        raise ValueError(f"{variable} is required for real dossier generation")
    return value
