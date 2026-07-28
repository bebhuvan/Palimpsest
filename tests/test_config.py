from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from history_pipeline.config import PipelineConfig, config_fingerprint_bytes, load_config


def test_open_core_and_research_overlay_are_distinct_enforceable_profiles() -> None:
    core = load_config(Path("config/pipeline.yml"))
    research = load_config(Path("config/research-overlay.yml"))

    assert core.distribution_profile == "open_core"
    assert core.license_policy.mode == "commercial"
    assert core.publication_requirements.require_year_pages is True
    assert core.publication_requirements.minimum_feature_entity_coverage == 0.40
    assert core.publication_requirements.minimum_feature_dossier_coverage == 0.45
    assert "CC-BY-NC-4.0" not in core.license_policy.allowed
    assert research.distribution_profile == "research"
    assert research.license_policy.mode == "noncommercial"
    assert "CC-BY-NC-4.0" in research.license_policy.allowed
    assert [source.id for source in research.sources[: len(core.sources)]] == [
        source.id for source in core.sources
    ]
    assert [source.id for source in research.sources[len(core.sources) :]] == [
        "getty_tgn_authority_pilot",
        "osm_authority_pilot",
        "whg_reconciliation",
    ]
    assert research.sources[-1].id == "whg_reconciliation"
    assert research.sources[-1].distribution_tier == "research_only"
    assert research.sources[-1].enabled is False
    assert config_fingerprint_bytes(Path("config/pipeline.yml")) != (
        config_fingerprint_bytes(Path("config/research-overlay.yml"))
    )


def test_open_core_rejects_enabled_research_only_source() -> None:
    source = {
        "id": "research-source",
        "adapter": "curated",
        "title": "Research source",
        "publisher": "Publisher",
        "url": "https://example.org/record.json",
        "license_id": "CC-BY-NC-4.0",
        "license_reviewed": True,
        "license_notes": "Reviewed non-commercial source.",
        "commercial_redistribution": "prohibited",
        "distribution_tier": "research_only",
        "citation": "Citation",
    }
    with pytest.raises(ValidationError, match="research_only"):
        PipelineConfig.model_validate(
            {
                "distribution_profile": "open_core",
                "sources": [source],
                "license_policy": {
                    "mode": "commercial",
                    "allowed": ["CC-BY-NC-4.0"],
                },
            }
        )


def test_open_core_rejects_unreviewed_commercial_redistribution() -> None:
    source = {
        "id": "unknown-rights",
        "adapter": "curated",
        "title": "Unknown rights",
        "publisher": "Publisher",
        "url": "https://example.org/record.json",
        "license_id": "CC-BY-4.0",
        "license_reviewed": True,
        "license_notes": "Dataset licence reviewed.",
        "commercial_redistribution": "unreviewed",
        "citation": "Citation",
    }
    with pytest.raises(ValidationError, match="reviewed commercial redistribution"):
        PipelineConfig.model_validate(
            {
                "distribution_profile": "open_core",
                "sources": [source],
                "license_policy": {
                    "mode": "commercial",
                    "allowed": ["CC-BY-4.0"],
                },
            }
        )
