from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from history_pipeline.models import (
    ChronicleEntry,
    ChronicleEntryKind,
    DatePrecision,
    SourceReference,
    SubjectExtract,
    YearChronicle,
    YearDossierContent,
)
from history_pipeline.restatement import RestatementRejected, normalise_for_checking
from history_pipeline.year_dossier import (
    MAXIMUM_PEOPLE_IN_PROSE,
    build_year_dossier,
    entry_labels,
    evidence_text,
    plan_sections,
    resolve_labels,
    validate_dossier_content,
    validate_year_dossier,
)

SOURCE = SourceReference(
    source_id="wikipedia",
    record_id="34181",
    title="Wikipedia: 1543",
    publisher="Wikimedia Foundation",
    url="https://en.wikipedia.org/wiki/1543",
    license_id="CC-BY-SA-4.0",
    retrieved_at=datetime(2026, 7, 25, tzinfo=UTC),
    citation="“1543”, EN Wikipedia",
)
GENERATED = {
    "prompt_version": "year-dossier-v1",
    "prompt_sha256": "a" * 64,
    "model_identifier": "fixture:test",
    "generated_at": datetime(2026, 7, 25, tzinfo=UTC),
}


def entry(
    text: str,
    kind: ChronicleEntryKind = ChronicleEntryKind.EVENT,
    *,
    month: int | None = 1,
    day: int | None = 4,
    sitelinks: int | None = None,
) -> ChronicleEntry:
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    return ChronicleEntry(
        entry_id=f"chronicle:1543:{kind.value}:{digest}",
        kind=kind,
        year=1543,
        month=month,
        day=day,
        date_precision=DatePrecision.EXACT if day else DatePrecision.YEAR,
        text=text,
        sitelink_count=sitelinks,
    )


def chronicle(entries: list[ChronicleEntry]) -> YearChronicle:
    return YearChronicle(
        chronicle_id="chronicle:1543:en",
        year=1543,
        language="en",
        page_id=1,
        revision_id=99,
        revision_timestamp=datetime(2026, 7, 25, tzinfo=UTC),
        content_checksum_sha256="b" * 64,
        source_ref=SOURCE,
        entries=entries,
    )


ENTRIES = [
    entry("Henry VIII allies with Charles V against France."),
    entry("Suleiman captures Esztergom.", day=5),
    entry("Martin Luther publishes On the Jews and Their Lies.", day=6),
    entry("The Act for the Advancement of True Religion is given assent.", day=7),
    entry("Tokugawa Ieyasu, Japanese shogun", ChronicleEntryKind.BIRTH, day=31, sitelinks=85),
    entry("Kano Eitoku, painter", ChronicleEntryKind.BIRTH, month=2, day=16, sitelinks=40),
]
LENSES = {
    ENTRIES[0].entry_id: "power",
    ENTRIES[1].entry_id: "power",
    ENTRIES[2].entry_id: "belief",
    ENTRIES[3].entry_id: "belief",
}


def plan():
    return plan_sections(ENTRIES, LENSES)


def test_sections_come_from_the_years_own_data() -> None:
    ids = [section_id for section_id, _, _ in plan()]

    assert ids == ["section:power", "section:belief"]


def test_who_was_born_and_who_died_are_rendered_rather_than_narrated() -> None:
    """Asked for as prose, births came back as "Other births included X (18 February), Y (1543)".

    That is a list with commas standing in for sentences, and it is what the register already is
    and does better. The prominent few get a restated sentence each about who they were instead.
    """

    ids = [section_id for section_id, _, _ in plan()]

    assert "section:births" not in ids
    assert "section:deaths" not in ids


def test_a_lens_with_too_little_material_is_folded_away() -> None:
    """A thin year should read as a short dossier, not a padded one."""

    thin = plan_sections(ENTRIES[:1], {ENTRIES[0].entry_id: "power"})
    ids = [section_id for section_id, _, _ in thin]

    assert "section:power" not in ids
    assert ids == ["section:elsewhere"]


