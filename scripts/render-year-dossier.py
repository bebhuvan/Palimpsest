"""Render a year dossier to one self-contained HTML page, for looking at.

Rendering the data finds bugs no test does. Junk records, broken markup, links landing on the
wrong span and headings that read as nonsense are all invisible in JSON and obvious on a page.
This is a debugging instrument that happens to be the shape of the product: it renders exactly
what the artifact contains and nothing it does not, so anything ugly here is ugly in the data.

    uv run python scripts/render-year-dossier.py \\
      --dossier data/chronicle/1543-dossier.json --output build/1543.html
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from history_pipeline.chronicle import MONTHS

DISCLOSURE = (
    "This dossier was written by a machine and has not been read by a person. Every name and "
    "date in the prose appears in the records it was written from \u2014 checked, not trusted. "
    "The connections are ours."
)


def linked(text: str, links: list[dict[str, Any]]) -> str:
    """Rebuild prose with its links, from character offsets the pipeline verified."""

    out: list[str] = []
    cursor = 0
    for link in sorted(links, key=lambda item: item["start"]):
        out.append(html.escape(text[cursor : link["start"]]))
        out.append(
            f'<a href="{html.escape(link["url"])}" title="{html.escape(link["title"])}">'
            f'{html.escape(text[link["start"] : link["end"]])}</a>'
        )
        cursor = link["end"]
    out.append(html.escape(text[cursor:]))
    return "".join(out)


def anchor_block(anchor: dict[str, Any], year: int) -> str:
    parts = ['<section class="anchor">']
    image = anchor.get("image")
    if image:
        parts.append(
            f'<figure><img src="{html.escape(image["image_url"])}" alt="" loading="lazy">'
            f'<figcaption><a href="{html.escape(image["descriptor_url"])}">'
            f'{html.escape(image["attribution"])}</a></figcaption></figure>'
        )
    date = anchor.get("date_text")
    parts.append(
        f'<h3>{html.escape(anchor["heading"])}'
        + (f'<span class="when">{html.escape(date)} {year}</span>' if date else "")
        + "</h3>"
    )
    parts.append(f'<p class="prose">{linked(anchor["prose"], anchor.get("links", []))}</p>')
    if anchor.get("quote"):
        quote = anchor["quote"]
        parts.append(
            f'<blockquote>{html.escape(quote["text"])}'
            f'<cite>&mdash; <a href="{html.escape(quote["source_url"])}">'
            f'{html.escape(quote["source_title"])}</a>, revision {quote["revision_id"]}</cite>'
            "</blockquote>"
        )
    if anchor.get("records"):
        parts.append('<details class="records"><summary>The records this was written from')
        parts.append(f' ({len(anchor["records"])})</summary><ul>')
        parts.extend(f"<li>{html.escape(record)}</li>" for record in anchor["records"])
        parts.append("</ul></details>")
    if anchor.get("related_years"):
        parts.append(
            '<p class="crosslinks">Reaches into '
            + ", ".join(
                f'<a href="#year-{other}">{other}</a>' for other in anchor["related_years"]
            )
            + "</p>"
        )
    parts.append("</section>")
    return "".join(parts)


def _person_name(entry: dict[str, Any]) -> tuple[str, str]:
    """Split a record into the person and what the source said about them.

    "Tokugawa Ieyasu, Japanese shogun (d. 1616)" is a name, a comma and a description, and it is
    written that way on every year page there is. Splitting it is what turns a list into people.
    """

    text = entry["text"]
    name = entry.get("subject_title")
    if name and text.startswith(name):
        return name, text[len(name) :].lstrip(" ,\u2013-").strip()
    head, _, tail = text.partition(",")
    return (head.strip(), tail.strip()) if tail else (text.strip(), "")


def people_block(entries: list[dict[str, Any]], kind: str, year: int) -> str:
    """Who was born or who died, as faces and sentences rather than a paragraph of commas."""

    chosen = [entry for entry in entries if entry["kind"] == kind]
    if not chosen:
        return ""
    chosen.sort(
        key=lambda item: (
            item.get("gloss") is None,
            -(item.get("sitelink_count") or 0),
            item.get("month") or 13,
            item.get("day") or 32,
        )
    )
    heading = "Born this year" if kind == "birth" else "Died this year"
    other = "died" if kind == "birth" else "born"
    parts = [
        f'<h2>{heading}</h2>',
        f'<p class="note">All {len(chosen)} recorded, most-written-about first. The sentence '
        "under a name is restated from that person's own article and checked against it alone. "
        "It says what they did, never why it mattered.</p>",
        '<ul class="people">',
    ]
    for entry in chosen:
        name, described = _person_name(entry)
        image = entry.get("image")
        parts.append('<li class="person">')
        if image:
            parts.append(
                f'<img class="face" src="{html.escape(image["image_url"])}" alt="" '
                f'loading="lazy" title="{html.escape(image["attribution"])}">'
            )
        else:
            parts.append('<span class="face blank" aria-hidden="true"></span>')
        parts.append('<div class="who">')
        url = entry.get("subject_url")
        shown = html.escape(name)
        parts.append(
            f'<b>{f"<a href=\"{html.escape(url)}\">{shown}</a>" if url else shown}</b>'
        )
        if entry.get("date_text"):
            parts.append(f'<span class="when">{html.escape(entry["date_text"])}</span>')
        if entry.get("related_year"):
            parts.append(
                f'<a class="rel" href="#year-{entry["related_year"]}">'
                f'{other} {entry["related_year"]}</a>'
            )
        if described and not entry.get("gloss"):
            parts.append(f'<span class="said">{html.escape(described)}</span>')
        if entry.get("gloss"):
            parts.append(
                f'<span class="gloss">{linked(entry["gloss"], entry.get("gloss_links", []))}</span>'
            )
        for also in entry.get("also_recorded_as", []):
            parts.append(f'<span class="also">also recorded as: {html.escape(also)}</span>')
        parts.append("</div></li>")
    parts.append("</ul>")
    return "".join(parts)


WORK_HEADINGS = {
    "book": "Books",
    "poem": "Poetry",
    "artwork": "Painting and sculpture",
    "music": "Music",
    "building": "Building",
    "work": "Other works",
}


def works_block(works: list[dict[str, Any]]) -> str:
    """What the year records as made, in the order its own pages filed it."""

    if not works:
        return ""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for work in works:
        grouped.setdefault(work["kind"], []).append(work)
    parts = [
        "<h2>Made this year</h2>",
        '<p class="note">Books, paintings and poems the year\'s own art, literature and poetry '
        "pages record. Creator and title as the source filed them; nothing here is a judgement "
        "about which were any good.</p>",
    ]
    for kind, heading in WORK_HEADINGS.items():
        group = grouped.get(kind)
        if not group:
            continue
        parts.append(f"<h3>{heading}</h3>")
        parts.append('<ul class="works">')
        for work in group:
            parts.append('<li class="work"><div class="what">')
            url = work.get("subject_url")
            title = html.escape(work["title"])
            # A record the parser could not split into a maker and a title is a sentence, not a
            # heading. Set in bold and hyperlinked whole it becomes a paragraph of underline.
            if work.get("creator") or len(work["title"]) <= 70:
                parts.append(
                    f'<b>{f"<a href=\"{html.escape(url)}\">{title}</a>" if url else title}</b>'
                )
            else:
                parts.append(f'<span class="loose">{title}</span>')
                if url and work.get("subject_title"):
                    parts.append(
                        f' <a class="src" href="{html.escape(url)}">'
                        f'{html.escape(work["subject_title"])}</a>'
                    )
            if work.get("creator"):
                parts.append(f'<span class="by">{html.escape(work["creator"])}</span>')
            if work.get("gloss"):
                parts.append(
                    f'<span class="gloss">'
                    f'{linked(work["gloss"], work.get("gloss_links", []))}</span>'
                )
            if work.get("source_page"):
                parts.append(f'<span class="from">{html.escape(work["source_page"])}</span>')
            parts.append("</div></li>")
        parts.append("</ul>")
    return "".join(parts)


def month_spine(overview: dict[str, Any]) -> str:
    """How the year's records fall across its months, shown rather than described."""

    months = overview.get("months") or []
    if not months or not any(months):
        return ""
    peak = max(months)
    bars = "".join(
        f'<span class="bar" style="--h:{round(100 * count / peak)}%" '
        f'title="{MONTHS[index]}: {count} records">'
        f'<i>{MONTHS[index][0]}</i></span>'
        for index, count in enumerate(months)
    )
    undated = overview.get("undated_count") or 0
    return (
        f'<div class="spine">{bars}</div>'
        f'<p class="note">Records by month. {undated} carry no month at all — a year article '
        "dates what its sources dated and no more.</p>"
    )


