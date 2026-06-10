#!/usr/bin/env python3
"""Headless pipeline runner.

Launched by the Streamlit UI as a background subprocess, or directly:

    python runner.py --runs-dir runs --run-id 20260610-...   # resume an existing run
    python runner.py --runs-dir runs \\
        --guide ../guide_paragraphs.json \\
        --model-doc sample_data/model_doc.sample.json \\
        --profile sample_data/model_profile.sample.yaml      # create + run

Progress and results are written to runs/<run_id>/ (see egim_validator.runstate).
Stages are idempotent: re-running skips work whose outputs already exist.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import traceback
from pathlib import Path

from egim_validator.config import Config, load_config
from egim_validator.ingest import load_guide, load_model_doc, load_profile
from egim_validator.runstate import (
    RunPaths,
    load_assessments,
    new_run_id,
    read_state,
    update_state,
    write_assessment,
)
from egim_validator.schemas import (
    Applicability,
    AssessmentRecord,
    Confidence,
    CoverageStatus,
    EvidenceRecord,
    Requirement,
)
from egim_validator.stages import assess as assess_stage
from egim_validator.stages import extract_requirements as extract_stage
from egim_validator.stages import report as report_stage
from egim_validator.stages import review as review_stage
from egim_validator.stages import triage as triage_stage
from egim_validator.stages import verify as verify_stage


def setup_run(args) -> RunPaths:
    if args.run_id:
        paths = RunPaths(args.runs_dir, args.run_id).ensure()
        if not (paths.inputs / "model_profile.yaml").exists():
            sys.exit(f"run {args.run_id} has no inputs/ — create runs via the UI or pass --guide/--model-doc/--profile")
        return paths

    for flag in ("guide", "model_doc", "profile"):
        if getattr(args, flag) is None:
            sys.exit(f"--{flag.replace('_', '-')} is required when creating a new run")

    profile = load_profile(args.profile)
    paths = RunPaths(args.runs_dir, new_run_id(profile.model_name)).ensure()
    shutil.copy(args.guide, paths.inputs / "guide_paragraphs.json")
    model_doc_src = Path(args.model_doc)
    shutil.copy(model_doc_src, paths.inputs / f"model_doc{model_doc_src.suffix}")
    shutil.copy(args.profile, paths.inputs / "model_profile.yaml")
    if args.config:
        shutil.copy(args.config, paths.inputs / "config.yaml")
    update_state(paths, run_id=paths.run_id, stage="created", model_name=profile.model_name)
    return paths


def find_model_doc(paths: RunPaths) -> Path:
    for f in paths.inputs.iterdir():
        if f.stem == "model_doc":
            return f
    sys.exit("no model_doc input found in run directory")


def run_pipeline(paths: RunPaths) -> None:
    config_path = paths.inputs / "config.yaml"
    config: Config = load_config(config_path if config_path.exists() else None)

    guide_path = paths.inputs / "guide_paragraphs.json"
    paragraphs = load_guide(guide_path)
    doc = load_model_doc(find_model_doc(paths))
    profile = load_profile(paths.inputs / "model_profile.yaml")

    def poll_cb(stage: str):
        def cb(batch):
            counts = batch.request_counts
            update_state(
                paths,
                stage=stage,
                batch_id=batch.id,
                batch_status=batch.processing_status,
                batch_processing=counts.processing,
                batch_succeeded=counts.succeeded,
                batch_errored=counts.errored,
            )
        return cb

    # ---- Stage 1: guide preprocessing (cached per guide version) -------------------
    update_state(paths, stage="extract", total_paragraphs=len(paragraphs))
    cache_dir = Path(__file__).parent / "data" / "requirements_cache"
    fingerprint = extract_stage.guide_fingerprint(guide_path)
    requirements = extract_stage.load_cached_requirements(cache_dir, fingerprint)
    if requirements is None:
        requirements = extract_stage.extract_requirements(paragraphs, config, on_progress=poll_cb("extract"))
        extract_stage.save_requirements(cache_dir, fingerprint, requirements)

    # ---- Stage 2: applicability triage ---------------------------------------------
    update_state(paths, stage="triage", total_requirements=len(requirements))
    applicability = triage_stage.triage(requirements, profile, config, on_progress=poll_cb("triage"))

    existing = load_assessments(paths)
    records: dict[str, AssessmentRecord] = dict(existing)
    for req in requirements:
        if req.ref in records:
            continue
        records[req.ref] = _base_record(req, applicability[req.ref])
        if not applicability[req.ref].applicable:
            write_assessment(paths, records[req.ref])

    # ---- Stage 3: core assessment (only applicable, not yet assessed) --------------
    todo = [
        req for req in requirements
        if applicability[req.ref].applicable and records[req.ref].status is None
    ]
    update_state(paths, stage="assess", to_assess=len(todo), assessed=len(existing))
    if todo:
        results = assess_stage.assess(
            todo, doc, profile, config,
            on_progress=poll_cb("assess"),
            on_submit=lambda bid: update_state(paths, stage="assess", batch_id=bid),
            batch_id=read_state(paths).get("resume_batch_id"),
        )
        for req in todo:
            record = records[req.ref]
            parsed, err = results.get(req.ref, (None, "missing from batch results"))
            if parsed is None:
                record.status = CoverageStatus.unclear
                record.rationale = f"[assessment failed: {err}]"
                record.confidence = Confidence.low
                record.needs_review = True
                record.flags.append("assessment request failed")
            else:
                record.status = parsed.status
                record.evidence = [
                    EvidenceRecord(quote=e.quote, section_id=e.section_id)
                    for e in parsed.evidence
                ]
                record.rationale = parsed.rationale
                record.confidence = parsed.confidence
                record.open_questions = parsed.open_questions

            # ---- Stage 4: citation verification, immediately per record ------------
            record = verify_stage.verify_record(record, doc, config.quote_match_threshold)
            if config.low_confidence_flags and record.confidence == Confidence.low:
                record.needs_review = True
                record.flags.append("low confidence")
            write_assessment(paths, record)

    # ---- Stage 5: adversarial review of 'covered' verdicts -------------------------
    if config.run_adversarial_review:
        update_state(paths, stage="review")
        reviewed = review_stage.adversarial_review(
            list(records.values()), doc, config, on_progress=poll_cb("review")
        )
        for record in reviewed:
            write_assessment(paths, record)

    # ---- Stage 6: exports -----------------------------------------------------------
    update_state(paths, stage="report")
    from egim_validator.runstate import load_overrides

    rows = report_stage.build_rows(list(load_assessments(paths).values()), load_overrides(paths))
    report_stage.to_excel(rows, paths.exports / "traceability_matrix.xlsx")
    report_stage.to_json(rows, paths.exports / "traceability_matrix.json")
    report_stage.to_markdown_summary(rows, paths.exports / "summary.md", profile.model_name)

    needs_review = sum(1 for r in load_assessments(paths).values() if r.needs_review)
    update_state(paths, stage="done", needs_review=needs_review)


def _base_record(req: Requirement, applicability: Applicability) -> AssessmentRecord:
    return AssessmentRecord(
        ref=req.ref,
        chapter=req.paragraph.chapter,
        section=req.paragraph.section,
        paragraph_number=req.paragraph.paragraph_number,
        paragraph_text=req.paragraph.text,
        kind=req.extraction.kind,
        obligations=req.extraction.obligations,
        topics=req.extraction.topics,
        applicability=applicability,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--run-id", help="resume an existing run")
    parser.add_argument("--guide", help="parsed guide JSON (output of ecb_pdf_to_json.py)")
    parser.add_argument("--model-doc", help="model documentation (.json or .md)")
    parser.add_argument("--profile", help="model_profile.yaml")
    parser.add_argument("--config", help="optional config.yaml overriding defaults")
    args = parser.parse_args()

    paths = setup_run(args)
    print(f"run: {paths.run_id}")
    try:
        run_pipeline(paths)
        print("done")
    except Exception:
        update_state(paths, stage="error", error=traceback.format_exc(limit=5))
        raise


if __name__ == "__main__":
    main()
