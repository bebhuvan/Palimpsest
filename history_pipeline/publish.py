from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Any

import orjson

from history_pipeline.models import BuildManifest, LatestPointer
from history_pipeline.storage import sha256_file


class R2Publisher:
    """Publish an immutable build and atomically advance its latest pointer."""

    def __init__(
        self,
        bucket: str,
        snapshot_bucket: str | None = None,
        root: Path = Path("dist/data"),
        raw_root: Path = Path("data/raw"),
        prefix: str = "v1",
        wrangler: str = "wrangler",
        dry_run: bool = False,
    ) -> None:
        self.bucket = bucket
        self.snapshot_bucket = snapshot_bucket
        self.root = root
        self.raw_root = raw_root
        self.prefix = prefix.strip("/")
        self.dry_run = dry_run
        self.wrangler = wrangler if dry_run else self._resolve(wrangler)

    def publish_latest(self) -> list[list[str]]:
        latest_path = self.root / "latest.json"
        latest = LatestPointer.model_validate(self._read_json(latest_path))
        manifest_path = self.root / self._safe_relative(latest.manifest)
        if sha256_file(manifest_path) != latest.manifest_checksum_sha256:
            raise ValueError("latest.json manifest checksum does not match its manifest")
        manifest = BuildManifest.model_validate(self._read_json(manifest_path))
        build_dir = manifest_path.parent
        commands: list[list[str]] = []

        if manifest.raw_snapshots and not self.snapshot_bucket:
            raise ValueError(
                "A separate private snapshot bucket is required for reproducible publication"
            )
        for snapshot in manifest.raw_snapshots:
            local_path = (
                self.raw_root / snapshot.source_id / self._safe_relative(snapshot.filename)
            )
            if not local_path.is_file():
                raise FileNotFoundError(f"Missing raw source snapshot: {local_path}")
            actual_checksum = sha256_file(local_path)
            if actual_checksum != snapshot.checksum_sha256:
                raise ValueError(
                    f"Raw snapshot checksum mismatch for {local_path}: "
                    f"expected {snapshot.checksum_sha256}, got {actual_checksum}"
                )
            commands.append(
                self._put_command(
                    local_path,
                    f"{self.prefix}/{snapshot.object_key}",
                    "application/octet-stream",
                    "private, max-age=31536000, immutable",
                    bucket=self.snapshot_bucket,
                )
            )

        for artifact in manifest.artifacts:
            local_path = build_dir / self._safe_relative(artifact.path)
            if not local_path.is_file():
                raise FileNotFoundError(f"Missing release artifact: {local_path}")
            actual_checksum = sha256_file(local_path)
            if actual_checksum != artifact.checksum_sha256:
                raise ValueError(
                    f"Checksum mismatch for {local_path}: "
                    f"expected {artifact.checksum_sha256}, got {actual_checksum}"
                )
            key = f"{self.prefix}/builds/{manifest.build_id}/{artifact.path}"
            commands.append(
                self._put_command(
                    local_path,
                    key,
                    artifact.media_type,
                    artifact.cache_control,
                )
            )

        commands.append(
            self._put_command(
                manifest_path,
                f"{self.prefix}/builds/{manifest.build_id}/manifest.json",
                "application/json",
                "public, max-age=31536000, immutable",
            )
        )
        # This is the only mutable object. Uploading it last makes publication atomic.
        commands.append(
            self._put_command(
                latest_path,
                f"{self.prefix}/latest.json",
                "application/json",
                "public, max-age=60, must-revalidate",
            )
        )

        if not self.dry_run:
            immutable_commands = commands[:-1]
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(self._run, immutable_commands))
            # Advance the mutable pointer only after every immutable upload succeeds.
            self._run(commands[-1])
        return commands

    @staticmethod
    def _run(command: list[str]) -> None:
        subprocess.run(command, check=True)

    def _put_command(
        self,
        path: Path,
        key: str,
        media_type: str,
        cache_control: str,
        *,
        bucket: str | None = None,
    ) -> list[str]:
        return [
            self.wrangler,
            "r2",
            "object",
            "put",
            f"{bucket or self.bucket}/{key}",
            "--file",
            str(path),
            "--content-type",
            media_type,
            "--cache-control",
            cache_control,
            "--remote",
        ]

    @staticmethod
    def _safe_relative(value: str) -> Path:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe path in build manifest: {value}")
        return Path(*path.parts)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("rb") as handle:
            value = orjson.loads(handle.read())
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object: {path}")
        return value

    @staticmethod
    def _resolve(command: str) -> str:
        candidate = Path(command)
        if candidate.is_file():
            return str(candidate)
        resolved = shutil.which(command)
        if resolved:
            return resolved
        local = Path("node_modules/.bin") / command
        if local.is_file():
            return str(local.resolve())
        raise FileNotFoundError(f"Command not found: {command}")
