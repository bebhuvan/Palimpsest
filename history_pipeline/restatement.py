"""Plain-English restatement of exactly one revision-pinned source extract.

A restatement sits deliberately between `source_extract` and `project_interpretation`. It is a
lossy, faithful transformation of a single source: it reorders, compresses and plainly rewords the
text a visitor would otherwise read raw. It never combines sources and never adds a claim.

That weaker claim is what buys a cheaper gate. An editorial dossier asserts something new, so it
needs per-claim citations and a named human reviewer. A restatement asserts nothing new, so what it
needs instead is mechanical proof that it stayed inside its source. This module is that proof:
every number and every proper noun in the output must already exist in the input, the output may
not grow, and a deny list rejects the evaluative register the source did not license.

The checks are deliberately strict and fail closed for the restatement but open for the visitor: a
rejected restatement is simply not published, and the reader falls back to the original extract.
Coverage is the only thing a false positive costs.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import orjson

from history_pipeline.dossiers import canonical_json_bytes, canonical_sha256
from history_pipeline.models import (
    DossierRestatement,
    DossierRestatementContent,
    HistoricalDossier,
    RestatementProvenance,
    RestatementResult,
    RestatementValidation,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

POLICY_VERSION = "closed-world-v1"

_NUMBER_PATTERN = re.compile(r"\d+")
_WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Words that are capitalised for grammatical reasons rather than because they name something. A
# capitalised token outside this set is treated as a proper noun and must exist in the source.
_FUNCTION_WORDS = frozenset(
    {
        "a", "about", "after", "against", "all", "also", "an", "and", "another", "any", "are",
        "around", "as", "at", "be", "because", "been", "before", "began", "being", "both", "built",
        "but", "by", "came", "can", "could", "did", "do", "does", "during", "each", "either",
        "for", "from", "had", "has", "have", "he", "her", "here", "his", "how", "however", "i",
        "if", "in", "into", "is", "it", "its", "later", "made", "many", "may", "might", "more",
        "most", "much", "must", "near", "neither", "no", "not", "now", "of", "on", "once", "one",
        "only", "or", "other", "our", "out", "over", "she", "should", "since", "so", "some",
        "such", "than", "that", "the", "their", "them", "then", "there", "these", "they", "this",
        "those", "through", "to", "two", "under", "until", "up", "was", "we", "were", "what",
        "when", "where", "which", "while", "who", "why", "will", "with", "within", "would", "you",
    }
)

# Register the source never licenses. Significance, legacy and destiny are claims; the rest are the
# stock cadences that make generated prose recognisable on sight.
_DENIED_PHRASES: tuple[str, ...] = (
    "a testament to",
    "stands as a testament",
    "rich tapestry",
    "rich history",
    "storied history",
    "nestled",
    "steeped in",
    "played a pivotal role",
    "played a crucial role",
    "played a key role",
    "left an indelible",
    "indelible mark",
    "would go on to",
    "went on to become",
    "not only",
    "it is important to note",
    "it is worth noting",
    "serves as a reminder",
    "stands today as",
    "to this day",
    "throughout history",
    "in the annals of",
    "cemented its place",
    "marked a turning point",
    "paved the way",
    "at the crossroads of",
    "melting pot",
    "bears witness",
    "echoes of",
    "shrouded in mystery",
    "lasting legacy",
    "enduring legacy",
    "vibrant",
    "bustling",
    "iconic",
    "renowned for its",
    "delve into",
    "tapestry of",
    "hub of",
    "beacon of",
)

# Present-day administrative statistics. The prompt orders these dropped rather than compressed,
# because a visitor standing on a map at a chosen year did not ask what tier of local government
# administers the site today.
_DENIED_ADMINISTRATIVE: tuple[str, ...] = (
    "by population",
    "sub-prefecture",
    "urban unit",
    "functional area",
    "metropolitan area",
    "electoral district",
    "administrative district",
    "traffic hub",
    "postal code",
    "time zone",
)

# "The Tricasses were the first inhabitants" is history; "62,088 inhabitants" is a census figure.
# The difference is the number beside it, so match the statistic rather than the word.
_POPULATION_STATISTIC = re.compile(
    r"(?:[\d][\d,. ]*\s*(?:inhabitants|residents|people)"
    r"|population of\s*[\d]"
    r"|census)",
    re.IGNORECASE,
)

# A parenthetical unit conversion carries two numbers that mean the same quantity. The set-based
# number check cannot tell a correct pair from a recombined one, because both numbers exist
# somewhere in the source. Requiring the conversion to be dropped removes the whole class.
_UNIT_CONVERSION = re.compile(
    r"\(\s*[\d.,]+\s*(?:mi|km|m|ft|yd|sq\s?mi|km2|mi2|ha|acres?|kilometres?|miles?)\s*\)",
    re.IGNORECASE,
)

# The first sentence must state what the thing was. These openings defer that.
_DENIED_OPENINGS: tuple[str, ...] = (
    "this ",
    "the history of",
    "the story of",
    "located in",
    "situated in",
    "known for",
    "one of the",
)


class RestatementRejected(ValueError):
    """A restatement left its source and must not be published."""

    def __init__(
        self, dossier_id: str, report: dict[str, Any], previous: Any = None
    ) -> None:
        self.dossier_id = dossier_id
        self.report = report
        # What was rejected, so a retry can repair it rather than start again. Carrying it changes
        # nothing about what may be published: the same checks run on whatever comes back.
        self.previous = previous
        # Set by the caller when the report names blocks by identifiers the model never saw.
        self.labels: dict[str, str] = {}
        # Set by the year-dossier caller so a repair can rebuild against the same generation.
        self.prompt_version: str = ""
        self.prompt_sha256: str = ""
        self.model_identifier: str = ""
        self.generated_at: Any = None
        self.provider_response_id: str | None = None
        detail = "; ".join(
            f"{name}={value}" for name, value in sorted(report.items()) if value
        )
        super().__init__(f"Restatement rejected for {dossier_id}: {detail}")


# Quotation and bracket characters that may precede the first real word of a sentence.
_OPENING_MARKS = "\"'([\u201c\u2018"

LEXICON_PATH = Path(__file__).with_name("common-words.txt")
LEXICON_MINIMUM_DOCUMENTS = 50

_lexicon_cache: frozenset[str] | None = None


def common_words() -> frozenset[str]:
    """Words English writes in lower case, so a capital on one is grammar rather than a name.

    Derived from the dossier corpus by `build-lexicon` and checked in, so validation stays hermetic
    and deterministic rather than depending on whatever corpus happens to be on disk.
    """

    global _lexicon_cache
    if _lexicon_cache is None:
        if not LEXICON_PATH.exists():
            _lexicon_cache = frozenset()
        else:
            _lexicon_cache = frozenset(
                line.strip()
                for line in LEXICON_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            )
    return _lexicon_cache


def build_common_words(
    extracts: Iterable[str],
    *,
    minimum_documents: int = LEXICON_MINIMUM_DOCUMENTS,
) -> list[str]:
    """Collect words that appear in lower case in at least `minimum_documents` sources.

    Only lower-case occurrences count. A proper noun is essentially never written lower case in
    running prose, which is what keeps place and person names out of the result.
    """

    document_frequency: Counter[str] = Counter()
    for extract in extracts:
        document_frequency.update(
            {
                word
                for word in _WORD_PATTERN.findall(extract)
                if word.islower() and len(word) > 2
            }
        )
    return sorted(
        word for word, count in document_frequency.items() if count >= minimum_documents
    )


def _sentence_initial_offsets(text: str) -> set[int]:
    """Offsets where a capital is required by grammar rather than chosen to mark a name."""

    offsets: set[int] = set()
    expecting = True
    for position, character in enumerate(text):
        if expecting and not character.isspace() and character not in _OPENING_MARKS:
            offsets.add(position)
            expecting = False
        if character in ".!?\n":
            expecting = True
    return offsets


def normalise_for_checking(text: str) -> str:
    """Remove invisible characters that would silently split a word before it is checked.

    A soft hyphen or zero-width space inside "England" is not visible to a reader but is a
    non-word character to the tokeniser, which then sees "Engla" and reports an invented name.
    Models emit these occasionally, and rejecting sound prose over one would be a false positive
    that no amount of prompting could fix.
    """

    stripped = "".join(
        character
        for character in unicodedata.normalize("NFC", text)
        if unicodedata.category(character) != "Cf"
    )
    return stripped


def _fold_diacritics(word: str) -> str:
    """Strip accents for comparison only.

    Sources spell the same name both ways — "Hjortensjon" in one article and "Hjortensjön" in
    another — and two genuinely different historical names essentially never differ by an accent
    alone, so folding them cannot admit an invented name.
    """

    return "".join(
        character
        for character in unicodedata.normalize("NFD", word)
        if unicodedata.category(character) != "Mn"
    )


def _source_vocabulary(source_text: str) -> frozenset[str]:
    words = _WORD_PATTERN.findall(source_text)
    return frozenset(word.casefold() for word in words) | frozenset(
        _fold_diacritics(word).casefold() for word in words
    )


def _name_is_supported(token: str, vocabulary: frozenset[str]) -> bool:
    folded = token.casefold()
    if folded in _FUNCTION_WORDS or folded in vocabulary:
        return True
    if _fold_diacritics(folded) in vocabulary:
        return True
    for suffix in ("'s", "\u2019s", "es", "s"):
        if folded.endswith(suffix) and folded[: -len(suffix)] in vocabulary:
            return True
    # A source plural restated as a singular, or vice versa, is not a new name.
    if any(candidate == f"{folded}s" or f"{candidate}s" == folded for candidate in vocabulary):
        return True
    # "a Thracian town" for "a town of Thrace" renames nothing: the demonym is built on a stem the
    # source already contains. The rule runs in one direction only, and deliberately.
    #
    # The reverse — writing "Rome" where the source says "Roman" — would need a stem of three
    # characters, and any threshold loose enough to accept Roman -> Rome also accepts
    # Roman -> Romania. There is no clean separation, so the reverse stays rejected. That costs
    # coverage on a real variant, and coverage is the cheap failure here: the reader is shown the
    # source extract instead. Corrupting a name is not cheap.
    for suffix in ("ian", "ean", "ese", "ish", "ic", "an"):
        if not folded.endswith(suffix):
            continue
        stem = folded[: -len(suffix)]
        if len(stem) < 4:
            continue
        if any(
            candidate.startswith(stem) or stem.startswith(candidate)
            for candidate in vocabulary
            if len(candidate) >= 4
        ):
            return True
    return False


def closed_world_report(
    content: DossierRestatementContent,
    source_text: str,
) -> dict[str, Any]:
    """Report every way the restatement stepped outside its source. Empty means it stayed inside."""

    generated_parts = [content.headline or "", content.text or ""]
    generated_parts.extend(entry.year_text for entry in content.timeline)
    generated_parts.extend(entry.text for entry in content.timeline)
    generated = normalise_for_checking("\n".join(part for part in generated_parts if part))
    source_text = normalise_for_checking(source_text)

    source_numbers = set(_NUMBER_PATTERN.findall(source_text))
    unsupported_numbers = sorted(
        {number for number in _NUMBER_PATTERN.findall(generated) if number not in source_numbers}
    )

    vocabulary = _source_vocabulary(source_text)
    # A capital only signals a name when the writer chose it. At the start of a sentence grammar
    # forces one, so "Construction began in 1892" is not a claim about somebody called
    # Construction. Sentence-initial words are exempt only when the corpus shows English writes
    # them in lower case; a name that never appears lower case is still checked in every position.
    lexicon = common_words()
    sentence_starts = _sentence_initial_offsets(generated)
    unsupported_names = sorted(
        {
            match.group()
            for match in _WORD_PATTERN.finditer(generated)
            if match.group()[:1].isupper()
            and not (
                match.start() in sentence_starts and match.group().casefold() in lexicon
            )
            and not _name_is_supported(match.group(), vocabulary)
        }
    )

    lowered = generated.casefold()
    source_lowered = source_text.casefold()
    # The deny list is closed-world like everything else here. Wikipedia writes "played a pivotal
    # role" and "at the hub of" in its own voice; carrying such a phrase across is restatement, not
    # invention, and rejecting it would punish the model for being faithful. Only register the
    # model introduced counts.
    denied = sorted(
        {
            phrase
            for phrase in _DENIED_PHRASES
            if phrase in lowered and phrase not in source_lowered
        }
    )
    denied += sorted(
        {
            f"unit-conversion:{match.group().strip()}"
            for match in _UNIT_CONVERSION.finditer(generated)
        }
    )

    body = (content.text or "").lstrip()
    opening = body.casefold()
    denied_openings = sorted(
        {f"opening:{prefix.strip()}" for prefix in _DENIED_OPENINGS if opening.startswith(prefix)}
    )

    # Kept separate from the faithfulness findings above. Retaining a present-day population count
    # is a true statement that fails the editorial brief; it is not an unsupported claim.
    retained_furniture = sorted(
        {phrase for phrase in _DENIED_ADMINISTRATIVE if phrase in lowered}
        | {
            f"statistic:{match.group().strip()}"
            for match in _POPULATION_STATISTIC.finditer(generated)
        }
    )

    return {
        "unsupported_numbers": unsupported_numbers,
        "unsupported_names": unsupported_names,
        "denied_phrases": denied + denied_openings,
        "retained_furniture": retained_furniture,
    }


def source_bound_text_report(text: str, source_text: str) -> dict[str, Any]:
    """Apply the factual subset checks to a short single-source explanation."""

    generated = normalise_for_checking(text)
    source_text = normalise_for_checking(source_text)
    source_numbers = set(_NUMBER_PATTERN.findall(source_text))
    unsupported_numbers = sorted(
        {number for number in _NUMBER_PATTERN.findall(generated) if number not in source_numbers}
    )
    vocabulary = _source_vocabulary(source_text)
    lexicon = common_words()
    sentence_starts = _sentence_initial_offsets(generated)
    unsupported_names = sorted(
        {
            match.group()
            for match in _WORD_PATTERN.finditer(generated)
            if match.group()[:1].isupper()
            and not (
                match.start() in sentence_starts and match.group().casefold() in lexicon
            )
            and not _name_is_supported(match.group(), vocabulary)
        }
    )
    return {
        "unsupported_numbers": unsupported_numbers,
        "unsupported_names": unsupported_names,
        "longer_than_source": len(generated) > len(source_text),
    }


def _restatement_id(
    content: DossierRestatementContent,
    provenance: RestatementProvenance,
) -> str:
    digest = canonical_sha256(
        {
            "content": content.model_dump(mode="json"),
            "generation": provenance.model_dump(mode="json"),
        }
    )
    return f"restatement:{digest[:16]}"


def build_restatement(
    content: DossierRestatementContent,
    dossier: HistoricalDossier,
    *,
    prompt_version: str,
    prompt_sha256: str,
    model_identifier: str,
    generated_at: datetime,
    provider_response_id: str | None = None,
) -> DossierRestatement:
    """Validate one model output against its source and bind it to that exact revision."""

    if content.result != RestatementResult.RESTATED:
        raise RestatementRejected(
            dossier.dossier_id, {"unsuitable": content.unsuitable_reason or "unsuitable"}
        )

    source_text = dossier.extract
    source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if source_sha256 != dossier.content_checksum_sha256:
        raise RestatementRejected(
            dossier.dossier_id, {"source_checksum": "source extract does not match its checksum"}
        )

    report = closed_world_report(content, source_text)
    text = (content.text or "").strip()
    if len(text) > len(source_text):
        report["length"] = [f"{len(text)} > {len(source_text)}"]
    # Only faithfulness blocks publication. `retained_furniture` records an editorial miss on a
    # restatement that is still true, and dropping a true restatement over house style would cost
    # coverage for no gain in correctness.
    retained_furniture = report.get("retained_furniture", [])
    blocking = {name: value for name, value in report.items() if name != "retained_furniture"}
    if any(blocking.values()):
        raise RestatementRejected(dossier.dossier_id, blocking)

    provenance = RestatementProvenance(
        prompt_version=prompt_version,
        prompt_sha256=prompt_sha256,
        model_identifier=model_identifier,
        source_sha256=source_sha256,
        output_sha256=canonical_sha256(content),
        generated_at=generated_at,
        provider_response_id=provider_response_id,
    )
    return DossierRestatement(
        restatement_id=_restatement_id(content, provenance),
        dossier_id=dossier.dossier_id,
        language=dossier.language,
        headline=(content.headline or "").strip(),
        text=text,
        timeline=content.timeline,
        entity_ids=list(dossier.entity_ids),
        source_revision_id=dossier.revision_id,
        source_content_checksum_sha256=source_sha256,
        content_checksum_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        generation=provenance,
        validation=RestatementValidation(
            policy_version=POLICY_VERSION,
            source_chars=len(source_text),
            restatement_chars=len(text),
            retained_furniture=list(retained_furniture),
        ),
    )


def validate_restatement(restatement: DossierRestatement, dossier: HistoricalDossier) -> None:
    """Re-run every check against the current source. Used by the release verifier."""

    if restatement.dossier_id != dossier.dossier_id:
        raise ValueError("Restatement is not bound to this dossier")
    source_sha256 = hashlib.sha256(dossier.extract.encode("utf-8")).hexdigest()
    if restatement.source_content_checksum_sha256 != source_sha256:
        raise ValueError(
            f"Restatement is stale: {restatement.dossier_id} changed since it was generated"
        )
    if restatement.source_revision_id != dossier.revision_id:
        raise ValueError(f"Restatement revision does not match its source: {dossier.dossier_id}")
    content = DossierRestatementContent(
        result=RestatementResult.RESTATED,
        headline=restatement.headline,
        text=restatement.text,
        timeline=list(restatement.timeline),
        unsuitable_reason=None,
    )
    report = closed_world_report(content, dossier.extract)
    blocking = {name: value for name, value in report.items() if name != "retained_furniture"}
    if any(blocking.values()):
        raise RestatementRejected(restatement.dossier_id, blocking)


def _openai_output_schema() -> dict[str, Any]:
    """Project the local contract onto the provider's supported JSON Schema subset."""

    schema = DossierRestatementContent.model_json_schema()

    def remove_unsupported(value: Any) -> None:
        if isinstance(value, dict):
            for keyword in ("minLength", "maxLength", "minimum", "maximum"):
                value.pop(keyword, None)
            for nested in value.values():
                remove_unsupported(nested)
        elif isinstance(value, list):
            for nested in value:
                remove_unsupported(nested)

    remove_unsupported(schema)
    return schema


