from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from history_pipeline.storage import DownloadCache, safely_extract_member


def test_offline_cache_requires_same_url_and_valid_checksum(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    destination = tmp_path / "raw" / "source.json"
    httpx_mock.add_response(url="https://example.org/v1.json", content=b'{"version":1}')
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        downloads.fetch("https://example.org/v1.json", destination)

    with DownloadCache(tmp_path / "cache", "HistoryJoice/test", offline=True) as downloads:
        with pytest.raises(ValueError, match="URL differs"):
            downloads.fetch("https://example.org/v2.json", destination)

    destination.write_bytes(b"tampered")
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test", offline=True) as downloads:
        with pytest.raises(ValueError, match="checksum mismatch"):
            downloads.fetch("https://example.org/v1.json", destination)


def test_offline_cache_rejects_old_transport_metadata(tmp_path: Path) -> None:
    destination = tmp_path / "raw" / "source.json"
    destination.parent.mkdir(parents=True)
    destination.write_text("{}", encoding="utf-8")
    destination.with_suffix(".json.metadata.json").write_text(
        json.dumps({"transport_cache_version": 1}), encoding="utf-8"
    )
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test", offline=True) as downloads:
        with pytest.raises(ValueError, match="stale"):
            downloads.fetch("https://example.org/source.json", destination)


def test_download_cache_retries_transient_server_errors(
    tmp_path: Path, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("history_pipeline.storage.time.sleep", lambda _: None)
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(content=b"recovered")
    destination = tmp_path / "raw" / "source.bin"

    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        asset = downloads.fetch("https://example.org/source.bin", destination)

    assert destination.read_bytes() == b"recovered"
    assert asset.checksum_sha256


def test_download_cache_retries_transport_errors(
    tmp_path: Path, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("history_pipeline.storage.time.sleep", lambda _: None)
    httpx_mock.add_exception(httpx.ReadTimeout("Wikimedia response stalled"))
    httpx_mock.add_response(content=b"recovered")
    destination = tmp_path / "raw" / "source.bin"

    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        asset = downloads.fetch("https://example.org/source.bin", destination)

    assert destination.read_bytes() == b"recovered"
    assert asset.checksum_sha256


def test_download_cache_preserves_content_addressed_versions(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    destination = tmp_path / "raw" / "source.json"
    url = "https://example.org/source.json"
    httpx_mock.add_response(url=url, content=b'{"version":1}')
    httpx_mock.add_response(url=url, content=b'{"version":2}')

    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        first = downloads.fetch(url, destination)
        second = downloads.fetch(url, destination, force=True)

    assert first.path != destination
    assert first.path.read_bytes() == b'{"version":1}'
    assert second.path.read_bytes() == b'{"version":2}'
    assert first.path != second.path


def test_download_cache_can_resume_a_checkpointed_response_without_network(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    destination = tmp_path / "raw" / "source.json"
    url = "https://example.org/source.json"
    httpx_mock.add_response(url=url, content=b'{"complete":true}')

    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        first = downloads.fetch(url, destination)
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        resumed = downloads.fetch(url, destination, reuse_cached=True)

    assert resumed == first


def test_download_cache_rejects_oversized_response(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(content=b"12345")
    with DownloadCache(
        tmp_path / "cache", "HistoryJoice/test", max_download_bytes=4
    ) as downloads:
        with pytest.raises(ValueError, match="size limit"):
            downloads.fetch("https://example.org/large", tmp_path / "raw" / "large")


def test_archive_extraction_rejects_oversized_member(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("data.json", "12345")
    with pytest.raises(ValueError, match="size limit"):
        safely_extract_member(
            archive,
            "data.json",
            tmp_path / "out",
            maximum_uncompressed_bytes=4,
        )
