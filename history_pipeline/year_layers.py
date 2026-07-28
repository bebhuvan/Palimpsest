"""Everything in a year dossier that nobody has to write.

The dossier has one known, unfixed failure mode: a containment check can prove every name and
number came from the evidence and cannot prove the relationship asserted between them. Two true
facts fuse into a false third, and every additional generated sentence is another chance to do it.

That makes the split in this module the important one. Depth assembled from records is free —
the register, the headlines, the cross-links, the incumbent rows and the conflict list are the
source's own words and numbers, rearranged, and no rearrangement can fuse anything. Depth written
as prose is not free. So the dossier gets most of its size from here, and the model is left with
the smaller job it is actually good at.

Nothing in this module contacts a model. The two functions that reach the network (`fetch_conflicts`
and `fetch_images`) read Wikidata and Commons, and both record what they were told rather than
deciding anything.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import unquote

import httpx
from pydantic import HttpUrl

from history_pipeline.chronicle import MONTHS
from history_pipeline.config import LicensePolicy
from history_pipeline.licenses import LicenseRejectedError, enforce_license
from history_pipeline.models import (
    ChronicleEntry,
    ChronicleEntryKind,
    DatePrecision,
    SubjectExtract,
    YearChronicle,
    YearConflict,
    YearConnection,
    YearContext,
    YearHeadline,
    YearImage,
    YearIncumbent,
    YearQuote,
    YearRegisterEntry,
    YearRelatedYear,
    YearTheme,
    YearWork,
)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# How many of the year's most-written-about records open the dossier.
HEADLINE_COUNT = 3
# How many happenings get a section of their own. Enough that a reader who scrolls finds several
# things worth stopping at; few enough that each can be given real room.
ANCHOR_COUNT = 8
# A war Wikidata dates across seven centuries is a category of warfare, not a war that was under
# way. Keeping them would bury the ones a reader can actually place in the year.
MAXIMUM_CONFLICT_SPAN_YEARS = 150
MAXIMUM_CONFLICTS = 12


def display_title(title: str | None) -> str | None:
    """A wiki title as a reader should see it.

    A year article often links to a section — "Zayyanid dynasty#List of rulers" — and the fragment
    is a route through Wikipedia rather than the name of anything.
    """

    if not title:
        return None
    return title.split("#", 1)[0].replace("_", " ").strip() or None


def date_text(month: int | None, day: int | None) -> str | None:
    """A date the way prose says it, or nothing when the source did not give one."""

    if month is None:
        return None
    if day is None:
        return MONTHS[month - 1]
    return f"{day} {MONTHS[month - 1]}"


_WORD = re.compile(r"[A-Za-zÀ-ɏ]+|\d+")
# Words carried by almost every entry, which would make any two look alike.
_STOPWORDS = frozenset(
    """a an and are as at be been by for from in into is it its of on or that the their to
    with which who whom whose was were will would he she they his her him them this these those
    after before during over under between against also new first""".split()
)


def _significant(text: str) -> set[str]:
    return {
        word.casefold()
        for word in _WORD.findall(text)
        if word.casefold() not in _STOPWORDS and len(word) > 2
    }


def _same_happening(left: ChronicleEntry, right: ChronicleEntry) -> bool:
    """Two records of one happening, or one record each of two.

    Wikipedia documents a year across a main article and a dozen topic and country pages, and the
    same event is written up on several of them in different words. Left alone, the reader meets
    Copernicus's death three times and the dossier's own prose repeats itself.

    Subject alone is not enough to merge on: Henry VIII made an alliance in February and a
    marriage in July, and merging those would delete an event. So a merge needs a compatible date
    and a majority of the shorter record's substantive words in common — which is also what lets
    a dated record on a country page supply the date the main article omitted.
    """

    if left.subject_wikidata_id is None or left.subject_wikidata_id != right.subject_wikidata_id:
        return False
    if left.kind is not right.kind:
        return False
    dates = {(left.month, left.day), (right.month, right.day)}
    if len(dates) > 1 and (None, None) not in dates:
        return False
    first, second = _significant(left.text), _significant(right.text)
    if not first or not second:
        return False
    return len(first & second) / min(len(first), len(second)) >= 0.6


class EntryCluster:
    """Several records of one happening, held together with the fullest of them in front."""

    __slots__ = ("members",)

    def __init__(self, members: list[ChronicleEntry]) -> None:
        self.members = members

    @property
    def lead(self) -> ChronicleEntry:
        """The record that says the most. Length is a poor measure of quality and a good one of
        detail, and detail is what a second wording is kept for."""

        return max(self.members, key=lambda entry: (len(entry.text), entry.entry_id))

    @property
    def entry_id(self) -> str:
        return self.lead.entry_id

    @property
    def entry_ids(self) -> list[str]:
        return [entry.entry_id for entry in self.members]

    @property
    def kind(self) -> ChronicleEntryKind:
        return self.lead.kind

    @property
    def month(self) -> int | None:
        return next((entry.month for entry in self.members if entry.month is not None), None)

    @property
    def day(self) -> int | None:
        dated = next(
            (entry for entry in self.members if entry.month is not None and entry.day is not None),
            None,
        )
        return dated.day if dated else None

    @property
    def sitelink_count(self) -> int | None:
        counts = [entry.sitelink_count for entry in self.members if entry.sitelink_count]
        return max(counts) if counts else None

    @property
    def related_years(self) -> list[int]:
        return sorted({entry.related_year for entry in self.members if entry.related_year})

    @property
    def source_pages(self) -> list[str]:
        return sorted({entry.source_page for entry in self.members if entry.source_page})

    @property
    def texts(self) -> list[str]:
        lead = self.lead
        return [lead.text] + [
            entry.text for entry in self.members if entry.entry_id != lead.entry_id
        ]

    def lens(self, lenses: Mapping[str, str]) -> str | None:
        for entry in self.members:
            found = entry.lens or lenses.get(entry.entry_id)
            if found:
                return found
        return None


def cluster_entries(entries: Sequence[ChronicleEntry]) -> list[EntryCluster]:
    """Collapse repeated records of one happening, keeping every one of them.

    Grouping is by Wikidata subject first, so the comparison never runs across the whole year: an
    entry with no resolved subject is its own cluster and is never merged, because without an
    identifier there is nothing solid to merge on.
    """

    by_subject: dict[str, list[ChronicleEntry]] = {}
    singles: list[EntryCluster] = []
    for entry in entries:
        if entry.subject_wikidata_id:
            by_subject.setdefault(entry.subject_wikidata_id, []).append(entry)
        else:
            singles.append(EntryCluster([entry]))
    clusters: list[EntryCluster] = list(singles)
    for group in by_subject.values():
        pending = list(group)
        while pending:
            head = pending.pop(0)
            members = [head]
            rest: list[ChronicleEntry] = []
            for candidate in pending:
                if any(_same_happening(member, candidate) for member in members):
                    members.append(candidate)
                else:
                    rest.append(candidate)
            pending = rest
            clusters.append(EntryCluster(members))
    return sorted(
        clusters,
        key=lambda cluster: (
            cluster.month or 13,
            cluster.day or 32,
            cluster.kind.value,
            cluster.lead.text,
        ),
    )


def collapse_duplicates(
    entries: Sequence[ChronicleEntry],
) -> tuple[list[ChronicleEntry], dict[str, list[str]]]:
    """The representative record of each happening, and what each one stands for.

    Section planning and the prose that follows work on this list, so a paragraph cannot narrate
    the same event twice under two lenses. The register still shows every record.
    """

    clusters = cluster_entries(entries)
    represented = {cluster.entry_id: cluster.entry_ids for cluster in clusters}
    # The representative carries the cluster's date, not its own. Clustering is what recovers a
    # date the main article left off — the Vesalius publication is undated on the year page and
    # dated June on the science page — and returning the bare lead threw that back away, so a
    # section was checked against evidence that no longer said "June" while its prose did.
    return [
        cluster.lead.model_copy(
            update={
                "month": cluster.month,
                "day": cluster.day,
                "date_precision": (
                    DatePrecision.EXACT if cluster.day is not None else DatePrecision.YEAR
                ),
            }
        )
        for cluster in clusters
    ], represented


def _url_for(title: str | None, extracts: Mapping[str, SubjectExtract]) -> HttpUrl | None:
    found = extracts.get(title or "")
    return found.url if found else None


def extract_index(extracts: Iterable[SubjectExtract]) -> dict[str, SubjectExtract]:
    """Look an article up by any title that reaches it.

    An extract is fetched under the title some entry linked and stored under its canonical one,
    and the fetch keeps one article per page ID. So the lead of "Nicolaus Copernicus" ended up
    filed under "Nicholas Copernicus" — the redirect a different entry happened to use — and every
    lookup by the canonical title missed it. The Copernicus anchor was written without Copernicus's
    own article behind it, which is how "Frombork" became an unsupported name in a paragraph about
    a man who died there.
    """

    index: dict[str, SubjectExtract] = {}
    for extract in extracts:
        index.setdefault(extract.title, extract)
        index.setdefault(extract.canonical_title, extract)
        index.setdefault(extract.title.split("#", 1)[0], extract)
    return index


def _extract_index(chronicle: YearChronicle) -> dict[str, SubjectExtract]:
    return extract_index(chronicle.subject_extracts)


# An author, a dash and a title is a row in a bibliography, not a sentence about a year. It
# belongs in the register and reads badly anywhere a paragraph is expected, so it is ranked last
# rather than dropped.
_BIBLIOGRAPHIC = re.compile("^[^.]{2,60}\\s+[\u2013\u2014-]\\s+\\S")


def reads_as_a_record(text: str) -> bool:
    return not _BIBLIOGRAPHIC.match(text)


def most_written_about(
    clusters: Sequence[EntryCluster],
    limit: int,
    *,
    kinds: Iterable[str] = ("event",),
    one_per_subject: bool = True,
) -> list[EntryCluster]:
    """Rank by how many language editions cover the subject, never by importance.

    This is a fact about how much has been written, and the reader is told so. It is used because
    it is the only ranking available that nobody in this pipeline chose.

    The count belongs to the subject rather than to the happening, so a famous person with three
    records takes the whole top of the list unless something stops them: ranking 1543 by sitelinks
    alone gave Martin Luther the first two places and Copernicus the next two. One per subject
    stops it, and within a subject the record that reads as a sentence and carries a date wins.
    """

    wanted = set(kinds)
    candidates = [
        cluster
        for cluster in clusters
        if cluster.kind.value in wanted and cluster.sitelink_count
    ]
    ranked = sorted(
        candidates,
        key=lambda cluster: (
            -(cluster.sitelink_count or 0),
            not reads_as_a_record(cluster.lead.text),
            cluster.month is None,
            -len(cluster.lead.text),
            cluster.entry_id,
        ),
    )
    if not one_per_subject:
        return ranked[:limit]
    chosen: list[EntryCluster] = []
    seen: set[str] = set()
    for cluster in ranked:
        subject = cluster.lead.subject_wikidata_id
        if subject and subject in seen:
            continue
        if subject:
            seen.add(subject)
        chosen.append(cluster)
        if len(chosen) == limit:
            break
    return chosen


def assemble_lede(
    chronicle: YearChronicle,
    clusters: Sequence[EntryCluster],
    count: int = HEADLINE_COUNT,
) -> tuple[str, list[YearHeadline]]:
    """Build the lede out of records instead of asking for one.

    The first sentence a reader meets is the most prominent claim on the page and the one they are
    least able to check, which makes it the worst possible place to let two facts fuse. Assembling
    it removes the risk rather than testing for it, and costs nothing: the year's three
    most-written-about records, in the source's own words, are a better opening than a summary of
    them would be.
    """

    extracts = _extract_index(chronicle)
    ranked = most_written_about(clusters, count)
    if not ranked:
        # A year whose subjects never resolved to Wikidata has no prominence signal at all. It
        # still needs an opening, and the earliest events are a defensible one: chosen by the
        # calendar, which is nobody's judgement either.
        ranked = [
            cluster for cluster in clusters if cluster.kind is ChronicleEntryKind.EVENT
        ][:count]
    headlines: list[YearHeadline] = []
    for cluster in ranked:
        lead = cluster.lead
        headlines.append(
            YearHeadline(
                entry_id=lead.entry_id,
                date_text=date_text(cluster.month, cluster.day),
                text=lead.text,
                subject_title=display_title(lead.subject_title),
                subject_url=_url_for(lead.subject_title, extracts),
                sitelink_count=cluster.sitelink_count,
            )
        )
    headlines.sort(key=lambda headline: (headline.text,))
    ordered = sorted(
        headlines,
        key=lambda headline: _sort_key(headline.date_text),
    )
    lede = " ".join(
        (f"{headline.date_text}: {headline.text}" if headline.date_text else headline.text)
        for headline in ordered
    )
    return lede, ordered


def _sort_key(text: str | None) -> tuple[int, int]:
    if not text:
        return (13, 32)
    parts = text.split()
    if len(parts) == 1:
        return (MONTHS.index(parts[0]) + 1 if parts[0] in MONTHS else 13, 0)
    return (MONTHS.index(parts[1]) + 1 if parts[1] in MONTHS else 13, int(parts[0]))


# What the year article's own section headings and companion pages say a record is. The page is a
# better signal than the heading: "Works published" means a poem on the poetry page and a book on
# the literature page.
WorkKind = Literal["book", "poem", "artwork", "music", "building", "work"]
_WORK_TOPICS = frozenset(
    {
        "New books", "Works", "Works published", "Publications", "Paintings", "Sculpture",
        "Architecture", "Buildings", "Music", "Poetry", "Prose", "Drama", "Literature",
    }
)
_WORK_KINDS: tuple[tuple[str, WorkKind], ...] = (
    ("in poetry", "poem"),
    ("in art", "artwork"),
    ("in music", "music"),
    ("in architecture", "building"),
    ("in literature", "book"),
)
_TOPIC_KINDS: dict[str, WorkKind] = {
    "New books": "book",
    "Publications": "book",
    "Prose": "book",
    "Drama": "book",
    "Literature": "book",
    "Poetry": "poem",
    "Paintings": "artwork",
    "Sculpture": "artwork",
    "Architecture": "building",
    "Buildings": "building",
    "Music": "music",
}
# "Andreas Vesalius - De humani corporis fabrica libri septem (On the Fabric of the Human Body)".
CREATOR_TITLE = re.compile(r"^(?P<creator>[^.]{2,70}?)\s+[\u2013\u2014-]\s+(?P<title>\S.*)$")


def work_kind(topic: str | None, source_page: str | None) -> WorkKind:
    for suffix, kind in _WORK_KINDS:
        if (source_page or "").endswith(suffix):
            return kind
    return _TOPIC_KINDS.get(topic or "", "work")


def build_works(
    clusters: Sequence[EntryCluster],
    extracts: Mapping[str, SubjectExtract],
) -> list[YearWork]:
    """What the year records as made, as rows rather than a paragraph of commas."""

    works: list[YearWork] = []
    for cluster in clusters:
        lead = cluster.lead
        if lead.topic not in _WORK_TOPICS:
            continue
        matched = CREATOR_TITLE.match(lead.text)
        creator = matched.group("creator").strip() if matched else None
        title = matched.group("title").strip() if matched else lead.text
        works.append(
            YearWork(
                entry_id=lead.entry_id,
                kind=work_kind(lead.topic, lead.source_page),
                creator=creator,
                title=title,
                subject_title=display_title(lead.subject_title),
                subject_url=_url_for(lead.subject_title, extracts),
                sitelink_count=cluster.sitelink_count,
                source_page=lead.source_page,
                # Deliberately no picture. The subject of "Titian - Ecce Homo" resolves to
                # Titian, so the only image available is a portrait of the painter, and a
                # portrait of Titian captioned "Ecce Homo" is a caption that lies. Showing the
                # work itself needs the work's own Wikidata item, which the chronicle does not
                # carry yet.
            )
        )
    order = {"book": 0, "poem": 1, "artwork": 2, "music": 3, "building": 4, "work": 5}
    return sorted(
        works,
        key=lambda work: (
            order[work.kind],
            -(work.sitelink_count or 0),
            work.title,
        ),
    )


def month_counts(clusters: Sequence[EntryCluster]) -> tuple[list[int], int]:
    """How many records fall in each month, and how many carry no month at all."""

    months = [0] * 12
    undated = 0
    for cluster in clusters:
        if cluster.month:
            months[cluster.month - 1] += 1
        else:
            undated += 1
    return months, undated


def build_register(
    chronicle: YearChronicle,
    clusters: Sequence[EntryCluster],
    lenses: Mapping[str, str],
    prominent: Iterable[str] = (),
    images: Mapping[str, YearImage] | None = None,
) -> list[YearRegisterEntry]:
    """Every happening the year recorded, in the source's own words.

    This is the floor of the dossier and the reason the prose above it is allowed to be selective.
    Nothing here is generated, so it can be exhaustive at no risk: a record no paragraph found
    room for still reaches the reader, dated, attributed and linked.
    """

    extracts = _extract_index(chronicle)
    marked = set(prominent)
    register: list[YearRegisterEntry] = []
    for cluster in clusters:
        lead = cluster.lead
        texts = cluster.texts
        register.append(
            YearRegisterEntry(
                entry_id=lead.entry_id,
                kind=cluster.kind,
                month=cluster.month,
                day=cluster.day,
                date_text=date_text(cluster.month, cluster.day),
                text=texts[0],
                also_recorded_as=texts[1:],
                qualifier=lead.qualifier,
                subject_title=display_title(lead.subject_title),
                subject_url=_url_for(lead.subject_title, extracts),
                subject_wikidata_id=lead.subject_wikidata_id,
                sitelink_count=cluster.sitelink_count,
                related_year=next(iter(cluster.related_years), None),
                source_pages=cluster.source_pages,
                topic=lead.topic,
                lens=cluster.lens(lenses),
                prominent=lead.entry_id in marked,
                image=(images or {}).get(lead.subject_wikidata_id or ""),
            )
        )
    return register


def build_related_years(
    chronicle: YearChronicle,
    clusters: Sequence[EntryCluster],
) -> list[YearRelatedYear]:
    """The other end of every life the year records.

    A birth entry carries the year of the death and a death entry the year of the birth. Both are
    already parsed out of the source, and following one is the cheapest way out of a page that
    exists: it leads somewhere the reader had no reason to expect and did not choose.
    """

    extracts = _extract_index(chronicle)
    grouped: dict[int, list[YearConnection]] = {}
    for cluster in clusters:
        lead = cluster.lead
        for year in cluster.related_years:
            if year == chronicle.year:
                continue
            grouped.setdefault(year, []).append(
                YearConnection(
                    entry_id=lead.entry_id,
                    kind=cluster.kind,
                    text=lead.text,
                    subject_title=display_title(lead.subject_title),
                    subject_url=_url_for(lead.subject_title, extracts),
                )
            )
    return [
        YearRelatedYear(
            year=year,
            direction="earlier" if year < chronicle.year else "later",
            connections=sorted(connections, key=lambda item: item.entry_id),
        )
        for year, connections in sorted(grouped.items())
    ]


_OFFICE = re.compile(
    "^\\s*(?P<office>[^:\u2013\u2014-]{2,40}?)\\s*[:\u2013\u2014-]\\s*(?P<holder>.+)$"
)
_PLACE = re.compile(r"^\d{1,4}\s+in\s+(?:the\s+)?(?P<place>.+)$")


def build_incumbents(entries: Sequence[ChronicleEntry]) -> list[YearIncumbent]:
    """Who held which office, as rows.

    Asked for as prose this came back as a row of dashes, which is the source telling us what it
    already was. The page it came from names the place, so the table has a first column without
    anybody having to infer one.
    """

    rows: list[YearIncumbent] = []
    for entry in entries:
        if entry.kind is not ChronicleEntryKind.INCUMBENT:
            continue
        matched = _OFFICE.match(entry.text)
        if not matched:
            continue
        place = _PLACE.match(entry.source_page or "")
        rows.append(
            YearIncumbent(
                entry_id=entry.entry_id,
                place=place.group("place") if place else (entry.source_page or "Unstated"),
                office=matched.group("office").strip(),
                holder=matched.group("holder").strip(),
            )
        )
    return sorted(rows, key=lambda row: (row.place, row.office, row.holder))


def build_themes(
    clusters: Sequence[EntryCluster],
    lenses: Mapping[str, str],
    headings: Mapping[str, str],
) -> list[YearTheme]:
    """How the year's records fall across the lenses, counted rather than characterised."""

    counted: dict[str, list[EntryCluster]] = {}
    for cluster in clusters:
        if cluster.kind is not ChronicleEntryKind.EVENT:
            continue
        lens = cluster.lens(lenses)
        if lens:
            counted.setdefault(lens, []).append(cluster)
    themes: list[YearTheme] = []
    for lens, heading in headings.items():
        group = counted.get(lens, [])
        if not group:
            continue
        subjects = [
            name
            for cluster in most_written_about(group, 5)
            if (name := display_title(cluster.lead.subject_title))
        ]
        themes.append(
            YearTheme(
                lens=lens,
                heading=heading,
                record_count=len(group),
                subjects=subjects,
            )
        )
    return sorted(themes, key=lambda theme: -theme.record_count)


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ɏ“])")
# What a Wikipedia lead opens with: a name, a bracketed pronunciation, a pair of life dates and
# a job title. It is the least quotable sentence on the page, tells a reader nothing they came
# for, and the phonetic brackets look broken beside prose.
_DEFINITIONAL = re.compile(
    r"^\S[^(]{0,60}\([^)]{0,200}\)\s+(?:was|is|were|are)\b"
    r"|^\S[^,]{0,60},?\s+(?:born|né|née)\b"
    r"|\[[^\]]*[ˈˌːəɪʊɐʁ][^\]]*\]"
    r"|;\s*(?:German|French|Italian|Spanish|Latin|Polish|Turkish|Greek|Russian):"
)
# A sentence with nothing in it, or one that is mostly apparatus.
_MODERN_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
MINIMUM_QUOTE_CHARS = 80
MAXIMUM_QUOTE_CHARS = 420


