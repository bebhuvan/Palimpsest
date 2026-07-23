from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry

from history_pipeline.models import ConfidenceGrade, CoverageCell, HistoricalFeature

DEFAULT_PERIODS = (
    (-3400, -2001),
    (-2000, -1001),
    (-1000, -1),
    (1, 499),
    (500, 999),
    (1000, 1499),
    (1500, 1799),
    (1800, 1885),
    (1886, 1945),
    (1946, 1999),
    (2000, 9999),
)


def build_coverage(
    features: Iterable[HistoricalFeature],
    cell_degrees: int = 30,
    minimum_year: int = -3400,
    maximum_year: int = 2026,
) -> list[CoverageCell]:
    buckets: dict[
        tuple[str, int, int, str], tuple[Counter[ConfidenceGrade], set[str], int]
    ] = {}
    for feature in features:
        geometry = shape(feature.geometry)
        for cell_id, _bounds in _intersecting_cells(geometry, cell_degrees):
            for period_start, period_end in DEFAULT_PERIODS:
                if period_end < minimum_year or period_start > maximum_year:
                    continue
                if feature.valid_to < period_start or feature.valid_from > period_end:
                    continue
                effective_start = max(period_start, minimum_year)
                effective_end = min(period_end, maximum_year)
                key = (cell_id, effective_start, effective_end, feature.kind.value)
                counts, reviewed, feature_count = buckets.get(key, (Counter(), set(), 0))
                counts[feature.spatial_confidence.grade] += 1
                if feature.review_status in {"verified", "contested"}:
                    reviewed.add(feature.feature_id)
                buckets[key] = (counts, reviewed, feature_count + 1)

    output: list[CoverageCell] = []
    for (cell_id, start, end, layer), (counts, reviewed, feature_count) in sorted(
        buckets.items()
    ):
        output.append(
            CoverageCell(
                cell_id=cell_id,
                bounds=_bounds_from_cell_id(cell_id, cell_degrees),
                valid_from=start,
                valid_to=end,
                layer=layer,
                feature_count=feature_count,
                confidence_counts=dict(counts),
                reviewed_count=len(reviewed),
            )
        )
    return output


def _intersecting_cells(
    geometry: BaseGeometry, cell_degrees: int
) -> list[tuple[str, tuple[float, float, float, float]]]:
    min_x, min_y, max_x, max_y = geometry.bounds
    min_lon_index = max(0, math.floor((min_x + 180) / cell_degrees))
    max_lon_index = min((360 // cell_degrees) - 1, math.floor((max_x + 180) / cell_degrees))
    min_lat_index = max(0, math.floor((min_y + 90) / cell_degrees))
    max_lat_index = min((180 // cell_degrees) - 1, math.floor((max_y + 90) / cell_degrees))
    cells = []
    for lon_index in range(min_lon_index, max_lon_index + 1):
        for lat_index in range(min_lat_index, max_lat_index + 1):
            cell_id = f"g{cell_degrees}:{lon_index}:{lat_index}"
            bounds = _bounds_from_cell_id(cell_id, cell_degrees)
            if geometry.intersects(box(*bounds)):
                cells.append((cell_id, bounds))
    return cells


def _bounds_from_cell_id(cell_id: str, cell_degrees: int) -> tuple[float, float, float, float]:
    _, lon_text, lat_text = cell_id.split(":")
    min_lon = -180 + int(lon_text) * cell_degrees
    min_lat = -90 + int(lat_text) * cell_degrees
    return (min_lon, min_lat, min_lon + cell_degrees, min_lat + cell_degrees)