def source_input(dossier: HistoricalDossier) -> str:
    """The complete and only allowed input for one restatement."""

    return canonical_json_bytes(
        {
            "title": dossier.title,
            "language": dossier.language,
            "source": dossier.source_ref.citation,
            "extract": dossier.extract,
        }
    ).decode("utf-8")


@dataclass(frozen=True)
class ProviderProfile:
    """One approved generation endpoint and what it can actually enforce.

    `enforces_schema` is a statement about the provider, not a preference. When it is false the
    request can only ask for well-formed JSON, so the contract is restated inside the prompt and
    the returned payload is validated locally before it is trusted. Either way nothing reaches a
    release without passing the same Pydantic contract and the same closed-world check.
    """

    name: str
    url: str
    api_style: Literal["responses", "chat_completions"]
    api_key_env: str
    enforces_schema: bool
    max_output_tokens: int = 4096
    extra_body: tuple[tuple[str, Any], ...] = ()


PROVIDERS: dict[str, ProviderProfile] = {
    "openai": ProviderProfile(
        name="openai",
        url="https://api.openai.com/v1/responses",
        api_style="responses",
        api_key_env="OPENAI_API_KEY",
        enforces_schema=True,
    ),
    # DeepSeek exposes no Responses API and rejects `response_format: json_schema`, so it gets
    # JSON mode plus an in-prompt contract. Thinking is off: restating one extract is a mechanical
    # transformation, and reasoning tokens are billed against the same output budget for no gain.
    "deepseek": ProviderProfile(
        name="deepseek",
        url="https://api.deepseek.com/chat/completions",
        api_style="chat_completions",
        api_key_env="DEEPSEEK_API_KEY",
        enforces_schema=False,
        max_output_tokens=32768,
        extra_body=(("thinking", {"type": "disabled"}),),
    ),
}


