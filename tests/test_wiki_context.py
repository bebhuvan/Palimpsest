from __future__ import annotations

from history_pipeline.adapters.wikidata import _select_expansion_qids
from history_pipeline.models import (
    EntityRelationship,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    SourceReference,
    WikidataReference,
    WikidataSnak,
)
from history_pipeline.wiki_context import build_wiki_feature_contexts


def _entity(
    qid: str,
    source: SourceReference,
    *,
    entity_type: str = "event",
    valid_from: int | None = None,
    valid_to: int | None = None,
    relationships: list[EntityRelationship] | None = None,
) -> HistoricalEntity:
    return HistoricalEntity(
        entity_id=f"wikidata:{qid}",
        wikidata_id=qid,
        entity_type=entity_type,
        names={"en": qid},
        valid_from=valid_from,
        valid_to=valid_to,
        relationships=relationships or [],
        source_refs=[source],
    )


def test_context_ranking_retains_references_and_filters_unrelated_time(
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    feature = historical_feature.model_copy(
        update={"entity_ids": ["wikidata:Q1"]}
    )
    cited = WikidataReference(
        reference_hash="reference-1",
        snaks=[WikidataSnak(predicate="P248", value={"id": "Q99"})],
    )
    seed = _entity(
        "Q1",
        source_reference,
        entity_type="historical_country",
        relationships=[
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q2",
                references=[cited],
            ),
            EntityRelationship(
                predicate="P156",
                relation_type="successor",
                target_entity_id="wikidata:Q3",
            ),
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q4",
            ),
        ],
    )
    event = _entity("Q2", source_reference, valid_from=-50, valid_to=20)
    successor = _entity(
        "Q3", source_reference, entity_type="historical_country", valid_from=900, valid_to=1100
    )
    unrelated_time = _entity("Q4", source_reference, valid_from=900, valid_to=1100)
    dossier = HistoricalDossier(
        dossier_id="wikipedia:en:2",
        title="Q2",
        language="en",
        entity_ids=["wikidata:Q2"],
        extract="A saved introduction.",
        url="https://en.wikipedia.org/wiki/Q2",
        page_id=2,
        content_checksum_sha256="b" * 64,
        source_ref=source_reference,
    )

    [context] = build_wiki_feature_contexts(
        [feature], [seed, event, successor, unrelated_time], [dossier]
    )

    assert [item.context_entity_id for item in context.items] == [
        "wikidata:Q2",
        "wikidata:Q3",
    ]
    assert context.items[0].source_strength == "referenced_statement"
    assert context.items[0].dossier_ids == ["wikipedia:en:2"]
    assert "wikidata:Q4" not in {item.context_entity_id for item in context.items}


def test_depth_one_frontier_prioritizes_shared_targets_and_obeys_cap(
    source_reference: SourceReference,
) -> None:
    first = _entity(
        "Q1",
        source_reference,
        relationships=[
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q10",
            ),
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q20",
            ),
        ],
    )
    second = _entity(
        "Q2",
        source_reference,
        relationships=[
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q20",
            ),
            EntityRelationship(
                predicate="P793",
                relation_type="significant_event",
                target_entity_id="wikidata:Q30",
            ),
        ],
    )

    selected, discovered_from, predicates = _select_expansion_qids(
        [first, second], {"P793"}, per_seed=2, total=1
    )

    assert selected == ["Q20"]
    assert discovered_from == {"Q20": {"Q1", "Q2"}}
    assert predicates == {"Q20": {"P793"}}
