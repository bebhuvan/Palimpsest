from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

import httpx
import typer
from pydantic import HttpUrl
from rich.console import Console
from rich.table import Table

from history_pipeline.assertion_restatement import (
    AssertionRestatementRejected,
    append_assertion_restatement,
    completed_assertion_checksums,
    generate_assertion_restatement,
    read_evidence_assertions,
)
from history_pipeline.causal import load_causal_dataset
from history_pipeline.chronicle import (
    _NAVIGATION,
    _resolved_wikidata_ids,
    _sitelink_counts,
    attach_prominence,
    build_chronicle,
    companion_pages,
    deduplicate_entries,
    fetch_page_wikitext,
    fetch_subject_extracts,
    fetch_year_wikitext,
    parse_year_wikitext,
    summarize,
)
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
    AcceptedProposalRelease,
    ApprovedEvidenceBundle,
    AssertionIndex,
    AssertionRestatement,
    AuthorityMatch,
    BuildManifest,
    CausalClaim,
    CausalDataset,
    CausalIndex,
    CausalPath,
    ChronologyIndex,
    CommunityProposal,
    ContentIndex,
    CoverageCell,
    DossierDraft,
    DossierDraftContent,
    DossierRestatement,
    DossierRestatementContent,
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
    SourceReference,
    SourceRegistry,
    SubjectExtract,
    ThematicAssertion,
    ThemeIndex,
    ThemeRuleSet,
    WikiContextIndex,
    WikiFeatureContext,
    YearConflict,
    YearImage,
)
from history_pipeline.pipeline import ADAPTERS, PipelineRun
from history_pipeline.publish import R2Publisher
from history_pipeline.restatement import (
    LEXICON_MINIMUM_DOCUMENTS,
    LEXICON_PATH,
    RestatementRejected,
    append_restatement,
    build_common_words,
    build_restatement,
    completed_source_checksums,
    dossiers_active_in_year,
    generate_restatement,
    load_model_output,
    pending_dossiers,
    provider_profile,
    read_dossiers,
    read_features,
    read_restatements,
    validate_restatement,
)
from history_pipeline.themes import load_theme_rules
from history_pipeline.verify import verify_latest_build
from history_pipeline.whg import (
    acquire_whg_dataset_snapshot,
    acquire_whg_snapshot,
    local_env_value,
    select_whg_subjects,
    write_whg_review_sheet,
    write_whg_snapshot,
)
from history_pipeline.year_dossier import (
    PEOPLE_GLOSSED,
    generate_year_dossier,
    plan_anchors,
    plan_sections,
    read_chronicle,
    read_year_context,
)
from history_pipeline.year_layers import (
    ANCHOR_COUNT,
    build_works,
    build_year_context,
    cluster_entries,
    extract_index,
    fetch_conflicts,
    fetch_images,
    most_written_about,
)

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


