from __future__ import annotations

import gzip
import hashlib
import shutil
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

import geopandas as gpd
import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import shape

from history_pipeline.config import SourceConfig
from history_pipeline.coverage import DEFAULT_PERIODS, build_coverage
from history_pipeline.models import (
    ArtifactFile,
    AssertionAdjacency,
    AssertionIndex,
    AuthorityMatch,
    CausalDataset,
    CausalEntityIndex,
    CausalIndex,
    ChronologyBandContract,
    ChronologyEntityIndex,
    ChronologyIndex,
    CommercialRedistribution,
    ContentIndex,
    DistributionTier,
    EvidenceAssertion,
    FeatureContentLink,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    HistoricalMapMetadata,
    HistoricalPeriodDefinition,
    HistoricalTheme,
    IndicatorObservation,
    IntegrationIndex,
    LayerCatalog,
    LayerDefinition,
    LayerRole,
    RegionTimeIndex,
    SourceRegistry,
    SourceRegistryEntry,
    ThematicAssertion,
    ThemeFeatureIndex,
    ThemeIndex,
    WikiContextIndex,
)
from history_pipeline.region_time import (
    GRID_DEGREES,
    MAXIMUM_RESULTS_PER_SELECTION,
    build_region_time_buckets,
)
from history_pipeline.storage import NdjsonWriter, sha256_file
from history_pipeline.wiki_context import DEFAULT_ROLE_QUOTAS, build_wiki_feature_contexts

ERA_PARTITIONS = {
    # The lower bound is replaced by the configured release minimum when artifacts
    # are selected. It is intentionally not a claim about when history begins.
    "ancient": (-3400, 499),
    "medieval": (500, 1499),
    "early-modern": (1500, 1799),
    "modern": (1800, 9999),
}
CONFIDENCE_AXES: tuple[
    Literal["temporal", "spatial", "interpretive"], ...
] = ("temporal", "spatial", "interpretive")


def era_partitions(minimum_year: int, maximum_year: int) -> dict[str, tuple[int, int]]:
    """Return map archives clipped to the configured release chronology."""

    partitions = {**ERA_PARTITIONS, "ancient": (minimum_year, 499)}
    return {
        era: (max(start, minimum_year), min(end, maximum_year))
        for era, (start, end) in partitions.items()
        if max(start, minimum_year) <= min(end, maximum_year)
    }


def build_artifacts(
    features: list[HistoricalFeature],
    indicators: list[IndicatorObservation],
    entities: list[HistoricalEntity],
    dossiers: list[HistoricalDossier],
    output_dir: Path,
    periods: list[HistoricalPeriodDefinition] | None = None,
    sources: list[SourceConfig] | None = None,
    causal: CausalDataset | None = None,
    thematic_assertions: list[ThematicAssertion] | None = None,
    evidence_assertions: list[EvidenceAssertion] | None = None,
    quality_report: dict[str, Any] | None = None,
    minimum_year: int = -3400,
    maximum_year: int = 2026,
    language_fallbacks: tuple[str, ...] = (),
    authority_matches: list[AuthorityMatch] | None = None,
    historical_maps: list[HistoricalMapMetadata] | None = None,
) -> list[ArtifactFile]:
    causal = causal or CausalDataset()
    thematic_assertions = thematic_assertions or []
    evidence_assertions = evidence_assertions or []
    periods = periods or []
    sources = sources or []
    authority_matches = authority_matches or []
    historical_maps = historical_maps or []
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    artifacts: list[ArtifactFile] = []

    for era, (start, end) in era_partitions(minimum_year, maximum_year).items():
        selected = [
            feature
            for feature in features
            if not (feature.valid_to < start or feature.valid_from > end)
        ]
        if not selected:
            continue
        path = output_dir / "features" / f"{era}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame = _feature_frame(selected)
        frame.to_parquet(path, compression="zstd", index=False)
        artifacts.append(_artifact(path, output_dir, "application/vnd.apache.parquet"))

    if indicators:
        path = output_dir / "indicators" / "observations.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(
            [observation.model_dump(mode="json") for observation in indicators]
        )
        pq.write_table(table, path, compression="zstd")
        artifacts.append(_artifact(path, output_dir, "application/vnd.apache.parquet"))

    if entities:
        path = output_dir / "entities.ndjson"
        with NdjsonWriter(path) as writer:
            for entity in entities:
                writer.write(entity)
        artifacts.append(_artifact(path, output_dir, "application/x-ndjson"))

    if dossiers:
        path = output_dir / "dossiers.ndjson"
        with NdjsonWriter(path) as writer:
            for dossier in dossiers:
                writer.write(dossier)
        artifacts.append(_artifact(path, output_dir, "application/x-ndjson"))

    artifacts.extend(
        _build_integration_artifacts(authority_matches, historical_maps, output_dir)
    )
    artifacts.extend(
        _build_content_artifacts(
            features,
            entities,
            dossiers,
            output_dir,
            language_fallbacks=language_fallbacks,
        )
    )
    wikidata_options = next(
        (source.options for source in sources if source.enabled and source.adapter == "wikidata"),
        {},
    )
    artifacts.extend(
        _build_wiki_context_artifacts(
            features, entities, dossiers, output_dir, options=wikidata_options
        )
    )
    artifacts.extend(
        _build_region_time_artifacts(
            features,
            entities,
            dossiers,
            output_dir,
            minimum_year=minimum_year,
            maximum_year=maximum_year,
        )
    )
    artifacts.extend(_build_causal_artifacts(causal, output_dir))
    artifacts.extend(_build_theme_artifacts(thematic_assertions, output_dir))
    artifacts.extend(_build_assertion_artifacts(evidence_assertions, output_dir))
    artifacts.extend(_build_layer_catalog(sources, historical_maps, output_dir))
    artifacts.extend(
        _build_chronology_artifacts(
            periods,
            output_dir,
            minimum_year=minimum_year,
            maximum_year=maximum_year,
        )
    )

    coverage_path = output_dir / "coverage.json"
    coverage = [
        cell.model_dump(mode="json")
        for cell in build_coverage(features, minimum_year=minimum_year, maximum_year=maximum_year)
    ]
    _write_json(coverage_path, coverage)
    artifacts.append(_artifact(coverage_path, output_dir, "application/json"))

    priority_path = output_dir / "coverage-priorities.json"
    _write_json(priority_path, _coverage_priorities(coverage))
    artifacts.append(_artifact(priority_path, output_dir, "application/json"))

    artifacts.extend(
        _build_search_artifacts(
            features,
            dossiers,
            output_dir,
            minimum_year=minimum_year,
            maximum_year=maximum_year,
        )
    )

    attribution_path = output_dir / "attribution.json"
    _write_json(
        attribution_path,
        _attributions(
            features,
            indicators,
            periods,
            entities,
            dossiers,
            causal,
            authority_matches,
            historical_maps,
        ),
    )
    artifacts.append(_artifact(attribution_path, output_dir, "application/json"))

    quality_path = output_dir / "quality.json"
    _write_json(quality_path, quality_report or {})
    artifacts.append(_artifact(quality_path, output_dir, "application/json"))

    registry_path = output_dir / "source-registry.json"
    _write_json(
        registry_path,
        SourceRegistry(entries=[_source_registry_entry(source) for source in sources]).model_dump(
            mode="json"
        ),
    )
    artifacts.append(_artifact(registry_path, output_dir, "application/json"))
    return artifacts


