"""The assembled half of a year dossier: everything nobody writes.

These layers carry most of the page, so their failures are the ones a reader meets first — a
record shown three times, a lede that spends all three slots on one man, a quotation that opens
with a pronunciation guide. None of that is detectable from the prose checks, because none of it
is prose.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from history_pipeline.config import LicensePolicy
from history_pipeline.models import (
    ChronicleEntry,
    ChronicleEntryKind,
    DatePrecision,
    SourceReference,
    SubjectExtract,
    YearChronicle,
)
from history_pipeline.year_layers import (
    ImageRejected,
    assemble_lede,
    build_incumbents,
    build_quote,
    build_register,
    build_related_years,
    build_themes,
    cluster_entries,
    collapse_duplicates,
    date_text,
    display_title,
    extract_index,
    image_from_commons,
    most_written_about,
    parse_conflicts,
    quotable,
    reads_as_a_record,
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


def entry(
    text: str,
    *,
    kind: ChronicleEntryKind = ChronicleEntryKind.EVENT,
    month: int | None = None,
    day: int | None = None,
    subject: str | None = None,
    wikidata_id: str | None = None,
    sitelinks: int | None = None,
    linked: list[str] | None = None,
    source_page: str | None = None,
    topic: str | None = None,
    lens: str | None = None,
    related_year: int | None = None,
    qualifier: str | None = None,
) -> ChronicleEntry:
    titles = list(linked or [])
    if subject and subject not in titles:
        titles.insert(0, subject)
    digest = hashlib.sha256(f"{text}{month}{day}{source_page}".encode()).hexdigest()[:16]
    return ChronicleEntry(
        entry_id=f"chronicle:1543:{kind.value}:{digest}",
        kind=kind,
        year=1543,
        month=month,
        day=day,
        date_precision=DatePrecision.EXACT if day else DatePrecision.YEAR,
        text=text,
        qualifier=qualifier,
        subject_title=subject,
        subject_wikidata_id=wikidata_id,
        linked_titles=titles,
        sitelink_count=sitelinks,
        source_page=source_page,
        topic=topic,
        lens=lens,
        related_year=related_year,
    )


def extract(
    canonical: str, body: str, page_id: int = 1, title: str | None = None
) -> SubjectExtract:
    return SubjectExtract(
        title=title or canonical,
        canonical_title=canonical,
        page_id=page_id,
        revision_id=7,
        url=f"https://en.wikipedia.org/wiki/{canonical.replace(' ', '_')}",
        extract=body,
        content_checksum_sha256=hashlib.sha256(body.encode()).hexdigest(),
    )


def chronicle(entries: list[ChronicleEntry], extracts: list[SubjectExtract] | None = None):
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
        subject_extracts=extracts or [],
    )


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

COPERNICUS_MAIN = entry(
    "Nicolaus Copernicus, Polish Renaissance mathematician and astronomer (born 1473)",
    kind=ChronicleEntryKind.DEATH,
    month=5,
    day=24,
    subject="Nicolaus Copernicus",
    wikidata_id="Q619",
    sitelinks=213,
    source_page="1543",
    related_year=1473,
)
COPERNICUS_AGAIN = entry(
    "Nicolaus Copernicus (born 1473), Polish astronomer.",
    kind=ChronicleEntryKind.DEATH,
    month=5,
    day=24,
    subject="Nicolaus Copernicus",
    wikidata_id="Q619",
    sitelinks=213,
    source_page="1543 in science",
    related_year=1473,
)
LUTHER_ONE = entry(
    "Martin Luther publishes On the Jews and Their Lies.",
    subject="Martin Luther",
    wikidata_id="Q9554",
    sitelinks=257,
    source_page="1543",
)
LUTHER_TWO = entry(
    "Martin Luther - Vom Schem Hamphoras",
    subject="Martin Luther",
    wikidata_id="Q9554",
    sitelinks=257,
    source_page="1543 in literature",
    topic="New books",
)


def test_one_happening_written_up_twice_becomes_one_record() -> None:
    """A year is documented across a dozen pages and repeats itself on most of them."""

    clusters = cluster_entries([COPERNICUS_MAIN, COPERNICUS_AGAIN])

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    # The fullest wording leads; the other is kept rather than discarded.
    assert clusters[0].texts[0] == COPERNICUS_MAIN.text
    assert clusters[0].texts[1] == COPERNICUS_AGAIN.text


def test_two_happenings_about_one_person_stay_two() -> None:
    """Merging on subject alone would delete an event: Luther wrote two books."""

    clusters = cluster_entries([LUTHER_ONE, LUTHER_TWO])

    assert len(clusters) == 2


def test_a_dated_companion_record_supplies_the_date_the_main_article_omitted() -> None:
    """The coronation is dated on the Scotland page and undated on the year page."""

    undated = entry(
        "Mary Stuart is crowned the Queen of Scots in Stirling at the age of nine months old.",
        subject="Mary, Queen of Scots",
        wikidata_id="Q119805638",
        source_page="1543",
    )
    dated = entry(
        "Coronation of Mary, Queen of Scots at Stirling.",
        month=9,
        day=9,
        subject="Mary, Queen of Scots",
        wikidata_id="Q119805638",
        source_page="1543 in Scotland",
    )
    cluster = cluster_entries([undated, dated])[0]

    assert len(cluster.members) == 2
    assert (cluster.month, cluster.day) == (9, 9)
    assert date_text(cluster.month, cluster.day) == "9 September"


def test_an_entry_with_no_wikidata_subject_is_never_merged() -> None:
    """Without an identifier there is nothing solid enough to merge on."""

    first = entry("A thing happened in a town.", subject=None)
    second = entry("A thing happened in a town again.", subject=None)

    assert len(cluster_entries([first, second])) == 2


def test_section_planning_sees_one_of_each_happening() -> None:
    representatives, represented = collapse_duplicates([COPERNICUS_MAIN, COPERNICUS_AGAIN])

    assert len(representatives) == 1
    assert len(represented[representatives[0].entry_id]) == 2


# ---------------------------------------------------------------------------
# Ranking and the assembled lede
# ---------------------------------------------------------------------------


def test_one_subject_cannot_take_the_whole_top_of_the_list() -> None:
    """Sitelinks belong to the subject, so a famous person otherwise wins every slot."""

    others = [
        entry("Somebody else did something notable.", subject="Titian", wikidata_id="Q47551",
              sitelinks=108),
    ]
    ranked = most_written_about(cluster_entries([LUTHER_ONE, LUTHER_TWO, *others]), 3)

    assert [item.lead.subject_wikidata_id for item in ranked] == ["Q9554", "Q47551"]


def test_a_bibliography_row_is_ranked_below_a_sentence() -> None:
    assert reads_as_a_record("Martin Luther publishes On the Jews and Their Lies.")
    assert not reads_as_a_record("Andreas Vesalius - De humani corporis fabrica libri septem")


def test_the_lede_is_assembled_from_records_rather_than_written() -> None:
    """The most prominent sentence on the page carries no generated claim at all."""

    nice = entry(
        "The city of Nice is captured by the Ottomans after a long bombardment.",
        month=8,
        day=22,
        subject="Nice",
        wikidata_id="Q33959",
        sitelinks=174,
    )
    ch = chronicle([LUTHER_ONE, LUTHER_TWO, nice])
    lede, headlines = assemble_lede(ch, cluster_entries(ch.entries))

    assert len(headlines) == 2
    assert [headline.subject_title for headline in headlines] == ["Nice", "Martin Luther"]
    # Verbatim, and dated where the source dated it.
    assert headlines[0].text == nice.text
    assert headlines[0].date_text == "22 August"
    assert nice.text in lede and LUTHER_ONE.text in lede


def test_a_year_with_no_prominence_signal_still_gets_a_lede() -> None:
    """A year whose subjects never resolved to Wikidata still has to open somehow."""

    plain = [entry("A ship sailed from a port.", month=3, day=1)]
    lede, headlines = assemble_lede(chronicle(plain), cluster_entries(plain))

    assert headlines and lede.startswith("1 March")


# ---------------------------------------------------------------------------
# The register and the doors out of it
# ---------------------------------------------------------------------------


def test_the_register_carries_every_record_and_both_wordings() -> None:
    ch = chronicle([COPERNICUS_MAIN, COPERNICUS_AGAIN, LUTHER_ONE])
    clusters = cluster_entries(ch.entries)
    register = build_register(ch, clusters, {}, prominent={LUTHER_ONE.entry_id})

    assert len(register) == 2
    death = next(item for item in register if item.kind is ChronicleEntryKind.DEATH)
    assert death.also_recorded_as == [COPERNICUS_AGAIN.text]
    assert death.source_pages == ["1543", "1543 in science"]
    assert death.related_year == 1473
    assert next(item for item in register if item.kind is ChronicleEntryKind.EVENT).prominent


def test_the_other_end_of_a_life_becomes_a_door_to_another_year() -> None:
    born = entry(
        "Tokugawa Ieyasu, Japanese shogun (d. 1616)",
        kind=ChronicleEntryKind.BIRTH,
        subject="Tokugawa Ieyasu",
        wikidata_id="Q171977",
        related_year=1616,
    )
    ch = chronicle([born, COPERNICUS_MAIN])
    related = build_related_years(ch, cluster_entries(ch.entries))

    assert [(item.year, item.direction) for item in related] == [
        (1473, "earlier"),
        (1616, "later"),
    ]
    assert related[1].connections[0].subject_title == "Tokugawa Ieyasu"


def test_a_record_pointing_at_its_own_year_is_not_a_door() -> None:
    same = entry("Somebody died.", kind=ChronicleEntryKind.DEATH, related_year=1543)
    ch = chronicle([same])

    assert build_related_years(ch, cluster_entries(ch.entries)) == []


def test_offices_are_rows_and_the_page_names_the_place() -> None:
    rows = build_incumbents(
        [
            entry("Monarch - Francis I", kind=ChronicleEntryKind.INCUMBENT,
                  source_page="1543 in France"),
            entry("Monarch: Go-Nara", kind=ChronicleEntryKind.INCUMBENT,
                  source_page="1543 in Japan"),
            entry("A battle was fought."),
        ]
    )

    assert [(row.place, row.office, row.holder) for row in rows] == [
        ("France", "Monarch", "Francis I"),
        ("Japan", "Monarch", "Go-Nara"),
    ]


def test_themes_are_counted_not_characterised() -> None:
    ch = chronicle([LUTHER_ONE, LUTHER_TWO])
    themes = build_themes(
        cluster_entries(ch.entries),
        {LUTHER_ONE.entry_id: "belief", LUTHER_TWO.entry_id: "culture"},
        {"belief": "Religion and reform", "culture": "Art, music and letters"},
    )

    assert [(theme.lens, theme.record_count) for theme in themes] == [
        ("belief", 1),
        ("culture", 1),
    ]
    assert themes[0].subjects == ["Martin Luther"]


def test_a_section_link_is_not_the_name_of_anything() -> None:
    assert display_title("Zayyanid dynasty#List of rulers") == "Zayyanid dynasty"
    assert display_title(None) is None


# ---------------------------------------------------------------------------
# Quotation
# ---------------------------------------------------------------------------

BOOK = extract(
    "De revolutionibus orbium coelestium",
    "De revolutionibus orbium coelestium (Latin) is the seminal work of Nicolaus Copernicus. "
    "The book, first printed in 1543 in Nuremberg, offered an alternative model of the universe "
    "to Ptolemy's geocentric system, which had been widely accepted since ancient times.",
    page_id=2,
)
PERSON = extract(
    "Nicolaus Copernicus",
    "Nicolaus Copernicus (19 February 1473 - 24 May 1543) was a Renaissance polymath. "
    "He formulated a model of the universe that placed the Sun rather than Earth at its centre.",
    page_id=3,
)
MODERN = extract(
    "Picardy",
    "Picardy is a historical territory of France. Since 1 January 2016 it has been part of the "
    "new region of Hauts-de-France, which was created by the territorial reform of that year.",
    page_id=4,
)


def test_a_definitional_opener_is_never_the_quotation() -> None:
    """The first sentence of a Wikipedia lead is the least quotable one on the page."""

    quote = build_quote(PERSON, year=1543, names=["Copernicus", "Earth"])

    assert quote is not None
    assert quote.text.startswith("He formulated")


def test_a_passage_about_the_subject_in_general_is_not_quoted() -> None:
    """"Picardy is a historical territory of France" is true and no use beside a siege."""

    assert build_quote(MODERN, year=1543, names=["Landrecies"]) is None


def test_present_day_furniture_is_left_out_of_a_quotation() -> None:
    assert build_quote(MODERN, year=1543, names=["Hauts-de-France"]) is None
    # The same sentence is fair game for a modern year, where it is not furniture.
    assert build_quote(MODERN, year=2016, names=["Hauts-de-France"]) is not None


def test_a_fragment_that_opens_a_bracket_it_never_closes_is_refused() -> None:
    broken = extract(
        "Catherine Parr",
        "Catherine Parr was queen. July or August 1512 - 5 September 1548) was Queen of England "
        "and Ireland as the last of the six wives of King Henry VIII, whom she married in 1543.",
        page_id=5,
    )

    assert build_quote(broken, year=1543, names=["Henry VIII"]) is None


def test_the_article_about_the_thing_is_quoted_before_the_one_about_the_person() -> None:
    quote = quotable(
        [PERSON, BOOK],
        ["Nicolaus Copernicus publishes De revolutionibus orbium coelestium in Nuremberg."],
        ["Nicolaus Copernicus", "De revolutionibus orbium coelestium", "Nuremberg"],
        "Nicolaus Copernicus",
        1543,
    )

    assert quote is not None
    assert quote.source_title == "De revolutionibus orbium coelestium"
    assert "Nuremberg" in quote.text


def test_an_extract_is_reachable_under_the_redirect_it_was_fetched_by() -> None:
    """The Copernicus anchor was written without Copernicus's article behind it once."""

    index = extract_index([extract("Nicolaus Copernicus", "A" * 200, title="Nicholas Copernicus")])

    assert "Nicolaus Copernicus" in index
    assert "Nicholas Copernicus" in index


