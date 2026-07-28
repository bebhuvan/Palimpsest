from __future__ import annotations

import hashlib
import shutil
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path

import orjson
from pydantic import HttpUrl

from history_pipeline.artifacts import build_artifacts, compute_build_id
from history_pipeline.curated import load_curated_records
from history_pipeline.models import (
    ArtifactFile,
    AuthorityMatch,
    BuildManifest,
    Confidence,
    ConfidenceGrade,
    DatePrecision,
    DossierRestatementContent,
    EntityRelationship,
    FeatureKind,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    HistoricalMapMetadata,
    HistoricalMapRendering,
    HistoricalTheme,
    LatestPointer,
    RawSnapshot,
    ReleaseRightsApproval,
    ReviewStatus,
    RightsReference,
    RightsScope,
    SourceReference,
    SpatialMeaning,
    TransformationStep,
)
from history_pipeline.restatement import build_restatement
from history_pipeline.storage import sha256_file
from history_pipeline.themes import (
    apply_thematic_assertions,
    classify_features,
    load_theme_rules,
)
from history_pipeline.tiles import build_pmtiles
from history_pipeline.verify import verify_latest_build

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "browser" / "fixtures" / "data"
GENERATED_AT = datetime(2026, 7, 23, 6, 0, tzinfo=UTC)


def source(
    source_id: str,
    *,
    title: str,
    publisher: str,
    url: str,
    license_id: str,
    record_id: str,
) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        record_id=record_id,
        title=title,
        publisher=publisher,
        url=HttpUrl(url),
        license_id=license_id,
        retrieved_at=GENERATED_AT,
        version="browser-pilot-v1",
        citation=f"{publisher}, {title}",
    )


def feature(
    feature_id: str,
    name: str,
    entity_id: str,
    coordinates: list[list[list[float]]],
    geometry_source: SourceReference,
) -> HistoricalFeature:
    confidence = Confidence(
        grade=ConfidenceGrade.B,
        rationale="Synthetic browser pilot with an explicit reviewed geometry contract.",
    )
    return HistoricalFeature(
        feature_id=feature_id,
        kind=FeatureKind.POLITY,
        spatial_meaning=SpatialMeaning.TERRITORIAL_CONTROL,
        names={"en": name},
        valid_from=50,
        valid_to=150,
        date_precision=DatePrecision.RANGE,
        geometry={"type": "Polygon", "coordinates": coordinates},
        temporal_confidence=confidence,
        spatial_confidence=confidence,
        interpretive_confidence=confidence,
        review_status=ReviewStatus.VERIFIED,
        source_refs=[geometry_source],
        themes=[HistoricalTheme.POWER],
        wikidata_ids=[entity_id.removeprefix("wikidata:")],
        entity_ids=[entity_id],
        wikipedia_titles={"en": name},
    )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        orjson.dumps(value, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"
    )


