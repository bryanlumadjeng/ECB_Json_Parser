"""Pipeline configuration. Defaults here; override any field via a YAML file."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from .schemas import ModelType


class ChapterRule(BaseModel):
    """First matching rule wins; ``match`` is a lowercase substring of the chapter title."""

    match: str
    model_types: list[ModelType]


DEFAULT_CHAPTER_RULES = [
    # Order matters: "counterparty credit risk" must match before plain "credit risk".
    ChapterRule(match="counterparty credit risk", model_types=[ModelType.counterparty_credit_risk]),
    ChapterRule(match="credit risk", model_types=[ModelType.credit_risk]),
    ChapterRule(match="market risk", model_types=[ModelType.market_risk]),
    ChapterRule(
        match="general",
        model_types=[
            ModelType.general,
            ModelType.credit_risk,
            ModelType.market_risk,
            ModelType.counterparty_credit_risk,
        ],
    ),
]


class Config(BaseModel):
    # Models
    assess_model: str = "claude-opus-4-8"
    extract_model: str = "claude-opus-4-8"
    triage_model: str = "claude-haiku-4-5"
    review_model: str = "claude-opus-4-8"

    # Token limits per request
    assess_max_tokens: int = 8000
    extract_max_tokens: int = 2000
    triage_max_tokens: int = 1000
    review_max_tokens: int = 4000

    # Behaviour
    run_adversarial_review: bool = True
    llm_triage_fallback: bool = True       # use Haiku for paragraphs no chapter rule matched
    quote_match_threshold: float = 0.85    # fuzzy-match ratio below which a quote is unverified
    low_confidence_flags: bool = True      # flag confidence == low for review
    batch_poll_seconds: int = 30

    chapter_rules: list[ChapterRule] = DEFAULT_CHAPTER_RULES


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        return Config()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)