def register_block(entries: list[dict[str, Any]], year: int) -> str:
    parts = ['<div class="register">']
    current: int | None = -1
    for entry in sorted(
        entries, key=lambda item: (item.get("month") or 13, item.get("day") or 32)
    ):
        month = entry.get("month")
        if month != current:
            current = month
            label = MONTHS[month - 1] if month else "Undated"
            parts.append(f'<h4 class="month">{label}</h4>')
        subject = entry.get("subject_url")
        name = html.escape(entry.get("subject_title") or "")
        parts.append('<div class="row">')
        parts.append(f'<span class="day">{entry.get("day") or ""}</span>')
        parts.append(f'<span class="kind kind-{entry["kind"]}">{entry["kind"]}</span>')
        body = html.escape(entry["text"])
        if subject and name:
            body += f' <a class="src" href="{html.escape(subject)}">{name}</a>'
        if entry.get("qualifier"):
            body += f' <span class="qual">({html.escape(entry["qualifier"])})</span>'
        if entry.get("prominent"):
            body += ' <span class="star" title="given room above">★</span>'
        if entry.get("related_year") and entry["related_year"] != year:
            body += (
                f' <a class="rel" href="#year-{entry["related_year"]}">'
                f'{entry["related_year"]}</a>'
            )
        for also in entry.get("also_recorded_as", []):
            body += f'<span class="also">also recorded as: {html.escape(also)}</span>'
        parts.append(f'<span class="what">{body}</span>')
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