def _balanced(text: str) -> bool:
    """A fragment that opens a bracket it never closes was cut out of a longer sentence."""

    depth = 0
    for character in text:
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def build_quote(
    extract: SubjectExtract,
    *,
    year: int | None = None,
    names: Sequence[str] = (),
    sentences: int = 2,
) -> YearQuote | None:
    """A quotable passage from one article lead, kept as the source wrote it.

    A quotation asserts nothing beyond having been said, which is why it is the one way to add
    length to a dossier that carries no risk at all. It is bound to the revision it was taken
    from, so it goes stale with everything else rather than drifting.

    Two things disqualify a passage. The first sentence of a Wikipedia lead is a definition with a
    pronunciation and a pair of dates in it, which is the least quotable sentence on the page. And
    a lead that never mentions the year or anything the record names is about the subject in
    general rather than about this — "Hungary is a landlocked country in Central Europe" is true,
    sourced, and no use to a reader standing in 1543. Returning nothing is the right answer for
    both; an anchor without a quotation is not a broken anchor.
    """

    parts = [part.strip() for part in _SENTENCE.split(extract.extract.strip()) if part.strip()]
    # The article's own name is in every sentence of it, so it cannot be evidence that a sentence
    # is about anything in particular. Without this, "Hungary is a landlocked country in Central
    # Europe" counted as relevant to an Ottoman campaign because it says Hungary.
    own = extract.canonical_title.casefold()
    wanted = {
        name
        for name in names
        if len(name) > 3 and name.casefold() not in own and own not in name.casefold()
    }
    start = None
    for index, part in enumerate(parts):
        if _DEFINITIONAL.search(part) or len(part) < 40 or not _balanced(part):
            continue
        # Present-day administrative furniture. "Since 1 January 2016, it has been part of the new
        # region of Hauts-de-France" is true of Picardy and no use beside a siege in 1543. The
        # restatement tier treats the same material the same way: it does not make anything
        # untrue, it makes the passage worse at its job.
        if year is not None and year < 1900 and _MODERN_YEAR.search(part):
            continue
        relevant = (year is not None and str(year) in part) or any(
            name in part for name in wanted
        )
        if relevant:
            start = index
            break
    if start is None:
        return None
    text = ""
    for part in parts[start : start + sentences]:
        if not _balanced(part):
            break
        candidate = f"{text} {part}".strip()
        if len(candidate) > MAXIMUM_QUOTE_CHARS and text:
            break
        text = candidate
    if len(text) < MINIMUM_QUOTE_CHARS or not _balanced(text):
        return None
    return YearQuote(
        text=text,
        source_title=extract.canonical_title,
        source_url=extract.url,
        revision_id=extract.revision_id,
        content_checksum_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def quotable(
    background: Sequence[SubjectExtract],
    records: Sequence[str],
    linked_titles: Sequence[str],
    subject_title: str | None,
    year: int | None = None,
) -> YearQuote | None:
    """Find the one passage in an anchor's background worth showing as itself.

    An anchor on the printing of a book has both a biography and the book behind it. The biography
    is the one the writer needed and the book is the one the reader wants a sentence of, so the
    article the record actually names is tried first.
    """

    text = " ".join(records)
    # What the records link to, rather than every capitalised word in them. A wikilink is the
    # source naming an entity; a regex over capitals also returns "Campaign" and "The", which then
    # match almost any sentence and let a modern geography lead pass as relevant.
    names = {display_title(title) or title for title in linked_titles}
    named = [
        item
        for item in background
        if item.canonical_title != subject_title and item.canonical_title in text
    ]
    for candidate in (*named, *background):
        quote = build_quote(candidate, year=year, names=sorted(names))
        if quote is not None:
            return quote
    return None


def anchor_id(entry_id: str) -> str:
    return f"anchor:{hashlib.sha256(entry_id.encode('utf-8')).hexdigest()[:16]}"


# ---------------------------------------------------------------------------
# What the year article does not know about itself
# ---------------------------------------------------------------------------

# The English Wikipedia article title is asked for alongside the Wikidata label, and preferred.
# A Wikidata label is edited by anyone and shows it: the 1543 strip carried "Italian War of
# 1542-46 Un penesote" straight onto the page. The article title for the same item is "Italian War
# of 1542-1546", and it doubles as somewhere a reader would actually want to go.
_CONFLICT_QUERY = """
SELECT ?war ?warLabel ?article ?start ?end ?sitelinks WHERE {{
  ?war wdt:P31/wdt:P279* wd:Q198 .
  ?war wdt:P580 ?start .
  ?war wdt:P582 ?end .
  ?war wikibase:sitelinks ?sitelinks .
  FILTER(YEAR(?start) <= {year} && YEAR(?end) >= {year})
  OPTIONAL {{
    ?article schema:about ?war ; schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 300
"""


def parse_conflicts(bindings: Sequence[Mapping[str, Any]], year: int) -> list[YearConflict]:
    """Turn a SPARQL result into wars that were under way, and drop the ones that were not.

    Wikidata dates "Anglo-French Wars" from 1109 to 1815. That is a true statement about a label
    and a false one about a war in progress, and shown beside a war of fifteen years it would
    teach a reader to distrust the whole strip. The span filter is the honest way to say we cannot
    tell the two apart: it drops the class instead of ranking within it.
    """

    conflicts: list[YearConflict] = []
    for row in bindings:
        try:
            identifier = str(row["war"]["value"]).rsplit("/", 1)[-1]
            title = str(row["warLabel"]["value"])
            start = int(str(row["start"]["value"])[:5].lstrip("-")[:4])
            end = int(str(row["end"]["value"])[:5].lstrip("-")[:4])
        except (KeyError, ValueError):
            continue
        if not identifier.startswith("Q") or identifier == title:
            continue
        article = (row.get("article") or {}).get("value")
        if isinstance(article, str) and article.startswith("https://en.wikipedia.org/"):
            title = unquote(article.rsplit("/", 1)[-1]).replace("_", " ")
        if end - start > MAXIMUM_CONFLICT_SPAN_YEARS or end < start:
            continue
        sitelinks = row.get("sitelinks")
        conflicts.append(
            YearConflict(
                wikidata_id=identifier,
                title=title,
                url=HttpUrl(
                    article
                    if isinstance(article, str) and article.startswith("https://")
                    else f"https://www.wikidata.org/wiki/{identifier}"
                ),
                start_year=start,
                end_year=end,
                began_this_year=start == year,
                ended_this_year=end == year,
                sitelink_count=int(sitelinks["value"]) if sitelinks else None,
            )
        )
    deduplicated = {conflict.wikidata_id: conflict for conflict in conflicts}
    return sorted(
        deduplicated.values(),
        key=lambda conflict: (-(conflict.sitelink_count or 0), conflict.wikidata_id),
    )[:MAXIMUM_CONFLICTS]


def fetch_conflicts(year: int, *, client: httpx.Client) -> list[YearConflict]:
    response = client.post(
        WIKIDATA_SPARQL,
        data={"query": _CONFLICT_QUERY.format(year=year)},
        headers={"Accept": "application/sparql-results+json"},
    )
    response.raise_for_status()
    return parse_conflicts(response.json().get("results", {}).get("bindings", []), year)


# Commons `extmetadata` reports a licence per file, in its own vocabulary. This maps that
# vocabulary onto the SPDX-style identifiers the release policy is written in; it does not decide
# anything. Whether an identified licence may be carried is `config/pipeline.yml`'s decision, made
# by the same `enforce_license` that governs every other source in the build — a picture is not a
# separate rights regime because it is a picture.
#
# The map is deliberately explicit rather than pattern-matched: "cc-by-nc-sa-3.0" and
# "cc-by-sa-3.0" differ by two characters and by everything that matters.
COMMONS_LICENSES: dict[str, str] = {
    "pd": "PDM-1.0",
    "cc0": "CC0-1.0",
    "cc-by-1.0": "CC-BY-1.0",
    "cc-by-2.0": "CC-BY-2.0",
    "cc-by-2.5": "CC-BY-2.5",
    "cc-by-3.0": "CC-BY-3.0",
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by-sa-1.0": "CC-BY-SA-1.0",
    "cc-by-sa-2.0": "CC-BY-SA-2.0",
    "cc-by-sa-2.5": "CC-BY-SA-2.5",
    "cc-by-sa-3.0": "CC-BY-SA-3.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
}
# Commons still carries the pre-4.0 jurisdiction ports. A ported licence is the same licence
# under a national legal system, so it is identified as such and then judged by the same policy.
COMMONS_LICENSES.update(
    {
        f"{stem}-{jurisdiction}": identifier
        for stem, identifier in (
            ("cc-by-2.0", "CC-BY-2.0"),
            ("cc-by-2.5", "CC-BY-2.5"),
            ("cc-by-3.0", "CC-BY-3.0"),
            ("cc-by-sa-2.0", "CC-BY-SA-2.0"),
            ("cc-by-sa-2.5", "CC-BY-SA-2.5"),
            ("cc-by-sa-3.0", "CC-BY-SA-3.0"),
        )
        for jurisdiction in (
            "at", "au", "br", "ca", "ch", "cz", "de", "dk", "ee", "es", "fi", "fr", "gr",
            "hu", "ie", "il", "it", "jp", "kr", "lu", "nl", "no", "nz", "pl", "pt", "ro",
            "rs", "se", "sg", "tw", "uk", "us", "za",
        )
    }
)
_HTML = re.compile(r"<[^>]+>")
# Commons hides a duplicate of the credit inside the credit, for its own reasons:
# `Unknown author<span style="display: none;">Unknown author</span>`. Stripping tags without
# stripping what they hide put "Unknown author Unknown author" under every picture.
_HIDDEN = re.compile(
    r"<([a-z]+)[^>]*style=[\"'][^\"']*display\s*:\s*none[^>]*>.*?</\1>", re.S | re.I
)


def _plain(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    text = _HTML.sub(" ", _HIDDEN.sub("", str(value.get("value") or "")))
    text = re.sub(r"\s+", " ", text).strip()
    # Some credits repeat themselves outside a hidden element too.
    halves = text.split()
    middle = len(halves) // 2
    if halves and len(halves) % 2 == 0 and halves[:middle] == halves[middle:]:
        text = " ".join(halves[:middle])
    return text


class ImageRejected(ValueError):
    """A Commons file the release may not carry, with the reason it may not."""


def image_from_commons(
    page: Mapping[str, Any],
    *,
    subject_wikidata_id: str,
    subject_title: str,
    policy: LicensePolicy | None = None,
) -> YearImage:
    """Clear one Commons file, or refuse it and say why.

    Commons hosting is not a licence. The file's own `extmetadata` is the only statement that
    binds, and a file with no recognised licence value, an explicit restriction, or a non-free
    marker is refused — not shown with a disclaimer. A wrong licence is not a presentation
    problem.
    """

    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    if _plain(meta.get("NonFree")) not in ("", "0", "false", "False"):
        raise ImageRejected(f"{page.get('title')}: marked non-free")
    restrictions = _plain(meta.get("Restrictions"))
    if restrictions:
        raise ImageRejected(f"{page.get('title')}: carries a restriction ({restrictions})")
    raw = _plain(meta.get("License")).casefold()
    license_id = COMMONS_LICENSES.get(raw)
    if license_id is None:
        raise ImageRejected(f"{page.get('title')}: licence {raw or 'unstated'!r} is unrecognised")
    if policy is not None:
        try:
            enforce_license(license_id, policy, str(page.get("title")))
        except LicenseRejectedError as refusal:
            raise ImageRejected(str(refusal)) from refusal
    url = info.get("thumburl") or info.get("url")
    if not url or not info.get("width") or not info.get("height"):
        raise ImageRejected(f"{page.get('title')}: no usable rendition")
    artist = _plain(meta.get("Artist")) or _plain(meta.get("Credit")) or "Unattributed"
    short_name = _plain(meta.get("LicenseShortName")) or license_id
    rights_uri = _plain(meta.get("LicenseUrl")) or None
    return YearImage(
        commons_file=str(page.get("title")),
        descriptor_url=HttpUrl(str(info.get("descriptionurl"))),
        image_url=HttpUrl(str(url)),
        width=int(info["thumbwidth"] or info["width"])
        if info.get("thumbwidth")
        else int(info["width"]),
        height=int(info["thumbheight"] or info["height"])
        if info.get("thumbheight")
        else int(info["height"]),
        mime_type=str(info.get("thumbmime") or info.get("mime") or "image/jpeg"),
        license_id=license_id,
        license_short_name=short_name,
        rights_uri=(
            HttpUrl(rights_uri) if rights_uri and rights_uri.startswith("http") else None
        ),
        attribution=f"{artist} — {short_name}, via Wikimedia Commons",
        subject_wikidata_id=subject_wikidata_id,
        subject_title=subject_title,
        caption=_plain(meta.get("ObjectName")) or None,
    )


def fetch_images(
    subjects: Mapping[str, str],
    *,
    client: httpx.Client,
    width: int = 720,
    policy: LicensePolicy | None = None,
) -> tuple[list[YearImage], list[str]]:
    """Find one cleared picture per subject, checking each file's own licence.

    Returns what cleared and a line per refusal. A thin picture set is then readable as a
    licensing outcome rather than as a gap in coverage, which is the difference between a
    limitation and a bug.
    """

    if not subjects:
        return [], []
    files: dict[str, str] = {}
    identifiers = sorted(subjects)
    for start in range(0, len(identifiers), 40):
        batch = identifiers[start : start + 40]
        response = client.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims",
                "format": "json",
            },
        )
        response.raise_for_status()
        for identifier, entity in (response.json().get("entities") or {}).items():
            claims = ((entity or {}).get("claims") or {}).get("P18") or []
            for claim in claims:
                value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if isinstance(value, str) and value:
                    files[identifier] = f"File:{value}"
                    break

    images: list[YearImage] = []
    rejected: list[str] = []
    titles = sorted(set(files.values()))
    by_file = {title: identifier for identifier, title in files.items()}
    for start in range(0, len(titles), 20):
        batch = titles[start : start + 20]
        response = client.get(
            COMMONS_API,
            params={
                "action": "query",
                "titles": "|".join(batch),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": str(width),
                "format": "json",
                "formatversion": "2",
            },
        )
        response.raise_for_status()
        for page in response.json().get("query", {}).get("pages", []):
            if page.get("missing"):
                continue
            identifier = by_file.get(str(page.get("title")))
            if not identifier:
                continue
            try:
                images.append(
                    image_from_commons(
                        page,
                        subject_wikidata_id=identifier,
                        subject_title=subjects[identifier],
                        policy=policy,
                    )
                )
            except (ImageRejected, ValueError, KeyError, TypeError) as refusal:
                rejected.append(str(refusal))
    return sorted(images, key=lambda image: image.subject_wikidata_id), sorted(rejected)


def build_year_context(
    year: int,
    *,
    conflicts: list[YearConflict],
    images: list[YearImage],
    rejected: list[str],
    retrieved_at: datetime | None = None,
) -> YearContext:
    return YearContext(
        year=year,
        retrieved_at=retrieved_at or datetime.now(UTC),
        conflicts=conflicts,
        images=images,
        rejected_images=rejected,
    )
