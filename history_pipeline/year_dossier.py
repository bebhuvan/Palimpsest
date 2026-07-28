"""Generate one prose dossier per year from that year's chronicle, and check it mechanically.

This tier has no human-review state, which is a disclosed position rather than an oversight. A
solo project cannot review thousands of essays, so what a reviewer would have caught is replaced
by three things that do not need one:

- a closed evidence set: the model is given that year's chronicle entries and nothing else, so it
  is arranging supplied material rather than recalling its own;
- the same containment check the restatement tier uses, which rejects any name or number the
  evidence does not contain;
- citations that must resolve: every block names the entries it draws on, and an entry ID that
  does not exist fails the dossier.

None of that can confirm the prose draws a sound conclusion from sound facts. That limit is real,
it is why the reader is told the connections are machine-made and unreviewed, and it is the reason
the dossier's shape comes from the year's own segmentation rather than from a model.

## What changed, and why it is the same argument carried further

The failure this tier cannot detect is fusion: two true facts joined into a false third. Every
name and number is contained, every citation resolves, and the sentence is still wrong. The only
thing that governs how often it can happen is how many facts are in front of the writer at once
and how many sentences it writes.

So the dossier is now built in three layers, and only the middle one is prose the model composes
freely:

- the **overview** opens on an assembled lede — the year's most-written-about records in the
  source's own words — and one short paragraph written from a digest of the year rather than from
  the year;
- the **anchors** give a handful of happenings real room, each written from its own clustered
  record and the lead of the article it is about. That is a window of two or three facts, not a
  hundred and ninety-six, and it is close enough to a restatement that the restatement tier's
  measured behaviour applies to it;
- the **register** carries every record, verbatim, and is assembled entirely.

And the containment check is now scoped to the block. A section used to be checked against the
whole year, which meant any name from any of its records could legitimately appear in any
sentence. Now each block is checked against its own evidence, so a paragraph about Nuremberg
cannot borrow a name from a paragraph about Kyoto. This does not detect fusion. It shrinks the
set of facts that can be fused, which is the only lever available without a reader.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import httpx

from history_pipeline.chronicle import MONTHS
from history_pipeline.dossiers import canonical_sha256
from history_pipeline.models import (
    ChronicleEntry,
    DossierRestatementContent,
    ProseLink,
    RestatementProvenance,
    RestatementResult,
    RestatementValidation,
    SubjectExtract,
    YearAnchor,
    YearChronicle,
    YearContext,
    YearDossier,
    YearDossierContent,
    YearDossierSection,
    YearOverview,
    year_dossier_body,
)
from history_pipeline.restatement import (
    POLICY_VERSION,
    ProviderProfile,
    RestatementRejected,
    closed_world_report,
    common_words,
    provider_profile,
)
from history_pipeline.year_layers import (
    ANCHOR_COUNT,
    CREATOR_TITLE,
    EntryCluster,
    anchor_id,
    assemble_lede,
    build_incumbents,
    build_register,
    build_related_years,
    build_themes,
    build_works,
    cluster_entries,
    collapse_duplicates,
    date_text,
    display_title,
    extract_index,
    month_counts,
    most_written_about,
    quotable,
    reads_as_a_record,
)

# Sections are derived from the year's own data. The model chooses prose, never structure, so
# every year is segmented identically and two years can be read against each other.
LENS_HEADINGS: dict[str, str] = {
    "power": "Rulers, wars and states",
    "belief": "Religion and reform",
    "knowledge": "Science, scholarship and exploration",
    "culture": "Art, music and letters",
    "trade": "Trade and movement",
    "nature": "Earth, weather and disease",
}
INCUMBENTS_SECTION = ("incumbents", "Who held power")
BIRTHS_SECTION = ("births", "Born this year")
DEATHS_SECTION = ("deaths", "Died this year")
MINIMUM_ENTRIES_PER_SECTION = 2
# A paragraph can carry a handful of names; beyond that it degenerates into a list.
MAXIMUM_PEOPLE_IN_PROSE = 6
# No paragraph covering thirty discrete events reads as anything but a list. The register
# below the dossier carries every record; a section only has to carry the ones worth reading.
MAXIMUM_EVENTS_IN_PROSE = 10


def _lens_of(entry: ChronicleEntry, lenses: Mapping[str, str]) -> str | None:
    """An entry's own section heading beats an outside classification, and costs nothing."""

    return entry.lens or lenses.get(entry.entry_id)


def plan_sections(
    entries: Sequence[ChronicleEntry],
    lenses: Mapping[str, str],
) -> list[tuple[str, str, list[ChronicleEntry]]]:
    """Group a year's entries into the sections its dossier will have.

    Returns (section_id, heading, entries). A lens with too little material is folded away rather
    than given a section with one line in it, so a thin year reads as a short dossier instead of a
    padded one.

    Repeated records of one happening are collapsed to one first. The same event written up on
    the main article and on a country page used to reach the model twice under two lenses, and
    came back narrated twice — the Lighthouse of Genoa appeared under both knowledge and nature in
    a real 1543 run.
    """

    representatives, _ = collapse_duplicates(entries)
    plan: list[tuple[str, str, list[ChronicleEntry]]] = []
    events = [entry for entry in representatives if entry.kind.value == "event"]
    for lens, heading in LENS_HEADINGS.items():
        selected = [entry for entry in events if _lens_of(entry, lenses) == lens]
        if len(selected) >= MINIMUM_ENTRIES_PER_SECTION:
            plan.append((f"section:{lens}", heading, selected))
    covered = {entry.entry_id for _, _, group in plan for entry in group}
    remainder = [entry for entry in events if entry.entry_id not in covered]
    if remainder:
        plan.append(("section:elsewhere", "Elsewhere in the year", remainder))
    # Who held which office is a table, and so is who was born and who died. Asked for as prose,
    # offices came back as a row of dashes and births came back as "Other births included Charles
    # III, Duke of Lorraine (18 February), Domenico Fontana (1543)" — a list with commas standing
    # in for sentences, which is what the register already is and does better. Both are rendered
    # now, and the prominent few get one restated sentence each about who they were.
    return plan


# How many article leads an anchor may draw on. The subject's own, plus the things the record
# links to — the book, the treaty, the battle. One article about a person produces a paragraph
# about that person; the linked articles are what make it a paragraph about the year.
MAXIMUM_ANCHOR_BACKGROUND = 5
# Other records in the year about the same subject that an anchor may gather in.
MAXIMUM_ANCHOR_SIBLINGS = 9
# The least a happening can say and still be worth a section of its own. An anchor whose records
# amount to one short line and whose background is a full biography is where the writing has the
# least to work from and the most to borrow from, which is exactly where a fusion comes from: the
# 1543 audit found both of its confirmed fusions in the thinnest-recorded anchor on the page.
# Raised from 120 after a one-record anchor on the Index Librorum Prohibitorum spent four attempts
# trying to say the Index banned De revolutionibus — which is the same year and is not true until
# 1616. With one line of its own to work from, the writing goes looking for a connection.
MINIMUM_ANCHOR_RECORD_CHARS = 200
# How many records per lens the overview paragraph is written from.
OVERVIEW_RECORDS_PER_LENS = 4


class AnchorPlan:
    """One happening the dossier will give a section of its own, and its whole evidence set."""

    __slots__ = ("_lens", "_sibling_lenses", "background", "cluster", "label", "siblings")

    def __init__(
        self,
        cluster: EntryCluster,
        background: Sequence[SubjectExtract],
        label: str,
        lens: str | None,
        siblings: Sequence[EntryCluster] = (),
    ) -> None:
        self.cluster = cluster
        self.background = list(background)
        self.label = label
        self._lens = lens
        # Other records in the same year about the same thing. An Ottoman campaign is four
        # records — a march, two sieges and a surrender — and an anchor allowed only the first of
        # them either writes a stub or reaches for the rest and is rejected for it. Reaching was
        # what happened: the first run of this design failed on an anchor about Suleiman that
        # wanted Esztergom and Szekesfehervar, which are the same campaign and were sitting in
        # the year. Widening to them keeps the world closed and makes it the right shape.
        self.siblings = list(siblings)
        self._sibling_lenses: list[str | None] = []

    @property
    def lens(self) -> str | None:
        """The anchor's own lens, or one its own records supply.

        A record that carries no lens still sits beside records that do, and an anchor labelled
        with nothing when three of its four records say "power" is a gap in the rendering rather
        than an honest absence.
        """

        if self._lens:
            return self._lens
        return next((item for item in self._sibling_lenses if item), None)

    @property
    def clusters(self) -> list[EntryCluster]:
        return [self.cluster, *self.siblings]

    @property
    def entry_ids(self) -> list[str]:
        return [entry_id for cluster in self.clusters for entry_id in cluster.entry_ids]

    @property
    def extract(self) -> SubjectExtract | None:
        return self.background[0] if self.background else None

    @property
    def anchor_id(self) -> str:
        return anchor_id(self.cluster.entry_id)

    @property
    def heading(self) -> str:
        lead = self.cluster.lead
        subject = display_title(lead.subject_title)
        return subject or (self.extract.canonical_title if self.extract else lead.text)

    def evidence(self) -> str:
        """Everything this anchor's paragraph may draw on, and the whole of it.

        Deliberately narrow. The anchor is where the dossier spends its words, so it is also where
        a fusion would be most damaging, and the way to make one less likely is to have less in
        front of the writer — not to warn it more sternly. Narrow is not the same as thin: the
        articles this record links to are about this record, and adding them widens what may be
        said about one happening without letting anything else in.
        """

        lines: list[str] = []
        for cluster in self.clusters:
            dated = date_text(cluster.month, cluster.day)
            lines.extend(f"{dated} — {text}" if dated else text for text in cluster.texts)
        lines.extend(
            f"Background on {item.canonical_title}: {item.extract}" for item in self.background
        )
        return "\n".join(lines)


