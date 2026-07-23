from __future__ import annotations

from history_pipeline.adapters.base import AdapterContext, AdapterResult
from history_pipeline.adapters.common import verify_expected_checksum


class CuratedSourceAdapter:
    """Snapshot an authority record used by repository-curated records."""

    def run(self, context: AdapterContext, limit: int | None = None) -> AdapterResult:
        del limit
        filename = str(context.source.options.get("snapshot_filename", "record.json"))
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise ValueError("curated snapshot_filename must be a plain filename")
        asset = context.downloads.fetch(
            str(context.source.url),
            context.raw_source_dir / filename,
        )
        verify_expected_checksum(context.source, asset)
        return AdapterResult(raw_assets=[asset])
