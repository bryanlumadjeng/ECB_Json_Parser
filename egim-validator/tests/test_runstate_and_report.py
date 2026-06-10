import tempfile
import unittest
from pathlib import Path

from egim_validator.runstate import (
    RunPaths,
    load_assessments,
    load_overrides,
    read_state,
    save_override,
    update_state,
    write_assessment,
)
from egim_validator.schemas import (
    Applicability,
    AssessmentRecord,
    CoverageStatus,
    Override,
    ReviewState,
)
from egim_validator.stages.report import build_rows


def make_record(ref="EGIM-0001", status=CoverageStatus.covered) -> AssessmentRecord:
    return AssessmentRecord(
        ref=ref,
        chapter="2 Credit risk",
        paragraph_text="Institutions should do X.",
        applicability=Applicability(applicable=True, reason="rule"),
        status=status,
        rationale="because",
    )


class TestRunState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = RunPaths(self.tmp.name, "run-1").ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_roundtrip(self):
        update_state(self.paths, stage="assess", to_assess=10)
        state = read_state(self.paths)
        self.assertEqual(state["stage"], "assess")
        self.assertEqual(state["to_assess"], 10)
        self.assertIn("updated_at", state)

    def test_assessment_roundtrip(self):
        write_assessment(self.paths, make_record())
        loaded = load_assessments(self.paths)
        self.assertEqual(loaded["EGIM-0001"].status, CoverageStatus.covered)

    def test_override_roundtrip(self):
        save_override(self.paths, Override(ref="EGIM-0001", status=CoverageStatus.gap, notes="disagree"))
        loaded = load_overrides(self.paths)
        self.assertEqual(loaded["EGIM-0001"].status, CoverageStatus.gap)


class TestReportMerge(unittest.TestCase):
    def test_override_wins_in_final_status(self):
        record = make_record(status=CoverageStatus.covered)
        override = Override(ref=record.ref, status=CoverageStatus.gap, review_state=ReviewState.overridden, notes="n")
        rows = build_rows([record], {record.ref: override})
        self.assertEqual(rows[0]["Agent status"], "covered")
        self.assertEqual(rows[0]["Final status"], "gap")
        self.assertEqual(rows[0]["Review state"], "overridden")
        self.assertEqual(rows[0]["Validator notes"], "n")

    def test_no_override_keeps_agent_status(self):
        record = make_record(status=CoverageStatus.partially_covered)
        rows = build_rows([record], {})
        self.assertEqual(rows[0]["Final status"], "partially_covered")
        self.assertEqual(rows[0]["Review state"], "pending")

    def test_not_applicable_overrides_status(self):
        record = make_record()
        record.applicability = Applicability(applicable=False, reason="market risk only")
        rows = build_rows([record], {})
        self.assertEqual(rows[0]["Final status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
