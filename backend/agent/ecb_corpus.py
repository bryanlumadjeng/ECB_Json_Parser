from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Guide zone boundaries by first paragraph ID
# Determined from supervisory_guide_paragraphs.json analysis
_ZONE_BOUNDARIES = [
    (1830, "ccr"),
    (1405, "market_risk_crr3"),
    (966, "market_risk_crr2"),
    (180, "credit_risk"),
    (0, "overarching"),
]


def _zone_for_id(para_id: int) -> str:
    for boundary, zone in _ZONE_BOUNDARIES:
        if para_id >= boundary:
            return zone
    return "overarching"


# Chapters that are primarily informational (table of contents, abbreviations, annex cover)
_SKIP_CHAPTER_NAMES: frozenset[str] = frozenset({
    "July 2025",
    "Foreword",
    "Relevant regulatory references",
    "Annex",
    "Abbreviations",
})

# Maps scope tag → list of chapter display names (after disambiguation)
# Chapters not listed here are still evaluated if their zone matches the scope.
# This is used only for the overarching section which always applies to all scopes.
ALWAYS_INCLUDE_ZONES: frozenset[str] = frozenset({"overarching"})


@dataclass
class EcbChapter:
    display_name: str
    chapter: str
    zone: str
    paragraphs: list[dict] = field(default_factory=list)

    @property
    def text(self) -> str:
        parts = []
        for p in self.paragraphs:
            pid = p.get("id", "")
            parts.append(f"[Para {pid}] {p['text']}")
        return "\n\n".join(parts)

    @property
    def paragraph_ids(self) -> list[int]:
        return [p["id"] for p in self.paragraphs]

    @property
    def total_chars(self) -> int:
        return sum(len(p["text"]) for p in self.paragraphs)


class EcbCorpus:
    def __init__(self, json_path: Path) -> None:
        self._chapters: list[EcbChapter] = []
        self._load(json_path)

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        paragraphs: list[dict] = data["paragraphs"]

        # Group paragraphs into chapters preserving document order.
        # Handle duplicate chapter names by appending a zone suffix.
        groups: list[EcbChapter] = []
        current: EcbChapter | None = None
        name_seen: dict[str, int] = {}  # track by name only for display deduplication

        for para in paragraphs:
            ch_name = para["chapter"]
            zone = _zone_for_id(para["id"])

            if current is None or current.chapter != ch_name or current.zone != zone:
                # Start a new group; disambiguate display name if seen before
                count = name_seen.get(ch_name, 0)
                name_seen[ch_name] = count + 1

                if count == 0:
                    display = ch_name
                else:
                    display = f"{ch_name} [{zone.replace('_', ' ').title()}]"

                current = EcbChapter(
                    display_name=display,
                    chapter=ch_name,
                    zone=zone,
                    paragraphs=[],
                )
                groups.append(current)

            current.paragraphs.append(para)

        # Filter out informational-only chapters and very short chapters
        self._chapters = [
            ch for ch in groups
            if ch.chapter not in _SKIP_CHAPTER_NAMES and ch.total_chars >= 200
        ]

    @property
    def chapters(self) -> list[EcbChapter]:
        return self._chapters

    def filter_by_scope(self, scope_tags: list[str]) -> list[EcbChapter]:
        """Return chapters matching the given scope tags.

        The overarching zone is always included regardless of scope_tags.
        Passing 'all' as a tag returns every chapter.
        """
        if "all" in scope_tags:
            return list(self._chapters)

        tag_set = set(scope_tags)
        return [
            ch for ch in self._chapters
            if ch.zone in ALWAYS_INCLUDE_ZONES or ch.zone in tag_set
        ]

    def build_chapter_bm25(self):  # -> BM25Index
        from backend.agent.bm25_index import BM25Index
        idx = BM25Index()
        idx.add_documents([ch.text for ch in self._chapters])
        return idx
