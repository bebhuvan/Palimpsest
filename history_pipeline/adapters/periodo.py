from __future__ import annotations

from typing import Any

import orjson
from pydantic import HttpUrl, ValidationError

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import source_reference, verify_expected_checksum
from history_pipeline.models import HistoricalPeriodDefinition, PeriodSpatialCoverage


class PeriodoAdapter:
    """Normalize attributed PeriodO definitions without treating them as global facts."""

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        asset = context.downloads.fetch(
            str(context.source.url), context.raw_source_dir / "periodo-dataset.json"
        )
        verify_expected_checksum(context.source, asset)
        payload = orjson.loads(asset.path.read_bytes())
        authorities = payload.get("authorities") if isinstance(payload, dict) else None
        if not isinstance(authorities, dict):
            raise ValueError("PeriodO dataset must contain an authorities object")
        result = AdapterResult(raw_assets=[asset])
        seen = 0
        for authority_key, authority in sorted(authorities.items()):
            if not isinstance(authority, dict):
                continue
            authority_id = str(authority.get("id") or authority_key)
            raw_source = authority.get("source")
            source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
            periods = authority.get("periods")
            if not isinstance(periods, dict):
                continue
            for period_key, period in sorted(periods.items()):
                if limit is not None and seen >= limit:
                    return result
                seen += 1
                period_id = (
                    str(period.get("id") or period_key)
                    if isinstance(period, dict)
                    else str(period_key)
                )
                try:
                    if not isinstance(period, dict):
                        raise ValueError("period must be an object")
                    result.periods.append(
                        self._normalize(
                            context,
                            asset,
                            authority_id,
                            period_id,
                            source,
                            period,
                        )
                    )
                except (TypeError, ValueError, ValidationError) as error:
                    result.rejections.append(
                        RejectedRecord(context.source.id, period_id, "normalize", str(error))
                    )
        return result

    @staticmethod
    def _normalize(
        context: AdapterContext,
        asset: Any,
        authority_id: str,
        period_id: str,
        authority_source: dict[str, Any],
        period: dict[str, Any],
    ) -> HistoricalPeriodDefinition:
        start = _year(period, "start")
        stop = _year(period, "stop")
        labels = _labels(period)
        citation = _citation(authority_source, authority_id)
        creators = _people(authority_source.get("creators"))
        if not creators and isinstance(authority_source.get("partOf"), dict):
            creators = _people(authority_source["partOf"].get("creators"))
        coverage: list[PeriodSpatialCoverage] = []
        for item in period.get("spatialCoverage") or []:
            if not isinstance(item, dict) or not str(item.get("label") or "").strip():
                continue
            uri = str(item.get("id") or "").strip() or None
            qid = _wikidata_qid(uri)
            coverage.append(
                PeriodSpatialCoverage(
                    label=str(item["label"]).strip(),
                    entity_id=f"wikidata:{qid}" if qid else None,
                    source_uri=HttpUrl(uri) if uri else None,
                )
            )
        permalink = f"https://n2t.net/ark:/99152/{period_id}"
        notes = [
            str(value).strip()
            for value in (period.get("note"), period.get("editorialNote"))
            if str(value or "").strip()
        ]
        return HistoricalPeriodDefinition(
            period_id=f"periodo:{period_id}",
            authority_id=f"periodo:{authority_id}",
            labels=labels,
            valid_from=start,
            valid_to=stop,
            start_label=str(period.get("start", {}).get("label") or start),
            stop_label=str(period.get("stop", {}).get("label") or stop),
            spatial_coverage=coverage,
            spatial_coverage_description=(
                str(period["spatialCoverageDescription"]).strip()
                if period.get("spatialCoverageDescription")
                else None
            ),
            authority_citation=citation,
            authority_creators=creators,
            source_locator=(
                str(authority_source["locator"]).strip()
                if authority_source.get("locator")
                else None
            ),
            notes=notes,
            broader_period_ids=_period_ids(period.get("broader")),
            narrower_period_ids=_period_ids(period.get("narrower")),
            same_as=[HttpUrl(value) for value in _urls(period.get("sameAs"))],
            source_ref=source_reference(
                context.source,
                asset,
                period_id,
                url=permalink,
                title=f"PeriodO: {next(iter(labels.values()))[0]}",
            ),
        )


def _year(period: dict[str, Any], key: str) -> int:
    value = period.get(key)
    if not isinstance(value, dict) or not isinstance(value.get("in"), dict):
        raise ValueError(f"period has no bounded {key} year")
    raw_year = value["in"].get("year")
    if raw_year is None:
        raise ValueError(f"period has no bounded {key} year")
    year = int(raw_year)
    return -1 if year == 0 else year


def _labels(period: dict[str, Any]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    localized = period.get("localizedLabels")
    if isinstance(localized, dict):
        for language, values in localized.items():
            if isinstance(values, list):
                cleaned = list(
                    dict.fromkeys(
                        str(value).strip() for value in values if str(value).strip()
                    )
                )
                if cleaned:
                    labels[str(language)] = cleaned
    label = str(period.get("label") or "").strip()
    language = str(period.get("languageTag") or "und")
    if label:
        labels.setdefault(language, [])
        if label not in labels[language]:
            labels[language].insert(0, label)
    if not labels:
        raise ValueError("period has no label")
    return labels


def _citation(source: dict[str, Any], authority_id: str) -> str:
    if source.get("citation"):
        return str(source["citation"]).strip()
    part_of = source.get("partOf")
    work: dict[str, Any] = part_of if isinstance(part_of, dict) else source
    parts = [*_people(work.get("creators")), str(work.get("title") or "").strip()]
    if work.get("yearPublished"):
        parts.append(str(work["yearPublished"]))
    citation = ". ".join(part for part in parts if part)
    return citation or f"PeriodO authority {authority_id}"


def _people(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("name")).strip()
        for item in value
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]


def _period_ids(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [f"periodo:{item}" for item in values if isinstance(item, str) and item]


def _urls(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, str) and item.startswith(("http://", "https://"))]


def _wikidata_qid(value: str | None) -> str | None:
    if not value:
        return None
    tail = value.rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.startswith("Q") and tail[1:].isdigit() else None
