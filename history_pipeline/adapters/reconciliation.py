from __future__ import annotations

import hashlib
from typing import Any, Literal, cast

import orjson
from pydantic import ValidationError

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import source_reference, verify_expected_checksum
from history_pipeline.licenses import enforce_source_license
from history_pipeline.models import (
    AuthorityMatch,
    Confidence,
    ConfidenceGrade,
    RightsReference,
    RightsScope,
    TransformationStep,
)

ADAPTER_VERSION = "1.0.0"


class AuthorityReconciliationAdapter:
    """Normalize a checksummed, editorially reviewed reconciliation response snapshot."""

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        if source.rights is None:
            raise ValueError(f"{source.id}: scoped metadata rights are required")
        if not source.version or not source.expected_checksum_sha256:
            raise ValueError(
                f"{source.id}: reconciliation source version and checksum are required"
            )
        enforce_source_license(
            source.rights.metadata.license_id,
            source.license_reviewed,
            context.pipeline.license_policy,
            source.id,
        )
        asset = context.downloads.fetch(
            str(source.url),
            context.raw_source_dir / "reconciliation.json",
        )
        verify_expected_checksum(source, asset)
        with asset.path.open("rb") as handle:
            payload = orjson.loads(handle.read())
        if not isinstance(payload, dict):
            raise ValueError("Reconciliation snapshot must be a JSON object")
        self._validate_envelope(context, payload)
        queries = payload.get("queries")
        if not isinstance(queries, list):
            raise ValueError("Reconciliation snapshot queries must be an array")
        if limit is not None:
            queries = queries[:limit]

        result = AdapterResult(raw_assets=[asset])
        allowed_namespaces = {
            str(value) for value in source.options.get("allowed_authority_namespaces", [])
        }
        if not allowed_namespaces:
            raise ValueError(
                f"{source.id}: allowed_authority_namespaces must be explicit"
            )
        for query_index, query in enumerate(queries):
            query_id = str(
                query.get("query_id") if isinstance(query, dict) else query_index
            )
            try:
                if not isinstance(query, dict):
                    raise ValueError("query must be an object")
                subject_id = str(query["subject_id"]).strip()
                if not subject_id:
                    raise ValueError("subject_id is empty")
                candidates = query.get("result")
                if not isinstance(candidates, list):
                    raise ValueError("query result must be an array")
                for candidate in candidates:
                    result.authority_matches.append(
                        self._match(
                            context,
                            asset,
                            payload,
                            query_id,
                            subject_id,
                            candidate,
                            allowed_namespaces,
                        )
                    )
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                result.rejections.append(
                    RejectedRecord(source.id, query_id, "normalize", str(error))
                )
        return result

    @staticmethod
    def _validate_envelope(
        context: AdapterContext,
        payload: dict[str, Any],
    ) -> None:
        source = context.source
        if payload.get("source_version") != source.version:
            raise ValueError(
                f"{source.id}: reconciliation source_version is missing or incompatible"
            )
        if payload.get("score_scale") != "0-100":
            raise ValueError(f"{source.id}: score_scale must be explicitly 0-100")
        rights = payload.get("rights")
        if not isinstance(rights, dict):
            raise ValueError(f"{source.id}: reconciliation snapshot has no rights object")
        expected = source.rights.metadata if source.rights else None
        if expected is None or rights.get("license_id") != expected.license_id:
            raise ValueError(f"{source.id}: reconciliation metadata licence differs")
        if rights.get("attribution") != expected.attribution:
            raise ValueError(f"{source.id}: reconciliation attribution differs")

    @staticmethod
    def _match(
        context: AdapterContext,
        asset: Any,
        payload: dict[str, Any],
        query_id: str,
        subject_id: str,
        candidate: Any,
        allowed_namespaces: set[str],
    ) -> AuthorityMatch:
        if not isinstance(candidate, dict):
            raise ValueError("candidate must be an object")
        source = context.source
        authority_id = str(candidate["id"]).strip()
        label = str(candidate["name"]).strip()
        namespace = str(candidate["authority_namespace"]).strip()
        if namespace not in allowed_namespaces:
            raise ValueError(f"authority namespace is not allowed: {namespace}")
        score = float(candidate["score"])
        if not 0 <= score <= 100:
            raise ValueError("candidate score is outside the declared 0-100 scale")
        review_status = str(candidate["review_status"])
        if review_status not in {"proposed", "accepted", "rejected"}:
            raise ValueError("candidate review_status must be explicit")
        relation = str(candidate.get("relation", "candidate"))
        if relation not in {"exact_match", "close_match", "candidate"}:
            raise ValueError("candidate relation is unsupported")
        if review_status == "accepted" and relation == "candidate":
            raise ValueError("accepted reconciliation must declare its match relation")
        typed_status = cast(
            Literal["proposed", "accepted", "rejected"], review_status
        )
        typed_relation = cast(
            Literal["exact_match", "close_match", "candidate"], relation
        )
        digest = hashlib.sha256(
            f"{source.id}\0{subject_id}\0{authority_id}".encode()
        ).hexdigest()[:16]
        rights = source.rights.metadata if source.rights else None
        if rights is None:
            raise ValueError("metadata rights are missing")
        return AuthorityMatch(
            match_id=f"match:{digest}",
            subject_id=subject_id,
            authority_id=authority_id,
            authority_namespace=namespace,
            label=label,
            relation=typed_relation,
            review_status=typed_status,
            confidence_score=score,
            confidence=Confidence(
                grade=_confidence_grade(score),
                rationale=(
                    f"{source.title} candidate score {score:g}/100; "
                    f"editorial status is {review_status}"
                ),
            ),
            source_ref=source_reference(
                source,
                asset,
                authority_id,
                url=str(candidate.get("uri") or source.url),
                title=f"{source.title}: {label}",
            ),
            rights=RightsReference(
                scope=RightsScope.METADATA,
                license_id=rights.license_id,
                attribution=rights.attribution,
                rights_uri=rights.rights_uri,
            ),
            lineage=[
                TransformationStep(
                    operation="normalize_reconciliation_candidate",
                    tool="history_pipeline.adapters.reconciliation",
                    tool_version=ADAPTER_VERSION,
                    input_record_ids=[query_id, authority_id],
                    parameters={
                        "provider_format": payload.get("provider_format"),
                        "score_scale": "0-100",
                    },
                )
            ],
        )


def _confidence_grade(score: float) -> ConfidenceGrade:
    if score >= 95:
        return ConfidenceGrade.A
    if score >= 80:
        return ConfidenceGrade.B
    if score >= 60:
        return ConfidenceGrade.C
    return ConfidenceGrade.D
