"""Stage 5 (optional) — adversarial review of 'covered' verdicts.

Asymmetric risk: a false "covered" hides a real gap from the validator, while a false
"gap" merely costs a second look. So a skeptical second pass tries to refute every
"covered" verdict; verdicts that don't survive are flagged for human review.
"""

from __future__ import annotations

from .. import llm
from ..config import Config
from ..ingest import render_model_doc
from ..schemas import AssessmentRecord, CoverageStatus, ModelDoc, ReviewLLM

SYSTEM_TEMPLATE = """\
You are a skeptical senior model validator reviewing a junior colleague's conclusion
that a regulatory requirement is fully covered by the model documentation below.
Your job is to try to REFUTE the conclusion: look for obligations that are only
mentioned but not substantiated, evidence quoted out of context, or missing aspects.
Set upheld=false only when you find a concrete, defensible objection; state it in
'challenge'. If the conclusion genuinely holds, set upheld=true and say why briefly.
"""


def adversarial_review(
    records: list[AssessmentRecord],
    doc: ModelDoc,
    config: Config,
    on_progress=None,
) -> list[AssessmentRecord]:
    targets = [r for r in records if r.status == CoverageStatus.covered and r.review_upheld is None]
    if not targets:
        return records

    system = [
        {"type": "text", "text": SYSTEM_TEMPLATE},
        {
            "type": "text",
            "text": render_model_doc(doc),
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
    ]
    requests = []
    for r in targets:
        evidence = "\n".join(f'- [{e.section_id}] "{e.quote}"' for e in r.evidence) or "- (none)"
        requests.append(
            llm.structured_request(
                r.ref,
                model=config.review_model,
                system=system,
                user_content=(
                    f"Requirement [{r.ref}] ({r.chapter or ''} {r.section or ''}):\n{r.paragraph_text}\n\n"
                    f"Junior validator's verdict: covered\nRationale: {r.rationale}\n"
                    f"Evidence cited:\n{evidence}\n\nTry to refute this verdict."
                ),
                schema_model=ReviewLLM,
                max_tokens=config.review_max_tokens,
            )
        )

    results = llm.run_structured_batch(
        requests, ReviewLLM, poll_seconds=config.batch_poll_seconds, on_poll=on_progress
    )
    by_ref = {r.ref: r for r in records}
    for ref, (parsed, err) in results.items():
        record = by_ref[ref]
        if parsed is None:
            record.flags.append(f"adversarial review failed: {err}")
            continue
        record.review_upheld = parsed.upheld
        record.review_challenge = parsed.challenge
        if not parsed.upheld:
            record.needs_review = True
            record.flags.append("'covered' verdict challenged by adversarial review")
    return records
