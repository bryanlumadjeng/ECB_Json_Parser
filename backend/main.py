from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is on the path so ecb_pdf_to_json can be imported
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.agent.bm25_index import BM25Index
from backend.agent.document_loader import chunk_text, detect_scope, load_document
from backend.agent.ecb_corpus import EcbCorpus
from backend.agent.evaluator import Evaluator
from backend.agent.report import build_report

_ECB_JSON = _ROOT / "supervisory_guide_paragraphs.json"

app = FastAPI(title="ECB Model Documentation Evaluator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the corpus once at startup
_corpus: EcbCorpus | None = None


def _get_corpus() -> EcbCorpus:
    global _corpus
    if _corpus is None:
        if not _ECB_JSON.exists():
            raise HTTPException(
                status_code=503,
                detail=f"ECB corpus not found at {_ECB_JSON}",
            )
        _corpus = EcbCorpus(_ECB_JSON)
    return _corpus


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "ecb_corpus": _ECB_JSON.exists()}


@app.post("/api/evaluate")
async def evaluate(
    file: UploadFile = File(...),
    scope: str = Form(default="auto"),
    max_chapters: int = Form(default=0),
    top_k: int = Form(default=6),
    chunk_size: int = Form(default=2000),
    overlap: int = Form(default=200),
) -> dict:
    # Validate inputs
    valid_scopes = {"auto", "all", "credit_risk", "market_risk_crr2", "market_risk_crr3", "ccr"}
    if scope not in valid_scopes:
        raise HTTPException(status_code=400, detail=f"Invalid scope. Must be one of: {valid_scopes}")

    suffix = Path(file.filename or "upload.txt").suffix.lower()
    if suffix not in {".pdf", ".txt", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Only .pdf, .txt, and .xlsx files are supported")

    # Save upload to a temp file
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        doc_text = load_document(tmp_path)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to parse document: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    if not doc_text.strip():
        raise HTTPException(status_code=422, detail="Document appears to be empty")

    chunks = chunk_text(doc_text, chunk_size=chunk_size, overlap=overlap)

    # Scope detection
    if scope == "auto":
        scope_tags = detect_scope(doc_text)
    else:
        scope_tags = [scope]

    corpus = _get_corpus()
    chapters = corpus.filter_by_scope(scope_tags)
    if max_chapters and max_chapters > 0:
        chapters = chapters[:max_chapters]

    if not chapters:
        raise HTTPException(status_code=422, detail="No relevant ECB chapters found for the detected scope")

    # Build bank document BM25 index
    bank_index = BM25Index()
    bank_index.add_documents([c.text for c in chunks])

    # Ensure Anthropic API key is present
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY environment variable must be set",
        )

    evaluator = Evaluator(api_key=api_key)
    results = []
    for chapter in chapters:
        result = await evaluator.evaluate_chapter(chapter, bank_index, chunks, top_k=top_k)
        results.append(result)

    total_input, total_output = evaluator.total_tokens
    all_chapters = corpus.chapters
    chapters_skipped = len(all_chapters) - len(chapters)

    report = build_report(
        bank_doc_path=Path(file.filename or "upload"),
        bank_doc_size=len(content),
        bank_chunks_count=len(chunks),
        ecb_json_path=_ECB_JSON,
        scope_tags=scope_tags,
        chapters_evaluated=len(chapters),
        chapters_skipped=chapters_skipped,
        results=results,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
    )

    import json as _json
    return _json.loads(report.to_json())
