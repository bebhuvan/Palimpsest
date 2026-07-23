from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from history_pipeline.models import ArtifactFile, BuildManifest
from history_pipeline.storage import sha256_file
from history_pipeline.verify import _verify_content_contract, verify_latest_build


def _release(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "dist"
    raw = tmp_path / "raw"
    build_id = "content123"
    build = root / "builds" / build_id
    build.mkdir(parents=True)
    for name in ("coverage.json", "attribution.json", "quality.json"):
        (build / name).write_text("[]\n", encoding="utf-8")
    content = build / "content"
    content.mkdir()
    (content / "index.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "sharding": {"algorithm": "sha256", "encoding": "utf-8", "prefix_length": 2},
                "collections": {
                    name: {
                        "path_template": f"content/{directory}/{{shard}}.json",
                        "count": 0,
                        "shards": [],
                    }
                    for name, directory in (
                        ("feature_links", "links"),
                        ("entities", "entities"),
                        ("dossiers", "dossiers"),
                    )
                },
                "language_policy": {"selection": "fallback", "available": []},
            }
        ),
        encoding="utf-8",
    )
    artifacts = [
        ArtifactFile(
            path=name,
            media_type="application/json",
            bytes=(build / name).stat().st_size,
            checksum_sha256=sha256_file(build / name),
            cache_control="public, max-age=31536000, immutable",
        )
        for name in ("coverage.json", "attribution.json", "quality.json", "content/index.json")
    ]
    manifest = BuildManifest(
        schema_version="1.2.0",
        build_id=build_id,
        generated_at=datetime.now(UTC),
        minimum_year=-3400,
        maximum_year=2026,
        sources=[],
        artifacts=artifacts,
        rejected_record_count=0,
        coverage_path="coverage.json",
        attribution_path="attribution.json",
    )
    (build / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), default=str), encoding="utf-8"
    )
    root.mkdir(exist_ok=True)
    (root / "latest.json").write_text(
        json.dumps(
            {
                "schema_version": manifest.schema_version,
                "build_id": build_id,
                "manifest": f"builds/{build_id}/manifest.json",
                "manifest_checksum_sha256": sha256_file(build / "manifest.json"),
                "generated_at": manifest.generated_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return root, raw


def test_verify_latest_build_checks_contract_and_files(tmp_path: Path) -> None:
    root, raw = _release(tmp_path)
    manifest = verify_latest_build(root, raw)
    assert manifest.build_id == "content123"


def test_verify_latest_build_requires_tiles_when_requested(tmp_path: Path) -> None:
    root, raw = _release(tmp_path)
    with pytest.raises(ValueError, match="PMTiles"):
        verify_latest_build(root, raw, require_tiles=True)


def test_content_verification_rejects_inconsistent_entity_availability(
    tmp_path: Path,
) -> None:
    build = tmp_path / "build"
    (build / "content/links").mkdir(parents=True)
    (build / "content/links/aa.json").write_text(
        json.dumps(
            {
                "feature:1": {
                    "feature_id": "feature:1",
                    "primary_entity_id": "wikidata:Q1",
                    "entity_ids": ["wikidata:Q1"],
                    "available_entity_ids": [],
                    "missing_entity_ids": [],
                    "dossier_ids": [],
                    "related_entity_ids": [],
                }
            }
        ),
        encoding="utf-8",
    )
    (build / "content/index.json").write_text(
        json.dumps(
            {
                "sharding": {"algorithm": "sha256"},
                "collections": {
                    "feature_links": {
                        "path_template": "content/links/{shard}.json",
                        "count": 1,
                        "shards": ["aa"],
                    },
                    "entities": {
                        "path_template": "content/entities/{shard}.json",
                        "count": 0,
                        "shards": [],
                    },
                    "dossiers": {
                        "path_template": "content/dossiers/{shard}.json",
                        "count": 0,
                        "shards": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="availability"):
        _verify_content_contract(
            build,
            "content/index.json",
            {"content/index.json", "content/links/aa.json"},
        )
