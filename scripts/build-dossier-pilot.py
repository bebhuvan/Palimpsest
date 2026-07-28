from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import orjson

from history_pipeline.curated import load_curated_records
from history_pipeline.dossiers import (
    ingest_model_output,
    read_json_model,
    validate_evidence_document_snapshot,
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
SNAPSHOT_PATH = ROOT / "data" / "raw" / "loc_copernicus" / "catalog-record.json"
GENERATED_AT = datetime(2026, 7, 23, 7, 5, tzinfo=UTC)
SOURCE_ID = "loc_copernicus"


def build_pilot(output_root: Path, snapshot_path: Path = SNAPSHOT_PATH) -> None:
    curated, _checksum = load_curated_records(CURATED_PATH)
    assertions = [
        assertion
        for assertion in curated.assertions
        if {source.source_id for source in assertion.source_refs} == {SOURCE_ID}
    ]
    if not assertions:
        raise ValueError("The Copernicus pilot has no curated assertions")
    source_ref = assertions[0].source_refs[0]
    if any(assertion.source_refs != [source_ref] for assertion in assertions):
        raise ValueError("Copernicus pilot assertions must retain one identical source revision")
    if source_ref.version is None:
        raise ValueError("Copernicus evidence source must have a revision identifier")
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot_checksum = hashlib.sha256(snapshot_bytes).hexdigest()
    if snapshot_checksum != source_ref.checksum_sha256:
        raise ValueError(
            f"LOC snapshot checksum differs from the curated source: {snapshot_path}"
        )
    snapshot = orjson.loads(snapshot_bytes)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("item"), dict):
        raise ValueError("LOC snapshot must contain an item object")
    item = snapshot["item"]
    assertions_by_id = {assertion.assertion_id: assertion for assertion in assertions}
    field_specs = (
        (
            "passage:loc-item-title",
            "/item/title",
            item.get("title"),
            ["assertion:de-revolutionibus-subject-heliocentric-astronomy"],
        ),
        (
            "passage:loc-item-creator-0",
            "/item/creators/0/title",
            (item.get("creators") or [{}])[0].get("title"),
            ["assertion:copernicus-authored-de-revolutionibus"],
        ),
        (
            "passage:loc-item-publication-note-0",
            "/item/notes/0/note",
            (item.get("notes") or [{}])[0].get("note"),
            [
                "assertion:copernicus-authored-de-revolutionibus",
                "assertion:publication-event-published-work",
                "assertion:publication-event-printed-by-petreius",
                "assertion:publication-event-occurred-in-nuremberg",
            ],
        ),
        (
            "passage:loc-item-created-published",
            "/item/created_published",
            item.get("created_published"),
            ["assertion:publication-event-published-work"],
        ),
    )
    if any(not isinstance(text, str) or not text for _, _, text, _ in field_specs):
        raise ValueError("LOC snapshot is missing a required exact evidence field")
    if any(
        assertion_id not in assertions_by_id
        for _, _, _, assertion_ids in field_specs
        for assertion_id in assertion_ids
    ):
        raise ValueError("LOC evidence fields reference an unknown curated assertion")

    evidence_text = "\n".join(str(text) for _, _, text, _ in field_specs)
    passages: list[EvidencePassage] = []
    offset = 0
    for passage_id, field_path, text, assertion_ids in field_specs:
        passage_text = str(text)
        passages.append(
            EvidencePassage(
                passage_id=passage_id,
                source_field_path=field_path,
                assertion_ids=assertion_ids,
                start_char=offset,
                end_char=offset + len(passage_text),
                text=passage_text,
                text_sha256=hashlib.sha256(passage_text.encode("utf-8")).hexdigest(),
            )
        )
        offset += len(passage_text) + 1

    modified = item.get("modified")
    if source_ref.version != modified:
        raise ValueError("Curated source revision does not match /item/modified")
    document = EvidenceDocument(
        source_ref=source_ref,
        source_revision_id=source_ref.version,
        source_revision_field_path="/item/modified",
        attribution=source_ref.citation,
        text=evidence_text,
        text_sha256=hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
        passages=passages,
    )
    validate_evidence_document_snapshot(document, snapshot_bytes)
    bundle = ApprovedEvidenceBundle(
        bundle_id="evidence-bundle:copernicus-1543-v1",
        subject_entity_ids=sorted(
            {entity_id for item in assertions for entity_id in item.subject_entity_ids}
        ),
        feature_ids=sorted(
            {feature_id for item in assertions for feature_id in item.feature_ids}
        ),
        assertions=assertions,
        sources=[document],
        approved_by="fixture:derived-from-data/curation/knowledge-1543.yml",
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
    write_json(output_root / "evidence-bundle.json", bundle)
    write_json(output_root / "draft.json", draft)
    print(f"Built deterministic machine dossier draft {draft.draft_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PILOT_ROOT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args()
    build_pilot(args.output, args.snapshot)


if __name__ == "__main__":
    main()
