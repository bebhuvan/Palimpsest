from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx
import orjson
from pydantic import HttpUrl

from history_pipeline.config import SourceConfig
from history_pipeline.enrichment import EnrichmentCheckpoint
from history_pipeline.models import (
    Confidence,
    ConfidenceGrade,
    EntityCoordinate,
    EntityDateClaim,
    EntityRelationship,
    HistoricalEntity,
    SourceReference,
    WikidataReference,
    WikidataSnak,
    WikipediaSitelink,
)
from history_pipeline.storage import DownloadCache, RawAsset

QID = re.compile(r"^Q[1-9][0-9]*$")
DATE_PREDICATES = {
    "P571": "inception",
    "P576": "dissolution",
    "P569": "birth",
    "P570": "death",
    "P585": "point_in_time",
    "P580": "start_time",
    "P582": "end_time",
}
RELATION_PREDICATES = {
    "P31": "instance_of",
    "P155": "predecessor",
    "P156": "successor",
    "P36": "capital",
    "P17": "country_or_parent_polity",
    "P131": "located_in_territorial_entity",
    "P361": "part_of",
    "P463": "member_of",
    "P527": "has_part",
    "P150": "contains_administrative_entity",
    "P793": "significant_event",
    "P112": "founded_by",
    "P276": "location",
    "P19": "birth_place",
    "P20": "death_place",
    "P710": "participant",
    "P1344": "participant_in",
    "P607": "conflict",
    "P106": "occupation",
    "P39": "position_held",
    "P135": "movement",
    "P136": "genre",
    "P921": "main_subject",
    "P1269": "facet_of",
}
IMAGE_PREDICATE = "P18"
COORDINATE_PREDICATE = "P625"
COMMONS_CATEGORY_PREDICATE = "P373"
DEFAULT_PREDICATES = [
    *DATE_PREDICATES,
    *RELATION_PREDICATES,
    IMAGE_PREDICATE,
    COORDINATE_PREDICATE,
    COMMONS_CATEGORY_PREDICATE,
]
ENTITY_TYPE_NAMES = {
    "Q5": "human",
    "Q6256": "country",
    "Q3024240": "historical_country",
    "Q3624078": "sovereign_state",
    "Q486972": "human_settlement",
    "Q4830453": "business_or_organization",
    "Q1656682": "event",
    "Q1190554": "occurrence",
    "Q13418847": "historical_event",
    "Q198": "war",
    "Q178561": "battle",
    "Q131569": "treaty",
    "Q43229": "organization",
}
WIKIMEDIA_NAVIGATION_ENTITY_TYPES = {
    # These items describe Wikimedia's navigation infrastructure, not historical
    # subjects that should be joined to map features.
    "Q4167410",  # Wikimedia disambiguation page
}


