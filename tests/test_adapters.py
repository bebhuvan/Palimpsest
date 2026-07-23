from __future__ import annotations

import gzip
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from history_pipeline.adapters.base import AdapterContext
from history_pipeline.adapters.cliopatria import CliopatriaAdapter
from history_pipeline.adapters.curated import CuratedSourceAdapter
from history_pipeline.adapters.linked_places import LinkedPlacesAdapter
from history_pipeline.adapters.open_context import OpenContextAdapter
from history_pipeline.adapters.owid import OwidAdapter
from history_pipeline.adapters.periodo import PeriodoAdapter
from history_pipeline.adapters.pleiades import PleiadesAdapter
from history_pipeline.adapters.wikidata import WikidataEnricher
from history_pipeline.adapters.wikipedia import WikipediaEnricher
from history_pipeline.config import PipelineConfig, SourceConfig
from history_pipeline.storage import DownloadCache


def _config(source: SourceConfig, tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        raw_dir=tmp_path / "raw",
        staged_dir=tmp_path / "staged",
        cache_dir=tmp_path / "cache",
        dist_dir=tmp_path / "dist",
        sources=[source],
        license_policy={"allowed": [source.license_id]},
    )


def _context(source: SourceConfig, tmp_path: Path) -> AdapterContext:
    config = _config(source, tmp_path)
    downloads = DownloadCache(config.cache_dir, "HistoryJoice/test")
    return AdapterContext(
        pipeline=config,
        source=source,
        downloads=downloads,
        raw_source_dir=config.raw_dir / source.id,
        staged_source_dir=config.staged_dir / source.id,
    )


def test_curated_adapter_snapshots_and_pins_authority_record(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    import hashlib

    payload = b'{"item":{"id":"92516339"}}'
    source = SourceConfig.model_validate(
        {
            "id": "curated-record",
            "adapter": "curated",
            "title": "Curated authority record",
            "publisher": "Example archive",
            "url": "https://example.org/record.json",
            "license_id": "PDM-1.0",
            "citation": "Example archive record",
            "expected_checksum_sha256": hashlib.sha256(payload).hexdigest(),
            "options": {"snapshot_filename": "catalog.json"},
        }
    )
    httpx_mock.add_response(url=str(source.url), content=payload)
    context = _context(source, tmp_path)
    try:
        result = CuratedSourceAdapter().run(context)
    finally:
        context.downloads.close()

    assert result.raw_assets[0].path.read_bytes() == payload
    assert result.raw_assets[0].checksum_sha256 == source.expected_checksum_sha256


def test_cliopatria_adapter_normalizes_and_rejects_bad_chronology(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "cliopatria",
            "adapter": "cliopatria",
            "title": "Cliopatria",
            "publisher": "Seshat",
            "url": "https://example.org/cliopatria.zip",
            "license_id": "CC-BY-4.0",
            "citation": "Citation",
            "member_name": "cliopatria_polities_only.geojson",
            "defaults": {
                "kind": "polity",
                "spatial_meaning": "territorial_control",
                "date_precision": "range",
                "temporal_confidence": "C",
                "spatial_confidence": "C",
                "interpretive_confidence": "C",
            },
        }
    )
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                },
                "properties": {
                    "Name": "Example",
                    "FromYear": -100,
                    "ToYear": 100,
                    "Area": 1,
                    "Type": "POLITY",
                    "Wikipedia": "Example",
                    "Wikidata": "Q1",
                    "SeshatID": "",
                    "Components": "",
                    "MemberOf": "",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"Name": "Bad", "FromYear": 0, "ToYear": 1},
            },
        ],
    }
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("cliopatria_polities_only.geojson", json.dumps(collection))
    httpx_mock.add_response(url=str(source.url), content=archive.getvalue())
    context = _context(source, tmp_path)
    try:
        result = CliopatriaAdapter().run(context)
    finally:
        context.downloads.close()
    assert len(result.features) == 1
    assert result.features[0].wikidata_ids == ["Q1"]
    assert len(result.rejections) == 1
    assert "year zero" in result.rejections[0].reason


def test_pleiades_adapter_requires_dated_place(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "pleiades",
            "adapter": "pleiades",
            "title": "Pleiades",
            "publisher": "ISAW",
            "url": "https://example.org/pleiades.json.gz",
            "license_id": "CC-BY-3.0",
            "citation": "Citation",
        }
    )
    payload = [
        {
            "id": "1",
            "title": "Dated place",
            "reprPoint": [10, 20],
            "names": [{"romanized": "Dated place", "language": "en", "start": -10, "end": 10}],
            "locations": [],
            "connections": [],
            "placeTypes": ["settlement"],
            "uri": "https://pleiades.stoa.org/places/1",
        },
        {"id": "2", "title": "Undated place", "reprPoint": [10, 20]},
    ]
    httpx_mock.add_response(
        url=str(source.url), content=gzip.compress(json.dumps(payload).encode())
    )
    context = _context(source, tmp_path)
    try:
        result = PleiadesAdapter().run(context)
    finally:
        context.downloads.close()
    assert [feature.names["en"] for feature in result.features] == ["Dated place"]
    assert len(result.rejections) == 1


