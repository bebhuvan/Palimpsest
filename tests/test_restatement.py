from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx
import orjson
import pytest

from history_pipeline.artifacts import build_artifacts, content_shard
from history_pipeline.models import (
    DossierRestatementContent,
    HistoricalDossier,
    SourceReference,
)
from history_pipeline.restatement import (
    RestatementRejected,
    build_common_words,
    build_restatement,
    closed_world_report,
    common_words,
    completed_source_checksums,
    generate_with_openai,
    pending_dossiers,
    validate_restatement,
)

SOURCE = (
    "Sirkap is the name of an archaeological site on the bank opposite to the city of Taxila, "
    "Punjab, Pakistan.\n"
    "The city of Sirkap was built by the Greco-Bactrian king Demetrius after he invaded "
    "modern-day Pakistan around 180 BC. Demetrius founded an Indo-Greek kingdom that was to last "
    "until around 10 BC. Sirkap is also said to have been rebuilt by king Menander I."
)

GENERATED = {
    "prompt_version": "dossier-restate-v1",
    "prompt_sha256": "a" * 64,
    "model_identifier": "fixture:test",
    "generated_at": datetime(2026, 7, 25, tzinfo=UTC),
}


def dossier(extract: str = SOURCE, *, revision_id: int = 42) -> HistoricalDossier:
    return HistoricalDossier(
        dossier_id="wikipedia:en:1001103",
        title="Sirkap",
        language="en",
        entity_ids=["wikidata:Q1"],
        extract=extract,
        url="https://en.wikipedia.org/wiki/Sirkap",
        page_id=1001103,
        revision_id=revision_id,
        content_checksum_sha256=hashlib.sha256(extract.encode("utf-8")).hexdigest(),
        source_ref=SourceReference(
            source_id="wikipedia",
            record_id="1001103",
            title="Sirkap",
            publisher="Wikimedia Foundation",
            url="https://en.wikipedia.org/wiki/Sirkap",
            license_id="CC-BY-SA-4.0",
            retrieved_at=datetime(2026, 7, 1, tzinfo=UTC),
            citation="Sirkap, English Wikipedia",
        ),
    )


def content(**overrides: object) -> DossierRestatementContent:
    payload: dict[str, object] = {
        "result": "restated",
        "headline": "A city built by a Greco-Bactrian king across the river from Taxila",
        "text": (
            "Sirkap is an archaeological site on the bank opposite Taxila, in Punjab, Pakistan.\n"
            "The Greco-Bactrian king Demetrius built the city after invading the region around "
            "180 BC. He founded an Indo-Greek kingdom that was to last until around 10 BC."
        ),
        "timeline": [
            {
                "year_text": "around 180 BC",
                "sort_year": -180,
                "text": "Demetrius built the city",
            },
            {"year_text": "around 10 BC", "sort_year": -10, "text": "The kingdom ended"},
        ],
        "unsuitable_reason": None,
    }
    payload.update(overrides)
    return DossierRestatementContent.model_validate(payload)


def test_faithful_restatement_is_accepted() -> None:
    restatement = build_restatement(content(), dossier(), **GENERATED)

    assert restatement.restatement_id.startswith("restatement:")
    assert restatement.dossier_id == "wikipedia:en:1001103"
    assert restatement.content_role == "source_restatement"
    assert restatement.dossier_kind == "restatement"
    assert restatement.source_revision_id == 42
    assert restatement.entity_ids == ["wikidata:Q1"]
    assert restatement.validation.restatement_chars < restatement.validation.source_chars


def test_restatement_id_is_content_addressed() -> None:
    first = build_restatement(content(), dossier(), **GENERATED)
    same = build_restatement(content(), dossier(), **GENERATED)
    different = build_restatement(
        content(headline="A city across the river from Taxila"), dossier(), **GENERATED
    )

    assert first.restatement_id == same.restatement_id
    assert first.restatement_id != different.restatement_id


def test_invented_number_is_rejected() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(text="Demetrius built Sirkap in 184 BC, opposite Taxila."),
            dossier(),
            **GENERATED,
        )

    assert error.value.report["unsupported_numbers"] == ["184"]


def test_derived_century_is_rejected() -> None:
    """A century computed from a source year is a new claim, not a restatement."""

    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(text="Demetrius built Sirkap in the 2nd century BC, opposite Taxila."),
            dossier(),
            **GENERATED,
        )

    assert "2" in error.value.report["unsupported_numbers"]


def test_invented_proper_noun_is_rejected() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(text="Sirkap was a centre of Gandharan culture opposite Taxila."),
            dossier(),
            **GENERATED,
        )

    assert error.value.report["unsupported_names"] == ["Gandharan"]


