from __future__ import annotations

import gzip
import hashlib
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, cast

import orjson

from history_pipeline.models import (
    AssertionAdjacency,
    AssertionIndex,
    BuildManifest,
    CausalDataset,
    CausalEntityIndex,
    EvidenceAssertion,
    LatestPointer,
    LayerCatalog,
    RegionTimeBucket,
    RegionTimeIndex,
    ThematicAssertion,
    ThemeFeatureIndex,
    ThemeIndex,
    WikiContextIndex,
    WikiFeatureContext,
)
from history_pipeline.region_time import cell_for_point
from history_pipeline.storage import sha256_file


def verify_latest_build(
    root: Path = Path("dist/data"),
    raw_root: Path = Path("data/raw"),
    *,
    require_tiles: bool = False,
) -> BuildManifest:
    latest = LatestPointer.model_validate(_read_object(root / "latest.json"))
    manifest_relative = _safe_relative(latest.manifest)
    manifest_path = root / manifest_relative
    if sha256_file(manifest_path) != latest.manifest_checksum_sha256:
        raise ValueError("latest.json manifest checksum does not match its manifest")
    manifest = BuildManifest.model_validate(_read_object(manifest_path))
    if latest.build_id != manifest.build_id:
        raise ValueError("latest.json build_id does not match its manifest")
    if manifest_path.parent.name != manifest.build_id:
        raise ValueError("Manifest path does not match its content-addressed build_id")

    paths: set[str] = set()
    for artifact in manifest.artifacts:
        if artifact.path in paths:
            raise ValueError(f"Duplicate artifact path: {artifact.path}")
        paths.add(artifact.path)
        artifact_path = manifest_path.parent / _safe_relative(artifact.path)
        _verify_file(artifact_path, artifact.bytes, artifact.checksum_sha256)

    if require_tiles and not any(path.endswith(".pmtiles") for path in paths):
        raise ValueError("Release verification requires at least one PMTiles artifact")
    contract_paths = {
        manifest.coverage_path,
        manifest.attribution_path,
        manifest.quality_path,
    }
    if _schema_at_least(manifest.schema_version, 1, 2):
        contract_paths.add(manifest.content_index_path)
    if _schema_at_least(manifest.schema_version, 1, 3):
        contract_paths.add(manifest.causal_index_path)
    if _schema_at_least(manifest.schema_version, 1, 4):
        contract_paths.update(
            {
                manifest.chronology_index_path,
                manifest.source_registry_path,
                manifest.coverage_priorities_path,
            }
        )
    if _schema_at_least(manifest.schema_version, 1, 8):
        contract_paths.add(manifest.theme_index_path)
    if _schema_at_least(manifest.schema_version, 1, 9):
        contract_paths.add(manifest.search_index_path)
    if _schema_at_least(manifest.schema_version, 1, 10):
        contract_paths.update(
            {manifest.assertion_index_path, manifest.layer_catalog_path}
        )
    if not contract_paths.issubset(paths):
        raise ValueError("Manifest contract paths are absent from its artifact list")
    content_records: dict[str, dict[str, Any]] = {}
    if _schema_at_least(manifest.schema_version, 1, 2):
        content_records = _verify_content_contract(
            manifest_path.parent, manifest.content_index_path, paths
        )
    if _schema_at_least(manifest.schema_version, 1, 3):
        _verify_causal_contract(manifest_path.parent, manifest.causal_index_path, paths)
    if _schema_at_least(manifest.schema_version, 1, 4):
        _verify_chronology_contract(manifest_path.parent, manifest.chronology_index_path, paths)
    if _schema_at_least(manifest.schema_version, 1, 5):
        if manifest.wiki_context_index_path not in paths:
            raise ValueError("Wiki context index is absent from artifact list")
        _verify_wiki_context_contract(
            manifest_path.parent,
            manifest.wiki_context_index_path,
            paths,
            content_records,
        )
    if _schema_at_least(manifest.schema_version, 1, 7):
        if manifest.region_time_index_path not in paths:
            raise ValueError("Region-time index is absent from artifact list")
        _verify_region_time_contract(
            manifest_path.parent,
            manifest.region_time_index_path,
            paths,
            content_records,
        )
    if _schema_at_least(manifest.schema_version, 1, 8):
        _verify_theme_contract(
            manifest_path.parent,
            manifest.theme_index_path,
            paths,
            content_records,
        )
    if _schema_at_least(manifest.schema_version, 1, 9):
        _verify_search_contract(
            manifest_path.parent,
            manifest.search_index_path,
            paths,
        )
    if _schema_at_least(manifest.schema_version, 1, 10):
        _verify_assertion_contract(
            manifest_path.parent,
            manifest.assertion_index_path,
            paths,
            content_records,
        )
        LayerCatalog.model_validate(
            _read_object(
                manifest_path.parent / _safe_relative(manifest.layer_catalog_path)
            )
        )

    snapshot_checksums: dict[str, set[str]] = {}
    for snapshot in manifest.raw_snapshots:
        snapshot_path = raw_root / snapshot.source_id / _safe_relative(snapshot.filename)
        _verify_file(snapshot_path, snapshot.bytes, snapshot.checksum_sha256)
        snapshot_checksums.setdefault(snapshot.source_id, set()).add(snapshot.checksum_sha256)
    for source in manifest.sources:
        if source.checksum_sha256 and source.checksum_sha256 not in snapshot_checksums.get(
            source.source_id, set()
        ):
            raise ValueError(f"Source {source.source_id} checksum has no matching raw snapshot")
    return manifest


