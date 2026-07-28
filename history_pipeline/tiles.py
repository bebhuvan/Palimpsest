from __future__ import annotations

import math
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import orjson
from shapely.geometry import mapping, shape

from history_pipeline.artifacts import canonical_entity_ids, content_shard, era_partitions
from history_pipeline.models import ArtifactFile, HistoricalFeature
from history_pipeline.storage import sha256_file


def build_pmtiles(
    features: list[HistoricalFeature],
    output_dir: Path,
    work_dir: Path,
    tippecanoe: str | None = None,
    minimum_zoom: int = 0,
    maximum_zoom: int = 7,
    simplification: float = 2.0,
    minimum_year: int = -3400,
    maximum_year: int = 2026,
) -> list[ArtifactFile]:
    executable = _resolve_tippecanoe(tippecanoe)
    work_dir.mkdir(parents=True, exist_ok=True)
    tile_dir = output_dir / "tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[ArtifactFile] = []

    for era, (start, end) in era_partitions(minimum_year, maximum_year).items():
        selected = [
            feature
            for feature in features
            if not (feature.valid_to < start or feature.valid_from > end)
        ]
        if not selected:
            continue
        sequence = work_dir / f"{era}.geojsonseq"
        _write_sequence(sequence, selected)
        label_sequence = work_dir / f"{era}-labels.geojsonseq"
        _write_label_sequence(label_sequence, selected, start, end)
        output = tile_dir / f"{era}.pmtiles"
        generated_output = work_dir / f"{era}.pmtiles"
        command = [
            executable,
            "--force",
            "--output",
            str(generated_output),
            "--named-layer",
            f"history:{sequence}",
            "--named-layer",
            f"history_labels:{label_sequence}",
            "--minimum-zoom",
            str(minimum_zoom),
            "--maximum-zoom",
            str(maximum_zoom),
            "--simplification",
            str(simplification),
            "--read-parallel",
            "--quiet",
            "--drop-densest-as-needed",
            "--name",
            f"Palimpsest: {era}",
            "--description",
            "Historical features with explicit validity intervals and uncertainty",
            "--attribution",
            "See attribution.json and each feature's source metadata",
        ]
        subprocess.run(command, check=True)
        _validate_pmtiles_header(generated_output)
        os.replace(generated_output, output)
        artifacts.append(
            ArtifactFile(
                path=output.relative_to(output_dir).as_posix(),
                media_type="application/vnd.pmtiles",
                bytes=output.stat().st_size,
                checksum_sha256=sha256_file(output),
                cache_control="public, max-age=31536000, immutable",
            )
        )
    return artifacts


def _write_sequence(path: Path, features: Iterable[HistoricalFeature]) -> None:
    with path.open("wb") as handle:
        for feature in features:
            entity_ids = canonical_entity_ids(feature)
            primary_source = feature.source_refs[0]
            properties = {
                "feature_id": feature.feature_id,
                "kind": feature.kind.value,
                "spatial_meaning": feature.spatial_meaning.value,
                "name": feature.names.get("en") or next(iter(feature.names.values())),
                "valid_from": feature.valid_from,
                "valid_to": feature.valid_to,
                "date_precision": feature.date_precision.value,
                "temporal_confidence": feature.temporal_confidence.grade.value,
                "spatial_confidence": feature.spatial_confidence.grade.value,
                "interpretive_confidence": feature.interpretive_confidence.grade.value,
                "review_status": feature.review_status.value,
                "themes": [theme.value for theme in feature.themes],
                "wikidata_id": feature.wikidata_ids[0] if feature.wikidata_ids else None,
                "primary_entity_id": entity_ids[0],
                "content_shard": content_shard(feature.feature_id),
                "min_display_zoom": feature.min_display_zoom,
                "dispute_group": feature.dispute_group,
                "perspective": feature.perspective,
                "temporal_uncertainty": bool(feature.temporal_uncertainty),
                "spatial_uncertainty": bool(feature.spatial_uncertainty),
                "source_id": primary_source.source_id,
                "source_record_id": primary_source.record_id,
                "source_title": primary_source.title,
                "source_publisher": primary_source.publisher,
                "source_url": str(primary_source.url),
                "source_citation": primary_source.citation,
                "source_version": primary_source.version,
                "license_id": primary_source.license_id,
                "year_dossier_years": feature.properties.get("year_dossier_years", []),
            }
            record = {
                "type": "Feature",
                "properties": properties,
                "geometry": feature.geometry,
                "tippecanoe": {"minzoom": math.ceil(feature.min_display_zoom)},
            }
            handle.write(b"\x1e")
            handle.write(orjson.dumps(record))
            handle.write(b"\n")