def test_every_record_reaches_the_model_and_the_prominent_ones_are_marked() -> None:
    """Hiding records would leave the writer choosing among an arbitrary subset."""

    from history_pipeline.year_dossier import _most_written_about, evidence_for

    people = [
        entry(f"Person {n}", ChronicleEntryKind.DEATH, month=3, day=n, sitelinks=n)
        for n in range(1, 12)
    ]
    events = [person.model_copy(update={"kind": ChronicleEntryKind.EVENT}) for person in people]
    _id, _heading, kept = plan_sections(events, {})[-1]

    # The plan keeps everything; the register carries them all either way.
    assert len(kept) == 11

    labels = {f"e{n}": person.entry_id for n, person in enumerate(kept, start=1)}
    shown = evidence_for(kept, labels, None, MAXIMUM_PEOPLE_IN_PROSE)
    assert shown.count("\n") == 10
    # Only the most-written-about are starred for the paragraph to lead with.
    assert shown.count("]*") == MAXIMUM_PEOPLE_IN_PROSE

    prominent = _most_written_about(kept, MAXIMUM_PEOPLE_IN_PROSE)
    assert min(person.sitelink_count or 0 for person in prominent) == 6
    assert [p.sitelink_count for p in prominent] == sorted(
        p.sitelink_count for p in prominent
    )


def test_who_held_power_stays_structured_rather_than_narrated() -> None:
    """Offices held are a table; asked for as prose they come back as a row of dashes."""

    holders = [
        entry("Monarch - Mary, Queen of Scots", ChronicleEntryKind.INCUMBENT, month=None, day=None),
        entry("Monarch - Henry VIII", ChronicleEntryKind.INCUMBENT, month=None, day=None),
    ]
    ids = [section_id for section_id, _, _ in plan_sections(holders, {})]

    assert "section:incumbents" not in ids


def test_labels_are_short_and_round_trip_back_to_entry_ids() -> None:
    labels = entry_labels(plan())

    assert all(label.startswith("e") and label[1:].isdigit() for label in labels)
    payload = resolve_labels(
        {"sections": [{"entry_ids": ["e1", "[e2]", "e1"]}]}, labels
    )
    assert payload["sections"][0]["entry_ids"] == [labels["e1"], labels["e2"]]


def test_an_unknown_label_is_left_alone_so_the_citation_check_can_reject_it() -> None:
    payload = resolve_labels({"sections": [{"entry_ids": ["e999"]}]}, entry_labels(plan()))

    assert payload["sections"][0]["entry_ids"] == ["e999"]


def test_evidence_text_carries_the_dates_the_model_was_shown() -> None:
    """Dates live in structured fields, so the checker must see them or reject real ones."""

    text = evidence_text(chronicle(ENTRIES))

    assert "January 4" in text
    assert "February 16" in text


def content(**overrides) -> YearDossierContent:
    payload = {
        "overview": "Henry VIII allied with Charles V against France.",
        "sections": [
            {
                "section_id": "section:power",
                "prose": "Henry VIII allies with Charles V. Suleiman captures Esztergom.",
                "entry_ids": [ENTRIES[0].entry_id, ENTRIES[1].entry_id],
            },
            {
                "section_id": "section:belief",
                "prose": "Martin Luther publishes On the Jews and Their Lies.",
                "entry_ids": [ENTRIES[2].entry_id],
            },
        ],
    }
    payload.update(overrides)
    return YearDossierContent.model_validate(payload)


def test_a_faithful_dossier_is_accepted_and_content_addressed() -> None:
    dossier = build_year_dossier(content(), chronicle(ENTRIES), plan(), **GENERATED)
    same = build_year_dossier(content(), chronicle(ENTRIES), plan(), **GENERATED)

    assert dossier.dossier_id == same.dossier_id
    assert dossier.editorial_state == "machine_generated"
    assert dossier.chronicle_revision_id == 99
    # Heading and lens are the pipeline's, never the model's.
    assert dossier.sections[0].heading == "Rulers, wars and states"
    assert [section.lens for section in dossier.sections] == ["power", "belief"]