def historical_map_fixture_png(width: int = 320, height: int = 192) -> bytes:
    """Create a deterministic, test-only parchment raster without external assets."""

    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            grid = x % 40 in {0, 1} or y % 32 in {0, 1}
            diagonal = abs((x * 3 // 5 + 28) - y) < 3
            border = x < 5 or y < 5 or x >= width - 5 or y >= height - 5
            if border:
                color = (83, 58, 40)
            elif diagonal:
                color = (83, 118, 124)
            elif grid:
                color = (166, 137, 99)
            else:
                variation = (x * 7 + y * 11) % 13
                color = (226 - variation, 208 - variation, 170 - variation // 2)
            rows.extend(color)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    geometry_source = source(
        "browser-pilot",
        title="Browser pilot reviewed geometry",
        publisher="Palimpsest test suite",
        url="https://example.org/palimpsest/browser-pilot",
        license_id="CC0-1.0",
        record_id="geometry-v1",
    )
    wikidata_source = source(
        "wikidata",
        title="Wikidata browser-pilot entity projection",
        publisher="Wikimedia Foundation and Wikidata contributors",
        url="https://www.wikidata.org/wiki/Q100",
        license_id="CC0-1.0",
        record_id="Q100",
    )
    wikipedia_source = source(
        "wikipedia",
        title="Wikipedia browser-pilot introduction",
        publisher="Wikimedia Foundation and Wikipedia contributors",
        url="https://en.wikipedia.org/wiki/History",
        license_id="CC-BY-SA-4.0",
        record_id="100",
    )
    map_metadata_source = source(
        "browser-map-metadata",
        title="Deterministic IIIF historical-map fixture",
        publisher="Palimpsest test suite",
        url="https://example.org/palimpsest/iiif/manifest",
        license_id="CC0-1.0",
        record_id="fixture-manifest-v1",
    )
    map_georeference_source = source(
        "browser-map-georef",
        title="Deterministic IIIF georeference fixture",
        publisher="Palimpsest test suite",
        url="https://example.org/palimpsest/iiif/georeference",
        license_id="CC-BY-4.0",
        record_id="fixture-georeference-v1",
    )
    authority_source = source(
        "browser-authority",
        title="Synthetic gazetteer authority fixture",
        publisher="Palimpsest test suite",
        url="https://example.org/palimpsest/authority/pilot-place",
        license_id="CC0-1.0",
        record_id="pilot-place",
    )
    authority_match = AuthorityMatch(
        match_id="match:0123456789abcdef",
        subject_id="wikidata:Q100",
        authority_id="tgn:test-pilot-place",
        authority_namespace="tgn",
        label="Pilot Gazetteer Place",
        relation="close_match",
        review_status="accepted",
        confidence_score=92,
        confidence=Confidence(
            grade=ConfidenceGrade.B,
            rationale="Synthetic accepted match used to verify reader-facing release joins.",
        ),
        source_ref=authority_source,
        rights=RightsReference(
            scope=RightsScope.METADATA,
            license_id="CC0-1.0",
            attribution="Palimpsest test suite synthetic authority fixture",
        ),
        lineage=[
            TransformationStep(
                operation="create_browser_authority_fixture",
                tool="scripts.build-browser-pilot",
                tool_version="1.0.0",
                input_record_ids=["wikidata:Q100", "tgn:test-pilot-place"],
                parameters={"test_fixture": True},
            )
        ],
    )
    map_image = historical_map_fixture_png()
    map_image_checksum = hashlib.sha256(map_image).hexdigest()
    map_rendering = HistoricalMapRendering(
        image_path="historical-maps/browser-fixture-map.png",
        image_checksum_sha256=map_image_checksum,
        coordinates=[(12, 30), (32, 30), (32, 20), (12, 20)],
    )
    historical_map = HistoricalMapMetadata(
        map_id="map:0123456789abcdef",
        manifest_id=HttpUrl("https://example.org/palimpsest/iiif/manifest"),
        canvas_id=HttpUrl("https://example.org/palimpsest/iiif/canvas"),
        annotation_id=HttpUrl(
            "https://example.org/palimpsest/iiif/georeference"
        ),
        label="Browser fixture map sheet",
        depicted_date="circa 1750",
        providers=["Palimpsest test suite"],
        required_statement=(
            "Synthetic historical-map image © Palimpsest test suite; test use only."
        ),
        metadata_rights=RightsReference(
            scope=RightsScope.METADATA,
            license_id="CC0-1.0",
            attribution="Palimpsest test suite",
        ),
        image_rights=RightsReference(
            scope=RightsScope.MEDIA,
            license_id="PDM-1.0",
            attribution="Palimpsest test suite synthetic fixture",
        ),
        georeference_rights=RightsReference(
            scope=RightsScope.GEOREFERENCE,
            license_id="CC-BY-4.0",
            attribution="Palimpsest test suite georeference fixture",
        ),
        georeference_confidence=Confidence(
            grade=ConfidenceGrade.C,
            rationale=(
                "Deterministic test control points exercise the renderer; they are not "
                "historical evidence."
            ),
        ),
        known_limitations=[
            "This is a synthetic browser-test image, not a historical institution scan.",
            "The quadrilateral tests release wiring, not cartographic accuracy.",
        ],
        release_rights_approvals=[
            ReleaseRightsApproval(
                scope=RightsScope.METADATA,
                status="approved",
                decision_id="rights:browser-map:metadata",
                reviewed_by="Palimpsest test suite",
                reviewed_at=GENERATED_AT,
                rationale="Synthetic fixture metadata is approved for deterministic tests.",
            ),
            ReleaseRightsApproval(
                scope=RightsScope.MEDIA,
                status="approved",
                decision_id="rights:browser-map:media",
                reviewed_by="Palimpsest test suite",
                reviewed_at=GENERATED_AT,
                rationale="Synthetic fixture pixels are approved for deterministic tests.",
            ),
            ReleaseRightsApproval(
                scope=RightsScope.GEOREFERENCE,
                status="approved",
                decision_id="rights:browser-map:georeference",
                reviewed_by="Palimpsest test suite",
                reviewed_at=GENERATED_AT,
                rationale="Synthetic fixture georeference is approved for deterministic tests.",
            ),
        ],
        rendering=map_rendering,
        source_refs=[map_metadata_source, map_georeference_source],
        lineage=[
            TransformationStep(
                operation="generate_deterministic_historical_map_fixture",
                tool="scripts.build-browser-pilot",
                tool_version="1.0.0",
                input_record_ids=[
                    "fixture-manifest-v1",
                    "fixture-georeference-v1",
                ],
                parameters={
                    "test_fixture": True,
                    "authoritative_geography": False,
                    "iiif_georeference_compatible": True,
                },
            )
        ],
    )
    enriched = feature(
        "browser-pilot:enriched-place:50:150:aaaa",
        "Enriched Pilot Place",
        "wikidata:Q100",
        [[[13, 21], [21, 21], [21, 29], [13, 29], [13, 21]]],
        geometry_source,
    )
    missing = feature(
        "browser-pilot:missing-dossier-place:50:150:bbbb",
        "Undossiered Pilot Place",
        "wikidata:Q200",
        [[[23, 21], [31, 21], [31, 29], [23, 29], [23, 21]]],
        geometry_source,
    )
    seed = HistoricalEntity(
        entity_id="wikidata:Q100",
        entity_type="historical_country",
        names={"en": "Enriched Pilot Place"},
        descriptions={
            "en": "A fully enriched synthetic entity used to verify release joins."
        },
        valid_from=50,
        valid_to=150,
        wikidata_id="Q100",
        links={"wikidata": HttpUrl("https://www.wikidata.org/wiki/Q100")},
        relationships=[
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q101",
            )
        ],
        source_refs=[wikidata_source],
    )
    context = HistoricalEntity(
        entity_id="wikidata:Q101",
        entity_type="event",
        names={"en": "Pilot Context Event"},
        descriptions={"en": "A bounded related event loaded from a context shard."},
        valid_from=90,
        valid_to=110,
        wikidata_id="Q101",
        context_depth=1,
        discovered_from_entity_ids=["wikidata:Q100"],
        discovery_predicates=["P793"],
        links={"wikidata": HttpUrl("https://www.wikidata.org/wiki/Q101")},
        source_refs=[wikidata_source.model_copy(update={"record_id": "Q101"})],
    )
    selected_extract = (
        "Enriched Pilot Place is a synthetic settlement used to verify that revision-pinned "
        "tertiary summaries reach the reading sidebar.\n"
        "The settlement was founded in 60. It became a provincial seat in 95 and kept that role "
        "until the administration moved elsewhere. A synthetic archive records that its walls "
        "were rebuilt in 140.\n"
        "This saved browser-pilot introduction verifies that revision-pinned tertiary summaries "
        "reach the reading sidebar."
    )
    selected_dossier = HistoricalDossier(
        dossier_id="wikipedia:en:100",
        title="Enriched Pilot Place",
        language="en",
        entity_ids=["wikidata:Q100"],
        extract=selected_extract,
        url=HttpUrl("https://en.wikipedia.org/wiki/History"),
        page_id=100,
        revision_id=1000,
        revision_timestamp=GENERATED_AT,
        requested_titles=["Enriched Pilot Place"],
        content_checksum_sha256=hashlib.sha256(selected_extract.encode()).hexdigest(),
        source_ref=wikipedia_source,
    )
    # One restated dossier and one left raw, so the pilot covers both reading states.
    selected_restatement = build_restatement(
        DossierRestatementContent.model_validate(
            {
                "result": "restated",
                "headline": "A synthetic settlement that became a provincial seat",
                "text": (
                    "Enriched Pilot Place is a synthetic settlement.\n"
                    "It was founded in 60 and became a provincial seat in 95, keeping that role "
                    "until the administration moved elsewhere. A synthetic archive records that "
                    "its walls were rebuilt in 140."
                ),
                "timeline": [
                    {
                        "year_text": "60",
                        "sort_year": 60,
                        "text": "The settlement was founded",
                    },
                    {
                        "year_text": "95",
                        "sort_year": 95,
                        "text": "It became a provincial seat",
                    },
                    {"year_text": "140", "sort_year": 140, "text": "Its walls were rebuilt"},
                ],
                "unsuitable_reason": None,
            }
        ),
        selected_dossier,
        prompt_version="dossier-restate-v1",
        prompt_sha256=hashlib.sha256(
            (ROOT / "prompts" / "dossier-restate-v1.txt").read_bytes()
        ).hexdigest(),
        model_identifier="fixture:deterministic-restatement-v1",
        generated_at=GENERATED_AT,
    )

    context_dossier = HistoricalDossier(
        dossier_id="wikipedia:en:101",
        title="Pilot Context Event",
        language="en",
        entity_ids=["wikidata:Q101"],
        extract="A saved introduction for the related browser-pilot event.",
        url=HttpUrl("https://en.wikipedia.org/wiki/Historical_event"),
        page_id=101,
        revision_id=1010,
        revision_timestamp=GENERATED_AT,
        requested_titles=["Pilot Context Event"],
        content_checksum_sha256=hashlib.sha256(
            b"A saved introduction for the related browser-pilot event."
        ).hexdigest(),
        source_ref=wikipedia_source.model_copy(update={"record_id": "101"}),
    )
    curated, _curated_checksum = load_curated_records(
        ROOT / "data" / "curation" / "knowledge-1543.yml"
    )
    curated_snapshot = b'{"fixture":"loc-copernicus-92516339"}\n'
    curated_snapshot_checksum = hashlib.sha256(curated_snapshot).hexdigest()

    def pilot_refs(refs: list[SourceReference]) -> list[SourceReference]:
        return [
            ref.model_copy(
                update={
                    "checksum_sha256": curated_snapshot_checksum,
                    "retrieved_at": GENERATED_AT,
                    "version": "browser-pilot-curated-snapshot-v1",
                }
            )
            for ref in refs
        ]

    curated_features = [
        item.model_copy(update={"source_refs": pilot_refs(item.source_refs)})
        for item in curated.features
    ]
    curated_entities = [
        item.model_copy(update={"source_refs": pilot_refs(item.source_refs)})
        for item in curated.entities
    ]
    curated_assertions = [
        item.model_copy(update={"source_refs": pilot_refs(item.source_refs)})
        for item in curated.assertions
    ]
    features = [enriched, missing, *curated_features]
    entities = [seed, context, *curated_entities]
    dossiers = [selected_dossier, context_dossier]
    rules, _checksum = load_theme_rules(ROOT / "data" / "curation" / "theme-rules.yml")
    thematic_assertions = classify_features(features, rules)
    features = apply_thematic_assertions(features, thematic_assertions)

    work = OUTPUT.parent / ".data-build"
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(OUTPUT, ignore_errors=True)
    work.mkdir(parents=True)
    artifacts = build_artifacts(
        features,
        [],
        entities,
        dossiers,
        work,
        thematic_assertions=thematic_assertions,
        evidence_assertions=curated_assertions,
        quality_report={
            "accepted_feature_count": len(features),
            "accepted_indicator_count": 0,
            "rejected_record_count": 0,
        },
        minimum_year=-3400,
        maximum_year=2026,
        language_fallbacks=("en",),
        sources=[],
        authority_matches=[authority_match],
        historical_maps=[historical_map],
        restatements=[selected_restatement],
    )
    map_image_path = work / map_rendering.image_path
    map_image_path.parent.mkdir(parents=True, exist_ok=True)
    map_image_path.write_bytes(map_image)
    artifacts.append(
        ArtifactFile(
            path=map_rendering.image_path,
            media_type="image/png",
            bytes=len(map_image),
            checksum_sha256=map_image_checksum,
            cache_control="public, max-age=31536000, immutable",
        )
    )
    artifacts.extend(
        build_pmtiles(
            features,
            work,
            OUTPUT.parent / ".tile-work",
            str(ROOT / ".tools" / "bin" / "tippecanoe"),
            minimum_zoom=0,
            maximum_zoom=7,
            simplification=2.0,
            minimum_year=-3400,
            maximum_year=2026,
        )
    )
    build_id = compute_build_id(
        b"palimpsest-browser-pilot-v3",
        [artifact.checksum_sha256 for artifact in artifacts],
    )
    build_dir = OUTPUT / "builds" / build_id
    build_dir.parent.mkdir(parents=True, exist_ok=True)
    work.rename(build_dir)
    manifest = BuildManifest(
        build_id=build_id,
        generated_at=GENERATED_AT,
        minimum_year=-3400,
        maximum_year=2026,
        sources=[
            geometry_source,
            wikidata_source,
            wikipedia_source,
            map_metadata_source,
            map_georeference_source,
            authority_source,
            curated_features[0].source_refs[0],
        ],
        artifacts=artifacts,
        raw_snapshots=[
            RawSnapshot(
                source_id="loc_copernicus",
                filename="catalog-record.json",
                original_url=HttpUrl(
                    "https://www.loc.gov/pictures/item/92516339/?fo=json"
                ),
                object_key=(
                    "snapshots/loc_copernicus/"
                    f"{curated_snapshot_checksum}/catalog-record.json"
                ),
                checksum_sha256=curated_snapshot_checksum,
                bytes=len(curated_snapshot),
                retrieved_at=GENERATED_AT,
            )
        ],
        rejected_record_count=0,
        coverage_path="coverage.json",
        attribution_path="attribution.json",
    )
    manifest_path = build_dir / "manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))
    pointer = LatestPointer(
        schema_version=manifest.schema_version,
        build_id=build_id,
        manifest=f"builds/{build_id}/manifest.json",
        manifest_checksum_sha256=sha256_file(manifest_path),
        generated_at=GENERATED_AT,
    )
    write_json(OUTPUT / "latest.json", pointer.model_dump(mode="json"))
    raw_root = OUTPUT.parent / ".data-source-snapshots"
    snapshot_path = raw_root / "loc_copernicus" / "catalog-record.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(curated_snapshot)
    verify_latest_build(OUTPUT, raw_root, require_tiles=True)
    shutil.rmtree(raw_root)
    shutil.rmtree(OUTPUT.parent / ".tile-work", ignore_errors=True)
    print(f"Built browser pilot release {build_id}")


if __name__ == "__main__":
    main()