class WikidataEnricher:
    """Fetch a fixed, shallow Wikidata projection for already-linked items.

    Only configured predicates are parsed. Optional depth-one expansion is explicitly capped.
    Numeric QID buckets make incremental additions invalidate at most one small request bucket.
    """

    def __init__(
        self, source: SourceConfig, downloads: DownloadCache, raw_source_dir: Path
    ) -> None:
        self.source = source
        self.downloads = downloads
        self.raw_source_dir = raw_source_dir

    def enrich(
        self,
        qids: Iterable[str],
        *,
        checkpoint: EnrichmentCheckpoint | None = None,
    ) -> tuple[list[HistoricalEntity], list[RawAsset]]:
        unique = sorted({qid for qid in qids if QID.fullmatch(qid)}, key=_qid_number)
        batch_size = min(max(int(self.source.options.get("batch_size", 50)), 1), 50)
        relationship_depth = int(self.source.options.get("relationship_depth", 0))
        if relationship_depth not in {0, 1}:
            raise ValueError("Wikidata relationship_depth must be 0 or 1")
        configured = self.source.options.get("predicates", DEFAULT_PREDICATES)
        predicates = [str(predicate) for predicate in configured]
        unknown = set(predicates) - set(DEFAULT_PREDICATES)
        if unknown:
            raise ValueError(f"Unsupported Wikidata predicates: {sorted(unknown)}")
        languages = [str(value) for value in self.source.options.get("languages", ["en"])]
        site_languages = [
            str(value)
            for value in self.source.options.get("sitelink_languages", languages)
        ]
        entities, assets = self._fetch(
            unique,
            batch_size,
            languages,
            site_languages,
            predicates,
            stage="wikidata-seeds",
            checkpoint=checkpoint,
        )
        if relationship_depth == 0 or not entities:
            return entities, assets
        expansion_predicates = {
            str(value)
            for value in self.source.options.get(
                "expansion_predicates",
                ["P155", "P156", "P36", "P361", "P527", "P793", "P112"],
            )
        }
        if unknown_expansion := expansion_predicates - set(RELATION_PREDICATES):
            raise ValueError(
                f"Unsupported Wikidata expansion predicates: {sorted(unknown_expansion)}"
            )
        selected, discovered_from, discovery_predicates = _select_expansion_qids(
            entities,
            expansion_predicates,
            per_seed=max(
                1, min(int(self.source.options.get("max_related_entities_per_seed", 40)), 100)
            ),
            total=max(
                1, min(int(self.source.options.get("max_related_entities_total", 2000)), 10000)
            ),
        )
        seed_ids = {entity.wikidata_id for entity in entities if entity.wikidata_id}
        selected = [qid for qid in selected if qid not in seed_ids]
        related, related_assets = self._fetch(
            selected,
            batch_size,
            languages,
            site_languages,
            predicates,
            stage="wikidata-related",
            checkpoint=checkpoint,
        )
        enriched_related = [
            entity.model_copy(
                update={
                    "context_depth": 1,
                    "discovered_from_entity_ids": sorted(
                        f"wikidata:{qid}"
                        for qid in discovered_from.get(entity.wikidata_id or "", set())
                    ),
                    "discovery_predicates": sorted(
                        discovery_predicates.get(entity.wikidata_id or "", set())
                    ),
                }
            )
            for entity in related
        ]
        combined = {entity.entity_id: entity for entity in [*entities, *enriched_related]}
        return [combined[key] for key in sorted(combined)], [*assets, *related_assets]

    def _fetch(
        self,
        unique: list[str],
        batch_size: int,
        languages: list[str],
        site_languages: list[str],
        predicates: list[str],
        *,
        stage: str,
        checkpoint: EnrichmentCheckpoint | None,
    ) -> tuple[list[HistoricalEntity], list[RawAsset]]:
        entities: list[HistoricalEntity] = []
        assets: list[RawAsset] = []
        batches = _stable_batches(unique, batch_size)
        if checkpoint:
            checkpoint.begin_stage(stage, len(batches))
        for position, (batch_key, batch) in enumerate(batches.items(), start=1):
            params = {
                "action": "wbgetentities",
                "format": "json",
                "formatversion": "2",
                "ids": "|".join(batch),
                "props": "labels|descriptions|aliases|claims|sitelinks",
                "languages": "|".join(languages),
                "languagefallback": "1",
                "sitefilter": "|".join(f"{language}wiki" for language in site_languages),
                "redirects": "yes",
                "maxlag": "5",
            }
            request_url = str(httpx.URL(str(self.source.url)).copy_merge_params(params))
            request_id = hashlib.sha256(request_url.encode()).hexdigest()[:12]
            reusing = bool(checkpoint and checkpoint.should_resume(stage, batch_key))
            if checkpoint:
                checkpoint.batch_started(
                    stage,
                    batch_key,
                    position,
                    len(batches),
                    reusing=reusing,
                )
            asset = self.downloads.fetch(
                request_url,
                self.raw_source_dir / f"entities-{batch_key}-{request_id}.json",
                reuse_cached=reusing,
            )
            assets.append(asset)
            with asset.path.open("rb") as handle:
                payload = orjson.loads(handle.read())
            entities.extend(
                self._parse(payload, asset, languages, site_languages, predicates)
            )
            if checkpoint:
                checkpoint.batch_completed(stage, batch_key)
        if checkpoint:
            checkpoint.stage_completed(stage)
        return sorted(entities, key=lambda entity: entity.entity_id), assets

    def _parse(
        self,
        payload: dict[str, Any],
        asset: RawAsset,
        languages: list[str],
        site_languages: list[str],
        predicates: list[str],
    ) -> list[HistoricalEntity]:
        if payload.get("error"):
            raise ValueError(f"Wikidata API error: {payload['error']}")
        raw_entities = payload.get("entities")
        if not isinstance(raw_entities, dict):
            raise ValueError("Wikidata response has no entity mapping")
        redirects: dict[str, list[str]] = defaultdict(list)
        for redirect in payload.get("redirects") or []:
            if isinstance(redirect, dict) and redirect.get("from") and redirect.get("to"):
                redirects[str(redirect["to"])].append(str(redirect["from"]))

        entities: list[HistoricalEntity] = []
        for key, item in raw_entities.items():
            if not isinstance(item, dict) or item.get("missing"):
                continue
            qid = str(item.get("id") or key)
            if not QID.fullmatch(qid):
                continue
            raw_claims = item.get("claims")
            claims: dict[str, Any] = raw_claims if isinstance(raw_claims, dict) else {}
            names = _language_values(item.get("labels"), languages)
            descriptions = _language_values(item.get("descriptions"), languages)
            aliases = _aliases(item.get("aliases"), languages)
            relationships = _relationships(claims, predicates)
            date_claims = _date_claims(claims, predicates)
            type_ids = [
                relation.target_entity_id.removeprefix("wikidata:")
                for relation in relationships
                if relation.predicate == "P31"
            ]
            if set(type_ids) & WIKIMEDIA_NAVIGATION_ENTITY_TYPES:
                continue
            entity_type = next(
                (
                    ENTITY_TYPE_NAMES[type_id]
                    for type_id in type_ids
                    if type_id in ENTITY_TYPE_NAMES
                ),
                f"wikidata:{type_ids[0]}" if type_ids else "unknown",
            )
            sitelinks = _sitelinks(item.get("sitelinks"), site_languages)
            revision = item.get("lastrevid")
            item_url = HttpUrl(f"https://www.wikidata.org/wiki/{qid}")
            valid_from = _preferred_year(
                date_claims, {"P571", "P569", "P580", "P585"}
            )
            valid_to = _preferred_year(
                date_claims, {"P576", "P570", "P582", "P585"}
            )
            temporal_confidence = None
            if (
                valid_from is not None
                and valid_to is not None
                and valid_from > valid_to
            ):
                # Wikidata items can describe several physical incarnations or carry
                # mutually incompatible community claims. Never swap, average, or
                # silently select a continuous interval across those statements.
                valid_from = None
                valid_to = None
                temporal_confidence = Confidence(
                    grade=ConfidenceGrade.D,
                    rationale=(
                        "No convenience interval was derived because the selected "
                        "Wikidata start and end claims are contradictory; the original "
                        "dated statements remain available in date_claims."
                    ),
                )
            source_ref = SourceReference(
                source_id=self.source.id,
                record_id=qid,
                title=f"Wikidata item {qid}",
                publisher=self.source.publisher,
                url=item_url,
                license_id=self.source.license_id,
                retrieved_at=asset.retrieved_at,
                version=str(revision) if revision else self.source.version,
                checksum_sha256=asset.checksum_sha256,
                citation=self.source.citation,
            )
            entities.append(
                HistoricalEntity(
                    entity_id=f"wikidata:{qid}",
                    entity_type=entity_type,
                    names=names or {"und": qid},
                    aliases=aliases,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    temporal_confidence=temporal_confidence,
                    wikidata_id=qid,
                    descriptions=descriptions,
                    links={"wikidata": item_url},
                    sitelinks=sitelinks,
                    date_claims=date_claims,
                    relationships=relationships,
                    commons_images=_commons_images(claims, predicates),
                    commons_categories=_commons_categories(claims, predicates),
                    coordinates=_coordinates(claims, predicates),
                    redirects_from=sorted(set(redirects.get(qid, []))),
                    source_refs=[source_ref],
                )
            )
        return entities


