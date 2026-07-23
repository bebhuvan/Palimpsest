from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from history_pipeline.cli import app

runner = CliRunner()


def test_config_check_command_validates_release_profile() -> None:
    result = runner.invoke(app, ["config-check", "--config", "config/pipeline.yml"])
    assert result.exit_code == 0, result.output
    assert "Configuration valid" in result.output


def test_schemas_command_writes_public_contracts(tmp_path: Path) -> None:
    output = tmp_path / "schemas"
    result = runner.invoke(app, ["schemas", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert (output / "LatestPointer.schema.json").is_file()
    assert (output / "HistoricalFeature.schema.json").is_file()
    assert (output / "HistoricalPeriodDefinition.schema.json").is_file()
    assert (output / "ChronologyIndex.schema.json").is_file()
    assert (output / "SourceRegistry.schema.json").is_file()
