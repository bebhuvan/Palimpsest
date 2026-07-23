from __future__ import annotations

from collections import defaultdict

from shapely.geometry import shape

from history_pipeline.coverage import DEFAULT_PERIODS, _intersecting_cells
from history_pipeline.models import (
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    RegionTimeBand,
    RegionTimeBucket,
    RegionTimeEntry,
)

GRID_DEGREES = 10
MAXIMUM_RESULTS_PER_SELECTION = 60


def build_region_time_buckets(
    features: list[HistoricalFeature],
    entities: list[HistoricalEntity],
    dossiers: list[HistoricalDossier],
    *,
    minimum_year: int,
    maximum_year: int,
) -> tuple[list[RegionTimeBucket], list[RegionTimeBand]]:
    """Index sourced geography and dated coordinates without inventing regions."""

    bands = _bands(minimum_year, maximum_year)
    dossiers_by_entity: dict[str, set[str]] = defaultdict(set)
    for dossier in dossiers:
        for entity_id in dossier.entity_ids:
            dossiers_by_entity[entity_id].add(dossier.dossier_id)

    bucket_entries: dict[str, dict[str, RegionTimeEntry]] = defaultdict(dict)
    mapped_entity_ids: set[str] = set()
    for feature in sorted(features, key=lambda item: item.feature_id):
        entity_ids = _canonical_entity_ids(feature)
        entity_id = entity_ids[0]
        mapped_entity_ids.update(entity_ids)
        geometry = shape(feature.geometry)
        point = geometry.representative_point()
        entry = RegionTimeEntry(
            entry_id=f"feature:{feature.feature_id}",
            entry_type="map_feature",
            entity_id=entity_id,
            feature_id=feature.feature_id,
            kind=feature.kind.value,
            themes=feature.themes,
            valid_from=feature.valid_from,
            valid_to=feature.valid_to,
            longitude=round(point.x, 5),
            latitude=round(point.y, 5),
            spatial_basis="feature_geometry_intersection",
            review_status=feature.review_status,
            temporal_confidence=feature.temporal_confidence.grade,
            dossier_ids=sorted(
                {
                    dossier_id
                    for linked_entity_id in entity_ids
                    for dossier_id in dossiers_by_entity.get(linked_entity_id, set())
                }
            ),
            source_ids=sorted({source.source_id for source in feature.source_refs}),
        )
        for cell_id, _bounds in _intersecting_cells(geometry, GRID_DEGREES):
            for band in bands:
                if _overlaps(entry.valid_from, entry.valid_to, band):
                    bucket_id = f"{band.band_id}|{cell_id}"
                    bucket_entries[bucket_id][entry.entry_id] = entry

    for entity in sorted(entities, key=lambda item: item.entity_id):
        earth_coordinates = [
            coordinate
            for coordinate in entity.coordinates
            if coordinate.globe is None or coordinate.globe.rstrip("/").endswith("/Q2")
        ]
        if entity.entity_id in mapped_entity_ids or not earth_coordinates:
            continue
        if entity.valid_from is None and entity.valid_to is None:
            continue
        valid_from = entity.valid_from if entity.valid_from is not None else entity.valid_to
        valid_to = entity.valid_to if entity.valid_to is not None else entity.valid_from
        if valid_from is None or valid_to is None or valid_from == 0 or valid_to == 0:
            continue
        coordinate = sorted(
            earth_coordinates,
            key=lambda item: (
                item.rank != "preferred",
                -1 if item.precision is None else item.precision,
            ),
        )[0]
        cell_id, _bounds = cell_for_point(
            coordinate.longitude, coordinate.latitude, GRID_DEGREES
        )
        entry = RegionTimeEntry(
            entry_id=f"entity:{entity.entity_id}",
            entry_type="wikidata_entity",
            entity_id=entity.entity_id,
            kind=entity.entity_type,
            valid_from=valid_from,
            valid_to=valid_to,
            longitude=coordinate.longitude,
            latitude=coordinate.latitude,
            spatial_basis="wikidata_coordinate",
            dossier_ids=sorted(dossiers_by_entity.get(entity.entity_id, set())),
            source_ids=sorted({source.source_id for source in entity.source_refs}),
        )
        for band in bands:
            if _overlaps(entry.valid_from, entry.valid_to, band):
                bucket_id = f"{band.band_id}|{cell_id}"
                bucket_entries[bucket_id][entry.entry_id] = entry

    buckets: list[RegionTimeBucket] = []
    bands_by_id = {band.band_id: band for band in bands}
    for bucket_id, entries in sorted(bucket_entries.items()):
        band_id, cell_id = bucket_id.split("|", 1)
        band = bands_by_id[band_id]
        bounds = cell_bounds(cell_id, GRID_DEGREES)
        buckets.append(
            RegionTimeBucket(
                bucket_id=bucket_id,
                cell_id=cell_id,
                band_id=band_id,
                bounds=bounds,
                valid_from=band.valid_from,
                valid_to=band.valid_to,
                entries=sorted(entries.values(), key=lambda item: item.entry_id),
            )
        )
    return buckets, bands


def cell_for_point(
    longitude: float, latitude: float, cell_degrees: int = GRID_DEGREES
) -> tuple[str, tuple[float, float, float, float]]:
    longitude = min(max(longitude, -180), 180)
    latitude = min(max(latitude, -90), 90)
    lon_index = min(360 // cell_degrees - 1, int((longitude + 180) // cell_degrees))
    lat_index = min(180 // cell_degrees - 1, int((latitude + 90) // cell_degrees))
    cell_id = f"g{cell_degrees}:{lon_index}:{lat_index}"
    return cell_id, cell_bounds(cell_id, cell_degrees)


def cell_bounds(
    cell_id: str, cell_degrees: int = GRID_DEGREES
) -> tuple[float, float, float, float]:
    prefix, lon_text, lat_text = cell_id.split(":")
    if prefix != f"g{cell_degrees}":
        raise ValueError(f"Cell {cell_id} does not use the configured grid")
    lon_index = int(lon_text)
    lat_index = int(lat_text)
    if not 0 <= lon_index < 360 // cell_degrees or not 0 <= lat_index < 180 // cell_degrees:
        raise ValueError(f"Cell index is outside the configured grid: {cell_id}")
    minimum_longitude = -180 + lon_index * cell_degrees
    minimum_latitude = -90 + lat_index * cell_degrees
    return (
        minimum_longitude,
        minimum_latitude,
        minimum_longitude + cell_degrees,
        minimum_latitude + cell_degrees,
    )


def _bands(minimum_year: int, maximum_year: int) -> list[RegionTimeBand]:
    return [
        RegionTimeBand(
            band_id=f"band-{index:02d}",
            valid_from=max(start, minimum_year),
            valid_to=min(end, maximum_year),
        )
        for index, (start, end) in enumerate(DEFAULT_PERIODS)
        if max(start, minimum_year) <= min(end, maximum_year)
    ]


def _overlaps(start: int, end: int, band: RegionTimeBand) -> bool:
    return end >= band.valid_from and start <= band.valid_to


def _canonical_entity_ids(feature: HistoricalFeature) -> list[str]:
    if feature.entity_ids:
        return feature.entity_ids
    if feature.wikidata_ids:
        return [f"wikidata:{qid}" for qid in feature.wikidata_ids]
    return [f"feature:{feature.feature_id}"]