def _stable_batches(qids: list[str], batch_size: int) -> dict[str, list[str]]:
    hash_buckets: dict[str, list[str]] = defaultdict(list)
    for qid in qids:
        bucket = hashlib.sha256(qid.encode("ascii")).hexdigest()[:2]
        hash_buckets[bucket].append(qid)
    buckets: dict[str, list[str]] = {}
    for bucket, values in sorted(hash_buckets.items()):
        ordered = sorted(values, key=_qid_number)
        for offset in range(0, len(ordered), batch_size):
            buckets[f"h{bucket}-{offset // batch_size:03d}"] = ordered[
                offset : offset + batch_size
            ]
    return dict(sorted(buckets.items()))


def _qid_number(qid: str) -> int:
    return int(qid[1:])


def _language_values(raw: Any, languages: list[str]) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    output: dict[str, str] = {}
    for language in languages:
        value = raw.get(language)
        if isinstance(value, dict) and value.get("value"):
            output[language] = str(value["value"])
    return output


def _aliases(raw: Any, languages: list[str]) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    output: dict[str, list[str]] = {}
    for language in languages:
        values = raw.get(language)
        if not isinstance(values, list):
            continue
        aliases = sorted(
            {
                str(value["value"])
                for value in values
                if isinstance(value, dict) and value.get("value")
            }
        )
        if aliases:
            output[language] = aliases
    return output