def test_an_invented_citation_is_rejected() -> None:
    broken = content(
        sections=[
            {
                "section_id": "section:power",
                "prose": "Henry VIII allies with Charles V.",
                "entry_ids": ["chronicle:1543:event:0000000000000000"],
            },
            *content().model_dump(mode="json")["sections"][1:],
        ]
    )

    with pytest.raises(RestatementRejected) as error:
        build_year_dossier(broken, chronicle(ENTRIES), plan(), **GENERATED)

    assert error.value.report["unresolved_citations"] == [
        "chronicle:1543:event:0000000000000000"
    ]


def test_a_missing_section_is_rejected() -> None:
    partial = content(sections=content().model_dump(mode="json")["sections"][:1])

    with pytest.raises(RestatementRejected) as error:
        build_year_dossier(partial, chronicle(ENTRIES), plan(), **GENERATED)

    assert set(error.value.report["sections"]) == {"section:belief"}


def test_a_name_absent_from_the_records_is_rejected() -> None:
    """The generalisation an unreviewed dossier must not make: naming what was not recorded."""

    report = validate_dossier_content(
        content(overview="Henry VIII allied with Charles V across Europe and Italy."),
        chronicle(ENTRIES),
        plan(),
    )

    assert report["unsupported_names"] == ["Europe", "Italy"]


def test_a_year_number_may_be_written_even_though_no_entry_repeats_it() -> None:
    report = validate_dossier_content(
        content(overview="Henry VIII allied with Charles V in 1543."),
        chronicle(ENTRIES),
        plan(),
    )

    assert not report


def test_a_dossier_goes_stale_when_its_chronicle_changes() -> None:
    dossier = build_year_dossier(content(), chronicle(ENTRIES), plan(), **GENERATED)
    edited = chronicle([*ENTRIES, entry("A later editor added an entry.", day=9)])

    with pytest.raises(ValueError, match="stale"):
        validate_year_dossier(dossier, edited)

    validate_year_dossier(dossier, chronicle(ENTRIES))


def test_invisible_characters_do_not_split_a_word_before_checking() -> None:
    """A soft hyphen inside a name is invisible to a reader and fatal to a naive tokeniser."""

    assert normalise_for_checking("Engla­nd") == "England"
    assert normalise_for_checking("Eth​iopia") == "Ethiopia"


def test_a_surname_is_linkable_but_a_title_word_is_not() -> None:
    """"Copernicus" is a name. "Scots" and "Empire" are the tails of titles, not names."""

    from history_pipeline.year_dossier import link_index

    def extract(canonical: str, page_id: int) -> SubjectExtract:
        text = f"{canonical} is a subject of the year."
        return SubjectExtract(
            title=canonical,
            canonical_title=canonical,
            page_id=page_id,
            revision_id=1,
            url=f"https://en.wikipedia.org/wiki/{canonical.replace(' ', '_')}",
            extract=text,
            content_checksum_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )

    ch = chronicle(ENTRIES)
    ch = ch.model_copy(
        update={
            "subject_extracts": [
                extract("Nicolaus Copernicus", 1),
                extract("Mary, Queen of Scots", 2),
                extract("Spanish Empire", 3),
            ]
        }
    )
    forms = {form for form, _ in link_index(ch)}

    assert "Copernicus" in forms
    assert "Scots" not in forms
    assert "Empire" not in forms
    assert "Mary, Queen of Scots" in forms


