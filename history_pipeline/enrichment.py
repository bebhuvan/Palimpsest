from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson


class EnrichmentCheckpoint:
    """Persist observable, resumable progress for one deterministic enrichment input."""

    def __init__(
        self,
        path: Path,
        run_id: str,
        *,
        emit: Callable[[str], None] | None = None,
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.emit = emit
        previous = self._load()
        self.resumed = bool(
            previous
            and previous.get("run_id") == run_id
            and previous.get("state") in {"running", "failed"}
        )
        stages = previous.get("stages", {}) if self.resumed and previous else {}
        started_at = previous.get("started_at") if self.resumed and previous else None
        self.data: dict[str, Any] = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "state": "running",
            "resumed": self.resumed,
            "started_at": started_at or self._now(),
            "updated_at": self._now(),
            "stages": stages if isinstance(stages, dict) else {},
        }
        self._write()
        action = "Resuming" if self.resumed else "Starting"
        self._emit(f"{action} Wikimedia enrichment run {run_id}")

    def begin_stage(self, stage: str, total_batches: int) -> None:
        existing = self.data["stages"].get(stage, {})
        completed = existing.get("completed_batches", [])
        if not isinstance(completed, list):
            completed = []
        self.data["stages"][stage] = {
            "state": "running",
            "total_batches": total_batches,
            "completed_batches": completed,
            "completed_count": len(completed),
            "current_batch": None,
        }
        self._touch()
        self._emit(
            f"{stage}: {len(completed)}/{total_batches} batches already checkpointed"
        )

    def should_resume(self, stage: str, batch_key: str) -> bool:
        stage_data = self.data["stages"].get(stage, {})
        return self.resumed and batch_key in stage_data.get("completed_batches", [])

    def batch_started(
        self,
        stage: str,
        batch_key: str,
        position: int,
        total_batches: int,
        *,
        reusing: bool,
    ) -> None:
        stage_data = self.data["stages"][stage]
        stage_data["current_batch"] = batch_key
        self._touch()
        mode = "reusing checkpointed response" if reusing else "fetching/revalidating"
        self._emit(f"{stage}: batch {position}/{total_batches} {batch_key} ({mode})")

    def batch_completed(self, stage: str, batch_key: str) -> None:
        stage_data = self.data["stages"][stage]
        completed = stage_data["completed_batches"]
        if batch_key not in completed:
            completed.append(batch_key)
            completed.sort()
        stage_data["completed_count"] = len(completed)
        stage_data["current_batch"] = None
        self._touch()

    def stage_completed(self, stage: str) -> None:
        stage_data = self.data["stages"][stage]
        stage_data["state"] = "complete"
        stage_data["current_batch"] = None
        self._touch()
        self._emit(
            f"{stage}: complete ({stage_data['completed_count']}/"
            f"{stage_data['total_batches']} batches)"
        )

    def complete(self, *, entities: int, dossiers: int, raw_assets: int) -> None:
        self.data["state"] = "complete"
        self.data["completed_at"] = self._now()
        self.data["results"] = {
            "entities": entities,
            "dossiers": dossiers,
            "raw_assets": raw_assets,
        }
        self.data.pop("error", None)
        self._touch()
        self._emit(
            f"Wikimedia enrichment complete: {entities} entities, "
            f"{dossiers} dossiers, {raw_assets} raw responses"
        )

    def fail(self, error: Exception) -> None:
        self.data["state"] = "failed"
        self.data["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
        self._touch()
        self._emit(f"Wikimedia enrichment stopped: {type(error).__name__}: {error}")

    def _load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with self.path.open("rb") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None

    def _touch(self) -> None:
        self.data["updated_at"] = self._now()
        self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(
                    orjson.dumps(
                        self.data,
                        option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
                    )
                )
                temporary.write(b"\n")
            os.replace(temporary_path, self.path)
            temporary_path = None
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)

    def _emit(self, message: str) -> None:
        if self.emit:
            self.emit(message)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
