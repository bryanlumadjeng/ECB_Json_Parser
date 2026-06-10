# ECB JSON Parser

Transposes each paragraph of the [ECB supervisory guide](https://www.bankingsupervision.europa.eu/ecb/pub/pdf/ssm.supervisory_guide202507.en.pdf)
(July 2025) into a JSON record.

## Setup

No installation is required — the parser runs on the Python standard
library alone (Python 3.10+). A bundled, dependency-free PDF reader
(`pdf_extract.py`) handles cross-reference streams, compressed object
streams, FlateDecode (with PNG/TIFF predictors) and Type0/CID fonts with
ToUnicode CMaps.

Two optional extras improve convenience, not correctness:

```bash
pip install -r requirements.txt   # optional
```

- **PyMuPDF** — if installed, it is used for higher-fidelity layout; if
  absent, the bundled extractor is used automatically.
- **requests** — only needed to download via `--url`. With a local file
  (`--pdf`) nothing extra is required.

## Usage

```bash
# Parse a local copy (no dependencies needed)
python ecb_pdf_to_json.py --pdf ssm.supervisory_guide202507.en.pdf

# Download the guide and parse it (needs requests + network access)
python ecb_pdf_to_json.py

# Different publication / custom output path
python ecb_pdf_to_json.py --url https://... -o out.json
```

The committed `supervisory_guide_paragraphs.json` is the result of running
the parser over the July 2025 guide (2,350 paragraphs).

## Output format

```json
{
  "source": "https://www.bankingsupervision.europa.eu/...pdf",
  "extracted_at": "2026-06-10T20:00:00+00:00",
  "paragraph_count": 123,
  "paragraphs": [
    {
      "id": 1,
      "paragraph_number": "1",
      "chapter": "1 Introduction",
      "section": "1.1 Scope",
      "page_start": 4,
      "page_end": 4,
      "text": "The ECB supervises significant institutions..."
    }
  ]
}
```

- `paragraph_number` is the number printed in the document itself when the
  paragraph is numbered (`"12."`), otherwise `null`.
- `chapter` / `section` give the heading context the paragraph appears under.
- Paragraphs that flow across a page break are merged, with `page_start` /
  `page_end` recording the span. End-of-line hyphenation is undone.
- Running headers/footers, bare page numbers and footnotes are excluded from
  the paragraph flow.

## How it works

`ecb_pdf_to_json.py` extracts layout blocks (text, page, font size,
boldness, vertical position) — via `pdf_extract.py` by default, or PyMuPDF
if installed — then:

1. determines the body font size (most common size, weighted by text length);
2. drops page furniture (text repeated on many pages, bare page numbers) and
   footnotes (notably smaller font);
3. treats larger or bold numbered blocks as headings and tracks the current
   chapter/section;
4. merges consecutive blocks into one paragraph when the previous block ends
   mid-sentence and the next one does not start a new numbered paragraph.

The segmentation logic is pure-Python and covered by unit tests:

```bash
python -m unittest test_ecb_pdf_to_json
```
