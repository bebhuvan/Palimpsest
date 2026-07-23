from __future__ import annotations

import csv
from typing import Any

import orjson
from pydantic import ValidationError

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import slugify, source_reference
from history_pipeline.models import IndicatorObservation


class OwidAdapter:
    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        slug = source.indicator_slug
        if not slug:
            raise ValueError(f"{source.id}: OWID adapter requires indicator_slug")

        csv_url = (
            f"https://ourworldindata.org/grapher/{slug}.csv"
            "?v=1&csvType=full&useColumnShortNames=true"
        )
        metadata_url = (
            f"https://ourworldindata.org/grapher/{slug}.metadata.json"
            "?v=1&csvType=full&useColumnShortNames=true"
        )
        csv_asset = context.downloads.fetch(csv_url, context.raw_source_dir / f"{slug}.csv")
        metadata_asset = context.downloads.fetch(
            metadata_url, context.raw_source_dir / f"{slug}.metadata.json"
        )
        with metadata_asset.path.open("rb") as handle:
            metadata = orjson.loads(handle.read())

        result = AdapterResult(raw_assets=[csv_asset, metadata_asset])
        with csv_asset.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            field_lookup = {field.casefold(): field for field in (reader.fieldnames or [])}
            required = {"entity", "code", "year"}
            if missing := required - set(field_lookup):
                raise ValueError(f"{source.id}: missing OWID columns: {sorted(missing)}")
            entity_field = field_lookup["entity"]
            code_field = field_lookup["code"]
            year_field = field_lookup["year"]
            value_columns = [
                field
                for field in (reader.fieldnames or [])
                if field.casefold() not in required
            ]
            if len(value_columns) != 1:
                raise ValueError(
                    f"{source.id}: expected one indicator column, found {value_columns}"
                )
            value_column = value_columns[0]
            unit = self._find_unit(metadata, value_column) or str(
                source.options.get("unit", "unknown")
            )
            for index, row in enumerate(reader):
                if limit is not None and index >= limit:
                    break
                record_id = (
                    f"{row.get(code_field) or slugify(row.get(entity_field, ''))}:"
                    f"{row.get(year_field)}"
                )
                try:
                    year = int(row[year_field])
                    if year == 0:
                        raise ValueError(
                            "upstream year zero requires an explicit chronology conversion"
                        )
                    raw_value = row.get(value_column, "")
                    value: float | int | None
                    if raw_value in (None, ""):
                        value = None
                    else:
                        parsed = float(raw_value)
                        value = int(parsed) if parsed.is_integer() else parsed
                    entity_name = row[entity_field]
                    entity_code = row.get(code_field) or f"owid:{slugify(entity_name)}"
                    observation = IndicatorObservation(
                        indicator_id=slug,
                        entity_id=entity_code,
                        year=year,
                        value=value,
                        unit=unit,
                        original_geographic_unit=entity_name,
                        spatial_mapping_valid=bool(
                            source.options.get("spatial_mapping_valid", False)
                        ),
                        spatial_mapping_note=str(
                            source.options.get(
                                "spatial_mapping_note",
                                "No historical geometry compatibility has been established.",
                            )
                        ),
                        source_ref=source_reference(
                            source,
                            csv_asset,
                            record_id,
                            url=csv_url,
                            title=f"{source.title}: {entity_name}, {year}",
                        ),
                    )
                    result.indicators.append(observation)
                except (KeyError, TypeError, ValueError, ValidationError) as error:
                    result.rejections.append(
                        RejectedRecord(source.id, record_id, "normalize", str(error))
                    )
        return result

    @staticmethod
    def _find_unit(metadata: dict[str, Any], value_column: str) -> str | None:
        # The Grapher metadata endpoint currently exposes columns at the top level.
        # Older exports nested them under ``dataset``; retain that fallback so cached
        # snapshots remain rebuildable when OWID changes response versions.
        candidates = [metadata.get("columns")]
        dataset = metadata.get("dataset")
        if isinstance(dataset, dict):
            candidates.append(dataset.get("columns"))
        for columns in candidates:
            if not isinstance(columns, dict):
                continue
            column = columns.get(value_column, {})
            if not isinstance(column, dict):
                continue
            for key in ("unit", "shortUnit"):
                if column.get(key):
                    return str(column[key])
        return None