def _write_label_sequence(
    path: Path,
    features: Iterable[HistoricalFeature],
    era_start: int,
    era_end: int,
) -> None:
    """Write one representative point per name attestation.

    Labels are a distinct vector layer so a place can change names without replacing or
    pretending to interpolate its reviewed geometry.
    """

    with path.open("wb") as handle:
        for feature in features:
            geometry = shape(feature.geometry)
            label_point = (
                geometry
                if geometry.geom_type == "Point"
                else geometry.representative_point()
            )
            entity_ids = canonical_entity_ids(feature)
            for name in feature.name_attestations:
                if name.valid_to < era_start or name.valid_from > era_end:
                    continue
                sources = name.source_refs or feature.source_refs
                primary_source = sources[0]
                properties = {
                    "label_id": name.name_id,
                    "feature_id": feature.feature_id,
                    "primary_entity_id": entity_ids[0],
                    "content_shard": content_shard(feature.feature_id),
                    "name": name.text,
                    "language": name.language,
                    "script": name.script,
                    "name_kind": name.name_kind.value,
                    "valid_from": name.valid_from,
                    "valid_to": name.valid_to,
                    "date_precision": name.date_precision.value,
                    "temporal_confidence": name.temporal_confidence.grade.value,
                    "spatial_confidence": feature.spatial_confidence.grade.value,
                    "interpretive_confidence": feature.interpretive_confidence.grade.value,
                    "temporal_basis": name.temporal_basis,
                    "primary": name.primary,
                    "perspective": name.perspective,
                    "kind": feature.kind.value,
                    "spatial_meaning": feature.spatial_meaning.value,
                    "review_status": feature.review_status.value,
                    "themes": [theme.value for theme in feature.themes],
                    "dispute_group": feature.dispute_group,
                    "wikidata_id": feature.wikidata_ids[0] if feature.wikidata_ids else None,
                    "min_display_zoom": feature.min_display_zoom,
                    "label_area": round(float(geometry.area), 8),
                    "source_id": primary_source.source_id,
                    "source_record_id": primary_source.record_id,
                    "license_id": primary_source.license_id,
                }
                record = {
                    "type": "Feature",
                    "properties": properties,
                    "geometry": mapping(label_point),
                    "tippecanoe": {"minzoom": math.ceil(feature.min_display_zoom)},
                }
                handle.write(b"\x1e")
                handle.write(orjson.dumps(record))
                handle.write(b"\n")


def _resolve_tippecanoe(explicit: str | None) -> str:
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return str(candidate)
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        raise FileNotFoundError(f"Configured tippecanoe executable not found: {explicit}")
    local = Path(".tools/bin/tippecanoe")
    if local.is_file():
        return str(local.resolve())
    resolved = shutil.which("tippecanoe")
    if resolved:
        return resolved
    raise FileNotFoundError(
        "tippecanoe is required for release builds; run scripts/install-tippecanoe.sh"
    )


def _validate_pmtiles_header(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(8)
    if not header.startswith(b"PMTiles") or header[7] != 3:
        raise ValueError(f"Invalid or unsupported PMTiles v3 archive: {path}")
