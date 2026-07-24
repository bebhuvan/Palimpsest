from __future__ import annotations

import csv
import gzip
import io
import re
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import orjson
from pydantic import ValidationError
from shapely import force_2d
from shapely.geometry import GeometryCollection, Point, mapping, shape
from shapely.ops import unary_union

from history_pipeline.adapters.base import AdapterContext, AdapterResult, RejectedRecord
from history_pipeline.adapters.common import (
    source_reference,
    stable_feature_id,
    verify_expected_checksum,
)
from history_pipeline.models import (
    Confidence,
    ConfidenceGrade,
    DatePrecision,
    FeatureKind,
    HistoricalFeature,
    ReviewStatus,
    SpatialMeaning,
)


class PleiadesAdapter:
    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        source = context.source
        is_release_archive = source.options.get("archive_format") == "tar.gz"
        asset = context.downloads.fetch(
            str(source.url),
            context.raw_source_dir
            / ("pleiades-release.tar.gz" if is_release_archive else "pleiades-places.json.gz"),
        )
        verify_expected_checksum(source, asset)
        result = AdapterResult(raw_assets=[asset])
        for index, (place, period_ranges) in enumerate(self._places(asset.path)):
            if limit is not None and index >= limit:
                break
            record_id = str(place.get("id") or index)
            try:
                geometry, geometry_origin = self._geometry(place)
                date_ranges = self._date_ranges(place, period_ranges)
                title = str(place.get("title") or "").strip()
                if not title:
                    raise ValueError("place has no title")
                source_url = str(
                    place.get("uri") or f"https://pleiades.stoa.org/places/{record_id}"
                )
                language_names = self._names(place, title)
                spatial_grade = (
                    ConfidenceGrade.B
                    if geometry_origin == "published_geometry"
                    else ConfidenceGrade.C
                )
                references = [
                    source_reference(
                        source,
                        asset,
                        record_id,
                        url=source_url,
                        title=f"Pleiades: {title}",
                    )
                ]
                normalized: list[HistoricalFeature] = []
                for valid_from, valid_to in date_ranges:
                    normalized.append(
                        HistoricalFeature(
                            feature_id=stable_feature_id(
                                source.id, record_id, valid_from, valid_to, geometry.wkb
                            ),
                            kind=self._kind(place),
                            spatial_meaning=SpatialMeaning.LOCATION,
                            names=language_names,
                            valid_from=valid_from,
                            valid_to=valid_to,
                            date_precision=DatePrecision.RANGE,
                            geometry=mapping(geometry),
                            temporal_confidence=Confidence(
                                grade=ConfidenceGrade.B,
                                rationale=(
                                    "Published Pleiades attestation interval; disconnected "
                                    "intervals remain separate features"
                                ),
                            ),
                            spatial_confidence=Confidence(
                                grade=spatial_grade,
                                rationale=(
                                    "Published Pleiades geometry"
                                    if geometry_origin == "published_geometry"
                                    else (
                                        "Pleiades representative point derived from "
                                        "published locations"
                                    )
                                ),
                            ),
                            interpretive_confidence=Confidence(
                                grade=ConfidenceGrade.B,
                                rationale="Peer-reviewed Pleiades place resource",
                            ),
                            review_status=ReviewStatus.PROVISIONAL,
                            source_refs=references,
                            wikidata_ids=self._wikidata_ids(place),
                            wikipedia_titles=self._wikipedia_titles(place),
                            min_display_zoom=3,
                            properties={
                                "description": place.get("description", ""),
                                "place_types": place.get("placeTypes", []),
                                "place_type_uris": place.get("placeTypeURIs", []),
                                "geometry_origin": geometry_origin,
                                "review_state": place.get("review_state"),
                                "attestation_interval": [valid_from, valid_to],
                                "place_interval_count": len(date_ranges),
                            },
                        )
                    )
                result.features.extend(normalized)
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                result.rejections.append(
                    RejectedRecord(source.id, record_id, "normalize", str(error))
                )
        return result

    @staticmethod
    def _places(
        path: Path,
    ) -> Iterator[tuple[dict[str, Any], dict[str, tuple[int, int]]]]:
        if path.name.endswith(".tar.gz"):
            yield from PleiadesAdapter._release_places(path)
            return
        with gzip.open(path, "rb") as handle:
            payload = orjson.loads(handle.read())
        if isinstance(payload, dict):
            records = payload.get("@graph") or payload.get("places") or payload.get("features")
        else:
            records = payload
        if not isinstance(records, list):
            raise ValueError("Unexpected Pleiades JSON dump structure")
        yield from ((record, {}) for record in records)

    @staticmethod
    def _release_places(
        path: Path,
    ) -> Iterator[tuple[dict[str, Any], dict[str, tuple[int, int]]]]:
        pattern = re.compile(r"^[^/]+/data/json/(?:[0-9]+/)+[0-9]+\.json$")
        # Release 4.1 contains one legitimate geometry-heavy place record of 20,395,657 bytes.
        # Keep a bounded per-member guard with narrow headroom rather than disabling the limit.
        maximum_member_bytes = 24 * 1024 * 1024
        maximum_total_bytes = 2 * 1024 * 1024 * 1024
        total_bytes = 0
        with tarfile.open(path, "r:gz") as bundle:
            period_ranges = PleiadesAdapter._release_period_ranges(bundle)
            members = sorted(
                (
                    member
                    for member in bundle.getmembers()
                    if member.isfile() and pattern.fullmatch(member.name)
                ),
                key=lambda member: member.name,
            )
            if not members:
                raise ValueError("Pleiades release contains no recognized place JSON")
            for member in members:
                if member.size > maximum_member_bytes:
                    raise ValueError(f"Pleiades archive member is too large: {member.name}")
                total_bytes += member.size
                if total_bytes > maximum_total_bytes:
                    raise ValueError("Pleiades archive exceeds the uncompressed size limit")
                handle = bundle.extractfile(member)
                if handle is None:
                    raise ValueError(f"Cannot read Pleiades archive member: {member.name}")
                payload = orjson.loads(handle.read(maximum_member_bytes + 1))
                if not isinstance(payload, dict):
                    raise ValueError(f"Pleiades place is not an object: {member.name}")
                yield payload, period_ranges

    @staticmethod
    def _release_period_ranges(
        bundle: tarfile.TarFile,
    ) -> dict[str, tuple[int, int]]:
        candidates = [
            member
            for member in bundle.getmembers()
            if member.isfile() and member.name.endswith("/data/gis/time_periods.csv")
        ]
        if len(candidates) != 1 or candidates[0].size > 4 * 1024 * 1024:
            raise ValueError("Pleiades release has no safe, unique time-period vocabulary")
        handle = bundle.extractfile(candidates[0])
        if handle is None:
            raise ValueError("Cannot read Pleiades time-period vocabulary")
        reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
        ranges: dict[str, tuple[int, int]] = {}
        for row in reader:
            key = str(row.get("key") or "").strip()
            match = re.search(
                r"\[\[\s*(-?[0-9]+)\s*,\s*(-?[0-9]+)\s*\]\]",
                str(row.get("definition") or ""),
            )
            if key and match:
                start, end = (_historical_year(int(value)) for value in match.groups())
                ranges[key] = (min(start, end), max(start, end))
        if not ranges:
            raise ValueError("Pleiades time-period vocabulary contains no bounded ranges")
        return ranges

    @staticmethod
    def _geometry(place: dict[str, Any]) -> tuple[Any, str]:
        geometries = []
        for feature in place.get("features") or []:
            raw_geometry = feature.get("geometry") if isinstance(feature, dict) else None
            if raw_geometry:
                candidate = shape(raw_geometry)
                if not candidate.is_empty:
                    geometries.append(candidate)
        if geometries:
            merged = force_2d(unary_union(geometries))
            if not isinstance(merged, GeometryCollection) or not merged.is_empty:
                return merged, "published_geometry"
        point = place.get("reprPoint")
        if isinstance(point, list) and len(point) >= 2:
            return Point(float(point[0]), float(point[1])), "representative_point"
        raise ValueError("place has no usable published geometry or representative point")

    @staticmethod
    def _date_ranges(
        place: dict[str, Any], period_ranges: dict[str, tuple[int, int]]
    ) -> list[tuple[int, int]]:
        intervals: set[tuple[int, int]] = set()
        for section in ("locations", "names", "connections"):
            for item in place.get(section) or []:
                if item.get("start") is not None and item.get("end") is not None:
                    start = _historical_year(int(item["start"]))
                    end = _historical_year(int(item["end"]))
                    intervals.add((min(start, end), max(start, end)))
                for attestation in item.get("attestations") or []:
                    if not isinstance(attestation, dict):
                        continue
                    key = str(attestation.get("timePeriod") or "")
                    if not key and attestation.get("timePeriodURI"):
                        key = str(attestation["timePeriodURI"]).rstrip("/").rsplit("/", 1)[-1]
                    if key in period_ranges:
                        intervals.add(period_ranges[key])
        if not intervals:
            raise ValueError("place has no bounded chronological attestation")
        merged: list[tuple[int, int]] = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    @staticmethod
    def _names(place: dict[str, Any], title: str) -> dict[str, str]:
        names = {"und": title}
        for name in place.get("names") or []:
            value = name.get("romanized") or name.get("attested")
            if value:
                language = name.get("language") or "und"
                names.setdefault(str(language), str(value))
        return names

    @staticmethod
    def _kind(place: dict[str, Any]) -> FeatureKind:
        types = " ".join(str(item).casefold() for item in place.get("placeTypes") or [])
        if any(token in types for token in ("settlement", "city", "village", "fort")):
            return FeatureKind.SETTLEMENT
        return FeatureKind.ARCHAEOLOGICAL_SITE

    @staticmethod
    def _reference_urls(place: dict[str, Any]) -> Iterator[str]:
        for container in [place, *(place.get("names") or []), *(place.get("locations") or [])]:
            if not isinstance(container, dict):
                continue
            for reference in container.get("references") or []:
                if not isinstance(reference, dict):
                    continue
                for key in ("accessURI", "alternateURI", "bibliographicURI"):
                    value = reference.get(key)
                    if isinstance(value, str) and value:
                        yield value

    @classmethod
    def _wikidata_ids(cls, place: dict[str, Any]) -> list[str]:
        identifiers = set()
        for url in cls._reference_urls(place):
            match = re.search(r"wikidata\.org/(?:wiki|entity)/(Q[1-9][0-9]*)", url)
            if match:
                identifiers.add(match.group(1))
        return sorted(identifiers)

    @classmethod
    def _wikipedia_titles(cls, place: dict[str, Any]) -> dict[str, str]:
        titles: dict[str, str] = {}
        for url in cls._reference_urls(place):
            match = re.search(r"https?://([a-z-]+)\.wikipedia\.org/wiki/([^?#]+)", url)
            if match:
                language, title = match.groups()
                titles.setdefault(language, unquote(title).replace("_", " "))
        return titles


def _historical_year(value: int) -> int:
    # Pleiades' integer ranges ordinarily use BCE/CE historical notation. Zero is
    # still disallowed by the canonical model and is explicitly converted to 1 BCE.
    return -1 if value == 0 else value
