from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from history_pipeline.causal import load_causal_dataset
from history_pipeline.config import load_config
from history_pipeline.curated import load_curated_records
from history_pipeline.licenses import enforce_source_license
from history_pipeline.models import (
    AssertionIndex,
    AuthorityMatch,
    BuildManifest,
    CausalClaim,
    CausalDataset,
    CausalIndex,
    CausalPath,
    ChronologyIndex,
    ContentIndex,
    CoverageCell,
    EvidenceAssertion,
    FeatureContentLink,
    HistoricalDossier,
    HistoricalEntity,
    HistoricalFeature,
    HistoricalMapMetadata,
    HistoricalName,
    HistoricalPeriodDefinition,
    IndicatorObservation,
    IntegrationIndex,
    LatestPointer,
    LayerCatalog,
    RegionTimeBucket,
    RegionTimeIndex,
    SourceRegistry,
    ThematicAssertion,
    ThemeIndex,
    ThemeRuleSet,
    WikiContextIndex,
    WikiFeatureContext,
)
from history_pipeline.pipeline import ADAPTERS, PipelineRun
from history_pipeline.publish import R2Publisher
from history_pipeline.themes import load_theme_rules
from history_pipeline.verify import verify_latest_build

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
console = Console()
DEFAULT_CONFIG = Path("config/pipeline.yml")


@app.command("config-check")
def config_check(
    config_path: Annotated[Path, typer.Option("--config")] = DEFAULT_CONFIG,
) -> None:
    config = load_config(config_path)
    for source in config.sources:
        if source.enabled:
            enforce_source_license(
                source.license_id,
                source.license_reviewed,
                config.license_policy,
                source.id,
            )
        if source.adapter not in {*ADAPTERS, "wikidata", "wikipedia", "curated"}:
            raise typer.BadParameter(f"Unknown adapter: {source.adapter}")
    causal, _checksum = load_causal_dataset(config.causal_claims_path)
    theme_rules, _theme_checksum = load_theme_rules(config.theme_rules_path)
    curated, _curated_checksum = load_curated_records(config.curated_records_path)
    for claim in causal.claims:
        for causal_source in claim.source_refs:
            enforce_source_license(
                causal_source.license_id,
                causal_source.license_reviewed,
                config.license_policy,
                causal_source.source_id,
            )
    console.print(
        f"[green]Configuration valid[/green]: {config.distribution_profile}, "
        f"{len(config.sources)} sources, "
        f"{config.minimum_year} to {config.maximum_year}, "
        f"{len(causal.claims)} causal claims, {len(theme_rules.rules)} theme rules, "
        f"{len(curated.assertions)} evidence assertions"
    )


@app.command("sources")
def sources(
    config_path: Annotated[Path, typer.Option("--config")] = DEFAULT_CONFIG,
) -> None:
    config = load_config(config_path)
    table = Table("ID", "Adapter", "Enabled", "Licence", "Title")
    for source in config.sources:
        table.add_row(
            source.id,
            source.adapter,
            "yes" if source.enabled else "no",
            source.license_id,
            source.title,
        )
    console.print(table)


@app.command("schemas")
def schemas(
    output: Annotated[Path, typer.Option("--output")] = Path("schemas"),
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    models = (
        HistoricalFeature,
        AuthorityMatch,
        HistoricalMapMetadata,
        IntegrationIndex,
        HistoricalName,
        HistoricalEntity,
        EvidenceAssertion,
        HistoricalDossier,
        IndicatorObservation,
        CoverageCell,
        BuildManifest,
        LatestPointer,
        FeatureContentLink,
        ContentIndex,
        CausalClaim,
        CausalPath,
        CausalDataset,
        CausalIndex,
        HistoricalPeriodDefinition,
        ChronologyIndex,
        SourceRegistry,
        WikiFeatureContext,
        WikiContextIndex,
        RegionTimeBucket,
        RegionTimeIndex,
        ThematicAssertion,
        ThemeRuleSet,
        ThemeIndex,
        AssertionIndex,
        LayerCatalog,
    )
    for model in models:
        path = output / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
    console.print(f"[green]Wrote {len(models)} schemas[/green] to {output}")


@app.command("build")
def build(
    config_path: Annotated[Path, typer.Option("--config")] = DEFAULT_CONFIG,
    limit: Annotated[
        int | None, typer.Option(help="Limit each primary source for smoke tests")
    ] = None,
    offline: Annotated[bool, typer.Option(help="Use only cached raw source files")] = False,
    enrich: Annotated[
        bool, typer.Option(help="Fetch Wikidata and Wikipedia enrichment")
    ] = False,
    tiles: Annotated[bool, typer.Option(help="Generate release PMTiles archives")] = False,
    tippecanoe: Annotated[
        str | None, typer.Option(help="Path or command name for tippecanoe")
    ] = None,
    advance_latest: Annotated[
        bool,
        typer.Option(help="Advance dist/data/latest.json after a successful build"),
    ] = True,
) -> None:
    config = load_config(config_path)
    manifest = PipelineRun(
        config,
        config_path,
        offline=offline,
        progress=lambda message: console.print(f"[cyan]Enrichment[/cyan] {message}"),
    ).build(
        limit=limit,
        enrich=enrich,
        tiles=tiles,
        tippecanoe=tippecanoe,
        advance_latest=advance_latest,
    )
    console.print(
        f"[green]Build {manifest.build_id} complete[/green]: "
        f"{len(manifest.artifacts)} artifacts, "
        f"{manifest.rejected_record_count} rejected records"
    )


@app.command("publish-r2")
def publish_r2(
    bucket: Annotated[str, typer.Option(envvar="R2_BUCKET")],
    snapshot_bucket: Annotated[
        str | None, typer.Option(envvar="R2_SNAPSHOT_BUCKET")
    ] = None,
    root: Annotated[Path, typer.Option("--root")] = Path("dist/data"),
    raw_root: Annotated[Path, typer.Option("--raw-root")] = Path("data/raw"),
    prefix: Annotated[str, typer.Option("--prefix")] = "v1",
    wrangler: Annotated[str, typer.Option("--wrangler")] = "wrangler",
    dry_run: Annotated[bool, typer.Option(help="Print the publication plan only")] = False,
) -> None:
    commands = R2Publisher(
        bucket=bucket,
        snapshot_bucket=snapshot_bucket,
        root=root,
        raw_root=raw_root,
        prefix=prefix,
        wrangler=wrangler,
        dry_run=dry_run,
    ).publish_latest()
    if dry_run:
        for command in commands:
            console.print(" ".join(command))
    console.print(f"[green]Publication plan complete[/green]: {len(commands)} uploads")


@app.command("verify-build")
def verify_build(
    root: Annotated[Path, typer.Option("--root")] = Path("dist/data"),
    raw_root: Annotated[Path, typer.Option("--raw-root")] = Path("data/raw"),
    require_tiles: Annotated[
        bool, typer.Option("--require-tiles", help="Require at least one PMTiles artifact")
    ] = False,
) -> None:
    manifest = verify_latest_build(root, raw_root, require_tiles=require_tiles)
    console.print(
        f"[green]Verified build {manifest.build_id}[/green]: "
        f"{len(manifest.artifacts)} artifacts, {len(manifest.raw_snapshots)} snapshots"
    )


if __name__ == "__main__":
    app()