def provider_profile(name: str) -> ProviderProfile:
    profile = PROVIDERS.get(name)
    if profile is None:
        raise ValueError(f"Unknown provider {name!r}. Known: {', '.join(sorted(PROVIDERS))}")
    return profile


def schema_instruction() -> str:
    """The output contract, for providers that cannot enforce a schema themselves."""

    return (
        "\n\nReturn one JSON object and nothing else. No prose, no code fence, no commentary.\n"
        "It must validate against this JSON Schema exactly, including every required key:\n"
        + json.dumps(_openai_output_schema(), indent=2)
        + "\n\nWhen the result is `restated`, set `unsuitable_reason` to null. When it is "
        "`unsuitable`, set `headline` and `text` to null and `timeline` to []."
    )


def _responses_request(
    dossier: HistoricalDossier, prompt: str, model_identifier: str
) -> dict[str, Any]:
    return {
        "model": model_identifier,
        "store": False,
        "instructions": prompt,
        "input": "Source extract (the complete and only allowed input):\n" + source_input(dossier),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "palimpsest_dossier_restatement",
                "strict": True,
                "schema": _openai_output_schema(),
            }
        },
    }


def _chat_completions_request(
    dossier: HistoricalDossier,
    prompt: str,
    model_identifier: str,
    profile: ProviderProfile,
) -> dict[str, Any]:
    return {
        "model": model_identifier,
        "stream": False,
        "max_tokens": profile.max_output_tokens,
        "response_format": {"type": "json_object"},
        **dict(profile.extra_body),
        "messages": [
            {"role": "system", "content": prompt + schema_instruction()},
            {
                "role": "user",
                "content": (
                    "Source extract (the complete and only allowed input):\n"
                    + source_input(dossier)
                ),
            },
        ],
    }