def _verify_file(path: Path, expected_bytes: int, expected_checksum: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Release file is missing: {path}")
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"Release file size mismatch: {path}")
    if sha256_file(path) != expected_checksum:
        raise ValueError(f"Release file checksum mismatch: {path}")


def _safe_relative(value: str) -> Path:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe release path: {value}")
    return Path(*path.parts)


def _read_object(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = orjson.loads(handle.read())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _verify_content_contract(
    build_dir: Path, index_path: str, artifacts: set[str]
) -> dict[str, dict[str, Any]]:
    index = _read_object(build_dir / _safe_relative(index_path))
    sharding = index.get("sharding")
    if not isinstance(sharding, dict) or sharding.get("algorithm") != "sha256":
        raise ValueError("Unsupported content-index sharding contract")
    collections = index.get("collections")
    if not isinstance(collections, dict):
        raise ValueError("Content index has no collections")
    records_by_collection: dict[str, dict[str, Any]] = {}
    for name in ("feature_links", "entities", "dossiers"):
        collection = collections.get(name)
        if not isinstance(collection, dict):
            raise ValueError(f"Content index is missing {name}")
        template = collection.get("path_template")
        shards = collection.get("shards")
        if not isinstance(template, str) or template.count("{shard}") != 1:
            raise ValueError(f"Invalid content path template for {name}")
        if not isinstance(shards, list) or any(
            not isinstance(shard, str) or len(shard) != 2 for shard in shards
        ):
            raise ValueError(f"Invalid content shard list for {name}")
        records: dict[str, Any] = {}
        for shard in shards:
            relative = template.replace("{shard}", shard)
            if relative not in artifacts:
                raise ValueError(f"Content shard is absent from artifact list: {relative}")
            payload = _read_object(build_dir / _safe_relative(relative))
            overlap = records.keys() & payload.keys()
            if overlap:
                raise ValueError(f"Duplicate content IDs across shards: {sorted(overlap)}")
            records.update(payload)
        if len(records) != collection.get("count"):
            raise ValueError(f"Content count mismatch for {name}")
        records_by_collection[name] = records

    entities = records_by_collection["entities"]
    dossiers = records_by_collection["dossiers"]
    for feature_id, link in records_by_collection["feature_links"].items():
        if not isinstance(link, dict) or link.get("feature_id") != feature_id:
            raise ValueError(f"Malformed feature content link: {feature_id}")
        entity_ids = set(link.get("entity_ids", []))
        available = set(link.get("available_entity_ids", []))
        missing = set(link.get("missing_entity_ids", []))
        if available | missing != entity_ids or available & missing:
            raise ValueError(f"Feature link entity availability is inconsistent: {feature_id}")
        if any(entity_id not in entities for entity_id in available):
            raise ValueError(f"Feature link marks an unavailable entity as available: {feature_id}")
        for dossier_id in link.get("dossier_ids", []):
            if dossier_id not in dossiers:
                raise ValueError(f"Feature link references missing dossier: {dossier_id}")
    return records_by_collection


def _verify_wiki_context_contract(
    build_dir: Path,
    index_path: str,
    artifacts: set[str],
    content: dict[str, dict[str, Any]],
) -> None:
    index = WikiContextIndex.model_validate(_read_object(build_dir / _safe_relative(index_path)))
    collection = index.feature_contexts
    contexts: dict[str, WikiFeatureContext] = {}
    for shard in collection.shards:
        relative = collection.path_template.replace("{shard}", shard)
        if relative not in artifacts:
            raise ValueError(f"Wiki context shard is absent: {relative}")
        payload = _read_object(build_dir / _safe_relative(relative))
        for feature_id, raw_context in payload.items():
            expected = hashlib.sha256(feature_id.encode("utf-8")).hexdigest()[:2]
            if expected != shard:
                raise ValueError(f"Wiki context is in wrong shard: {feature_id}")
            if feature_id in contexts:
                raise ValueError(f"Duplicate wiki context: {feature_id}")
            context = WikiFeatureContext.model_validate(raw_context)
            if context.feature_id != feature_id:
                raise ValueError(f"Wiki context key does not match feature_id: {feature_id}")
            contexts[feature_id] = context
    if len(contexts) != collection.count:
        raise ValueError("Wiki context count mismatch")

    links = content.get("feature_links", {})
    entities = content.get("entities", {})
    dossiers = content.get("dossiers", {})
    for feature_id, context in contexts.items():
        if feature_id not in links:
            raise ValueError(f"Wiki context references missing feature: {feature_id}")
        if any(entity_id not in entities for entity_id in context.seed_entity_ids):
            raise ValueError(f"Wiki context seed entity is missing: {feature_id}")
        for item in context.items:
            if item.context_entity_id not in entities:
                raise ValueError(f"Wiki context entity is missing: {item.context_entity_id}")
            if any(dossier_id not in dossiers for dossier_id in item.dossier_ids):
                raise ValueError(f"Wiki context dossier is missing for {item.context_entity_id}")


def _verify_region_time_contract(
    build_dir: Path,
    index_path: str,
    artifacts: set[str],
    content: dict[str, dict[str, Any]],
) -> None:
    index = RegionTimeIndex.model_validate(_read_object(build_dir / _safe_relative(index_path)))
    bands = {band.band_id: band for band in index.time_bands}
    if len(bands) != len(index.time_bands):
        raise ValueError("Region-time bands must be unique")
    buckets: dict[str, RegionTimeBucket] = {}
    for shard in index.buckets.shards:
        relative = index.buckets.path_template.replace("{shard}", shard)
        if relative not in artifacts:
            raise ValueError(f"Region-time shard is absent: {relative}")
        payload = _read_object(build_dir / _safe_relative(relative))
        for bucket_id, raw_bucket in payload.items():
            expected = hashlib.sha256(bucket_id.encode("utf-8")).hexdigest()[:2]
            if expected != shard:
                raise ValueError(f"Region-time bucket is in wrong shard: {bucket_id}")
            if bucket_id in buckets:
                raise ValueError(f"Duplicate region-time bucket: {bucket_id}")
            bucket = RegionTimeBucket.model_validate(raw_bucket)
            if bucket.bucket_id != bucket_id:
                raise ValueError(f"Region-time key does not match bucket_id: {bucket_id}")
            band = bands.get(bucket.band_id)
            if not band or (bucket.valid_from, bucket.valid_to) != (
                band.valid_from,
                band.valid_to,
            ):
                raise ValueError(f"Region-time bucket has an invalid band: {bucket_id}")
            if bucket_id != f"{bucket.band_id}|{bucket.cell_id}":
                raise ValueError(f"Malformed region-time bucket ID: {bucket_id}")
            entry_ids = [entry.entry_id for entry in bucket.entries]
            if len(entry_ids) != len(set(entry_ids)):
                raise ValueError(f"Duplicate entries in region-time bucket: {bucket_id}")
            buckets[bucket_id] = bucket
    if len(buckets) != index.buckets.count:
        raise ValueError("Region-time bucket count mismatch")

    links = content.get("feature_links", {})
    entities = content.get("entities", {})
    dossiers = content.get("dossiers", {})
    for bucket in buckets.values():
        for entry in bucket.entries:
            if entry.valid_to < bucket.valid_from or entry.valid_from > bucket.valid_to:
                raise ValueError(f"Region-time entry does not intersect its band: {entry.entry_id}")
            if any(dossier_id not in dossiers for dossier_id in entry.dossier_ids):
                raise ValueError(f"Region-time entry references missing dossier: {entry.entry_id}")
            if entry.entry_type == "map_feature":
                link = links.get(entry.feature_id or "")
                if not isinstance(link, dict) or entry.entity_id not in link.get("entity_ids", []):
                    raise ValueError(f"Region-time feature join is invalid: {entry.entry_id}")
            else:
                if entry.entity_id not in entities:
                    raise ValueError(f"Region-time entity is missing: {entry.entity_id}")
                cell_id, _bounds = cell_for_point(
                    entry.longitude, entry.latitude, index.grid.cell_degrees
                )
                if cell_id != bucket.cell_id:
                    raise ValueError(
                        f"Region-time entity coordinate is in wrong cell: {entry.entry_id}"
                    )


def _verify_theme_contract(
    build_dir: Path,
    index_path: str,
    artifacts: set[str],
    content: dict[str, dict[str, Any]],
) -> None:
    index = ThemeIndex.model_validate(_read_object(build_dir / _safe_relative(index_path)))
    records: dict[str, dict[str, Any]] = {}
    for name in ("assertions", "features"):
        collection = getattr(index.collections, name)
        materialized: dict[str, Any] = {}
        for shard in collection.shards:
            relative = collection.path_template.replace("{shard}", shard)
            if relative not in artifacts:
                raise ValueError(f"Theme shard is absent: {relative}")
            payload = _read_object(build_dir / _safe_relative(relative))
            for record_id in payload:
                expected = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:2]
                if expected != shard:
                    raise ValueError(f"Theme record is in wrong shard: {record_id}")
            overlap = materialized.keys() & payload.keys()
            if overlap:
                raise ValueError(f"Duplicate theme IDs across shards: {sorted(overlap)}")
            materialized.update(payload)
        if len(materialized) != collection.count:
            raise ValueError(f"Theme count mismatch for {name}")
        records[name] = materialized

    assertions = {
        assertion_id: ThematicAssertion.model_validate(value)
        for assertion_id, value in records["assertions"].items()
    }
    feature_links = content.get("feature_links", {})
    for feature_id, raw_feature in records["features"].items():
        feature = ThemeFeatureIndex.model_validate(raw_feature)
        if feature.feature_id != feature_id:
            raise ValueError(f"Theme feature key mismatch: {feature_id}")
        if feature_links and feature_id not in feature_links:
            raise ValueError(f"Theme index references missing feature: {feature_id}")
        linked = [assertions.get(assertion_id) for assertion_id in feature.assertion_ids]
        if any(assertion is None for assertion in linked):
            raise ValueError(f"Theme index references missing assertion: {feature_id}")
        if any(feature_id not in assertion.feature_ids for assertion in linked if assertion):
            raise ValueError(f"Theme assertion join is inconsistent: {feature_id}")
        if set(feature.themes) != {assertion.theme for assertion in linked if assertion}:
            raise ValueError(f"Theme feature summary is inconsistent: {feature_id}")


