from __future__ import annotations

import csv
import hashlib
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import orjson

WHG_RECONCILE_URL = "https://whgazetteer.org/reconcile"
WHG_SCHEMA_URL = "https://whgazetteer.org/api/schema/?format=json"
WHG_ATTRIBUTION_URL = "https://whgazetteer.org/api/attribution/"
WHG_DATASET_ENTITY_URL = "https://whgazetteer.org/entity/dataset:{dataset_id}/api"
WHG_PROVIDER_FORMAT = "whg-reconciliation-v0.2"
WHG_PLATFORM_LICENSE = "CC-BY-NC-4.0"
WHG_PLATFORM_ATTRIBUTION = "World Historical Gazetteer"
_CATALOGUE_NAME = re.compile(r"^[A-Z]?\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class WhgSubject:
    query_id: str
    subject_id: str
    name: str
    valid_from: int
    valid_to: int
    longitude: float
    latitude: float
    kind: str


def local_env_value(path: Path, name: str) -> str:
    """Read one local secret without exporting or logging the rest of the file."""

    if not path.exists():
        return ""
    prefix = name + "="
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line.startswith(prefix):
                continue
            value = line.removeprefix(prefix).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value
    return ""


def select_whg_subjects(
    features_path: Path,
    *,
    limit: int,
    source_id: str = "pleiades",
    only_without_wikidata: bool = True,
) -> list[WhgSubject]:
    """Choose a deterministic, geographically varied reconciliation pilot."""

    if limit < 1:
        raise ValueError("WHG pilot limit must be positive")
    candidates: list[tuple[str, WhgSubject]] = []
    with features_path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            feature = orjson.loads(line)
            if feature.get("kind") not in {"settlement", "archaeological_site"}:
                continue
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict) or geometry.get("type") != "Point":
                continue
            coordinates = geometry.get("coordinates")
            if (
                not isinstance(coordinates, list)
                or len(coordinates) < 2
                or not all(isinstance(value, (int, float)) for value in coordinates[:2])
            ):
                continue
            source_ids = {
                reference.get("source_id")
                for reference in feature.get("source_refs", [])
                if isinstance(reference, dict)
            }
            if source_id not in source_ids:
                continue
            if only_without_wikidata and feature.get("wikidata_ids"):
                continue
            names = feature.get("names")
            if not isinstance(names, dict) or not names:
                continue
            name = str(
                names.get("en") or names.get("und") or next(iter(names.values()))
            ).strip()
            feature_id = str(feature.get("feature_id", "")).strip()
            alphabetic_count = sum(character.isalpha() for character in name)
            if (
                not name
                or not feature_id
                or name.casefold() in {"unknown", "unnamed", "untitled"}
                or (name.startswith("[") and name.endswith("]"))
                or _CATALOGUE_NAME.fullmatch(name)
                or alphabetic_count < 4
            ):
                continue
            subject = WhgSubject(
                query_id=f"query:{hashlib.sha256(feature_id.encode()).hexdigest()[:16]}",
                subject_id=feature_id,
                name=name,
                valid_from=int(feature["valid_from"]),
                valid_to=int(feature["valid_to"]),
                longitude=float(coordinates[0]),
                latitude=float(coordinates[1]),
                kind=str(feature["kind"]),
            )
            candidates.append((hashlib.sha256(feature_id.encode()).hexdigest(), subject))
    return [subject for _digest, subject in sorted(candidates)[:limit]]