def test_only_the_first_mention_of_a_subject_is_linked() -> None:
    """Linking every mention turns a paragraph into a field of blue."""

    from history_pipeline.year_dossier import attach_links, link_index

    text = "Copernicus died in May. Copernicus had written one book."
    ch = chronicle(ENTRIES).model_copy(
        update={
            "subject_extracts": [
                SubjectExtract(
                    title="Nicolaus Copernicus",
                    canonical_title="Nicolaus Copernicus",
                    page_id=1,
                    revision_id=1,
                    url="https://en.wikipedia.org/wiki/Nicolaus_Copernicus",
                    extract="Nicolaus Copernicus was an astronomer.",
                    content_checksum_sha256=hashlib.sha256(
                        b"Nicolaus Copernicus was an astronomer."
                    ).hexdigest(),
                )
            ]
        }
    )
    links = attach_links(text, link_index(ch))

    assert len(links) == 1
    assert text[links[0].start : links[0].end] == "Copernicus"
    assert links[0].start == 0


# ---------------------------------------------------------------------------
# Blocks: a smaller closed world per paragraph
# ---------------------------------------------------------------------------


def test_a_block_may_not_borrow_a_name_from_a_block_it_is_not_about() -> None:
    """The whole-year check cannot see this: the name is in the year, just not in this block.

    It does not detect a fusion, and nothing mechanical can. It reduces how many facts are in
    front of the writer when it writes a sentence, which is the only lever there is.
    """

    report = validate_dossier_content(
        content(
            sections=[
                {
                    "section_id": "section:power",
                    "prose": "Henry VIII allied with Charles V.",
                    "entry_ids": [ENTRIES[0].entry_id],
                },
                {
                    # Luther is a real record of this year, and not a record of this block.
                    "section_id": "section:belief",
                    "prose": "Martin Luther wrote while Suleiman marched.",
                    "entry_ids": [ENTRIES[2].entry_id],
                },
            ]
        ),
        chronicle(ENTRIES),
        plan(),
    )

    assert report["block:section:belief"]["unsupported_names"] == ["Suleiman"]
    # And the whole-year check passes it, which is the point.
    assert "unsupported_names" not in report


def test_the_year_itself_is_never_an_invented_number_in_any_block() -> None:
    report = validate_dossier_content(
        content(
            sections=[
                {
                    "section_id": "section:power",
                    "prose": "Henry VIII allied with Charles V in 1543.",
                    "entry_ids": [ENTRIES[0].entry_id],
                },
                *content().model_dump(mode="json")["sections"][1:],
            ]
        ),
        chronicle(ENTRIES),
        plan(),
    )

    assert not report


def test_a_sentence_copied_out_of_the_prompt_is_rejected() -> None:
    """Found live: a dossier's lede was the prompt's worked example, word for word.

    Every name and number in it appeared somewhere in the year's records, so nothing rejected it.
    An illustration of good writing is the one text in the request that is not evidence.
    """

    from history_pipeline.year_dossier import prompt_echoes

    prompt = (
        "On 21 March a book arguing that the Earth moves was printed at Nuremberg. In June "
        "another mapped the human body."
    )

    assert prompt_echoes(prompt, prompt)
    assert not prompt_echoes("Henry VIII married Catherine Parr in July.", prompt)


def test_the_checker_is_not_handed_half_a_word() -> None:
    """A prefix cut at a fixed character count reported "Ottoma" as an invented name."""

    from history_pipeline.year_dossier import _headline_of

    text = "The Ottoman Empire under Suleiman the Magnificent captured the city."

    assert _headline_of(text, 12) == "The Ottoman"
    assert _headline_of(text, 500) == text


def test_emphasis_the_model_added_is_repaired_rather_than_rejected() -> None:
    """The asterisks are formatting, not a claim, and they break prose-link offsets."""

    from history_pipeline.year_dossier import strip_emphasis

    assert strip_emphasis("Luther published *On the Jews and Their Lies*.") == (
        "Luther published On the Jews and Their Lies."
    )
    assert strip_emphasis("2 * 3 is not emphasis") == "2 * 3 is not emphasis"


