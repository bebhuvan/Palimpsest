from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest
from pytest_httpx import HTTPXMock

from history_pipeline.config import PipelineConfig, SourceConfig
from history_pipeline.models import (
    AssertionEvidenceBasis,
    AssertionObject,
    Confidence,
    DatePrecision,
    EvidenceAssertion,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    SourceReference,
)
from history_pipeline.pipeline import PipelineRun


def test_pipeline_filters_indicator_window_without_counting_scope_as_rejection(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "owid-population",
            "adapter": "owid",
            "title": "Population",
            "publisher": "Our World in Data",
            "url": "https://ourworldindata.org/grapher/population",
            "license_id": "CC-BY-4.0",
            "license_reviewed": True,
            "license_notes": "Fixture review",
            "citation": "Citation",
            "indicator_slug": "population",
        }
    )
    config = PipelineConfig(
        minimum_year=-3400,
        maximum_year=2026,
        raw_dir=tmp_path / "raw",
        staged_dir=tmp_path / "staged",
        cache_dir=tmp_path / "cache",
        dist_dir=tmp_path / "dist",
        sources=[source],
        license_policy={"allowed": [source.license_id]},
    )
    config_path = tmp_path / "pipeline.yml"
    config_path.write_text("fixture: true\n", encoding="utf-8")
    csv_url = (
        "https://ourworldindata.org/grapher/population.csv"
        "?v=1&csvType=full&useColumnShortNames=true"
    )
    metadata_url = (
        "https://ourworldindata.org/grapher/population.metadata.json"
        "?v=1&csvType=full&useColumnShortNames=true"
    )
    httpx_mock.add_response(
        url=csv_url,
        text=(
            "entity,code,year,population_historical\n"
            "Example,EXA,-4000,1\n"
            "Example,EXA,-3400,2\n"
            "Example,EXA,0,3\n"
            "Example,EXA,2027,4\n"
        ),
    )
    httpx_mock.add_response(
        url=metadata_url,
        json={"columns": {"population_historical": {"unit": "people"}}},
    )

    manifest = PipelineRun(config, config_path, user_agent="Palimpsest/test").build(
        advance_latest=False
    )

    assert manifest.rejected_record_count == 1
    assert manifest.sources[0].record_id == "EXA:-3400"
    indicator_path = (
        config.dist_dir / "builds" / manifest.build_id / "indicators" / "observations.parquet"
    )
    records = pq.read_table(indicator_path).to_pylist()
    assert [(record["year"], record["unit"]) for record in records] == [(-3400, "people")]
    assert not (config.dist_dir / "latest.json").exists()


def test_pipeline_merges_duplicate_relationship_rows_without_losing_provenance(
    historical_feature: HistoricalFeature,
) -> None:
    second_reference = SourceReference.model_validate(
        {
            **historical_feature.source_refs[0].model_dump(),
            "record_id": "record-2",
        }
    )
    first = historical_feature.model_copy(
        update={"properties": {"Components": "Example polity"}}
    )
    second = historical_feature.model_copy(
        update={
            "names": {"en": "(Example polity)"},
            "properties": {"MemberOf": "Example empire"},
            "source_refs": [second_reference],
        }
    )

    merged = PipelineRun._deduplicate_features([first, second])

    assert len(merged) == 1
    assert merged[0].properties == {
        "Components": "Example polity",
        "MemberOf": "Example empire",
        "merged_upstream_records": 2,
        "alternate_names": ["(Example polity)"],
    }
    assert merged[0].names == {"en": "Example polity"}
    assert [reference.record_id for reference in merged[0].source_refs] == [
        "record-1",
        "record-2",
    ]


