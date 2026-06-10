"""Tests for the paragraph segmentation logic in ecb_pdf_to_json.

These use synthetic Block objects shaped like the PyMuPDF extractor output,
so they run without pymupdf installed and without network access.
"""

import unittest

from ecb_pdf_to_json import (
    Block,
    HeadingState,
    body_font_size,
    build_output,
    join_lines,
    segment_paragraphs,
)

BODY = 10.0
HEADING = 14.0
FOOTNOTE = 8.0


def block(text, page=1, size=BODY, bold=False, y0=300.0):
    return Block(text=text, page=page, font_size=size, bold=bold, y0=y0)


class JoinLinesTest(unittest.TestCase):
    def test_dehyphenates_line_breaks(self):
        self.assertEqual(
            join_lines(["The super-", "vision of banks"]),
            "The supervision of banks",
        )

    def test_keeps_real_hyphens_before_uppercase(self):
        self.assertEqual(
            join_lines(["the EU-", "China dialogue"]),
            "the EU- China dialogue",
        )

    def test_collapses_whitespace(self):
        self.assertEqual(join_lines(["a  b", " c "]), "a b c")


class HeadingStateTest(unittest.TestCase):
    def test_chapter_resets_section(self):
        state = HeadingState()
        state.update("2 Supervisory approach")
        state.update("2.1 Risk tolerance")
        self.assertEqual(state.section, "2.1 Risk tolerance")
        state.update("3 Supervisory cycle")
        self.assertEqual(state.chapter, "3 Supervisory cycle")
        self.assertIsNone(state.section)

    def test_unnumbered_heading_is_chapter(self):
        state = HeadingState()
        state.update("Foreword")
        self.assertEqual(state.chapter, "Foreword")


class SegmentationTest(unittest.TestCase):
    def test_paragraphs_get_heading_context(self):
        blocks = [
            block("1 Introduction", size=HEADING),
            block("1. The ECB supervises significant institutions."),
            block("1.1 Scope", size=HEADING),
            block("2. This guide applies to all supervised entities."),
        ]
        paras = segment_paragraphs(blocks)
        self.assertEqual(len(paras), 2)
        self.assertEqual(paras[0].chapter, "1 Introduction")
        self.assertIsNone(paras[0].section)
        self.assertEqual(paras[0].paragraph_number, "1")
        self.assertEqual(paras[1].section, "1.1 Scope")
        self.assertEqual(paras[1].paragraph_number, "2")

    def test_paragraph_continues_across_pages(self):
        blocks = [
            block("3. Supervision is conducted on the basis of", page=4),
            block("a forward-looking assessment of risks.", page=5),
        ]
        paras = segment_paragraphs(blocks)
        self.assertEqual(len(paras), 1)
        self.assertEqual(
            paras[0].text,
            "3. Supervision is conducted on the basis of a forward-looking "
            "assessment of risks.",
        )
        self.assertEqual(paras[0].page_start, 4)
        self.assertEqual(paras[0].page_end, 5)

    def test_new_numbered_paragraph_is_not_merged(self):
        blocks = [
            block("4. First point without terminal punctuation"),
            block("5. Second point follows."),
        ]
        paras = segment_paragraphs(blocks)
        self.assertEqual(len(paras), 2)

    def test_footnotes_and_furniture_are_dropped(self):
        blocks = [
            block("Guide to banking supervision", page=p, y0=20.0)
            for p in range(1, 7)
        ] + [
            block("6. A body paragraph stays in the output.", page=2),
            block("1 See Article 4 of the SSM Regulation.", page=2, size=FOOTNOTE),
            block("12", page=2, y0=810.0),
        ]
        paras = segment_paragraphs(blocks)
        self.assertEqual(len(paras), 1)
        self.assertIn("body paragraph", paras[0].text)

    def test_body_font_size_weighted_by_text_length(self):
        blocks = [
            block("Short heading", size=HEADING),
            block("A much longer body paragraph " * 5),
        ]
        self.assertEqual(body_font_size(blocks), BODY)

    def test_build_output_schema(self):
        paras = segment_paragraphs([block("7. Only paragraph here.")])
        out = build_output(paras, "test.pdf")
        self.assertEqual(out["paragraph_count"], 1)
        record = out["paragraphs"][0]
        self.assertEqual(record["id"], 1)
        self.assertEqual(record["paragraph_number"], "7")
        self.assertEqual(record["page_start"], 1)
        self.assertIn("text", record)


if __name__ == "__main__":
    unittest.main()
