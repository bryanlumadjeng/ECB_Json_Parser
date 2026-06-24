from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.agent.bm25_index import BM25Index


class TestBM25Index(unittest.TestCase):
    def test_empty_returns_empty(self):
        idx = BM25Index()
        self.assertEqual(idx.query("anything"), [])

    def test_add_and_query_single(self):
        idx = BM25Index()
        idx.add_documents(["probability of default IRB model"])
        results = idx.query("IRB probability default")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 0)

    def test_ranking_order(self):
        idx = BM25Index()
        idx.add_documents([
            "probability of default IRB model calibration",
            "loss given default LGD downturn estimation",
            "market risk value at risk VaR backtesting",
        ])
        results = idx.query("probability default IRB calibration")
        self.assertEqual(results[0][0], 0)

    def test_top_k(self):
        idx = BM25Index()
        idx.add_documents([f"document number {i} with unique content" for i in range(10)])
        results = idx.query("document number unique", top_k=3)
        self.assertEqual(len(results), 3)

    def test_missing_term_graceful(self):
        idx = BM25Index()
        idx.add_documents(["probability of default"])
        results = idx.query("zzzzzznonexistent")
        self.assertEqual(results, [])

    def test_tokenize_filters_stop_words(self):
        tokens = BM25Index.tokenize("the model and its use for the IRB approach")
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertNotIn("its", tokens)
        self.assertIn("model", tokens)
        self.assertIn("irb", tokens)

    def test_add_documents_twice_increments_index(self):
        idx = BM25Index()
        idx.add_documents(["credit risk IRB"])
        idx.add_documents(["market risk VaR"])
        results = idx.query("market risk VaR")
        self.assertEqual(results[0][0], 1)

    def test_scores_are_positive(self):
        idx = BM25Index()
        idx.add_documents(["IRB probability default", "LGD downturn loss"])
        for _, score in idx.query("IRB LGD"):
            self.assertGreater(score, 0)


if __name__ == "__main__":
    unittest.main()
