"""Thin wrapper around the Anthropic SDK: structured batch requests + polling.

Every LLM call in this pipeline goes through the Message Batches API (50% discount,
hours-scale latency is fine for a validation run). Each request constrains the output
with ``output_config.format`` (JSON schema derived from a Pydantic model with
``extra="forbid"``), so results parse deterministically.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Iterator, Type, TypeVar

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def structured_request(
    custom_id: str,
    *,
    model: str,
    system: str | list[dict[str, Any]],
    user_content: str,
    schema_model: Type[BaseModel],
    max_tokens: int,
) -> Request:
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
        "thinking": {"type": "adaptive"},
        "output_config": {
            "format": {"type": "json_schema", "schema": schema_model.model_json_schema()}
        },
    }
    return Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(**params))


def submit_batch(requests: list[Request]) -> str:
    batch = get_client().messages.batches.create(requests=requests)
    return batch.id


def wait_for_batch(
    batch_id: str,
    poll_seconds: int = 30,
    on_poll: Callable[[Any], None] | None = None,
) -> None:
    client = get_client()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if on_poll is not None:
            on_poll(batch)
        if batch.processing_status == "ended":
            return
        time.sleep(poll_seconds)


def iter_structured_results(
    batch_id: str, schema_model: Type[T]
) -> Iterator[tuple[str, T | None, str | None]]:
    """Yield ``(custom_id, parsed_or_None, error_or_None)`` for each batch result."""
    client = get_client()
    for result in client.messages.batches.results(batch_id):
        cid = result.custom_id
        if result.result.type != "succeeded":
            yield cid, None, f"batch result: {result.result.type}"
            continue
        msg = result.result.message
        if msg.stop_reason == "refusal":
            yield cid, None, "model refused"
            continue
        text = next((b.text for b in msg.content if b.type == "text"), None)
        if text is None:
            yield cid, None, "no text block in response"
            continue
        try:
            yield cid, schema_model.model_validate(json.loads(text)), None
        except Exception as exc:  # schema drift / truncated output
            yield cid, None, f"parse error: {exc}"


def run_structured_batch(
    requests: list[Request],
    schema_model: Type[T],
    poll_seconds: int = 30,
    on_poll: Callable[[Any], None] | None = None,
    on_submit: Callable[[str], None] | None = None,
    batch_id: str | None = None,
) -> dict[str, tuple[T | None, str | None]]:
    """Submit (or resume) a batch and block until all results are collected."""
    if batch_id is None:
        batch_id = submit_batch(requests)
    if on_submit is not None:
        on_submit(batch_id)
    wait_for_batch(batch_id, poll_seconds=poll_seconds, on_poll=on_poll)
    return {cid: (parsed, err) for cid, parsed, err in iter_structured_results(batch_id, schema_model)}