# ---------------------------------------------------------------------------
# What the year article does not know about itself
# ---------------------------------------------------------------------------


def binding(
    identifier: str,
    label: str,
    start: str,
    end: str,
    sitelinks: str = "10",
    article: str | None = None,
):
    row = {
        "war": {"value": f"http://www.wikidata.org/entity/{identifier}"},
        "warLabel": {"value": label},
        "start": {"value": f"{start}-01-01T00:00:00Z"},
        "end": {"value": f"{end}-01-01T00:00:00Z"},
        "sitelinks": {"value": sitelinks},
    }
    if article:
        row["article"] = {"value": article}
    return row


def test_the_article_title_is_preferred_over_the_wikidata_label() -> None:
    """A Wikidata label is edited by anyone and shows it.

    The 1543 strip carried "Italian War of 1542-46 Un penesote" onto the page. The article title
    for the same item is the name of the war, and it doubles as somewhere a reader wants to go.
    """

    conflicts = parse_conflicts(
        [
            binding(
                "Q5",
                "Italian War of 1542-46 Un penesote",
                "1542",
                "1546",
                article="https://en.wikipedia.org/wiki/Italian_War_of_1542-1546",
            )
        ],
        1543,
    )

    assert conflicts[0].title == "Italian War of 1542-1546"
    assert str(conflicts[0].url).startswith("https://en.wikipedia.org/")


