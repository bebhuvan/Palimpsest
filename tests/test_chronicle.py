from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from history_pipeline.chronicle import (
    _resolved_wikidata_ids,
    _sitelink_counts,
    attach_prominence,
    build_chronicle,
    fetch_year_wikitext,
    parse_year_wikitext,
    summarize,
)
from history_pipeline.models import ChronicleEntryKind, DatePrecision, SourceReference

DASH = "\u2013"

WIKITEXT = """
{{Year nav|1543}}
'''1543''' ('''MDXLIII''') was a [[common year]].

== Events ==
=== JanuaryDASHJune ===
* [[January 4]] &ndash; [[Andrea Centurione Pietrasanta]] begins a term as [[Doge of Genoa|Doge]].
* [[February 21]] &ndash; '''[[Battle of Wayna Daga]]''': A joint force defeats [[Ahmad ibn
Ibrahim al-Ghazi]].<ref>A citation that must not survive.</ref>
** The victory ends the campaign.
=== JulyDASHDecember ===
* [[November 3]] &ndash; A fleet arrives at [[Toulon]].
* [[Nicolaus Copernicus]] publishes ''[[De revolutionibus orbium coelestium]]''.

== Births ==
* [[January 31]] &ndash; [[Tokugawa Ieyasu]], Japanese [[shōgun]] (d. [[1616]])
* [[January 18]] (baptized) &ndash; [[Alfonso Ferrabosco the elder|Alfonso Ferrabosco]], composer

== Deaths ==
* [[January 2]] &ndash; [[Francesco Canova da Milano]], Italian composer (b. [[1497]])

== References ==
* Not an entry.
""".replace("DASH", DASH)

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


def entries():
    return parse_year_wikitext(WIKITEXT, 1543)


def find(text_fragment: str):
    return next(entry for entry in entries() if text_fragment in entry.text)


def test_sections_are_read_into_their_kinds() -> None:
    counts = summarize(
        build_chronicle(
            1543,
            {"wikitext": WIKITEXT, "revid": 1, "pageid": 2},
            language="en",
            source_ref=SOURCE,
            revision_timestamp=datetime(2026, 7, 25, tzinfo=UTC),
            entries=entries(),
        )
    )

    assert counts["event"] == 5
    assert counts["birth"] == 2
    assert counts["death"] == 1
    # The References section is not an entry section and must not leak in.
    assert counts["total"] == 8


def test_a_dated_entry_keeps_its_day_and_drops_the_date_from_its_text() -> None:
    entry = find("Andrea Centurione")

    assert (entry.month, entry.day) == (1, 4)
    assert entry.date_precision == DatePrecision.EXACT
    assert entry.text.startswith("Andrea Centurione Pietrasanta begins")
    assert "January 4" not in entry.text


def test_an_undated_entry_carries_the_year_only() -> None:
    entry = find("Copernicus publishes")

    assert entry.month is None and entry.day is None
    assert entry.date_precision == DatePrecision.YEAR


def test_a_sub_bullet_inherits_the_date_above_it() -> None:
    entry = find("The victory ends")

    assert (entry.month, entry.day) == (2, 21)


def test_markup_citations_and_bold_are_stripped_but_wording_is_kept() -> None:
    entry = find("Battle of Wayna Daga")

    assert "must not survive" not in entry.text
    assert "'''" not in entry.text and "[[" not in entry.text
    assert entry.text.startswith("Battle of Wayna Daga:")


def test_a_qualifier_is_retained_rather_than_discarded() -> None:
    entry = find("Alfonso Ferrabosco")

    assert entry.qualifier == "baptized"


def test_the_subject_is_the_first_link_that_is_not_navigation() -> None:
    """A date article is a navigation link, never what the entry is about."""

    assert find("Tokugawa Ieyasu").subject_title == "Tokugawa Ieyasu"
    assert find("Francesco Canova").subject_title == "Francesco Canova da Milano"
    assert "January 31" in find("Tokugawa Ieyasu").linked_titles


def test_a_companion_year_is_captured_for_births_and_deaths() -> None:
    assert find("Tokugawa Ieyasu").related_year == 1616
    assert find("Francesco Canova").related_year == 1497


def test_entry_ids_are_content_addressed_and_stable() -> None:
    first = {entry.entry_id for entry in parse_year_wikitext(WIKITEXT, 1543)}
    again = {entry.entry_id for entry in parse_year_wikitext(WIKITEXT, 1543)}
    other_year = {entry.entry_id for entry in parse_year_wikitext(WIKITEXT, 1544)}

    assert first == again
    assert not (first & other_year)


def test_entries_are_ordered_by_date_with_undated_last() -> None:
    ordered = entries()
    keys = [(e.month or 13, e.day or 32) for e in ordered]

    assert keys == sorted(keys)
    assert ordered[-1].month is None


