from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from history_pipeline.models import (
    HistoricalFeature,
    HistoricalTheme,
    ReviewStatus,
    ThematicAssertion,
    ThemeRole,
    ThemeRule,
    ThemeRuleSet,
)

THEME_ORDER = {theme: index for index, theme in enumerate(HistoricalTheme)}


def load_theme_rules(path: Path | None) -> tuple[ThemeRuleSet, str | None]:
    """Load the reviewed classifier and retain its bytes in the build identity."""

    if path is None:
        return ThemeRuleSet(authored_by="History Joice", rules=[]), None
    if not path.is_file():
        raise FileNotFoundError(f"Configured theme rule file is missing: {path}")
    payload = path.read_bytes()
    rules = ThemeRuleSet.model_validate(yaml.safe_load(payload) or {})
    return rules, hashlib.sha256(payload).hexdigest()


def classify_features(
    features: list[HistoricalFeature], ruleset: ThemeRuleSet
) -> list[ThematicAssertion]:
    """Evaluate reviewed rules without inspecting names, descriptions, or prose."""

    assertions: list[ThematicAssertion] = []
    for feature in sorted(features, key=lambda item: item.feature_id):
        for rule in ruleset.rules:
            matched = _match_rule(feature, rule)
            if matched is None:
                continue
            identity = "\x1f".join(
                (
                    feature.feature_id,
                    rule.rule_id,
                    rule.theme.value,
                    rule.subtheme,
                    str(feature.valid_from),
                    str(feature.valid_to),
                )
            )
            assertions.append(
                ThematicAssertion(
                    assertion_id=(
                        f"theme:{hashlib.sha256(identity.encode()).hexdigest()[:16]}"
                    ),
                    subject_id=feature.feature_id,
                    subject_kind=feature.kind,
                    feature_ids=[feature.feature_id],
                    entity_ids=sorted(feature.entity_ids),
                    theme=rule.theme,
                    subtheme=rule.subtheme,
                    role=rule.role,
                    valid_from=feature.valid_from,
                    valid_to=feature.valid_to,
                    classification_basis=rule.classification_basis,
                    rule_id=rule.rule_id,
                    matched_values=matched,
                    confidence=rule.confidence,
                    review_status=rule.review_status,
                    rationale=rule.rationale,
                    source_refs=feature.source_refs,
                )
            )
    return assertions


def apply_thematic_assertions(
    features: list[HistoricalFeature], assertions: list[ThematicAssertion]
) -> list[HistoricalFeature]:
    """Materialize publishable themes as a tile/search shortcut.

    The assertion artifact remains authoritative. Contextual and rejected assertions
    never change map filtering.
    """

    by_feature: dict[str, set[HistoricalTheme]] = {}
    for assertion in assertions:
        if (
            assertion.role == ThemeRole.CONTEXTUAL
            or assertion.review_status == ReviewStatus.REJECTED
        ):
            continue
        for feature_id in assertion.feature_ids:
            by_feature.setdefault(feature_id, set()).add(assertion.theme)
    return [
        feature.model_copy(
            update={
                "themes": sorted(
                    by_feature.get(feature.feature_id, set()),
                    key=lambda theme: THEME_ORDER[theme],
                )
            }
        )
        for feature in features
    ]


def _match_rule(feature: HistoricalFeature, rule: ThemeRule) -> list[str] | None:
    matched: list[str] = []
    if rule.source_ids:
        feature_sources = {source.source_id for source in feature.source_refs}
        source_matches = sorted(feature_sources & set(rule.source_ids))
        if not source_matches:
            return None
        matched.extend(f"source:{value}" for value in source_matches)
    if rule.feature_kinds:
        if feature.kind not in rule.feature_kinds:
            return None
        matched.append(f"kind:{feature.kind.value}")
    if rule.spatial_meanings:
        if feature.spatial_meaning not in rule.spatial_meanings:
            return None
        matched.append(f"spatial_meaning:{feature.spatial_meaning.value}")
    if rule.property_path:
        property_name = rule.property_path.removeprefix("properties.")
        values = _structured_values(feature.properties.get(property_name))
        property_matches = sorted(values & {_normalize_value(item) for item in rule.match_any})
        if not property_matches:
            return None
        matched.extend(f"{rule.property_path}:{value}" for value in property_matches)
    return matched


def _structured_values(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        candidates = value
    elif isinstance(value, (str, int, float, bool)):
        candidates = [value]
    else:
        return set()
    return {_normalize_value(item) for item in candidates if str(item).strip()}


def _normalize_value(value: Any) -> str:
    text = str(value).strip().casefold().rstrip("/")
    text = text.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")