def test_register_the_source_itself_uses_is_not_a_violation() -> None:
    """Wikipedia writes "played a pivotal role" in its own voice. Carrying it across is faithful."""

    source = (
        "The Medes established an empire in the 7th century BC that lasted until the 550s BC, "
        "played a pivotal role in the fall of the Assyrian Empire, and competed with Lydia."
    )
    report = closed_world_report(
        content(
            headline="An empire that helped end Assyria",
            text=(
                "The Medes established an empire in the 7th century BC. It played a pivotal role "
                "in the fall of the Assyrian Empire and competed with Lydia."
            ),
            timeline=[],
        ),
        source,
    )

    assert not report["denied_phrases"]


def test_generated_register_is_rejected() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(
                text=(
                    "Sirkap stands as a testament to the vibrant Greco-Bactrian kingdom "
                    "opposite Taxila."
                )
            ),
            dossier(),
            **GENERATED,
        )

    assert "stands as a testament" in error.value.report["denied_phrases"]
    assert "vibrant" in error.value.report["denied_phrases"]


def test_deferring_opening_is_rejected() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(text="Located in Punjab, Sirkap is an archaeological site opposite Taxila."),
            dossier(),
            **GENERATED,
        )

    assert "opening:located in" in error.value.report["denied_phrases"]


def test_restatement_longer_than_its_source_is_rejected() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(content(), dossier(extract=SOURCE[:120]), **GENERATED)

    assert "length" in error.value.report


def test_timeline_entries_stay_inside_the_source() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(
                timeline=[
                    {"year_text": "155 BC", "sort_year": -155, "text": "Menander I took the city"}
                ]
            ),
            dossier(),
            **GENERATED,
        )

    assert error.value.report["unsupported_numbers"] == ["155"]


def test_narrative_order_is_normalised_to_chronological_order() -> None:
    """Listing events as the source narrates them is not an evidence error, so it is not fatal."""

    normalised = content(
        timeline=[
            {"year_text": "around 10 BC", "sort_year": -10, "text": "The kingdom ended"},
            {"year_text": "around 180 BC", "sort_year": -180, "text": "Demetrius built it"},
        ]
    )

    assert [entry.sort_year for entry in normalised.timeline] == [-180, -10]


def test_unsuitable_source_produces_no_restatement() -> None:
    with pytest.raises(RestatementRejected) as error:
        build_restatement(
            content(
                result="unsuitable",
                headline=None,
                text=None,
                timeline=[],
                unsuitable_reason="The source is a present-day administrative division.",
            ),
            dossier(),
            **GENERATED,
        )

    assert "administrative division" in error.value.report["unsuitable"]


def test_restatement_goes_stale_when_the_source_revision_changes() -> None:
    restatement = build_restatement(content(), dossier(), **GENERATED)
    edited = dossier(extract=SOURCE + "\nA later editor added a sentence.", revision_id=43)

    with pytest.raises(ValueError, match="stale"):
        validate_restatement(restatement, edited)

    validate_restatement(restatement, dossier())


def test_hedges_may_be_kept_and_do_not_trip_the_checks() -> None:
    restatement = build_restatement(
        content(
            text=(
                "Sirkap is an archaeological site opposite Taxila. It is also said to have been "
                "rebuilt by king Menander I."
            )
        ),
        dossier(),
        **GENERATED,
    )

    assert "said to have been rebuilt" in restatement.text


def test_pending_dossiers_skips_completed_and_thin_sources(tmp_path) -> None:
    completed = {"wikipedia:en:1001103": hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()}
    thin = dossier(extract="A stub.")

    assert pending_dossiers([dossier()], completed) == []
    assert pending_dossiers([dossier()], {}) == [dossier()]
    assert pending_dossiers([thin], {}) == []
    assert completed_source_checksums(tmp_path / "missing.ndjson") == {}


def test_pending_dossiers_returns_records_whose_source_moved_on() -> None:
    stale = {"wikipedia:en:1001103": "0" * 64}

    assert len(pending_dossiers([dossier()], stale)) == 1


def test_report_is_empty_for_an_exact_copy() -> None:
    assert not any(closed_world_report(content(), SOURCE).values())


