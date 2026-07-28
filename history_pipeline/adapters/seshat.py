from __future__ import annotations

import hashlib
import html
import re
from typing import Any
from urllib.parse import urlencode, urljoin

import orjson
from pydantic import ValidationError

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import source_reference
from history_pipeline.models import (
    AssertionEvidenceBasis,
    AssertionObject,
    AssertionObjectKind,
    Confidence,
    ConfidenceGrade,
    DatePrecision,
    EvidenceAssertion,
    ReviewStatus,
)
from history_pipeline.storage import RawAsset

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def _plain_text(value: object) -> str:
    text = html.unescape(str(value or "").replace("<br>", "\n").replace("<br/>", "\n"))
    return _WHITESPACE.sub(" ", _HTML_TAG.sub(" ", text)).strip()


def _explanation_and_citations(value: object) -> tuple[str | None, list[str]]:
    parts = str(value or "").split("§REF§")
    explanation = _plain_text(" ".join(parts[0::2]))
    citations = [_plain_text(part) for part in parts[1::2] if _plain_text(part)]
    return explanation or None, list(dict.fromkeys(citations))


def _year(value: object, fallback: object) -> int:
    selected = fallback if value is None else value
    year = int(str(selected))
    if year == 0:
        raise ValueError("Seshat year zero cannot enter the no-year-zero chronology")
    return year