def test_pleiades_does_not_fill_gaps_between_attestations() -> None:
    place = {
        "locations": [
            {"start": -100, "end": -50},
            {"start": 50, "end": 100},
        ]
    }

    assert PleiadesAdapter._date_ranges(place, {}) == [(-100, -50), (50, 100)]


def test_pleiades_adapter_reads_numbered_release_without_extracting(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "pleiades",
            "adapter": "pleiades",
            "title": "Pleiades",
            "publisher": "ISAW",
            "url": "https://example.org/v1.tar.gz",
            "license_id": "CC-BY-3.0",
            "citation": "Citation",
            "options": {"archive_format": "tar.gz"},
        }
    )
    place = {
        "id": "1",
        "title": "Dated place",
        "reprPoint": [10, 20],
        "names": [{"romanized": "Dated place", "language": "en", "start": -10, "end": 10}],
        "references": [
            {"accessURI": "https://www.wikidata.org/wiki/Q123"},
            {"accessURI": "https://fr.wikipedia.org/wiki/Lieu_test"},
        ],
        "placeTypes": ["settlement"],
    }
    archive = io.BytesIO()
    encoded = json.dumps(place).encode()
    with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
        periods = (
            b"key,term,definition,lower_bound,upper_bound,same_as\n"
            b"example,Example,\"[[-10,10]]\",,,\n"
        )
        period_info = tarfile.TarInfo(
            "pleiades.datasets-1/data/gis/time_periods.csv"
        )
        period_info.size = len(periods)
        bundle.addfile(period_info, io.BytesIO(periods))
        info = tarfile.TarInfo("pleiades.datasets-1/data/json/1/1.json")
        info.size = len(encoded)
        bundle.addfile(info, io.BytesIO(encoded))
        hostile = tarfile.TarInfo("../../not-a-place.json")
        hostile.size = 2
        bundle.addfile(hostile, io.BytesIO(b"{}"))
    httpx_mock.add_response(url=str(source.url), content=archive.getvalue())
    context = _context(source, tmp_path)
    try:
        result = PleiadesAdapter().run(context)
    finally:
        context.downloads.close()
    assert len(result.features) == 1
    assert result.features[0].wikidata_ids == ["Q123"]
    assert result.features[0].wikipedia_titles == {"fr": "Lieu test"}


def test_periodo_adapter_preserves_competing_definition_and_authority(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    payload = {
        "authorities": {
            "p0auth": {
                "id": "p0auth",
                "source": {
                    "citation": "Historian. Example chronology. 2020.",
                    "creators": [{"name": "Historian"}],
                },
                "periods": {
                    "p0authabc": {
                        "id": "p0authabc",
                        "label": "Example age",
                        "languageTag": "en",
                        "localizedLabels": {"en": ["Example age"], "fr": ["Âge exemple"]},
                        "start": {"in": {"year": "-100"}, "label": "ca. 100 BCE"},
                        "stop": {"in": {"year": "100"}, "label": "ca. 100 CE"},
                        "spatialCoverage": [
                            {"id": "http://www.wikidata.org/entity/Q42", "label": "Example"}
                        ],
                        "note": "One scholarly periodization.",
                    }
                },
            }
        }
    }
    encoded = json.dumps(payload).encode()
    import hashlib

    source = SourceConfig.model_validate(
        {
            "id": "periodo",
            "adapter": "periodo",
            "title": "PeriodO",
            "publisher": "PeriodO",
            "url": "https://example.org/periodo.json",
            "license_id": "CC0-1.0",
            "citation": "PeriodO citation",
            "expected_checksum_sha256": hashlib.sha256(encoded).hexdigest(),
        }
    )
    httpx_mock.add_response(url=str(source.url), content=encoded)
    context = _context(source, tmp_path)
    try:
        result = PeriodoAdapter().run(context)
    finally:
        context.downloads.close()
    assert not result.rejections
    period = result.periods[0]
    assert period.period_id == "periodo:p0authabc"
    assert period.labels["fr"] == ["Âge exemple"]
    assert period.spatial_coverage[0].entity_id == "wikidata:Q42"
    assert period.authority_citation == "Historian. Example chronology. 2020."


def test_periodo_adapter_fails_closed_when_reviewed_payload_changes(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "periodo",
            "adapter": "periodo",
            "title": "PeriodO",
            "publisher": "PeriodO",
            "url": "https://example.org/periodo.json",
            "license_id": "CC0-1.0",
            "citation": "PeriodO citation",
            "expected_checksum_sha256": "a" * 64,
        }
    )
    httpx_mock.add_response(url=str(source.url), json={"authorities": {}})
    context = _context(source, tmp_path)
    try:
        with pytest.raises(ValueError, match="checksum changed"):
            PeriodoAdapter().run(context)
    finally:
        context.downloads.close()


