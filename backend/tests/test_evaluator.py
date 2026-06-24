from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.agent.evaluator import Evaluator


class TestParseVerdict(unittest.TestCase):
    def _evaluator(self):
        # Only _parse_verdict is tested here; no real API client needed
        e = object.__new__(Evaluator)
        e._model = "claude-sonnet-4-6"
        e._max_retries = 1
        e._inter_call_delay = 0
        e._total_input = 0
        e._total_output = 0
        return e

    def test_valid_json_compliant(self):
        ev = self._evaluator()
        raw = '{"verdict":"compliant","confidence":"high","ecb_requirement_summary":"ok","gap_description":null,"matched_excerpts":["some text"],"recommendation":null}'
        result = ev._parse_verdict(raw)
        self.assertEqual(result["verdict"], "compliant")
        self.assertEqual(result["confidence"], "high")

    def test_strips_markdown_fences(self):
        ev = self._evaluator()
        raw = '```json\n{"verdict":"missing","confidence":"medium","ecb_requirement_summary":"x","gap_description":"y","matched_excerpts":[],"recommendation":"z"}\n```'
        result = ev._parse_verdict(raw)
        self.assertEqual(result["verdict"], "missing")

    def test_strips_plain_fences(self):
        ev = self._evaluator()
        raw = '```\n{"verdict":"partial","confidence":"low","ecb_requirement_summary":"","gap_description":null,"matched_excerpts":[],"recommendation":null}\n```'
        result = ev._parse_verdict(raw)
        self.assertEqual(result["verdict"], "partial")

    def test_invalid_json_fallback_regex(self):
        ev = self._evaluator()
        raw = 'blah blah "verdict": "missing" blah'
        result = ev._parse_verdict(raw)
        self.assertEqual(result["verdict"], "missing")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("parse error", result["gap_description"])

    def test_completely_unparseable_returns_partial(self):
        ev = self._evaluator()
        result = ev._parse_verdict("not json at all")
        self.assertEqual(result["verdict"], "partial")
        self.assertEqual(result["confidence"], "low")

    def test_invalid_verdict_normalized_to_partial(self):
        ev = self._evaluator()
        raw = '{"verdict":"unknown_value","confidence":"high","ecb_requirement_summary":"","gap_description":null,"matched_excerpts":[],"recommendation":null}'
        result = ev._parse_verdict(raw)
        self.assertEqual(result["verdict"], "partial")

    def test_not_applicable_verdict_valid(self):
        ev = self._evaluator()
        raw = '{"verdict":"not_applicable","confidence":"high","ecb_requirement_summary":"","gap_description":null,"matched_excerpts":[],"recommendation":null}'
        result = ev._parse_verdict(raw)
        self.assertEqual(result["verdict"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
