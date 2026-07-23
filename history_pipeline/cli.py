from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from history_pipeline.causal import load_causal_dataset
from history_pipeline.config import load_config
from history_pipeline.curated import CuratedRecords, load_curated_records
from history_pipeline.dossiers import (
    api_key_from_environment,
    generate_with_openai,
    ingest_model_output,
    publish_reviewed_draft,
    read_json_model,
    reject_draft,
    review_draft,
    write_json,
)
from history_pipeline.licenses import enforce_source_license
from history_pipeline.models import (
    ApprovedEvidenceBundle,
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
    DossierDraft,
    DossierDraftContent,
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
    PublishedEditorialDossier,
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
        ApprovedEvidenceBundle,
        DossierDraftContent,
        DossierDraft,
        PublishedEditorialDossier,
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


def _load_dossier_inputs(
    bundle_path: Path,
    curated_path: Path,
) -> tuple[ApprovedEvidenceBundle, CuratedRecords]:
    bundle = read_json_model(bundle_path, ApprovedEvidenceBundle)
    curated, _checksum = load_curated_records(curated_path)
    return bundle, curated


def _parse_timestamp(value: str, option: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise typer.BadParameter(f"{option} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise typer.BadParameter(f"{option} must include a UTC offset")
    return parsed


@app.command("dossier-ingest")
def dossier_ingest(
    bundle_path: Annotated[Path, typer.Option("--bundle")],
    model_output_path: Annotated[Path, typer.Option("--model-output")],
    output_path: Annotated[Path, typer.Option("--output")],
    prompt_path: Annotated[Path, typer.Option("--prompt")],
    prompt_version: Annotated[str, typer.Option("--prompt-version")],
    model_identifier: Annotated[str, typer.Option("--model")],
    generated_at: Annotated[str, typer.Option("--generated-at")],
    curated_path: Annotated[Path, typer.Option("--curated")] = Path(
        "data/curation/knowledge-1543.yml"
    ),
) -> None:
    bundle, curated = _load_dossier_inputs(bundle_path, curated_path)
    prompt = prompt_path.read_text(encoding="utf-8")
    content = read_json_model(model_output_path, DossierDraftContent)
    draft = ingest_model_output(
        content,
        bundle,
        curated,
        prompt_version=prompt_version,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        model_identifier=model_identifier,
        generated_at=_parse_timestamp(generated_at, "--generated-at"),
    )
    write_json(output_path, draft)
    console.print(f"[green]Validated dossier draft[/green] {draft.draft_id}")


@app.command("dossier-generate")
def dossier_generate(
    bundle_path: Annotated[Path, typer.Option("--bundle")],
    output_path: Annotated[Path, typer.Option("--output")],
    prompt_path: Annotated[Path, typer.Option("--prompt")],
    prompt_version: Annotated[str, typer.Option("--prompt-version")],
    model_identifier: Annotated[str, typer.Option("--model")],
    api_key_env: Annotated[str, typer.Option("--api-key-env")] = "OPENAI_API_KEY",
    curated_path: Annotated[Path, typer.Option("--curated")] = Path(
        "data/curation/knowledge-1543.yml"
    ),
) -> None:
    bundle, curated = _load_dossier_inputs(bundle_path, curated_path)
    draft = generate_with_openai(
        bundle,
        curated,
        prompt=prompt_path.read_text(encoding="utf-8"),
        prompt_version=prompt_version,
        model_identifier=model_identifier,
        api_key=api_key_from_environment(api_key_env),
    )
    write_json(output_path, draft)
    console.print(f"[green]Generated and validated dossier draft[/green] {draft.draft_id}")


@app.command("dossier-review")
def dossier_review(
    bundle_path: Annotated[Path, typer.Option("--bundle")],
    draft_path: Annotated[Path, typer.Option("--draft")],
    output_path: Annotated[Path, typer.Option("--output")],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    reviewed_at: Annotated[str, typer.Option("--reviewed-at")],
    notes: Annotated[str, typer.Option("--notes")],
    curated_path: Annotated[Path, typer.Option("--curated")] = Path(
        "data/curation/knowledge-1543.yml"
    ),
) -> None:
    bundle, curated = _load_dossier_inputs(bundle_path, curated_path)
    draft = read_json_model(draft_path, DossierDraft)
    reviewed = review_draft(
        draft,
        bundle,
        curated,
        reviewed_by=reviewed_by,
        reviewed_at=_parse_timestamp(reviewed_at, "--reviewed-at"),
        notes=notes,
    )
    write_json(output_path, reviewed)
    console.print(f"[green]Recorded human dossier review[/green] {reviewed.draft_id}")


@app.command("dossier-publish")
def dossier_publish(
    bundle_path: Annotated[Path, typer.Option("--bundle")],
    draft_path: Annotated[Path, typer.Option("--reviewed-draft")],
    output_dir: Annotated[Path, typer.Option("--output-dir")],
    editorial_license_id: Annotated[str, typer.Option("--editorial-license-id")],
    editorial_attribution: Annotated[str, typer.Option("--editorial-attribution")],
    published_at: Annotated[str, typer.Option("--published-at")],
    curated_path: Annotated[Path, typer.Option("--curated")] = Path(
        "data/curation/knowledge-1543.yml"
    ),
) -> None:
    bundle, curated = _load_dossier_inputs(bundle_path, curated_path)
    draft = read_json_model(draft_path, DossierDraft)
    dossier = publish_reviewed_draft(
        draft,
        bundle,
        curated,
        editorial_license_id=editorial_license_id,
        editorial_attribution=editorial_attribution,
        published_at=_parse_timestamp(published_at, "--published-at"),
    )
    output_path = output_dir / f"{dossier.dossier_id.rsplit(':', 1)[-1]}.json"
    write_json(output_path, dossier, immutable=True)
    console.print(f"[green]Published immutable editorial dossier[/green] {output_path}")


@app.command("dossier-reject")
def dossier_reject(
    bundle_path: Annotated[Path, typer.Option("--bundle")],
    draft_path: Annotated[Path, typer.Option("--draft")],
    output_path: Annotated[Path, typer.Option("--output")],
    rejected_by: Annotated[str, typer.Option("--rejected-by")],
    rejected_at: Annotated[str, typer.Option("--rejected-at")],
    reason: Annotated[str, typer.Option("--reason")],
    curated_path: Annotated[Path, typer.Option("--curated")] = Path(
        "data/curation/knowledge-1543.yml"
    ),
) -> None:
    bundle, curated = _load_dossier_inputs(bundle_path, curated_path)
    draft = read_json_model(draft_path, DossierDraft)
    rejected = reject_draft(
        draft,
        bundle,
        curated,
        rejected_by=rejected_by,
        rejected_at=_parse_timestamp(rejected_at, "--rejected-at"),
        reason=reason,
    )
    write_json(output_path, rejected)
    console.print(f"[yellow]Rejected dossier draft[/yellow] {rejected.draft_id}")


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