def test_release_publishes_restatement_shards_and_drops_stale_ones(
    tmp_path,
    historical_feature,
) -> None:
    """A release ships fresh restatements and silently omits ones whose source moved on."""

    fresh = dossier()
    moved_on = dossier(extract=SOURCE + "\nA later editor added a sentence.", revision_id=43)
    restatement = build_restatement(content(), fresh, **GENERATED)

    output = tmp_path / "build"
    build_artifacts(
        [historical_feature],
        [],
        [],
        [moved_on],
        output,
        restatements=[restatement],
    )

    index = orjson.loads((output / "content" / "index.json").read_bytes())
    assert index["collections"]["restatements"]["count"] == 0

    output_fresh = tmp_path / "build-fresh"
    build_artifacts(
        [historical_feature],
        [],
        [],
        [fresh],
        output_fresh,
        restatements=[restatement],
    )

    index = orjson.loads((output_fresh / "content" / "index.json").read_bytes())
    assert index["collections"]["restatements"]["count"] == 1
    shard = content_shard(fresh.dossier_id, 2)
    records = orjson.loads(
        (output_fresh / "content" / "restatements" / f"{shard}.json").read_bytes()
    )
    # Sharded by source dossier ID, so a reader that resolved a dossier needs no second lookup.
    assert records[fresh.dossier_id]["restatement_id"] == restatement.restatement_id
    assert records[fresh.dossier_id]["content_role"] == "source_restatement"


def test_generation_sends_only_the_source_and_validates_what_comes_back() -> None:
    """The provider sees one extract, and its output is checked before it is trusted."""

    requested: dict[str, object] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        requested.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_fixture",
                "model": "fixture:model-revision",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(content().model_dump(mode="json")),
                            }
                        ],
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        restatement = generate_with_openai(
            dossier(),
            prompt="restate this",
            prompt_version="dossier-restate-v1",
            model_identifier="fixture:requested-model",
            api_key="test-only",
            generated_at=datetime(2026, 7, 25, tzinfo=UTC),
            client=client,
        )

    assert restatement.generation.model_identifier == "fixture:model-revision"
    assert restatement.generation.provider_response_id == "resp_fixture"
    assert requested["store"] is False
    assert requested["text"]["format"]["strict"] is True
    # The prompt claims the extract is the only allowed input, so nothing else may be sent.
    assert "Menander" in str(requested["input"])
    assert "wikidata:Q1" not in str(requested["input"])


def test_generation_rejects_provider_output_that_leaves_the_source() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        strayed = content(text="Sirkap was a centre of Gandharan culture opposite Taxila.")
        return httpx.Response(
            200,
            json={
                "id": "resp_fixture",
                "model": "fixture:model-revision",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(strayed.model_dump(mode="json")),
                            }
                        ],
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(RestatementRejected):
            generate_with_openai(
                dossier(),
                prompt="restate this",
                prompt_version="dossier-restate-v1",
                model_identifier="fixture:requested-model",
                api_key="test-only",
                client=client,
            )


def test_bce_year_with_a_positive_sort_year_is_rejected() -> None:
    """A sign slip would move a record a full era on the reader's timeline."""

    with pytest.raises(ValueError, match="BCE but its sort year is not"):
        content(
            timeline=[{"year_text": "77 BCE", "sort_year": 77, "text": "The city became capital"}]
        )


def test_ce_year_with_a_negative_sort_year_is_rejected() -> None:
    with pytest.raises(ValueError, match="CE but its sort year is not"):
        content(
            timeline=[{"year_text": "150 AD", "sort_year": -150, "text": "The city appears"}]
        )


def test_parenthetical_unit_conversion_is_rejected() -> None:
    """Two numbers for one quantity: both exist in the source, so only the pairing can be wrong."""

    source = (
        "Perinthus lay 35 kilometres (22 mi) west of Selymbria and 90 kilometres (56 mi) west of "
        "Byzantium, on a small peninsula, and was built like an amphitheatre on a hill."
    )
    report = closed_world_report(
        content(
            headline="A town west of Byzantium",
            text="Perinthus lay 90 kilometres (22 mi) west of Byzantium, on a small peninsula.",
            timeline=[],
        ),
        source,
    )

    assert any(phrase.startswith("unit-conversion:") for phrase in report["denied_phrases"])


def test_present_day_statistics_are_recorded_but_do_not_block_publication() -> None:
    """Keeping a population count makes a restatement worse, not untrue, so it is not fatal."""

    source = (
        "Schaan is the largest municipality of Liechtenstein by population. As of 2019 it has a "
        "population of 6,039, making it the most populous administrative district."
    )
    report = closed_world_report(
        content(
            headline="The largest municipality of Liechtenstein",
            text="Schaan is the largest municipality of Liechtenstein by population.",
            timeline=[],
        ),
        source,
    )

    assert report["retained_furniture"] == ["by population"]
    assert not report["denied_phrases"]


