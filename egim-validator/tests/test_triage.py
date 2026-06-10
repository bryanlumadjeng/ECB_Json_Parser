import unittest

from egim_validator.config import Config
from egim_validator.schemas import (
    GuideParagraph,
    ModelProfile,
    ModelType,
    Requirement,
    RequirementExtraction,
    RequirementKind,
)
from egim_validator.stages.triage import triage


def req(ref_id: int, chapter: str, kind=RequirementKind.requirement, model_types=None) -> Requirement:
    p = GuideParagraph(id=ref_id, chapter=chapter, text="Institutions should do X.")
    return Requirement(
        ref=p.ref,
        paragraph=p,
        extraction=RequirementExtraction(
            kind=kind, summary="s", obligations=["do X"], topics=[], model_types=model_types or []
        ),
    )


CONFIG = Config(llm_triage_fallback=False)
CREDIT_PROFILE = ModelProfile(model_name="m", model_type=ModelType.credit_risk)


class TestTriageRules(unittest.TestCase):
    def test_general_chapter_applies_to_all(self):
        result = triage([req(1, "1 General topics")], CREDIT_PROFILE, CONFIG)
        self.assertTrue(result["EGIM-0001"].applicable)

    def test_credit_chapter_applies_to_credit_model(self):
        result = triage([req(2, "2 Credit risk")], CREDIT_PROFILE, CONFIG)
        self.assertTrue(result["EGIM-0002"].applicable)

    def test_market_chapter_not_applicable_to_credit_model(self):
        result = triage([req(3, "3 Market risk")], CREDIT_PROFILE, CONFIG)
        self.assertFalse(result["EGIM-0003"].applicable)

    def test_counterparty_matches_before_credit(self):
        # "counterparty credit risk" contains "credit risk" — rule order must disambiguate
        result = triage([req(4, "4 Counterparty credit risk")], CREDIT_PROFILE, CONFIG)
        self.assertFalse(result["EGIM-0004"].applicable)
        self.assertIn("counterparty", result["EGIM-0004"].reason)

    def test_background_paragraph_not_applicable(self):
        result = triage([req(5, "1 General topics", kind=RequirementKind.background)], CREDIT_PROFILE, CONFIG)
        self.assertFalse(result["EGIM-0005"].applicable)

    def test_unmatched_chapter_defaults_to_applicable(self):
        result = triage([req(6, "Annex A")], CREDIT_PROFILE, CONFIG)
        self.assertTrue(result["EGIM-0006"].applicable)

    def test_paragraph_level_scope_used_when_no_chapter_rule(self):
        r = req(7, "Annex B", model_types=[ModelType.market_risk])
        result = triage([r], CREDIT_PROFILE, CONFIG)
        self.assertFalse(result["EGIM-0007"].applicable)


if __name__ == "__main__":
    unittest.main()
