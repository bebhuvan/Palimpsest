from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import httpx
import orjson
from pydantic import HttpUrl

from history_pipeline.config import SourceConfig
from history_pipeline.enrichment import EnrichmentCheckpoint
from history_pipeline.models import HistoricalDossier, SourceReference
from history_pipeline.storage import DownloadCache, RawAsset


class WikipediaEnricher:
    def __init__(
        self, source: SourceConfig, downloads: DownloadCache, raw_source_dir: Path
    ) -> None:
        self.source = source
        self.downloads = downloads
        self.raw_source_dir = raw_source_dir

    def enrich(
        self,
        titles: Iterable[str],
        *,
        entity_ids_by_title: Mapping[str, list[str]] | None = None,
        checkpoint: EnrichmentCheckpoint | None = None,
    ) -> tuple[list[HistoricalDossier], list[RawAsset]]:
        unique = sorted({title.strip() for title in titles if title.strip()})
        batch_size = min(max(int(self.source.options.get("batch_size", 20)), 1), 20)
        language = str(self.source.options.get("language", "en"))
        dossiers: list[HistoricalDossier] = []
        assets: list[RawAsset] = []
        batches = _stable_title_batches(unique, batch_size)
        stage = f"wikipedia-{language}"
        if checkpoint:
            checkpoint.begin_stage(stage, len(batches))
        for position, (bucket, batch) in enumerate(batches.items(), start=1):
            params = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "extracts|info|pageprops|revisions",
                "exintro": "1",
                "explaintext": "1",
                "inprop": "url",
                "rvprop": "ids|timestamp",
                "redirects": "1",
                "maxlag": "5",
                "titles": "|".join(batch),
            }
            request_url = str(httpx.URL(str(self.source.url)).copy_merge_params(params))
            batch_id = hashlib.sha256(request_url.encode()).hexdigest()[:12]
            reusing = bool(checkpoint and checkpoint.should_resume(stage, bucket))
            if checkpoint:
                checkpoint.batch_started(
                    stage,
                    bucket,
                    position,
                    len(batches),
                    reusing=reusing,
                )
            asset = self.downloads.fetch(
                request_url,
                self.raw_source_dir / f"extracts-{language}-{bucket}-{batch_id}.json",
                reuse_cached=reusing,
            )
            assets.append(asset)
            with asset.path.open("rb") as handle:
                payload = orjson.loads(handle.read())
            dossiers.extend(
                self._parse(
                    payload,
                    asset,
                    language,
                    batch,
                    entity_ids_by_title or {},
                )
            )
            if checkpoint:
                checkpoint.batch_completed(stage, bucket)
        if checkpoint:
            checkpoint.stage_completed(stage)
        return _merge_duplicate_pages(dossiers), assets

    def _parse(
        self,
        payload: dict[str, Any],
        asset: RawAsset,
        language: str,
        requested: list[str],
        entity_ids_by_title: Mapping[str, list[str]],
    ) -> list[HistoricalDossier]:
        if payload.get("error"):
            raise ValueError(f"Wikipedia API error: {payload['error']}")
        query = payload.get("query")
        if not isinstance(query, dict) or not isinstance(query.get("pages"), list):
            raise ValueError("Wikipedia response has no page list")
        title_targets = _title_targets(query)
        dossiers: list[HistoricalDossier] = []
        for page in query["pages"]:
            if (
                not isinstance(page, dict)
                or page.get("missing")
                or page.get("invalid")
                or not isinstance(page.get("pageid"), int)
                or (
                    isinstance(page.get("pageprops"), dict)
                    and "disambiguation" in page["pageprops"]
                )
            ):
                continue
            revision = (page.get("revisions") or [{}])[0]
            if not isinstance(revision, dict) or not revision.get("revid"):
                raise ValueError(
                    f"Wikipedia page {page['pageid']} has no pinned revision ID"
                )
            if not revision.get("timestamp"):
                raise ValueError(
                    f"Wikipedia page {page['pageid']} has no revision timestamp"
                )
            if not page.get("fullurl"):
                raise ValueError(
                    f"Wikipedia page {page['pageid']} has no canonical full URL"
                )
            extract = str(page.get("extract", "")).strip()
            if not extract:
                continue
            page_url = HttpUrl(str(page["fullurl"]))
            canonical_title = str(page["title"])
            matched_titles = sorted(
                title
                for title in requested
                if _resolve_title(title, title_targets).casefold()
                == canonical_title.casefold()
            )
            entity_ids = sorted(
                {
                    entity_id
                    for title in matched_titles
                    for entity_id in entity_ids_by_title.get(title, [])
                }
            )
            source_ref = SourceReference(
                source_id=self.source.id,
                record_id=str(page["pageid"]),
                title=f"Wikipedia: {canonical_title}",
                publisher=self.source.publisher,
                url=page_url,
                license_id=self.source.license_id,
                retrieved_at=asset.retrieved_at,
                version=str(revision.get("revid")) if revision.get("revid") else None,
                checksum_sha256=asset.checksum_sha256,
                citation=self.source.citation,
            )
            dossiers.append(
                HistoricalDossier(
                    dossier_id=f"wikipedia:{language}:{page['pageid']}",
                    title=canonical_title,
                    language=language,
                    entity_ids=entity_ids,
                    extract=extract,
                    url=page_url,
                    page_id=page["pageid"],
                    revision_id=revision.get("revid"),
                    revision_timestamp=revision.get("timestamp"),
                    requested_titles=matched_titles,
                    redirects_from=sorted(
                        title
                        for title in matched_titles
                        if title.casefold() != canonical_title.casefold()
                    ),
                    content_checksum_sha256=hashlib.sha256(extract.encode("utf-8")).hexdigest(),
                    source_ref=source_ref,
                )
            )
        return dossiers