def test_open_context_generalizes_coordinates_and_converts_iso_year(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "open-context",
            "adapter": "open_context",
            "title": "Open Context",
            "publisher": "Open Context",
            "url": "https://opencontext.org/query/",
            "license_id": "CC-BY-4.0",
            "citation": "Citation",
            "defaults": {
                "kind": "archaeological_site",
                "spatial_meaning": "location",
                "date_precision": "range",
                "temporal_confidence": "B",
                "spatial_confidence": "C",
                "interpretive_confidence": "B",
            },
            "options": {
                "queries": ["https://opencontext.org/query/?proj=test"],
                "max_records": 10,
                "public_coordinate_decimals": 3,
            },
        }
    )
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "#1",
                "label": "Site",
                "rdfs:isDefinedBy": "https://opencontext.org/subjects/1",
                "oc-api:human-remains-related": False,
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [12.34567, 23.45678]},
                "when": {"start": "0", "stop": "10"},
                "properties": {"href": "https://opencontext.org/subjects/1"},
            }
        ],
    }
    httpx_mock.add_response(content=json.dumps(payload).encode())
    context = _context(source, tmp_path)
    try:
        result = OpenContextAdapter().run(context)
    finally:
        context.downloads.close()
    feature = result.features[0]
    assert feature.valid_from == -1
    assert feature.geometry["coordinates"] == (12.346, 23.457)


def test_owid_adapter_reads_current_grapher_metadata_shape(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "owid-population",
            "adapter": "owid",
            "title": "Population",
            "publisher": "Our World in Data",
            "url": "https://ourworldindata.org/grapher/population",
            "license_id": "CC-BY-4.0",
            "citation": "Citation",
            "indicator_slug": "population",
        }
    )
    csv_url = (
        "https://ourworldindata.org/grapher/population.csv"
        "?v=1&csvType=full&useColumnShortNames=true"
    )
    metadata_url = (
        "https://ourworldindata.org/grapher/population.metadata.json"
        "?v=1&csvType=full&useColumnShortNames=true"
    )
    httpx_mock.add_response(
        url=csv_url,
        text="entity,code,year,population_historical\nExample,EXA,-100,1234\n",
    )
    httpx_mock.add_response(
        url=metadata_url,
        json={"columns": {"population_historical": {"unit": "people", "shortUnit": ""}}},
    )
    context = _context(source, tmp_path)
    try:
        result = OwidAdapter().run(context)
    finally:
        context.downloads.close()
    assert len(result.indicators) == 1
    assert result.indicators[0].unit == "people"
    assert result.indicators[0].value == 1234