def test_a_historical_use_of_inhabitants_is_not_a_census_figure() -> None:
    """"The first inhabitants" is history. "62,088 inhabitants" is a statistic."""

    source = (
        "Troyes stood at the hub of numerous highways. The Tricasses tribe were the first "
        "inhabitants. Troyes had a population of 62,088 inhabitants in 2023."
    )
    historical = closed_world_report(
        content(
            headline="A city on the highways",
            text="The Tricasses tribe were the first inhabitants of Troyes.",
            timeline=[],
        ),
        source,
    )
    statistical = closed_world_report(
        content(
            headline="A city on the highways",
            text="Troyes had 62,088 inhabitants in 2023.",
            timeline=[],
        ),
        source,
    )

    assert not historical["retained_furniture"]
    assert statistical["retained_furniture"]


def test_a_demonym_built_on_a_source_stem_is_accepted() -> None:
    """"A Thracian town" for "a town of Thrace" renames nothing."""

    source = "Perinthus was a great and flourishing town of ancient Thrace, on the Propontis."
    report = closed_world_report(
        content(
            headline="A flourishing Thracian town on the Propontis",
            text="Perinthus was a flourishing Thracian town on the Propontis.",
            timeline=[],
        ),
        source,
    )

    assert not report["unsupported_names"]


def test_a_demonym_built_on_an_absent_stem_is_still_rejected() -> None:
    source = "Sirkap is an archaeological site opposite Taxila, in Punjab, Pakistan."
    report = closed_world_report(
        content(
            headline="A site opposite Taxila",
            text="Sirkap was a Gandharan site opposite Taxila.",
            timeline=[],
        ),
        source,
    )

    assert report["unsupported_names"] == ["Gandharan"]


def test_a_place_name_behind_a_source_demonym_is_rejected_by_design() -> None:
    """The demonym rule runs one way only.

    Accepting "Rome" for a source that says "Roman" needs a three-character stem, and any
    threshold that loose also accepts "Romania". The reverse stays rejected: the reader falls back
    to the source extract, which is the cheap failure.
    """

    source = "Eboracum was a fort and later a city in the Roman province of Britannia."
    report = closed_world_report(
        content(
            headline="A fort in a province of Rome",
            text="Eboracum was a fort and later a city in a province of Rome, in Britannia.",
            timeline=[],
        ),
        source,
    )

    assert report["unsupported_names"] == ["Rome"]


def test_an_unrelated_proper_noun_survives_the_symmetric_rule() -> None:
    source = "Eboracum was a fort and later a city in the Roman province of Britannia."
    report = closed_world_report(
        content(
            headline="A fort in Britannia",
            text="Eboracum was a fort in Britannia, near the Erechtheion.",
            timeline=[],
        ),
        source,
    )

    assert report["unsupported_names"] == ["Erechtheion"]


def test_sentence_initial_common_noun_is_not_read_as_a_name() -> None:
    """Grammar capitalises the first word of a sentence; that is not a claim about a person."""

    source = (
        "Pontarlier is a commune in the Doubs department. Work on the fort went on for years "
        "after the fire, and the town rebuilt its walls."
    )
    report = closed_world_report(
        content(
            headline="A commune in the Doubs department",
            text="Pontarlier is a commune in the Doubs department. Construction went on for years.",
            timeline=[],
        ),
        source,
    )

    assert not report["unsupported_names"]


def test_a_name_is_still_checked_when_it_starts_a_sentence() -> None:
    """The exemption is limited to words the corpus shows English writes in lower case."""

    source = "Sirkap is an archaeological site opposite Taxila, in Punjab, Pakistan."
    report = closed_world_report(
        content(
            headline="A site opposite Taxila",
            text="Sirkap lies opposite Taxila. Gandharan workshops stood nearby.",
            timeline=[],
        ),
        source,
    )

    assert report["unsupported_names"] == ["Gandharan"]


def test_a_name_mid_sentence_is_never_exempt() -> None:
    """A common word used mid-sentence was capitalised by choice, so it stays checked."""

    source = "Sirkap is an archaeological site opposite Taxila, in Punjab, Pakistan."
    report = closed_world_report(
        content(
            headline="A site opposite Taxila",
            text="Sirkap lies opposite the Gulf and Taxila.",
            timeline=[],
        ),
        source,
    )

    assert report["unsupported_names"] == ["Gulf"]


def test_the_lexicon_holds_common_words_and_excludes_names() -> None:
    lexicon = common_words()

    assert {"construction", "settlement", "fortress", "notable"} <= lexicon
    assert not lexicon & {"gandharan", "erechtheion", "mauryan", "thracian", "byzantium"}


def test_lexicon_is_built_from_lower_case_occurrences_only() -> None:
    words = build_common_words(
        ["Thrace was a region. the town grew."] * 60 + ["Thrace and Thrace."] * 60,
        minimum_documents=50,
    )

    assert "town" in words
    assert "thrace" not in words