def test_a_rejection_becomes_an_instruction_for_the_next_attempt() -> None:
    """Feeding a check's output back is not the same as relaxing it: it only ever says remove."""

    from history_pipeline.year_dossier import correction_note

    note = correction_note(
        {
            "block:section:deaths": {
                "unsupported_names": ["Frombork"],
                "unsupported_numbers": ["70"],
            },
            "unsupported_names": ["Venlo"],
            "prose": ["opening:overview:'The year 1543 saw'"],
        }
    )

    assert note is not None
    assert "remove 70, Frombork" in note
    assert "Venlo" in note
    assert "announcing the year" in note
    assert correction_note({}) is None


def test_an_anchor_gathers_the_other_records_of_the_same_campaign() -> None:
    """One record and one biography produces a biography. The campaign is four records."""

    from history_pipeline.year_dossier import plan_anchors
    from history_pipeline.year_layers import extract_index

    march = entry(
        "Suleiman the Magnificent, Sultan of the Ottoman Empire, follows up on his 1541 "
        "annexation of Hungary by invading a second time to capture areas taken by Archduke "
        "Ferdinand, including Esztergom.",
        day=23,
    )
    march = march.model_copy(
        update={
            "subject_title": "Suleiman the Magnificent",
            "subject_wikidata_id": "Q8474",
            "linked_titles": ["Suleiman the Magnificent", "Hungary"],
            "sitelink_count": 154,
        }
    )
    siege = entry(
        "Esztergom surrenders to the Ottomans led by Suleiman the Magnificent after a siege "
        "that had begun earlier in the summer.",
        day=10,
    )
    siege = siege.model_copy(
        update={
            "subject_title": "Esztergom",
            "subject_wikidata_id": "Q171353",
            "linked_titles": ["Esztergom", "Suleiman the Magnificent"],
            "sitelink_count": 30,
        }
    )
    background = SubjectExtract(
        title="Suleiman the Magnificent",
        canonical_title="Suleiman the Magnificent",
        page_id=9,
        revision_id=1,
        url="https://en.wikipedia.org/wiki/Suleiman_the_Magnificent",
        extract="He ruled the Ottoman Empire. " * 20,
        content_checksum_sha256=hashlib.sha256(
            ("He ruled the Ottoman Empire. " * 20).encode()
        ).hexdigest(),
    )
    anchors = plan_anchors([march, siege], {}, extract_index([background]))

    assert len(anchors) == 1
    assert len(anchors[0].siblings) == 1
    assert "Esztergom" in anchors[0].evidence()
    assert set(anchors[0].entry_ids) == {march.entry_id, siege.entry_id}


def test_the_correction_names_the_spelling_the_records_actually_use() -> None:
    """The commonest rejection is a word-form variant, not an invention.

    Told only to remove "Chants", the model removed the sentence and wrote "Chants" again on the
    next attempt, because nothing told it the source says "Chantz".
    """

    from history_pipeline.year_dossier import near_misses

    assert near_misses(["Chants"], "La Forme des Prieres et Chantz ecclesiastiques") == {
        "Chants": "Chantz"
    }
    # A genuine invention has nothing near it, and is reported without a suggestion.
    assert near_misses(["Venlo"], "Guelders and Rome and Nuremberg") == {}


