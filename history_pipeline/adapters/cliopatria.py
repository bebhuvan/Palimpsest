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
from history_pipeline.storage import safely_extract_member


class CliopatriaAdapter:
    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        if source.defaults is None or source.member_name is None:
            raise ValueError("Cliopatria requires defaults and member_name")

        archive = context.downloads.fetch(
            str(source.url), context.raw_source_dir / "cliopatria.geojson.zip"
        )
        extracted = safely_extract_member(
            archive.path, source.member_name, context.staged_source_dir
        )
        frame = gpd.read_file(extracted)
        if frame.crs is None:
            frame = frame.set_crs("EPSG:4326")
        elif frame.crs.to_epsg() != 4326:
            frame = frame.to_crs("EPSG:4326")

        result = AdapterResult(raw_assets=[archive])
        rows = frame.head(limit) if limit else frame
        for index, row in rows.iterrows():
            record_id = str(index)
            try:
                geometry = row.geometry
                if geometry is None or geometry.is_empty:
                    raise ValueError("empty geometry")
                name = str(row["Name"]).strip()
                valid_from = int(row["FromYear"])
                valid_to = int(row["ToYear"])
                wikidata = str(clean_scalar(row.get("Wikidata")) or "").strip()
                wikipedia = str(clean_scalar(row.get("Wikipedia")) or "").strip()
                feature = HistoricalFeature(
                    feature_id=stable_feature_id(
                        source.id, name, valid_from, valid_to, geometry.wkb
                    ),
                    kind=source.defaults.kind,
                    spatial_meaning=source.defaults.spatial_meaning,
                    names={"en": name},
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
                    source_refs=[source_reference(source, archive, record_id)],
                    wikidata_ids=[wikidata] if wikidata.startswith("Q") else [],
                    wikipedia_titles={"en": wikipedia} if wikipedia else {},
                    min_display_zoom=source.defaults.min_display_zoom,
                    properties={
                        key: clean_scalar(row.get(key))
                        for key in ("Area", "Type", "SeshatID", "Components", "MemberOf")
                        if clean_scalar(row.get(key)) is not None
                    },
                )
                result.features.append(feature)
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                result.rejections.append(
                    RejectedRecord(source.id, record_id, "normalize", str(error))
                )
        return result
