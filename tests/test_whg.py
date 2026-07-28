from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import orjson
import pytest

from history_pipeline.whg import (
    WHG_DATASET_ENTITY_URL,
    WHG_RECONCILE_URL,
    WHG_SCHEMA_URL,
    WhgSubject,
    acquire_whg_dataset_snapshot,
    acquire_whg_snapshot,
    local_env_value,
    select_whg_subjects,
    write_whg_review_sheet,
)


def test_local_env_value_reads_only_requested_key(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("OTHER=hidden\nWHG_API_TOKEN='safe-token'\n", encoding="utf-8")

    assert local_env_value(path, "WHG_API_TOKEN") == "safe-token"
    assert local_env_value(path, "MISSING") == ""


def test_select_whg_subjects_is_deterministic_and_prefers_authority_gaps(
    tmp_path: Path,
) -> None:
    path = tmp_path / "features.ndjson"
    features = [
        {
            "feature_id": "pleiades:eligible",
            "kind": "settlement",
            "names": {"und": "Eligible"},
            "valid_from": -50,
            "valid_to": 100,
            "geometry": {"type": "Point", "coordinates": [12.5, 41.9]},
            "wikidata_ids": [],
            "source_refs": [{"source_id": "pleiades"}],
        },
        {
            "feature_id": "pleiades:already-linked",
            "kind": "settlement",
            "names": {"und": "Linked"},
            "valid_from": -50,
            "valid_to": 100,
            "geometry": {"type": "Point", "coordinates": [12.5, 41.9]},
            "wikidata_ids": ["Q1"],
            "source_refs": [{"source_id": "pleiades"}],
        },
        {
            "feature_id": "other:record",
            "kind": "settlement",
            "names": {"und": "Other"},
            "valid_from": -50,
            "valid_to": 100,
            "geometry": {"type": "Point", "coordinates": [12.5, 41.9]},
            "wikidata_ids": [],
            "source_refs": [{"source_id": "other"}],
        },
        {
            "feature_id": "pleiades:catalogue-code",
            "kind": "archaeological_site",
            "names": {"und": "U549"},
            "valid_from": -50,
            "valid_to": 100,
            "geometry": {"type": "Point", "coordinates": [12.5, 41.9]},
            "wikidata_ids": [],
            "source_refs": [{"source_id": "pleiades"}],
        },
    ]
    path.write_bytes(b"\n".join(orjson.dumps(feature) for feature in features) + b"\n")

    subjects = select_whg_subjects(path, limit=10)

    assert [subject.subject_id for subject in subjects] == ["pleiades:eligible"]
    assert subjects[0].name == "Eligible"
    assert subjects[0].longitude == 12.5


def test_acquire_whg_snapshot_is_sanitized_and_keeps_results_proposed() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == WHG_RECONCILE_URL:
            return httpx.Response(
                200,
                json={
                    "query:one": {
                        "result": [
                            {
                                "id": "place:227721",
                                "name": "Patna",
                                "score": 100,
                                "match": False,
                                "alt_names": ["Pataliputra"],
                                "repr_point": [85.13, 25.59],
                            },
                            {
                                "id": "place:999",
                                "name": "Pataliputra",
                                "score": 100,
                                "match": True,
                                "repr_point": [-79.3, 43.7],
                            }
                        ],
                        "variants_used": [],
                    }
                },
            )
        if str(request.url) == WHG_SCHEMA_URL:
            return httpx.Response(
                200,
                json={"openapi": "3.0.3", "info": {"title": "WHG API", "version": "1.0.0"}},
            )
        if request.url.path == "/api/attribution/":
            return httpx.Response(
                200,
                json={
                    "sources": {"whg": {"name": "Specialist Gazetteers"}},
                    "whg": {"spdx_id": "CC-BY-NC-4.0"},
                },
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    subject = WhgSubject(
        query_id="query:one",
        subject_id="pleiades:one",
        name="Pataliputra",
        valid_from=-500,
        valid_to=500,
        longitude=85.1,
        latitude=25.6,
        kind="settlement",
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        snapshot = acquire_whg_snapshot(
            [subject],
            api_token="must-not-survive",
            user_agent="Palimpsest/test",
            namespaces=("whg", "wd"),
            retrieved_at=datetime(2026, 7, 26, tzinfo=UTC),
            client=client,
        )

    encoded = orjson.dumps(snapshot)
    assert b"must-not-survive" not in encoded
    [candidate] = snapshot["queries"][0]["result"]
    assert candidate["review_status"] == "proposed"
    assert candidate["relation"] == "candidate"
    assert candidate["provider_match"] is False
    assert candidate["distance_km"] < 50
    [discarded] = snapshot["queries"][0]["discarded_candidates"]
    assert discarded["reason"] == "outside_requested_radius"
    assert snapshot["rights"]["license_id"] == "CC-BY-NC-4.0"
    reconcile_request = requests[0]
    assert reconcile_request.headers["authorization"] == "Bearer must-not-survive"
    assert "fclasses" not in orjson.loads(reconcile_request.content)["queries"]["query:one"]


def test_acquire_whg_snapshot_requires_a_token() -> None:
    with pytest.raises(ValueError, match="WHG_API_TOKEN"):
        acquire_whg_snapshot(
            [
                WhgSubject(
                    query_id="query:one",
                    subject_id="subject:one",
                    name="Place",
                    valid_from=1,
                    valid_to=2,
                    longitude=0,
                    latitude=0,
                    kind="settlement",
                )
            ],
            api_token="",
            user_agent="Palimpsest/test",
            namespaces=("whg",),
        )


def test_acquire_whg_dataset_snapshot_is_bounded_and_sanitized() -> None:
    endpoint = WHG_DATASET_ENTITY_URL.format(dataset_id=693)

    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == endpoint
        assert request.headers["authorization"] == "Bearer must-not-survive"
        return httpx.Response(
            200,
            json={
                "@context": "https://example.org/lpf",
                "type": "FeatureCollection",
                "citation": {
                    "title": "Buddhist monasteries of the Western Ghats",
                    "DOI": "10.60681/whg-dataset-693",
                },
                "license": "CC BY-NC 4.0",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"title": "Bhaja", "src_id": "2"},
                        "geometry": {"type": "Point", "coordinates": [73.48, 18.73]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"title": "Ambivale", "src_id": "1"},
                        "geometry": {"type": "Point", "coordinates": [73.49, 19.01]},
                    },
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        snapshot = acquire_whg_dataset_snapshot(
            693,
            api_token="must-not-survive",
            user_agent="Palimpsest/test",
            limit=1,
            retrieved_at=datetime(2026, 7, 26, tzinfo=UTC),
            client=client,
        )

    assert [feature["properties"]["title"] for feature in snapshot["features"]] == [
        "Ambivale"
    ]
    audit = snapshot["_palimpsest_acquisition"]
    assert audit["provider_feature_count"] == 2
    assert audit["selected_feature_count"] == 1
    assert audit["endpoint"] == endpoint
    assert b"must-not-survive" not in orjson.dumps(snapshot)


def test_write_whg_review_sheet_keeps_decisions_blank(tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    write_whg_review_sheet(
        path,
        {
            "queries": [
                {
                    "query_id": "query:one",
                    "subject_id": "pleiades:one",
                    "subject": {
                        "name": "Pataliputra",
                        "valid_from": -500,
                        "valid_to": 500,
                    },
                    "result": [
                        {
                            "id": "place:227721",
                            "name": "Patna",
                            "authority_namespace": "whg",
                            "score": 100,
                            "distance_km": 1.2,
                            "provider_match": False,
                            "uri": "https://whgazetteer.org/entity/place:227721/",
                        }
                    ],
                }
            ]
        },
    )

    text = path.read_text(encoding="utf-8")
    assert "Pataliputra" in text
    assert "place:227721" in text
    assert "decision,relation,reviewer_note" in text.splitlines()[0]
    assert text.splitlines()[1].endswith(",,,")