@app.command("acquire-whg")
def acquire_whg(
    features_path: Annotated[Path, typer.Option("--features")] = Path(
        "data/staged/canonical/features.ndjson"
    ),
    output_path: Annotated[Path, typer.Option("--output")] = Path(
        "data/editorial/whg/reconciliation-pilot.json"
    ),
    review_sheet_path: Annotated[Path | None, typer.Option("--review-sheet")] = None,
    api_token_env: Annotated[str, typer.Option("--api-token-env")] = "WHG_API_TOKEN",
    user_agent_env: Annotated[str, typer.Option("--user-agent-env")] = "WHG_USER_AGENT",
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 25,
    candidates: Annotated[int, typer.Option("--candidates", min=1, max=25)] = 5,
    radius_km: Annotated[float, typer.Option("--radius-km", min=0.1, max=500)] = 50,
    source_id: Annotated[str, typer.Option("--source-id")] = "pleiades",
    namespaces: Annotated[str, typer.Option("--namespaces")] = (
        "whg,gn,tgn,wd,osm,ohm"
    ),
) -> None:
    """Acquire a bounded, sanitized WHG reconciliation snapshot for review."""

    api_token = os.environ.get(api_token_env, "") or local_env_value(
        Path(".env"), api_token_env
    )
    if not api_token:
        raise typer.BadParameter(f"{api_token_env} is not configured")
    user_agent = os.environ.get(
        user_agent_env,
        "Palimpsest/0.1 (non-commercial historical research)",
    )
    allowed_namespaces = tuple(
        dict.fromkeys(value.strip() for value in namespaces.split(",") if value.strip())
    )
    subjects = select_whg_subjects(
        features_path,
        limit=limit,
        source_id=source_id,
    )
    console.print(
        f"[cyan]Reconciling {len(subjects)} {source_id} records with WHG[/cyan] · "
        f"{candidates} candidates each · {radius_km:g} km radius"
    )
    snapshot = acquire_whg_snapshot(
        subjects,
        api_token=api_token,
        user_agent=user_agent,
        namespaces=allowed_namespaces,
        candidate_limit=candidates,
        radius_km=radius_km,
    )
    write_whg_snapshot(output_path, snapshot)
    active_review_sheet = review_sheet_path or output_path.with_suffix(".review.csv")
    write_whg_review_sheet(active_review_sheet, snapshot)
    match_count = sum(len(query["result"]) for query in snapshot["queries"])
    provider_matches = sum(
        int(candidate["provider_match"])
        for query in snapshot["queries"]
        for candidate in query["result"]
    )
    console.print(
        f"[green]Wrote sanitized WHG pilot[/green] to {output_path} · "
        f"{match_count} proposed candidates · {provider_matches} provider match flags · "
        f"review sheet {active_review_sheet}"
    )


@app.command("acquire-whg-dataset")
def acquire_whg_dataset(
    dataset_id: Annotated[int, typer.Option("--dataset-id", min=1)],
    output_path: Annotated[Path, typer.Option("--output")] = Path(
        "data/editorial/whg/dataset-preview.json"
    ),
    api_token_env: Annotated[str, typer.Option("--api-token-env")] = "WHG_API_TOKEN",
    user_agent_env: Annotated[str, typer.Option("--user-agent-env")] = "WHG_USER_AGENT",
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 10,
) -> None:
    """Acquire a deterministic, non-production WHG specialist-dataset preview."""

    api_token = os.environ.get(api_token_env, "") or local_env_value(
        Path(".env"), api_token_env
    )
    if not api_token:
        raise typer.BadParameter(f"{api_token_env} is not configured")
    user_agent = os.environ.get(
        user_agent_env,
        "Palimpsest/0.1 (non-commercial historical research)",
    )
    snapshot = acquire_whg_dataset_snapshot(
        dataset_id,
        api_token=api_token,
        user_agent=user_agent,
        limit=limit,
    )
    write_whg_snapshot(output_path, snapshot)
    acquisition = snapshot["_palimpsest_acquisition"]
    console.print(
        f"[green]Wrote WHG dataset preview[/green] to {output_path} · "
        f"{acquisition['selected_feature_count']} of "
        f"{acquisition['provider_feature_count']} features · "
        f"provider checksum {acquisition['provider_checksum_sha256'][:12]}"
    )


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
        CommunityProposal,
        AcceptedProposalRelease,
        HistoricalName,
        HistoricalEntity,
        EvidenceAssertion,
        HistoricalDossier,
        ApprovedEvidenceBundle,
        DossierDraftContent,
        DossierDraft,
        PublishedEditorialDossier,
        DossierRestatementContent,
        DossierRestatement,
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
        AssertionRestatement,
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