def test_pipeline_links_seshat_assertions_by_exact_polity_id(
    historical_feature: HistoricalFeature,
) -> None:
    feature = historical_feature.model_copy(
        update={
            "properties": {"SeshatID": "eg_example"},
            "entity_ids": ["wikidata:Q1"],
        }
    )
    assertion = EvidenceAssertion(
        assertion_id="assertion:seshat:0123456789abcdef",
        subject_entity_ids=["seshat-polity:eg_example"],
        predicate="written_record",
        object=AssertionObject(kind="text", value="present"),
        valid_from=-100,
        valid_to=100,
        date_precision=DatePrecision.RANGE,
        confidence=Confidence(grade="B", rationale="Fixture evidence"),
        evidence_basis=AssertionEvidenceBasis.SCHOLARLY_ASSERTION,
        source_refs=historical_feature.source_refs,
    )

    [linked] = PipelineRun._link_source_assertions([assertion], [feature])

    assert linked.subject_entity_ids == ["wikidata:Q1"]
    assert linked.feature_ids == [feature.feature_id]


def test_pipeline_does_not_fan_parent_assertions_into_member_geometries(
    historical_feature: HistoricalFeature,
) -> None:
    parent = historical_feature.model_copy(
        update={
            "feature_id": "test-source:empire:-100:100:parent",
            "properties": {
                "SeshatID": "gb_example_empire",
                "Components": "Example colony",
            },
            "entity_ids": ["wikidata:Q1"],
        }
    )
    member = historical_feature.model_copy(
        update={
            "feature_id": "test-source:colony:-100:100:member",
            "properties": {
                "SeshatID": "gb_example_empire",
                "MemberOf": "(Example empire)",
            },
            "entity_ids": ["wikidata:Q2"],
        }
    )
    assertion = EvidenceAssertion(
        assertion_id="assertion:seshat:fedcba9876543210",
        subject_entity_ids=["seshat-polity:gb_example_empire"],
        predicate="polity_population",
        object=AssertionObject(
            kind="number_range", value_from=10, value_to=10, unit="people"
        ),
        valid_from=-100,
        valid_to=100,
        date_precision=DatePrecision.RANGE,
        confidence=Confidence(grade="B", rationale="Aggregate fixture evidence"),
        evidence_basis=AssertionEvidenceBasis.SCHOLARLY_ASSERTION,
        source_refs=historical_feature.source_refs,
    )

    [linked] = PipelineRun._link_source_assertions([assertion], [parent, member])

    assert linked.subject_entity_ids == ["wikidata:Q1"]
    assert linked.feature_ids == [parent.feature_id]


def test_publication_requirements_reject_capability_thin_latest(
    tmp_path: Path,
    historical_feature: HistoricalFeature,
) -> None:
    config = PipelineConfig(
        raw_dir=tmp_path / "raw",
        staged_dir=tmp_path / "staged",
        cache_dir=tmp_path / "cache",
        dist_dir=tmp_path / "dist",
        sources=[],
        license_policy={"allowed": []},
        publication_requirements={
            "require_year_pages": True,
            "minimum_feature_entity_coverage": 0.5,
            "minimum_feature_dossier_coverage": 0.5,
        },
    )
    feature = historical_feature.model_copy(
        update={"entity_ids": ["wikidata:Q1"]}
    )
    run = PipelineRun(config, tmp_path / "pipeline.yml")

    with pytest.raises(
        ValueError,
        match=(
            r"no year dossiers were loaded; "
            r"feature/entity coverage 0\.00% is below 50\.00%; "
            r"feature/dossier coverage 0\.00% is below 50\.00%"
        ),
    ):
        run._validate_publication_requirements(
            [feature], [], [], year_dossier_count=0
        )