def plan_anchors(
    entries: Sequence[ChronicleEntry],
    lenses: Mapping[str, str],
    extracts: Mapping[str, SubjectExtract],
    count: int = ANCHOR_COUNT,
) -> list[AnchorPlan]:
    """Choose the happenings that get room, ranked by how much has been written about them.

    An anchor needs an article behind it as well as a record: without the subject's lead there is
    nothing to say beyond what the register already says, and a paragraph with nothing to add is
    exactly the padding this dossier is trying not to be.

    A bibliography row — "Titian - Ecce Homo" — is refused here even though it ranks high, because
    the record says nothing about the year and the article behind it says everything about a life.
    A paragraph written from that pair is a biography with a date on it.
    """

    clusters = cluster_entries(entries)
    taken: set[str] = set()
    led: set[str] = set()
    chosen: list[AnchorPlan] = []
    for cluster in most_written_about(clusters, count * 4):
        if not reads_as_a_record(cluster.lead.text) or cluster.entry_id in taken:
            continue
        # A record another anchor already gathered is still evidence here if it is about the same
        # thing. Excluding it split Columbus's voyage across three anchors — the crossing, the
        # landfall on Hispaniola, the wreck of the Santa María — and each of them then reached for
        # the other two and was rejected for it. Only an anchor's own leading record is reserved,
        # because that is what stops the same happening getting two sections.
        siblings = [
            other
            for other in clusters
            if other.entry_id != cluster.entry_id
            and other.entry_id not in led
            and _shares_a_subject(cluster, other)
        ]
        siblings = sorted(siblings, key=lambda item: (item.month or 13, item.day or 32))[
            : MAXIMUM_ANCHOR_SIBLINGS
        ]
        seen: set[int] = set()
        background: list[SubjectExtract] = []
        for source in (cluster, *siblings):
            for title in (source.lead.subject_title or "", *source.lead.linked_titles):
                found = extracts.get(title)
                if found and found.page_id not in seen and len(found.extract) >= 120:
                    seen.add(found.page_id)
                    background.append(found)
                if len(background) == MAXIMUM_ANCHOR_BACKGROUND:
                    break
            if len(background) == MAXIMUM_ANCHOR_BACKGROUND:
                break
        if not background or len(background[0].extract) < 200:
            continue
        substance = sum(
            len(text) for source in (cluster, *siblings) for text in source.texts
        )
        if substance < MINIMUM_ANCHOR_RECORD_CHARS:
            continue
        led.add(cluster.entry_id)
        taken.add(cluster.entry_id)
        taken.update(sibling.entry_id for sibling in siblings)
        planned = AnchorPlan(
            cluster, background, f"a{len(chosen) + 1}", cluster.lens(lenses), siblings
        )
        planned._sibling_lenses = [sibling.lens(lenses) for sibling in siblings]
        chosen.append(planned)
        if len(chosen) == count:
            break
    return chosen


def _shares_a_subject(left: EntryCluster, right: EntryCluster) -> bool:
    """Whether two records are about the same thing, according to the source.

    Three separate lines record the siege of Nice: the siege beginning on 6 August under the
    Franco-Ottoman alliance, the city falling on 22 August, and a bare "Siege of Nice" with
    the span of days after it.
    They share no wikilink and no Wikidata subject, so a link-only rule leaves an anchor about the
    fall of a city that may not name who took it, and the paragraph reaches for the name anyway
    and is rejected. Naming the subject in the text is the source saying the two are connected,
    which is weaker evidence than a link and still the source's own.
    """

    if (
        left.lead.subject_wikidata_id
        and left.lead.subject_wikidata_id == right.lead.subject_wikidata_id
    ):
        return True
    for one, other in ((left, right), (right, left)):
        subject = display_title(one.lead.subject_title)
        if not subject or len(subject) < 4:
            continue
        if subject in other.lead.linked_titles:
            return True
        if re.search(rf"(?<!\w){re.escape(subject)}(?!\w)", other.lead.text):
            return True
    return False


# How many people get a sentence saying who they were. Each costs one narrow closed world and
# buys a reader the difference between a name on a list and somebody they might follow.
PEOPLE_GLOSSED = 10
# And how many books, paintings and poems get a sentence saying what they are.
WORKS_GLOSSED = 6


class PersonPlan:
    """One person or work that will carry a sentence, and the one article it may come from.

    This is the narrowest evidence set in the dossier: a single revision-pinned article lead about
    a single person. That makes it a restatement rather than a synthesis, which is the tier whose
    behaviour has actually been measured — and it is the reason a gloss can be offered at all.
    """

    __slots__ = ("cluster", "extract", "kind", "label")

    def __init__(
        self,
        cluster: EntryCluster,
        extract: SubjectExtract,
        label: str,
        kind: str = "person",
    ) -> None:
        self.cluster = cluster
        self.extract = extract
        self.label = label
        self.kind = kind

    @property
    def entry_id(self) -> str:
        return self.cluster.entry_id

    @property
    def name(self) -> str:
        if self.kind == "work":
            return self.extract.canonical_title
        return display_title(self.cluster.lead.subject_title) or self.extract.canonical_title

    def evidence(self) -> str:
        return f"{self.cluster.lead.text}\n{self.extract.extract}"


def plan_people(
    entries: Sequence[ChronicleEntry],
    extracts: Mapping[str, SubjectExtract],
    count: int = PEOPLE_GLOSSED,
    works: int = WORKS_GLOSSED,
) -> list[PersonPlan]:
    """Choose the people and the works worth a sentence, by how much has been written about them.

    A work gets the same treatment as a person and for the same reason: "Titian - Ecce Homo" is a
    row in a catalogue, and one restated sentence from the painting's own article is the
    difference between a title and something a reader might go and look at.
    """

    clusters = cluster_entries(entries)
    made = [work.entry_id for work in build_works(clusters, extracts)]
    chosen: list[PersonPlan] = []

    def take(candidates: Sequence[EntryCluster], kind: str, limit: int) -> None:
        taken = 0
        for cluster in candidates:
            extract = _gloss_source(cluster, extracts, kind)
            if extract is None or len(extract.extract) < 200:
                continue
            chosen.append(PersonPlan(cluster, extract, f"p{len(chosen) + 1}", kind))
            taken += 1
            if taken == limit:
                return

    take(most_written_about(clusters, count * 3, kinds=("birth", "death")), "person", count)
    # Ranked among the works themselves. Ranking them inside the general event ranking loses them:
    # that ranking keeps one record per subject, so Luther's treatise displaced Luther's other
    # book and the year's only two glossable works became one.
    by_entry = {cluster.entry_id: cluster for cluster in clusters}
    take([by_entry[entry_id] for entry_id in made if entry_id in by_entry], "work", works)
    return chosen


def _gloss_source(
    cluster: EntryCluster,
    extracts: Mapping[str, SubjectExtract],
    kind: str,
) -> SubjectExtract | None:
    """The one article a gloss may be restated from.

    For a person that is their own article. For a work it is the work's, not its maker's: the
    subject of "Titian - Ecce Homo" resolves to Titian, and a sentence written from Titian's
    article says who Titian was, which is not what a reader looking at a painting wants.
    """

    lead = cluster.lead
    if kind != "work":
        return extracts.get(lead.subject_title or "")
    # Only the part of the record after the creator counts. "Clément Marot, Théodore de Bèze and
    # Pierre Certon La Forme des Prieres" names three people before it names the work, and any of
    # them would otherwise be taken for the thing that was made.
    matched = CREATOR_TITLE.match(lead.text)
    if not matched:
        return None
    named = matched.group("title")
    for title in lead.linked_titles:
        if title == lead.subject_title or title not in named:
            continue
        found = extracts.get(title)
        if found and len(found.extract) >= 200:
            return found
    return None


def _most_written_about(
    entries: Sequence[ChronicleEntry],
    limit: int = MAXIMUM_PEOPLE_IN_PROSE,
) -> list[ChronicleEntry]:
    """Keep the records most has been written about, in date order.

    Handing a model thirty records produces a list, not prose. The full set still reaches the
    reader as the year's register; this is only what a paragraph is allowed to name, ranked by
    how many language editions cover the subject rather than by anyone's judgement.
    """

    if len(entries) <= limit:
        return list(entries)
    ranked = sorted(entries, key=lambda entry: -(entry.sitelink_count or 0))[:limit]
    return sorted(ranked, key=lambda entry: (entry.month or 13, entry.day or 32))


