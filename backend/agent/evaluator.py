from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass

import anthropic

from backend.agent.bm25_index import BM25Index
from backend.agent.document_loader import Chunk
from backend.agent.ecb_corpus import EcbChapter

SYSTEM_PROMPT = """You are an expert regulatory compliance analyst specializing in ECB \
banking supervision requirements for internal models (credit risk IRB, market risk, \
counterparty credit risk). You evaluate whether a bank's model documentation demonstrates \
compliance with ECB supervisory requirements.

Verdict definitions:
- compliant: the bank document clearly and specifically addresses all material aspects of the requirement
- partial: the bank document addresses some aspects but has identifiable gaps or is insufficiently specific
- missing: no meaningful evidence in the bank document that this requirement is addressed
- not_applicable: this ECB requirement does not apply to the scope of the bank document

Rules:
- Be specific about gaps; quote exact bank document text as evidence
- Cite ECB paragraph numbers when referencing specific requirements
- Respond ONLY with valid JSON, no markdown fences"""

_EVAL_TEMPLATE = """\
=== ECB REGULATORY REQUIREMENTS ===
Chapter: {chapter_name}
ECB Supervisory Guide for Internal Models, July 2025
Paragraph IDs: {para_ids}

{ecb_text}

=== BANK MODEL DOCUMENTATION (Top {top_k} Relevant Excerpts) ===
{bank_excerpts}

=== EVALUATION TASK ===
Does the bank documentation above satisfy the ECB requirements above?
Respond with JSON only (no markdown, no code fences):
{{
  "verdict": "compliant" | "partial" | "missing" | "not_applicable",
  "confidence": "high" | "medium" | "low",
  "ecb_requirement_summary": "<1-2 sentence summary of the ECB requirement>",
  "gap_description": "<specific gaps identified, or null if compliant>",
  "matched_excerpts": ["<exact quote from bank doc>"],
  "recommendation": "<remediation action, or null if compliant>"
}}"""

VALID_VERDICTS = frozenset({"compliant", "partial", "missing", "not_applicable"})
VALID_CONFIDENCES = frozenset({"high", "medium", "low"})


@dataclass
class EvaluationResult:
    chapter: str
    display_name: str
    zone: str
    paragraph_ids: list[int]
    verdict: str
    confidence: str
    ecb_requirement_summary: str
    gap_description: str | None
    matched_excerpts: list[str]
    recommendation: str | None
    input_tokens: int = 0
    output_tokens: int = 0


DEFAULT_MODEL = "claude-sonnet-4-6"


class Evaluator:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = 3,
        inter_call_delay: float = 0.5,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"],
            max_retries=0,  # we handle retries ourselves
        )
        self._model = model
        self._max_retries = max_retries
        self._inter_call_delay = inter_call_delay
        self._total_input = 0
        self._total_output = 0

    async def evaluate_chapter(
        self,
        chapter: EcbChapter,
        bank_index: BM25Index,
        bank_chunks: list[Chunk],
        top_k: int = 6,
    ) -> EvaluationResult:
        hits = bank_index.query(chapter.text, top_k=top_k)
        retrieved = [bank_chunks[idx].text for idx, _ in hits]

        bank_excerpts = "\n\n---\n\n".join(
            f"[Excerpt {i+1}]\n{text}" for i, text in enumerate(retrieved)
        ) or "(No relevant excerpts found in bank document)"

        user_prompt = _EVAL_TEMPLATE.format(
            chapter_name=chapter.display_name,
            para_ids=", ".join(str(i) for i in chapter.paragraph_ids),
            ecb_text=chapter.text[:12000],  # guard against very large chapters
            top_k=top_k,
            bank_excerpts=bank_excerpts,
        )

        raw, in_tok, out_tok = await self._call_api(user_prompt)
        self._total_input += in_tok
        self._total_output += out_tok

        parsed = self._parse_verdict(raw)

        return EvaluationResult(
            chapter=chapter.chapter,
            display_name=chapter.display_name,
            zone=chapter.zone,
            paragraph_ids=chapter.paragraph_ids,
            verdict=parsed.get("verdict", "partial"),
            confidence=parsed.get("confidence", "low"),
            ecb_requirement_summary=parsed.get("ecb_requirement_summary", ""),
            gap_description=parsed.get("gap_description"),
            matched_excerpts=parsed.get("matched_excerpts", []),
            recommendation=parsed.get("recommendation"),
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

    async def _call_api(self, user_prompt: str) -> tuple[str, int, int]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                msg = await self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                content = msg.content[0].text
                in_tok = msg.usage.input_tokens
                out_tok = msg.usage.output_tokens
                if self._inter_call_delay > 0:
                    await asyncio.sleep(self._inter_call_delay)
                return content, in_tok, out_tok
            except anthropic.RateLimitError as exc:
                last_exc = exc
                await asyncio.sleep(2 ** attempt)
            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500:
                    last_exc = exc
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise RuntimeError(f"API call failed after {self._max_retries} retries") from last_exc

    def _parse_verdict(self, raw: str) -> dict:
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            # Normalise verdict and confidence
            data["verdict"] = data.get("verdict", "partial").lower()
            data["confidence"] = data.get("confidence", "low").lower()
            if data["verdict"] not in VALID_VERDICTS:
                data["verdict"] = "partial"
            if data["confidence"] not in VALID_CONFIDENCES:
                data["confidence"] = "low"
            return data
        except json.JSONDecodeError:
            pass

        # Fallback: extract verdict field with regex
        m = re.search(r'"verdict"\s*:\s*"(\w+)"', raw)
        verdict = m.group(1).lower() if m else "partial"
        if verdict not in VALID_VERDICTS:
            verdict = "partial"

        return {
            "verdict": verdict,
            "confidence": "low",
            "ecb_requirement_summary": "",
            "gap_description": f"[parse error — raw response truncated: {raw[:200]}]",
            "matched_excerpts": [],
            "recommendation": None,
        }

    @property
    def total_tokens(self) -> tuple[int, int]:
        return self._total_input, self._total_output