def test_an_unsupported_sentence_is_deleted_rather_than_costing_the_whole_year() -> None:
    """Deletion can only shrink what a dossier claims, and the checks all run again after it."""

    from history_pipeline.year_dossier import _drop_unsupported_sentences

    rejection = RestatementRejected(
        "year:1543",
        {"block:section:power": {"unsupported_names": ["Venlo"]}},
        content(
            sections=[
                {
                    "section_id": "section:power",
                    "prose": (
                        "Henry VIII allied with Charles V. The Treaty of Venlo was signed. "
                        "Suleiman captured Esztergom."
                    ),
                    "entry_ids": [ENTRIES[0].entry_id],
                },
                *content().model_dump(mode="json")["sections"][1:],
            ]
        ).model_dump(mode="json"),
    )
    rejection.prompt_version = "year-dossier-v2"
    rejection.prompt_sha256 = "a" * 64
    rejection.model_identifier = "fixture:test"
    rejection.generated_at = datetime(2026, 7, 25, tzinfo=UTC)

    repaired = _drop_unsupported_sentences(
        rejection, chronicle(ENTRIES), LENSES, context=None
    )

    assert repaired is not None
    power = next(s for s in repaired.sections if s.section_id == "section:power")
    assert "Venlo" not in power.prose
    assert "Suleiman captured Esztergom." in power.prose
    assert repaired.removed_sentences == ["The Treaty of Venlo was signed."]


def test_a_paragraph_that_would_be_cut_to_one_line_is_left_alone() -> None:
    """A block cut to its last sentence can be left resting on an antecedent that went with it."""

    from history_pipeline.year_dossier import _drop_unsupported_sentences

    rejection = RestatementRejected(
        "year:1543",
        {"block:section:power": {"unsupported_names": ["Venlo"]}},
        content(
            sections=[
                {
                    "section_id": "section:power",
                    "prose": "The Treaty of Venlo was signed. It ended a war.",
                    "entry_ids": [ENTRIES[0].entry_id],
                },
                *content().model_dump(mode="json")["sections"][1:],
            ]
        ).model_dump(mode="json"),
    )

    assert _drop_unsupported_sentences(
        rejection, chronicle(ENTRIES), LENSES, context=None
    ) is None


def test_a_rejection_that_is_not_a_containment_fault_is_never_repaired_by_deletion() -> None:
    """Deleting a sentence cannot fix a missing section or a citation that does not resolve."""

    from history_pipeline.year_dossier import _drop_unsupported_sentences

    rejection = RestatementRejected(
        "year:1543",
        {"sections": ["section:births"]},
        content().model_dump(mode="json"),
    )

    assert _drop_unsupported_sentences(
        rejection, chronicle(ENTRIES), LENSES, context=None
    ) is None


def test_a_gloss_may_not_carry_a_judgement_even_when_its_article_makes_one() -> None:
    """The one place the closed-world deny list is deliberately not closed-world.

    Everywhere else, a phrase is denied only when the model introduced it: carrying the source's
    own wording across is restatement, not invention. An article is free to say somebody was one
    of the greatest portraitists of their century. This tier has no reader who could stand behind
    repeating it, so the gloss carries what they did and not what anyone thinks of it.
    """

    report = validate_dossier_content(
        content(
            people=[
                {
                    "person_id": "p1",
                    "gloss": "Hans Holbein is considered one of the greatest portraitists.",
                }
            ]
        ),
        chronicle(ENTRIES),
        plan(),
    )

    assert any(
        fault.startswith("significance:p1|") for fault in report.get("prose", [])
    )
    assert report["people"] == ["p1"]


def test_a_gloss_does_not_repeat_the_name_printed_above_it() -> None:
    """Removing a prefix is safe in a way that rewriting one is not: it only deletes."""

    from history_pipeline.year_dossier import trim_repeated_subject

    assert trim_repeated_subject(
        "Tokugawa Ieyasu was a Japanese daimyo who founded the shogunate.", "Tokugawa Ieyasu"
    ) == "was a Japanese daimyo who founded the shogunate."
    # An appositive the record already carries goes with it.
    assert trim_repeated_subject(
        "Juan Rodríguez Cabrillo, Portuguese explorer, was the first European to reach it.",
        "Juan Rodríguez Cabrillo",
    ) == "was the first European to reach it."
    # A sentence built around the name keeps it, rather than being cut to a fragment.
    assert trim_repeated_subject(
        "The Cellini Salt Cellar is a sculpture of gold and enamel.", "Cellini Salt Cellar"
    ) == "The Cellini Salt Cellar is a sculpture of gold and enamel."