@app.command("year-dossier")
def year_dossier_command(
    chronicle_path: Annotated[Path, typer.Option("--chronicle")],
    output_path: Annotated[Path, typer.Option("--output")],
    model_identifier: Annotated[str, typer.Option("--model")],
    lenses_path: Annotated[Path | None, typer.Option("--lenses")] = None,
    context_path: Annotated[Path | None, typer.Option("--context")] = None,
    provider: Annotated[str, typer.Option("--provider")] = "deepseek",
    prompt_version: Annotated[str, typer.Option("--prompt-version")] = "year-dossier-v2",
    api_key_env: Annotated[str, typer.Option("--api-key-env")] = "",
    attempts: Annotated[int, typer.Option("--attempts")] = 5,
) -> None:
    """Write one year's prose dossier from its chronicle. Generated, disclosed, unreviewed."""

    try:
        profile = provider_profile(provider)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    chronicle = read_chronicle(chronicle_path)
    lenses: dict[str, str] = {}
    if lenses_path and lenses_path.exists():
        lenses = json.loads(lenses_path.read_text(encoding="utf-8"))
    context = read_year_context(context_path) if context_path and context_path.exists() else None
    plan = plan_sections(chronicle.entries, lenses)
    anchors = plan_anchors(
        chronicle.entries, lenses, extract_index(chronicle.subject_extracts)
    )
    console.print(
        f"[cyan]{chronicle.year}: {len(chronicle.entries)} records "
        f"in {len(anchors)} anchors and {len(plan)} sections[/cyan]"
    )
    for anchor in anchors:
        console.print(
            f"   [dim]{anchor.cluster.sitelink_count:>4} editions[/dim]  {anchor.heading}"
        )
    for _section_id, heading, group in plan:
        console.print(f"   [dim]{len(group):>3} records[/dim]  {heading}")
    dossier = generate_year_dossier(
        chronicle,
        lenses,
        prompt_version=prompt_version,
        model_identifier=model_identifier,
        api_key=api_key_from_environment(api_key_env or profile.api_key_env),
        provider=provider,
        context=context,
        attempts=attempts,
        on_retry=lambda attempt, rejection: console.print(
            f"[yellow]attempt {attempt} rejected[/yellow] "
            + json.dumps(rejection.report, ensure_ascii=False)
        ),
    )
    write_json(output_path, dossier)
    console.print(
        f"[green]Wrote {dossier.dossier_id}[/green] to {output_path} · "
        f"{dossier.validation.restatement_chars} chars of prose from "
        f"{dossier.validation.source_chars} chars of records · "
        f"{len(dossier.register_entries)} register entries · "
        f"{len(dossier.related_years)} related years · "
        f"{sum(1 for anchor in dossier.anchors if anchor.image)} images"
    )


@app.command("build-year-context")
def build_year_context_command(
    year: Annotated[int, typer.Option("--year")],
    chronicle_path: Annotated[Path, typer.Option("--chronicle")],
    output_path: Annotated[Path, typer.Option("--output")],
    config_path: Annotated[Path, typer.Option("--config")] = DEFAULT_CONFIG,
    user_agent_env: Annotated[str, typer.Option("--user-agent-env")] = "WIKIMEDIA_USER_AGENT",
    images: Annotated[bool, typer.Option("--images/--no-images")] = True,
    conflicts: Annotated[bool, typer.Option("--conflicts/--no-conflicts")] = True,
) -> None:
    """Fetch what a year article does not know about itself: wars in progress, and pictures.

    Both come from outside the year article, so they are written to their own artifact. A dossier
    built without it is complete, not degraded.
    """

    user_agent = os.environ.get(user_agent_env)
    if not user_agent:
        raise typer.BadParameter(f"{user_agent_env} is required to contact Wikimedia")
    chronicle = read_chronicle(chronicle_path)
    found: list[YearConflict] = []
    pictures: list[YearImage] = []
    rejected: list[str] = []
    with httpx.Client(timeout=180, headers={"User-Agent": user_agent}) as client:
        if conflicts:
            found = fetch_conflicts(year, client=client)
            console.print(f"[cyan]{len(found)} wars recorded as running across {year}[/cyan]")
            for conflict in found:
                marker = " (ended this year)" if conflict.ended_this_year else ""
                console.print(
                    f"   [dim]{conflict.start_year}-{conflict.end_year}[/dim]  "
                    f"{conflict.title}{marker}"
                )
        if images:
            # Events for the anchors, and people for the births and deaths, which are rendered
            # as faces rather than narrated as a list.
            clusters = cluster_entries(chronicle.entries)
            subjects = {
                cluster.lead.subject_wikidata_id: cluster.lead.subject_title or ""
                for group, limit in (
                    (("event",), ANCHOR_COUNT * 3),
                    (("birth", "death"), PEOPLE_GLOSSED * 2),
                )
                for cluster in most_written_about(clusters, limit, kinds=group)
                if cluster.lead.subject_wikidata_id
            }
            pictures, rejected = fetch_images(
                subjects, client=client, policy=load_config(config_path).license_policy
            )
            console.print(
                f"[cyan]{len(pictures)} Commons files cleared, "
                f"{len(rejected)} refused[/cyan]"
            )
            for refusal in rejected:
                console.print(f"   [yellow]refused[/yellow] {refusal}")

    context = build_year_context(
        year, conflicts=found, images=pictures, rejected=rejected
    )
    write_json(output_path, context)
    console.print(f"[green]Wrote year context[/green] to {output_path}")