def test_wikimedia_enrichment_is_snapshotted_and_rebuilds_offline(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    wikidata = SourceConfig.model_validate(
        {
            "id": "wikidata",
            "adapter": "wikidata",
            "title": "Wikidata",
            "publisher": "Wikimedia",
            "url": "https://www.wikidata.org/w/api.php",
            "license_id": "CC0-1.0",
            "citation": "Citation",
            "options": {"languages": ["en"]},
        }
    )
    wikipedia = SourceConfig.model_validate(
        {
            "id": "wikipedia",
            "adapter": "wikipedia",
            "title": "Wikipedia",
            "publisher": "Wikimedia",
            "url": "https://en.wikipedia.org/w/api.php",
            "license_id": "CC-BY-SA-4.0",
            "citation": "Citation",
        }
    )
    httpx_mock.add_response(
        json={
            "entities": {
                "Q1": {
                    "id": "Q1",
                    "lastrevid": 42,
                    "labels": {"en": {"language": "en", "value": "Universe"}},
                    "descriptions": {
                        "en": {"language": "en", "value": "totality of existence"}
                    },
                    "aliases": {
                        "en": [{"language": "en", "value": "the universe"}]
                    },
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {
                                    "snaktype": "value",
                                    "datavalue": {"value": {"id": "Q6256"}},
                                },
                            }
                        ],
                        "P571": [
                            {
                                "id": "Q1$inception",
                                "rank": "preferred",
                                "mainsnak": {
                                    "snaktype": "value",
                                    "datavalue": {
                                        "value": {
                                            "time": "+1900-00-00T00:00:00Z",
                                            "precision": 9,
                                            "before": 0,
                                            "after": 0,
                                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                        }
                                    },
                                },
                                "references": [
                                    {
                                        "hash": "source-hash",
                                        "snaks": {
                                            "P248": [
                                                {
                                                    "datatype": "wikibase-item",
                                                    "datavalue": {"value": {"id": "Q99"}},
                                                }
                                            ]
                                        },
                                    }
                                ],
                            }
                        ],
                        "P18": [
                            {
                                "mainsnak": {
                                    "snaktype": "value",
                                    "datavalue": {"value": "Universe.jpg"},
                                }
                            }
                        ],
                    },
                    "sitelinks": {"enwiki": {"site": "enwiki", "title": "Universe"}},
                }
            },
            "redirects": [{"from": "Q999", "to": "Q1"}],
        }
    )
    httpx_mock.add_response(
        json={
            "query": {
                "redirects": [{"from": "The Universe", "to": "Universe"}],
                "pages": [
                    {
                        "pageid": 1,
                        "title": "Universe",
                        "extract": "An introductory extract.",
                        "fullurl": "https://en.wikipedia.org/wiki/Universe",
                        "revisions": [{"revid": 2, "timestamp": "2026-01-01T00:00:00Z"}],
                    }
                ]
            }
        }
    )
    cache_dir = tmp_path / "cache"
    with DownloadCache(cache_dir, "HistoryJoice/test") as downloads:
        entities, wikidata_assets = WikidataEnricher(
            wikidata, downloads, tmp_path / "raw" / "wikidata"
        ).enrich(["Q1", "Q1"])
        dossiers, wikipedia_assets = WikipediaEnricher(
            wikipedia, downloads, tmp_path / "raw" / "wikipedia"
        ).enrich(["The Universe"], entity_ids_by_title={"The Universe": ["wikidata:Q1"]})

    assert entities[0].names == {"en": "Universe"}
    assert entities[0].aliases == {"en": ["the universe"]}
    assert entities[0].valid_from == 1900
    assert entities[0].date_claims[0].statement_id == "Q1$inception"
    assert entities[0].date_claims[0].references[0].reference_hash == "source-hash"
    assert entities[0].relationships[0].target_entity_id == "wikidata:Q6256"
    assert entities[0].sitelinks["en"].title == "Universe"
    assert entities[0].commons_images == ["Universe.jpg"]
    assert entities[0].source_refs[0].checksum_sha256 == wikidata_assets[0].checksum_sha256
    assert dossiers[0].source_ref.checksum_sha256 == wikipedia_assets[0].checksum_sha256
    assert dossiers[0].entity_ids == ["wikidata:Q1"]
    assert dossiers[0].redirects_from == ["The Universe"]
    assert dossiers[0].dossier_id == "wikipedia:en:1"

    with DownloadCache(cache_dir, "HistoryJoice/test", offline=True) as downloads:
        offline_entities, _ = WikidataEnricher(
            wikidata, downloads, tmp_path / "raw" / "wikidata"
        ).enrich(["Q1"])
        offline_dossiers, _ = WikipediaEnricher(
            wikipedia, downloads, tmp_path / "raw" / "wikipedia"
        ).enrich(
            ["The Universe"],
            entity_ids_by_title={"The Universe": ["wikidata:Q1"]},
        )
    assert offline_entities == entities
    assert offline_dossiers == dossiers


def test_linked_places_requires_chronology_and_preserves_names(
    tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    source = SourceConfig.model_validate(
        {
            "id": "linked-places",
            "adapter": "linked_places",
            "title": "Reviewed places",
            "publisher": "Example publisher",
            "url": "https://example.org/places.json",
            "license_id": "CC-BY-4.0",
            "citation": "Citation",
            "defaults": {
                "kind": "settlement",
                "spatial_meaning": "location",
                "date_precision": "range",
                "temporal_confidence": "B",
                "spatial_confidence": "B",
                "interpretive_confidence": "B",
            },
            "options": {"chronology": "astronomical"},
        }
    )
    httpx_mock.add_response(
        json={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "@id": "https://example.org/place/1",
                    "properties": {"title": "Example place"},
                    "geometry": {"type": "Point", "coordinates": [10, 20]},
                    "names": [{"toponym": "Exemplum", "lang": "la"}],
                    "when": {
                        "timespans": [
                            {"start": {"earliest": "0"}, "end": {"latest": "100"}}
                        ]
                    },
                }
            ],
        }
    )
    context = _context(source, tmp_path)
    try:
        result = LinkedPlacesAdapter().run(context)
    finally:
        context.downloads.close()

    assert result.features[0].valid_from == -1
    assert result.features[0].names == {"und": "Example place", "la": "Exemplum"}