def _responses_output(payload: dict[str, Any]) -> str:
    if payload.get("status") != "completed":
        raise ValueError(f"Provider response did not complete: {payload.get('status')}")
    output_texts = [
        part.get("text")
        for item in payload.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text" and isinstance(part.get("text"), str)
    ]
    if len(output_texts) != 1:
        raise ValueError("Provider response must contain exactly one structured output")
    return str(output_texts[0])


def _chat_completions_output(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("Provider response must contain exactly one choice")
    choice = choices[0]
    reason = choice.get("finish_reason")
    if reason not in (None, "stop"):
        # A reasoning model that ran out of budget returns truncated JSON. Say so plainly rather
        # than letting a JSON decode error stand in for an exhausted token ceiling.
        raise ValueError(f"Provider stopped before finishing the output: {reason}")
    content = (choice.get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Provider response contained no output text")
    return content


def _strip_code_fence(text: str) -> str:
    """JSON mode is not a guarantee. Recover a fenced object rather than discarding the work."""

    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped.split("\n", 1)[1] if "\n" in stripped else ""
    return body.rsplit("```", 1)[0].strip()


def generate_restatement(
    dossier: HistoricalDossier,
    *,
    prompt: str,
    prompt_version: str,
    model_identifier: str,
    api_key: str,
    provider: str = "openai",
    generated_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> DossierRestatement:
    """Generate one restatement through an approved provider and validate what comes back."""

    if not api_key:
        raise ValueError("An API key is required for restatement generation")
    profile = provider_profile(provider)
    if profile.api_style == "responses":
        request = _responses_request(dossier, prompt, model_identifier)
    else:
        request = _chat_completions_request(dossier, prompt, model_identifier, profile)

    owns_client = client is None
    active_client = client or httpx.Client(timeout=180)
    try:
        response = active_client.post(
            profile.url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request,
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            active_client.close()

    if profile.api_style == "responses":
        output_text = _responses_output(payload)
    else:
        output_text = _strip_code_fence(_chat_completions_output(payload))
    try:
        output = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise ValueError("Provider structured output is not valid JSON") from error
    actual_model = payload.get("model")
    if not isinstance(actual_model, str) or not actual_model:
        raise ValueError("Provider response omitted its model identifier")
    response_id = payload.get("id")
    if response_id is not None and not isinstance(response_id, str):
        raise ValueError("Provider response ID is malformed")
    return build_restatement(
        DossierRestatementContent.model_validate(output),
        dossier,
        prompt_version=prompt_version,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        model_identifier=actual_model,
        generated_at=generated_at or datetime.now(UTC),
        provider_response_id=response_id,
    )


def generate_with_openai(
    dossier: HistoricalDossier,
    *,
    prompt: str,
    prompt_version: str,
    model_identifier: str,
    api_key: str,
    generated_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> DossierRestatement:
    return generate_restatement(
        dossier,
        prompt=prompt,
        prompt_version=prompt_version,
        model_identifier=model_identifier,
        api_key=api_key,
        provider="openai",
        generated_at=generated_at,
        client=client,
    )


def read_dossiers(path: Path) -> Iterator[HistoricalDossier]:
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                yield HistoricalDossier.model_validate_json(line)


def read_restatements(path: Path) -> Iterator[DossierRestatement]:
    if not path.exists():
        return
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                yield DossierRestatement.model_validate_json(line)


def append_restatement(path: Path, restatement: DossierRestatement) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(restatement) + b"\n")


def completed_source_checksums(path: Path) -> dict[str, str]:
    """Map dossier ID to the source checksum it was restated from, for resumable runs."""

    return {
        restatement.dossier_id: restatement.source_content_checksum_sha256
        for restatement in read_restatements(path)
    }


def pending_dossiers(
    dossiers: Iterable[HistoricalDossier],
    completed: dict[str, str],
    *,
    minimum_chars: int = 200,
) -> list[HistoricalDossier]:
    """Dossiers still needing a restatement, including those whose source revision moved on."""

    pending: list[HistoricalDossier] = []
    for dossier in dossiers:
        if len(dossier.extract) < minimum_chars:
            continue
        checksum = hashlib.sha256(dossier.extract.encode("utf-8")).hexdigest()
        if completed.get(dossier.dossier_id) != checksum:
            pending.append(dossier)
    return pending


def _feature_entity_ids(feature: dict[str, Any]) -> list[str]:
    """The same entity join the release build uses, so a year selection matches the map."""

    entity_ids = feature.get("entity_ids") or []
    if entity_ids:
        return [str(entity_id) for entity_id in entity_ids]
    wikidata_ids = feature.get("wikidata_ids") or []
    if wikidata_ids:
        return [f"wikidata:{qid}" for qid in wikidata_ids]
    return [f"feature:{feature['feature_id']}"]


def dossiers_active_in_year(
    dossiers: Iterable[HistoricalDossier],
    features: Iterable[dict[str, Any]],
    year: int,
) -> list[HistoricalDossier]:
    """Dossiers joined to a reviewed feature whose validity interval covers `year`.

    This is the reading set for one year of the map: what a visitor could actually open with the
    slider at that year, rather than everything the corpus happens to contain.
    """

    by_entity: dict[str, list[HistoricalDossier]] = {}
    for dossier in dossiers:
        for entity_id in dossier.entity_ids:
            by_entity.setdefault(entity_id, []).append(dossier)

    selected: dict[str, HistoricalDossier] = {}
    for feature in features:
        if not (int(feature["valid_from"]) <= year <= int(feature["valid_to"])):
            continue
        for entity_id in _feature_entity_ids(feature):
            for dossier in by_entity.get(entity_id, []):
                selected[dossier.dossier_id] = dossier
    return sorted(selected.values(), key=lambda dossier: dossier.dossier_id)


def read_features(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                yield orjson.loads(line)


def load_model_output(path: Path) -> DossierRestatementContent:
    return DossierRestatementContent.model_validate(orjson.loads(path.read_bytes()))