def entry_labels(
    plan: Sequence[tuple[str, str, list[ChronicleEntry]]],
    anchors: Sequence[AnchorPlan] = (),
) -> dict[str, str]:
    """Short citation labels the model can copy without corrupting them.

    A chronicle entry ID ends in sixteen hex characters, which a model transcribes wrongly often
    enough to fail an otherwise sound dossier. It is given `e12` to copy and the real ID is
    restored here, so a citation is verified rather than trusted either way.
    """

    labels: dict[str, str] = {}
    known: set[str] = set()
    for _section_id, _heading, group in plan:
        for entry in group:
            if entry.entry_id not in known:
                known.add(entry.entry_id)
                labels[f"e{len(labels) + 1}"] = entry.entry_id
    for anchor in anchors:
        for entry_id in anchor.entry_ids:
            if entry_id not in known:
                known.add(entry_id)
                labels[f"e{len(labels) + 1}"] = entry_id
    return labels


def evidence_for(
    entries: Iterable[ChronicleEntry],
    labels: Mapping[str, str],
    extracts: Mapping[str, SubjectExtract] | None = None,
    prominent_limit: int = MAXIMUM_EVENTS_IN_PROSE,
) -> str:
    """The complete and only allowed input for one section, as the model will see it.

    Every record is shown, including ones a paragraph will not have room to name. Hiding them
    would leave the writer choosing among an arbitrary subset; showing them, marked by how much
    has been written about each, lets it choose what to lead with and leave the rest to the
    register.
    """

    by_entry = {entry_id: label for label, entry_id in labels.items()}
    materialized = sorted(
        entries, key=lambda entry: (entry.month or 13, entry.day or 32)
    )
    prominent = {
        entry.entry_id
        for entry in _most_written_about(materialized, prominent_limit)
    }
    lines = [
        f"[{by_entry.get(entry.entry_id, entry.entry_id)}]"
        + ("*" if entry.entry_id in prominent else " ")
        + (f" {MONTHS[entry.month - 1]} {entry.day} -" if entry.month and entry.day else "")
        + (f" ({entry.topic})" if entry.topic and entry.topic not in ("Events",) else "")
        + f" {entry.text}"
        for entry in materialized
    ]
    if extracts:
        context: list[SubjectExtract] = []
        for entry in materialized:
            found = extracts.get(entry.subject_title or "")
            if found and found.canonical_title not in {c.canonical_title for c in context}:
                context.append(found)
        if context:
            lines.append("")
            lines.append("Background on the subjects above:")
            lines.extend(f"  {item.canonical_title}: {item.extract}" for item in context)
    return "\n".join(lines)


def section_evidence_text(
    entries: Sequence[ChronicleEntry],
    extracts: Mapping[str, SubjectExtract],
    clusters: Sequence[EntryCluster] = (),
) -> str:
    """Everything one section is allowed to say, for the containment check.

    The dates are rendered back out because a chronicle entry keeps them in structured fields, so
    checking against bare text would reject "January 18" as invented when the entry is dated
    exactly that.

    A section also gets the year's other records about the same subjects. Scoping a block to its
    own records exactly was too tight to write from: the religion section of 1492 held the papal
    conclave beginning on 8 August and not the election of Alexander VI three days later, which
    the year records under another lens. A writer that stops mid-conclave is not being careful,
    and one that finishes it was rejected five attempts running. Widening on the source's own
    links keeps the world closed and makes it the right shape, which is the same argument as for
    the anchors.
    """

    lines: list[str] = []
    seen: set[int] = set()
    known = {entry.entry_id for entry in entries}
    material = list(entries)
    for cluster in clusters:
        if cluster.entry_id in known:
            continue
        if any(_shares_a_subject_entry(entry, cluster) for entry in entries):
            material.append(cluster.lead)
    for entry in material:
        prefix = date_text(entry.month, entry.day)
        lines.append(f"{prefix} {entry.text}" if prefix else entry.text)
        if entry.qualifier:
            lines.append(entry.qualifier)
        for title in (entry.subject_title or "", *entry.linked_titles):
            found = extracts.get(title)
            if found and found.page_id not in seen:
                seen.add(found.page_id)
                lines.append(found.extract)
    return "\n".join(lines)


def _shares_a_subject_entry(entry: ChronicleEntry, cluster: EntryCluster) -> bool:
    other = cluster.lead
    if entry.subject_wikidata_id and entry.subject_wikidata_id == other.subject_wikidata_id:
        return True
    for one, two in ((entry, other), (other, entry)):
        subject = display_title(one.subject_title)
        if subject and len(subject) >= 4 and subject in two.linked_titles:
            return True
    return False


def resolve_labels(payload: Any, labels: Mapping[str, str]) -> Any:
    """Turn the labels the model cited back into chronicle entry IDs."""

    if not isinstance(payload, dict):
        return payload
    for key in ("sections", "anchors"):
        blocks = payload.get(key)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            given = block.get("entry_ids")
            if not isinstance(given, list):
                continue
            block["entry_ids"] = list(
                dict.fromkeys(
                    labels.get(str(cited).strip("[]"), str(cited)) for cited in given
                )
            )
    return payload


def evidence_text(chronicle: YearChronicle, context: YearContext | None = None) -> str:
    """Every word the dossier is allowed to draw on, for the whole-dossier containment check.

    Subject article leads count as evidence alongside the year's own entries. Adding them widens
    what the writer may legitimately say without weakening the rule: the set is larger, and still
    closed.

    Dates are rendered back out as the model was shown them. A chronicle entry keeps its date in
    structured fields rather than in its text, so checking against the bare text would reject
    "January 18" as an invented number when the entry is dated exactly that.
    """

    lines: list[str] = [extract.extract for extract in chronicle.subject_extracts]
    for entry in chronicle.entries:
        if entry.month and entry.day:
            lines.append(f"{MONTHS[entry.month - 1]} {entry.day} {entry.text}")
        elif entry.month:
            lines.append(f"{MONTHS[entry.month - 1]} {entry.text}")
        else:
            lines.append(entry.text)
        if entry.qualifier:
            lines.append(entry.qualifier)
    if context:
        for conflict in context.conflicts:
            lines.append(f"{conflict.title} {conflict.start_year} {conflict.end_year}")
    return "\n".join(lines)


def overview_digest(
    chronicle: YearChronicle,
    clusters: Sequence[EntryCluster],
    lenses: Mapping[str, str],
    lede: str,
    themes: Sequence[Any],
    incumbents: Sequence[Any],
    context: YearContext | None,
    anchors: Sequence[Any] = (),
) -> str:
    """What the overview paragraph is written from: a digest of the year, not the year.

    Handing the whole chronicle to a paragraph that has to be short guarantees a summary, and a
    summary of a hundred and ninety-six records is where a generalisation nobody recorded gets
    made. So the digest is a sample rather than the corpus: the most-written-about handful under
    each lens, in the source's own words, plus what was already assembled above the paragraph —
    the offices, the wars, the counts.

    It has to be big enough to write from. The first version carried only lens names and subject
    names, and the paragraph that came back reached past it for Catherine Parr and the Index
    Librorum Prohibitorum, which were in the year but not in the digest. A digest too thin to
    write from does not make the writing safer; it makes the rejection systematic.
    """

    lines = [f"The year is {chronicle.year}.", "", "Its most-written-about records:", lede, ""]
    if anchors:
        # The overview sits above the anchors on the page and is meant to name the threads a
        # reader can already see. Leaving the anchors out of its evidence meant it kept reaching
        # for Charles V, who has a section of his own further down — a rejection that was really
        # the digest disagreeing with the page.
        lines.append("The happenings this dossier gives room to:")
        for anchor in anchors:
            for cluster in anchor.clusters:
                dated = date_text(cluster.month, cluster.day)
                lines.append(f"  {dated + ' — ' if dated else ''}{cluster.lead.text}")
        lines.append("")
    by_lens: dict[str, list[EntryCluster]] = {}
    for cluster in clusters:
        if cluster.kind.value != "event":
            continue
        lens = cluster.lens(lenses)
        if lens:
            by_lens.setdefault(lens, []).append(cluster)
    for lens, heading in LENS_HEADINGS.items():
        group = by_lens.get(lens, [])
        if not group:
            continue
        lines.append(f"{heading} — {len(group)} records, including:")
        for cluster in most_written_about(group, OVERVIEW_RECORDS_PER_LENS):
            dated = date_text(cluster.month, cluster.day)
            lines.append(f"  {dated + ' — ' if dated else ''}{cluster.lead.text}")
        lines.append("")
    if incumbents:
        lines.append("Offices held through the year:")
        lines.extend(f"  {row.place}: {row.office} {row.holder}" for row in incumbents)
        lines.append("")
    if context and context.conflicts:
        lines.append("Wars Wikidata records as running across the year:")
        lines.extend(
            f"  {conflict.title} ({conflict.start_year} to {conflict.end_year})"
            + (" — ended this year" if conflict.ended_this_year else "")
            for conflict in context.conflicts
        )
    return "\n".join(lines)


def _section_schema() -> dict[str, Any]:
    schema = YearDossierContent.model_json_schema()

    def prune(value: Any) -> None:
        if isinstance(value, dict):
            for keyword in ("minLength", "maxLength", "minItems", "maxItems", "pattern"):
                value.pop(keyword, None)
            for nested in value.values():
                prune(nested)
        elif isinstance(value, list):
            for nested in value:
                prune(nested)

    prune(schema)
    return schema