def _feature_frame(features: list[HistoricalFeature]) -> gpd.GeoDataFrame:
    records: list[dict[str, Any]] = []
    for feature in features:
        records.append(
            {
                "feature_id": feature.feature_id,
                "kind": feature.kind.value,
                "spatial_meaning": feature.spatial_meaning.value,
                "names_json": orjson.dumps(feature.names).decode(),
                "name_attestations_json": orjson.dumps(
                    [name.model_dump(mode="json") for name in feature.name_attestations]
                ).decode(),
                "valid_from": feature.valid_from,
                "valid_to": feature.valid_to,
                "date_precision": feature.date_precision.value,
                "temporal_confidence": feature.temporal_confidence.grade.value,
                "spatial_confidence": feature.spatial_confidence.grade.value,
                "interpretive_confidence": feature.interpretive_confidence.grade.value,
                "review_status": feature.review_status.value,
                "themes": [theme.value for theme in feature.themes],
                "source_refs_json": orjson.dumps(
                    [source.model_dump(mode="json") for source in feature.source_refs]
                ).decode(),
                "entity_ids": feature.entity_ids,
                "wikidata_ids": feature.wikidata_ids,
                "wikipedia_titles_json": orjson.dumps(feature.wikipedia_titles).decode(),
                "min_display_zoom": feature.min_display_zoom,
                "dispute_group": feature.dispute_group,
                "perspective": feature.perspective,
                "temporal_uncertainty_json": (
                    feature.temporal_uncertainty.model_dump_json()
                    if feature.temporal_uncertainty
                    else None
                ),
                "spatial_uncertainty_json": (
                    feature.spatial_uncertainty.model_dump_json()
                    if feature.spatial_uncertainty
                    else None
                ),
                "properties_json": orjson.dumps(feature.properties).decode(),
                "geometry": shape(feature.geometry),
            }
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def _search_records(
    features: Iterable[HistoricalFeature], dossiers: Iterable[HistoricalDossier]
) -> list[dict[str, Any]]:
    dossier_ids_by_entity: dict[str, set[str]] = defaultdict(set)
    for dossier in dossiers:
        for entity_id in dossier.entity_ids:
            dossier_ids_by_entity[entity_id].add(dossier.dossier_id)
    grouped: dict[str, list[HistoricalFeature]] = defaultdict(list)
    for feature in features:
        key = canonical_entity_ids(feature)[0]
        grouped[key].append(feature)
    records = []
    for key, group in sorted(grouped.items()):
        first = min(group, key=lambda feature: feature.valid_from)
        geometry = shape(first.geometry)
        point = geometry.representative_point()
        names: dict[str, str] = {}
        themes: set[str] = set()
        source_ids: set[str] = set()
        name_attestations: dict[str, dict[str, Any]] = {}
        for feature in group:
            names.update(feature.names)
            themes.update(theme.value for theme in feature.themes)
            source_ids.update(source.source_id for source in feature.source_refs)
            for name in feature.name_attestations:
                name_attestations[name.name_id] = {
                    "name_id": name.name_id,
                    "feature_id": feature.feature_id,
                    "text": name.text,
                    "language": name.language,
                    "script": name.script,
                    "name_kind": name.name_kind.value,
                    "valid_from": name.valid_from,
                    "valid_to": name.valid_to,
                    "date_precision": name.date_precision.value,
                    "temporal_confidence": name.temporal_confidence.grade.value,
                    "primary": name.primary,
                    "perspective": name.perspective,
                    "temporal_basis": name.temporal_basis,
                    "source_ids": sorted({source.source_id for source in name.source_refs}),
                }
        records.append(
            {
                "entity_id": key,
                "dossier_ids": sorted(dossier_ids_by_entity.get(key, set())),
                "content_shard": content_shard(key),
                "names": names,
                "name_attestations": sorted(
                    name_attestations.values(),
                    key=lambda item: (
                        item["valid_from"],
                        not item["primary"],
                        item["language"],
                        item["text"],
                    ),
                ),
                "kind": first.kind.value,
                "themes": sorted(themes),
                "source_ids": sorted(source_ids),
                "valid_from": min(feature.valid_from for feature in group),
                "valid_to": max(feature.valid_to for feature in group),
                "longitude": round(point.x, 5),
                "latitude": round(point.y, 5),
                "feature_ids": [feature.feature_id for feature in group],
            }
        )
    return records


def _build_search_artifacts(
    features: Iterable[HistoricalFeature],
    dossiers: Iterable[HistoricalDossier],
    output_dir: Path,
    *,
    minimum_year: int,
    maximum_year: int,
    page_size: int = 250,
) -> list[ArtifactFile]:
    """Write the legacy bulk export and the lazy static-search contract."""

    records = _search_records(features, dossiers)
    artifacts: list[ArtifactFile] = []

    legacy_path = output_dir / "search.ndjson"
    with NdjsonWriter(legacy_path) as writer:
        for record in records:
            writer.write(record)
    artifacts.append(_artifact(legacy_path, output_dir, "application/x-ndjson"))

    record_buckets: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    feature_buckets: dict[str, dict[str, str]] = defaultdict(dict)
    token_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        entity_id = str(record["entity_id"])
        record_buckets[content_shard(entity_id)][entity_id] = record
        for feature_id in record["feature_ids"]:
            feature_buckets[content_shard(feature_id)][feature_id] = entity_id
        tokens = {token for name in _record_search_names(record) for token in _search_tokens(name)}
        for token in sorted(tokens):
            token_records[token].append(record)

    record_shards = _write_mapping_shards(
        record_buckets, output_dir / "search" / "records", output_dir
    )
    feature_shards = _write_mapping_shards(
        feature_buckets, output_dir / "search" / "features", output_dir
    )
    artifacts.extend(artifact for artifact, _shard in record_shards)
    artifacts.extend(artifact for artifact, _shard in feature_shards)

    token_paths: dict[str, str] = {}
    for token, matching in sorted(token_records.items()):
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        path = output_dir / "search" / "names" / f"{token_digest}.json.gz"
        _write_gzip_json(path, matching)
        artifact = _artifact(path, output_dir, "application/gzip")
        artifacts.append(artifact)
        token_paths[token] = artifact.path

    pages: list[str] = []
    for page_number, offset in enumerate(range(0, len(records), page_size)):
        page = f"{page_number:04d}"
        path = output_dir / "search" / "pages" / f"{page}.json.gz"
        _write_gzip_json(path, records[offset : offset + page_size])
        artifacts.append(_artifact(path, output_dir, "application/gzip"))
        pages.append(page)

    time_bands: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(DEFAULT_PERIODS):
        effective_start = max(start, minimum_year)
        effective_end = min(end, maximum_year)
        if effective_start > effective_end:
            continue
        matching = [
            record
            for record in records
            if record["valid_to"] >= effective_start and record["valid_from"] <= effective_end
        ]
        band_id = f"band-{index:02d}"
        path = output_dir / "search" / "time" / f"{band_id}.json.gz"
        _write_gzip_json(path, matching)
        artifact = _artifact(path, output_dir, "application/gzip")
        artifacts.append(artifact)
        time_bands.append(
            {
                "band_id": band_id,
                "valid_from": effective_start,
                "valid_to": effective_end,
                "path": artifact.path,
                "count": len(matching),
            }
        )

    index_path = output_dir / "search" / "index.json"
    _write_json(
        index_path,
        {
            "schema_version": "1.0.0",
            "semantics": "lazy-static-search-over-release-records",
            "normalization": "unicode-nfkd-lowercase-alphanumeric-spaces",
            "minimum_query_length": 2,
            "name_ngrams": {
                "length": 2,
                "paths": token_paths,
            },
            "records": {
                "path_template": "search/records/{shard}.json",
                "count": len(records),
                "shards": [shard for _artifact_file, shard in record_shards],
            },
            "features": {
                "path_template": "search/features/{shard}.json",
                "count": sum(len(record["feature_ids"]) for record in records),
                "shards": [shard for _artifact_file, shard in feature_shards],
            },
            "pages": {
                "path_template": "search/pages/{page}.json.gz",
                "page_size": page_size,
                "count": len(records),
                "pages": pages,
            },
            "time_bands": time_bands,
            "compression": "gzip",
        },
    )
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _record_search_names(record: dict[str, Any]) -> set[str]:
    return {
        *record["names"].values(),
        *(name["text"] for name in record["name_attestations"]),
    }


def _normalize_search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).lower()
    without_marks = "".join(
        character for character in decomposed if not unicodedata.category(character).startswith("M")
    )
    return " ".join(
        "".join(character if character.isalnum() else " " for character in without_marks).split()
    )


