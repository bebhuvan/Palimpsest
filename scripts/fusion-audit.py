"""Lay every generated sentence beside the evidence its block was allowed to use.

The containment check proves that each name and number came from the evidence. It cannot prove
the relationship asserted between them, so two true facts can be joined into a false third and
pass everything. That failure has a name here — fusion — and nobody has measured how often it
happens.

This does not detect fusion. Nothing mechanical does; if it could, the check would already reject
it. What this does is make the measurement possible: one sentence per row, with the block's whole
evidence set beside it, in a form somebody can read and mark. The marking has to come from
outside, and specifically not from the model that wrote the prose, which will agree with itself.

    uv run python scripts/fusion-audit.py --year 1543 --output build/audit-1543.md

Then read it, and for each sentence write one of:

    ok        every claim, including the relationships, is in the evidence
    fusion    every name is in the evidence and the relationship between them is not
    unclear   cannot be decided from the evidence alone

`--sample N` takes a spread across blocks rather than the first N, so the count means something.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from history_pipeline.year_dossier import (
    LENS_HEADINGS,
    overview_digest,
    plan_anchors,
    plan_sections,
    read_chronicle,
    read_year_context,
    section_evidence_text,
)
from history_pipeline.year_layers import (
    assemble_lede,
    build_incumbents,
    build_themes,
    cluster_entries,
    extract_index,
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ɏ“(])")


def sentences(prose: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(prose.strip()) if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--chronicle-dir", type=Path, default=Path("data/chronicle"))
    arguments = parser.parse_args()

    directory = arguments.chronicle_dir
    year = arguments.year
    chronicle = read_chronicle(directory / f"{year}.json")
    dossier = json.loads((directory / f"{year}-dossier.json").read_text(encoding="utf-8"))
    lenses_path = directory / f"{year}-lenses.json"
    lenses = json.loads(lenses_path.read_text()) if lenses_path.exists() else {}
    context_path = directory / f"{year}-context.json"
    context = read_year_context(context_path) if context_path.exists() else None

    extracts = extract_index(chronicle.subject_extracts)
    clusters = cluster_entries(chronicle.entries)
    plan = plan_sections(chronicle.entries, lenses)
    anchors = plan_anchors(chronicle.entries, lenses, extracts)
    lede, _ = assemble_lede(chronicle, clusters)
    digest = overview_digest(
        chronicle,
        clusters,
        lenses,
        lede,
        build_themes(clusters, lenses, LENS_HEADINGS),
        build_incumbents(chronicle.entries),
        context,
        anchors,
    )

    blocks: list[tuple[str, str, str]] = []
    overview = dossier.get("overview") or {}
    if overview.get("prose"):
        blocks.append(("overview", overview["prose"], digest))
    by_id = {planned.anchor_id: planned for planned in anchors}
    for anchor in dossier.get("anchors", []):
        planned = by_id.get(anchor["anchor_id"])
        if planned:
            blocks.append((f"anchor {anchor['heading']}", anchor["prose"], planned.evidence()))
    for section in dossier.get("sections", []):
        group = next(
            (entries for section_id, _, entries in plan if section_id == section["section_id"]),
            [],
        )
        blocks.append(
            (
                f"section {section['heading']}",
                section["prose"],
                section_evidence_text(group, extracts, clusters),
            )
        )

    rows = [
        (name, index, sentence, evidence)
        for name, prose, evidence in blocks
        for index, sentence in enumerate(sentences(prose), start=1)
    ]
    if arguments.sample and arguments.sample < len(rows):
        step = len(rows) / arguments.sample
        rows = [rows[int(position * step)] for position in range(arguments.sample)]

    lines = [
        f"# Fusion audit: {year}",
        "",
        f"{len(rows)} generated sentences, each beside the evidence its block was allowed to use.",
        "",
        "Mark each `verdict` as `ok`, `fusion` or `unclear`. A `fusion` is a sentence where every",
        "name and number is in the evidence and the relationship asserted between them is not.",
        "The containment check passed all of these; that is the point of the exercise.",
        "",
        "---",
        "",
    ]
    # The evidence is printed once per block rather than once per sentence. Repeating it made a
    # three-megabyte file nobody could scroll, which is a good way to guarantee the measurement
    # never gets made.
    current = None
    for name, index, sentence, evidence in rows:
        if name != current:
            current = name
            lines.append(f"## {name}")
            lines.append("")
            lines.append("<details><summary>the evidence this block was allowed to use</summary>")
            lines.append("")
            lines.append("```")
            lines.append(evidence)
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")
        lines.append(f"**{index}.** {sentence}")
        lines.append("")
        lines.append("verdict: ")
        lines.append("")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(rows)} sentences to {arguments.output}")


if __name__ == "__main__":
    main()