def _relationships(
    claims: dict[str, Any], predicates: list[str]
) -> list[EntityRelationship]:
    output: list[EntityRelationship] = []
    for predicate, relation_type in RELATION_PREDICATES.items():
        if predicate not in predicates:
            continue
        for claim in claims.get(predicate) or []:
            value = _claim_value(claim)
            target = value.get("id") if isinstance(value, dict) else None
            if isinstance(target, str) and QID.fullmatch(target):
                output.append(
                    EntityRelationship(
                        predicate=predicate,
                        relation_type=relation_type,
                        target_entity_id=f"wikidata:{target}",
                        rank=_rank(claim),
                        statement_id=_statement_id(claim),
                        qualifiers=_statement_qualifiers(claim),
                        references=_statement_references(claim),
                    )
                )
    return sorted(
        output,
        key=lambda relation: (
            relation.predicate,
            relation.target_entity_id,
            relation.rank,
        ),
    )


def _date_claims(claims: dict[str, Any], predicates: list[str]) -> list[EntityDateClaim]:
    output: list[EntityDateClaim] = []
    for predicate in DATE_PREDICATES:
        if predicate not in predicates:
            continue
        for claim in claims.get(predicate) or []:
            value = _claim_value(claim)
            if not isinstance(value, dict) or not value.get("time"):
                continue
            output.append(
                EntityDateClaim(
                    predicate=predicate,
                    time=str(value["time"]),
                    year=_time_year(str(value["time"])),
                    precision=value.get("precision"),
                    calendar_model=value.get("calendarmodel"),
                    before=int(value.get("before", 0)),
                    after=int(value.get("after", 0)),
                    rank=_rank(claim),
                    statement_id=_statement_id(claim),
                    qualifiers=_statement_qualifiers(claim),
                    references=_statement_references(claim),
                )
            )
    return output


def _claim_value(claim: Any) -> Any:
    if not isinstance(claim, dict):
        return None
    snak = claim.get("mainsnak")
    if not isinstance(snak, dict) or snak.get("snaktype") != "value":
        return None
    datavalue = snak.get("datavalue")
    return datavalue.get("value") if isinstance(datavalue, dict) else None


def _time_year(value: str) -> int | None:
    match = re.match(r"^([+-])(\d+)-", value)
    if not match:
        return None
    astronomical = int(match.group(2)) * (-1 if match.group(1) == "-" else 1)
    return astronomical - 1 if astronomical <= 0 else astronomical


def _preferred_year(claims: list[EntityDateClaim], predicates: set[str]) -> int | None:
    candidates = [claim for claim in claims if claim.predicate in predicates and claim.year]
    preferred = [claim for claim in candidates if claim.rank == "preferred"] or candidates
    return preferred[0].year if preferred else None


def _sitelinks(raw: Any, languages: list[str]) -> dict[str, WikipediaSitelink]:
    if not isinstance(raw, dict):
        return {}
    output: dict[str, WikipediaSitelink] = {}
    for language in languages:
        value = raw.get(f"{language}wiki")
        if not isinstance(value, dict) or not value.get("title"):
            continue
        title = str(value["title"])
        output[language] = WikipediaSitelink(
            language=language,
            title=title,
            url=HttpUrl(
                f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            ),
        )
    return output


def _commons_images(claims: dict[str, Any], predicates: list[str]) -> list[str]:
    if IMAGE_PREDICATE not in predicates:
        return []
    return sorted(
        {
            str(value)
            for claim in claims.get(IMAGE_PREDICATE) or []
            if isinstance((value := _claim_value(claim)), str)
        }
    )


