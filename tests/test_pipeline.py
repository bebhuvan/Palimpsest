from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest
from pytest_httpx import HTTPXMock

from history_pipeline.config import PipelineConfig, SourceConfig
from history_pipeline.models import HistoricalFeature, SourceReference
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

    manifest = PipelineRun(config, config_path, user_agent="HistoryJoice/test").build(
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
    run = PipelineRun(config, config_path, user_agent="HistoryJoice/test")

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
        "HistoryJoice/0.1 (https://history.example.org/contact)",
        "HistoryJoice/0.1 (data@example.org)",
        "HistoryJoice/0.1 (wikipedia:en; User:ExampleEditor)",
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
        "HistoryJoice/0.1",
        "curl/8.0 (https://example.org/contact)",
        "HistoryJoice/0.1 (http://localhost/contact)",
        "HistoryJoice/0.1 (not-an-email@example)",
    ],
)
def test_wikimedia_user_agent_rejects_generic_or_uncontactable_clients(
    user_agent: str,
) -> None:
    assert not PipelineRun._valid_wikimedia_user_agent(user_agent)
