from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import orjson

from history_pipeline.models import AssertionRestatement, EvidenceAssertion
from history_pipeline.restatement import provider_profile, source_bound_text_report


class AssertionRestatementRejected(ValueError):
    pass


def read_evidence_assertions(path: Path) -> Iterator[EvidenceAssertion]:
    if not path.exists():
        return
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                yield EvidenceAssertion.model_validate_json(line)


def read_assertion_restatements(path: Path) -> Iterator[AssertionRestatement]:
    if not path.exists():
        return
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                yield AssertionRestatement.model_validate_json(line)


def append_assertion_restatement(path: Path, value: AssertionRestatement) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(orjson.dumps(value.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS))
        handle.write(b"\n")


def completed_assertion_checksums(path: Path) -> set[tuple[str, str]]:
    return {
        (item.assertion_id, item.source_excerpt_checksum_sha256)
        for item in read_assertion_restatements(path)
    }


def generate_assertion_restatement(
    assertion: EvidenceAssertion,
    *,
    prompt: str,
    prompt_version: str,
    model_identifier: str,
    api_key: str,
    provider: str = "deepseek",
    generated_at: datetime | None = None,
    client: httpx.Client | None = None,
) -> AssertionRestatement:
    if not assertion.source_excerpt or not assertion.source_excerpt_checksum_sha256:
        raise ValueError(f"{assertion.assertion_id} has no source explanation to restate")
    if not api_key:
        raise ValueError("An API key is required for assertion restatement")
    profile = provider_profile(provider)
    if profile.api_style != "chat_completions":
        raise ValueError("Assertion restatement currently supports chat-completions providers")
    request = {
        "model": model_identifier,
        "stream": False,
        "max_tokens": min(profile.max_output_tokens, 512),
        "response_format": {"type": "json_object"},
        **dict(profile.extra_body),
        "messages": [
            {
                "role": "system",
                "content": (
                    prompt
                    + "\n\nReturn one JSON object and nothing else, with exactly this shape: "
                    '{"text":"one or two short plain-English sentences"}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Variable: {assertion.predicate}\n"
                    "Source explanation (the complete and only allowed factual input):\n"
                    f"{assertion.source_excerpt}"
                ),
            },
        ],
    }
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
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("Provider response must contain exactly one choice")
    choice = choices[0]
    if choice.get("finish_reason") not in (None, "stop"):
        raise ValueError("Provider stopped before completing the assertion restatement")
    content = (choice.get("message") or {}).get("content")
    if not isinstance(content, str):
        raise ValueError("Provider response contained no text")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ValueError("Provider assertion restatement is not valid JSON") from error
    if set(result) != {"text"} or not isinstance(result["text"], str):
        raise ValueError("Provider assertion restatement has the wrong shape")
    text = result["text"].strip()
    report = source_bound_text_report(text, assertion.source_excerpt)
    if any(report.values()):
        raise AssertionRestatementRejected(
            f"{assertion.assertion_id} left its source: {report}"
        )
    actual_model = payload.get("model")
    if not isinstance(actual_model, str) or not actual_model:
        raise ValueError("Provider response omitted its model identifier")
    response_id = payload.get("id")
    if response_id is not None and not isinstance(response_id, str):
        raise ValueError("Provider response ID is malformed")
    return AssertionRestatement(
        assertion_id=assertion.assertion_id,
        text=text,
        source_excerpt_checksum_sha256=assertion.source_excerpt_checksum_sha256,
        prompt_version=prompt_version,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        provider=provider,
        model_identifier=actual_model,
        generated_at=generated_at or datetime.now(UTC),
        provider_response_id=response_id,
    )
