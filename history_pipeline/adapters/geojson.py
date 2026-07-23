from __future__ import annotations

import geopandas as gpd
from pydantic import ValidationError
from shapely.geometry import mapping

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import (
    clean_scalar,
    confidence,
    source_reference,
    stable_feature_id,
)
from history_pipeline.models import HistoricalFeature


class GeoJsonAdapter:
    """Configurable adapter for reviewed GeoJSON sources.

    Required options: name_field, from_year_field, to_year_field. It deliberately does
    not guess historical semantics from arbitrary source columns.
    """

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        if source.defaults is None:
            raise ValueError(f"{source.id}: GeoJSON adapter requires defaults")
        required = ("name_field", "from_year_field", "to_year_field")
        missing = [key for key in required if key not in source.options]
        if missing:
            raise ValueError(f"{source.id}: missing adapter options: {', '.join(missing)}")

        suffix = str(source.options.get("suffix", ".geojson"))
        asset = context.downloads.fetch(
            str(source.url), context.raw_source_dir / f"source{suffix}"
        )
        frame = gpd.read_file(asset.path)
        if frame.crs is None:
            raise ValueError(f"{source.id}: input CRS is missing; refusing to guess")
        if frame.crs.to_epsg() != 4326:
            frame = frame.to_crs("EPSG:4326")

        result = AdapterResult(raw_assets=[asset])
        rows = frame.head(limit) if limit else frame
        for index, row in rows.iterrows():
            record_id = str(clean_scalar(row.get(source.options.get("id_field"))) or index)
            try:
                geometry = row.geometry
                if geometry is None or geometry.is_empty:
                    raise ValueError("empty geometry")
                name = str(row[source.options["name_field"]]).strip()
                valid_from = int(row[source.options["from_year_field"]])
                valid_to = int(row[source.options["to_year_field"]])
                feature = HistoricalFeature(
                    feature_id=stable_feature_id(
                        source.id, name, valid_from, valid_to, geometry.wkb
                    ),
                    kind=source.defaults.kind,
                    spatial_meaning=source.defaults.spatial_meaning,
                    names={str(source.options.get("language", "und")): name},
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
                        source.defaults.interpretive_confidence, source.title, "interpretation"
                    ),
                    review_status=source.defaults.review_status,
                    source_refs=[source_reference(source, asset, record_id)],
                    min_display_zoom=source.defaults.min_display_zoom,
                    properties={
                        key: clean_scalar(value)
                        for key, value in row.items()
                        if key != "geometry" and clean_scalar(value) is not None
                    },
                )
                result.features.append(feature)
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                result.rejections.append(
                    RejectedRecord(source.id, record_id, "normalize", str(error))
                )
        return result