def _verify_assertion_contract(
    build_dir: Path,
    index_path: str,
    artifacts: set[str],
    content: dict[str, dict[str, Any]],
) -> None:
    index = AssertionIndex.model_validate(
        _read_object(build_dir / _safe_relative(index_path))
    )
    materialized: dict[str, dict[str, Any]] = {}
    for name in ("records", "entities", "features"):
        collection = getattr(index.collections, name)
        records: dict[str, Any] = {}
        for shard in collection.shards:
            relative = collection.path_template.replace("{shard}", shard)
            if relative not in artifacts:
                raise ValueError(f"Assertion shard is absent: {relative}")
            payload = _read_object(build_dir / _safe_relative(relative))
            for record_id in payload:
                expected = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:2]
                if expected != shard:
                    raise ValueError(f"Assertion record is in wrong shard: {record_id}")
            overlap = records.keys() & payload.keys()
            if overlap:
                raise ValueError(
                    f"Duplicate assertion IDs across shards: {sorted(overlap)}"
                )
            records.update(payload)
        if len(records) != collection.count:
            raise ValueError(f"Assertion count mismatch for {name}")
        materialized[name] = records

    assertions = {
        assertion_id: EvidenceAssertion.model_validate(value)
        for assertion_id, value in materialized["records"].items()
    }
    entities = content.get("entities", {})
    feature_links = content.get("feature_links", {})
    expected_entities: dict[str, set[str]] = {}
    expected_features: dict[str, set[str]] = {}
    for assertion_id, assertion in assertions.items():
        linked_entities = set(assertion.subject_entity_ids)
        if assertion.object.entity_id:
            linked_entities.add(assertion.object.entity_id)
        if any(entity_id not in entities for entity_id in linked_entities):
            raise ValueError(
                f"Evidence assertion references a missing entity: {assertion_id}"
            )
        if any(feature_id not in feature_links for feature_id in assertion.feature_ids):
            raise ValueError(
                f"Evidence assertion references a missing feature: {assertion_id}"
            )
        for entity_id in linked_entities:
            expected_entities.setdefault(entity_id, set()).add(assertion_id)
        for feature_id in assertion.feature_ids:
            expected_features.setdefault(feature_id, set()).add(assertion_id)

    for name, expected_adjacency in (
        ("entities", expected_entities),
        ("features", expected_features),
    ):
        actual = {
            subject_id: AssertionAdjacency.model_validate(value)
            for subject_id, value in materialized[name].items()
        }
        if set(actual) != set(expected_adjacency):
            raise ValueError(f"Assertion {name} adjacency subjects are inconsistent")
        for subject_id, adjacency in actual.items():
            if (
                adjacency.subject_id != subject_id
                or set(adjacency.assertion_ids) != expected_adjacency[subject_id]
            ):
                raise ValueError(
                    f"Assertion {name} adjacency is inconsistent: {subject_id}"
                )


