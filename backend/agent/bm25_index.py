from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple

STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "man", "new", "now", "old", "see", "two", "way", "who", "boy",
    "did", "its", "let", "put", "say", "she", "too", "use", "that", "this",
    "with", "have", "from", "they", "will", "been", "were", "said", "each",
    "which", "their", "time", "when", "there", "than", "then", "some", "into",
    "more", "also", "other", "about", "such", "these", "where", "what",
    "shall", "may", "must", "should", "would", "could", "does", "used",
    "being", "both", "only", "over", "under", "same", "however",
})


class BM25Index:
    """Stdlib-only BM25 retrieval over a list of text documents."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._index: dict[str, dict[int, int]] = {}  # term → {doc_idx: tf}
        self._doc_lengths: list[int] = []
        self._avg_dl: float = 0.0
        self._n_docs: int = 0

    def add_documents(self, texts: list[str]) -> None:
        for text in texts:
            doc_idx = self._n_docs
            tokens = self.tokenize(text)
            self._doc_lengths.append(len(tokens))
            tf = Counter(tokens)
            for term, freq in tf.items():
                self._index.setdefault(term, {})[doc_idx] = freq
            self._n_docs += 1
        total = sum(self._doc_lengths)
        self._avg_dl = total / self._n_docs if self._n_docs else 0.0

    def query(self, query_text: str, top_k: int = 10) -> list[tuple[int, float]]:
        if self._n_docs == 0:
            return []
        terms = self.tokenize(query_text)
        scores: dict[int, float] = {}
        for term in set(terms):
            posting = self._index.get(term)
            if not posting:
                continue
            df = len(posting)
            idf = math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1)
            for doc_idx, tf in posting.items():
                dl = self._doc_lengths[doc_idx]
                norm_tf = tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self._avg_dl)
                )
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * norm_tf
        if not scores:
            return []
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    @staticmethod
    def tokenize(text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
        return [t for t in tokens if t not in STOP_WORDS]
