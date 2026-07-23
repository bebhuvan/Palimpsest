from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from history_pipeline.adapters.wikidata import WikidataEnricher
from history_pipeline.adapters.wikipedia import WikipediaEnricher
from history_pipeline.config import SourceConfig
from history_pipeline.enrichment import EnrichmentCheckpoint
from history_pipeline.storage import DownloadCache


def _wikipedia_source() -> SourceConfig:
    return SourceConfig.model_validate(
        {
            "id": "wikipedia",
            "adapter": "wikipedia",
            "title": "Wikipedia",
            "publisher": "Wikimedia",
            "url": "https://en.wikipedia.org/w/api.php",
            "license_id": "CC-BY-SA-4.0",
            "citation": "Wikipedia contributors",
            "options": {"batch_size": 1, "language": "en"},
        }
    )


def _wikidata_source() -> SourceConfig:
    return SourceConfig.model_validate(
        {
            "id": "wikidata",
            "adapter": "wikidata",
            "title": "Wikidata",
            "publisher": "Wikimedia",
            "url": "https://www.wikidata.org/w/api.php",
            "license_id": "CC0-1.0",
            "citation": "Wikidata contributors",
            "options": {
                "batch_size": 1,
                "languages": ["en"],
                "relationship_depth": 0,
            },
        }
    )


def _entity(qid: str) -> dict[str, object]:
    return {
        "entities": {
            qid: {
                "id": qid,
                "lastrevid": int(qid[1:]) * 10,
                "labels": {
                    "en": {"language": "en", "value": f"Entity {qid}"}
                },
                "claims": {},
                "sitelinks": {},
            }
        }
    }


def _page(title: str, page_id: int) -> dict[str, object]:
    return {
        "query": {
            "pages": [
                {
                    "pageid": page_id,
                    "title": title,
                    "extract": f"{title} introduction.",
                    "fullurl": f"https://en.wikipedia.org/wiki/{title}",
                    "revisions": [
                        {
                            "revid": page_id * 10,
                            "timestamp": "2026-01-01T00:00:00Z",
                        }
                    ],
                }
            ]
        }
    }


def test_wikipedia_enrichment_resumes_completed_batches_and_reports_status(
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("history_pipeline.storage.time.sleep", lambda _: None)
    source = _wikipedia_source()
    status_path = tmp_path / "staged" / "enrichment" / "status.json"
    messages: list[str] = []
    first_checkpoint = EnrichmentCheckpoint(
        status_path, "same-input", emit=messages.append
    )
    # Hash-bucket ordering fetches Beta before Alpha. Complete Beta, then interrupt Alpha.
    httpx_mock.add_response(json=_page("Beta", 2))
    for _ in range(3):
        httpx_mock.add_response(status_code=503)
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        enricher = WikipediaEnricher(
            source, downloads, tmp_path / "raw" / "wikipedia"
        )
        with pytest.raises(Exception) as error:
            enricher.enrich(
                ["Alpha", "Beta"],
                entity_ids_by_title={
                    "Alpha": ["wikidata:Q1"],
                    "Beta": ["wikidata:Q2"],
                },
                checkpoint=first_checkpoint,
            )
    first_checkpoint.fail(error.value)

    failed = json.loads(status_path.read_text(encoding="utf-8"))
    assert failed["state"] == "failed"
    assert failed["stages"]["wikipedia-en"]["completed_count"] == 1

    second_checkpoint = EnrichmentCheckpoint(
        status_path, "same-input", emit=messages.append
    )
    assert second_checkpoint.resumed
    httpx_mock.add_response(json=_page("Alpha", 1))
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        dossiers, assets = WikipediaEnricher(
            source, downloads, tmp_path / "raw" / "wikipedia"
        ).enrich(
            ["Alpha", "Beta"],
            entity_ids_by_title={
                "Alpha": ["wikidata:Q1"],
                "Beta": ["wikidata:Q2"],
            },
            checkpoint=second_checkpoint,
        )
    second_checkpoint.complete(
        entities=0, dossiers=len(dossiers), raw_assets=len(assets)
    )

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["state"] == "complete"
    assert status["resumed"] is True
    assert status["results"]["dossiers"] == 2
    assert [dossier.title for dossier in dossiers] == ["Alpha", "Beta"]
    assert any("reusing checkpointed response" in message for message in messages)


def test_wikidata_enrichment_resumes_completed_batches(
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("history_pipeline.storage.time.sleep", lambda _: None)
    source = _wikidata_source()
    status_path = tmp_path / "staged" / "enrichment" / "status.json"
    first_checkpoint = EnrichmentCheckpoint(status_path, "same-input")
    # Q1 hashes before Q2, so the first response is safely checkpointed.
    httpx_mock.add_response(json=_entity("Q1"))
    for _ in range(3):
        httpx_mock.add_response(status_code=503)
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        with pytest.raises(Exception) as error:
            WikidataEnricher(
                source, downloads, tmp_path / "raw" / "wikidata"
            ).enrich(["Q1", "Q2"], checkpoint=first_checkpoint)
    first_checkpoint.fail(error.value)

    second_checkpoint = EnrichmentCheckpoint(status_path, "same-input")
    httpx_mock.add_response(json=_entity("Q2"))
    with DownloadCache(tmp_path / "cache", "HistoryJoice/test") as downloads:
        entities, assets = WikidataEnricher(
            source, downloads, tmp_path / "raw" / "wikidata"
        ).enrich(["Q1", "Q2"], checkpoint=second_checkpoint)

    assert [entity.entity_id for entity in entities] == [
        "wikidata:Q1",
        "wikidata:Q2",
    ]
    assert len(assets) == 2
    assert second_checkpoint.data["stages"]["wikidata-seeds"]["completed_count"] == 2
