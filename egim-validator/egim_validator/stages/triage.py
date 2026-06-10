"""Stage 2 — applicability triage: which checklist rows apply to this engagement.

Cheap and mostly deterministic: chapter-level rules first (EGIM chapters map cleanly to
model types), then the paragraph-level ``model_types`` extracted in stage 1, and only
for rows neither resolves, an optional Haiku batch.
"""

from __future__ import annotations

from .. import llm
from ..config import Config
from ..schemas import (
    Applicability,
    ModelProfile,
    ModelType,
    Requirement,
    RequirementKind,
    TriageLLM,
)

TRIAGE_SYSTEM = """\
You decide whether one paragraph of the ECB guide to internal models applies to a
specific model validation engagement. Answer applicable=true unless the paragraph
clearly targets a different model type or situation than the engagement described.
When in doubt, answer applicable=true (a validator will review).
"""


def _rule_applicability(req: Requirement, profile: ModelProfile, config: Config) -> Applicability | None:
    if req.extraction.kind == RequirementKind.background:
        return Applicability(applicable=False, reason="Background paragraph — nothing to evidence.", method="rule")

    chapter = (req.paragraph.chapter or "").lower()
    for rule in config.chapter_rules:
        if rule.match in chapter:
            applicable = profile.model_type in rule.model_types or ModelType.general in rule.model_types
            scope = ", ".join(t.value for t in rule.model_types)
            return Applicability(
                applicable=applicable,
                reason=f"Chapter rule '{rule.match}' → scope [{scope}]; engagement is {profile.model_type.value}.",
                method="rule",
            )

    extracted = req.extraction.model_types
    if extracted:
        applicable = profile.model_type in extracted or ModelType.general in extracted
        scope = ", ".join(t.value for t in extracted)
        return Applicability(
            applicable=applicable,
            reason=f"Paragraph-level scope [{scope}]; engagement is {profile.model_type.value}.",
            method="rule",
        )
    return None


def triage(
    requirements: list[Requirement],
    profile: ModelProfile,
    config: Config,
    on_progress=None,
) -> dict[str, Applicability]:
    out: dict[str, Applicability] = {}
    unresolved: list[Requirement] = []

    for req in requirements:
        result = _rule_applicability(req, profile, config)
        if result is not None:
            out[req.ref] = result
        else:
            unresolved.append(req)

    if unresolved and config.llm_triage_fallback:
        engagement = (
            f"Engagement: validation of '{profile.model_name}', model type "
            f"{profile.model_type.value}, portfolio: {profile.portfolio or 'n/a'}. {profile.notes}"
        )
        requests = [
            llm.structured_request(
                req.ref,
                model=config.triage_model,
                system=TRIAGE_SYSTEM,
                user_content=(
                    f"{engagement}\n\nGuide paragraph ({req.paragraph.label}):\n{req.paragraph.text}"
                ),
                schema_model=TriageLLM,
                max_tokens=config.triage_max_tokens,
            )
            for req in unresolved
        ]
        results = llm.run_structured_batch(
            requests, TriageLLM, poll_seconds=config.batch_poll_seconds, on_poll=on_progress
        )
        for req in unresolved:
            parsed, err = results.get(req.ref, (None, "missing"))
            if parsed is None:
                out[req.ref] = Applicability(
                    applicable=True, reason=f"LLM triage failed ({err}); defaulted to applicable.", method="llm"
                )
            else:
                out[req.ref] = Applicability(applicable=parsed.applicable, reason=parsed.reason, method="llm")
    else:
        for req in unresolved:
            out[req.ref] = Applicability(
                applicable=True, reason="No rule matched; defaulted to applicable for review.", method="rule"
            )
    return out