class SeshatApiAdapter:
    """Snapshot selected public Seshat variables as linkable structured assertions."""

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        variables = source.options.get("variables")
        if not isinstance(variables, list) or not variables:
            raise ValueError(f"{source.id}: seshat_api requires a non-empty variables list")

        result = AdapterResult()
        terms_url = source.options.get("terms_url")
        if isinstance(terms_url, str) and terms_url:
            result.raw_assets.append(
                context.downloads.fetch(
                    terms_url,
                    context.raw_source_dir / "terms.html",
                    reuse_cached=True,
                )
            )

        for definition in variables:
            if not isinstance(definition, dict):
                raise ValueError(f"{source.id}: every Seshat variable must be an object")
            endpoint = str(definition.get("endpoint", "")).strip("/")
            field = str(definition.get("field", "")).strip()
            label = str(definition.get("label", "")).strip()
            value_kind = str(definition.get("kind", "categorical"))
            if not endpoint or not field or not label:
                raise ValueError(
                    f"{source.id}: Seshat variables require endpoint, field, and label"
                )
            records, assets = self._fetch_collection(context, endpoint)
            result.raw_assets.extend(assets)
            selected = records[:limit] if limit else records
            for record, record_asset in selected:
                record_id = str(record.get("id", "unknown"))
                try:
                    assertion = self._normalize(
                        context,
                        endpoint=endpoint,
                        field=field,
                        label=label,
                        value_kind=value_kind,
                        unit=str(definition.get("unit", "")).strip() or None,
                        record=record,
                        asset=record_asset,
                    )
                    if assertion is not None:
                        result.evidence_assertions.append(assertion)
                except (KeyError, TypeError, ValueError, ValidationError) as error:
                    result.rejections.append(
                        RejectedRecord(
                            source.id,
                            f"{endpoint}:{record_id}",
                            "normalize",
                            str(error),
                        )
                    )
        return result

    def _fetch_collection(
        self, context: AdapterContext, endpoint: str
    ) -> tuple[list[tuple[dict[str, Any], RawAsset]], list[RawAsset]]:
        page_size = int(context.source.options.get("page_size", 1000))
        url = urljoin(str(context.source.url), endpoint + "/")
        url = f"{url}?{urlencode({'page_size': page_size})}"
        page = 1
        records: list[tuple[dict[str, Any], RawAsset]] = []
        assets: list[RawAsset] = []
        while url:
            destination = (
                context.raw_source_dir
                / endpoint.replace("/", "__")
                / f"page-{page:04d}.json"
            )
            asset = context.downloads.fetch(url, destination, reuse_cached=True)
            assets.append(asset)
            payload = orjson.loads(asset.path.read_bytes())
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ValueError(f"{context.source.id}: malformed Seshat page {url}")
            records.extend(
                (item, asset) for item in payload["results"] if isinstance(item, dict)
            )
            next_url = payload.get("next")
            if next_url is not None and not isinstance(next_url, str):
                raise ValueError(f"{context.source.id}: malformed Seshat pagination link")
            url = next_url or ""
            page += 1
        return records, assets

    def _normalize(
        self,
        context: AdapterContext,
        *,
        endpoint: str,
        field: str,
        label: str,
        value_kind: str,
        unit: str | None,
        record: dict[str, Any],
        asset: RawAsset,
    ) -> EvidenceAssertion | None:
        polity = record["polity"]
        if not isinstance(polity, dict):
            raise ValueError("Seshat observation has no polity object")
        polity_code = str(polity["name"]).strip()
        if not polity_code:
            raise ValueError("Seshat observation has no polity code")
        valid_from = _year(record.get("year_from"), polity.get("start_year"))
        valid_to = _year(record.get("year_to"), polity.get("end_year"))
        if valid_from > valid_to:
            raise ValueError("Seshat observation begins after it ends")

        if value_kind == "number_range":
            lower = record.get(f"{field}_from")
            upper = record.get(f"{field}_to")
            if lower is None and upper is None:
                return None
            assertion_object = AssertionObject(
                kind=AssertionObjectKind.NUMBER_RANGE,
                value_from=lower,
                value_to=upper,
                unit=unit or "value",
            )
        elif value_kind == "categorical":
            value = record.get(field)
            if value is None or not str(value).strip():
                return None
            assertion_object = AssertionObject(
                kind=AssertionObjectKind.TEXT,
                value=str(value).strip(),
            )
        else:
            raise ValueError(f"Unsupported Seshat value kind: {value_kind}")

        explanation, citations = _explanation_and_citations(record.get("description"))
        excerpt_checksum = (
            hashlib.sha256(explanation.encode("utf-8")).hexdigest()
            if explanation
            else None
        )
        record_id = str(record["id"])
        endpoint_url = urljoin(str(context.source.url), endpoint + "/")
        uncertain = bool(record.get("is_uncertain"))
        disputed = bool(record.get("is_disputed"))
        qualifiers = [
            word
            for present, word in ((uncertain, "uncertain"), (disputed, "disputed"))
            if present
        ]
        rationale = (
            "Seshat marks this coding as " + " and ".join(qualifiers) + "."
            if qualifiers
            else "Seshat publishes this machine-readable coding with an explanatory note."
        )
        digest = hashlib.sha256(f"{endpoint}:{record_id}".encode()).hexdigest()[:16]
        return EvidenceAssertion(
            assertion_id=f"assertion:seshat:{digest}",
            # The pipeline replaces this acquisition key with the canonical entity and feature
            # identifiers after Cliopatria has been normalized.
            subject_entity_ids=[f"seshat-polity:{polity_code}"],
            feature_ids=[],
            predicate=field,
            object=assertion_object,
            valid_from=valid_from,
            valid_to=valid_to,
            date_precision=(
                DatePrecision.YEAR if valid_from == valid_to else DatePrecision.RANGE
            ),
            confidence=Confidence(
                grade=ConfidenceGrade.C if qualifiers else ConfidenceGrade.B,
                rationale=rationale,
            ),
            evidence_basis=AssertionEvidenceBasis.SCHOLARLY_ASSERTION,
            review_status=ReviewStatus.CONTESTED if disputed else ReviewStatus.PROVISIONAL,
            source_refs=[
                source_reference(
                    context.source,
                    asset,
                    f"{endpoint}:{record_id}",
                    url=f"{endpoint_url}{record_id}/",
                    title=f"Seshat: {label}",
                    modified=True,
                )
            ],
            source_excerpt=explanation,
            source_excerpt_checksum_sha256=excerpt_checksum,
            source_citations=citations,
        )
