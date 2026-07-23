from __future__ import annotations

from pathlib import Path

from history_pipeline.models import FeatureKind, HistoricalTheme, ThemeRole
from history_pipeline.themes import (
    apply_thematic_assertions,
    classify_features,
    load_theme_rules,
)

RULES = Path("data/curation/theme-rules.yml")


def test_polity_classification_is_sourced_and_materialized(historical_feature) -> None:
    rules, checksum = load_theme_rules(RULES)

    assertions = classify_features([historical_feature], rules)
    features = apply_thematic_assertions([historical_feature], assertions)

    [assertion] = assertions
    assert checksum is not None
    assert assertion.theme == HistoricalTheme.POWER
    assert assertion.subtheme == "governance"
    assert assertion.matched_values == ["kind:polity"]
    assert assertion.feature_ids == [historical_feature.feature_id]
    assert assertion.source_refs == historical_feature.source_refs
    assert features[0].themes == [HistoricalTheme.POWER]


def test_explicit_place_types_can_produce_multiple_nonexclusive_assertions(
    historical_feature,
) -> None:
    rules, _checksum = load_theme_rules(RULES)
    source = historical_feature.source_refs[0].model_copy(
        update={"source_id": "pleiades"}
    )
    place = historical_feature.model_copy(
        update={
            "kind": FeatureKind.ARCHAEOLOGICAL_SITE,
            "source_refs": [source],
            "properties": {
                "place_types": ["temple", "market", "fortification"]
            },
            "themes": [],
        }
    )

    assertions = classify_features([place], rules)

    assert {assertion.theme for assertion in assertions} == {
        HistoricalTheme.POWER,
        HistoricalTheme.BELIEF,
        HistoricalTheme.TRADE,
    }
    assert all(assertion.role == ThemeRole.PRIMARY for assertion in assertions)
    assert apply_thematic_assertions([place], assertions)[0].themes == [
        HistoricalTheme.POWER,
        HistoricalTheme.BELIEF,
        HistoricalTheme.TRADE,
    ]


def test_classifier_uses_exact_structured_values_not_prose_or_substrings(
    historical_feature,
) -> None:
    rules, _checksum = load_theme_rules(RULES)
    source = historical_feature.source_refs[0].model_copy(
        update={"source_id": "pleiades"}
    )
    place = historical_feature.model_copy(
        update={
            "kind": FeatureKind.ARCHAEOLOGICAL_SITE,
            "source_refs": [source],
            "properties": {
                "place_types": ["marketplace"],
                "description": "A temple, palace, library, theatre, and port.",
            },
            "themes": [HistoricalTheme.POWER],
        }
    )

    assertions = classify_features([place], rules)

    assert assertions == []
    assert apply_thematic_assertions([place], assertions)[0].themes == []


def test_assertion_ids_are_deterministic(historical_feature) -> None:
    rules, _checksum = load_theme_rules(RULES)

    first = classify_features([historical_feature], rules)
    second = classify_features([historical_feature], rules)

    assert [item.assertion_id for item in first] == [
        item.assertion_id for item in second
    ]


def test_event_is_multi_label_only_from_its_own_structured_types(
    historical_feature,
) -> None:
    rules, _checksum = load_theme_rules(RULES)
    event = historical_feature.model_copy(
        update={
            "kind": FeatureKind.EVENT,
            "properties": {
                "event_types": ["publication"],
                "related_place_types": ["palace", "temple", "market"],
            },
            "themes": [],
        }
    )

    assertions = classify_features([event], rules)

    assert {assertion.theme for assertion in assertions} == {
        HistoricalTheme.KNOWLEDGE,
        HistoricalTheme.CULTURE,
    }
    assert all("properties.event_types:publication" in item.matched_values for item in assertions)


def test_generic_route_does_not_automatically_mean_trade(historical_feature) -> None:
    rules, _checksum = load_theme_rules(RULES)
    route = historical_feature.model_copy(
        update={"kind": FeatureKind.ROUTE, "properties": {}, "themes": []}
    )

    assert classify_features([route], rules) == []
