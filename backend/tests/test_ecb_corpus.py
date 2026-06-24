from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.agent.ecb_corpus import EcbCorpus

ECB_JSON = Path(__file__).parent.parent.parent / "supervisory_guide_paragraphs.json"


@unittest.skipUnless(ECB_JSON.exists(), "supervisory_guide_paragraphs.json not found")
class TestEcbCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = EcbCorpus(ECB_JSON)

    def test_loads_paragraphs(self):
        total_paras = sum(len(ch.paragraphs) for ch in self.corpus.chapters)
        self.assertGreater(total_paras, 2000)

    def test_chapter_count_reasonable(self):
        # Should be close to 76 (minus skipped informational chapters)
        self.assertGreater(len(self.corpus.chapters), 50)
        self.assertLess(len(self.corpus.chapters), 80)

    def test_no_tiny_chapters(self):
        for ch in self.corpus.chapters:
            self.assertGreaterEqual(ch.total_chars, 200, f"Chapter too short: {ch.display_name!r}")

    def test_filter_credit_risk_includes_credit_chapters(self):
        chapters = self.corpus.filter_by_scope(["credit_risk"])
        names = [ch.chapter for ch in chapters]
        self.assertIn("16 Probability of default", names)
        self.assertIn("17 Loss given default", names)
        self.assertIn("18 Conversion factors", names)

    def test_filter_always_includes_overarching(self):
        chapters = self.corpus.filter_by_scope(["credit_risk"])
        zones = {ch.zone for ch in chapters}
        self.assertIn("overarching", zones)

    def test_filter_credit_risk_excludes_market_risk(self):
        chapters = self.corpus.filter_by_scope(["credit_risk"])
        zones = {ch.zone for ch in chapters}
        self.assertNotIn("market_risk_crr2", zones)
        self.assertNotIn("market_risk_crr3", zones)
        self.assertNotIn("ccr", zones)

    def test_filter_all_returns_everything(self):
        all_chapters = self.corpus.filter_by_scope(["all"])
        self.assertEqual(len(all_chapters), len(self.corpus.chapters))

    def test_paragraph_ids_property(self):
        ch = self.corpus.chapters[0]
        ids = ch.paragraph_ids
        self.assertIsInstance(ids, list)
        self.assertTrue(all(isinstance(i, int) for i in ids))

    def test_text_includes_para_prefix(self):
        ch = next(c for c in self.corpus.chapters if len(c.paragraphs) > 2)
        self.assertIn("[Para ", ch.text)

    def test_filter_ccr(self):
        chapters = self.corpus.filter_by_scope(["ccr"])
        ccr_chapters = [ch for ch in chapters if ch.zone == "ccr"]
        self.assertGreater(len(ccr_chapters), 5)

    def test_no_duplicate_display_names(self):
        names = [ch.display_name for ch in self.corpus.chapters]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