@app.command("build-chronicle")
def build_chronicle_command(
    year: Annotated[int, typer.Option("--year")],
    output_path: Annotated[Path, typer.Option("--output")],
    language: Annotated[str, typer.Option("--language")] = "en",
    source_id: Annotated[str, typer.Option("--source-id")] = "wikipedia",
    license_id: Annotated[str, typer.Option("--license-id")] = "CC-BY-SA-4.0",
    publisher: Annotated[str, typer.Option("--publisher")] = "Wikimedia Foundation",
    user_agent_env: Annotated[str, typer.Option("--user-agent-env")] = "WIKIMEDIA_USER_AGENT",
    prominence: Annotated[bool, typer.Option("--prominence/--no-prominence")] = True,
    context: Annotated[bool, typer.Option("--context/--no-context")] = True,
    companion_sources: Annotated[
        bool, typer.Option("--companions/--no-companions")
    ] = True,
) -> None:
    """Ingest one Wikipedia year article as dated event, birth and death records."""

    user_agent = os.environ.get(user_agent_env)
    if not user_agent:
        raise typer.BadParameter(f"{user_agent_env} is required to contact Wikimedia")
    retrieved_at = datetime.now(UTC)
    with httpx.Client(timeout=90, headers={"User-Agent": user_agent}) as client:
        parse = fetch_year_wikitext(year, client=client, language=language)
        entries = parse_year_wikitext(str(parse["wikitext"]), year, source_page=str(year))
        console.print(f"[cyan]{len(entries)} entries from the {year} article[/cyan]")
        companions: list[tuple[str, dict[str, Any]]] = []
        if companion_sources:
            for title in companion_pages(year):
                found = fetch_page_wikitext(title, client=client, language=language)
                if found is None:
                    continue
                extra = parse_year_wikitext(str(found["wikitext"]), year, source_page=title)
                if not extra:
                    continue
                companions.append((title, found))
                entries.extend(extra)
                console.print(f"   [dim]{len(extra):>3} more from[/dim] {title}")
            entries = deduplicate_entries(entries)
            console.print(
                f"[cyan]{len(entries)} entries after merging "
                f"{len(companions)} pages[/cyan]"
            )
        wikidata_ids: dict[str, str] = {}
        sitelinks: dict[str, int] = {}
        places: set[str] = set()
        if prominence and entries:
            # Every non-navigation link is resolved, not just the first, so the subject can be
            # chosen by what a link is rather than where it sits in the sentence.
            titles = sorted(
                {
                    title
                    for entry in entries
                    for title in entry.linked_titles
                    if not _NAVIGATION.match(title)
                }
            )
            wikidata_ids = _resolved_wikidata_ids(titles, client=client, language=language)
            sitelinks, places = _sitelink_counts(wikidata_ids.values(), client=client)
            console.print(
                f"[cyan]{len(wikidata_ids)} subjects resolved to Wikidata, "
                f"{len(sitelinks)} with a sitelink count[/cyan]"
            )
        entries = attach_prominence(entries, wikidata_ids, sitelinks, places)
        extracts: list[SubjectExtract] = []
        if context and entries:
            subjects = {e.subject_title for e in entries if e.subject_title}
            # The articles a prominent record links to are about that record: the book, the
            # treaty, the city taken. Without them an anchor written from one line and one
            # biography becomes a biography. They are fetched only for the records that will get
            # room, because fetching every link would double the request for pages nothing reads.
            clusters = cluster_entries(entries)
            wanted = list(most_written_about(clusters, ANCHOR_COUNT * 5))
            # And every book, painting and poem: a work is glossed from its own article, and its
            # article is only ever reachable through the link beside its maker's name.
            made = {work.entry_id for work in build_works(clusters, {})}
            wanted.extend(item for item in clusters if item.entry_id in made)
            for cluster in wanted:
                subjects.update(
                    title
                    for title in cluster.lead.linked_titles
                    if not _NAVIGATION.match(title)
                )
            extracts = fetch_subject_extracts(
                sorted(subjects), wikidata_ids, client=client, language=language
            )
            console.print(
                f"[cyan]{len(extracts)} subject articles fetched as context "
                f"({sum(len(x.extract) for x in extracts):,} chars)[/cyan]"
            )

    wikitext = str(parse["wikitext"])
    source_ref = SourceReference(
        source_id=source_id,
        record_id=str(parse["pageid"]),
        title=f"Wikipedia: {year}",
        publisher=publisher,
        url=HttpUrl(f"https://{language}.wikipedia.org/wiki/{year}"),
        license_id=license_id,
        retrieved_at=retrieved_at,
        version=str(parse["revid"]),
        checksum_sha256=hashlib.sha256(wikitext.encode("utf-8")).hexdigest(),
        citation=f"“{year}”, {language.upper()} Wikipedia, revision {parse['revid']}",
    )
    chronicle = build_chronicle(
        year,
        parse,
        language=language,
        source_ref=source_ref,
        revision_timestamp=retrieved_at,
        entries=entries,
        subject_extracts=extracts,
    )
    write_json(output_path, chronicle)
    counts = summarize(chronicle)
    console.print(
        f"[green]Wrote {counts['total']} chronicle entries[/green] to {output_path} · "
        f"{counts['event']} events · {counts['birth']} births · {counts['death']} deaths · "
        f"{counts['with_day']} dated to the day"
    )
    ranked = sorted(
        (entry for entry in chronicle.entries if entry.sitelink_count),
        key=lambda entry: -(entry.sitelink_count or 0),
    )[:5]
    for entry in ranked:
        console.print(
            f"  [dim]{entry.sitelink_count:>4} language editions[/dim]  {entry.subject_title}"
        )


