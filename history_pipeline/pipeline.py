from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import orjson
from pydantic import HttpUrl

from history_pipeline.adapters import (
    AuthorityReconciliationAdapter,
    CliopatriaAdapter,
    CuratedSourceAdapter,
    GeoJsonAdapter,
    IiifMapAdapter,
    LinkedPlacesAdapter,
    OpenContextAdapter,
    OwidAdapter,
    PeriodoAdapter,
    PleiadesAdapter,
)
from history_pipeline.adapters.base import AdapterContext, RejectedRecord, SourceAdapter
from history_pipeline.adapters.wikidata import WikidataEnricher
from history_pipeline.adapters.wikipedia import WikipediaEnricher
from history_pipeline.artifacts import build_artifacts, compute_build_id
from history_pipeline.causal import load_causal_dataset, validate_causal_entities
from history_pipeline.config import PipelineConfig, config_fingerprint_bytes
from history_pipeline.curated import load_curated_records
from history_pipeline.enrichment import EnrichmentCheckpoint
from history_pipeline.licenses import enforce_source_license
from history_pipeline.models import (
    ArtifactFile,
    AuthorityMatch,
    BuildManifest,
    CausalDataset,
    EvidenceAssertion,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    HistoricalMapMetadata,
    HistoricalName,
    HistoricalPeriodDefinition,
    IndicatorObservation,
    LatestPointer,
    RawSnapshot,
    SourceReference,
    ThematicAssertion,
)
from history_pipeline.storage import DownloadCache, NdjsonWriter, RawAsset, sha256_file
from history_pipeline.themes import (
    apply_thematic_assertions,
    classify_features,
    load_theme_rules,
)
from history_pipeline.tiles import build_pmtiles
from history_pipeline.validation import Severity, validate_collection

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "cliopatria": CliopatriaAdapter,
    "curated": CuratedSourceAdapter,
    "geojson": GeoJsonAdapter,
    "linked_places": LinkedPlacesAdapter,
    "owid": OwidAdapter,
    "pleiades": PleiadesAdapter,
    "periodo": PeriodoAdapter,
    "open_context": OpenContextAdapter,
    "authority_reconciliation": AuthorityReconciliationAdapter,
    "iiif_maps": IiifMapAdapter,
}
WIKIMEDIA_CLIENT = re.compile(
    r"^[A-Za-z][A-Za-z0-9._-]{2,}/[A-Za-z0-9][A-Za-z0-9._-]*"
)
WIKIMEDIA_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}(?![\w.-])"
)
WIKIMEDIA_USER = re.compile(
    r"(?:^|[\s(;,])(?:[a-z][a-z0-9-]*:)?User:[^\s();,]+",
    re.IGNORECASE,
)
GENERIC_WIKIMEDIA_CLIENTS = {
    "curl",
    "httpx",
    "lwp",
    "python",
    "python-requests",
    "python-urllib",
    "requests",
    "urllib",
    "wget",
}