def test_a_war_in_progress_is_kept_and_a_seven_century_label_is_not() -> None:
    """"Anglo-French Wars, 1109 to 1815" is a true label and a false war in progress."""

    conflicts = parse_conflicts(
        [
            binding("Q1", "Ethiopian-Adal War", "1529", "1543", "40"),
            binding("Q2", "Anglo-French Wars", "1109", "1815", "60"),
            binding("Q3", "Italian Wars", "1494", "1559", "50"),
        ],
        1543,
    )

    assert [item.title for item in conflicts] == ["Italian Wars", "Ethiopian-Adal War"]
    assert conflicts[1].ended_this_year
    assert not conflicts[1].began_this_year


def test_a_war_beginning_in_the_selected_year_is_flagged_as_such() -> None:
    conflicts = parse_conflicts([binding("Q4", "A war", "1543", "1550")], 1543)

    assert conflicts[0].began_this_year and not conflicts[0].ended_this_year


def test_a_row_without_a_resolvable_identifier_is_dropped() -> None:
    assert parse_conflicts([{"warLabel": {"value": "Nameless"}}], 1543) == []


def commons_page(license_value: str, **overrides):
    metadata = {
        "License": {"value": license_value},
        "LicenseShortName": {"value": "Public domain"},
        "Artist": {"value": "<span>Unknown author</span>"},
        "Restrictions": {"value": ""},
    }
    metadata.update({key: {"value": value} for key, value in overrides.items()})
    return {
        "title": "File:Portrait.jpg",
        "imageinfo": [
            {
                "url": "https://upload.wikimedia.org/portrait.jpg",
                "thumburl": "https://upload.wikimedia.org/thumb/portrait.jpg",
                "thumbwidth": 720,
                "thumbheight": 900,
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Portrait.jpg",
                "width": 1024,
                "height": 1280,
                "mime": "image/jpeg",
                "extmetadata": metadata,
            }
        ],
    }


