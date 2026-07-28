from __future__ import annotations

import gzip
from pathlib import Path

import geopandas as gpd
import orjson
import pytest

from history_pipeline.artifacts import _reading_eligibility, build_artifacts, content_shard
from history_pipeline.models import (
    EntityCoordinate,
    EntityRelationship,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    HistoricalPeriodDefinition,
    PeriodSpatialCoverage,
    SourceReference,
)
from history_pipeline.themes import classify_features, load_theme_rules
from history_pipeline.verify import (
    _verify_chronology_contract,
    _verify_content_contract,
    _verify_region_time_contract,
    _verify_search_contract,
    _verify_theme_contract,
    _verify_wiki_context_contract,
)


def test_artifact_build_writes_contract_files(
    tmp_path: Path,
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    period = HistoricalPeriodDefinition(
        period_id="periodo:p0testabc",
        authority_id="periodo:p0test",
        labels={"en": ["Test period"]},
        valid_from=-50,
        valid_to=50,
        start_label="50 BCE",
        stop_label="50 CE",
        spatial_coverage=[PeriodSpatialCoverage(label="Example", entity_id="wikidata:Q1")],
        authority_citation="Test scholarly chronology",
        source_ref=source_reference,
    )
    rules, _checksum = load_theme_rules(Path("data/curation/theme-rules.yml"))
    thematic_assertions = classify_features([historical_feature], rules)
    artifacts = build_artifacts(
        [historical_feature],
        [],
        [],
        [],
        tmp_path / "build",
        periods=[period],
        thematic_assertions=thematic_assertions,
    )
    paths = {artifact.path for artifact in artifacts}
    assert "features/ancient.parquet" in paths
    assert "features/medieval.parquet" not in paths
    assert "coverage.json" in paths
    assert "search.ndjson" in paths
    assert "search/index.json" in paths
    assert "attribution.json" in paths
    assert "quality.json" in paths
    assert "content/index.json" in paths
    assert "context/index.json" in paths
    assert "region-time/index.json" in paths
    assert "themes/index.json" in paths
    assert "chronology/index.json" in paths
    assert "source-registry.json" in paths
    assert "coverage-priorities.json" in paths
    assert "integrations/index.json" in paths
    assert "integrations/authority-matches.ndjson" in paths
    assert "integrations/historical-maps.ndjson" in paths

    chronology = orjson.loads((tmp_path / "build/chronology/index.json").read_bytes())
    assert chronology["semantics"] == "attributed-competing-period-definitions"
    assert chronology["collections"]["definitions"]["count"] == 1
    assert chronology["collections"]["entities"]["count"] == 1
    _verify_chronology_contract(tmp_path / "build", "chronology/index.json", paths)

    priorities = orjson.loads((tmp_path / "build/coverage-priorities.json").read_bytes())
    assert priorities["methodology"]["scope"] == "observed 30-degree cells only"

    context_index = orjson.loads((tmp_path / "build/context/index.json").read_bytes())
    assert context_index["feature_contexts"]["count"] == 0
    assert context_index["ranking_policy"]["causal_claims_excluded"] is True
    region_index = orjson.loads((tmp_path / "build/region-time/index.json").read_bytes())
    assert region_index["grid"]["semantics"] == "discovery-grid-not-historical-regions"
    content = _verify_content_contract(tmp_path / "build", "content/index.json", paths)
    _verify_theme_contract(tmp_path / "build", "themes/index.json", paths, content)
    _verify_region_time_contract(tmp_path / "build", "region-time/index.json", paths, content)

    shard = content_shard(historical_feature.feature_id)
    links = orjson.loads((tmp_path / f"build/content/links/{shard}.json").read_bytes())
    link = links[historical_feature.feature_id]
    assert link["primary_entity_id"] == "wikidata:Q1"
    assert link["missing_entity_ids"] == [link["primary_entity_id"]]
    assert link["reading_eligibility"] == [
        {
            "entity_id": "wikidata:Q1",
            "identity_basis": "source_asserted",
            "identity_relation": "exact_match",
            "temporal_overlap": "unknown",
            "reading_eligible": False,
            "reason_codes": ["entity_not_enriched"],
        }
    ]

    frame = gpd.read_parquet(tmp_path / "build/features/ancient.parquet")
    assert frame.iloc[0]["feature_id"] == historical_feature.feature_id
    assert '"text":"Example polity"' in frame.iloc[0]["name_attestations_json"]
    assert list(frame.iloc[0]["themes"]) == ["power"]
    assert frame.crs.to_epsg() == 4326

    search = orjson.loads((tmp_path / "build/search.ndjson").read_bytes().splitlines()[0])
    [name] = search["name_attestations"]
    assert name["feature_id"] == historical_feature.feature_id
    assert name["valid_from"] == -100
    assert name["valid_to"] == 100
    assert search["themes"] == ["power"]
    assert search["year_dossier_years"] == []

    search_index = orjson.loads((tmp_path / "build/search/index.json").read_bytes())
    assert search_index["semantics"] == "lazy-static-search-over-release-records"
    assert search_index["records"]["count"] == 1
    assert search_index["features"]["count"] == 1
    assert search_index["pages"]["count"] == 1
    token_path = search_index["name_ngrams"]["paths"]["po"]
    with gzip.open(tmp_path / "build" / token_path, "rb") as handle:
        token_records = orjson.loads(handle.read())
    assert token_records[0]["entity_id"] == search["entity_id"]
    _verify_search_contract(tmp_path / "build", "search/index.json", paths)
    with (tmp_path / "build" / token_path).open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:
            handle.write(b"[]")
    with pytest.raises(ValueError, match="postings are incomplete"):
        _verify_search_contract(tmp_path / "build", "search/index.json", paths)

    theme_index = orjson.loads((tmp_path / "build/themes/index.json").read_bytes())
    assert theme_index["semantics"] == "sourced-multi-label-thematic-assertions"
    assert theme_index["collections"]["assertions"]["count"] == 1


def test_primary_reading_requires_bounded_overlapping_identity(
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    overlapping = HistoricalEntity(
        entity_id="wikidata:Q1",
        entity_type="historical_country",
        names={"en": "Overlapping polity"},
        valid_from=-50,
        valid_to=50,
        source_refs=[source_reference],
    )
    incompatible = overlapping.model_copy(update={"valid_from": 395, "valid_to": 1453})
    undated = overlapping.model_copy(update={"valid_from": None, "valid_to": None})

    assert _reading_eligibility(
        historical_feature, overlapping.entity_id, overlapping
    ).reading_eligible
    rejected = _reading_eligibility(
        historical_feature, incompatible.entity_id, incompatible
    )
    assert rejected.temporal_overlap == "none"
    assert rejected.reason_codes == ["entity_interval_starts_after_feature"]
    assert not _reading_eligibility(
        historical_feature, undated.entity_id, undated
    ).reading_eligible


def test_pleiades_place_continuity_is_not_unqualified_primary_reading(
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    pleiades_source = source_reference.model_copy(update={"source_id": "pleiades"})
    feature = historical_feature.model_copy(update={"source_refs": [pleiades_source]})
    entity = HistoricalEntity(
        entity_id="wikidata:Q1",
        entity_type="human_settlement",
        names={"en": "Later settlement"},
        valid_from=-100,
        valid_to=100,
        source_refs=[source_reference],
    )

    decision = _reading_eligibility(feature, entity.entity_id, entity)

    assert decision.identity_relation == "place_continuity"
    assert decision.temporal_overlap == "overlaps"
    assert decision.reason_codes[-1] == "place_continuity_requires_review"
    assert not decision.reading_eligible


def test_polity_joined_to_broader_topic_is_not_primary_reading(
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    topic = HistoricalEntity(
        entity_id="wikidata:Q179848",
        entity_type="wikidata:Q518554",
        names={"en": "Scramble for Africa"},
        valid_from=-50,
        valid_to=50,
        source_refs=[source_reference],
    )

    decision = _reading_eligibility(historical_feature, topic.entity_id, topic)

    assert decision.identity_relation == "broader_topic"
    assert decision.temporal_overlap == "overlaps"
    assert decision.reason_codes[-1] == "entity_kind_incompatible_with_feature"
    assert not decision.reading_eligible


def test_wiki_context_artifacts_have_verified_stable_joins(
    tmp_path: Path,
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    feature = historical_feature.model_copy(update={"entity_ids": ["wikidata:Q1"]})
    seed = HistoricalEntity(
        entity_id="wikidata:Q1",
        entity_type="historical_country",
        names={"en": "Seed"},
        relationships=[
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q2",
            )
        ],
        source_refs=[source_reference],
    )
    event = HistoricalEntity(
        entity_id="wikidata:Q2",
        entity_type="event",
        names={"en": "Event"},
        valid_from=-50,
        valid_to=20,
        context_depth=1,
        discovered_from_entity_ids=["wikidata:Q1"],
        discovery_predicates=["P793"],
        coordinates=[EntityCoordinate(latitude=5, longitude=5, precision=0.1)],
        source_refs=[source_reference],
    )
    dossier = HistoricalDossier(
        dossier_id="wikipedia:en:2",
        title="Event",
        language="en",
        entity_ids=["wikidata:Q2"],
        extract="Saved revision text.",
        url="https://en.wikipedia.org/wiki/Event",
        page_id=2,
        content_checksum_sha256="c" * 64,
        source_ref=source_reference,
    )
    build_dir = tmp_path / "context-build"
    artifacts = build_artifacts([feature], [], [seed, event], [dossier], build_dir)
    paths = {artifact.path for artifact in artifacts}
    content = _verify_content_contract(build_dir, "content/index.json", paths)
    _verify_wiki_context_contract(build_dir, "context/index.json", paths, content)
    _verify_region_time_contract(build_dir, "region-time/index.json", paths, content)

    shard = content_shard(feature.feature_id)
    context_path = build_dir / f"context/features/{shard}.json"
    payload = orjson.loads(context_path.read_bytes())
    payload[feature.feature_id]["items"][0]["dossier_ids"] = ["missing:dossier"]
    context_path.write_bytes(orjson.dumps(payload))
    with pytest.raises(ValueError, match="Wiki context dossier is missing"):
        _verify_wiki_context_contract(build_dir, "context/index.json", paths, content)
