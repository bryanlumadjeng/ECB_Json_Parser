# EGIM Validator — Architecture & Design

Status: implemented (v0.1). This document records the design decisions behind the code
in this folder.

## 1. Problem & approach

A model validator must check whether a bank's model documentation evidences compliance
with the **ECB guide to internal models (EGIM)**. Done by hand this means walking
hundreds of guide paragraphs against hundreds of pages of documentation.

**Direction of validation.** The workflow is *guideline-driven*: it iterates over EGIM
paragraphs, not over model-doc paragraphs. This guarantees complete regulatory coverage
(no guide paragraph can be silently skipped) and yields a traceability matrix as the
natural output shape. The inverse mapping (doc section → relevant guide paragraphs)
falls out of the evidence references for free.

**Workflow, not free agent.** The pipeline is a staged, code-orchestrated sequence of
LLM calls rather than an open-ended agent loop. Reasons: every step is auditable
(prompt, response and verdict are persisted per paragraph), runs are resumable and
idempotent, costs are predictable, and nothing about the task needs model-driven
exploration — the checklist *is* the plan.

**Human in the loop by construction.** Agent verdicts are drafts. The UI's override
layer (separate `overrides.json`, agent output immutable) makes the validator's decision
the authoritative record while preserving the machine verdict for audit.

## 2. Trust architecture

Three mechanisms keep the LLM honest, ordered by strength:

1. **Programmatic citation verification (stage 4).** Every evidence quote must be found
   in the cited section (exact normalized match, then fuzzy ≥ 0.85). A quote found
   elsewhere in the doc flags "wrong section"; a quote found nowhere marks the record
   `needs_review` and the verdict untrusted. This is deterministic code, not a model
   opinion — fabricated evidence cannot reach the validator unflagged.
2. **Adversarial review (stage 5).** A second pass with a skeptical persona tries to
   *refute* every `covered` verdict. The asymmetry is deliberate: a false "covered"
   hides a real gap (expensive, dangerous); a false "gap" costs one extra look. Only
   "covered" needs the second opinion.
3. **Conservative prompting (stage 3).** The assessment prompt instructs: mentioning a
   topic is not evidencing it; when unsure, do not choose "covered"; low confidence is
   flagged for review.

## 3. Pipeline

```
guide_paragraphs.json     model_doc.json/.md     model_profile.yaml
        │                        │                      │
        ▼                        │                      │
[1 extract]  paragraph → kind, atomic obligations, topics, model-type scope
        │    (Opus batch, structured outputs; cached by guide SHA-256)
        ▼                        │                      │
[2 triage]   chapter rules → paragraph scope → Haiku fallback ◀──────┘
        │    applicable? + reason (rule|llm)
        ▼                        ▼
[3 assess]   per applicable requirement: status, evidence quotes, rationale,
        │    confidence, open questions   (Opus batch; doc in cached system prefix)
        ▼
[4 verify]   quotes matched back into the doc (exact + fuzzy)  ← anti-hallucination gate
        ▼
[5 review]   skeptical pass over 'covered' verdicts (optional, default on)
        ▼
[6 report]   Excel matrix + Summary sheet, JSON, Markdown summary
```

Stage notes:

- **1 extract** runs once per guide version — results cached in
  `data/requirements_cache/requirements_<sha>.json`. Failed extractions degrade to an
  unclassified *requirement* (never silently dropped).
- **2 triage** is deterministic where possible. EGIM chapters map cleanly to model
  types; rule order matters ("counterparty credit risk" before "credit risk").
  Background paragraphs are not applicable by definition. Unresolved rows default to
  applicable (false inclusion is cheap, false exclusion is not).
- **3 assess** sends ONE requirement per request so each verdict is independent,
  parallelizable and idempotent (`custom_id` = paragraph ref).

## 4. Claude API usage

| Concern | Choice |
|---|---|
| Models | `claude-opus-4-8` for extraction/assessment/review; `claude-haiku-4-5` for triage fallback |
| Thinking | `thinking: {type: "adaptive"}` on every request |
| Output shape | `output_config.format` JSON schema generated from Pydantic models with `extra="forbid"` (→ `additionalProperties: false`); responses parse deterministically, no regexing |
| Throughput/cost | **Message Batches API** for every stage — 50% discount; a validation run is not latency-sensitive |
| Long context | The full rendered model doc sits in the **system prefix** of every assess/review request with `cache_control: {type: "ephemeral", ttl: "1h"}` |