class PipelineRun:
    def __init__(
        self,
        config: PipelineConfig,
        config_path: Path,
        *,
        offline: bool = False,
        user_agent: str | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.offline = offline
        self.user_agent = user_agent or os.environ.get(
            config.user_agent_env, "HistoryJoiceDataPipeline/0.1 (local development)"
        )
        self.progress = progress

    def build(
        self,
        *,
        limit: int | None = None,
        enrich: bool = False,
        tiles: bool = False,
        tippecanoe: str | None = None,
        advance_latest: bool = True,
    ) -> BuildManifest:
        if enrich and not self.offline:
            self._validate_wikimedia_user_agent()
        self._prepare_directories()
        causal, causal_checksum = load_causal_dataset(self.config.causal_claims_path)
        theme_rules, theme_rules_checksum = load_theme_rules(self.config.theme_rules_path)
        curated, curated_checksum = load_curated_records(
            self.config.curated_records_path
        )
        features: list[HistoricalFeature] = list(curated.features)
        indicators: list[IndicatorObservation] = []
        periods: list[HistoricalPeriodDefinition] = []
        authority_matches: list[AuthorityMatch] = []
        historical_maps: list[HistoricalMapMetadata] = []
        entities: list[HistoricalEntity] = list(curated.entities)
        evidence_assertions: list[EvidenceAssertion] = list(curated.assertions)
        dossiers: list[HistoricalDossier] = []
        rejections: list[RejectedRecord] = []
        checksums: list[str] = []
        if causal_checksum:
            checksums.append(causal_checksum)
        if theme_rules_checksum:
            checksums.append(theme_rules_checksum)
        if curated_checksum:
            checksums.append(curated_checksum)
        raw_assets: list[tuple[str, RawAsset]] = []

        with DownloadCache(
            self.config.cache_dir,
            self.user_agent,
            offline=self.offline,
        ) as downloads:
            for source in self.config.sources:
                if not source.enabled:
                    continue
                enforce_source_license(
                    source.license_id,
                    source.license_reviewed,
                    self.config.license_policy,
                    source.id,
                )
                adapter_type = ADAPTERS.get(source.adapter)
                if adapter_type is None:
                    continue
                context = AdapterContext(
                    pipeline=self.config,
                    source=source,
                    downloads=downloads,
                    raw_source_dir=self.config.raw_dir / source.id,
                    staged_source_dir=self.config.staged_dir / source.id,
                )
                result = adapter_type().run(context, limit=limit)
                features.extend(result.features)
                indicators.extend(result.indicators)
                periods.extend(result.periods)
                authority_matches.extend(result.authority_matches)
                historical_maps.extend(result.historical_maps)
                rejections.extend(result.rejections)
                checksums.extend(asset.checksum_sha256 for asset in result.raw_assets)
                raw_assets.extend((source.id, asset) for asset in result.raw_assets)

        ingested_feature_count = len(features)
        ingested_indicator_count = len(indicators)
        ingested_period_count = len(periods)
        features, indicators = self._filter_to_scope(features, indicators)
        periods = self._filter_periods_to_scope(periods)
        scoped_feature_count = len(features)
        features = self._deduplicate_features(features)
        features = self._ensure_entity_links(features)
        deduplicated_feature_count = len(features)
        validation = validate_collection(features)
        invalid_ids = {
            issue.feature_id for issue in validation.issues if issue.severity == Severity.ERROR
        }
        accepted_features = [
            feature for feature in features if feature.feature_id not in invalid_ids
        ]
        for issue in validation.issues:
            if issue.severity == Severity.ERROR:
                rejections.append(
                    RejectedRecord("canonical", issue.feature_id, "validate", issue.message)
                )

        thematic_assertions = classify_features(accepted_features, theme_rules)
        accepted_features = apply_thematic_assertions(
            accepted_features, thematic_assertions
        )

        if enrich:
            checkpoint = self._enrichment_checkpoint(accepted_features)
            with DownloadCache(
                self.config.cache_dir,
                self.user_agent,
                offline=self.offline,
            ) as downloads:
                try:
                    enriched_entities, dossiers, enrichment_assets = self._enrich(
                        accepted_features,
                        downloads,
                        checkpoint=checkpoint,
                    )
                except Exception as error:
                    checkpoint.fail(error)
                    raise
            checkpoint.complete(
                entities=len(enriched_entities),
                dossiers=len(dossiers),
                raw_assets=len(enrichment_assets),
            )
            checksums.extend(asset.checksum_sha256 for _, asset in enrichment_assets)
            raw_assets.extend(enrichment_assets)
            entities = self._merge_entities(entities, enriched_entities)

        self._validate_causal_sources(causal)
        self._validate_evidence_assertions(
            evidence_assertions, accepted_features, entities
        )
        validate_causal_entities(causal, accepted_features, entities)

        self._write_staged(
            accepted_features,
            indicators,
            periods,
            entities,
            dossiers,
            causal,
            thematic_assertions,
            evidence_assertions,
            authority_matches,
            historical_maps,
            rejections,
            validation.issues,
        )
        builds_dir = self.config.dist_dir / "builds"
        builds_dir.mkdir(parents=True, exist_ok=True)
        temporary_build = Path(tempfile.mkdtemp(prefix=".build-", dir=builds_dir))
        input_id = compute_build_id(
            config_fingerprint_bytes(self.config_path),
            [*checksums, *(feature.feature_id for feature in accepted_features)],
        )
        tile_work = self.config.staged_dir / "tiles" / f"inputs-{input_id}"
        shutil.rmtree(tile_work, ignore_errors=True)
        try:
            artifacts = build_artifacts(
                accepted_features,
                indicators,
                entities,
                dossiers,
                temporary_build,
                periods=periods,
                causal=causal,
                thematic_assertions=thematic_assertions,
                evidence_assertions=evidence_assertions,
                quality_report=self._quality_report(
                    ingested_feature_count=ingested_feature_count,
                    ingested_indicator_count=ingested_indicator_count,
                    ingested_period_count=ingested_period_count,
                    scoped_feature_count=scoped_feature_count,
                    deduplicated_feature_count=deduplicated_feature_count,
                    accepted_feature_count=len(accepted_features),
                    accepted_indicator_count=len(indicators),
                    accepted_period_count=len(periods),
                    causal_claim_count=len(causal.claims),
                    causal_path_count=len(causal.paths),
                    thematic_assertion_count=len(thematic_assertions),
                    evidence_assertion_count=len(evidence_assertions),
                    rejections=rejections,
                    validation_issues=validation.issues,
                ),
                minimum_year=self.config.minimum_year,
                maximum_year=self.config.maximum_year,
                language_fallbacks=self._language_fallbacks(),
                sources=self.config.sources,
                authority_matches=authority_matches,
                historical_maps=historical_maps,
            )
            if tiles:
                artifacts.extend(
                    build_pmtiles(
                        accepted_features,
                        temporary_build,
                        tile_work,
                        tippecanoe,
                        minimum_zoom=self.config.tiles.minimum_zoom,
                        maximum_zoom=self.config.tiles.maximum_zoom,
                        simplification=self.config.tiles.simplification,
                        minimum_year=self.config.minimum_year,
                        maximum_year=self.config.maximum_year,
                    )
                )
        except Exception:
            shutil.rmtree(temporary_build, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(tile_work, ignore_errors=True)
        artifact_checksums = [artifact.checksum_sha256 for artifact in artifacts]
        build_id = compute_build_id(
            config_fingerprint_bytes(self.config_path), [*checksums, *artifact_checksums]
        )
        build_dir = builds_dir / build_id
        if build_dir.exists():
            self._verify_existing_build(build_dir, artifacts)
            shutil.rmtree(temporary_build)
        else:
            temporary_build.rename(build_dir)
        source_refs = self._unique_source_refs(
            accepted_features,
            indicators,
            periods,
            entities,
            dossiers,
            causal,
            evidence_assertions,
            authority_matches,
            historical_maps,
        )
        generated_at = max(
            (asset.retrieved_at for _, asset in raw_assets), default=datetime.now(UTC)
        )
        manifest = BuildManifest(
            build_id=build_id,
            minimum_year=self.config.minimum_year,
            maximum_year=self.config.maximum_year,
            sources=source_refs,
            raw_snapshots=self._raw_snapshots(raw_assets),
            artifacts=artifacts,
            rejected_record_count=len(rejections),
            coverage_path="coverage.json",
            attribution_path="attribution.json",
            quality_path="quality.json",
            generated_at=generated_at,
        )
        self._write_json(build_dir / "manifest.json", manifest.model_dump(mode="json"))
        manifest_path = build_dir / "manifest.json"
        pointer = LatestPointer(
            schema_version=manifest.schema_version,
            build_id=build_id,
            manifest=f"builds/{build_id}/manifest.json",
            manifest_checksum_sha256=sha256_file(manifest_path),
            generated_at=manifest.generated_at,
        )
        if advance_latest:
            self._write_json(
                self.config.dist_dir / "latest.json",
                pointer.model_dump(mode="json"),
            )
        return manifest

    def _language_fallbacks(self) -> tuple[str, ...]:
        for source in self.config.sources:
            if source.enabled and source.adapter == "wikipedia":
                primary = str(source.options.get("language", "en"))
                configured = [
                    str(language)
                    for language in source.options.get("fallback_languages", [primary])
                ]
                return tuple(dict.fromkeys([primary, *configured]))
        return ()

    def _validate_wikimedia_user_agent(self) -> None:
        wiki_enabled = any(
            source.enabled and source.adapter in {"wikidata", "wikipedia"}
            for source in self.config.sources
        )
        if wiki_enabled and not self._valid_wikimedia_user_agent(self.user_agent):
            raise ValueError(
                "Online Wikimedia enrichment requires a descriptive client/version and "
                "one contact channel: an email address, an HTTP(S) website, or a "
                "Wikimedia User:name"
            )

    @staticmethod
    def _valid_wikimedia_user_agent(value: str) -> bool:
        client = WIKIMEDIA_CLIENT.match(value.strip())
        if not client:
            return False
        client_name = client.group(0).split("/", 1)[0].casefold()
        if client_name in GENERIC_WIKIMEDIA_CLIENTS:
            return False
        if WIKIMEDIA_EMAIL.search(value) or WIKIMEDIA_USER.search(value):
            return True
        for candidate in re.findall(r"https?://[^\s();,]+", value):
            parsed = urlparse(candidate)
            if (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and "." in parsed.hostname
                and not parsed.username
                and not parsed.password
            ):
                return True
        return False

    def _enrichment_checkpoint(
        self, features: list[HistoricalFeature]
    ) -> EnrichmentCheckpoint:
        digest = hashlib.sha256()
        digest.update(config_fingerprint_bytes(self.config_path))
        for feature_id in sorted(feature.feature_id for feature in features):
            digest.update(b"\0")
            digest.update(feature_id.encode("utf-8"))
        return EnrichmentCheckpoint(
            self.config.staged_dir / "enrichment" / "status.json",
            digest.hexdigest()[:16],
            emit=self.progress,
        )

    def _validate_causal_sources(self, dataset: CausalDataset) -> None:
        for claim in dataset.claims:
            for source in claim.source_refs:
                enforce_source_license(
                    source.license_id,
                    source.license_reviewed,
                    self.config.license_policy,
                    source.source_id,
                )

    def _validate_evidence_assertions(
        self,
        assertions: list[EvidenceAssertion],
        features: list[HistoricalFeature],
        entities: list[HistoricalEntity],
    ) -> None:
        configured = {source.id: source for source in self.config.sources}
        feature_ids = {feature.feature_id for feature in features}
        entity_ids = {entity.entity_id for entity in entities}
        for assertion in assertions:
            linked_entities = set(assertion.subject_entity_ids)
            if assertion.object.entity_id:
                linked_entities.add(assertion.object.entity_id)
            missing_entities = linked_entities - entity_ids
            missing_features = set(assertion.feature_ids) - feature_ids
            if missing_entities or missing_features:
                missing = sorted({*missing_entities, *missing_features})
                raise ValueError(
                    f"Evidence assertion {assertion.assertion_id} references records "
                    f"absent from the release: {', '.join(missing)}"
                )
            for reference in assertion.source_refs:
                source = configured.get(reference.source_id)
                if source is None:
                    raise ValueError(
                        f"Evidence source is absent from pipeline.yml: {reference.source_id}"
                    )
                if source.license_id != reference.license_id:
                    raise ValueError(
                        f"Evidence source licence differs from pipeline.yml: "
                        f"{reference.source_id}"
                    )
                enforce_source_license(
                    reference.license_id,
                    source.license_reviewed,
                    self.config.license_policy,
                    reference.source_id,
                )

    @staticmethod
    def _merge_entities(
        curated: list[HistoricalEntity], enriched: list[HistoricalEntity]
    ) -> list[HistoricalEntity]:
        merged = {entity.entity_id: entity for entity in curated}
        for entity in enriched:
            if entity.entity_id in merged:
                raise ValueError(
                    f"Curated and enriched entities collide: {entity.entity_id}"
                )
            merged[entity.entity_id] = entity
        return [merged[entity_id] for entity_id in sorted(merged)]

    @staticmethod
    def _quality_report(
        *,
        ingested_feature_count: int,
        ingested_indicator_count: int,
        ingested_period_count: int,
        scoped_feature_count: int,
        deduplicated_feature_count: int,
        accepted_feature_count: int,
        accepted_indicator_count: int,
        accepted_period_count: int,
        causal_claim_count: int,
        causal_path_count: int,
        thematic_assertion_count: int,
        evidence_assertion_count: int,
        rejections: list[RejectedRecord],
        validation_issues: list[Any],
    ) -> dict[str, Any]:
        source_stage = Counter(
            f"{rejection.source_id}:{rejection.stage}" for rejection in rejections
        )
        reasons = Counter(rejection.reason.splitlines()[0] for rejection in rejections)
        validation_codes = Counter(issue.code for issue in validation_issues)
        return {
            "ingested_feature_count": ingested_feature_count,
            "ingested_indicator_count": ingested_indicator_count,
            "ingested_period_count": ingested_period_count,
            "scoped_feature_count": scoped_feature_count,
            "deduplicated_feature_count": deduplicated_feature_count,
            "accepted_feature_count": accepted_feature_count,
            "accepted_indicator_count": accepted_indicator_count,
            "accepted_period_count": accepted_period_count,
            "causal_claim_count": causal_claim_count,
            "causal_path_count": causal_path_count,
            "thematic_assertion_count": thematic_assertion_count,
            "evidence_assertion_count": evidence_assertion_count,
            "rejected_record_count": len(rejections),
            "rejections_by_source_stage": dict(sorted(source_stage.items())),
            "rejections_by_reason": dict(sorted(reasons.items())),
            "validation_issues_by_code": dict(sorted(validation_codes.items())),
        }

    @staticmethod
    def _verify_existing_build(build_dir: Path, artifacts: list[ArtifactFile]) -> None:
        for artifact in artifacts:
            path = build_dir / artifact.path
            if not path.is_file() or sha256_file(path) != artifact.checksum_sha256:
                raise ValueError(f"Existing content-addressed build is corrupt: {path}")

    def _filter_to_scope(
        self,
        features: list[HistoricalFeature],
        indicators: list[IndicatorObservation],
    ) -> tuple[list[HistoricalFeature], list[IndicatorObservation]]:
        """Exclude records that cannot appear inside this product's time window.

        Out-of-scope upstream records are not data errors, so they are deliberately
        excluded rather than added to the rejected-record count. Intersecting feature
        intervals retain their original dates to avoid falsifying source chronology.
        """

        scoped_features = [
            feature
            for feature in features
            if feature.valid_to >= self.config.minimum_year
            and feature.valid_from <= self.config.maximum_year
        ]
        scoped_indicators = [
            observation
            for observation in indicators
            if self.config.minimum_year <= observation.year <= self.config.maximum_year
        ]
        return scoped_features, scoped_indicators

    def _filter_periods_to_scope(
        self, periods: list[HistoricalPeriodDefinition]
    ) -> list[HistoricalPeriodDefinition]:
        return [
            period
            for period in periods
            if period.valid_to >= self.config.minimum_year
            and period.valid_from <= self.config.maximum_year
        ]

    @staticmethod
    def _deduplicate_features(
        features: list[HistoricalFeature],
    ) -> list[HistoricalFeature]:
        """Merge duplicate source rows when their canonical historical claim agrees.

        Cliopatria sometimes repeats the same geometry and interval to express complementary
        ``Components`` and ``MemberOf`` relationships. The stable feature ID intentionally
        collides in that case. Both record-level citations and all property values are retained.
        Conflicting canonical claims are left untouched so validation still rejects the collision.
        """

        grouped: dict[str, list[HistoricalFeature]] = {}
        for feature in features:
            grouped.setdefault(feature.feature_id, []).append(feature)
        output: list[HistoricalFeature] = []
        for group in grouped.values():
            if len(group) == 1:
                output.append(group[0])
                continue
            canonical_claims = {
                feature.model_dump_json(
                    exclude={
                        "properties",
                        "names",
                        "name_attestations",
                        "source_refs",
                        "wikidata_ids",
                        "wikipedia_titles",
                        "entity_ids",
                    }
                )
                for feature in group
            }
            if len(canonical_claims) != 1:
                output.extend(group)
                continue
            first = group[0]
            property_values: dict[str, list[Any]] = {}
            for feature in group:
                for key, value in feature.properties.items():
                    if value in (None, ""):
                        continue
                    values = property_values.setdefault(key, [])
                    serialized = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
                    if all(
                        orjson.dumps(existing, option=orjson.OPT_SORT_KEYS) != serialized
                        for existing in values
                    ):
                        values.append(value)
            properties: dict[str, Any] = {
                key: values[0] if len(values) == 1 else values
                for key, values in property_values.items()
            }
            properties["merged_upstream_records"] = len(group)
            names_by_language: dict[str, set[str]] = {}
            for feature in group:
                for language, name in feature.names.items():
                    names_by_language.setdefault(language, set()).add(name)
            names = {
                language: min(
                    values,
                    key=lambda value: (
                        value.count("(") + value.count(")"),
                        len(value),
                        value,
                    ),
                )
                for language, values in names_by_language.items()
            }
            alternate_names = sorted(
                {
                    name
                    for values in names_by_language.values()
                    for name in values
                    if name not in names.values()
                }
            )
            if alternate_names:
                properties["alternate_names"] = alternate_names
            name_attestations: dict[str, HistoricalName] = {}
            for feature in group:
                for attestation in feature.name_attestations:
                    existing = name_attestations.get(attestation.name_id)
                    references = {
                        (reference.source_id, reference.record_id): reference
                        for reference in (
                            *(existing.source_refs if existing else []),
                            *attestation.source_refs,
                        )
                    }
                    name_attestations[attestation.name_id] = attestation.model_copy(
                        update={"source_refs": list(references.values())}
                    )
            references = {
                (reference.source_id, reference.record_id): reference
                for feature in group
                for reference in feature.source_refs
            }
            output.append(
                first.model_copy(
                    update={
                        "properties": properties,
                        "names": names,
                        "name_attestations": list(name_attestations.values()),
                        "source_refs": list(references.values()),
                        "wikidata_ids": sorted(
                            {qid for feature in group for qid in feature.wikidata_ids}
                        ),
                        "entity_ids": sorted(
                            {entity for feature in group for entity in feature.entity_ids}
                        ),
                        "wikipedia_titles": {
                            language: title
                            for feature in group
                            for language, title in feature.wikipedia_titles.items()
                        },
                    }
                )
            )
        return output

    @staticmethod
    def _ensure_entity_links(
        features: list[HistoricalFeature],
    ) -> list[HistoricalFeature]:
        """Materialize the stable map-feature to content-entity join.

        Wikidata-backed entities use a namespaced QID. Features without a reconciled
        identifier retain a build-independent local entity ID instead of being grouped
        by a mutable display name.
        """

        linked: list[HistoricalFeature] = []
        for feature in features:
            entity_ids = list(feature.entity_ids)
            entity_ids.extend(f"wikidata:{qid}" for qid in feature.wikidata_ids)
            unique = list(dict.fromkeys(entity_ids))
            if not unique:
                unique = [f"feature:{feature.feature_id}"]
            linked.append(feature.model_copy(update={"entity_ids": unique}))
        return linked

    def _enrich(
        self,
        features: list[HistoricalFeature],
        downloads: DownloadCache,
        *,
        checkpoint: EnrichmentCheckpoint | None = None,
    ) -> tuple[
        list[HistoricalEntity], list[HistoricalDossier], list[tuple[str, RawAsset]]
    ]:
        by_adapter = {
            source.adapter: source
            for source in self.config.sources
            if source.enabled and source.adapter in {"wikidata", "wikipedia"}
        }
        entities: list[HistoricalEntity] = []
        dossiers: list[HistoricalDossier] = []
        assets: list[tuple[str, RawAsset]] = []
        if wikidata := by_adapter.get("wikidata"):
            enforce_source_license(
                wikidata.license_id,
                wikidata.license_reviewed,
                self.config.license_policy,
                wikidata.id,
            )
            qids = [qid for feature in features for qid in feature.wikidata_ids]
            entities, wikidata_assets = WikidataEnricher(
                wikidata, downloads, self.config.raw_dir / wikidata.id
            ).enrich(qids, checkpoint=checkpoint)
            assets.extend((wikidata.id, asset) for asset in wikidata_assets)
        if wikipedia := by_adapter.get("wikipedia"):
            enforce_source_license(
                wikipedia.license_id,
                wikipedia.license_reviewed,
                self.config.license_policy,
                wikipedia.id,
            )
            language = str(wikipedia.options.get("language", "en"))
            title_entities: dict[str, set[str]] = {}
            for feature in features:
                title = feature.wikipedia_titles.get(language)
                if title:
                    title_entities.setdefault(title, set()).update(feature.entity_ids)
            primary_entities = sorted(
                (entity for entity in entities if entity.context_depth == 0),
                key=lambda entity: entity.entity_id,
            )
            related_limit = max(
                0, min(int(wikipedia.options.get("max_related_pages", 1500)), 5000)
            )
            related_entities = sorted(
                (entity for entity in entities if entity.context_depth == 1),
                key=lambda entity: (
                    -len(entity.discovered_from_entity_ids),
                    entity.entity_id,
                ),
            )[:related_limit]
            for entity in [*primary_entities, *related_entities]:
                sitelink = entity.sitelinks.get(language)
                if sitelink:
                    title_entities.setdefault(sitelink.title, set()).add(entity.entity_id)
            dossiers, wikipedia_assets = WikipediaEnricher(
                wikipedia, downloads, self.config.raw_dir / wikipedia.id
            ).enrich(
                title_entities,
                entity_ids_by_title={
                    title: sorted(entity_ids)
                    for title, entity_ids in title_entities.items()
                },
                checkpoint=checkpoint,
            )
            assets.extend((wikipedia.id, asset) for asset in wikipedia_assets)
        return entities, dossiers, assets

    def _prepare_directories(self) -> None:
        for directory in (
            self.config.raw_dir,
            self.config.staged_dir,
            self.config.cache_dir,
            self.config.dist_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def _write_staged(
        self,
        features: list[HistoricalFeature],
        indicators: list[IndicatorObservation],
        periods: list[HistoricalPeriodDefinition],
        entities: list[HistoricalEntity],
        dossiers: list[HistoricalDossier],
        causal: CausalDataset,
        thematic_assertions: list[ThematicAssertion],
        evidence_assertions: list[EvidenceAssertion],
        authority_matches: list[AuthorityMatch],
        historical_maps: list[HistoricalMapMetadata],
        rejections: list[RejectedRecord],
        validation_issues: list[Any],
    ) -> None:
        staged = self.config.staged_dir / "canonical"
        datasets: tuple[tuple[str, list[Any]], ...] = (
            ("features.ndjson", features),
            ("indicators.ndjson", indicators),
            ("period-definitions.ndjson", periods),
            ("entities.ndjson", entities),
            ("dossiers.ndjson", dossiers),
            ("causal-claims.ndjson", causal.claims),
            ("causal-paths.ndjson", causal.paths),
            ("thematic-assertions.ndjson", thematic_assertions),
            ("evidence-assertions.ndjson", evidence_assertions),
            ("authority-matches.ndjson", authority_matches),
            ("historical-maps.ndjson", historical_maps),
            ("rejections.ndjson", [asdict(rejection) for rejection in rejections]),
            (
                "validation.ndjson",
                [
                    {
                        "feature_id": issue.feature_id,
                        "code": issue.code,
                        "severity": issue.severity.value,
                        "message": issue.message,
                    }
                    for issue in validation_issues
                ],
            ),
        )
        for filename, records in datasets:
            with NdjsonWriter(staged / filename) as writer:
                for record in records:
                    writer.write(record)

    @staticmethod
    def _unique_source_refs(
        features: list[HistoricalFeature],
        indicators: list[IndicatorObservation],
        periods: list[HistoricalPeriodDefinition],
        entities: list[HistoricalEntity],
        dossiers: list[HistoricalDossier],
        causal: CausalDataset,
        evidence_assertions: list[EvidenceAssertion],
        authority_matches: list[AuthorityMatch],
        historical_maps: list[HistoricalMapMetadata],
    ) -> list[SourceReference]:
        references = [reference for feature in features for reference in feature.source_refs]
        references.extend(observation.source_ref for observation in indicators)
        references.extend(period.source_ref for period in periods)
        references.extend(reference for entity in entities for reference in entity.source_refs)
        references.extend(dossier.source_ref for dossier in dossiers)
        references.extend(
            source for claim in causal.claims for source in claim.source_refs
        )
        references.extend(
            source
            for assertion in evidence_assertions
            for source in assertion.source_refs
        )
        references.extend(match.source_ref for match in authority_matches)
        references.extend(
            source for historical_map in historical_maps for source in historical_map.source_refs
        )
        unique: dict[str, SourceReference] = {}
        for reference in references:
            unique.setdefault(reference.source_id, reference)
        return [unique[key] for key in sorted(unique)]

    def _raw_snapshots(self, assets: list[tuple[str, RawAsset]]) -> list[RawSnapshot]:
        snapshots: dict[tuple[str, str], RawSnapshot] = {}
        for source_id, asset in assets:
            key = (source_id, asset.checksum_sha256)
            source_root = self.config.raw_dir / source_id
            relative_path = asset.path.relative_to(source_root).as_posix()
            snapshots[key] = RawSnapshot(
                source_id=source_id,
                filename=relative_path,
                original_url=HttpUrl(asset.url),
                object_key=(
                    f"snapshots/{source_id}/{asset.checksum_sha256}/{asset.path.name}"
                ),
                bytes=asset.path.stat().st_size,
                checksum_sha256=asset.checksum_sha256,
                retrieved_at=asset.retrieved_at,
                etag=asset.etag,
                last_modified=asset.last_modified,
            )
        return [snapshots[key] for key in sorted(snapshots)]

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            orjson.dumps(value, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(payload)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