def test_a_credit_commons_hides_a_copy_of_is_not_shown_twice() -> None:
    """Commons writes the credit, then repeats it inside a display:none span."""

    image = image_from_commons(
        commons_page("pd"), subject_wikidata_id="Q619", subject_title="Nicolaus Copernicus"
    )

    assert image.attribution.startswith("Unknown author \u2014")


def test_a_public_domain_commons_file_clears_with_its_own_attribution() -> None:
    image = image_from_commons(
        commons_page("pd"), subject_wikidata_id="Q619", subject_title="Nicolaus Copernicus"
    )

    assert image.license_id == "PDM-1.0"
    assert image.width == 720
    assert "Unknown author" in image.attribution


@pytest.mark.parametrize(
    ("page", "reason"),
    [
        (commons_page("cc-by-nc-2.0"), "unrecognised"),
        (commons_page("pd", Restrictions="trademarked"), "restriction"),
        (commons_page("", NonFree="1"), "non-free"),
        (commons_page(""), "unrecognised"),
    ],
)
def test_commons_hosting_is_not_a_licence(page, reason: str) -> None:
    """The licence lives on the file. A file the policy cannot carry is dropped, not captioned."""

    with pytest.raises(ImageRejected, match=reason):
        image_from_commons(page, subject_wikidata_id="Q1", subject_title="Anything")


def test_the_release_policy_decides_which_identified_licence_may_be_carried() -> None:
    """A picture is not a separate rights regime. The same policy governs it as every source."""

    policy = LicensePolicy(mode="commercial", allowed=["PDM-1.0"], denied=[])
    cleared = image_from_commons(
        commons_page("pd"),
        subject_wikidata_id="Q1",
        subject_title="Anything",
        policy=policy,
    )
    assert cleared.license_id == "PDM-1.0"

    # A jurisdiction port is identified as the licence it is, then judged like any other.
    with pytest.raises(ImageRejected, match="not allowed"):
        image_from_commons(
            commons_page("cc-by-sa-3.0-de"),
            subject_wikidata_id="Q2",
            subject_title="Anything",
            policy=policy,
        )
