import unittest

from egim_validator.schemas import (
    Applicability,
    AssessmentRecord,
    CoverageStatus,
    DocSection,
    EvidenceRecord,
    ModelDoc,
)
from egim_validator.stages.verify import match_quote, verify_record

DOC = ModelDoc(
    sections=[
        DocSection(id="S1", heading="Governance", text="The model is registered in the group model inventory under ID RM-PD-017."),
        DocSection(id="S2", heading="Validation", text="Validation is performed annually by Model Risk Management."),
    ]
)


def make_record(evidence):
    return AssessmentRecord(
        ref="EGIM-0001",
        applicability=Applicability(applicable=True, reason="test"),
        status=CoverageStatus.covered,
        evidence=evidence,
    )


class TestMatchQuote(unittest.TestCase):
    def test_exact_match(self):
        ok, score = match_quote("group model inventory", DOC.sections[0].text)
        self.assertTrue(ok)
        self.assertEqual(score, 1.0)

    def test_whitespace_and_case_insensitive(self):
        ok, _ = match_quote("Group  model\nINVENTORY", DOC.sections[0].text)
        self.assertTrue(ok)

    def test_fuzzy_match_minor_difference(self):
        ok, score = match_quote(
            "The model is registered in the group model inventory under RM-PD-017.",
            DOC.sections[0].text,
        )
        self.assertTrue(ok)
        self.assertGreater(score, 0.85)

    def test_fabricated_quote_fails(self):
        ok, score = match_quote("The model uses quantum annealing for PD estimation.", DOC.sections[0].text)
        self.assertFalse(ok)
        self.assertLess(score, 0.85)


class TestVerifyRecord(unittest.TestCase):
    def test_verified_evidence(self):
        record = make_record([EvidenceRecord(quote="group model inventory", section_id="S1")])
        record = verify_record(record, DOC)
        self.assertTrue(record.evidence[0].verified)
        self.assertFalse(record.needs_review)

    def test_wrong_section_is_flagged_but_verified(self):
        record = make_record([EvidenceRecord(quote="group model inventory", section_id="S2")])
        record = verify_record(record, DOC)
        self.assertTrue(record.evidence[0].verified)
        self.assertTrue(any("not in cited section" in f for f in record.flags))

    def test_fabricated_quote_flags_record(self):
        record = make_record([EvidenceRecord(quote="entirely invented text about something else", section_id="S1")])
        record = verify_record(record, DOC)
        self.assertFalse(record.evidence[0].verified)
        self.assertTrue(record.needs_review)
        self.assertTrue(any("unverifiable" in f for f in record.flags))

    def test_unknown_section_id(self):
        record = make_record([EvidenceRecord(quote="group model inventory", section_id="NOPE")])
        record = verify_record(record, DOC)
        # quote exists elsewhere in the doc, so it verifies with a flag
        self.assertTrue(record.evidence[0].verified)
        self.assertTrue(any("not in cited section" in f for f in record.flags))


if __name__ == "__main__":
    unittest.main()
