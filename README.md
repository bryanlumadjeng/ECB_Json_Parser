# ECB JSON Parser

Transposes each paragraph of the [ECB supervisory guide](https://www.bankingsupervision.europa.eu/ecb/pub/pdf/ssm.supervisory_guide202507.en.pdf)
(July 2025) into a JSON record.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Download the guide and write supervisory_guide_paragraphs.json
python ecb_pdf_to_json.py

# Or parse a local copy / a different ECB publication
python ecb_pdf_to_json.py --pdf ssm.supervisory_guide202507.en.pdf
python ecb_pdf_to_json.py --url https://... -o out.json
```

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

`ecb_pdf_to_json.py` extracts layout blocks with PyMuPDF (text, page, font
size, boldness, vertical position), then:

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
