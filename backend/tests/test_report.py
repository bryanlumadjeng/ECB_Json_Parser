from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.agent.evaluator import EvaluationResult
from backend.agent.report import ComplianceReport, build_report, compute_compliance_score

ECB_JSON = Path(__file__).parent.parent.parent / "supervisory_guide_paragraphs.json"
BANK_DOC = Path(__file__).parent / "fixtures" / "sample_doc.txt"


def _make_result(verdict: str, chapter: str = "Test Chapter") -> EvaluationResult:
    return EvaluationResult(
        chapter=chapter,
        display_name=chapter,
        zone="credit_risk",
        paragraph_ids=[1, 2, 3],
        verdict=verdict,
        confidence="high",
        ecb_requirement_summary="Test requirement",
        gap_description="Gap detail" if verdict in ("missing", "partial") else None,
        matched_excerpts=[],
        recommendation="Fix it" if verdict != "compliant" else None,
        input_tokens=100,
        output_tokens=50,
    )


class TestComplianceScore(unittest.TestCase):
    def test_all_compliant(self):
        results = [_make_result("compliant") for _ in range(4)]
        self.assertAlmostEqual(compute_compliance_score(results), 1.0)

    def test_all_missing(self):
        results = [_make_result("missing") for _ in range(4)]
        self.assertAlmostEqual(compute_compliance_score(results), 0.0)

    def test_mixed(self):
        results = [
            _make_result("compliant"),
            _make_result("partial"),
            _make_result("missing"),
        ]
        # (1 + 0.5 + 0) / 3 = 0.5
        self.assertAlmostEqual(compute_compliance_score(results), 0.5, places=3)

    def test_excludes_not_applicable(self):
        results = [
            _make_result("compliant"),
            _make_result("not_applicable"),
            _make_result("not_applicable"),
        ]
        # Only 1 applicable, it's compliant → 1.0
        self.assertAlmostEqual(compute_compliance_score(results), 1.0)

    def test_empty_returns_zero(self):
        self.assertAlmostEqual(compute_compliance_score([]), 0.0)

    def test_all_not_applicable_returns_zero(self):
        results = [_make_result("not_applicable") for _ in range(3)]
        self.assertAlmostEqual(compute_compliance_score(results), 0.0)


class TestBuildReport(unittest.TestCase):
    def _build(self, results):
        return build_report(
            bank_doc_path=BANK_DOC,
            bank_doc_size=1000,
            bank_chunks_count=10,
            ecb_json_path=ECB_JSON,
            scope_tags=["credit_risk"],
            chapters_evaluated=len(results),
            chapters_skipped=5,
            results=results,
            total_input_tokens=5000,
            total_output_tokens=1000,
        )

    def test_report_structure_keys(self):
        report = self._build([_make_result("compliant")])
        self.assertTrue(report.report_id.startswith("eval_"))
        self.assertIsNotNone(report.generated_at)
        self.assertIn("summary", report.__dataclass_fields__)

    def test_finding_ids_sequential(self):
        results = [
            _make_result("missing", "Chapter A"),
            _make_result("partial", "Chapter B"),
            _make_result("compliant", "Chapter C"),
        ]
        report = self._build(results)
        self.assertEqual(len(report.findings), 2)
        self.assertEqual(report.findings[0]["finding_id"], "F001")
        self.assertEqual(report.findings[1]["finding_id"], "F002")

    def test_summary_counts(self):
        results = [
            _make_result("compliant"),
            _make_result("partial"),
            _make_result("missing"),
            _make_result("not_applicable"),
        ]
        report = self._build(results)
        s = report.summary
        self.assertEqual(s["compliant"], 1)
        self.assertEqual(s["partial"], 1)
        self.assertEqual(s["missing"], 1)
        self.assertEqual(s["not_applicable"], 1)

    def test_overall_verdict_non_compliant_when_missing(self):
        report = self._build([_make_result("missing")])
        self.assertEqual(report.summary["overall_verdict"], "non_compliant")

    def test_overall_verdict_partial(self):
        report = self._build([_make_result("partial")])
        self.assertEqual(report.summary["overall_verdict"], "partial")

    def test_to_json_valid(self):
        import json
        report = self._build([_make_result("compliant")])
        parsed = json.loads(report.to_json())
        self.assertIn("summary", parsed)
        self.assertIn("findings", parsed)

    def test_markdown_has_summary_table(self):
        report = self._build([_make_result("compliant")])
        md = report.to_markdown()
        self.assertIn("Compliance score", md)
        self.assertIn("## Summary", md)

    def test_markdown_missing_before_partial(self):
        results = [_make_result("missing", "A"), _make_result("partial", "B")]
        report = self._build(results)
        md = report.to_markdown()
        idx_missing = md.index("## Missing")
        idx_partial = md.index("## Partial")
        self.assertLess(idx_missing, idx_partial)

    def test_token_usage_in_report(self):
        report = self._build([_make_result("compliant")])
        self.assertEqual(report.token_usage["input_tokens"], 5000)
        self.assertEqual(report.token_usage["output_tokens"], 1000)
        self.assertGreater(report.token_usage["estimated_cost_usd"], 0)


if __name__ == "__main__":
    unittest.main()
