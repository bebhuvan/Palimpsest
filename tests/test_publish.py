from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from history_pipeline.models import ArtifactFile, BuildManifest
from history_pipeline.publish import R2Publisher
from history_pipeline.storage import sha256_file


def test_publisher_uploads_pointer_last(tmp_path: Path) -> None:
    root = tmp_path / "data"
    build_id = "abc123"
    build = root / "builds" / build_id
    build.mkdir(parents=True)
    artifact_path = build / "coverage.json"
    artifact_path.write_text("{}\n")
    artifact = ArtifactFile(
        path="coverage.json",
        media_type="application/json",
        bytes=artifact_path.stat().st_size,
        checksum_sha256=sha256_file(artifact_path),
        cache_control="public, max-age=31536000, immutable",
    )
    manifest = BuildManifest(
        build_id=build_id,
        minimum_year=-3400,
        maximum_year=2026,
        sources=[],
        artifacts=[artifact],
        rejected_record_count=0,
        coverage_path="coverage.json",
        attribution_path="attribution.json",
        generated_at=datetime.now(UTC),
    )
    (build / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), default=str)
    )
    (root / "latest.json").write_text(
        json.dumps(
            {
                "schema_version": manifest.schema_version,
                "build_id": build_id,
                "manifest": f"builds/{build_id}/manifest.json",
                "manifest_checksum_sha256": sha256_file(build / "manifest.json"),
                "generated_at": manifest.generated_at.isoformat(),
            }
        )
    )

    commands = R2Publisher(
        "bucket", root=root, wrangler="/bin/true", dry_run=True
    ).publish_latest()
    assert commands[-1][4] == "bucket/v1/latest.json"
    assert any("immutable" in argument for argument in commands[0])


def test_publisher_never_advances_pointer_after_immutable_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    build_id = "failed-build"
    build = root / "builds" / build_id
    build.mkdir(parents=True)
    artifact_path = build / "coverage.json"
    artifact_path.write_text("{}\n", encoding="utf-8")
    artifact = ArtifactFile(
        path="coverage.json",
        media_type="application/json",
        bytes=artifact_path.stat().st_size,
        checksum_sha256=sha256_file(artifact_path),
        cache_control="public, max-age=31536000, immutable",
    )
    manifest = BuildManifest(
        schema_version="1.1.0",
        build_id=build_id,
        minimum_year=-3400,
        maximum_year=2026,
        sources=[],
        artifacts=[artifact],
        rejected_record_count=0,
        coverage_path="coverage.json",
        attribution_path="attribution.json",
        generated_at=datetime.now(UTC),
    )
    (build / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), default=str), encoding="utf-8"
    )
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
    publisher = R2Publisher("bucket", root=root, wrangler="/bin/true")
    attempted: list[str] = []

    def fail_immutable(command: list[str]) -> None:
        attempted.append(command[4])
        raise RuntimeError("upload failed")

    monkeypatch.setattr(publisher, "_run", fail_immutable)
    with pytest.raises(RuntimeError, match="upload failed"):
        publisher.publish_latest()
    assert "bucket/v1/latest.json" not in attempted