@app.command("build-lexicon")
def build_lexicon(
    dossiers_path: Annotated[Path, typer.Option("--dossiers")],
    output_path: Annotated[Path, typer.Option("--output")] = LEXICON_PATH,
    minimum_documents: Annotated[int, typer.Option("--minimum-documents")] = (
        LEXICON_MINIMUM_DOCUMENTS
    ),
) -> None:
    """Regenerate the common-word lexicon the restatement name check uses."""

    extracts = [dossier.extract for dossier in read_dossiers(dossiers_path)]
    words = build_common_words(extracts, minimum_documents=minimum_documents)
    header = (
        "# Words the dossier corpus writes in lower case in at least "
        f"{minimum_documents} documents.\n"
        "# A capital on one of these at the start of a sentence is grammar, not a name.\n"
        f"# Regenerate with: history-data build-lexicon --dossiers {dossiers_path}\n"
        f"# Derived from {len(extracts)} source extracts. Do not edit by hand.\n"
    )
    output_path.write_text(header + "\n".join(words) + "\n", encoding="utf-8")
    console.print(f"[green]Wrote {len(words)} common words[/green] to {output_path}")


@app.command("restate-dossiers")
def restate_dossiers(
    dossiers_path: Annotated[Path, typer.Option("--dossiers")],
    output_path: Annotated[Path, typer.Option("--output")],
    model_identifier: Annotated[str, typer.Option("--model")],
    prompt_path: Annotated[Path, typer.Option("--prompt")] = Path(
        "prompts/dossier-restate-v1.txt"
    ),
    prompt_version: Annotated[str, typer.Option("--prompt-version")] = "dossier-restate-v1",
    provider: Annotated[str, typer.Option("--provider")] = "openai",
    api_key_env: Annotated[str, typer.Option("--api-key-env")] = "",
    limit: Annotated[int, typer.Option("--limit")] = 0,
    minimum_chars: Annotated[int, typer.Option("--minimum-chars")] = 200,
    year: Annotated[int, typer.Option("--year")] = 0,
    features_path: Annotated[Path, typer.Option("--features")] = Path(
        "data/staged/canonical/features.ndjson"
    ),
    concurrency: Annotated[int, typer.Option("--concurrency")] = 8,
) -> None:
    """Restate source extracts in plain English, resuming from any completed work."""

    try:
        profile = provider_profile(provider)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    prompt = prompt_path.read_text(encoding="utf-8")
    api_key = api_key_from_environment(api_key_env or profile.api_key_env)
    if not profile.enforces_schema:
        console.print(
            f"[yellow]{profile.name} cannot enforce a response schema[/yellow]; the contract is "
            "sent in the prompt and every reply is validated locally before it is trusted."
        )
    completed = completed_source_checksums(output_path)
    candidates = list(read_dossiers(dossiers_path))
    if year:
        if not features_path.exists():
            raise typer.BadParameter(f"--year needs reviewed features; {features_path} is absent")
        candidates = dossiers_active_in_year(candidates, read_features(features_path), year)
        console.print(
            f"[cyan]{len(candidates)} dossiers joined to features active in {year}[/cyan]"
        )
    pending = pending_dossiers(candidates, completed, minimum_chars=minimum_chars)
    if limit > 0:
        pending = pending[:limit]
    console.print(
        f"[cyan]{len(completed)} restated already[/cyan] · "
        f"[cyan]{len(pending)} to process[/cyan] · "
        f"[cyan]{concurrency} at a time[/cyan]"
    )

    written = 0
    rejected = 0
    failed = 0
    # One lock guards the append so a worker never interleaves a partial NDJSON line. The file
    # stays the resume log, so an interrupted run still costs only the records in flight.
    write_lock = Lock()

    def restate_one(dossier: HistoricalDossier) -> tuple[str, str]:
        try:
            restatement = generate_restatement(
                dossier,
                prompt=prompt,
                prompt_version=prompt_version,
                model_identifier=model_identifier,
                api_key=api_key,
                provider=provider,
            )
        except RestatementRejected as rejection:
            return "rejected", str(rejection)
        except (ValueError, httpx.HTTPError) as error:
            return "failed", f"{dossier.dossier_id}: {error}"
        with write_lock:
            append_restatement(output_path, restatement)
        return "written", restatement.restatement_id

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for outcome, detail in pool.map(restate_one, pending):
            if outcome == "written":
                written += 1
            elif outcome == "rejected":
                rejected += 1
                console.print(f"[yellow]rejected[/yellow] {detail}")
            else:
                failed += 1
                console.print(f"[red]failed[/red] {detail}")
    console.print(
        f"[green]Wrote {written} restatements[/green] to {output_path} · "
        f"{rejected} rejected by the closed-world check · {failed} provider failures"
    )