def acquire_whg_snapshot(
    subjects: list[WhgSubject],
    *,
    api_token: str,
    user_agent: str,
    namespaces: tuple[str, ...],
    candidate_limit: int = 5,
    radius_km: float = 50,
    retrieved_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not subjects:
        raise ValueError("At least one WHG subject is required")
    if not api_token:
        raise ValueError("WHG_API_TOKEN is required")
    if not user_agent.strip():
        raise ValueError("A descriptive WHG user agent is required")
    if not namespaces:
        raise ValueError("At least one WHG authority namespace is required")
    if not 1 <= candidate_limit <= 25:
        raise ValueError("WHG candidate limit must be between 1 and 25")
    if not 0 < radius_km <= 500:
        raise ValueError("WHG radius must be greater than zero and at most 500 km")

    queries = {
        subject.query_id: {
            "query": subject.name,
            "mode": "fuzzy",
            "start": subject.valid_from,
            "end": subject.valid_to,
            "lat": subject.latitude,
            "lng": subject.longitude,
            "radius": radius_km,
            "namespaces": ",".join(namespaces),
            "undated": True,
            "unlocated": False,
            "size": candidate_limit,
        }
        for subject in subjects
    }
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
    }
    owns_client = client is None
    active_client = client or httpx.Client(timeout=180)
    try:
        response = active_client.post(
            WHG_RECONCILE_URL,
            headers=headers,
            json={"queries": queries},
        )
        response.raise_for_status()
        provider_response = response.json()
        schema_response = active_client.get(
            WHG_SCHEMA_URL,
            headers={"User-Agent": user_agent},
        )
        schema_response.raise_for_status()
        schema = schema_response.json()
        attribution_response = active_client.get(
            WHG_ATTRIBUTION_URL,
            headers={"User-Agent": user_agent},
            params={"namespaces": ",".join(namespaces)},
        )
        attribution_response.raise_for_status()
        attribution = attribution_response.json()
    finally:
        if owns_client:
            active_client.close()

    if not isinstance(provider_response, dict):
        raise ValueError("WHG reconciliation response must be an object")
    if not isinstance(schema, dict) or not isinstance(schema.get("info"), dict):
        raise ValueError("WHG schema response is malformed")
    if not isinstance(attribution, dict) or not isinstance(
        attribution.get("sources"), dict
    ):
        raise ValueError("WHG attribution response is malformed")

    schema_bytes = orjson.dumps(schema, option=orjson.OPT_SORT_KEYS)
    schema_version = str(schema["info"].get("version", "")).strip()
    if not schema_version:
        raise ValueError("WHG schema has no version")
    source_version = (
        f"whg-api-{schema_version}-schema-{hashlib.sha256(schema_bytes).hexdigest()[:12]}"
    )
    subject_by_query = {subject.query_id: subject for subject in subjects}
    snapshot_queries: list[dict[str, Any]] = []
    for query_id, subject in subject_by_query.items():
        raw_query_result = provider_response.get(query_id)
        if not isinstance(raw_query_result, dict):
            raise ValueError(f"WHG response omitted query {query_id}")
        raw_candidates = raw_query_result.get("result")
        if not isinstance(raw_candidates, list):
            raise ValueError(f"WHG query {query_id} has no result array")
        normalized_candidates: list[dict[str, Any]] = []
        discarded_candidates: list[dict[str, Any]] = []
        for candidate in raw_candidates:
            if not isinstance(candidate, dict):
                raise ValueError(f"WHG query {query_id} returned a malformed candidate")
            authority_id = str(candidate.get("id", "")).strip()
            label = str(candidate.get("name", "")).strip()
            score = candidate.get("score")
            if (
                not authority_id.startswith("place:")
                or not label
                or not isinstance(score, (int, float))
            ):
                raise ValueError(f"WHG query {query_id} returned an incomplete candidate")
            point = candidate.get("repr_point")
            if (
                not isinstance(point, list)
                or len(point) < 2
                or not all(isinstance(value, (int, float)) for value in point[:2])
            ):
                discarded_candidates.append(
                    {
                        "reason": "missing_representative_point",
                        "provider_candidate": candidate,
                    }
                )
                continue
            distance_km = _haversine_km(
                subject.longitude,
                subject.latitude,
                float(point[0]),
                float(point[1]),
            )
            if distance_km > radius_km:
                discarded_candidates.append(
                    {
                        "reason": "outside_requested_radius",
                        "distance_km": round(distance_km, 3),
                        "provider_candidate": candidate,
                    }
                )
                continue
            parts = authority_id.split(":")
            authority_namespace = parts[1] if len(parts) > 2 else "whg"
            if authority_namespace not in namespaces:
                discarded_candidates.append(
                    {
                        "reason": "outside_namespace_allowlist",
                        "provider_candidate": candidate,
                    }
                )
                continue
            normalized_candidates.append(
                {
                    "id": authority_id,
                    "uri": f"https://whgazetteer.org/entity/{authority_id}/",
                    "name": label,
                    "authority_namespace": authority_namespace,
                    "score": float(score),
                    "distance_km": round(distance_km, 3),
                    "review_status": "proposed",
                    "relation": "candidate",
                    "provider_match": bool(candidate.get("match", False)),
                    "provider_candidate": candidate,
                }
            )
        snapshot_queries.append(
            {
                "query_id": query_id,
                "subject_id": subject.subject_id,
                "subject": asdict(subject),
                "request": queries[query_id],
                "result": normalized_candidates,
                "discarded_candidates": discarded_candidates,
                "provider_variants_used": raw_query_result.get("variants_used", []),
            }
        )

    generated_at = retrieved_at or datetime.now(UTC)
    return {
        "source_version": source_version,
        "provider_format": WHG_PROVIDER_FORMAT,
        "score_scale": "0-100",
        "retrieved_at": generated_at.isoformat().replace("+00:00", "Z"),
        "endpoint": WHG_RECONCILE_URL,
        "schema": {
            "url": WHG_SCHEMA_URL,
            "version": schema_version,
            "checksum_sha256": hashlib.sha256(schema_bytes).hexdigest(),
        },
        "rights": {
            "license_id": WHG_PLATFORM_LICENSE,
            "attribution": WHG_PLATFORM_ATTRIBUTION,
        },
        "namespaces": list(namespaces),
        "attribution": attribution,
        "queries": snapshot_queries,
    }