def _commons_categories(claims: dict[str, Any], predicates: list[str]) -> list[str]:
    if COMMONS_CATEGORY_PREDICATE not in predicates:
        return []
    return sorted(
        {
            str(value)
            for claim in claims.get(COMMONS_CATEGORY_PREDICATE) or []
            if isinstance((value := _claim_value(claim)), str)
        }
    )


def _coordinates(
    claims: dict[str, Any], predicates: list[str]
) -> list[EntityCoordinate]:
    if COORDINATE_PREDICATE not in predicates:
        return []
    output: list[EntityCoordinate] = []
    for claim in claims.get(COORDINATE_PREDICATE) or []:
        value = _claim_value(claim)
        if not isinstance(value, dict):
            continue
        latitude = value.get("latitude")
        longitude = value.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(
            longitude, (int, float)
        ):
            continue
        output.append(
            EntityCoordinate(
                latitude=latitude,
                longitude=longitude,
                precision=value.get("precision"),
                globe=value.get("globe"),
                rank=_rank(claim),
            )
        )
    return output


def _statement_id(claim: Any) -> str | None:
    if not isinstance(claim, dict):
        return None
    value = claim.get("id")
    return str(value) if value else None


def _statement_qualifiers(claim: Any) -> list[WikidataSnak]:
    if not isinstance(claim, dict):
        return []
    qualifiers = claim.get("qualifiers")
    return _normalized_snaks(qualifiers if isinstance(qualifiers, dict) else {})


def _statement_references(claim: Any) -> list[WikidataReference]:
    if not isinstance(claim, dict):
        return []
    output: list[WikidataReference] = []
    for reference in claim.get("references") or []:
        if not isinstance(reference, dict):
            continue
        snaks = reference.get("snaks")
        output.append(
            WikidataReference(
                reference_hash=(
                    str(reference["hash"]) if reference.get("hash") else None
                ),
                snaks=_normalized_snaks(snaks if isinstance(snaks, dict) else {}),
            )
        )
    return output


def _normalized_snaks(snaks: dict[str, Any]) -> list[WikidataSnak]:
    output: list[WikidataSnak] = []
    for predicate, values in sorted(snaks.items()):
        if not re.fullmatch(r"P[1-9][0-9]*", predicate) or not isinstance(values, list):
            continue
        for snak in values:
            if not isinstance(snak, dict):
                continue
            datavalue = snak.get("datavalue")
            if not isinstance(datavalue, dict) or "value" not in datavalue:
                continue
            output.append(
                WikidataSnak(
                    predicate=predicate,
                    datatype=(str(snak["datatype"]) if snak.get("datatype") else None),
                    value=datavalue["value"],
                )
            )
    return output


def _select_expansion_qids(
    entities: list[HistoricalEntity],
    predicates: set[str],
    *,
    per_seed: int,
    total: int,
) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]]]:
    """Choose a deterministic, capped depth-one frontier without traversing type edges."""

    discovered_from: dict[str, set[str]] = defaultdict(set)
    discovery_predicates: dict[str, set[str]] = defaultdict(set)
    for entity in sorted(entities, key=lambda item: item.entity_id):
        seed_qid = entity.wikidata_id
        if not seed_qid:
            continue
        candidates = sorted(
            {
                (
                    relation.target_entity_id.removeprefix("wikidata:"),
                    relation.predicate,
                )
                for relation in entity.relationships
                if relation.predicate in predicates
            }
        )[:per_seed]
        for target_qid, predicate in candidates:
            discovered_from[target_qid].add(seed_qid)
            discovery_predicates[target_qid].add(predicate)
    selected = sorted(
        discovered_from,
        key=lambda qid: (-len(discovered_from[qid]), _qid_number(qid)),
    )[:total]
    selected_set = set(selected)
    return (
        selected,
        {qid: values for qid, values in discovered_from.items() if qid in selected_set},
        {
            qid: values
            for qid, values in discovery_predicates.items()
            if qid in selected_set
        },
    )


def _rank(claim: Any) -> Literal["preferred", "normal", "deprecated"]:
    value = claim.get("rank") if isinstance(claim, dict) else None
    return value if value in {"preferred", "normal", "deprecated"} else "normal"
