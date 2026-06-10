#!/usr/bin/env python3
"""Transpose each paragraph of an ECB supervisory guide PDF into JSON.

Downloads (or reads locally) the ECB supervisory guide, extracts its text
with PyMuPDF, reassembles the raw layout blocks into logical paragraphs and
writes one JSON record per paragraph, including the chapter/section heading
context and the page range each paragraph spans.

Usage:
    python ecb_pdf_to_json.py                       # download default guide
    python ecb_pdf_to_json.py --pdf local_copy.pdf  # use a local file
    python ecb_pdf_to_json.py -o paragraphs.json

Requires: pymupdf, requests  (pip install -r requirements.txt)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_URL = (
    "https://www.bankingsupervision.europa.eu/ecb/pub/pdf/"
    "ssm.supervisory_guide202507.en.pdf"
)

# Some ECB endpoints reject requests with a bare python/curl User-Agent.
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ecb-json-parser/1.0"}

# Heading detection: numbered headings such as "2", "2.1", "2.1.3" followed
# by a title that does not end like a sentence.
HEADING_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(\S.*)$")

# Numbered paragraphs such as "12. The ECB ..." at the start of a block.
PARA_NUMBER_RE = re.compile(r"^(\d{1,3})\.\s+(?=[A-Z“‘(])")

# Footnote markers like "12 See Article ..." at the bottom of a page are
# short blocks in a clearly smaller font; handled via font size, not regex.

SENTENCE_END = tuple(".!?:;”’)")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Block:
    """A raw text block as produced by the PDF extractor: one or more lines
    of text with a dominant font size and a page number."""

    text: str
    page: int
    font_size: float
    bold: bool = False
    y0: float = 0.0
    page_height: float = 842.0


@dataclass
class Paragraph:
    text: str
    page_start: int
    page_end: int
    chapter: str | None = None
    section: str | None = None
    paragraph_number: str | None = None

    def to_json(self, idx: int) -> dict:
        return {
            "id": idx,
            "paragraph_number": self.paragraph_number,
            "chapter": self.chapter,
            "section": self.section,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "text": self.text,
        }


@dataclass
class HeadingState:
    chapter: str | None = None
    section: str | None = None

    def update(self, heading_text: str) -> None:
        match = HEADING_NUMBER_RE.match(heading_text)
        if match and "." not in match.group(1):
            self.chapter = heading_text
            self.section = None
        elif match:
            self.section = heading_text
        else:
            # Unnumbered heading (e.g. "Foreword", "Introduction"): treat as
            # a chapter-level context switch.
            self.chapter = heading_text
            self.section = None


# ---------------------------------------------------------------------------
# PDF extraction (PyMuPDF)
# ---------------------------------------------------------------------------

def download_pdf(url: str, dest: Path) -> Path:
    import requests

    response = requests.get(url, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError(
            f"Response from {url} is not a PDF "
            f"(content-type: {response.headers.get('content-type')})"
        )
    dest.write_bytes(response.content)
    return dest


def extract_blocks(pdf_path: Path) -> list[Block]:
    """Read the PDF and return one Block per visual text block."""
    import fitz  # PyMuPDF

    blocks: list[Block] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            page_dict = page.get_text("dict")
            for raw in page_dict["blocks"]:
                if raw.get("type") != 0:  # images etc.
                    continue
                lines: list[str] = []
                sizes: list[float] = []
                bold_flags: list[bool] = []
                for line in raw["lines"]:
                    spans = [s for s in line["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    lines.append("".join(s["text"] for s in spans).strip())
                    for span in spans:
                        sizes.append(round(span["size"], 1))
                        bold_flags.append(bool(span["flags"] & 2 ** 4))
                text = join_lines(lines)
                if not text:
                    continue
                blocks.append(
                    Block(
                        text=text,
                        page=page_index,
                        font_size=Counter(sizes).most_common(1)[0][0],
                        bold=sum(bold_flags) > len(bold_flags) / 2,
                        y0=raw["bbox"][1],
                        page_height=page.rect.height,
                    )
                )
    return blocks


def join_lines(lines: list[str]) -> str:
    """Join the lines of a block into a single string, undoing end-of-line
    hyphenation ("super-" + "vision" -> "supervision")."""
    out = ""
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if out.endswith("-") and line[:1].islower():
            out = out[:-1] + line
        elif out:
            out += " " + line
        else:
            out = line
    return out


# ---------------------------------------------------------------------------
# Paragraph segmentation (pure logic, unit-testable without PyMuPDF)
# ---------------------------------------------------------------------------

def body_font_size(blocks: list[Block]) -> float:
    """The body text size is the most common font size weighted by length."""
    counter: Counter = Counter()
    for block in blocks:
        counter[block.font_size] += len(block.text)
    return counter.most_common(1)[0][0] if counter else 10.0


def repeated_furniture(blocks: list[Block]) -> set[str]:
    """Texts that recur on many pages (running headers/footers)."""
    seen: dict[str, set[int]] = {}
    for block in blocks:
        seen.setdefault(block.text, set()).add(block.page)
    pages = {b.page for b in blocks}
    threshold = max(3, len(pages) // 4)
    return {text for text, on in seen.items() if len(on) >= threshold}


def is_page_furniture(block: Block, furniture: set[str]) -> bool:
    if block.text in furniture:
        return True
    # Bare page numbers / short marginalia at the extreme top or bottom.
    near_edge = block.y0 < 0.07 * block.page_height or block.y0 > 0.93 * block.page_height
    return near_edge and len(block.text) <= 40 and not block.text.endswith(SENTENCE_END)


def is_heading(block: Block, body_size: float) -> bool:
    if len(block.text) > 150 or block.text.endswith(SENTENCE_END[:3]):
        return False
    if block.font_size >= body_size + 1.0:
        return True
    return block.bold and bool(HEADING_NUMBER_RE.match(block.text))


def continues_previous(prev: Paragraph, block: Block) -> bool:
    """A block continues the previous paragraph if the paragraph did not end
    a sentence and the block does not start a new numbered paragraph."""
    if PARA_NUMBER_RE.match(block.text):
        return False
    if prev.text.endswith(SENTENCE_END):
        return False
    first = block.text[:1]
    return first.islower() or first in ",;)–-”" or prev.text.endswith("-")


def segment_paragraphs(blocks: list[Block]) -> list[Paragraph]:
    body_size = body_font_size(blocks)
    furniture = repeated_furniture(blocks)
    state = HeadingState()
    paragraphs: list[Paragraph] = []

    for block in blocks:
        if is_page_furniture(block, furniture):
            continue
        # Footnotes and other small print are kept out of the paragraph flow.
        if block.font_size <= body_size - 1.5:
            continue
        if is_heading(block, body_size):
            state.update(block.text)
            continue

        if paragraphs and continues_previous(paragraphs[-1], block):
            prev = paragraphs[-1]
            joiner = "" if prev.text.endswith("-") else " "
            prev.text = (prev.text.rstrip("-") if prev.text.endswith("-") else prev.text) + joiner + block.text
            prev.page_end = block.page
            continue

        number_match = PARA_NUMBER_RE.match(block.text)
        paragraphs.append(
            Paragraph(
                text=block.text,
                page_start=block.page,
                page_end=block.page,
                chapter=state.chapter,
                section=state.section,
                paragraph_number=number_match.group(1) if number_match else None,
            )
        )
    return paragraphs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_output(paragraphs: list[Paragraph], source: str) -> dict:
    return {
        "source": source,
        "extracted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "paragraph_count": len(paragraphs),
        "paragraphs": [p.to_json(i) for i, p in enumerate(paragraphs, start=1)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL, help="PDF URL to download")
    parser.add_argument("--pdf", type=Path, help="use a local PDF instead of downloading")
    parser.add_argument("-o", "--output", type=Path, default=Path("supervisory_guide_paragraphs.json"))
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation (0 = compact)")
    args = parser.parse_args(argv)

    if args.pdf:
        pdf_path, source = args.pdf, str(args.pdf)
    else:
        pdf_path = Path(Path(args.url).name or "document.pdf")
        print(f"Downloading {args.url} ...", file=sys.stderr)
        download_pdf(args.url, pdf_path)
        source = args.url

    blocks = extract_blocks(pdf_path)
    paragraphs = segment_paragraphs(blocks)
    output = build_output(paragraphs, source)

    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=args.indent or None) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(paragraphs)} paragraphs to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