def _verify_search_contract(build_dir: Path, index_path: str, artifacts: set[str]) -> None:
    index = _read_object(build_dir / _safe_relative(index_path))
    if index.get("semantics") != "lazy-static-search-over-release-records":
        raise ValueError("Search index has unsupported semantics")
    if index.get("compression") != "gzip":
        raise ValueError("Search index has unsupported compression")

    record_contract = index.get("records")
    feature_contract = index.get("features")
    page_contract = index.get("pages")
    ngrams = index.get("name_ngrams")
    bands = index.get("time_bands")
    for name, contract, placeholder in (
        ("records", record_contract, "{shard}"),
        ("features", feature_contract, "{shard}"),
        ("pages", page_contract, "{page}"),
    ):
        if not isinstance(contract, dict):
            raise ValueError(f"Search index is missing {name}")
        template = contract.get("path_template")
        if not isinstance(template, str) or template.count(placeholder) != 1:
            raise ValueError(f"Invalid search path template for {name}")
    if (
        not isinstance(ngrams, dict)
        or ngrams.get("length") != 2
        or not isinstance(ngrams.get("paths"), dict)
    ):
        raise ValueError("Search index has an invalid n-gram contract")
    if not isinstance(bands, list):
        raise ValueError("Search index has invalid time bands")
    record_contract = cast(dict[str, Any], record_contract)
    feature_contract = cast(dict[str, Any], feature_contract)
    page_contract = cast(dict[str, Any], page_contract)
    ngrams = cast(dict[str, Any], ngrams)

    records: dict[str, dict[str, Any]] = {}
    for shard in record_contract.get("shards", []):
        if not isinstance(shard, str) or len(shard) != 2:
            raise ValueError("Search index has an invalid record shard")
        relative = record_contract["path_template"].replace("{shard}", shard)
        if relative not in artifacts:
            raise ValueError(f"Search record shard is absent: {relative}")
        record_payload = _read_object(build_dir / _safe_relative(relative))
        for entity_id, record in record_payload.items():
            if hashlib.sha256(entity_id.encode()).hexdigest()[:2] != shard:
                raise ValueError(f"Search record is in wrong shard: {entity_id}")
            if not isinstance(record, dict) or record.get("entity_id") != entity_id:
                raise ValueError(f"Malformed search record: {entity_id}")
        if records.keys() & record_payload.keys():
            raise ValueError("Duplicate search records across shards")
        records.update(record_payload)
    if len(records) != record_contract.get("count"):
        raise ValueError("Search record count mismatch")

    feature_ids: set[str] = set()
    for shard in feature_contract.get("shards", []):
        if not isinstance(shard, str) or len(shard) != 2:
            raise ValueError("Search index has an invalid feature shard")
        relative = feature_contract["path_template"].replace("{shard}", shard)
        if relative not in artifacts:
            raise ValueError(f"Search feature shard is absent: {relative}")
        feature_payload = _read_object(build_dir / _safe_relative(relative))
        for feature_id, entity_id in feature_payload.items():
            if hashlib.sha256(feature_id.encode()).hexdigest()[:2] != shard:
                raise ValueError(f"Search feature is in wrong shard: {feature_id}")
            record = records.get(entity_id)
            if not record or feature_id not in record.get("feature_ids", []):
                raise ValueError(f"Search feature join is invalid: {feature_id}")
            if feature_id in feature_ids:
                raise ValueError(f"Duplicate search feature: {feature_id}")
            feature_ids.add(feature_id)
    if len(feature_ids) != feature_contract.get("count"):
        raise ValueError("Search feature count mismatch")

    paged_ids: list[str] = []
    pages = page_contract.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Search index has an invalid page list")
    for page in pages:
        if not isinstance(page, str):
            raise ValueError("Search index has an invalid page name")
        relative = page_contract["path_template"].replace("{page}", page)
        if relative not in artifacts:
            raise ValueError(f"Search page is absent: {relative}")
        page_payload = _read_gzip_array(build_dir / _safe_relative(relative))
        for record in page_payload:
            if records.get(str(record.get("entity_id"))) != record:
                raise ValueError(f"Search page record differs from exact record: {relative}")
        paged_ids.extend(str(record.get("entity_id")) for record in page_payload)
    if paged_ids != sorted(records):
        raise ValueError("Search pages do not cover records in stable order")

    for band in bands:
        if not isinstance(band, dict) or not isinstance(band.get("path"), str):
            raise ValueError("Search index has a malformed time band")
        relative = band["path"]
        if relative not in artifacts:
            raise ValueError(f"Search time band is absent: {relative}")
        band_payload = _read_gzip_array(build_dir / _safe_relative(relative))
        if len(band_payload) != band.get("count"):
            raise ValueError(f"Search time-band count mismatch: {relative}")
        expected_band_ids = [
            entity_id
            for entity_id in sorted(records)
            if records[entity_id].get("valid_to", -(10**9)) >= band.get("valid_from", 0)
            and records[entity_id].get("valid_from", 10**9) <= band.get("valid_to", 0)
        ]
        actual_band_ids = [str(record.get("entity_id")) for record in band_payload]
        if actual_band_ids != expected_band_ids:
            raise ValueError(f"Search time band is incomplete or unordered: {relative}")
        for record in band_payload:
            if (
                records.get(str(record.get("entity_id"))) != record
                or record.get("valid_to", -(10**9)) < band.get("valid_from", 0)
                or record.get("valid_from", 10**9) > band.get("valid_to", 0)
            ):
                raise ValueError(f"Invalid search time-band record: {relative}")

    expected_tokens = {
        token
        for record in records.values()
        for name in _search_record_names(record)
        for token in _search_tokens(name)
    }
    token_paths = cast(dict[str, Any], ngrams["paths"])
    if set(token_paths) != expected_tokens:
        raise ValueError("Search n-gram tokens do not cover the published names")
    if len(set(token_paths.values())) != len(token_paths):
        raise ValueError("Search n-gram paths must be unique")
    for token, relative in token_paths.items():
        if not isinstance(relative, str) or relative not in artifacts:
            raise ValueError(f"Search n-gram shard is absent: {relative}")
        token_payload = _read_gzip_array(build_dir / _safe_relative(relative))
        expected_token_ids = [
            entity_id
            for entity_id in sorted(records)
            if any(
                token in _normalize_search_text(name)
                for name in _search_record_names(records[entity_id])
            )
        ]
        actual_token_ids = [str(record.get("entity_id")) for record in token_payload]
        if actual_token_ids != expected_token_ids:
            raise ValueError(f"Search n-gram postings are incomplete or unordered: {token}")
        for record in token_payload:
            posted_entity_id = record.get("entity_id")
            if records.get(str(posted_entity_id)) != record or not any(
                token in _normalize_search_text(name) for name in _search_record_names(record)
            ):
                raise ValueError(f"Invalid search n-gram posting: {token}")


