from __future__ import annotations

from typing import Any, cast

import orjson
from pydantic import ValidationError
from shapely.geometry import mapping, shape

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import confidence, source_reference, stable_feature_id
from history_pipeline.models import HistoricalFeature


class LinkedPlacesAdapter:
    """Ingest a reviewed Linked Places Format export.

    The adapter deliberately requires a declared chronology and rejects undated records. It is
    intended for selected WHG or Pelagios-compatible datasets, not an unbounded API crawl.
    """

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        if source.defaults is None:
            raise ValueError(f"{source.id}: Linked Places adapter requires defaults")
        chronology = source.options.get("chronology")
        if chronology not in {"historical", "astronomical"}:
            raise ValueError(
                f"{source.id}: chronology must be explicitly historical or astronomical"
            )
        asset = context.downloads.fetch(
            str(source.url), context.raw_source_dir / "linked-places.json"
        )
        with asset.path.open("rb") as handle:
            payload = orjson.loads(handle.read())
        records = self._records(payload)
        if limit is not None:
            records = records[:limit]

        result = AdapterResult(raw_assets=[asset])
        for index, record in enumerate(records):
            record_id = str(record.get("@id") or record.get("id") or index)
            try:
                raw_geometry = record.get("geometry")
                if not raw_geometry:
                    geometries = record.get("geometries") or []
                    if len(geometries) != 1:
                        raise ValueError(
                            "record must have one geometry; split multiple attestations upstream"
                        )
                    raw_geometry = geometries[0].get("geometry", geometries[0])
                geometry = shape(raw_geometry)
                if geometry.is_empty:
                    raise ValueError("empty geometry")
                valid_from, valid_to = self._date_range(record, chronology)
                properties = record.get("properties") or {}
                title = str(properties.get("title") or record.get("title") or "").strip()
                if not title:
                    raise ValueError("place has no title")
                names = self._names(record, title)
                result.features.append(
                    HistoricalFeature(
                        feature_id=stable_feature_id(
                            source.id, record_id, valid_from, valid_to, geometry.wkb
                        ),
                        kind=source.defaults.kind,
                        spatial_meaning=source.defaults.spatial_meaning,
                        names=names,
                        valid_from=valid_from,
                        valid_to=valid_to,
                        date_precision=source.defaults.date_precision,
                        geometry=mapping(geometry),
                        temporal_confidence=confidence(
                            source.defaults.temporal_confidence, source.title, "time"
                        ),
                        spatial_confidence=confidence(
                            source.defaults.spatial_confidence, source.title, "geometry"
                        ),
                        interpretive_confidence=confidence(
                            source.defaults.interpretive_confidence,
                            source.title,
                            "interpretation",
                        ),
                        review_status=source.defaults.review_status,
                        source_refs=[
                            source_reference(
                                source,
                                asset,
                                record_id,
                                url=record_id if record_id.startswith("http") else None,
                                title=f"{source.title}: {title}",
                            )
                        ],
                        min_display_zoom=source.defaults.min_display_zoom,
                        properties={
                            "types": record.get("types", []),
                            "links": record.get("links", []),
                            "relations": record.get("relations", []),
                            "source_properties": properties,
                        },
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                result.rejections.append(
                    RejectedRecord(source.id, record_id, "normalize", str(error))
                )
        return result

    @staticmethod
    def _records(payload: Any) -> list[dict[str, Any]]:
        records: Any
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict) and payload.get("type") == "Feature":
            records = [payload]
        elif isinstance(payload, dict):
            records = payload.get("features") or payload.get("@graph")
        else:
            records = None
        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise ValueError("Unexpected Linked Places document structure")
        return cast(list[dict[str, Any]], records)

    @staticmethod
    def _date_range(record: dict[str, Any], chronology: str) -> tuple[int, int]:
        timespans = (record.get("when") or {}).get("timespans") or []
        starts: list[int] = []
        ends: list[int] = []
        for timespan in timespans:
            start = timespan.get("start") or {}
            end = timespan.get("end") or {}
            start_value = start.get("earliest", start.get("latest"))
            end_value = end.get("latest", end.get("earliest"))
            if start_value not in (None, ""):
                starts.append(_year(int(str(start_value)), chronology))
            if end_value not in (None, ""):
                ends.append(_year(int(str(end_value)), chronology))
        if not starts or not ends:
            raise ValueError("place has no bounded timespan")
        return min(starts), max(ends)

    @staticmethod
    def _names(record: dict[str, Any], title: str) -> dict[str, str]:
        names = {"und": title}
        for item in record.get("names") or []:
            value = item.get("toponym")
            if value:
                names.setdefault(str(item.get("lang") or "und"), str(value))
        return names


def _year(value: int, chronology: str) -> int:
    if chronology == "astronomical" and value <= 0:
        return value - 1
    if value == 0:
        raise ValueError("historical chronology cannot contain year zero")
    return value
