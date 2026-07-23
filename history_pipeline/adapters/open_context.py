from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import orjson
from pydantic import ValidationError
from shapely.geometry import Point, mapping, shape

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import confidence, source_reference, stable_feature_id
from history_pipeline.models import HistoricalFeature


class OpenContextAdapter:
    """Ingest explicitly curated Open Context searches.

    Broad harvesting is intentionally unsupported. Each configuration must provide
    bounded query URLs and a record limit, and human-remains-related records are rejected.
    """

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        if source.defaults is None:
            raise ValueError(f"{source.id}: Open Context adapter requires defaults")
        queries = source.options.get("queries") or []
        if not queries:
            raise ValueError(f"{source.id}: at least one curated query is required")
        maximum = min(
            limit or int(source.options.get("max_records", 1000)),
            int(source.options.get("max_records", 1000)),
        )
        decimals = int(source.options.get("public_coordinate_decimals", 3))
        result = AdapterResult()
        seen = 0
        for query_index, query_url in enumerate(queries):
            if seen >= maximum:
                break
            page = 1
            while seen < maximum:
                page_size = min(100, maximum - seen)
                paged_url = _with_query(str(query_url), rows=page_size, page=page)
                asset = context.downloads.fetch(
                    paged_url,
                    context.raw_source_dir / f"query-{query_index + 1}-page-{page}.json",
                )
                result.raw_assets.append(asset)
                with asset.path.open("rb") as handle:
                    payload = orjson.loads(handle.read())
                page_features = payload.get("features", [])
                if not page_features:
                    break
                for feature in page_features:
                    if seen >= maximum:
                        break
                    properties = feature.get("properties", {})
                    record_id = str(
                        properties.get("uri") or feature.get("slug") or feature.get("id")
                    )
                    try:
                        if (
                            feature.get("oc-api:human-remains-related") is True
                            or properties.get("oc-api:human-remains-related") is True
                        ):
                            raise ValueError("sensitive human-remains-related record excluded")
                        raw_geometry = shape(feature["geometry"])
                        if raw_geometry.is_empty:
                            raise ValueError("empty geometry")
                        point = raw_geometry.representative_point()
                        public_point = Point(
                            _round(point.x, decimals), _round(point.y, decimals)
                        )
                        when = feature.get("when") or {}
                        valid_from = _iso_year_to_historical(int(when["start"]))
                        valid_to = _iso_year_to_historical(int(when["stop"]))
                        label = str(
                            feature.get("label") or properties.get("label") or record_id
                        )
                        canonical = HistoricalFeature(
                            feature_id=stable_feature_id(
                                source.id, record_id, valid_from, valid_to, public_point.wkb
                            ),
                            kind=source.defaults.kind,
                            spatial_meaning=source.defaults.spatial_meaning,
                            names={"und": label},
                            valid_from=valid_from,
                            valid_to=valid_to,
                            date_precision=source.defaults.date_precision,
                            geometry=mapping(public_point),
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
                                    url=str(
                                        properties.get("href")
                                        or feature.get("rdfs:isDefinedBy")
                                        or source.url
                                    ),
                                    title=f"Open Context: {label}",
                                ),
                            ],
                            min_display_zoom=source.defaults.min_display_zoom,
                            properties={
                                "item_category": properties.get("item category"),
                                "project_label": properties.get("project label"),
                                "context_label": properties.get("context label"),
                                "coordinate_precision_decimals": decimals,
                                "source_geometry_type": raw_geometry.geom_type,
                            },
                        )
                        result.features.append(canonical)
                        seen += 1
                    except (KeyError, TypeError, ValueError, ValidationError) as error:
                        result.rejections.append(
                            RejectedRecord(source.id, record_id, "normalize", str(error))
                        )
                if len(page_features) < page_size:
                    break
                page += 1
        return result


def _with_query(url: str, **updates: Any) -> str:
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update({key: str(value) for key, value in updates.items()})
    query.setdefault("type", "subjects")
    query.setdefault("response", "geo-record")
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def _iso_year_to_historical(value: int) -> int:
    # Open Context follows ISO 8601 astronomical numbering: 0000 is 1 BCE,
    # -0001 is 2 BCE. The canonical contract uses historical BCE/CE integers.
    return value - 1 if value <= 0 else value


def _round(value: float, decimals: int) -> float:
    quantizer = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP))