def test_publication_requirements_accept_complete_reader_capabilities(
    tmp_path: Path,
    historical_feature: HistoricalFeature,
    source_reference: SourceReference,
) -> None:
    config = PipelineConfig(
        raw_dir=tmp_path / "raw",
        staged_dir=tmp_path / "staged",
        cache_dir=tmp_path / "cache",
        dist_dir=tmp_path / "dist",
        sources=[],
        license_policy={"allowed": []},
        publication_requirements={
            "require_year_pages": True,
            "minimum_feature_entity_coverage": 1,
            "minimum_feature_dossier_coverage": 1,
        },
    )
    feature = historical_feature.model_copy(
        update={"entity_ids": ["wikidata:Q1"]}
    )
    entity = HistoricalEntity(
        entity_id="wikidata:Q1",
        entity_type="polity",
        names={"en": "Example polity"},
        source_refs=[source_reference],
    )
    dossier = HistoricalDossier(
        dossier_id="wikipedia:en:1",
        title="Example polity",
        language="en",
        entity_ids=["wikidata:Q1"],
        extract="A saved source introduction.",
        url="https://en.wikipedia.org/wiki/Example",
        page_id=1,
        content_checksum_sha256="c" * 64,
        source_ref=source_reference,
    )

    PipelineRun(config, tmp_path / "pipeline.yml")._validate_publication_requirements(
        [feature], [entity], [dossier], year_dossier_count=1
    )


def test_enrichment_checkpoint_fingerprints_authority_inputs(
    tmp_path: Path, historical_feature: HistoricalFeature
) -> None:
    config = PipelineConfig(
        raw_dir=tmp_path / "raw",
        staged_dir=tmp_path / "staged",
        cache_dir=tmp_path / "cache",
        dist_dir=tmp_path / "dist",
        sources=[],
        license_policy={"allowed": []},
    )
    config_path = tmp_path / "pipeline.yml"
    config_path.write_text("sources: []\n", encoding="utf-8")
    run = PipelineRun(config, config_path, user_agent="Palimpsest/test")

    original = run._enrichment_checkpoint([historical_feature]).run_id
    changed_qid = run._enrichment_checkpoint(
        [historical_feature.model_copy(update={"wikidata_ids": ["Q2"]})]
    ).run_id
    changed_title = run._enrichment_checkpoint(
        [
            historical_feature.model_copy(
                update={"wikipedia_titles": {"en": "Different article"}}
            )
        ]
    ).run_id

    assert len({original, changed_qid, changed_title}) == 3


def test_online_enrichment_requires_contactable_user_agent(tmp_path: Path) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "wikidata",
            "adapter": "wikidata",
            "title": "Wikidata",
            "publisher": "Wikimedia",
            "url": "https://www.wikidata.org/w/api.php",
            "license_id": "CC0-1.0",
            "license_reviewed": True,
            "license_notes": "Fixture review",
            "citation": "Citation",
        }
    )
    config = PipelineConfig(
        raw_dir=tmp_path / "raw",
        staged_dir=tmp_path / "staged",
        cache_dir=tmp_path / "cache",
        dist_dir=tmp_path / "dist",
        sources=[source],
        license_policy={"allowed": [source.license_id]},
    )
    run = PipelineRun(config, tmp_path / "pipeline.yml", user_agent="local test")
    with pytest.raises(ValueError, match="descriptive client/version"):
        run.build(enrich=True)


@pytest.mark.parametrize(
    "user_agent",
    [
        "Palimpsest/0.1 (https://history.example.org/contact)",
        "Palimpsest/0.1 (data@example.org)",
        "Palimpsest/0.1 (wikipedia:en; User:ExampleEditor)",
    ],
)
def test_wikimedia_user_agent_accepts_one_valid_contact_channel(
    user_agent: str,
) -> None:
    assert PipelineRun._valid_wikimedia_user_agent(user_agent)


@pytest.mark.parametrize(
    "user_agent",
    [
        "local test",
        "Palimpsest/0.1",
        "curl/8.0 (https://example.org/contact)",
        "Palimpsest/0.1 (http://localhost/contact)",
        "Palimpsest/0.1 (not-an-email@example)",
    ],
)
def test_wikimedia_user_agent_rejects_generic_or_uncontactable_clients(
    user_agent: str,
) -> None:
    assert not PipelineRun._valid_wikimedia_user_agent(user_agent)
