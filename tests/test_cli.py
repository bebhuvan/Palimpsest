from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from history_pipeline.cli import app

runner = CliRunner()


def test_config_check_command_validates_release_profile() -> None:
    result = runner.invoke(app, ["config-check", "--config", "config/pipeline.yml"])
    assert result.exit_code == 0, result.output
    assert "Configuration valid" in result.output
    assert "open_core" in result.output


def test_config_check_command_validates_research_overlay() -> None:
    result = runner.invoke(
        app,
        ["config-check", "--config", "config/research-overlay.yml"],
    )
    assert result.exit_code == 0, result.output
    assert "research" in result.output


def test_schemas_command_writes_public_contracts(tmp_path: Path) -> None:
    output = tmp_path / "schemas"
    result = runner.invoke(app, ["schemas", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert (output / "LatestPointer.schema.json").is_file()
    assert (output / "HistoricalFeature.schema.json").is_file()
    assert (output / "HistoricalPeriodDefinition.schema.json").is_file()
    assert (output / "ChronologyIndex.schema.json").is_file()
    assert (output / "SourceRegistry.schema.json").is_file()
    assert (output / "AuthorityMatch.schema.json").is_file()
    assert (output / "HistoricalMapMetadata.schema.json").is_file()
    assert (output / "IntegrationIndex.schema.json").is_file()
    assert (output / "CommunityProposal.schema.json").is_file()
    assert (output / "AcceptedProposalRelease.schema.json").is_file()
    assert (output / "ApprovedEvidenceBundle.schema.json").is_file()
    assert (output / "DossierDraftContent.schema.json").is_file()
    assert (output / "DossierDraft.schema.json").is_file()
    assert (output / "PublishedEditorialDossier.schema.json").is_file()


def test_dossier_ingest_accepts_timezone_aware_iso_timestamp(tmp_path: Path) -> None:
    output = tmp_path / "draft.json"
    result = runner.invoke(
        app,
        [
            "dossier-ingest",
            "--bundle",
            "data/editorial/copernicus-1543/evidence-bundle.json",
            "--model-output",
            "data/editorial/copernicus-1543/model-output.json",
            "--prompt",
            "prompts/dossier-draft-v1.txt",
            "--prompt-version",
            "dossier-draft-v1",
            "--model",
            "fixture:deterministic-dossier-v1",
            "--generated-at",
            "2026-07-23T07:05:00Z",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.read_bytes() == (
        Path("data/editorial/copernicus-1543/draft.json").read_bytes()
    )
