from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import httpx
import orjson

TRANSPORT_CACHE_VERSION = 2


@dataclass(frozen=True)
class RawAsset:
    path: Path
    url: str
    checksum_sha256: str
    retrieved_at: datetime
    etag: str | None
    last_modified: str | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DownloadCache:
    def __init__(
        self,
        root: Path,
        user_agent: str,
        timeout_seconds: float = 120,
        offline: bool = False,
        max_download_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.max_download_bytes = max_download_bytes
        self.client = httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_seconds, connect=30),
            transport=httpx.HTTPTransport(retries=3),
            # Let httpx advertise only encodings supported by installed decoders.
            headers={"User-Agent": user_agent},
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> DownloadCache:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch(
        self,
        url: str,
        destination: Path,
        force: bool = False,
        *,
        reuse_cached: bool = False,
    ) -> RawAsset:
        destination.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = destination.with_suffix(destination.suffix + ".metadata.json")
        metadata = self._load_metadata(metadata_path)
        if self.offline:
            if not destination.exists():
                raise FileNotFoundError(
                    f"Offline build is missing cached source asset: {destination}"
                )
            if not metadata or metadata.get("transport_cache_version") != TRANSPORT_CACHE_VERSION:
                raise ValueError(
                    f"Offline source cache is stale and must be refreshed: {destination}"
                )
            if metadata.get("url") != url:
                raise ValueError(
                    f"Offline source cache URL differs from configuration: {destination}"
                )
            return self._asset_from_metadata(destination, url, metadata)
        headers: dict[str, str] = {}
        cache_is_current = (
            metadata is not None
            and metadata.get("transport_cache_version") == TRANSPORT_CACHE_VERSION
            and metadata.get("url") == url
        )
        current_metadata = metadata if cache_is_current else None
        if (
            reuse_cached
            and destination.exists()
            and current_metadata is not None
            and not force
        ):
            return self._asset_from_metadata(destination, url, current_metadata)
        if destination.exists() and current_metadata is not None and not force:
            if current_metadata.get("etag"):
                headers["If-None-Match"] = current_metadata["etag"]
            if current_metadata.get("last_modified"):
                headers["If-Modified-Since"] = current_metadata["last_modified"]

        for attempt in range(3):
            try:
                with self.client.stream("GET", url, headers=headers) as response:
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                        retry_after = response.headers.get("retry-after", "")
                        delay = (
                            min(float(retry_after), 30.0)
                            if retry_after.isdigit()
                            else 2**attempt
                        )
                    else:
                        return self._store_response(
                            response, destination, metadata_path, url, metadata
                        )
            except httpx.TransportError:
                if attempt >= 2:
                    raise
                delay = 2**attempt
            time.sleep(delay)
        raise RuntimeError(f"Unreachable retry state while downloading {url}")

    def _store_response(
        self,
        response: httpx.Response,
        destination: Path,
        metadata_path: Path,
        url: str,
        metadata: dict[str, Any] | None,
    ) -> RawAsset:
        if response.status_code == 304 and destination.exists():
            return self._asset_from_metadata(destination, url, metadata or {})
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self.max_download_bytes:
            raise ValueError(f"Download exceeds size limit for {url}")
        # Preserve the previous checksummed response before replacing the acquisition path.
        if destination.exists() and metadata:
            self._asset_from_metadata(destination, url, metadata)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                downloaded = 0
                for chunk in response.iter_bytes(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > self.max_download_bytes:
                        raise ValueError(f"Download exceeds size limit for {url}")
                    temporary.write(chunk)
            os.replace(temporary_path, destination)
            temporary_path = None
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
        retrieved_at = datetime.now(UTC)
        result = {
            "transport_cache_version": TRANSPORT_CACHE_VERSION,
            "url": url,
            "checksum_sha256": sha256_file(destination),
            "retrieved_at": retrieved_at.isoformat(),
            "etag": response.headers.get("etag"),
            "last_modified": response.headers.get("last-modified"),
            "bytes": destination.stat().st_size,
        }
        self._write_json_atomic(metadata_path, result)
        return self._asset_from_metadata(destination, url, result)

    @staticmethod
    def _load_metadata(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        with path.open("rb") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"Download metadata must be a JSON object: {path}")
        return value

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(orjson.dumps(value, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))
            temporary.write(b"\n")
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)

    @staticmethod
    def _asset_from_metadata(path: Path, url: str, metadata: dict[str, Any]) -> RawAsset:
        checksum = sha256_file(path)
        expected_checksum = metadata.get("checksum_sha256")
        if expected_checksum and expected_checksum != checksum:
            raise ValueError(
                f"Cached source checksum mismatch for {path}: "
                f"expected {expected_checksum}, got {checksum}"
            )
        expected_bytes = metadata.get("bytes")
        if expected_bytes is not None and int(expected_bytes) != path.stat().st_size:
            raise ValueError(f"Cached source size mismatch for {path}")
        retrieved = metadata.get("retrieved_at")
        retrieved_at = datetime.fromisoformat(retrieved) if retrieved else datetime.now(UTC)
        snapshot_path = DownloadCache._preserve_snapshot(path, checksum)
        return RawAsset(
            path=snapshot_path,
            url=url,
            checksum_sha256=checksum,
            retrieved_at=retrieved_at,
            etag=metadata.get("etag"),
            last_modified=metadata.get("last_modified"),
        )

    @staticmethod
    def _preserve_snapshot(path: Path, checksum: str) -> Path:
        snapshot = path.parent / "snapshots" / checksum / path.name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists():
            if sha256_file(snapshot) != checksum:
                raise ValueError(f"Preserved source snapshot is corrupt: {snapshot}")
            return snapshot
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=snapshot.parent, prefix=f".{snapshot.name}.", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                with path.open("rb") as source:
                    shutil.copyfileobj(source, temporary, length=1024 * 1024)
            os.replace(temporary_path, snapshot)
            temporary_path = None
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
        return snapshot


def safely_extract_member(
    archive: Path,
    member_name: str,
    destination: Path,
    *,
    maximum_uncompressed_bytes: int = 1024 * 1024 * 1024,
    maximum_compression_ratio: float = 200,
) -> Path:
    """Extract exactly one configured member and reject path traversal."""

    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as bundle:
        candidates = [name for name in bundle.namelist() if name == member_name]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected exactly one archive member {member_name!r}; found {len(candidates)}"
            )
        name = candidates[0]
        info = bundle.getinfo(name)
        if info.file_size > maximum_uncompressed_bytes:
            raise ValueError(f"Archive member exceeds size limit: {name}")
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > maximum_compression_ratio:
            raise ValueError(f"Archive member has unsafe compression ratio: {name}")
        output = (destination / Path(name).name).resolve()
        if destination.resolve() not in output.parents:
            raise ValueError(f"Unsafe archive member: {name}")
        with (
            bundle.open(name) as source,
            tempfile.NamedTemporaryFile(
                dir=destination, prefix=f".{output.name}.", delete=False
            ) as temporary,
        ):
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                temporary.write(chunk)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output)
        return output


class NdjsonWriter:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._handle = path.open("wb")

    def write(self, value: Any) -> None:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        self._handle.write(orjson.dumps(value, option=orjson.OPT_SORT_KEYS))
        self._handle.write(b"\n")

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> NdjsonWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def read_ndjson(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield orjson.loads(line)
            except orjson.JSONDecodeError as error:
                raise ValueError(f"Invalid NDJSON in {path}:{line_number}") from error