def _merge_duplicate_pages(
    dossiers: Iterable[HistoricalDossier],
) -> list[HistoricalDossier]:
    """Publish one dossier per Wikipedia page while retaining every resolved join.

    Different requested titles can resolve to the same canonical page from separate
    stable hash buckets. Keep the newest pinned revision and merge the titles and
    entity links that led to it.
    """

    by_id: dict[str, list[HistoricalDossier]] = {}
    for dossier in dossiers:
        by_id.setdefault(dossier.dossier_id, []).append(dossier)
    merged: list[HistoricalDossier] = []
    for dossier_id in sorted(by_id):
        candidates = by_id[dossier_id]
        selected = max(
            candidates,
            key=lambda dossier: (
                dossier.revision_timestamp.isoformat()
                if dossier.revision_timestamp
                else "",
                dossier.revision_id or -1,
                dossier.content_checksum_sha256,
            ),
        )
        merged.append(
            selected.model_copy(
                update={
                    "entity_ids": sorted(
                        {
                            entity_id
                            for candidate in candidates
                            for entity_id in candidate.entity_ids
                        }
                    ),
                    "requested_titles": sorted(
                        {
                            title
                            for candidate in candidates
                            for title in candidate.requested_titles
                        }
                    ),
                    "redirects_from": sorted(
                        {
                            title
                            for candidate in candidates
                            for title in candidate.redirects_from
                        }
                    ),
                }
            )
        )
    return merged


def _title_targets(query: dict[str, Any]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for key in ("normalized", "redirects"):
        for item in query.get(key) or []:
            if isinstance(item, dict) and item.get("from") and item.get("to"):
                targets[str(item["from"]).casefold()] = str(item["to"])
    return targets


def _resolve_title(title: str, targets: dict[str, str]) -> str:
    current = title
    seen: set[str] = set()
    while current.casefold() in targets and current.casefold() not in seen:
        seen.add(current.casefold())
        current = targets[current.casefold()]
    return current


def _stable_title_batches(titles: list[str], batch_size: int) -> dict[str, list[str]]:
    hash_buckets: dict[str, list[str]] = {}
    for title in titles:
        bucket = hashlib.sha256(title.encode("utf-8")).hexdigest()[:2]
        hash_buckets.setdefault(bucket, []).append(title)
    batches: dict[str, list[str]] = {}
    for bucket, values in sorted(hash_buckets.items()):
        ordered = sorted(values)
        for offset in range(0, len(ordered), batch_size):
            batches[f"h{bucket}-{offset // batch_size:03d}"] = ordered[
                offset : offset + batch_size
            ]
    return batches