@app.command("restate-assertions")
def restate_assertions(
    assertions_path: Annotated[Path, typer.Option("--assertions")] = Path(
        "data/staged/canonical/evidence-assertions.ndjson"
    ),
    output_path: Annotated[Path, typer.Option("--output")] = Path(
        "data/editorial/seshat-restatements.ndjson"
    ),
    model_identifier: Annotated[str, typer.Option("--model")] = "deepseek-v4-flash",
    prompt_path: Annotated[Path, typer.Option("--prompt")] = Path(
        "prompts/seshat-restate-v1.txt"
    ),
    prompt_version: Annotated[str, typer.Option("--prompt-version")] = "seshat-restate-v1",
    provider: Annotated[str, typer.Option("--provider")] = "deepseek",
    api_key_env: Annotated[str, typer.Option("--api-key-env")] = "",
    limit: Annotated[int, typer.Option("--limit")] = 0,
    concurrency: Annotated[int, typer.Option("--concurrency")] = 8,
) -> None:
    """Restate Seshat evidence notes in plain English without changing their data."""

    try:
        profile = provider_profile(provider)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    prompt = prompt_path.read_text(encoding="utf-8")
    api_key = api_key_from_environment(api_key_env or profile.api_key_env)
    completed = completed_assertion_checksums(output_path)
    candidates = [
        assertion
        for assertion in read_evidence_assertions(assertions_path)
        if assertion.source_excerpt
        and any(source.source_id == "seshat_api" for source in assertion.source_refs)
        and (
            assertion.assertion_id,
            assertion.source_excerpt_checksum_sha256 or "",
        )
        not in completed
    ]
    if limit > 0:
        candidates = candidates[:limit]
    console.print(
        f"[cyan]{len(completed)} restated already[/cyan] · "
        f"[cyan]{len(candidates)} Seshat explanations to process[/cyan] · "
        f"[cyan]{concurrency} at a time[/cyan]"
    )
    write_lock = Lock()

    def restate_one(assertion: EvidenceAssertion) -> tuple[str, str]:
        try:
            restatement = generate_assertion_restatement(
                assertion,
                prompt=prompt,
                prompt_version=prompt_version,
                model_identifier=model_identifier,
                api_key=api_key,
                provider=provider,
            )
        except AssertionRestatementRejected as error:
            return "rejected", str(error)
        except (ValueError, httpx.HTTPError) as error:
            return "failed", f"{assertion.assertion_id}: {error}"
        with write_lock:
            append_assertion_restatement(output_path, restatement)
        return "written", assertion.assertion_id

    written = rejected = failed = 0
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        for outcome, detail in pool.map(restate_one, candidates):
            if outcome == "written":
                written += 1
            elif outcome == "rejected":
                rejected += 1
                console.print(f"[yellow]rejected[/yellow] {detail}")
            else:
                failed += 1
                console.print(f"[red]failed[/red] {detail}")
    console.print(
        f"[green]Wrote {written} Seshat restatements[/green] to {output_path} · "
        f"{rejected} rejected by the source-bound check · {failed} provider failures"
    )


