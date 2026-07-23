from __future__ import annotations

from collections import defaultdict
from typing import Any

from history_pipeline.models import (
    EntityRelationship,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    WikiContextItem,
    WikiContextRole,
    WikiFeatureContext,
)

DEFAULT_ROLE_QUOTAS = {
    WikiContextRole.PERSON: 12,
    WikiContextRole.EVENT: 12,
    WikiContextRole.INSTITUTION: 8,
    WikiContextRole.POLITY: 8,
    WikiContextRole.PLACE: 8,
    WikiContextRole.THEME: 8,
    WikiContextRole.OTHER: 4,
}

RELATION_WEIGHTS = {
    "significant_event": 45,
    "conflict": 45,
    "participant_in": 42,
    "participant": 40,
    "predecessor": 40,
    "successor": 40,
    "capital": 38,
    "founded_by": 38,
    "location": 36,
    "birth_place": 34,
    "death_place": 34,
    "contains_administrative_entity": 30,
    "part_of": 28,
    "has_part": 28,
    "member_of": 26,
    "country_or_parent_polity": 26,
    "located_in_territorial_entity": 26,
    "movement": 24,
    "main_subject": 24,
    "facet_of": 22,
    "position_held": 20,
    "occupation": 20,
    "genre": 16,
}

CONTINUITY_RELATIONS = {"predecessor", "successor"}


def build_wiki_feature_contexts(
    features: list[HistoricalFeature],
    entities: list[HistoricalEntity],
    dossiers: list[HistoricalDossier],
    options: dict[str, Any] | None = None,
) -> list[WikiFeatureContext]:
    options = options or {}
    maximum = max(1, min(int(options.get("max_context_entities_per_feature", 40)), 100))
    margin = max(0, min(int(options.get("temporal_margin_years", 50)), 500))
    configured_quotas = options.get("role_quotas") or {}
    quotas = {
        role: max(0, min(int(configured_quotas.get(role.value, default)), 50))
        for role, default in DEFAULT_ROLE_QUOTAS.items()
    }
    entity_by_id = {entity.entity_id: entity for entity in entities}
    dossiers_by_entity: dict[str, set[str]] = defaultdict(set)
    for dossier in dossiers:
        for entity_id in dossier.entity_ids:
            dossiers_by_entity[entity_id].add(dossier.dossier_id)

    output: list[WikiFeatureContext] = []
    for feature in sorted(features, key=lambda item: item.feature_id):
        seed_ids = [
            entity_id
            for entity_id in feature.entity_ids
            if entity_id in entity_by_id and entity_by_id[entity_id].context_depth == 0
        ]
        grouped: dict[str, list[EntityRelationship]] = defaultdict(list)
        for seed_id in seed_ids:
            for relationship in entity_by_id[seed_id].relationships:
                if relationship.target_entity_id in entity_by_id:
                    grouped[relationship.target_entity_id].append(relationship)
        candidates: list[WikiContextItem] = []
        for target_id, relationships in grouped.items():
            target = entity_by_id[target_id]
            relation_types = sorted({item.relation_type for item in relationships})
            temporal_state = _temporal_state(feature, target, margin)
            if temporal_state == "outside" and not set(relation_types) & CONTINUITY_RELATIONS:
                continue
            referenced = any(item.references for item in relationships)
            role = _context_role(target, relation_types)
            score = max(RELATION_WEIGHTS.get(item, 15) for item in relation_types)
            reasons = [f"Wikidata relation: {item}" for item in relation_types]
            if referenced:
                score += 20
                reasons.append("At least one Wikidata statement retains a reference")
            if temporal_state == "overlap":
                score += 20
                reasons.append("Entity chronology intersects the mapped feature")
            elif temporal_state == "unknown":
                score += 5
                reasons.append("Entity chronology is not bounded in the selected projection")
            else:
                score += 5
                reasons.append("Retained as an explicit predecessor or successor")
            if target.sitelinks:
                score += 10
                reasons.append("A configured-language Wikipedia sitelink is available")
            candidates.append(
                WikiContextItem(
                    context_entity_id=target_id,
                    role=role,
                    relationship_types=relation_types,
                    valid_from=target.valid_from,
                    valid_to=target.valid_to,
                    source_strength=(
                        "referenced_statement" if referenced else "wikidata_statement"
                    ),
                    score=min(score, 100),
                    selection_reasons=reasons,
                    dossier_ids=sorted(dossiers_by_entity[target_id]),
                )
            )
        counts: dict[WikiContextRole, int] = defaultdict(int)
        selected: list[WikiContextItem] = []
        for candidate in sorted(
            candidates, key=lambda item: (-item.score, item.context_entity_id)
        ):
            if len(selected) >= maximum:
                break
            if counts[candidate.role] >= quotas[candidate.role]:
                continue
            selected.append(candidate)
            counts[candidate.role] += 1
        if seed_ids:
            output.append(
                WikiFeatureContext(
                    feature_id=feature.feature_id,
                    seed_entity_ids=sorted(seed_ids),
                    items=selected,
                )
            )
    return output


def _temporal_state(
    feature: HistoricalFeature, entity: HistoricalEntity, margin: int
) -> str:
    if entity.valid_from is None and entity.valid_to is None:
        return "unknown"
    start = entity.valid_from if entity.valid_from is not None else entity.valid_to
    end = entity.valid_to if entity.valid_to is not None else entity.valid_from
    if start is None or end is None:
        return "unknown"
    if end < feature.valid_from - margin or start > feature.valid_to + margin:
        return "outside"
    return "overlap"


def _context_role(
    entity: HistoricalEntity, relationship_types: list[str]
) -> WikiContextRole:
    if entity.entity_type == "human":
        return WikiContextRole.PERSON
    if entity.entity_type in {
        "event",
        "occurrence",
        "historical_event",
        "war",
        "battle",
        "treaty",
    }:
        return WikiContextRole.EVENT
    if entity.entity_type in {"business_or_organization", "organization"}:
        return WikiContextRole.INSTITUTION
    if entity.entity_type in {"country", "historical_country", "sovereign_state"}:
        return WikiContextRole.POLITY
    if entity.entity_type == "human_settlement":
        return WikiContextRole.PLACE
    relation_set = set(relationship_types)
    if relation_set & {"significant_event", "conflict", "participant_in"}:
        return WikiContextRole.EVENT
    if relation_set & {"founded_by", "participant"}:
        return WikiContextRole.PERSON
    if relation_set & {"capital", "location", "birth_place", "death_place"}:
        return WikiContextRole.PLACE
    if relation_set & {"predecessor", "successor", "country_or_parent_polity"}:
        return WikiContextRole.POLITY
    if relation_set & {
        "movement",
        "genre",
        "main_subject",
        "facet_of",
        "occupation",
        "position_held",
    }:
        return WikiContextRole.THEME
    if relation_set & {"part_of", "has_part", "member_of"}:
        return WikiContextRole.INSTITUTION
    return WikiContextRole.OTHER
