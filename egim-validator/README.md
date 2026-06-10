# EGIM Validator

Agentic workflow + Streamlit cockpit that checks bank **model documentation** against the
**ECB guide to internal models (EGIM)** and produces a per-paragraph **compliance
traceability matrix**: for every guide paragraph — applicability, coverage status
(covered / partially covered / gap / not applicable / unclear), verbatim evidence quotes
with section references, rationale, and confidence. A validator reviews, overrides and
exports the result.

> Agent verdicts are **drafts for the validator**, never a final judgement. Every quote is
> programmatically verified against the source documentation, and "covered" verdicts pass
> an adversarial second LLM pass before they reach the review queue.

## How it relates to ECB_Json_Parser

The parser (`ecb_pdf_to_json.py`, repo root) is a **one-off preprocessing tool**: run it
once per guide version to turn the ECB PDF into paragraph JSON. This app consumes that
JSON unchanged and never touches the parser.

```
ECB guide PDF ──(ecb_pdf_to_json.py, once)──▶ guide_paragraphs.json ─┐
model_doc.json / .md  (bank's structured model documentation) ──────┤
model_profile.yaml    (model type, portfolio, engagement notes) ────┴─▶ EGIM Validator
```

## Quickstart

```bash
cd egim-validator
pip install -r requirements.txt
cp .env.example .env           # add your ANTHROPIC_API_KEY

# Option A — UI (recommended)
streamlit run app/Home.py

# Option B — headless
python runner.py --runs-dir runs \
    --guide path/to/guide_paragraphs.json \
    --model-doc sample_data/model_doc.sample.json \
    --profile sample_data/model_profile.sample.yaml
```

Sample inputs to try the full loop are in `sample_data/`.

Run tests (no API key needed — the LLM-free core is fully unit-tested):

```bash
python -m unittest discover -s tests
```

## Pipeline

| Stage | What | How |
|---|---|---|
| 1 extract | Classify each guide paragraph: requirement / expectation / background; atomic obligations; topics; model-type scope | Opus batch + structured outputs; cached per guide version (`data/requirements_cache/`) |
| 2 triage | Which paragraphs apply to this engagement | Chapter rules first, paragraph scope second, Haiku fallback for the remainder |
| 3 assess | Judge coverage of each applicable requirement | Full model doc in a **cached system prefix** (1h TTL); one batched Opus request per requirement; ~50% batch discount + ~90% cache savings on doc tokens |
| 4 verify | Match every evidence quote back into the doc | Programmatic exact + fuzzy match — the anti-hallucination gate |
| 5 review | Try to refute every "covered" verdict | Skeptical Opus pass; failed verdicts are flagged (false "covered" is the expensive error) |
| 6 report | Traceability matrix | Excel (Matrix + Summary sheets), JSON, Markdown summary |

## UI ↔ pipeline contract

The pipeline runs as a **background subprocess** (`runner.py`) and shares state with the
UI only through the run directory — so the review workspace works while a run is still
in flight, and a closed browser loses nothing:

```
runs/<run_id>/
  state.json              pipeline-owned: stage, batch ids, counts (atomic writes)
  inputs/                 copies of guide / model_doc / profile / config
  assessments/<ref>.json  one record per paragraph, written as results land
  overrides.json          UI-owned: validator decisions — agent output is never mutated
  exports/                traceability_matrix.xlsx / .json, summary.md
  runner.log
```

UI pages: **Home** (create + launch runs) → **Run Monitor** (live progress, needs-review
queue) → **Review Workspace** (filterable matrix, side-by-side evidence with highlighted
quotes, status overrides + notes) → **Export** (overrides merged over agent verdicts).

## Input formats

- **Guide**: output of `ecb_pdf_to_json.py` (`{"paragraphs": [{id, paragraph_number, chapter, section, page_start, page_end, text}]}`).
- **Model doc**: JSON `{"title", "sections": [{"id", "heading", "text"}]}` (or a bare
  list of sections), or Markdown (split into sections at `#`–`####` headings).
- **Profile**: YAML — `model_name`, `model_type` (`credit_risk` | `market_risk` |
  `counterparty_credit_risk` | `general`), `portfolio`, `notes`.

Pipeline knobs (models, thresholds, chapter rules, adversarial review on/off) live in
`egim_validator/config.py`; override any field with a YAML file passed at run creation.

## Design

The full architecture rationale — stage design, prompt strategy, caching layout, cost
model, governance and limitations — is in [`docs/AGENT_DESIGN.md`](docs/AGENT_DESIGN.md).
