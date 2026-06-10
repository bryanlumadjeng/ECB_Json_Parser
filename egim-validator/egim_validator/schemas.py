"""Data model for the validation pipeline.

Two families of models live here:

* LLM-facing schemas (suffix ``LLM`` or used as ``output_config.format``): these use
  ``extra="forbid"`` so the generated JSON schema carries ``additionalProperties: false``,
  which the structured-outputs API requires.
* Storage records: what the pipeline persists under ``runs/<run_id>/``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- guide side


class ModelType(str, Enum):
    general = "general"
    credit_risk = "credit_risk"
    market_risk = "market_risk"
    counterparty_credit_risk = "counterparty_credit_risk"


class GuideParagraph(BaseModel):
    """One paragraph of the parsed ECB guide (schema of ecb_pdf_to_json.py output)."""

    id: int
    paragraph_number: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    page_start: int = 0
    page_end: int = 0
    text: str

    @property
    def ref(self) -> str:
        return f"EGIM-{self.id:04d}"

    @property
    def label(self) -> str:
        bits = [b for b in (self.chapter, self.section) if b]
        num = f"para {self.paragraph_number}" if self.paragraph_number else f"id {self.id}"
        return " / ".join(bits + [num])


class RequirementKind(str, Enum):
    requirement = "requirement"      # binding obligation ("institutions must/should ...")
    expectation = "expectation"      # supervisory expectation, softer phrasing
    background = "background"        # scope, definitions, narrative — nothing to evidence


class RequirementExtraction(BaseModel):
    """LLM output schema for guide preprocessing (stage 1)."""

    model_config = ConfigDict(extra="forbid")

    kind: RequirementKind
    summary: str = Field(description="One-sentence summary of what the paragraph demands.")
    obligations: list[str] = Field(
        description="Atomic, independently checkable obligations contained in the paragraph. "
        "Empty for background paragraphs."
    )
    topics: list[str] = Field(description="Short topic tags, e.g. 'data quality', 'PD estimation'.")
    model_types: list[ModelType] = Field(
        description="Risk model types this paragraph applies to. Use 'general' when it applies "
        "to all internal models."
    )


class Requirement(BaseModel):
    """A guide paragraph enriched with its extraction — one checklist row."""

    ref: str
    paragraph: GuideParagraph
    extraction: RequirementExtraction


# ----------------------------------------------------------------------- model-doc side


class DocSection(BaseModel):
    id: str
    heading: str
    text: str


class ModelDoc(BaseModel):
    title: str = "Model documentation"
    sections: list[DocSection]

    def section_by_id(self) -> dict[str, DocSection]:
        return {s.id: s for s in self.sections}


class ModelProfile(BaseModel):
    """Engagement metadata that drives applicability triage."""

    model_name: str = "Unnamed model"
    model_type: ModelType = ModelType.credit_risk
    portfolio: str = ""
    notes: str = ""


# ------------------------------------------------------------------------- assessment


class Applicability(BaseModel):
    applicable: bool
    reason: str
    method: str = "rule"  # "rule" | "llm"


class CoverageStatus(str, Enum):
    covered = "covered"
    partially_covered = "partially_covered"
    gap = "gap"
    not_applicable = "not_applicable"
    unclear = "unclear"


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str = Field(description="Verbatim quote copied exactly from the model documentation.")
    section_id: str = Field(description="The id attribute of the <section> the quote comes from.")


class AssessmentLLM(BaseModel):
    """LLM output schema for the core assessment (stage 3)."""

    model_config = ConfigDict(extra="forbid")

    status: CoverageStatus
    evidence: list[EvidenceLLM] = Field(
        description="Quotes that substantiate the status. Empty when status is 'gap'."
    )
    rationale: str = Field(description="Why the evidence does or does not satisfy each obligation.")
    confidence: Confidence
    open_questions: list[str] = Field(
        description="Questions the validator should put to the model owner."
    )


class TriageLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applicable: bool
    reason: str


class ReviewLLM(BaseModel):
    """LLM output schema for the adversarial review pass (stage 5)."""

    model_config = ConfigDict(extra="forbid")

    upheld: bool = Field(description="True if the 'covered' verdict survives skeptical scrutiny.")
    challenge: str = Field(description="The strongest objection found, or why none exists.")


class EvidenceRecord(BaseModel):
    quote: str
    section_id: str
    verified: Optional[bool] = None
    match_score: Optional[float] = None


class AssessmentRecord(BaseModel):
    """One persisted row of the traceability matrix (agent side, never mutated by the UI)."""

    ref: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    paragraph_number: Optional[str] = None
    paragraph_text: str = ""
    kind: RequirementKind = RequirementKind.requirement
    obligations: list[str] = []
    topics: list[str] = []

    applicability: Applicability
    status: Optional[CoverageStatus] = None
    evidence: list[EvidenceRecord] = []
    rationale: str = ""
    confidence: Optional[Confidence] = None
    open_questions: list[str] = []

    review_upheld: Optional[bool] = None
    review_challenge: str = ""

    needs_review: bool = False
    flags: list[str] = []

    @property
    def all_evidence_verified(self) -> Optional[bool]:
        checked = [e.verified for e in self.evidence if e.verified is not None]
        if not checked:
            return None
        return all(checked)


# ------------------------------------------------------------------- validator overrides


class ReviewState(str, Enum):
    pending = "pending"
    accepted = "accepted"
    overridden = "overridden"
    needs_work = "needs_work"


class Override(BaseModel):
    """Validator decision for one paragraph; stored separately from agent output."""

    ref: str
    status: Optional[CoverageStatus] = None  # None = keep agent status
    review_state: ReviewState = ReviewState.pending
    notes: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def final_status(record: AssessmentRecord, override: Optional[Override]) -> Optional[CoverageStatus]:
    if override is not None and override.status is not None:
        return override.status
    if not record.applicability.applicable:
        return CoverageStatus.not_applicable
    return record.status