def test_a_chronicle_rejects_an_entry_from_another_year() -> None:
    mixed = entries()
    stray = mixed[0].model_copy(update={"year": 1544})

    with pytest.raises(ValueError, match="dated outside its year"):
        build_chronicle(
            1543,
            {"wikitext": WIKITEXT, "revid": 1, "pageid": 2},
            language="en",
            source_ref=SOURCE,
            revision_timestamp=datetime(2026, 7, 25, tzinfo=UTC),
            entries=[stray],
        )


def test_the_chronicle_checksum_covers_the_exact_wikitext() -> None:
    chronicle = build_chronicle(
        1543,
        {"wikitext": WIKITEXT, "revid": 7, "pageid": 2},
        language="en",
        source_ref=SOURCE,
        revision_timestamp=datetime(2026, 7, 25, tzinfo=UTC),
        entries=entries(),
    )

    assert chronicle.content_checksum_sha256 == hashlib.sha256(WIKITEXT.encode()).hexdigest()
    assert chronicle.revision_id == 7
    assert chronicle.chronicle_id == "chronicle:1543:en"


def test_fetch_requires_a_pinned_revision() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"parse": {"wikitext": WIKITEXT, "pageid": 2}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="no pinned revision"):
            fetch_year_wikitext(1543, client=client)


def test_fetch_surfaces_an_api_error_rather_than_returning_nothing() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": "missingtitle"}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="rejected the year request"):
            fetch_year_wikitext(1543, client=client)


def test_redirects_are_followed_when_resolving_subjects_to_wikidata() -> None:
    """Henry VIII of England redirects to Henry VIII; the reader would follow it, so this does."""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "redirects": [{"from": "Henry VIII of England", "to": "Henry VIII"}],
                    "pages": [
                        {"title": "Henry VIII", "pageprops": {"wikibase_item": "Q38370"}}
                    ],
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        resolved = _resolved_wikidata_ids(
            ["Henry VIII of England"], client=client, language="en"
        )

    assert resolved == {"Henry VIII of England": "Q38370"}


