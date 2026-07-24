from __future__ import annotations

from pathlib import Path

import orjson

from history_pipeline.artifacts import build_artifacts
from history_pipeline.config import load_config
from history_pipeline.curated import load_curated_records
from history_pipeline.models import EntityKind, LayerCatalog, LayerRole
from history_pipeline.themes import (
    apply_thematic_assertions,
    classify_features,
    load_theme_rules,
)
from history_pipeline.verify import (
    _verify_assertion_contract,
    _verify_content_contract,
    _verify_theme_contract,
)


def test_1543_slice_is_structured_sourced_and_multi_lens() -> None:
    records, checksum = load_curated_records(
        Path("data/curation/knowledge-1543.yml")
    )
    rules, _rules_checksum = load_theme_rules(Path("data/curation/theme-rules.yml"))

    assert checksum
    assert {entity.entity_kind for entity in records.entities} >= {
        EntityKind.PERSON,
        EntityKind.EVENT,
        EntityKind.INSTITUTION,
        EntityKind.WORK,
        EntityKind.PLACE,
    }
    assert len(records.features) == 3
    wiki_seeds = {
        item.feature_id: (item.wikidata_ids, item.wikipedia_titles)
        for item in records.features
    }
    assert wiki_seeds["historyjoice:publication-de-revolutionibus:1543"] == (
        ["Q20951088", "Q845981"],
        {"en": "De revolutionibus orbium coelestium"},
    )
    assert wiki_seeds["historyjoice:royal-cedula-vasco-de-quiroga:1543"] == (
        ["Q2990920"],
        {"en": "Vasco de Quiroga"},
    )
    assert wiki_seeds["historyjoice:tanegashima-firearms-tradition:1543"] == (
        ["Q358057"],
        {"en": "Tanegashima (gun)"},
    )
    feature = next(
        item
        for item in records.features
        if item.feature_id == "historyjoice:publication-de-revolutionibus:1543"
    )
    assertions = classify_features(records.features, rules)
    classified = {
        item.feature_id: item
        for item in apply_thematic_assertions(records.features, assertions)
    }
    assert "knowledge" in classified[feature.feature_id].model_dump(mode="json")["themes"]
    cedula = classified["historyjoice:royal-cedula-vasco-de-quiroga:1543"]
    assert set(cedula.model_dump(mode="json")["themes"]) == {"power"}
    cedula_lenses = {
        assertion.theme.value
        for assertion in assertions
        if assertion.subject_id == cedula.feature_id
    }
    assert cedula_lenses == {"belief", "power"}
    tanegashima = classified[
        "historyjoice:tanegashima-firearms-tradition:1543"
    ]
    assert set(tanegashima.model_dump(mode="json")["themes"]) == {
        "knowledge",
        "trade",
    }
    tanegashima_lenses = {
        assertion.theme.value
        for assertion in assertions
        if assertion.subject_id == tanegashima.feature_id
    }
    assert tanegashima_lenses == {"knowledge", "power", "trade"}
    assert feature.valid_from == feature.valid_to == 1543
    assert feature.temporal_uncertainty
    assert feature.spatial_uncertainty
    assert all(
        assertion.representation == "structured_sourced_assertion"
        and assertion.source_refs
        for assertion in records.assertions
    )


def test_copernicus_slice_publishes_verified_assertion_and_layer_contracts(
    tmp_path: Path,
) -> None:
    records, _checksum = load_curated_records(
        Path("data/curation/knowledge-1543.yml")
    )
    rules, _rules_checksum = load_theme_rules(Path("data/curation/theme-rules.yml"))
    thematic = classify_features(records.features, rules)
    features = apply_thematic_assertions(records.features, thematic)
    config = load_config(Path("config/pipeline.yml"))
    build_dir = tmp_path / "build"

    artifacts = build_artifacts(
        features,
        [],
        records.entities,
        [],
        build_dir,
        thematic_assertions=thematic,
        evidence_assertions=records.assertions,
        sources=config.sources,
    )
    paths = {artifact.path for artifact in artifacts}
    assert "assertions/index.json" in paths
    assert "layers/index.json" in paths

    content = _verify_content_contract(build_dir, "content/index.json", paths)
    _verify_theme_contract(build_dir, "themes/index.json", paths, content)
    _verify_assertion_contract(build_dir, "assertions/index.json", paths, content)

    index = orjson.loads((build_dir / "assertions/index.json").read_bytes())
    assert index["collections"]["records"]["count"] == len(records.assertions)
    catalog = LayerCatalog.model_validate_json(
        (build_dir / "layers/index.json").read_bytes()
    )
    assert {layer.role for layer in catalog.layers} == set(LayerRole)
    labels = {layer.labels["en"] for layer in catalog.layers}
    assert "Modern reference geography" in labels
    assert "Historical map images (optional)" in labels
