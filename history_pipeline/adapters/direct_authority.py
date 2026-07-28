from __future__ import annotations

import hashlib
from typing import Any, Literal, cast

import orjson

from history_pipeline.adapters.base import AdapterContext, AdapterResult
from history_pipeline.adapters.common import source_reference
from history_pipeline.models import (
    AuthorityMatch,
    Confidence,
    ConfidenceGrade,
    RightsReference,
    RightsScope,
    TransformationStep,
)
from history_pipeline.storage import RawAsset

ADAPTER_VERSION = "1.0.0"


class DirectAuthorityAdapter:
    """Publish reviewed links fetched from their actual authority, not a discovery mirror."""

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        if source.rights is None:
            raise ValueError(f"{source.id}: direct authority metadata rights are required")
        if not source.version:
            raise ValueError(f"{source.id}: direct authority version is required")
        configured = source.options.get("records")
        if not isinstance(configured, list) or not configured:
            raise ValueError(f"{source.id}: direct authority records are required")
        records = configured[:limit] if limit is not None else configured
        result = AdapterResult()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"{source.id}: direct authority record must be an object")
            authority_id = str(record.get("authority_id", "")).strip()
            namespace = str(record.get("authority_namespace", "")).strip()
            url = str(record.get("url", "")).strip()
            expected_checksum = str(record.get("checksum_sha256", "")).strip()
            expected_content_checksum = str(
                record.get("content_checksum_sha256", "")
            ).strip()
            if (
                not authority_id
                or not namespace
                or not url.startswith("https://")
                or (
                    len(expected_checksum) != 64
                    and len(expected_content_checksum) != 64
                )
            ):
                raise ValueError(f"{source.id}: direct authority record is incomplete")
            asset = context.downloads.fetch(
                url,
                context.raw_source_dir / f"{index:02d}-{namespace}.json",
                reuse_cached=True,
            )
            if expected_checksum and asset.checksum_sha256 != expected_checksum:
                raise ValueError(
                    f"{source.id}: checksum changed for direct authority {authority_id}"
                )
            payload = orjson.loads(asset.path.read_bytes())
            canonical_payload = (
                payload.get("elements")
                if namespace == "osm" and isinstance(payload, dict)
                else payload
            )
            content_checksum = hashlib.sha256(
                orjson.dumps(canonical_payload, option=orjson.OPT_SORT_KEYS)
            ).hexdigest()
            if (
                expected_content_checksum
                and content_checksum != expected_content_checksum
            ):
                raise ValueError(
                    f"{source.id}: canonical content changed for {authority_id}"
                )
            self._validate_payload(namespace, authority_id, record, payload)
            result.raw_assets.append(asset)
            result.authority_matches.append(
                self._match(context, asset, record, authority_id, namespace)
            )
        return result

    @staticmethod
    def _validate_payload(
        namespace: str,
        authority_id: str,
        record: dict[str, Any],
        payload: Any,
    ) -> None:
        expected_label = str(record.get("label", "")).strip()
        if not expected_label or not isinstance(payload, dict):
            raise ValueError(f"{authority_id}: authority response is malformed")
        if namespace == "tgn":
            expected_numeric_id = authority_id.removeprefix("tgn:")
            if str(payload.get("id", "")).rstrip("/").split("/")[-1] != expected_numeric_id:
                raise ValueError(f"{authority_id}: Getty response identifier differs")
            names = {
                str(item.get("content", "")).casefold()
                for item in payload.get("identified_by", [])
                if isinstance(item, dict) and item.get("type") == "Name"
            }
            if expected_label.casefold() not in names:
                raise ValueError(f"{authority_id}: Getty response omitted reviewed label")
        elif namespace == "osm":
            expected_osm_id = int(authority_id.removeprefix("osm:node:"))
            elements = payload.get("elements")
            if not isinstance(elements, list):
                raise ValueError(f"{authority_id}: OSM response omitted elements")
            matching = [
                item
                for item in elements
                if isinstance(item, dict)
                and item.get("type") == "node"
                and item.get("id") == expected_osm_id
            ]
            if (
                len(matching) != 1
                or str((matching[0].get("tags") or {}).get("name", "")).casefold()
                != expected_label.casefold()
            ):
                raise ValueError(f"{authority_id}: OSM response differs from review")
        else:
            raise ValueError(f"{authority_id}: unsupported direct authority namespace")

    @staticmethod
    def _match(
        context: AdapterContext,
        asset: RawAsset,
        record: dict[str, Any],
        authority_id: str,
        namespace: str,
    ) -> AuthorityMatch:
        source = context.source
        subject_id = str(record.get("subject_id", "")).strip()
        query_id = str(record.get("discovery_query_id", "")).strip()
        label = str(record.get("label", "")).strip()
        relation = str(record.get("relation", "")).strip()
        rationale = str(record.get("rationale", "")).strip()
        if (
            not subject_id
            or not query_id.startswith("query:")
            or relation != "close_match"
            or not rationale
        ):
            raise ValueError(f"{authority_id}: reviewed relation metadata is incomplete")
        digest = hashlib.sha256(
            f"{source.id}\0{subject_id}\0{authority_id}".encode()
        ).hexdigest()[:16]
        if source.rights is None:
            raise ValueError(f"{source.id}: direct authority metadata rights are required")
        rights = source.rights.metadata
        typed_relation = cast(Literal["close_match"], relation)
        return AuthorityMatch(
            match_id=f"match:{digest}",
            subject_id=subject_id,
            authority_id=authority_id,
            authority_namespace=namespace,
            label=label,
            relation=typed_relation,
            review_status="accepted",
            confidence_score=90,
            confidence=Confidence(grade=ConfidenceGrade.B, rationale=rationale),
            source_ref=source_reference(
                source,
                asset,
                authority_id,
                url=str(record["url"]),
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
                    operation="verify_direct_authority_link",
                    tool="history_pipeline.adapters.direct_authority",
                    tool_version=ADAPTER_VERSION,
                    input_record_ids=[query_id, authority_id],
                    parameters={
                        "discovery_route": "World Historical Gazetteer reconciliation",
                        "identity_decision": "editorially reviewed close match",
                    },
                )
            ],
        )