def _search_tokens(value: str) -> set[str]:
    normalized = _normalize_search_text(value)
    return {
        normalized[index : index + 2]
        for index in range(max(0, len(normalized) - 1))
        if " " not in normalized[index : index + 2]
    }


def _write_mapping_shards(
    buckets: dict[str, dict[str, Any]],
    directory: Path,
    output_root: Path,
) -> list[tuple[ArtifactFile, str]]:
    written: list[tuple[ArtifactFile, str]] = []
    for shard, values in sorted(buckets.items()):
        path = directory / f"{shard}.json"
        _write_json(path, values)
        written.append((_artifact(path, output_root, "application/json"), shard))
    return written


def _write_gzip_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            compressed.write(payload)


def content_shard(identifier: str, prefix_length: int = 2) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:prefix_length]


def canonical_entity_ids(feature: HistoricalFeature) -> list[str]:
    if feature.entity_ids:
        return feature.entity_ids
    if feature.wikidata_ids:
        return [f"wikidata:{qid}" for qid in feature.wikidata_ids]
    return [f"feature:{feature.feature_id}"]


def _build_content_artifacts(
    features: Iterable[HistoricalFeature],
    entities: Iterable[HistoricalEntity],
    dossiers: Iterable[HistoricalDossier],
    output_dir: Path,
    *,
    language_fallbacks: tuple[str, ...],
) -> list[ArtifactFile]:
    materialized_features = list(features)
    materialized_entities = list(entities)
    materialized_dossiers = list(dossiers)
    entity_by_id = {entity.entity_id: entity for entity in materialized_entities}
    dossiers_by_entity: dict[str, set[str]] = defaultdict(set)
    for dossier in materialized_dossiers:
        for entity_id in dossier.entity_ids:
            dossiers_by_entity[entity_id].add(dossier.dossier_id)

    links: list[FeatureContentLink] = []
    for feature in materialized_features:
        entity_ids = canonical_entity_ids(feature)
        dossier_ids = sorted(
            {
                dossier_id
                for entity_id in entity_ids
                for dossier_id in dossiers_by_entity.get(entity_id, set())
            }
        )
        related_ids: set[str] = set()
        for entity_id in entity_ids:
            entity = entity_by_id.get(entity_id)
            if entity:
                related_ids.update(
                    relationship.target_entity_id for relationship in entity.relationships
                )
        related = sorted(related_ids)
        links.append(
            FeatureContentLink(
                feature_id=feature.feature_id,
                primary_entity_id=entity_ids[0],
                entity_ids=entity_ids,
                available_entity_ids=sorted(
                    entity_id for entity_id in entity_ids if entity_id in entity_by_id
                ),
                missing_entity_ids=sorted(
                    entity_id for entity_id in entity_ids if entity_id not in entity_by_id
                ),
                dossier_ids=dossier_ids,
                related_entity_ids=related,
            )
        )

    artifacts: list[ArtifactFile] = []
    link_shards = _write_shards(
        links,
        identifier=lambda link: link.feature_id,
        directory=output_dir / "content" / "links",
        output_root=output_dir,
    )
    entity_shards = _write_shards(
        materialized_entities,
        identifier=lambda entity: entity.entity_id,
        directory=output_dir / "content" / "entities",
        output_root=output_dir,
    )
    dossier_shards = _write_shards(
        materialized_dossiers,
        identifier=lambda dossier: dossier.dossier_id,
        directory=output_dir / "content" / "dossiers",
        output_root=output_dir,
    )
    for artifact, _shard in (*link_shards, *entity_shards, *dossier_shards):
        artifacts.append(artifact)

    index_path = output_dir / "content" / "index.json"
    _write_json(
        index_path,
        ContentIndex.model_validate(
            {
                "schema_version": "1.0.0",
                "sharding": {
                    "algorithm": "sha256",
                    "encoding": "utf-8",
                    "prefix_length": 2,
                },
                "collections": {
                    "feature_links": {
                        "path_template": "content/links/{shard}.json",
                        "count": len(links),
                        "shards": [shard for _artifact_file, shard in link_shards],
                    },
                    "entities": {
                        "path_template": "content/entities/{shard}.json",
                        "count": len(materialized_entities),
                        "shards": [shard for _artifact_file, shard in entity_shards],
                    },
                    "dossiers": {
                        "path_template": "content/dossiers/{shard}.json",
                        "count": len(materialized_dossiers),
                        "shards": [shard for _artifact_file, shard in dossier_shards],
                    },
                },
                "language_policy": {
                    "selection": "requested-language-then-configured-fallback",
                    "available": sorted({dossier.language for dossier in materialized_dossiers}),
                    "fallback_order": list(language_fallbacks),
                    "no_indiscriminate_duplication": True,
                },
            }
        ).model_dump(mode="json"),
    )
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _write_shards(
    records: Iterable[Any],
    *,
    identifier: Any,
    directory: Path,
    output_root: Path,
) -> list[tuple[ArtifactFile, str]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(dict)
    for record in records:
        record_id = identifier(record)
        buckets[content_shard(record_id)][record_id] = record.model_dump(mode="json")
    written: list[tuple[ArtifactFile, str]] = []
    for shard, values in sorted(buckets.items()):
        path = directory / f"{shard}.json"
        _write_json(path, values)
        written.append((_artifact(path, output_root, "application/json"), shard))
    return written


def _build_wiki_context_artifacts(
    features: list[HistoricalFeature],
    entities: list[HistoricalEntity],
    dossiers: list[HistoricalDossier],
    output_dir: Path,
    *,
    options: dict[str, Any],
) -> list[ArtifactFile]:
    contexts = build_wiki_feature_contexts(features, entities, dossiers, options)
    shards = _write_shards(
        contexts,
        identifier=lambda context: context.feature_id,
        directory=output_dir / "context" / "features",
        output_root=output_dir,
    )
    artifacts = [artifact for artifact, _shard in shards]
    quotas = options.get("role_quotas") or {}
    index_path = output_dir / "context" / "index.json"
    index = WikiContextIndex.model_validate(
        {
            "sharding": {"algorithm": "sha256", "encoding": "utf-8", "prefix_length": 2},
            "feature_contexts": {
                "path_template": "context/features/{shard}.json",
                "count": len(contexts),
                "shards": [shard for _artifact, shard in shards],
            },
            "ranking_policy": {
                "algorithm": "bounded-explicit-relations-v1",
                "maximum_entities_per_feature": max(
                    1, min(int(options.get("max_context_entities_per_feature", 40)), 100)
                ),
                "temporal_margin_years": max(
                    0, min(int(options.get("temporal_margin_years", 50)), 500)
                ),
                "role_quotas": {
                    role.value: max(0, min(int(quotas.get(role.value, default)), 50))
                    for role, default in DEFAULT_ROLE_QUOTAS.items()
                },
                "evidence_basis": "Wikidata statements; references retained when supplied",
                "causal_claims_excluded": True,
            },
        }
    )
    _write_json(index_path, index.model_dump(mode="json"))
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _build_region_time_artifacts(
    features: list[HistoricalFeature],
    entities: list[HistoricalEntity],
    dossiers: list[HistoricalDossier],
    output_dir: Path,
    *,
    minimum_year: int,
    maximum_year: int,
) -> list[ArtifactFile]:
    buckets, bands = build_region_time_buckets(
        features,
        entities,
        dossiers,
        minimum_year=minimum_year,
        maximum_year=maximum_year,
    )
    shards = _write_shards(
        buckets,
        identifier=lambda bucket: bucket.bucket_id,
        directory=output_dir / "region-time" / "buckets",
        output_root=output_dir,
    )
    artifacts = [artifact for artifact, _shard in shards]
    index_path = output_dir / "region-time" / "index.json"
    index = RegionTimeIndex.model_validate(
        {
            "sharding": {
                "algorithm": "sha256",
                "encoding": "utf-8",
                "prefix_length": 2,
            },
            "grid": {
                "cell_degrees": GRID_DEGREES,
                "longitude_origin": -180,
                "latitude_origin": -90,
                "semantics": "discovery-grid-not-historical-regions",
            },
            "time_bands": [band.model_dump(mode="json") for band in bands],
            "buckets": {
                "path_template": "region-time/buckets/{shard}.json",
                "count": len(buckets),
                "shards": [shard for _artifact, shard in shards],
            },
            "maximum_results_per_selection": MAXIMUM_RESULTS_PER_SELECTION,
            "inclusion_policy": "reviewed-features-and-dated-coordinate-entities",
            "causal_claims_excluded": True,
        }
    )
    _write_json(index_path, index.model_dump(mode="json"))
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _build_causal_artifacts(dataset: CausalDataset, output_dir: Path) -> list[ArtifactFile]:
    claims = sorted(dataset.claims, key=lambda claim: claim.claim_id)
    paths = sorted(dataset.paths, key=lambda path: path.path_id)
    claims_by_id = {claim.claim_id: claim for claim in claims}
    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    paths_by_entity: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        for entity_id in claim.cause_entity_ids:
            outgoing[entity_id].add(claim.claim_id)
        for entity_id in claim.effect_entity_ids:
            incoming[entity_id].add(claim.claim_id)
    for path in paths:
        for claim_id in path.claim_ids:
            claim = claims_by_id[claim_id]
            for entity_id in {*claim.cause_entity_ids, *claim.effect_entity_ids}:
                paths_by_entity[entity_id].add(path.path_id)
    entity_ids = sorted({*incoming, *outgoing, *paths_by_entity})
    adjacency = [
        CausalEntityIndex(
            entity_id=entity_id,
            incoming_claim_ids=sorted(incoming[entity_id]),
            outgoing_claim_ids=sorted(outgoing[entity_id]),
            path_ids=sorted(paths_by_entity[entity_id]),
        )
        for entity_id in entity_ids
    ]

    claim_shards = _write_shards(
        claims,
        identifier=lambda claim: claim.claim_id,
        directory=output_dir / "causal" / "claims",
        output_root=output_dir,
    )
    entity_shards = _write_shards(
        adjacency,
        identifier=lambda entity: entity.entity_id,
        directory=output_dir / "causal" / "entities",
        output_root=output_dir,
    )
    path_shards = _write_shards(
        paths,
        identifier=lambda path: path.path_id,
        directory=output_dir / "causal" / "paths",
        output_root=output_dir,
    )
    artifacts = [artifact for artifact, _shard in (*claim_shards, *entity_shards, *path_shards)]
    index_path = output_dir / "causal" / "index.json"
    _write_json(
        index_path,
        CausalIndex.model_validate(
            {
                "schema_version": "1.0.0",
                "sharding": {
                    "algorithm": "sha256",
                    "encoding": "utf-8",
                    "prefix_length": 2,
                },
                "collections": {
                    "claims": {
                        "path_template": "causal/claims/{shard}.json",
                        "count": len(claims),
                        "shards": [shard for _artifact, shard in claim_shards],
                    },
                    "entities": {
                        "path_template": "causal/entities/{shard}.json",
                        "count": len(adjacency),
                        "shards": [shard for _artifact, shard in entity_shards],
                    },
                    "paths": {
                        "path_template": "causal/paths/{shard}.json",
                        "count": len(paths),
                        "shards": [shard for _artifact, shard in path_shards],
                    },
                },
            }
        ).model_dump(mode="json"),
    )
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _build_theme_artifacts(
    assertions: list[ThematicAssertion], output_dir: Path
) -> list[ArtifactFile]:
    ordered = sorted(assertions, key=lambda assertion: assertion.assertion_id)
    by_feature: dict[str, list[ThematicAssertion]] = defaultdict(list)
    for assertion in ordered:
        for feature_id in assertion.feature_ids:
            by_feature[feature_id].append(assertion)
    feature_indexes = [
        ThemeFeatureIndex(
            feature_id=feature_id,
            assertion_ids=sorted(assertion.assertion_id for assertion in feature_assertions),
            themes=sorted(
                {assertion.theme for assertion in feature_assertions},
                key=lambda theme: theme.value,
            ),
        )
        for feature_id, feature_assertions in sorted(by_feature.items())
    ]
    assertion_shards = _write_shards(
        ordered,
        identifier=lambda assertion: assertion.assertion_id,
        directory=output_dir / "themes" / "assertions",
        output_root=output_dir,
    )
    feature_shards = _write_shards(
        feature_indexes,
        identifier=lambda feature: feature.feature_id,
        directory=output_dir / "themes" / "features",
        output_root=output_dir,
    )
    artifacts = [artifact for artifact, _shard in (*assertion_shards, *feature_shards)]
    index_path = output_dir / "themes" / "index.json"
    index = ThemeIndex.model_validate(
        {
            "sharding": {
                "algorithm": "sha256",
                "encoding": "utf-8",
                "prefix_length": 2,
            },
            "collections": {
                "assertions": {
                    "path_template": "themes/assertions/{shard}.json",
                    "count": len(ordered),
                    "shards": [shard for _artifact, shard in assertion_shards],
                },
                "features": {
                    "path_template": "themes/features/{shard}.json",
                    "count": len(feature_indexes),
                    "shards": [shard for _artifact, shard in feature_shards],
                },
            },
        }
    )
    _write_json(index_path, index.model_dump(mode="json"))
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _build_assertion_artifacts(
    assertions: list[EvidenceAssertion], output_dir: Path
) -> list[ArtifactFile]:
    ordered = sorted(assertions, key=lambda assertion: assertion.assertion_id)
    by_entity: dict[str, set[str]] = defaultdict(set)
    by_feature: dict[str, set[str]] = defaultdict(set)
    for assertion in ordered:
        for entity_id in assertion.subject_entity_ids:
            by_entity[entity_id].add(assertion.assertion_id)
        if assertion.object.entity_id:
            by_entity[assertion.object.entity_id].add(assertion.assertion_id)
        for feature_id in assertion.feature_ids:
            by_feature[feature_id].add(assertion.assertion_id)
    entity_indexes = [
        AssertionAdjacency(subject_id=entity_id, assertion_ids=sorted(assertion_ids))
        for entity_id, assertion_ids in sorted(by_entity.items())
    ]
    feature_indexes = [
        AssertionAdjacency(subject_id=feature_id, assertion_ids=sorted(assertion_ids))
        for feature_id, assertion_ids in sorted(by_feature.items())
    ]
    record_shards = _write_shards(
        ordered,
        identifier=lambda assertion: assertion.assertion_id,
        directory=output_dir / "assertions" / "records",
        output_root=output_dir,
    )
    entity_shards = _write_shards(
        entity_indexes,
        identifier=lambda adjacency: adjacency.subject_id,
        directory=output_dir / "assertions" / "entities",
        output_root=output_dir,
    )
    feature_shards = _write_shards(
        feature_indexes,
        identifier=lambda adjacency: adjacency.subject_id,
        directory=output_dir / "assertions" / "features",
        output_root=output_dir,
    )
    artifacts = [
        artifact
        for artifact, _shard in (*record_shards, *entity_shards, *feature_shards)
    ]
    index_path = output_dir / "assertions" / "index.json"
    index = AssertionIndex.model_validate(
        {
            "sharding": {
                "algorithm": "sha256",
                "encoding": "utf-8",
                "prefix_length": 2,
            },
            "collections": {
                "records": {
                    "path_template": "assertions/records/{shard}.json",
                    "count": len(ordered),
                    "shards": [shard for _artifact, shard in record_shards],
                },
                "entities": {
                    "path_template": "assertions/entities/{shard}.json",
                    "count": len(entity_indexes),
                    "shards": [shard for _artifact, shard in entity_shards],
                },
                "features": {
                    "path_template": "assertions/features/{shard}.json",
                    "count": len(feature_indexes),
                    "shards": [shard for _artifact, shard in feature_shards],
                },
            },
        }
    )
    _write_json(index_path, index.model_dump(mode="json"))
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _build_layer_catalog(
    sources: list[SourceConfig],
    historical_maps: list[HistoricalMapMetadata],
    output_dir: Path,
) -> list[ArtifactFile]:
    reviewed_map_sources = sorted(
        source.id
        for source in sources
        if source.enabled and "historical_geometry" in {role.value for role in source.roles}
    )
    historical_image_sources = sorted(
        {
            reference.source_id
            for historical_map in historical_maps
            if historical_map.rendering is not None
            for reference in historical_map.source_refs
        }
    )
    layers = [
        LayerDefinition(
            layer_id="layer:map:modern-reference-geography",
            role=LayerRole.MAP_SOURCE,
            labels={"en": "Modern reference geography"},
            description=(
                "Contemporary Natural Earth land and physical water used only for "
                "orientation, not as historical or political authority."
            ),
        ),
        LayerDefinition(
            layer_id="layer:map:reviewed-release",
            role=LayerRole.MAP_SOURCE,
            labels={"en": "Reviewed release geometry"},
            description="Immutable, source-backed geometry published in this release.",
            source_ids=reviewed_map_sources,
        ),
        LayerDefinition(
            layer_id="layer:map:openhistoricalmap",
            role=LayerRole.MAP_SOURCE,
            labels={"en": "OpenHistoricalMap live context"},
            description=(
                "Live contributor context kept separate from immutable release geometry."
            ),
        ),
        LayerDefinition(
            layer_id="layer:map:historical-images",
            role=LayerRole.MAP_SOURCE,
            labels={"en": "Historical map images (optional)"},
            description=(
                "Rights-approved scanned-map depictions rendered as an optional image "
                "overlay; they are neither canonical geometry nor geographic authority."
            ),
            source_ids=historical_image_sources,
        ),
        *[
            LayerDefinition(
                layer_id=f"layer:lens:{theme.value}",
                role=LayerRole.THEMATIC_LENS,
                labels={"en": theme.value.replace("_", " ").title()},
                description="Foregrounds records with a published thematic assertion.",
                theme=theme,
            )
            for theme in HistoricalTheme
        ],
        *[
            LayerDefinition(
                layer_id=f"layer:confidence:{axis}",
                role=LayerRole.CONFIDENCE_OVERLAY,
                labels={"en": f"{axis.title()} confidence"},
                description=f"Styles records by their {axis} confidence grade.",
                confidence_axis=axis,
            )
            for axis in CONFIDENCE_AXES
        ],
        LayerDefinition(
            layer_id="layer:provenance:source",
            role=LayerRole.PROVENANCE_OVERLAY,
            labels={"en": "Source provenance"},
            description="Styles records by source identity while retaining licence metadata.",
        ),
    ]
    path = output_dir / "layers" / "index.json"
    catalog = LayerCatalog(layers=layers)
    _write_json(path, catalog.model_dump(mode="json"))
    return [_artifact(path, output_dir, "application/json")]


def _build_chronology_artifacts(
    periods: list[HistoricalPeriodDefinition],
    output_dir: Path,
    *,
    minimum_year: int,
    maximum_year: int,
) -> list[ArtifactFile]:
    definitions = sorted(periods, key=lambda period: period.period_id)
    by_entity: dict[str, set[str]] = defaultdict(set)
    for period in definitions:
        for coverage in period.spatial_coverage:
            if coverage.entity_id:
                by_entity[coverage.entity_id].add(period.period_id)
    entities = [
        ChronologyEntityIndex(entity_id=entity_id, period_ids=sorted(period_ids))
        for entity_id, period_ids in sorted(by_entity.items())
    ]
    definition_shards = _write_shards(
        definitions,
        identifier=lambda period: period.period_id,
        directory=output_dir / "chronology" / "definitions",
        output_root=output_dir,
    )
    entity_shards = _write_shards(
        entities,
        identifier=lambda entity: entity.entity_id,
        directory=output_dir / "chronology" / "entities",
        output_root=output_dir,
    )
    artifacts = [artifact for artifact, _shard in (*definition_shards, *entity_shards)]
    bands: list[ChronologyBandContract] = []
    for index, (start, end) in enumerate(DEFAULT_PERIODS):
        effective_start = max(start, minimum_year)
        effective_end = min(end, maximum_year)
        if effective_start > effective_end:
            continue
        period_ids = [
            period.period_id
            for period in definitions
            if period.valid_to >= effective_start and period.valid_from <= effective_end
        ]
        band_id = f"band-{index:02d}"
        path = output_dir / "chronology" / "time" / f"{band_id}.json"
        _write_json(path, period_ids)
        artifacts.append(_artifact(path, output_dir, "application/json"))
        bands.append(
            ChronologyBandContract(
                band_id=band_id,
                valid_from=effective_start,
                valid_to=effective_end,
                path=path.relative_to(output_dir).as_posix(),
                count=len(period_ids),
            )
        )
    index_path = output_dir / "chronology" / "index.json"
    _write_json(
        index_path,
        ChronologyIndex.model_validate(
            {
                "schema_version": "1.0.0",
                "semantics": "attributed-competing-period-definitions",
                "sharding": {
                    "algorithm": "sha256",
                    "encoding": "utf-8",
                    "prefix_length": 2,
                },
                "collections": {
                    "definitions": {
                        "path_template": "chronology/definitions/{shard}.json",
                        "count": len(definitions),
                        "shards": [shard for _artifact, shard in definition_shards],
                    },
                    "entities": {
                        "path_template": "chronology/entities/{shard}.json",
                        "count": len(entities),
                        "shards": [shard for _artifact, shard in entity_shards],
                    },
                },
                "time_bands": bands,
            }
        ).model_dump(mode="json"),
    )
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _coverage_priorities(coverage: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "political": {"polity"},
        "places": {"settlement", "archaeological_site"},
        "events": {"event"},
        "movement": {"route", "mobile_group"},
        "cultural_social": {"cultural_region", "social_group", "cultural_network"},
    }
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for cell in coverage:
        grouped[(cell["cell_id"], cell["valid_from"], cell["valid_to"])].append(cell)
    priorities = []
    for (cell_id, start, end), cells in sorted(grouped.items()):
        layer_counts = {str(cell["layer"]): int(cell["feature_count"]) for cell in cells}
        category_counts = {
            category: sum(layer_counts.get(layer, 0) for layer in layers)
            for category, layers in groups.items()
        }
        missing = sorted(category for category, count in category_counts.items() if count == 0)
        reviewed = sum(int(cell["reviewed_count"]) for cell in cells)
        represented = len(groups) - len(missing)
        severity = (
            "high" if represented <= 1 or reviewed == 0 else "medium" if represented <= 2 else "low"
        )
        priorities.append(
            {
                "cell_id": cell_id,
                "bounds": cells[0]["bounds"],
                "valid_from": start,
                "valid_to": end,
                "priority": severity,
                "category_counts": category_counts,
                "missing_categories": missing,
                "reviewed_feature_count": reviewed,
            }
        )
    return {
        "schema_version": "1.0.0",
        "methodology": {
            "scope": "observed 30-degree cells only",
            "warning": (
                "Absence from this report is not evidence of historical absence; fully empty "
                "cells require a reviewed land/region mask before prioritization."
            ),
            "categories": {key: sorted(value) for key, value in groups.items()},
        },
        "priorities": priorities,
    }


def _source_registry_entry(source: SourceConfig) -> SourceRegistryEntry:
    return SourceRegistryEntry(
        source_id=source.id,
        enabled=source.enabled,
        adapter=source.adapter,
        roles=source.roles,
        title=source.title,
        publisher=source.publisher,
        url=source.url,
        license_id=source.license_id,
        license_reviewed=source.license_reviewed,
        commercial_redistribution=CommercialRedistribution(source.commercial_redistribution),
        distribution_tier=DistributionTier(source.distribution_tier),
        redistribution_conditions=source.redistribution_conditions,
        separates_media_rights=bool(source.rights and source.rights.media),
        version=source.version,
        expected_checksum_sha256=source.expected_checksum_sha256,
        temporal_scope=source.temporal_scope,
        geographic_scope=source.geographic_scope,
        release_policy=source.release_policy,
        limitations=source.limitations,
    )


def _build_integration_artifacts(
    authority_matches: list[AuthorityMatch],
    historical_maps: list[HistoricalMapMetadata],
    output_dir: Path,
) -> list[ArtifactFile]:
    root = output_dir / "integrations"
    root.mkdir(parents=True, exist_ok=True)
    artifacts: list[ArtifactFile] = []

    matches_path = root / "authority-matches.ndjson"
    with NdjsonWriter(matches_path) as writer:
        for match in authority_matches:
            writer.write(match)
    artifacts.append(_artifact(matches_path, output_dir, "application/x-ndjson"))

    maps_path = root / "historical-maps.ndjson"
    with NdjsonWriter(maps_path) as writer:
        for historical_map in historical_maps:
            writer.write(historical_map)
    artifacts.append(_artifact(maps_path, output_dir, "application/x-ndjson"))

    index_path = root / "index.json"
    index = IntegrationIndex(
        authority_match_count=len(authority_matches),
        historical_map_count=len(historical_maps),
    )
    index_path.write_bytes(
        orjson.dumps(index.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
        + b"\n"
    )
    artifacts.append(_artifact(index_path, output_dir, "application/json"))
    return artifacts


def _attributions(
    features: Iterable[HistoricalFeature],
    indicators: Iterable[IndicatorObservation],
    periods: Iterable[HistoricalPeriodDefinition],
    entities: Iterable[HistoricalEntity],
    dossiers: Iterable[HistoricalDossier],
    causal: CausalDataset,
    authority_matches: Iterable[AuthorityMatch] = (),
    historical_maps: Iterable[HistoricalMapMetadata] = (),
) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    sources = [reference for feature in features for reference in feature.source_refs]
    sources.extend(observation.source_ref for observation in indicators)
    sources.extend(period.source_ref for period in periods)
    sources.extend(reference for entity in entities for reference in entity.source_refs)
    sources.extend(dossier.source_ref for dossier in dossiers)
    sources.extend(source for claim in causal.claims for source in claim.source_refs)
    sources.extend(match.source_ref for match in authority_matches)
    sources.extend(
        reference
        for historical_map in historical_maps
        for reference in historical_map.source_refs
    )
    for source in sources:
        key = (source.source_id, source.license_id)
        unique[key] = {
            "source_id": source.source_id,
            "title": source.title.split(":", 1)[0],
            "publisher": source.publisher,
            "url": str(source.url),
            "license_id": source.license_id,
            "citation": source.citation,
        }
    return [unique[key] for key in sorted(unique)]


def _artifact(path: Path, root: Path, media_type: str) -> ArtifactFile:
    return ArtifactFile(
        path=path.relative_to(root).as_posix(),
        media_type=media_type,
        bytes=path.stat().st_size,
        checksum_sha256=sha256_file(path),
        cache_control="public, max-age=31536000, immutable",
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(value, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n")


def compute_build_id(config_bytes: bytes, checksums: Iterable[str]) -> str:
    digest = hashlib.sha256(config_bytes)
    for checksum in sorted(checksums):
        digest.update(checksum.encode())
    return digest.hexdigest()[:16]