def _read_gzip_array(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rb") as handle:
        payload = orjson.loads(handle.read())
    if not isinstance(payload, list) or any(not isinstance(record, dict) for record in payload):
        raise ValueError(f"Expected a gzip-compressed JSON array: {path}")
    return payload


def _search_record_names(record: dict[str, Any]) -> set[str]:
    names = record.get("names", {})
    attestations = record.get("name_attestations", [])
    if not isinstance(names, dict) or not isinstance(attestations, list):
        return set()
    return {
        *(str(name) for name in names.values()),
        *(
            str(attestation.get("text", ""))
            for attestation in attestations
            if isinstance(attestation, dict)
        ),
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


def _verify_causal_contract(build_dir: Path, index_path: str, artifacts: set[str]) -> None:
    index = _read_object(build_dir / _safe_relative(index_path))
    sharding = index.get("sharding")
    if not isinstance(sharding, dict) or sharding != {
        "algorithm": "sha256",
        "encoding": "utf-8",
        "prefix_length": 2,
    }:
        raise ValueError("Unsupported causal-index sharding contract")
    collections = index.get("collections")
    if not isinstance(collections, dict):
        raise ValueError("Causal index has no collections")
    records_by_collection: dict[str, dict[str, Any]] = {}
    for name in ("claims", "entities", "paths"):
        collection = collections.get(name)
        if not isinstance(collection, dict):
            raise ValueError(f"Causal index is missing {name}")
        template = collection.get("path_template")
        shards = collection.get("shards")
        if not isinstance(template, str) or template.count("{shard}") != 1:
            raise ValueError(f"Invalid causal path template for {name}")
        if not isinstance(shards, list) or any(
            not isinstance(shard, str) or len(shard) != 2 for shard in shards
        ):
            raise ValueError(f"Invalid causal shard list for {name}")
        records: dict[str, Any] = {}
        for shard in shards:
            relative = template.replace("{shard}", shard)
            if relative not in artifacts:
                raise ValueError(f"Causal shard is absent from artifact list: {relative}")
            payload = _read_object(build_dir / _safe_relative(relative))
            for record_id in payload:
                expected = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:2]
                if expected != shard:
                    raise ValueError(f"Causal record is in the wrong shard: {record_id}")
            overlap = records.keys() & payload.keys()
            if overlap:
                raise ValueError(f"Duplicate causal IDs across shards: {sorted(overlap)}")
            records.update(payload)
        if len(records) != collection.get("count"):
            raise ValueError(f"Causal count mismatch for {name}")
        records_by_collection[name] = records

    claims = records_by_collection["claims"]
    paths = records_by_collection["paths"]
    dataset = CausalDataset.model_validate(
        {"claims": list(claims.values()), "paths": list(paths.values())}
    )
    if any(claim.claim_id not in claims for claim in dataset.claims):
        raise ValueError("Causal claim key does not match its claim_id")
    if any(path.path_id not in paths for path in dataset.paths):
        raise ValueError("Causal path key does not match its path_id")

    adjacency = {
        entity_id: CausalEntityIndex.model_validate(record)
        for entity_id, record in records_by_collection["entities"].items()
    }
    expected_incoming: dict[str, set[str]] = {}
    expected_outgoing: dict[str, set[str]] = {}
    expected_paths: dict[str, set[str]] = {}
    claims_by_id = {claim.claim_id: claim for claim in dataset.claims}
    for claim in dataset.claims:
        for entity_id in claim.cause_entity_ids:
            expected_outgoing.setdefault(entity_id, set()).add(claim.claim_id)
        for entity_id in claim.effect_entity_ids:
            expected_incoming.setdefault(entity_id, set()).add(claim.claim_id)
    for path in dataset.paths:
        for claim_id in path.claim_ids:
            claim = claims_by_id[claim_id]
            for entity_id in {*claim.cause_entity_ids, *claim.effect_entity_ids}:
                expected_paths.setdefault(entity_id, set()).add(path.path_id)
    for entity_id, record in adjacency.items():
        if record.entity_id != entity_id:
            raise ValueError(f"Causal entity key does not match its entity_id: {entity_id}")
        for claim_id in record.incoming_claim_ids:
            raw_claim = claims.get(claim_id)
            if not isinstance(raw_claim, dict) or entity_id not in raw_claim.get(
                "effect_entity_ids", []
            ):
                raise ValueError(f"Invalid incoming causal adjacency: {entity_id}")
        for claim_id in record.outgoing_claim_ids:
            raw_claim = claims.get(claim_id)
            if not isinstance(raw_claim, dict) or entity_id not in raw_claim.get(
                "cause_entity_ids", []
            ):
                raise ValueError(f"Invalid outgoing causal adjacency: {entity_id}")
        if any(path_id not in paths for path_id in record.path_ids):
            raise ValueError(f"Causal adjacency references a missing path: {entity_id}")
        if set(record.incoming_claim_ids) != expected_incoming.get(entity_id, set()):
            raise ValueError(f"Incomplete incoming causal adjacency: {entity_id}")
        if set(record.outgoing_claim_ids) != expected_outgoing.get(entity_id, set()):
            raise ValueError(f"Incomplete outgoing causal adjacency: {entity_id}")
        if set(record.path_ids) != expected_paths.get(entity_id, set()):
            raise ValueError(f"Incomplete causal path adjacency: {entity_id}")
    referenced_entities = {
        entity_id
        for claim in dataset.claims
        for entity_id in (*claim.cause_entity_ids, *claim.effect_entity_ids)
    }
    if referenced_entities != set(adjacency):
        raise ValueError("Causal entity adjacency does not cover exactly the claim entities")


def _verify_chronology_contract(build_dir: Path, index_path: str, artifacts: set[str]) -> None:
    index = _read_object(build_dir / _safe_relative(index_path))
    if index.get("semantics") != "attributed-competing-period-definitions":
        raise ValueError("Chronology index must retain interpretive semantics")
    collections = index.get("collections")
    if not isinstance(collections, dict):
        raise ValueError("Chronology index has no collections")
    records_by_collection: dict[str, dict[str, Any]] = {}
    for name in ("definitions", "entities"):
        collection = collections.get(name)
        if not isinstance(collection, dict):
            raise ValueError(f"Chronology index is missing {name}")
        template = collection.get("path_template")
        shards = collection.get("shards")
        if not isinstance(template, str) or template.count("{shard}") != 1:
            raise ValueError(f"Invalid chronology path template for {name}")
        if not isinstance(shards, list):
            raise ValueError(f"Invalid chronology shard list for {name}")
        records: dict[str, Any] = {}
        for shard in shards:
            if not isinstance(shard, str) or len(shard) != 2:
                raise ValueError(f"Invalid chronology shard name for {name}")
            relative = template.replace("{shard}", shard)
            if relative not in artifacts:
                raise ValueError(f"Chronology shard is absent: {relative}")
            payload = _read_object(build_dir / _safe_relative(relative))
            for record_id in payload:
                expected = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:2]
                if expected != shard:
                    raise ValueError(f"Chronology record is in wrong shard: {record_id}")
            if records.keys() & payload.keys():
                raise ValueError(f"Duplicate chronology IDs in {name}")
            records.update(payload)
        if len(records) != collection.get("count"):
            raise ValueError(f"Chronology count mismatch for {name}")
        records_by_collection[name] = records

    definitions = records_by_collection["definitions"]
    for entity_id, record in records_by_collection["entities"].items():
        if not isinstance(record, dict) or record.get("entity_id") != entity_id:
            raise ValueError(f"Malformed chronology entity index: {entity_id}")
        if any(period_id not in definitions for period_id in record.get("period_ids", [])):
            raise ValueError(f"Chronology entity references missing definition: {entity_id}")

    for band in index.get("time_bands", []):
        if not isinstance(band, dict) or not isinstance(band.get("path"), str):
            raise ValueError("Malformed chronology time band")
        relative = band["path"]
        if relative not in artifacts:
            raise ValueError(f"Chronology time band is absent: {relative}")
        with (build_dir / _safe_relative(relative)).open("rb") as handle:
            period_ids = orjson.loads(handle.read())
        if not isinstance(period_ids, list) or len(period_ids) != band.get("count"):
            raise ValueError(f"Chronology time-band count mismatch: {relative}")
        if any(period_id not in definitions for period_id in period_ids):
            raise ValueError(f"Chronology time band references a missing period: {relative}")


def _schema_at_least(value: str, major: int, minor: int) -> bool:
    try:
        parts = value.split(".")
        return (int(parts[0]), int(parts[1])) >= (major, minor)
    except (IndexError, ValueError) as error:
        raise ValueError(f"Invalid schema version: {value}") from error
