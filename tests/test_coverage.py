from __future__ import annotations

from history_pipeline.coverage import build_coverage
from history_pipeline.models import HistoricalFeature


def test_coverage_spans_bce_and_ce_periods(historical_feature: HistoricalFeature) -> None:
    cells = build_coverage([historical_feature], cell_degrees=30)
    intervals = {(cell.valid_from, cell.valid_to) for cell in cells}
    assert (-1000, -1) in intervals
    assert (1, 499) in intervals
    assert all(cell.feature_count == 1 for cell in cells)


def test_coverage_does_not_fill_a_multipart_bounding_box(
    historical_feature: HistoricalFeature,
) -> None:
    feature = historical_feature.model_copy(
        update={
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[-101, -41], [-99, -41], [-99, -39], [-101, -39], [-101, -41]]],
                    [[[99, 39], [101, 39], [101, 41], [99, 41], [99, 39]]],
                ],
            }
        }
    )
    cells = build_coverage([feature], cell_degrees=30)
    assert not any(cell.bounds == (-30, -30, 0, 0) for cell in cells)