**Caching layout.** Render order is system → messages; the prefix is `[instructions,
documentation]` with the breakpoint on the documentation block, so instructions + doc
cache together. Both are byte-stable across the whole batch — only the short user
message varies. Effective doc-token cost ≈ one write (1.25–2×) + N reads (0.1×) instead
of N full passes. The 1h TTL covers batch scheduling spread.

**Cost sketch** (EGIM ≈ 900 paragraphs, ~600 applicable; doc ≈ 150K tokens): without
caching, assessment input would be ~600 × 150K = 90M tokens. With the cached prefix it
is ~1 write + 599 reads ≈ 150K + 599×15K-equivalent ≈ ~9.2M token-equivalents, halved
again by the batch discount — order of $50–100 per full run rather than thousands.
(Numbers are an estimate; actuals depend on doc size and output volume.)

**Fallback for oversized docs.** If doc + instructions approach the context window, the
documented fallback is retrieval: build a section index (id, heading, first sentences),
let a cheap pass pick candidate sections per requirement, and place only those in the
request. Not implemented in v0.1; the seam is `assess.build_system()`.

## 5. Run directory = UI ↔ pipeline contract

The Streamlit UI and the pipeline are decoupled by design — the pipeline is launched as
a detached subprocess and communicates exclusively via `runs/<run_id>/`:

- `state.json` — pipeline-owned heartbeat: stage, batch id/status, counts. Atomic
  writes (tmp + `os.replace`), so the UI can poll mid-write safely.
- `assessments/<ref>.json` — one file per paragraph, written **as results land**, so the
  Review Workspace is usable while a run is still in flight.
- `overrides.json` — UI-owned. The pipeline never reads or writes validator decisions;
  the UI never mutates agent output. Exports merge the two, override wins.
- Crash-safety for free: a closed laptop or dead Streamlit process loses nothing; the
  runner is resumable (`--run-id`) and skips work whose outputs exist.

Why not a DB/queue: single-validator local tool, confidential documents stay on disk,
and files are trivially inspectable/archivable as an audit artifact.

## 6. Governance & limitations

- **Decision rights.** The exported FINAL status is validator-owned; agent status is
  retained beside it. `Review state` (pending/accepted/overridden/needs_work) makes
  unreviewed rows visible.
- **Flags routed to humans:** unverifiable quotes, challenged "covered" verdicts, low
  confidence, failed requests, extraction fallbacks.
- **Confidentiality.** Model documentation is sent to the Anthropic API; deployment
  must follow the bank's data-handling approvals (API data is not used for training by
  default; consider a zero-retention agreement and the EU region endpoints as needed).
- **Out of scope (v0.1):** CRR/EBA RTS cross-references; multi-document evidence
  packages; OCR of scanned PDFs; automatic EGIM-version diffing.
- **Known soft spots:** triage rules assume EGIM-style chapter titles (configurable in
  `config.py`); fuzzy quote threshold 0.85 trades a few false flags for zero silent
  fabrications; extraction quality bounds checklist quality — spot-check
  `requirements_cache` once per guide version.

## 7. Module map

```
egim-validator/
  runner.py                     headless pipeline (subprocess entrypoint)
  egim_validator/
    schemas.py                  all data models (LLM-facing + storage)
    config.py                   models, thresholds, chapter rules
    ingest.py                   guide JSON, model doc (JSON/MD), profile YAML
    llm.py                      batch submit/poll + structured-output parsing
    runstate.py                 run directory contract (atomic state, records, overrides)
    stages/
      extract_requirements.py   stage 1   triage.py     stage 2
      assess.py                 stage 3   verify.py     stage 4
      review.py                 stage 5   report.py     stage 6
  app/                          Streamlit: Home, Run Monitor, Review Workspace, Export
  sample_data/                  runnable end-to-end demo inputs
  tests/                        LLM-free unit tests (verify, triage, runstate, report, ingest)
```
