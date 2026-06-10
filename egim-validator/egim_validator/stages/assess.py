"""Stage 3 — core assessment: judge coverage of each applicable requirement.

The full model documentation sits in a cached system prefix (1-hour TTL); every batch
request shares that prefix and differs only in the per-requirement user message, so the
documentation tokens are paid for roughly once, not once per requirement.
"""

from __future__ import annotations

from typing import Any

from .. import llm
from ..config import Config
from ..ingest import render_model_doc
from ..schemas import AssessmentLLM, ModelDoc, ModelProfile, Requirement

INSTRUCTIONS = """\
You are assisting a bank model validator. The full model documentation under validation
is provided below inside <model_documentation>. For each request you receive ONE
paragraph of the ECB guide to internal models (EGIM) together with its atomic
obligations. Judge how well the documentation evidences compliance with that paragraph.

Status definitions:
- covered: every obligation is clearly and substantively evidenced in the documentation.
- partially_covered: some obligations are evidenced, or the treatment is superficial.
- gap: the documentation does not address the obligations.
- not_applicable: the paragraph genuinely cannot apply to this model (explain why).
- unclear: the documentation is ambiguous or contradictory; a human must judge.

Evidence rules (strict):
- Every quote MUST be copied verbatim, character for character, from the documentation.
- Every quote MUST carry the id of the <section> it appears in.
- Never paraphrase inside a quote. Quotes are programmatically verified against the
  source; an unverifiable quote invalidates the assessment.
- Prefer 1-4 short, decisive quotes over many long ones.

Judgement rules:
- Be conservative. The cost of wrongly reporting "covered" is much higher than the cost
  of wrongly reporting "partially_covered" or "gap". If unsure, do not choose "covered".
- Mentioning a topic is not evidencing it: the documentation must show WHAT was done and
  HOW, not merely that something exists.
- rationale: map each obligation to the evidence (or its absence), briefly.
- open_questions: concrete questions the validator should put to the model owner.
"""


def build_system(doc: ModelDoc) -> list[dict[str, Any]]:
    # Stable content first; the cache breakpoint sits on the last (documentation) block,
    # caching instructions + documentation together for every request in the batch.
    return [
        {"type": "text", "text": INSTRUCTIONS},
        {
            "type": "text",
            "text": render_model_doc(doc),
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
    ]


def _user_content(req: Requirement, profile: ModelProfile) -> str:
    obligations = "\n".join(f"- {o}" for o in req.extraction.obligations) or "- (assess the paragraph as a whole)"
    return (
        f"Engagement: '{profile.model_name}' ({profile.model_type.value}); "
        f"portfolio: {profile.portfolio or 'n/a'}.\n\n"
        f"EGIM paragraph [{req.ref}] — {req.paragraph.label}:\n"
        f"{req.paragraph.text}\n\n"
        f"Obligations to check:\n{obligations}\n\n"
        f"Assess coverage of this paragraph in the model documentation."
    )


def assess(
    requirements: list[Requirement],
    doc: ModelDoc,
    profile: ModelProfile,
    config: Config,
    on_progress=None,
    on_submit=None,
    batch_id: str | None = None,
) -> dict[str, tuple[AssessmentLLM | None, str | None]]:
    system = build_system(doc)
    requests = [
        llm.structured_request(
            req.ref,
            model=config.assess_model,
            system=system,
            user_content=_user_content(req, profile),
            schema_model=AssessmentLLM,
            max_tokens=config.assess_max_tokens,
        )
        for req in requirements
    ]
    return llm.run_structured_batch(
        requests,
        AssessmentLLM,
        poll_seconds=config.batch_poll_seconds,
        on_poll=on_progress,
        on_submit=on_submit,
        batch_id=batch_id,
    )