@app.command("restate-ingest")
def restate_ingest(
    dossiers_path: Annotated[Path, typer.Option("--dossiers")],
    dossier_id: Annotated[str, typer.Option("--dossier-id")],
    model_output_path: Annotated[Path, typer.Option("--model-output")],
    output_path: Annotated[Path, typer.Option("--output")],
    model_identifier: Annotated[str, typer.Option("--model")],
    generated_at: Annotated[str, typer.Option("--generated-at")],
    prompt_path: Annotated[Path, typer.Option("--prompt")] = Path(
        "prompts/dossier-restate-v1.txt"
    ),
    prompt_version: Annotated[str, typer.Option("--prompt-version")] = "dossier-restate-v1",
) -> None:
    """Validate saved model output against its source without contacting a provider."""

    dossier = next(
        (item for item in read_dossiers(dossiers_path) if item.dossier_id == dossier_id), None
    )
    if dossier is None:
        raise typer.BadParameter(f"{dossier_id} is not in {dossiers_path}")
    prompt = prompt_path.read_text(encoding="utf-8")
    restatement = build_restatement(
        load_model_output(model_output_path),
        dossier,
        prompt_version=prompt_version,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        model_identifier=model_identifier,
        generated_at=_parse_timestamp(generated_at, "--generated-at"),
    )
    append_restatement(output_path, restatement)
    console.print(f"[green]Validated restatement[/green] {restatement.restatement_id}")


@app.command("restate-verify")
def restate_verify(
    dossiers_path: Annotated[Path, typer.Option("--dossiers")],
    restatements_path: Annotated[Path, typer.Option("--restatements")],
) -> None:
    """Re-run every closed-world check against the current sources."""

    sources = {dossier.dossier_id: dossier for dossier in read_dossiers(dossiers_path)}
    checked = 0
    problems: list[str] = []
    for restatement in read_restatements(restatements_path):
        dossier = sources.get(restatement.dossier_id)
        if dossier is None:
            problems.append(f"{restatement.dossier_id}: source dossier is not in this release")
            continue
        try:
            validate_restatement(restatement, dossier)
        except ValueError as error:
            problems.append(str(error))
            continue
        checked += 1
    for problem in problems:
        console.print(f"[red]{problem}[/red]")
    console.print(f"[green]{checked} restatements verified[/green] · {len(problems)} problems")
    if problems:
        raise typer.Exit(code=1)


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