# Openings that announce a year instead of telling the reader something. A prompt alone does not
# stop these; they are the most worn groove in the model's training and it returns to them.
_DENIED_LEDE_OPENINGS = re.compile(
    r"^\s*(?:in\s+)?-?\d{1,4}\s*(?:,|\s+(?:was|saw|marked|witnessed|brought))"
    r"|^\s*the\s+year\b"
    r"|^\s*this\s+year\b"
    r"|^\s*one\s+of\s+the\b",
    re.IGNORECASE,
)
# "a year of war, science and political change" says nothing and appears everywhere.
_DENIED_DOSSIER_PHRASES: tuple[str, ...] = (
    "a year of",
    "a year marked by",
    # The summing-up closer. "The year was busy with Ottoman expansion, Franco-Ottoman
    # cooperation, and English alignments against France" restates the paragraph above it in
    # abstractions and is the last thing a reader needs.
    "the year was busy",
    "the year saw",
    "was a year",
    "is remembered",
    "would go on to",
    "left a lasting",
    "saw the rise of",
    "would prove",
    "set the stage",
    "in many ways",
    "across the globe",
    "the world was",
)
# "January 3: Name, description." is a list with punctuation standing in for sentences.
_LIST_FORMATTING = re.compile(
    r"(?:^|\s)(?:" + "|".join(MONTHS) + r")\s+\d{1,2}\s*:",
)
# Significance, refused absolutely rather than closed-world. Everywhere else in this pipeline a
# phrase is only denied when the model introduced it, because carrying the source's own wording
# across is restatement rather than invention. A gloss is the one place that rule does not hold:
# an article is free to say somebody was one of the greatest portraitists of their century, and
# this tier has no reader who could stand behind repeating it. What they did is carried; what
# anyone thinks of it is not.
_DENIED_GLOSS_PHRASES: tuple[str, ...] = (
    "one of the greatest",
    "one of the most",
    "considered one of",
    "regarded as one of",
    "is considered",
    "is regarded",
    "best known",
    "best-known",
    "remembered for",
    "most important",
    "most influential",
    "greatest",
    "masterpiece",
    "renowned",
    "celebrated as",
    "widely regarded",
    "landmark",
    "seminal",
)
_ECHO_WINDOW = 12


def _shingles(text: str, size: int = _ECHO_WINDOW) -> set[str]:
    words = re.findall(r"\w+", text.casefold())
    return {" ".join(words[start : start + size]) for start in range(len(words) - size + 1)}


def prompt_echoes(prose: str, prompt: str) -> list[str]:
    """Spans the model copied out of its own instructions.

    Found in a real 1543 run: the dossier's lede was the prompt's worked example, word for word,
    including a date the example had chosen. Every name and number in it appeared somewhere in the
    year's records, so nothing rejected it. An illustration of good writing is the one piece of
    text in the request that is not evidence, and copying it is the one way to produce a sentence
    that passes every check while having been written by nobody about nothing.
    """

    return sorted(_shingles(prose) & _shingles(prompt))


def _prose_faults(
    blocks: Sequence[tuple[str, str]],
    prompt: str | None = None,
) -> list[str]:
    """Report register and formatting faults across every generated block."""

    faults: list[str] = []
    whole = "\n".join(prose for _, prose in blocks).casefold()
    faults.extend(
        f"phrase:{phrase}" for phrase in _DENIED_DOSSIER_PHRASES if phrase in whole
    )
    for block_id, prose in blocks:
        if _DENIED_LEDE_OPENINGS.match(prose):
            faults.append(f"opening:{block_id}|{prose[:40]!r}")
        if len(_LIST_FORMATTING.findall(prose)) >= 2:
            faults.append(f"list-formatting:{block_id}|")
        if prompt:
            for echo in prompt_echoes(prose, prompt):
                faults.append(f"prompt-echo:{block_id}|{echo!r}")
    return sorted(faults)


def _headline_of(prose: str, limit: int = 200) -> str:
    """A prefix that ends on a word.

    The containment check reads the headline and the body together, so a prefix cut at a fixed
    character count hands it half a word. "The Ottoman Empire" sliced at two hundred characters
    became "The Ottoma", which is not in any source and was reported as an invented name — a
    rejection caused entirely by the checker's own input.
    """

    if len(prose) <= limit:
        return prose
    cut = prose[:limit]
    return cut[: cut.rfind(" ")] if " " in cut else cut


# Emphasis the model adds around a title. The instruction says plain text and it mostly complies;
# when it does not, the asterisks are formatting rather than a claim, and discarding a sound
# dossier over them would be the same mistake as rejecting a trimmed section prefix. Stripping is
# also what keeps prose-link offsets meaningful, since a link is attached at a character position.
_EMPHASIS = re.compile(r"(?<!\w)([*_]{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)", re.S)


def strip_emphasis(prose: str) -> str:
    previous = None
    while previous != prose:
        previous = prose
        prose = _EMPHASIS.sub(r"\2", prose)
    return prose


def near_misses(names: Sequence[str], evidence: str) -> dict[str, str]:
    """For each name the evidence does not contain, the source word it is nearest to.

    The commonest rejection is not an invention. It is a word-form variant: the source writes
    "Chantz" and the model writes "Chants", or "Erechtheum" becomes "Erechtheion". Told only to
    remove the word, the model removes the sentence around it and reintroduces the same spelling
    on the next attempt, because it does not know what the source actually wrote. Telling it is
    not a relaxation — the containment check is unchanged and still decides — it is the difference
    between a correction and a complaint.
    """

    vocabulary = sorted({match.group() for match in re.finditer(r"[^\W\d_]{4,}", evidence)})
    suggestions: dict[str, str] = {}
    for name in names:
        close = get_close_matches(name, vocabulary, n=1, cutoff=0.8)
        if close and close[0] != name:
            suggestions[name] = close[0]
    return suggestions


def _containment(prose: str, evidence: str) -> dict[str, Any]:
    report = closed_world_report(
        DossierRestatementContent(
            result=RestatementResult.RESTATED,
            headline=_headline_of(prose),
            text=prose,
            timeline=[],
            unsuitable_reason=None,
        ),
        evidence,
    )
    faults = {
        name: value
        for name, value in report.items()
        if value and name != "retained_furniture"
    }
    suggestions = near_misses(faults.get("unsupported_names", []), evidence)
    if suggestions:
        faults["near"] = suggestions
    return faults


