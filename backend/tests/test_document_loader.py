from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.agent.document_loader import chunk_text, detect_scope, load_document


FIXTURE = Path(__file__).parent / "fixtures" / "sample_doc.txt"


class TestChunkText(unittest.TestCase):
    def test_single_chunk_short_text(self):
        chunks = chunk_text("Short text.", chunk_size=2000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "chunk_0000")

    def test_multiple_chunks(self):
        text = "Word " * 1000  # 5000 chars
        chunks = chunk_text(text, chunk_size=1000, overlap=0)
        self.assertGreater(len(chunks), 1)

    def test_chunk_max_size(self):
        text = "A" * 5000
        chunks = chunk_text(text, chunk_size=1000, overlap=0)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), 1100)  # some tolerance for sentence breaks

    def test_overlap_causes_more_chunks(self):
        text = "Sentence ends here. " * 200
        no_overlap = chunk_text(text, chunk_size=500, overlap=0)
        with_overlap = chunk_text(text, chunk_size=500, overlap=100)
        self.assertGreaterEqual(len(with_overlap), len(no_overlap))

    def test_char_start_end_consistent(self):
        text = "Hello world. " * 300
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        for chunk in chunks:
            self.assertGreaterEqual(chunk.char_end, chunk.char_start)


class TestLoadDocument(unittest.TestCase):
    def test_load_txt(self):
        text = load_document(FIXTURE)
        self.assertGreater(len(text), 100)
        self.assertIn("IRB", text)

    def test_unsupported_extension_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".docx") as f:
            with self.assertRaises(ValueError):
                load_document(Path(f.name))


class TestDetectScope(unittest.TestCase):
    def test_credit_risk_detected(self):
        text = load_document(FIXTURE)
        scope = detect_scope(text)
        self.assertIn("credit_risk", scope)

    def test_non_credit_doc(self):
        text = "VaR stressed expected shortfall FRTB DRC sensitivities bucket curvature delta nmrf rrao"
        scope = detect_scope(text)
        # Should not be credit-risk dominant
        self.assertTrue(
            "market_risk_crr3" in scope or "market_risk_crr2" in scope,
        )

    def test_ccr_doc(self):
        text = "EPE IMM netting margin collateral alpha CVA counterparty MPOR EEPE MTM"
        scope = detect_scope(text)
        self.assertIn("ccr", scope)

    def test_returns_list(self):
        scope = detect_scope("some generic text")
        self.assertIsInstance(scope, list)


if __name__ == "__main__":
    unittest.main()