def test_sitelink_counts_come_from_wikidata_in_one_batch() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "entities": {
                    "Q38370": {"sitelinks": {f"w{n}": {} for n in range(107)}, "claims": {}},
                    "Q1794": {
                        "sitelinks": {f"w{n}": {} for n in range(60)},
                        "claims": {"P625": [{}]},
                    },
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        counts, places = _sitelink_counts(["Q38370", "Q1794"], client=client)

    assert counts == {"Q38370": 107, "Q1794": 60}
    # A coordinate is what makes something a place, and only places carry one.
    assert places == {"Q1794"}


def test_an_event_prefers_a_subject_that_is_not_a_place() -> None:
    """"In Nuremberg, De revolutionibus is printed" is about the book, not the city."""

    entry = find("Copernicus publishes")
    resolved = attach_prominence(
        [entry],
        {"Nicolaus Copernicus": "Q619", "De revolutionibus orbium coelestium": "Q1191248"},
        {"Q619": 213, "Q1191248": 40},
        places={"Q619"},
    )[0]

    assert resolved.subject_title == "De revolutionibus orbium coelestium"


def test_a_death_keeps_its_person_even_though_a_person_is_not_a_place() -> None:
    resolved = attach_prominence(
        [find("Francesco Canova")],
        {"Francesco Canova da Milano": "Q1394"},
        {"Q1394": 30},
        places=set(),
    )[0]

    assert resolved.subject_title == "Francesco Canova da Milano"


def test_prominence_is_attached_without_touching_the_source_wording() -> None:
    parsed = entries()
    before = {entry.entry_id: entry.text for entry in parsed}
    resolved = attach_prominence(
        parsed,
        {"Tokugawa Ieyasu": "Q10850"},
        {"Q10850": 85},
    )

    tokugawa = next(e for e in resolved if e.subject_title == "Tokugawa Ieyasu")
    assert tokugawa.sitelink_count == 85
    assert tokugawa.subject_wikidata_id == "Q10850"
    # Everything else keeps a null count rather than a guessed one.
    assert all(e.sitelink_count is None for e in resolved if e.subject_title != "Tokugawa Ieyasu")
    assert {e.entry_id: e.text for e in resolved} == before


def test_a_subject_must_be_one_of_the_entry_links() -> None:
    entry = find("Tokugawa Ieyasu")

    with pytest.raises(ValueError, match="must be one of the entry"):
        entry.model_copy(update={"subject_title": "Someone Else"}).model_validate(
            json.loads(
                entry.model_copy(update={"subject_title": "Someone Else"}).model_dump_json()
            )
        )


def test_kinds_cover_events_births_and_deaths() -> None:
    kinds = {entry.kind for entry in entries()}

    assert kinds == {
        ChronicleEntryKind.EVENT,
        ChronicleEntryKind.BIRTH,
        ChronicleEntryKind.DEATH,
    }


def test_a_bullet_with_a_date_and_no_content_is_not_an_entry() -> None:
    """The 1543 article really contains "* [[March 7]] &ndash; " with nothing after it."""

    empty = WIKITEXT.replace(
        "== Deaths ==",
        "* [[March 7]] &ndash; \n\n== Deaths ==",
    )
    texts = [entry.text for entry in parse_year_wikitext(empty, 1543)]

    assert "March 7" not in texts


def test_grouping_labels_are_not_read_as_entries() -> None:
    """"date unknown" is a sub-heading in a year article, and it is written as a bullet."""

    grouped = WIKITEXT.replace(
        "== Deaths ==",
        "* '''date unknown'''\n* probable\n\n== Deaths ==",
    )
    texts = {entry.text.casefold() for entry in parse_year_wikitext(grouped, 1543)}

    assert "date unknown" not in texts
    assert "probable" not in texts


def test_a_companion_page_writes_the_day_before_the_month() -> None:
    """Accepting only "July 1" discarded the date on every country and topic page."""

    wikitext = (
        "== Events ==\n"
        "* 9 September \u2013 Coronation of [[Mary, Queen of Scots]] at [[Stirling]].\n"
        "* June \u2013 [[Andreas Vesalius]] publishes [[De humani corporis fabrica]].\n"
        "* September\u2013October \u2013 [[Landrecies]] is besieged.\n"
        "* approximate date \u2013 [[William Clowes (surgeon)|William Clowes]] is born.\n"
    )
    parsed = parse_year_wikitext(wikitext, 1543)

    def find(fragment: str):
        return next(entry for entry in parsed if fragment in entry.text)

    coronation = find("Coronation")
    assert (coronation.month, coronation.day) == (9, 9)
    vesalius = find("Vesalius")
    assert (vesalius.month, vesalius.day) == (6, None)
    assert vesalius.date_precision is DatePrecision.YEAR
    # A span is dated from where it began.
    assert find("Landrecies").month == 9
    # An uncertainty the source stated belongs in the qualifier, not in the sentence.
    clowes = find("Clowes")
    assert clowes.month is None
    assert clowes.qualifier == "approximate date"


def test_a_grouping_label_is_not_a_record_but_a_two_word_name_is() -> None:
    """"Also" and "In France" introduce a run of bullets; "James Tyrie" is a person."""

    wikitext = (
        "== Births ==\n"
        "* Also\n"
        "* In France\n"
        "* [[James Tyrie]]\n"
    )
    texts = [entry.text for entry in parse_year_wikitext(wikitext, 1543)]

    assert texts == ["James Tyrie"]


def test_a_coordinate_alone_does_not_make_something_a_place() -> None:
    """Wikidata gives the Alhambra Decree the coordinates of the Alhambra.

    Reading P625 on its own made the record about the decree into a record about Roman
    Catholicism, because the decree was skipped as scenery and the next link won.
    """

    from history_pipeline.chronicle import NON_PLACE_CLASSES, _is_classed_as

    decree = {
        "P625": [{}],
        "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q49848"}}}}],
    }
    city = {
        "P625": [{}],
        "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q515"}}}}],
    }

    assert _is_classed_as(decree, NON_PLACE_CLASSES)
    assert not _is_classed_as(city, NON_PLACE_CLASSES)


def test_an_event_is_about_what_happened_not_where() -> None:
    """"In Nuremberg, a book is printed" is about the book. That rule still has to hold."""

    from history_pipeline.chronicle import choose_subject
    from history_pipeline.models import ChronicleEntry, ChronicleEntryKind, DatePrecision

    entry = ChronicleEntry(
        entry_id="chronicle:1543:event:" + "a" * 16,
        kind=ChronicleEntryKind.EVENT,
        year=1543,
        date_precision=DatePrecision.YEAR,
        text="In Nuremberg, De revolutionibus orbium coelestium is printed.",
        linked_titles=["Nuremberg", "De revolutionibus orbium coelestium"],
    )
    ids = {"Nuremberg": "Q2090", "De revolutionibus orbium coelestium": "Q1069422"}

    assert choose_subject(entry, ids, {"Q2090"}) == "De revolutionibus orbium coelestium"
    # And a decree no longer counted as a place wins over what follows it.
    decree = entry.model_copy(
        update={
            "text": "Ferdinand and Isabella sign the Alhambra Decree.",
            "linked_titles": ["Alhambra Decree", "Roman Catholicism"],
        }
    )
    assert (
        choose_subject(
            decree,
            {"Alhambra Decree": "Q1061030", "Roman Catholicism": "Q1841"},
            set(),
        )
        == "Alhambra Decree"
    )
