"""Ingest a Wikipedia year article as dated event, birth and death records.

The map is seeded from place gazetteers, so selecting a year returns everything standing rather
than anything occurring. A year article is the opposite: it is a list of what happened, dated to
the day, and it is the source that lets a year page answer "what happened" instead of "what
existed".

Nothing here is generated. Entry text is the source's own wording, retained verbatim, and the
record is an ingestion of a list rather than a restatement. The only derived field is
`sitelink_count`, which counts language editions and is a measure of how much has been written,
never a claim that a subject mattered.

Parsing is separated from fetching so the parser can be tested against fixtures without a network.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Container, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

import httpx
from pydantic import HttpUrl

from history_pipeline.models import (
    ChronicleEntry,
    ChronicleEntryKind,
    DatePrecision,
    SourceReference,
    SubjectExtract,
    YearChronicle,
)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
MONTH_NUMBER = {name: number for number, name in enumerate(MONTHS, start=1)}

# A year is documented across many pages, and each keeps its content under its own headings.
# The heading is itself a subject signal: "Astronomy" and "Paintings" say what an entry is about
# without anyone having to classify it, so lensing most entries costs nothing.
_SECTIONS: dict[str, tuple[ChronicleEntryKind, str | None]] = {
    "Events": (ChronicleEntryKind.EVENT, None),
    "Births": (ChronicleEntryKind.BIRTH, None),
    "Deaths": (ChronicleEntryKind.DEATH, None),
    "Incumbents": (ChronicleEntryKind.INCUMBENT, "power"),
    "Incumbent": (ChronicleEntryKind.INCUMBENT, "power"),
    # Knowledge
    "Astronomy": (ChronicleEntryKind.EVENT, "knowledge"),
    "Mathematics": (ChronicleEntryKind.EVENT, "knowledge"),
    "Medicine": (ChronicleEntryKind.EVENT, "knowledge"),
    "Physiology": (ChronicleEntryKind.EVENT, "knowledge"),
    "Botany": (ChronicleEntryKind.EVENT, "knowledge"),
    "Technology": (ChronicleEntryKind.EVENT, "knowledge"),
    "Exploration": (ChronicleEntryKind.EVENT, "knowledge"),
    "Science": (ChronicleEntryKind.EVENT, "knowledge"),
    # Culture
    "Works": (ChronicleEntryKind.EVENT, "culture"),
    "Works published": (ChronicleEntryKind.EVENT, "culture"),
    "Paintings": (ChronicleEntryKind.EVENT, "culture"),
    "Sculpture": (ChronicleEntryKind.EVENT, "culture"),
    "Architecture": (ChronicleEntryKind.EVENT, "culture"),
    "Buildings": (ChronicleEntryKind.EVENT, "culture"),
    "New books": (ChronicleEntryKind.EVENT, "culture"),
    "Publications": (ChronicleEntryKind.EVENT, "culture"),
    "Prose": (ChronicleEntryKind.EVENT, "culture"),
    "Drama": (ChronicleEntryKind.EVENT, "culture"),
    "Poetry": (ChronicleEntryKind.EVENT, "culture"),
    "Music": (ChronicleEntryKind.EVENT, "culture"),
    "Literature": (ChronicleEntryKind.EVENT, "culture"),
}

_SECTION_BODY = r"==+\s*{name}\s*==+(.*?)(?=\n==[^=]|\Z)"
_REF = re.compile(r"<ref[^>]*?(?:/>|>.*?</ref>)", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
# Wikipedia does not write dates the same way on every page. The main year article writes the
# month first; the country and topic pages write the day first, give a month with no day, or
# write a span across two months. Accepting only one of those discarded the date on every
# companion page \u2014 in the 1543 run, a coronation and a treaty signing both arrived undated with
# "9 September \u2013" still sitting in the text where a reader would see it.
_MONTH_NAMES = "|".join(MONTHS)
# An uncertainty the source stated. It belongs in the qualifier, not in the middle of a sentence.
_APPROXIMATE = (
    r"approximate date|approximately|approximate|probable date|probable|"
    r"unknown date|date unknown|date not known|uncertain date|c\.|circa"
)
_DATE = re.compile(
    rf"^(?:(?P<approximate>{_APPROXIMATE})\s*(?:\u2013|-|\u2014|:)?\s*)?"
    rf"(?:(?P<month>{_MONTH_NAMES})\s+(?P<day>\d{{1,2}})"
    rf"|(?P<day_first>\d{{1,2}})\s+(?P<month_first>{_MONTH_NAMES})"
    rf"|(?P<month_only>{_MONTH_NAMES}))"
    # A span of dates is dated from where it began.
    rf"(?:\s*[/\u2013\u2014-]\s*(?:{_MONTH_NAMES}|\d{{1,2}})(?:\s+(?:{_MONTH_NAMES}))?)?"
    r"(?:\s*\((?P<qualifier>[^)]*)\))?"
    r"\s*(?:\u2013|-|\u2014)\s*(?P<rest>.+)$",
    re.IGNORECASE,
)


# The same uncertainty with no month behind it: "approximate date - William Clowes (died 1604)".
# The source is telling the reader how firm the date is, so it belongs in the qualifier the reader
# is shown, not at the front of the sentence where it reads as part of the name.
_UNDATED = re.compile(
    rf"^(?P<approximate>{_APPROXIMATE})\s*(?:\u2013|-|\u2014|:)\s*(?P<rest>.+)$", re.IGNORECASE
)


def _parse_date(cleaned: str) -> tuple[int | None, int | None, str | None, str] | None:
    """Read whatever date form the page used, or report that there was none."""

    matched = _DATE.match(cleaned)
    if not matched:
        undated = _UNDATED.match(cleaned)
        if undated:
            return None, None, undated.group("approximate").strip().rstrip("."), undated.group(
                "rest"
            )
        return None
    month_name = (
        matched.group("month") or matched.group("month_first") or matched.group("month_only")
    )
    month = MONTH_NUMBER.get(month_name.capitalize()) if month_name else None
    if month is None:
        return None
    day_text = matched.group("day") or matched.group("day_first")
    day = int(day_text) if day_text else None
    if day is not None and not 1 <= day <= 31:
        return None
    approximate = matched.group("approximate")
    qualifier = matched.group("qualifier") or (
        approximate.strip().rstrip(".") if approximate else None
    )
    return month, day, qualifier, matched.group("rest")
_LIFESPAN = re.compile(r"\((?:d|b)\.\s*(?P<year>\d{3,4})[^)]*\)")
# Date articles and bare years are navigation links, never the subject of an entry.
_NAVIGATION = re.compile(
    r"^(?:" + "|".join(MONTHS) + r")(?:\s+\d{1,2})?$|^\d{1,4}(?:\s*(?:BC|BCE|AD))?$"
)


def _strip_markup(fragment: str) -> str:
    text = _REF.sub("", fragment)
    text = _COMMENT.sub("", text)
    # A lang template wraps a real title; removing it wholesale removes the work being named.
    text = re.sub(r"\{\{lang(?:-[a-z-]+)?\|(?:[a-z-]+\|)?([^{}|]*)\}\}", r"\1", text, flags=re.I)
    for _ in range(3):
        text = _TEMPLATE.sub("", text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = _TAG.sub("", text)
    for entity, replacement in (
        ("&ndash;", "\u2013"), ("&mdash;", "\u2014"), ("&nbsp;", " "), ("&amp;", "&"),
    ):
        text = text.replace(entity, replacement)
    text = re.sub(r"\[\[|\]\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# Sub-headings that group a section rather than record anything. A year article uses them as
# bullets, so they arrive looking exactly like entries.
_STRUCTURAL_MARKERS = frozenset(
    {
        "date unknown",
        "dates unknown",
        "date uncertain",
        "unknown date",
        "unknown dates",
        "probable",
        "probable date",
        "probable dates",
        "approximate date",
        "approximate dates",
        "unknown",
        "undated",
    }
)
_GROUPING_OPENERS = frozenset(
    {"also", "others", "other", "in", "at", "the", "and", "plus", "elsewhere", "including"}
)
_DATE_ONLY = re.compile(
    r"^(?:" + "|".join(MONTHS) + r")\s+\d{1,2}$|^\d{1,4}$",
)


def _is_structural(text: str) -> bool:
    """A grouping label or a date with nothing after it is not a record of anything."""

    stripped = text.strip().strip(":-\u2013\u2014 ").strip()
    if not stripped:
        return True
    if stripped.casefold() in _STRUCTURAL_MARKERS:
        return True
    # "Also" and "In France" are how a year article introduces a run of bullets, and left in they
    # reach the reader as entries with nothing in them. But "James Tyrie" and "Monarch: Go-Nara"
    # are two words and are records, so shortness alone cannot be the test: a grouping label opens
    # with a function word, and a record opens with the thing it is about.
    words = stripped.split()
    if len(words) < 3 and words[0].casefold() in _GROUPING_OPENERS:
        return True
    # "See 1543 in poetry" is a cross-reference to another page, not a record of anything.
    if words[0].casefold() == "see" and len(words) <= 6:
        return True
    return bool(_DATE_ONLY.match(stripped))


_GALLERY = re.compile(r"<gallery[^>]*>.*?</gallery>", re.S | re.I)


def _logical_lines(section: str) -> list[str]:
    """Rejoin a bullet whose wikilink was wrapped across source lines.

    Wrapping mid-link is rare but real, and splitting on it strands an unclosed `[[` that survives
    markup stripping and reaches the reader as broken text.
    """

    joined: list[str] = []
    for raw in section.split("\n"):
        if joined and joined[-1].count("[[") > joined[-1].count("]]"):
            joined[-1] = f"{joined[-1]} {raw.strip()}"
            continue
        joined.append(raw)
    return joined


def _linked_titles(fragment: str) -> list[str]:
    titles: list[str] = []
    for target in re.findall(r"\[\[([^\]]+?)\]\]", fragment):
        title = target.split("|", 1)[0].strip()
        if not title or title.startswith(("File:", "Image:", "Category:")):
            continue
        if title not in titles:
            titles.append(title)
    return titles


def _entry_id(
    year: int,
    kind: ChronicleEntryKind,
    month: int | None,
    day: int | None,
    text: str,
) -> str:
    digest = hashlib.sha256(
        f"{year}|{kind}|{month}|{day}|{text}".encode()
    ).hexdigest()[:16]
    return f"chronicle:{year}:{kind.value}:{digest}"


def parse_year_wikitext(
    wikitext: str,
    year: int,
    *,
    source_page: str | None = None,
) -> list[ChronicleEntry]:
    """Read every recognised section of one year page.

    Year coverage is spread over a main article plus topic and country pages, and each uses its
    own headings. Reading only Events/Births/Deaths silently discards the art, the science and the
    poetry, which is most of what makes a year worth reading about.
    """

    entries: list[ChronicleEntry] = []
    for heading, (kind, lens) in _SECTIONS.items():
        section = re.search(_SECTION_BODY.format(name=re.escape(heading)), wikitext, re.S)
        if not section:
            continue
        month: int | None = None
        day: int | None = None
        for line in _logical_lines(_GALLERY.sub("", section.group(1))):
            stripped = line.strip()
            if not stripped.startswith("*"):
                continue
            nested = stripped.startswith("**")
            body = stripped.lstrip("*").strip()
            linked = _linked_titles(body)
            cleaned = _strip_markup(body)
            dated = _parse_date(cleaned)
            qualifier = None
            if dated:
                month, day, qualifier, text = dated
            else:
                text = cleaned
                # A sub-bullet shares the date of the entry above it; a new top-level bullet
                # without a date genuinely has none.
                if not nested:
                    month = day = None
            text = text.strip(" \u2013\u2014-:").strip()
            if _is_structural(text):
                # A grouping label carries no date of its own, so it must not leave the
                # running month set for the entries that follow it.
                if not nested and not dated:
                    month = day = None
                continue
            lifespan = _LIFESPAN.search(text)
            subject = next(
                (title for title in linked if not _NAVIGATION.match(title)), None
            )
            entries.append(
                ChronicleEntry(
                    entry_id=_entry_id(year, kind, month, day, text),
                    kind=kind,
                    year=year,
                    month=month,
                    day=day,
                    date_precision=(
                        DatePrecision.EXACT if day is not None else DatePrecision.YEAR
                    ),
                    text=text,
                    qualifier=qualifier or None,
                    subject_title=subject,
                    linked_titles=linked,
                    related_year=int(lifespan.group("year")) if lifespan else None,
                    source_page=source_page,
                    topic=heading,
                    lens=lens,
                )
            )
    return deduplicate_entries(entries)


def deduplicate_entries(entries: Iterable[ChronicleEntry]) -> list[ChronicleEntry]:
    """A year article occasionally repeats a line verbatim; the entry ID makes that detectable."""

    seen: dict[str, ChronicleEntry] = {}
    for entry in entries:
        seen.setdefault(entry.entry_id, entry)
    return sorted(
        seen.values(),
        key=lambda entry: (entry.month or 13, entry.day or 32, entry.kind.value, entry.text),
    )


def chronicle_sort_key(entry: ChronicleEntry) -> tuple[int, int]:
    return (entry.month or 13, entry.day or 32)


# Topic and country pages that carry a year's art, science, poetry and rulers. Absent ones are
# skipped: coverage varies enormously by year and a missing page is normal, not an error.
TOPIC_PAGES: tuple[str, ...] = (
    "{year} in science", "{year} in art", "{year} in literature", "{year} in poetry",
    "{year} in music", "{year} in architecture",
)
COUNTRY_PAGES: tuple[str, ...] = (
    "{year} in England", "{year} in Scotland", "{year} in Ireland", "{year} in France",
    "{year} in Spain", "{year} in Japan", "{year} in China", "{year} in India",
    "{year} in Sweden", "{year} in Denmark", "{year} in Norway", "{year} in Italy",
    "{year} in Germany", "{year} in Russia", "{year} in the Ottoman Empire",
    "{year} in Portugal", "{year} in the Netherlands", "{year} in Canada", "{year} in Mexico",
)


def companion_pages(year: int) -> list[str]:
    return [
        template.format(year=year) for template in (*TOPIC_PAGES, *COUNTRY_PAGES)
    ]


def fetch_page_wikitext(
    title: str,
    *,
    client: httpx.Client,
    language: str = "en",
) -> dict[str, Any] | None:
    """Fetch one companion page, or None when the year has no such page."""

    response = client.get(
        WIKIPEDIA_API.replace("en.", f"{language}."),
        params={
            "action": "parse",
            "page": title,
            "prop": "wikitext|revid",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
        },
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        return None
    parse = payload.get("parse") or {}
    if not isinstance(parse.get("wikitext"), str) or not parse.get("revid"):
        return None
    return parse


def fetch_year_wikitext(
    year: int,
    *,
    client: httpx.Client,
    language: str = "en",
) -> dict[str, Any]:
    """Fetch one year article, pinned to the revision that answered."""

    response = client.get(
        WIKIPEDIA_API.replace("en.", f"{language}."),
        params={
            "action": "parse",
            "page": str(year),
            "prop": "wikitext|revid",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise ValueError(f"Wikipedia rejected the year request: {payload['error']}")
    parse = payload.get("parse") or {}
    wikitext = parse.get("wikitext")
    if not isinstance(wikitext, str) or not wikitext.strip():
        raise ValueError(f"Year article {year} returned no wikitext")
    if not parse.get("revid"):
        raise ValueError(f"Year article {year} has no pinned revision ID")
    return parse


def _resolved_wikidata_ids(
    titles: list[str],
    *,
    client: httpx.Client,
    language: str,
) -> dict[str, str]:
    """Map article titles to Wikidata IDs, following redirects the way the reader would."""

    resolved: dict[str, str] = {}
    for start in range(0, len(titles), 40):
        batch = titles[start : start + 40]
        response = client.get(
            WIKIPEDIA_API.replace("en.", f"{language}."),
            params={
                "action": "query",
                "prop": "pageprops",
                "ppprop": "wikibase_item",
                "redirects": "1",
                "titles": "|".join(batch),
                "format": "json",
                "formatversion": "2",
            },
        )
        response.raise_for_status()
        query = response.json().get("query", {})
        forward = {
            item["from"]: item["to"]
            for key in ("redirects", "normalized")
            for item in query.get(key, [])
        }
        by_title = {
            page["title"]: (page.get("pageprops") or {}).get("wikibase_item")
            for page in query.get("pages", [])
            if "missing" not in page
        }
        for title in batch:
            target = title
            for _ in range(3):
                target = forward.get(target, target)
            wikidata_id = by_title.get(target)
            if isinstance(wikidata_id, str) and wikidata_id:
                resolved[title] = wikidata_id
    return resolved


# A coordinate is not enough to make something a place. Wikidata gives the Alhambra Decree the
# coordinates of the Alhambra and the Ensisheim meteorite the coordinates of the field it fell in,
# so reading P625 alone made an entry about a decree an entry about Roman Catholicism, and an
# entry about a meteorite an entry about meteorites. These are the classes a year article
# actually produces that carry a coordinate and are not places.
NON_PLACE_CLASSES = frozenset(
    {
        "Q49848",  # document
        "Q2571972",  # decree
        "Q131569",  # treaty
        "Q60186",  # meteorite
        "Q178561",  # battle
        "Q198",  # war
        "Q571",  # book
        "Q47461344",  # written work
        "Q179461",  # religious text
        "Q3305213",  # painting
    }
)


def _sitelink_counts(
    wikidata_ids: Iterable[str],
    *,
    client: httpx.Client,
) -> tuple[dict[str, int], set[str]]:
    """Count language editions per Wikidata item.

    Counted from `sitelinks` in one batched call rather than paging Wikipedia's langlinks, which
    truncates silently across batched titles and quietly reports zero for real articles.

    Also returns the subset that is a place, which is how a place is told from a person, an event
    or a work when choosing what an entry is about.
    """

    counts: dict[str, int] = {}
    places: set[str] = set()
    unique = sorted(set(wikidata_ids))
    for start in range(0, len(unique), 50):
        batch = unique[start : start + 50]
        response = client.get(
            WIKIDATA_API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "sitelinks|claims",
                "format": "json",
            },
        )
        response.raise_for_status()
        for wikidata_id, entity in (response.json().get("entities") or {}).items():
            if not isinstance(entity, dict) or "sitelinks" not in entity:
                continue
            counts[wikidata_id] = len(entity["sitelinks"])
            claims = entity.get("claims") or {}
            # P625 is coordinate location; P31 is what the thing is.
            if claims.get("P625") and not _is_classed_as(claims, NON_PLACE_CLASSES):
                places.add(wikidata_id)
    return counts, places


def _is_classed_as(claims: Mapping[str, Any], classes: Container[str]) -> bool:
    for statement in claims.get("P31") or []:
        value = ((statement.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(value, dict) and value.get("id") in classes:
            return True
    return False


def choose_subject(
    entry: ChronicleEntry,
    wikidata_ids: Mapping[str, str],
    places: Container[str],
) -> str | None:
    """Pick the linked title an entry is actually about.

    Taking the first non-navigation link puts the wrong thing first surprisingly often, because a
    sentence tends to open with where something happened. "In Nuremberg, De revolutionibus is
    printed" is about the book; an attempt to conquer San Marino is not about San Marino, whose
    modern fame would otherwise make a failed skirmish the largest thing in the year.

    A place carries coordinates and a person or a work does not, so for events the first
    non-place link wins. A birth or death is about its person, who is already first.
    """

    candidates = [
        title for title in entry.linked_titles if not _NAVIGATION.match(title)
    ]
    if not candidates:
        return None
    if entry.kind is not ChronicleEntryKind.EVENT:
        return candidates[0]
    for title in candidates:
        wikidata_id = wikidata_ids.get(title)
        if wikidata_id and wikidata_id not in places:
            return title
    return candidates[0]


def fetch_subject_extracts(
    titles: Sequence[str],
    wikidata_ids: Mapping[str, str],
    *,
    client: httpx.Client,
    language: str = "en",
    minimum_chars: int = 80,
) -> list[SubjectExtract]:
    """Fetch the lead section of every article a chronicle entry is about.

    Each is pinned to the revision that answered and checksummed, exactly as a dossier extract is,
    so a writer drawing on one is drawing on a fixed text rather than a moving page.
    """

    extracts: list[SubjectExtract] = []
    seen: set[int] = set()
    for start in range(0, len(titles), 20):
        batch = list(titles[start : start + 20])
        response = client.get(
            WIKIPEDIA_API.replace("en.", f"{language}."),
            params={
                "action": "query",
                "prop": "extracts|info|revisions",
                "exintro": "1",
                "explaintext": "1",
                "inprop": "url",
                "rvprop": "ids",
                "redirects": "1",
                "maxlag": "5",
                "titles": "|".join(batch),
                "format": "json",
                "formatversion": "2",
            },
        )
        response.raise_for_status()
        query = response.json().get("query", {})
        forward = {
            item["from"]: item["to"]
            for key in ("redirects", "normalized")
            for item in query.get(key, [])
        }
        pages = {page["title"]: page for page in query.get("pages", []) if "missing" not in page}
        for title in batch:
            target = title
            for _ in range(3):
                target = forward.get(target, target)
            page = pages.get(target)
            if page is None:
                continue
            extract = (page.get("extract") or "").strip()
            revision = (page.get("revisions") or [{}])[0]
            if len(extract) < minimum_chars or not revision.get("revid"):
                continue
            if page["pageid"] in seen:
                continue
            seen.add(page["pageid"])
            extracts.append(
                SubjectExtract(
                    title=title,
                    canonical_title=page["title"],
                    page_id=int(page["pageid"]),
                    revision_id=int(revision["revid"]),
                    url=HttpUrl(
                        str(page.get("fullurl"))
                        if page.get("fullurl")
                        else f"https://{language}.wikipedia.org/wiki/"
                        + page["title"].replace(" ", "_")
                    ),
                    extract=extract,
                    wikidata_id=wikidata_ids.get(title),
                    content_checksum_sha256=hashlib.sha256(
                        extract.encode("utf-8")
                    ).hexdigest(),
                )
            )
    return sorted(extracts, key=lambda item: item.canonical_title)


def attach_prominence(
    entries: list[ChronicleEntry],
    wikidata_ids: Mapping[str, str],
    sitelinks: Mapping[str, int],
    places: Container[str] = frozenset(),
) -> list[ChronicleEntry]:
    """Record each subject's Wikidata ID and language-edition count."""

    resolved: list[ChronicleEntry] = []
    for entry in entries:
        subject = choose_subject(entry, wikidata_ids, places)
        wikidata_id = wikidata_ids.get(subject or "")
        resolved.append(
            entry.model_copy(
                update={
                    "subject_title": subject,
                    "subject_wikidata_id": wikidata_id,
                    "sitelink_count": sitelinks.get(wikidata_id) if wikidata_id else None,
                }
            )
        )
    return resolved