def acquire_whg_dataset_snapshot(
    dataset_id: int,
    *,
    api_token: str,
    user_agent: str,
    limit: int | None = None,
    retrieved_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch a bounded WHG dataset Entity API response without serializing credentials."""

    if dataset_id < 1:
        raise ValueError("WHG dataset ID must be positive")
    if not api_token:
        raise ValueError("WHG_API_TOKEN is required")
    if not user_agent.strip():
        raise ValueError("A descriptive WHG user agent is required")
    if limit is not None and not 1 <= limit <= 1000:
        raise ValueError("WHG dataset preview limit must be between 1 and 1000")

    endpoint = WHG_DATASET_ENTITY_URL.format(dataset_id=dataset_id)
    owns_client = client is None
    active_client = client or httpx.Client(timeout=180)
    try:
        response = active_client.get(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/geo+json, application/ld+json, application/json",
                "User-Agent": user_agent,
            },
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            active_client.close()

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError("WHG dataset entity must be a FeatureCollection")
    features = payload.get("features")
    citation = payload.get("citation")
    license_notice = payload.get("license")
    if not isinstance(features, list) or not all(
        isinstance(feature, dict) for feature in features
    ):
        raise ValueError("WHG dataset entity has a malformed features array")
    if not isinstance(citation, dict) or not str(citation.get("title", "")).strip():
        raise ValueError("WHG dataset entity has no usable citation")
    if not isinstance(license_notice, str) or not license_notice.strip():
        raise ValueError("WHG dataset entity has no licence notice")

    provider_bytes = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    selected = sorted(
        features,
        key=lambda feature: (
            str((feature.get("properties") or {}).get("title", "")).casefold(),
            str(
                feature.get("@id")
                or feature.get("id")
                or (feature.get("properties") or {}).get("src_id", "")
            ),
        ),
    )
    if limit is not None:
        selected = selected[:limit]
    generated_at = retrieved_at or datetime.now(UTC)
    return {
        "@context": payload.get("@context"),
        "type": "FeatureCollection",
        "citation": citation,
        "license": license_notice,
        "_palimpsest_acquisition": {
            "schema_version": "1.0.0",
            "dataset_id": dataset_id,
            "endpoint": endpoint,
            "retrieved_at": generated_at.isoformat().replace("+00:00", "Z"),
            "provider_feature_count": len(features),
            "selected_feature_count": len(selected),
            "provider_checksum_sha256": hashlib.sha256(provider_bytes).hexdigest(),
            "selection": (
                "all features"
                if limit is None
                else f"first {limit} records sorted by title and source ID"
            ),
        },
        "features": selected,
    }


def _haversine_km(
    longitude_a: float,
    latitude_a: float,
    longitude_b: float,
    latitude_b: float,
) -> float:
    radius = 6371.0088
    latitude_a_radians = math.radians(latitude_a)
    latitude_b_radians = math.radians(latitude_b)
    latitude_delta = latitude_b_radians - latitude_a_radians
    longitude_delta = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_a_radians)
        * math.cos(latitude_b_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(haversine))


def write_whg_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(
        orjson.dumps(snapshot, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"
    )
    temporary.replace(path)


def write_whg_review_sheet(path: Path, snapshot: dict[str, Any]) -> None:
    """Write an editable candidate table without changing the evidence snapshot."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fieldnames = [
        "query_id",
        "subject_id",
        "subject_name",
        "valid_from",
        "valid_to",
        "candidate_id",
        "candidate_name",
        "authority_namespace",
        "score",
        "distance_km",
        "provider_match",
        "candidate_url",
        "decision",
        "relation",
        "reviewer_note",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for query in snapshot.get("queries", []):
            subject = query["subject"]
            for candidate in query["result"]:
                writer.writerow(
                    {
                        "query_id": query["query_id"],
                        "subject_id": query["subject_id"],
                        "subject_name": subject["name"],
                        "valid_from": subject["valid_from"],
                        "valid_to": subject["valid_to"],
                        "candidate_id": candidate["id"],
                        "candidate_name": candidate["name"],
                        "authority_namespace": candidate["authority_namespace"],
                        "score": candidate["score"],
                        "distance_km": candidate["distance_km"],
                        "provider_match": str(candidate["provider_match"]).lower(),
                        "candidate_url": candidate["uri"],
                        "decision": "",
                        "relation": "",
                        "reviewer_note": "",
                    }
                )
    temporary.replace(path)