def render(dossier: dict[str, Any]) -> str:
    year = dossier["year"]
    overview = dossier.get("overview") or {}
    head = [
        f"<header><p class=\"kicker\">A year in the world</p><h1>{year}</h1>",
        '<p class="lede">',
    ]
    for headline in dossier.get("headlines", []):
        when = headline.get("date_text")
        head.append(
            '<span class="headline">'
            + (f'<b>{html.escape(when)}</b> ' if when else "")
            + html.escape(headline["text"])
            + "</span>"
        )
    head.append("</p>")
    head.append(
        '<p class="note">The three records most has been written about, in the sources\' own '
        "words. Nothing in this paragraph was generated.</p></header>"
    )

    counts = (
        f'<div class="counts">'
        f'<span><b>{overview.get("event_count", 0)}</b> events</span>'
        f'<span><b>{overview.get("birth_count", 0)}</b> born</span>'
        f'<span><b>{overview.get("death_count", 0)}</b> died</span>'
        f'<span><b>{overview.get("dated_count", 0)}</b> dated to the day</span>'
        f'<span><b>{len(overview.get("source_pages", []))}</b> source pages</span>'
        f"</div>"
    )

    themes = ""
    if overview.get("themes"):
        themes = '<ul class="themes">' + "".join(
            f'<li><b>{html.escape(theme["heading"])}</b> '
            f'<span class="n">{theme["record_count"]}</span>'
            f'<span class="who">{html.escape(", ".join(theme["subjects"]))}</span></li>'
            for theme in overview["themes"]
        ) + "</ul>"

    conflicts = ""
    if dossier.get("conflicts"):
        conflicts = (
            "<h3>Wars already under way</h3>"
            '<p class="note">From Wikidata start and end dates spanning this year, not from the '
            "year article. A war in this list was in progress; the year article records only its "
            "battles.</p><ul class=\"conflicts\">"
            + "".join(
                f'<li><a href="{html.escape(item["url"])}">{html.escape(item["title"])}</a>'
                f'<span class="span">{item["start_year"]}&ndash;{item["end_year"]}</span>'
                + (
                    '<span class="flag">ended this year</span>'
                    if item.get("ended_this_year")
                    else ""
                )
                + (
                    '<span class="flag">began this year</span>'
                    if item.get("began_this_year")
                    else ""
                )
                + "</li>"
                for item in dossier["conflicts"]
            )
            + "</ul>"
        )

    incumbents = ""
    if dossier.get("incumbents"):
        incumbents = (
            "<h3>Who held power</h3><table><tbody>"
            + "".join(
                f"<tr><td>{html.escape(row['place'])}</td>"
                f"<td>{html.escape(row['office'])}</td>"
                f"<td>{html.escape(row['holder'])}</td></tr>"
                for row in dossier["incumbents"]
            )
            + "</tbody></table>"
        )

    overview_prose = ""
    if overview.get("prose"):
        overview_prose = (
            '<p class="prose big">'
            + linked(overview["prose"], overview.get("links", []))
            + "</p>"
        )

    anchors = "".join(anchor_block(anchor, year) for anchor in dossier.get("anchors", []))
    register = dossier.get("register_entries", [])
    births = people_block(register, "birth", year)
    deaths = people_block(register, "death", year)
    spine = month_spine(overview)
    made_ids = {work["entry_id"] for work in dossier.get("works", [])}
    works = works_block(dossier.get("works", []))
    events = [
        item
        for item in register
        if item["kind"] == "event" and item["entry_id"] not in made_ids
    ]

    sections = "".join(
        f'<section class="sweep"><h3>{html.escape(section["heading"])}</h3>'
        f'<p class="prose">{linked(section["prose"], section.get("links", []))}</p>'
        f'<p class="cited">{len(section["entry_ids"])} records</p></section>'
        for section in dossier.get("sections", [])
    )

    related = ""
    if dossier.get("related_years"):
        rows = []
        for item in dossier["related_years"]:
            people = "; ".join(
                (
                    f'<a href="{html.escape(link["subject_url"])}">'
                    f'{html.escape(link["subject_title"] or link["text"][:40])}</a>'
                    if link.get("subject_url")
                    else html.escape(link["text"][:40])
                )
                for link in item["connections"]
            )
            rows.append(
                f'<li id="year-{item["year"]}"><b>{item["year"]}</b>'
                f'<span class="dir">{item["direction"]}</span>'
                f'<span class="who">{people}</span></li>'
            )
        related = (
            "<h3>Years this one reaches</h3>"
            '<p class="note">Every life recorded here has another end. These are the years it '
            "falls in — parsed from the records, not chosen.</p>"
            f'<ul class="related">{"".join(rows)}</ul>'
        )

    generation = dossier.get("generation", {})
    footer = (
        f'<footer><p class="disclose">{html.escape(DISCLOSURE)}</p>'
        f'<p class="meta">Model {html.escape(str(generation.get("model_identifier")))} · '
        f'prompt {html.escape(str(generation.get("prompt_version")))} · '
        f'chronicle revision {dossier.get("chronicle_revision_id")} · '
        f'evidence {html.escape(str(dossier.get("evidence_checksum_sha256"))[:12])} · '
        f'{dossier.get("validation", {}).get("restatement_chars")} characters of prose from '
        f'{dossier.get("validation", {}).get("source_chars")} characters of records</p></footer>'
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{year} — Palimpsest</title>
<style>{STYLE}</style></head><body>
<main>
{"".join(head)}
<div class="layer" id="overview"><h2>The shape of the year</h2>
{counts}{overview_prose}{spine}{themes}{conflicts}{incumbents}</div>
<div class="layer" id="anchors"><h2>Given room</h2>
<p class="note">The happenings most has been written about, each written only from its own
records and the articles they link to.</p>
{anchors}</div>
<div class="layer" id="sweep"><h2>The sweep of the year</h2>{sections}</div>
<div class="layer" id="made">{works}</div>
<div class="layer" id="people">{births}{deaths}</div>
<div class="layer" id="doors">{related}</div>
<div class="layer" id="register"><h2>Every record</h2>
<p class="note">All {len(events)} events, in the sources' own words. Nothing here was
generated; the people and the works are above.</p>
{register_block(events, year)}</div>
{footer}
</main></body></html>"""


STYLE = """
:root{--ink:#17150f;--dim:#6b6558;--rule:#ded7c6;--bg:#faf7f0;--accent:#8a3324;--panel:#f2ede0}
@media (prefers-color-scheme:dark){:root{--ink:#ece7dc;--dim:#9a9284;--rule:#3a352c;
--bg:#14130f;--accent:#d98b5f;--panel:#1d1b15}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:17px/1.6 "Iowan Old Style",Palatino,Georgia,serif}
main{max-width:44rem;margin:0 auto;padding:3rem 1.25rem 6rem}
a{color:var(--accent);text-underline-offset:2px}
h1{font-size:4.5rem;line-height:1;margin:.2em 0;letter-spacing:-.03em}
h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.18em;color:var(--dim);
font-family:ui-sans-serif,system-ui,sans-serif;font-weight:600;
border-top:1px solid var(--rule);padding-top:1rem;margin:3.5rem 0 1.25rem}
h3{font-size:1.32rem;margin:1.6rem 0 .4rem;line-height:1.25}
h3 .when{font-size:.72rem;font-family:ui-sans-serif,system-ui,sans-serif;letter-spacing:.1em;
text-transform:uppercase;color:var(--dim);margin-left:.7em;white-space:nowrap}
.kicker{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.72rem;letter-spacing:.2em;
text-transform:uppercase;color:var(--dim);margin:0}
.lede{font-size:1.22rem;line-height:1.5;margin:1.2rem 0 .6rem}
.headline{display:block;padding:.55rem 0;border-bottom:1px solid var(--rule)}
.headline b{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.7rem;letter-spacing:.1em;
text-transform:uppercase;color:var(--dim);display:inline-block;min-width:7.5em}
.note{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.8rem;line-height:1.5;
color:var(--dim);margin:.5rem 0 1rem}
.counts{display:flex;flex-wrap:wrap;gap:.4rem 1.6rem;font-family:ui-sans-serif,system-ui,
sans-serif;font-size:.78rem;color:var(--dim);padding:.8rem 0;border-bottom:1px solid var(--rule)}
.counts b{font-size:1.15rem;color:var(--ink);font-family:inherit}
.prose{margin:1rem 0}
.prose.big{font-size:1.1rem}
.themes{list-style:none;padding:0;margin:1.2rem 0}
.themes li{display:grid;grid-template-columns:1fr auto;gap:0 .8rem;padding:.5rem 0;
border-bottom:1px solid var(--rule)}
.themes .n{font-variant-numeric:tabular-nums;color:var(--dim)}
.themes .who{grid-column:1/-1;font-size:.8rem;color:var(--dim);
font-family:ui-sans-serif,system-ui,sans-serif}
.conflicts{list-style:none;padding:0;margin:0}
.conflicts li{padding:.4rem 0;border-bottom:1px solid var(--rule);display:flex;
flex-wrap:wrap;gap:.6rem;align-items:baseline}
.conflicts .span{font-variant-numeric:tabular-nums;color:var(--dim);font-size:.85rem}
.flag{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.65rem;letter-spacing:.08em;
text-transform:uppercase;background:var(--accent);color:var(--bg);padding:.1rem .45rem;
border-radius:2px}
table{width:100%;border-collapse:collapse;font-size:.92rem}
td{padding:.4rem .6rem .4rem 0;border-bottom:1px solid var(--rule)}
td:first-child{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.78rem;color:var(--dim);
text-transform:uppercase;letter-spacing:.06em;width:8rem}
.anchor{margin:2.5rem 0;padding-bottom:1.5rem;border-bottom:1px solid var(--rule)}
figure{margin:0 0 1rem;float:right;width:min(42%,15rem);margin-left:1.4rem}
figure img{width:100%;height:auto;display:block;border-radius:2px}
figcaption{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.65rem;line-height:1.4;
color:var(--dim);margin-top:.35rem}
blockquote{margin:1.2rem 0;padding-left:1rem;border-left:2px solid var(--accent);
font-size:.95rem;color:var(--dim);font-style:italic}
cite{display:block;font-style:normal;font-size:.72rem;margin-top:.4rem;
font-family:ui-sans-serif,system-ui,sans-serif}
details.records{clear:both;font-family:ui-sans-serif,system-ui,sans-serif;font-size:.8rem;
color:var(--dim);margin-top:1rem}
details.records summary{cursor:pointer}
details.records ul{margin:.6rem 0 0;padding-left:1.1rem}
details.records li{margin:.3rem 0}
.crosslinks{clear:both;font-family:ui-sans-serif,system-ui,sans-serif;font-size:.78rem;
color:var(--dim)}
.sweep{margin:1.8rem 0}
.cited{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.72rem;color:var(--dim);margin:0}
.related{list-style:none;padding:0;margin:0;
columns:2;column-gap:2rem;font-family:ui-sans-serif,system-ui,sans-serif;font-size:.82rem}
.related li{break-inside:avoid;padding:.45rem 0;border-bottom:1px solid var(--rule)}
.related b{font-size:1rem;font-family:inherit}
.related .dir{color:var(--dim);font-size:.68rem;margin-left:.4em;text-transform:uppercase;
letter-spacing:.08em}
.related .who{display:block;color:var(--dim)}
.register{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.85rem}
.month{font-size:.72rem;text-transform:uppercase;letter-spacing:.14em;color:var(--dim);
margin:1.6rem 0 .4rem;position:sticky;top:0;background:var(--bg);padding:.4rem 0}
.register .row{display:grid;grid-template-columns:2rem 4.2rem 1fr;gap:.6rem;padding:.35rem 0;
border-bottom:1px solid var(--rule);align-items:baseline}
.register .day{text-align:right;color:var(--dim);font-variant-numeric:tabular-nums}
.kind{font-size:.62rem;text-transform:uppercase;letter-spacing:.07em;color:var(--dim);
padding-top:.2em}
.kind-birth{color:#3f7d4f}.kind-death{color:#8a3324}
@media (prefers-color-scheme:dark){.kind-birth{color:#7fb98d}.kind-death{color:#d98b5f}}
.register .also{display:block;color:var(--dim);font-size:.76rem;padding-left:.8rem;
border-left:2px solid var(--rule);margin-top:.3rem}
.register .qual{color:var(--dim);font-size:.76rem}
.register .src{font-size:.76rem}
.register .rel{font-variant-numeric:tabular-nums}
.star{color:var(--accent)}
.spine{display:flex;align-items:flex-end;gap:.35rem;height:5rem;margin:1.4rem 0 .4rem}
.bar{flex:1;background:var(--rule);height:var(--h);min-height:2px;position:relative;
border-radius:1px}
.bar i{position:absolute;bottom:-1.3rem;left:0;right:0;text-align:center;font-style:normal;
font-size:.6rem;color:var(--dim);font-family:ui-sans-serif,system-ui,sans-serif}
.spine+.note{margin-top:1.6rem}
.works{list-style:none;padding:0;margin:.6rem 0 1.8rem}
.work{display:grid;grid-template-columns:1fr;gap:.15rem;padding:.6rem 0;
border-bottom:1px solid var(--rule)}
.work:has(.plate){grid-template-columns:4.4rem 1fr;gap:0 1rem;align-items:start}
.plate{width:4.4rem;height:5.6rem;object-fit:cover;display:block;border-radius:2px;
background:var(--panel)}
.work .what b{font-size:1rem}
.work .by{display:block;color:var(--dim);font-size:.85rem;
font-family:ui-sans-serif,system-ui,sans-serif}
.work .from{display:block;color:var(--dim);font-size:.66rem;margin-top:.25rem;
font-family:ui-sans-serif,system-ui,sans-serif;letter-spacing:.04em}
.work .gloss{display:block;margin-top:.3rem;font-size:.94rem}
.work .loose{font-size:.95rem}
.work .src{font-size:.8rem;white-space:nowrap}
.people{list-style:none;padding:0;margin:1rem 0 2.5rem}
.person{display:grid;grid-template-columns:3.6rem 1fr;gap:0 1rem;padding:.9rem 0;
border-bottom:1px solid var(--rule);align-items:start}
.face{width:3.6rem;height:3.6rem;object-fit:cover;object-position:50% 22%;border-radius:50%;
display:block;background:var(--panel)}
.face.blank{border-radius:50%;background:var(--panel);display:block}
.who b{font-size:1.05rem}
.who .when{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.68rem;letter-spacing:.09em;
text-transform:uppercase;color:var(--dim);margin-left:.6em}
.who .rel{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.68rem;margin-left:.6em;
font-variant-numeric:tabular-nums}
.who .said{display:block;color:var(--dim);font-size:.9rem;margin-top:.1rem}
.who .gloss{display:block;margin-top:.35rem}
.who .also{display:block;color:var(--dim);font-size:.76rem;margin-top:.3rem;padding-left:.7rem;
border-left:2px solid var(--rule);font-family:ui-sans-serif,system-ui,sans-serif}
footer{margin-top:4rem;border-top:1px solid var(--rule);padding-top:1.2rem;
font-family:ui-sans-serif,system-ui,sans-serif}
.disclose{font-size:.85rem;color:var(--ink)}
.meta{font-size:.7rem;color:var(--dim);line-height:1.7}
@media (max-width:34rem){h1{font-size:3rem}figure{float:none;width:100%;margin:0 0 1rem}
.related{columns:1}.register .row{grid-template-columns:1.6rem 1fr}
.register .kind{display:none}}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    dossier = json.loads(arguments.dossier.read_text(encoding="utf-8"))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(render(dossier), encoding="utf-8")
    print(f"wrote {arguments.output}")


if __name__ == "__main__":
    main()