def build_chronicle(
    year: int,
    parse: Mapping[str, Any],
    *,
    language: str,
    source_ref: SourceReference,
    revision_timestamp: datetime,
    entries: list[ChronicleEntry],
    subject_extracts: list[SubjectExtract] | None = None,
) -> YearChronicle:
    wikitext = str(parse["wikitext"])
    return YearChronicle(
        chronicle_id=f"chronicle:{year}:{language}",
        year=year,
        language=language,
        page_id=int(parse["pageid"]),
        revision_id=int(parse["revid"]),
        revision_timestamp=revision_timestamp,
        content_checksum_sha256=hashlib.sha256(wikitext.encode("utf-8")).hexdigest(),
        source_ref=source_ref,
        entries=entries,
        subject_extracts=subject_extracts or [],
    )


def summarize(chronicle: YearChronicle) -> dict[str, Any]:
    """Counts a caller can print without re-deriving them from the entry list."""

    by_kind = {kind.value: 0 for kind in ChronicleEntryKind}
    dated = 0
    with_subject = 0
    for entry in chronicle.entries:
        by_kind[entry.kind.value] += 1
        if entry.day is not None:
            dated += 1
        if entry.subject_wikidata_id:
            with_subject += 1
    return {
        "total": len(chronicle.entries),
        **by_kind,
        "with_day": dated,
        "with_wikidata_subject": with_subject,
    }