def validate_dossier_content(
    content: YearDossierContent,
    chronicle: YearChronicle,
    plan: Sequence[tuple[str, str, list[ChronicleEntry]]],
    anchors: Sequence[AnchorPlan] = (),
    people: Sequence[PersonPlan] = (),
    *,
    context: YearContext | None = None,
    overview_evidence: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Report every way the dossier left its evidence. Empty means it stayed inside.

    Containment is checked twice, and the second time is the one that bites. The whole dossier is
    checked against the whole year, which catches anything invented outright. Then every block is
    checked against its own evidence alone, which catches a paragraph borrowing a name from a
    record it is not about. The second check cannot catch a fusion either — nothing mechanical
    can — but it is the difference between a paragraph that could fuse any two of a hundred and
    ninety-six facts and one that could fuse any two of three.
    """

    known = {entry.entry_id for entry in chronicle.entries}
    expected = {section_id for section_id, _, _ in plan}
    report: dict[str, Any] = {}

    returned = {section.section_id for section in content.sections}
    if returned != expected:
        report["sections"] = sorted(returned.symmetric_difference(expected))

    expected_anchors = {anchor.anchor_id for anchor in anchors}
    returned_anchors = {anchor.anchor_id for anchor in content.anchors}
    if returned_anchors != expected_anchors:
        report["anchors"] = sorted(returned_anchors.symmetric_difference(expected_anchors))

    cited: list[str] = [
        entry_id
        for section in content.sections
        for entry_id in section.entry_ids
    ]
    cited.extend(
        entry_id for anchor in content.anchors for entry_id in anchor.entry_ids
    )
    unresolved = sorted({entry_id for entry_id in cited if entry_id not in known})
    if unresolved:
        report["unresolved_citations"] = unresolved

    extracts = extract_index(chronicle.subject_extracts)
    clusters = cluster_entries(chronicle.entries)
    for section in content.sections:
        group = next(
            (entries for section_id, _, entries in plan if section_id == section.section_id),
            None,
        )
        if group is None:
            continue
        faults = _containment(
            section.prose,
            f"{chronicle.year}\n{section_evidence_text(group, extracts, clusters)}",
        )
        if faults:
            report[f"block:{section.section_id}"] = faults

    expected_people = {planned.label for planned in people}
    returned_people = {person.person_id for person in content.people}
    if returned_people != expected_people:
        report["people"] = sorted(returned_people.symmetric_difference(expected_people))

    by_person = {planned.label: planned for planned in people}
    for person in content.people:
        planned_person = by_person.get(person.person_id)
        if planned_person is None:
            continue
        faults = _containment(
            person.gloss, f"{chronicle.year}\n{planned_person.evidence()}"
        )
        if faults:
            report[f"block:{person.person_id}"] = faults

    by_anchor = {anchor.anchor_id: anchor for anchor in anchors}
    for draft in content.anchors:
        planned = by_anchor.get(draft.anchor_id)
        if planned is None:
            continue
        faults = _containment(draft.prose, f"{chronicle.year}\n{planned.evidence()}")
        if faults:
            report[f"block:{draft.anchor_id}"] = faults

    if overview_evidence is not None:
        faults = _containment(
            content.overview, f"{chronicle.year}\n{overview_evidence}"
        )
        if faults:
            report["block:overview"] = faults

    # The containment check is the restatement tier's, unchanged, with the year's records standing
    # in for a single extract. A dossier is a restatement of many entries at once.
    body = "\n\n".join(
        [
            content.overview,
            *(anchor.prose for anchor in content.anchors),
            *(person.gloss for person in content.people),
            *(section.prose for section in content.sections),
        ]
    )
    for name, value in _containment(
        body, f"{chronicle.year}\n{evidence_text(chronicle, context)}"
    ).items():
        report[name] = value

    blocks = [
        ("overview", content.overview),
        *((anchor.anchor_id, anchor.prose) for anchor in content.anchors),
        *((section.section_id, section.prose) for section in content.sections),
    ]
    # A gloss is one sentence and opens on a name by design, so the opening rule does not apply
    # to it; the deny list and containment still do.
    gloss_faults = _prose_faults(
        [(person.person_id, person.gloss) for person in content.people], prompt
    )
    gloss_faults = [fault for fault in gloss_faults if not fault.startswith("opening:")]
    for person in content.people:
        lowered = person.gloss.casefold()
        gloss_faults.extend(
            f"significance:{person.person_id}|{phrase}"
            for phrase in _DENIED_GLOSS_PHRASES
            if phrase in lowered
        )
    prose_faults = _prose_faults(blocks, prompt) + gloss_faults
    if prose_faults:
        report["prose"] = sorted(prose_faults)
    return report


def link_index(chronicle: YearChronicle) -> list[tuple[str, SubjectExtract]]:
    """Surface forms that may be linked, longest first so the fullest name wins.

    A subject is linkable under its own title, its canonical title, and — for a multi-word
    personal name — its last word, because prose says "Copernicus" after saying it in full once.
    A single-word surname is only admitted when it is unambiguous across the year.
    """

    forms: dict[str, list[SubjectExtract]] = {}
    for extract in chronicle.subject_extracts:
        for form in {extract.title, extract.canonical_title}:
            forms.setdefault(form, []).append(extract)
        # "Nicolaus Copernicus" -> "Copernicus". But "Mary, Queen of Scots" is a title, not a
        # name, and its last word is a people rather than a surname: linking "Scots" reads as
        # a mistake. A comma or a lower-case connective marks a title, so those keep only
        # their full form.
        title = extract.canonical_title
        words = title.split()
        looks_like_a_title = "," in title or any(word.islower() for word in words)
        # "Spanish Empire" fails the same way: its last word is a common noun, and the corpus
        # lexicon already knows which words English writes in lower case.
        common = words[-1].casefold() in common_words()
        if (
            not looks_like_a_title
            and not common
            and len(words) >= 2
            and len(words[-1]) > 3
            and words[-1][0].isupper()
        ):
            forms.setdefault(words[-1], []).append(extract)
    unambiguous = [
        (form, found[0])
        for form, found in forms.items()
        if len({item.page_id for item in found}) == 1
    ]
    return sorted(unambiguous, key=lambda pair: -len(pair[0]))


def attach_links(prose: str, index: Sequence[tuple[str, SubjectExtract]]) -> list[ProseLink]:
    """Link the first mention of each subject, without overlapping an existing link.

    Only the first occurrence is linked. Linking every mention turns a paragraph into a field of
    blue, and the reader only needs one route to the source.
    """

    taken: list[tuple[int, int]] = []
    links: list[ProseLink] = []
    linked_pages: set[int] = set()
    for form, extract in index:
        if extract.page_id in linked_pages:
            continue
        for match in re.finditer(rf"(?<!\w){re.escape(form)}(?!\w)", prose):
            start, end = match.span()
            if any(start < other_end and other_start < end for other_start, other_end in taken):
                continue
            taken.append((start, end))
            linked_pages.add(extract.page_id)
            links.append(
                ProseLink(
                    start=start,
                    end=end,
                    text=prose[start:end],
                    url=extract.url,
                    title=extract.canonical_title,
                )
            )
            break
    return sorted(links, key=lambda link: link.start)


def build_year_dossier(
    content: YearDossierContent,
    chronicle: YearChronicle,
    plan: Sequence[tuple[str, str, list[ChronicleEntry]]],
    anchors: Sequence[AnchorPlan] = (),
    people: Sequence[PersonPlan] = (),
    *,
    lenses: Mapping[str, str] | None = None,
    context: YearContext | None = None,
    prompt_version: str,
    prompt_sha256: str,
    prompt_text: str | None = None,
    model_identifier: str,
    generated_at: datetime,
    provider_response_id: str | None = None,
) -> YearDossier:
    lenses = dict(lenses or {})
    clusters = cluster_entries(chronicle.entries)
    lede, headlines = assemble_lede(chronicle, clusters)
    themes = build_themes(clusters, lenses, LENS_HEADINGS)
    incumbents = build_incumbents(chronicle.entries)
    digest = overview_digest(
        chronicle, clusters, lenses, lede, themes, incumbents, context, anchors
    )
    report = validate_dossier_content(
        content,
        chronicle,
        plan,
        anchors,
        people,
        context=context,
        overview_evidence=digest,
        prompt=prompt_text,
    )
    if report:
        rejection = RestatementRejected(
            f"year:{chronicle.year}", report, content.model_dump(mode="json")
        )
        # How to say to the model which block it must repair, in the model's own vocabulary.
        rejection.labels = {planned.anchor_id: planned.label for planned in anchors}
        # Carried so a last-resort repair can rebuild the dossier against the same generation
        # rather than inventing a new provenance for prose that was already written.
        rejection.prompt_version = prompt_version
        rejection.prompt_sha256 = prompt_sha256
        rejection.model_identifier = model_identifier
        rejection.generated_at = generated_at
        rejection.provider_response_id = provider_response_id
        raise rejection

    headings = {
        section_id: (heading, section_id.split(":", 1)[1])
        for section_id, heading, _ in plan
    }
    index = link_index(chronicle)
    sections = [
        YearDossierSection(
            section_id=draft.section_id,
            heading=headings[draft.section_id][0],
            lens=headings[draft.section_id][1],
            prose=draft.prose,
            entry_ids=draft.entry_ids,
            links=attach_links(draft.prose, index),
        )
        for draft in content.sections
    ]
    images = {image.subject_wikidata_id: image for image in (context.images if context else [])}
    by_anchor = {planned.anchor_id: planned for planned in anchors}
    built_anchors = [
        _build_anchor(by_anchor[draft.anchor_id], draft, index, images)
        for draft in content.anchors
        if draft.anchor_id in by_anchor
    ]
    prominent = {
        entry_id for planned in anchors for entry_id in planned.entry_ids
    }
    prominent.update(headline.entry_id for headline in headlines)
    overview = YearOverview(
        prose=content.overview,
        links=attach_links(content.overview, index),
        entry_ids=[headline.entry_id for headline in headlines],
        themes=themes,
        months=month_counts(clusters)[0],
        undated_count=month_counts(clusters)[1],
        event_count=sum(1 for cluster in clusters if cluster.kind.value == "event"),
        birth_count=sum(1 for cluster in clusters if cluster.kind.value == "birth"),
        death_count=sum(1 for cluster in clusters if cluster.kind.value == "death"),
        dated_count=sum(1 for cluster in clusters if cluster.day is not None),
        source_pages=sorted(
            {entry.source_page for entry in chronicle.entries if entry.source_page}
        ),
    )
    register_entries = _glossed_register(
        build_register(chronicle, clusters, lenses, prominent, images),
        content.people,
        people,
        index,
    )
    made = _glossed_works(
        build_works(clusters, extract_index(chronicle.subject_extracts)),
        content.people,
        people,
        index,
    )
    body = year_dossier_body(
        overview.prose,
        [anchor.prose for anchor in built_anchors]
        + [item.gloss for item in register_entries if item.gloss]
        + [work.gloss for work in made if work.gloss],
        [section.prose for section in sections],
    )
    evidence = evidence_text(chronicle, context)
    evidence_checksum = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
    provenance = RestatementProvenance(
        prompt_version=prompt_version,
        prompt_sha256=prompt_sha256,
        model_identifier=model_identifier,
        source_sha256=evidence_checksum,
        output_sha256=canonical_sha256(content),
        generated_at=generated_at,
        provider_response_id=provider_response_id,
    )
    digest_id = canonical_sha256(
        {
            "content": content.model_dump(mode="json"),
            "generation": provenance.model_dump(mode="json"),
        }
    )[:16]
    return YearDossier(
        dossier_id=f"year-dossier:{chronicle.year}:{chronicle.language}:{digest_id}",
        year=chronicle.year,
        language=chronicle.language,
        lede=lede,
        lede_links=attach_links(lede, index),
        headlines=headlines,
        overview=overview,
        anchors=built_anchors,
        sections=sections,
        works=made,
        register_entries=register_entries,
        related_years=build_related_years(chronicle, clusters),
        incumbents=incumbents,
        conflicts=list(context.conflicts) if context else [],
        chronicle_id=chronicle.chronicle_id,
        chronicle_revision_id=chronicle.revision_id,
        evidence_checksum_sha256=evidence_checksum,
        content_checksum_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        source_refs=[chronicle.source_ref],
        generation=provenance,
        validation=RestatementValidation(
            policy_version=POLICY_VERSION,
            source_chars=len(evidence),
            restatement_chars=len(body),
        ),
    )


def trim_repeated_subject(gloss: str, name: str | None) -> str:
    """Drop a name the gloss repeats, when it is already set in bold above the sentence.

    The instruction not to repeat the record is ignored about half the time, and the result is
    "Tokugawa Ieyasu" printed twice a centimetre apart. Removing a prefix is safe in a way that
    rewriting one is not: it deletes, and what is left is checked again by nothing because it was
    already checked as part of the whole.
    """

    if not name:
        return gloss
    matched = re.match(
        rf"^{re.escape(name)}\b(?:\s*,[^,]{{0,80}},)?\s*", gloss
    )
    if not matched or matched.end() == 0:
        return gloss
    remainder = gloss[matched.end() :].strip()
    # Keep it only when what is left reads as a continuation of the name above: a verb, or any
    # lower-case opening, which is what an appositive leaves behind. A remainder that opens on a
    # capital was a sentence built around the name, and cutting it leaves a fragment.
    if len(remainder) < 20:
        return gloss
    if not re.match(
        r"^(?:was|is|were|are|had|would|later|became|wrote|led|founded)\b|^[a-zà-ÿ]",
        remainder,
    ):
        return gloss
    return remainder


def _glossed_works(
    works: list[Any],
    drafts: Sequence[Any],
    planned: Sequence[PersonPlan],
    index: Sequence[tuple[str, SubjectExtract]],
) -> list[Any]:
    by_label = {item.label: item.entry_id for item in planned}
    glosses = {
        by_label[draft.person_id]: draft.gloss
        for draft in drafts
        if draft.person_id in by_label
    }
    trimmed = {
        entry_id: trim_repeated_subject(gloss, _work_title(works, entry_id))
        for entry_id, gloss in glosses.items()
    }
    return [
        work.model_copy(
            update={
                "gloss": trimmed[work.entry_id],
                "gloss_links": attach_links(trimmed[work.entry_id], index),
            }
        )
        if work.entry_id in trimmed
        else work
        for work in works
    ]


def _work_title(works: Sequence[Any], entry_id: str) -> str | None:
    for work in works:
        if work.entry_id == entry_id:
            return str(work.title).split(" (", 1)[0]
    return None


def _glossed_register(
    register: list[Any],
    drafts: Sequence[Any],
    people: Sequence[PersonPlan],
    index: Sequence[tuple[str, SubjectExtract]],
) -> list[Any]:
    """Attach each restated sentence to the person it is about."""

    by_label = {planned.label: planned.entry_id for planned in people}
    glosses = {
        by_label[draft.person_id]: draft.gloss
        for draft in drafts
        if draft.person_id in by_label
    }
    return [
        entry.model_copy(
            update={
                "gloss": (
                    trimmed := trim_repeated_subject(
                        glosses[entry.entry_id], entry.subject_title
                    )
                ),
                "gloss_links": attach_links(trimmed, index),
            }
        )
        if entry.entry_id in glosses
        else entry
        for entry in register
    ]


def _build_anchor(
    planned: AnchorPlan,
    draft: Any,
    index: Sequence[tuple[str, SubjectExtract]],
    images: Mapping[str, Any],
) -> YearAnchor:
    lead = planned.cluster.lead
    records = [text for cluster in planned.clusters for text in cluster.texts]
    return YearAnchor(
        anchor_id=planned.anchor_id,
        heading=planned.heading[:140],
        date_text=date_text(planned.cluster.month, planned.cluster.day),
        lens=planned.lens,
        prose=draft.prose,
        links=attach_links(draft.prose, index),
        entry_ids=draft.entry_ids,
        records=records,
        subject_title=display_title(lead.subject_title),
        subject_url=planned.extract.url if planned.extract else None,
        subject_wikidata_id=lead.subject_wikidata_id,
        sitelink_count=planned.cluster.sitelink_count,
        quote=quotable(
            planned.background,
            records,
            [
                title
                for cluster in planned.clusters
                for entry in cluster.members
                for title in entry.linked_titles
            ],
            lead.subject_title,
            lead.year,
        ),
        image=images.get(lead.subject_wikidata_id or ""),
        related_years=sorted(
            {year for cluster in planned.clusters for year in cluster.related_years}
        ),
    )


def validate_year_dossier(
    dossier: YearDossier,
    chronicle: YearChronicle,
    context: YearContext | None = None,
) -> None:
    """Re-run every check against the current chronicle. Used before publication."""

    if dossier.chronicle_id != chronicle.chronicle_id:
        raise ValueError("Year dossier is not bound to this chronicle")
    evidence = evidence_text(chronicle, context)
    if dossier.evidence_checksum_sha256 != hashlib.sha256(evidence.encode("utf-8")).hexdigest():
        raise ValueError(
            f"Year dossier is stale: the {chronicle.year} chronicle changed since it was generated"
        )
    if dossier.chronicle_revision_id != chronicle.revision_id:
        raise ValueError("Year dossier revision does not match its chronicle")


def generate_year_dossier(
    chronicle: YearChronicle,
    lenses: Mapping[str, str],
    *,
    prompt_version: str,
    model_identifier: str,
    api_key: str,
    provider: str = "deepseek",
    context: YearContext | None = None,
    generated_at: datetime | None = None,
    client: httpx.Client | None = None,
    attempts: int = 3,
    on_retry: Any = None,
) -> YearDossier:
    """Generate one year's dossier, retrying a rejection rather than loosening the check.

    Rejections here are stochastic — a dropped prefix, a mistyped label — not systematic, so the
    same prompt usually passes on the next attempt. Retrying is the cheap fix; relaxing a check to
    admit a malformed name would be the expensive one, because it would admit real errors too.
    """

    last: RestatementRejected | None = None
    correction: str | None = None
    total = max(1, attempts)
    for attempt in range(1, total + 1):
        try:
            return _generate_once(
                chronicle,
                lenses,
                prompt_version=prompt_version,
                model_identifier=model_identifier,
                api_key=api_key,
                provider=provider,
                context=context,
                generated_at=generated_at,
                client=client,
                correction=correction,
            )
        except RestatementRejected as rejection:
            last = rejection
            correction = correction_note(
                rejection.report, rejection.previous, getattr(rejection, "labels", None)
            )
            if on_retry and attempt < total:
                on_retry(attempt, rejection)
    assert last is not None
    if last.previous is not None:
        repaired = _drop_unsupported_sentences(
            last, chronicle, lenses, context=context, on_retry=on_retry
        )
        if repaired is not None:
            return repaired
    raise last


# A block must keep this many sentences after a deletion, or the deletion is refused and the year
# goes unwritten instead. One surviving sentence is a stub, and a paragraph cut to its last line
# can be left saying something its removed antecedent was carrying.
MINIMUM_SENTENCES_AFTER_REMOVAL = 2
_PROSE_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-\u024f\u201c(])")


def _drop_unsupported_sentences(
    rejection: RestatementRejected,
    chronicle: YearChronicle,
    lenses: Mapping[str, str],
    *,
    context: YearContext | None,
    on_retry: Any = None,
) -> YearDossier | None:
    """Last resort: delete the sentences the check could not support, and check again.

    This is not a relaxation and it is worth being precise about why. Every check runs again,
    unchanged, on what is left; nothing is admitted that would not have been admitted before.
    Deletion can only shrink what the dossier claims. What it buys is coverage: without it one
    archaic spelling in one clause of one paragraph costs a reader the whole year, and at the
    scale this runs there is nobody to intervene.

    It refuses rather than mangles. A block that would fall below two sentences is left alone and
    the year fails, because a paragraph cut to a single line can end up resting on an antecedent
    that went with the deletion.
    """

    plan = plan_sections(chronicle.entries, lenses)
    extracts = extract_index(chronicle.subject_extracts)
    anchors = plan_anchors(chronicle.entries, lenses, extracts)
    people = plan_people(chronicle.entries, extracts)
    payload = dict(rejection.previous or {})
    removed: list[str] = []

    for key, faults in rejection.report.items():
        if not key.startswith("block:") or not isinstance(faults, dict):
            return None
        block = key.split(":", 1)[1]
        tokens = {
            *faults.get("unsupported_names", []),
            *faults.get("unsupported_numbers", []),
        }
        if not tokens or set(faults) - {"unsupported_names", "unsupported_numbers", "near"}:
            return None
        if block.startswith("p") and block[1:].isdigit():
            # A gloss is one sentence. Deleting it leaves nothing, and a person with a blank
            # sentence is worse than a person with none, so the year fails instead.
            return None
        prose = _block_prose(payload, block)
        if prose is None:
            return None
        kept = [
            sentence
            for sentence in _PROSE_SENTENCE.split(prose)
            if not any(
                re.search(rf"(?<!\w){re.escape(token)}(?!\w)", sentence) for token in tokens
            )
        ]
        if len(kept) < MINIMUM_SENTENCES_AFTER_REMOVAL or len(kept) == len(
            _PROSE_SENTENCE.split(prose)
        ):
            return None
        removed.extend(
            sentence.strip()
            for sentence in _PROSE_SENTENCE.split(prose)
            if sentence not in kept
        )
        _set_block_prose(payload, block, " ".join(part.strip() for part in kept))

    if not removed:
        return None
    if on_retry:
        on_retry(0, RestatementRejected(rejection.dossier_id, {"removed": removed}))
    content = YearDossierContent.model_validate(payload)
    dossier = build_year_dossier(
        content,
        chronicle,
        plan,
        anchors,
        people,
        lenses=lenses,
        context=context,
        prompt_version=rejection.prompt_version,
        prompt_sha256=rejection.prompt_sha256,
        model_identifier=rejection.model_identifier,
        generated_at=rejection.generated_at,
        provider_response_id=rejection.provider_response_id,
    )
    return dossier.model_copy(update={"removed_sentences": removed})


def _block_prose(payload: Mapping[str, Any], block: str) -> str | None:
    if block == "overview":
        value = payload.get("overview")
        return value if isinstance(value, str) else None
    key = "anchors" if block.startswith("anchor:") else "sections"
    field = "anchor_id" if key == "anchors" else "section_id"
    for item in payload.get(key) or []:
        if isinstance(item, dict) and item.get(field) == block:
            prose = item.get("prose")
            return prose if isinstance(prose, str) else None
    return None


def _set_block_prose(payload: dict[str, Any], block: str, prose: str) -> None:
    if block == "overview":
        payload["overview"] = prose
        return
    key = "anchors" if block.startswith("anchor:") else "sections"
    field = "anchor_id" if key == "anchors" else "section_id"
    for item in payload.get(key) or []:
        if isinstance(item, dict) and item.get(field) == block:
            item["prose"] = prose


def correction_note(
    report: Mapping[str, Any],
    previous: Any = None,
    block_names: Mapping[str, str] | None = None,
) -> str | None:
    """Turn a rejection into an instruction for the next attempt.

    Re-sending the identical request and hoping is only the right move when a rejection is
    stochastic. Several are not: the check knows exactly which word was not in a block's evidence,
    and withholding that from the retry wastes the one piece of information the run produced.

    This adds nothing to what the model may say. The evidence is unchanged, every check runs again
    on the new attempt, and the note only ever says *remove* — never that something is now
    permitted. Feeding a check's output back is not the same as relaxing it.
    """

    names = dict(block_names or {})
    lines: list[str] = []
    for key, value in sorted(report.items()):
        if key.startswith("block:"):
            block = key.split(":", 1)[1]
            # The model knows an anchor as "a3". The report names it by the identifier the
            # pipeline substituted afterwards, which the model has never seen, so an instruction
            # written in those terms is an instruction about nothing. A 1492 run failed five
            # attempts on one number because every correction addressed a block by a name that
            # did not exist for the reader of the correction.
            block = names.get(block, block)
            faults = value if isinstance(value, dict) else {}
            words = [
                item
                for name in ("unsupported_names", "unsupported_numbers")
                for item in faults.get(name, [])
            ]
            if words:
                near = faults.get("near") or {}
                spelled = "; ".join(
                    f"you wrote {written!r} where the records write {near[written]!r} — "
                    "use the records' spelling exactly"
                    for written in sorted(near)
                )
                lines.append(
                    f"- in {block}: remove {', '.join(sorted(set(words)))}. "
                    "That block's evidence does not contain them. Rewrite the sentence without "
                    "the fact, or drop the sentence."
                    + (f" {spelled}." if spelled else "")
                )
            if faults.get("denied_phrases"):
                lines.append(f"- in {block}: drop the wording {faults['denied_phrases']}.")
        elif key == "unsupported_names" and value:
            lines.append(
                f"- nowhere in this year's records: {', '.join(sorted(set(value)))}. "
                "Remove them entirely."
            )
        elif key == "unsupported_numbers" and value:
            lines.append(
                f"- numbers not in the records: {', '.join(sorted(set(value)))}. Remove them."
            )
        elif key == "prose" and value:
            for fault in value:
                if fault.startswith("opening:"):
                    target = fault.split(":", 1)[1].split("|", 1)[0]
                    lines.append(
                        f"- {names.get(target, target)} opens by announcing the year. "
                        "Start it on a person, a place or a thing done."
                    )
                elif fault.startswith("significance:"):
                    target, _, phrase = fault.split(":", 1)[1].partition("|")
                    lines.append(
                        f"- {names.get(target, target)} says {phrase!r}. That is a judgement "
                        "about how much something mattered, and this dossier does not carry one "
                        "even when the article makes it. Say what was done instead."
                    )
                elif fault.startswith("phrase:"):
                    lines.append(f"- remove the phrase \"{fault.split(':', 1)[1]}\".")
                elif fault.startswith("prompt-echo:"):
                    lines.append(
                        "- one block copies a sentence out of the instructions. "
                        "Write it from the records instead."
                    )
        elif key in ("sections", "anchors", "people") and value:
            missing = ", ".join(names.get(item, item) for item in value)
            lines.append(
                f"- your answer is missing these {key}: {missing}. Return every one of them, "
                "with the identifier exactly as given. Do not merge or rename any."
            )
        elif key == "unresolved_citations" and value:
            lines.append(
                "- some entry_ids do not exist. Cite only the short labels given, exactly."
            )
    if not lines:
        return None
    note = (
        "\n\n# Your previous attempt was rejected by the evidence check\n\n"
        "Return the same JSON with exactly these repairs and no other change. Keep every other "
        "sentence word for word.\n" + "\n".join(lines)
    )
    if previous is not None:
        note += "\n\nYour previous answer:\n" + json.dumps(
            previous, ensure_ascii=False, indent=1
        )
    return note


def _generate_once(
    chronicle: YearChronicle,
    lenses: Mapping[str, str],
    *,
    prompt_version: str,
    model_identifier: str,
    api_key: str,
    provider: str,
    context: YearContext | None,
    generated_at: datetime | None,
    client: httpx.Client | None,
    correction: str | None = None,
) -> YearDossier:
    if not api_key:
        raise ValueError("An API key is required for year-dossier generation")
    plan = plan_sections(chronicle.entries, lenses)
    if not plan:
        raise RestatementRejected(
            f"year:{chronicle.year}", {"evidence": "no entries to write from"}
        )
    by_title = extract_index(chronicle.subject_extracts)
    anchors = plan_anchors(chronicle.entries, lenses, by_title)
    people = plan_people(chronicle.entries, by_title)
    profile = provider_profile(provider)
    clusters = cluster_entries(chronicle.entries)
    lede, _headlines = assemble_lede(chronicle, clusters)
    themes = build_themes(clusters, lenses, LENS_HEADINGS)
    incumbents = build_incumbents(chronicle.entries)
    digest = overview_digest(
        chronicle, clusters, lenses, lede, themes, incumbents, context, anchors
    )
    prompt = build_prompt(chronicle, plan, anchors, people)
    labels = entry_labels(plan, anchors)
    payload = _payload(plan, anchors, people, labels, by_title, digest)
    request = _request(
        profile,
        model_identifier,
        prompt,
        payload + (correction or ""),
        repairing=bool(correction),
    )

    owns_client = client is None
    active = client or httpx.Client(timeout=300)
    try:
        response = active.post(
            profile.url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=request,
        )
        response.raise_for_status()
        body = response.json()
    finally:
        if owns_client:
            active.close()

    content = YearDossierContent.model_validate(
        resolve_labels(
            _normalise_block_ids(_output(profile, body), plan, anchors), labels
        )
    )
    model = body.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("Provider response omitted its model identifier")
    return build_year_dossier(
        content,
        chronicle,
        plan,
        anchors,
        people,
        lenses=lenses,
        context=context,
        prompt_version=prompt_version,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        prompt_text=prompt,
        model_identifier=model,
        generated_at=generated_at or datetime.now(UTC),
        provider_response_id=body.get("id") if isinstance(body.get("id"), str) else None,
    )


def _payload(
    plan: Sequence[tuple[str, str, list[ChronicleEntry]]],
    anchors: Sequence[AnchorPlan],
    people: Sequence[PersonPlan],
    labels: Mapping[str, str],
    extracts: Mapping[str, SubjectExtract],
    digest: str,
) -> str:
    by_entry = {entry_id: label for label, entry_id in labels.items()}
    parts = ["# The year in digest — the only input for `overview`", digest]
    if anchors:
        parts.append(
            "\n# Anchors — one paragraph each, from that anchor's records and nothing else"
        )
        for anchor in anchors:
            cited = " ".join(
                f"[{by_entry[eid]}]" for eid in anchor.entry_ids if eid in by_entry
            )
            parts.append(
                f"\n## {anchor.label} — {anchor.heading}\ncite: {cited}\n{anchor.evidence()}"
            )
    if people:
        parts.append(
            "\n# People — one sentence each, from that person's own article and nothing else"
        )
        for person in people:
            parts.append(
                f"\n## {person.label} ({person.kind}) — {person.name}\n{person.evidence()}"
            )
    parts.append("\n# Sections — the sweep of the year")
    for section_id, heading, group in plan:
        parts.append(
            f"\n## {section_id} — {heading}\n"
            + evidence_for(
                group,
                labels,
                extracts,
                MAXIMUM_PEOPLE_IN_PROSE
                if section_id in ("section:births", "section:deaths")
                else MAXIMUM_EVENTS_IN_PROSE,
            )
        )
    return "\n".join(parts)


def build_prompt(
    chronicle: YearChronicle,
    plan: Sequence[tuple[str, str, list[ChronicleEntry]]],
    anchors: Sequence[AnchorPlan] = (),
    people: Sequence[PersonPlan] = (),
) -> str:
    outline = "\n".join(
        f'- section_id must be exactly "{section_id}" — heading "{heading}" '
        f"({len(group)} entries)"
        for section_id, heading, group in plan
    )
    anchor_outline = "\n".join(
        f'- anchor_id must be exactly "{anchor.label}" — {anchor.heading}'
        for anchor in anchors
    )
    people_outline = "\n".join(
        f'- person_id must be exactly "{person.label}" — {person.name}' for person in people
    )
    return f"""You write the dossier for one year, from that year's records.

Your reader came looking for one thing and stayed. Give them the year as it was lived: dated,
specific, and full of what they did not know.

## Everything you write comes from what is in front of you

The records and the background under them are the whole world. Do not add a name, a number, a
cause or a consequence from anywhere else — not from memory, not from inference. Keep every hedge
the records keep. Where they are thin, write less.

Each block has its own evidence and may use only its own. An anchor may not borrow a name from
another anchor, and a section may not borrow one from a section.

## What a good sentence looks like here

These records are unusually specific. That specificity is the whole value; spending it on summary
wastes it.

- The number, not the adjective. Give the strength of the army, not that it was large.
- The place and the age, not the country. Give the town somebody died in and how old they were.
- The relationship, not the title. Say whose sister she was, not that she was a courtier.
- What a book argued, not that it appeared. Say what it claimed about the world.

## The three things you are writing

**`overview`** — one paragraph, five to eight sentences, written only from the digest at the top
of the input. This is the only place in the dossier that stands back, and it is not a preview:
everything below it will name Copernicus and Suleiman again, so spending your sentences listing
them wastes the one paragraph that could have done something else.

Do this instead. Put things that happened at once beside each other and let the distance between
them show — a book printed in one town while an army took another, a nine-month-old crowned in
the same month a treaty was signed. Say what was already under way before the year opened and
still running when it closed. Say where the records are thick and where they are thin, and be
plain that thin means little was written down rather than that little happened.

You may say two things were true at once, because the digest says so. Never say one caused the
other, that either mattered, or what the year "was" — no summing up, and no closing sentence
that names three themes.

Its first three words decide whether anybody reads the rest. Do not start it with the year, with
"The year", or with any wording that announces a year rather than reporting something. Start with
a person, a place, a book, an army.

**`anchors`** — one paragraph of four to eight sentences each, and this is where the dossier has
room. Take the happening seriously: what it was, who was involved, where, what the record and the
background actually say about it. Use the background under the anchor — it is there so that a
paragraph can say more than the one-line record does. Stay inside that anchor's own evidence.

**`people`** — one sentence each, for somebody born or dead this year, or for a book, painting or
poem the year records as made. Say who or what it was, from that one article and nothing else.

For a person: what they went on to do, or had done, and when. For a work: what it contains, what
it argues, or what it shows. A reader meeting a bare name on a list wants the one fact that makes
them stop, in the fewest words that carry it.

Not why any of it mattered, not what it is remembered for, not its influence, not its legacy —
those are claims the article may make and this dossier may not carry. Twenty-five words at the
outside. Do not repeat the dates, the nationality or the occupation already in the record; the
reader can see those beside your sentence, and repeating them wastes the only sentence there is.

**`sections`** — one paragraph each, sweeping. These carry the rest of the year, so they move
fast: the most-written-about records get a clause each and the others are left to the register
beneath the dossier, where every record appears anyway. There is no births or deaths section:
those are rendered from the records, and your sentences above are what they carry.

## Let the year stay simultaneous

A year is not a story. It is a coincidence, and the pleasure is in the distance between things
that happened at once. Set them side by side and let the reader feel it.

## Structure

The blocks are fixed. Do not invent, merge, reorder or rename them. Cite in `entry_ids` the
short label of every record a block draws on — "e12", exactly as given, never invented.

A record marked with * is one many languages have written about. Lead with those and give them
room; mention the rest only where they earn it.

Anchors:
{anchor_outline or "- none this year"}

People:
{people_outline or "- none this year"}

Sections:
{outline}

## Voice

Plain, direct, unhurried. Short declarative sentences that carry weight. Past tense. The ordinary
word: built, not constructed. Never the stock phrases of encyclopedia filler — no tapestries, no
testaments, no turning points, no legacies, and never call a year "a year of" anything.

Open every block on the most concrete thing in it — a person, a place, a thing done — never on
the year. Not "In 1543, Copernicus published" and not "The year saw"; just "Copernicus was
presented a copy of". The reader already knows which year they are in. In the births and deaths
sections write sentences about people, not dated list entries.

Write plain text with no markup at all. Names are linked afterwards from records that hold the
addresses, so a link you write would be a guess.

Do not copy any sentence out of these instructions. Nothing here is evidence.

Return only a json object matching the supplied schema."""


def _normalise_block_ids(
    payload: Any,
    plan: Sequence[tuple[str, str, list[ChronicleEntry]]],
    anchors: Sequence[AnchorPlan],
) -> Any:
    """Restore identifiers a provider without schema enforcement tends to mangle.

    The identifier is ours, not the model's — it is handed over in the prompt and only has to come
    back intact. Rejecting a whole dossier because a prefix was trimmed would discard sound prose
    over a formatting slip, so an unambiguous match is repaired instead.
    """

    if not isinstance(payload, dict):
        return payload
    if isinstance(payload.get("overview"), str):
        payload["overview"] = strip_emphasis(payload["overview"])
    for block in (*(payload.get("sections") or []), *(payload.get("anchors") or [])):
        if isinstance(block, dict) and isinstance(block.get("prose"), str):
            block["prose"] = strip_emphasis(block["prose"])
    known = {section_id for section_id, _, _ in plan}
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        given = section.get("section_id")
        if not isinstance(given, str) or given in known:
            continue
        candidate = given if given.startswith("section:") else f"section:{given}"
        if candidate in known:
            section["section_id"] = candidate
    by_label = {anchor.label: anchor.anchor_id for anchor in anchors}
    for anchor in payload.get("anchors") or []:
        if not isinstance(anchor, dict):
            continue
        given = anchor.get("anchor_id")
        if isinstance(given, str) and given.strip("[]") in by_label:
            anchor["anchor_id"] = by_label[given.strip("[]")]
    return payload


def _request(
    profile: ProviderProfile,
    model: str,
    prompt: str,
    payload: str,
    *,
    repairing: bool = False,
) -> dict[str, Any]:
    user = "Records for this year (the complete and only allowed input):\n" + payload
    if profile.api_style == "responses":
        return {
            "model": model,
            "store": False,
            "instructions": prompt,
            "input": user,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "palimpsest_year_dossier",
                    "strict": True,
                    "schema": _section_schema(),
                }
            },
        }
    return {
        "model": model,
        "stream": False,
        "max_tokens": profile.max_output_tokens,
        "response_format": {"type": "json_object"},
        # A repair is a mechanical edit to text that already exists, so sampling widely is
        # actively unhelpful: the model rewrites paragraphs that were accepted and reintroduces
        # faults the previous attempt had removed. The first attempt keeps its range.
        **({"temperature": 0.2} if repairing else {}),
        **dict(profile.extra_body),
        "messages": [
            {"role": "system", "content": prompt + "\n\nSchema:\n" + json.dumps(_section_schema())},
            {"role": "user", "content": user},
        ],
    }


def _output(profile: ProviderProfile, body: dict[str, Any]) -> Any:
    if profile.api_style == "responses":
        texts = [
            part.get("text")
            for item in body.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        ]
        if len(texts) != 1:
            raise ValueError("Provider response must contain exactly one structured output")
        raw = str(texts[0])
    else:
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Provider response must contain exactly one choice")
        choice = choices[0]
        if choice.get("finish_reason") not in (None, "stop"):
            raise ValueError(
                f"Provider stopped before finishing the dossier: {choice.get('finish_reason')}"
            )
        raw = str((choice.get("message") or {}).get("content") or "")
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ValueError("Provider structured output is not valid JSON") from error


def read_chronicle(path: Path) -> YearChronicle:
    return YearChronicle.model_validate_json(path.read_bytes())


def read_year_context(path: Path) -> YearContext:
    return YearContext.model_validate_json(path.read_bytes())
