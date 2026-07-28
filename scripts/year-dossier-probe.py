"""Make one year-dossier request and keep everything, whether or not it passes.

A rejection is the most informative thing this pipeline produces and the default path throws it
away: `generate_year_dossier` retries, and a run that fails three times leaves nothing on disk to
read. This writes the prompt, the payload, the raw model output and the validation report to a
directory, so a systematic rejection can be told from a stochastic one by looking at it.

    uv run python scripts/year-dossier-probe.py --year 1543 --out /tmp/probe
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

from history_pipeline.models import YearDossierContent
from history_pipeline.restatement import provider_profile
from history_pipeline.year_dossier import (
    LENS_HEADINGS,
    _normalise_block_ids,
    _output,
    _payload,
    _request,
    build_prompt,
    entry_labels,
    overview_digest,
    plan_anchors,
    plan_sections,
    read_chronicle,
    read_year_context,
    resolve_labels,
    validate_dossier_content,
)
from history_pipeline.year_layers import (
    assemble_lede,
    build_incumbents,
    build_themes,
    cluster_entries,
    extract_index,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--chronicle-dir", type=Path, default=Path("data/chronicle"))
    arguments = parser.parse_args()

    out = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    chronicle = read_chronicle(arguments.chronicle_dir / f"{arguments.year}.json")
    lenses_path = arguments.chronicle_dir / f"{arguments.year}-lenses.json"
    lenses = json.loads(lenses_path.read_text()) if lenses_path.exists() else {}
    context_path = arguments.chronicle_dir / f"{arguments.year}-context.json"
    context = read_year_context(context_path) if context_path.exists() else None

    plan = plan_sections(chronicle.entries, lenses)
    by_title = extract_index(chronicle.subject_extracts)
    anchors = plan_anchors(chronicle.entries, lenses, by_title)
    clusters = cluster_entries(chronicle.entries)
    lede, _ = assemble_lede(chronicle, clusters)
    themes = build_themes(clusters, lenses, LENS_HEADINGS)
    incumbents = build_incumbents(chronicle.entries)
    digest = overview_digest(
        chronicle, clusters, lenses, lede, themes, incumbents, context, anchors
    )
    prompt = build_prompt(chronicle, plan, anchors)
    labels = entry_labels(plan, anchors)
    payload = _payload(plan, anchors, labels, by_title, digest)

    (out / "prompt.txt").write_text(prompt)
    (out / "payload.txt").write_text(payload)
    (out / "digest.txt").write_text(digest)

    profile = provider_profile(arguments.provider)
    key = os.environ[profile.api_key_env]
    with httpx.Client(timeout=600) as client:
        response = client.post(
            profile.url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=_request(profile, arguments.model, prompt, payload),
        )
        response.raise_for_status()
        body = response.json()
    (out / "response.json").write_text(json.dumps(body, indent=2, ensure_ascii=False))

    raw = _output(profile, body)
    (out / "raw.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    content = YearDossierContent.model_validate(
        resolve_labels(_normalise_block_ids(raw, plan, anchors), labels)
    )
    report = validate_dossier_content(
        content,
        chronicle,
        plan,
        anchors,
        context=context,
        overview_evidence=digest,
        prompt=prompt,
    )
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False) or "clean")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
