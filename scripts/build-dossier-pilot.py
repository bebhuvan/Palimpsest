from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import orjson

from history_pipeline.curated import load_curated_records
from history_pipeline.dossiers import (
    ingest_model_output,
    publish_reviewed_draft,
    read_json_model,
    review_draft,
    write_json,
)
from history_pipeline.models import (
    ApprovedEvidenceBundle,
    DossierDraftContent,
    EvidenceDocument,
    EvidencePassage,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT_ROOT = ROOT / "data" / "editorial" / "copernicus-1543"
CURATED_PATH = ROOT / "data" / "curation" / "knowledge-1543.yml"
PROMPT_PATH = ROOT / "prompts" / "dossier-draft-v1.txt"
GENERATED_AT = datetime(2026, 7, 23, 7, 5, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 7, 23, 7, 30, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)

PASSAGE_IDS = (
    "passage:copernicus-authorship",
    "passage:publication-work",
    "passage:publication-printer",
    "passage:publication-place",
    "passage:heliocentric-subject",
)


def build_pilot(output_root: Path) -> None:
    curated, _checksum = load_curated_records(CURATED_PATH)
    evidence_text = (PILOT_ROOT / "evidence.txt").read_text(encoding="utf-8")
    lines = evidence_text.splitlines(keepends=True)
    if len(lines) != len(curated.assertions) or len(lines) != len(PASSAGE_IDS):
        raise ValueError("Copernicus evidence lines must map one-to-one to assertions")

    passages: list[EvidencePassage] = []
    offset = 0
    for assertion, passage_id, line in zip(
        curated.assertions, PASSAGE_IDS, lines, strict=True
    ):
        passage_text = line.removesuffix("\n")
        if passage_text != assertion.confidence.rationale:
            raise ValueError(
                f"Evidence passage differs from curated rationale: {assertion.assertion_id}"
            )
        passages.append(
            EvidencePassage(
                passage_id=passage_id,
                assertion_ids=[assertion.assertion_id],
                start_char=offset,
                end_char=offset + len(passage_text),
                text=passage_text,
                text_sha256=hashlib.sha256(passage_text.encode("utf-8")).hexdigest(),
            )
        )
        offset += len(line)

    source_ref = curated.assertions[0].source_refs[0]
    if any(assertion.source_refs != [source_ref] for assertion in curated.assertions):
        raise ValueError("Copernicus pilot assertions must retain one identical source revision")
    if source_ref.version is None:
        raise ValueError("Copernicus evidence source must have a revision identifier")
    bundle = ApprovedEvidenceBundle(
        bundle_id="evidence-bundle:copernicus-1543-v1",
        subject_entity_ids=sorted(
            {entity_id for item in curated.assertions for entity_id in item.subject_entity_ids}
        ),
        feature_ids=sorted(
            {feature_id for item in curated.assertions for feature_id in item.feature_ids}
        ),
        assertions=curated.assertions,
        sources=[
            EvidenceDocument(
                source_ref=source_ref,
                source_revision_id=source_ref.version,
                attribution=source_ref.citation,
                text=evidence_text,
                text_sha256=hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
                passages=passages,
            )
        ],
        approved_by="History Joice editorial pilot",
        approved_at=datetime(2026, 7, 23, 7, 0, tzinfo=UTC),
    )
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    content = read_json_model(PILOT_ROOT / "model-output.json", DossierDraftContent)
    draft = ingest_model_output(
        content,
        bundle,
        curated,
        prompt_version="dossier-draft-v1",
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        model_identifier="fixture:deterministic-dossier-v1",
        generated_at=GENERATED_AT,
    )
    reviewed = review_draft(
        draft,
        bundle,
        curated,
        reviewed_by="History Joice editorial pilot",
        reviewed_at=REVIEWED_AT,
        notes=(
            "Verified each sentence against the cited Library of Congress metadata "
            "passage; no broader significance or causation was added."
        ),
    )
    published = publish_reviewed_draft(
        reviewed,
        bundle,
        curated,
        editorial_license_id="CC-BY-4.0",
        editorial_attribution="History Joice editorial team",
        published_at=PUBLISHED_AT,
    )

    write_json(output_root / "evidence-bundle.json", bundle)
    write_json(output_root / "draft.json", draft)
    write_json(output_root / "reviewed-draft.json", reviewed)
    published_path = (
        output_root / "published" / f"{published.dossier_id.rsplit(':', 1)[-1]}.json"
    )
    if published_path.exists():
        expected = published_path.read_bytes()
        actual = (
            orjson.dumps(
                published.model_dump(mode="json"),
                option=orjson.OPT_SORT_KEYS,
            )
            + b"\n"
        )
        if expected != actual:
            raise FileExistsError(f"Immutable pilot dossier differs: {published_path}")
    else:
        write_json(published_path, published, immutable=True)
    print(f"Built deterministic dossier pilot {draft.draft_id} -> {published.dossier_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PILOT_ROOT)
    args = parser.parse_args()
    build_pilot(args.output)


if __name__ == "__main__":
    main()
