from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.agent.evaluator import EvaluationResult, Evaluator

# Azure OpenAI pricing approximation (GPT-4o as of 2025)
_COST_PER_1K_INPUT = 0.005
_COST_PER_1K_OUTPUT = 0.015


def compute_compliance_score(results: list[EvaluationResult]) -> float:
    applicable = [r for r in results if r.verdict != "not_applicable"]
    if not applicable:
        return 0.0
    score = sum(
        1.0 if r.verdict == "compliant" else 0.5 if r.verdict == "partial" else 0.0
        for r in applicable
    )
    return round(score / len(applicable), 4)


@dataclass
class ComplianceReport:
    report_id: str
    generated_at: str
    bank_document: dict
    ecb_guide: dict
    scope: dict
    summary: dict
    findings: list[dict]
    chapter_evaluations: list[dict]
    token_usage: dict

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        lines: list[str] = []
        s = self.summary

        lines.append("# ECB Supervisory Guide Compliance Report")
        lines.append(f"\n**Generated:** {self.generated_at}")
        lines.append(f"**Document:** {self.bank_document.get('path', 'unknown')}")
        lines.append(f"**Scope:** {', '.join(self.scope.get('tags', []))}")
        lines.append(f"**Chapters evaluated:** {self.scope.get('chapters_evaluated', 0)}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Compliance score | **{round(s['compliance_score'] * 100, 1)}%** |")
        lines.append(f"| Compliant | {s['compliant']} |")
        lines.append(f"| Partial | {s['partial']} |")
        lines.append(f"| Missing | {s['missing']} |")
        lines.append(f"| Not applicable | {s['not_applicable']} |")
        lines.append(f"| Overall verdict | **{s['overall_verdict'].upper()}** |")
        lines.append("")

        # Findings sorted: missing first, then partial
        missing = [f for f in self.findings if f["verdict"] == "missing"]
        partial = [f for f in self.findings if f["verdict"] == "partial"]

        if missing:
            lines.append("## Missing Requirements")
            lines.append("")
            for f in missing:
                lines.append(f"### {f['finding_id']} — {f['ecb_chapter']}")
                lines.append(f"**ECB Paragraphs:** {', '.join(str(i) for i in f['ecb_paragraph_ids'])}")
                lines.append(f"**Requirement:** {f['ecb_requirement_summary']}")
                if f.get("gap_description"):
                    lines.append(f"**Gap:** {f['gap_description']}")
                if f.get("recommendation"):
                    lines.append(f"**Recommendation:** {f['recommendation']}")
                lines.append("")

        if partial:
            lines.append("## Partial Compliance")
            lines.append("")
            for f in partial:
                lines.append(f"### {f['finding_id']} — {f['ecb_chapter']}")
                lines.append(f"**ECB Paragraphs:** {', '.join(str(i) for i in f['ecb_paragraph_ids'])}")
                lines.append(f"**Requirement:** {f['ecb_requirement_summary']}")
                if f.get("gap_description"):
                    lines.append(f"**Gap:** {f['gap_description']}")
                if f.get("recommendation"):
                    lines.append(f"**Recommendation:** {f['recommendation']}")
                if f.get("matched_excerpts"):
                    lines.append("**Evidence found:**")
                    for ex in f["matched_excerpts"][:2]:
                        lines.append(f"> {ex[:300]}")
                lines.append("")

        lines.append("## Token Usage")
        lines.append("")
        tu = self.token_usage
        lines.append(f"- Input tokens: {tu.get('input_tokens', 0):,}")
        lines.append(f"- Output tokens: {tu.get('output_tokens', 0):,}")
        lines.append(f"- Estimated cost: ${tu.get('estimated_cost_usd', 0):.2f}")
        lines.append("")

        return "\n".join(lines)


def build_report(
    bank_doc_path: Path,
    bank_doc_size: int,
    bank_chunks_count: int,
    ecb_json_path: Path,
    scope_tags: list[str],
    chapters_evaluated: int,
    chapters_skipped: int,
    results: list[EvaluationResult],
    total_input_tokens: int,
    total_output_tokens: int,
) -> ComplianceReport:
    now = datetime.now(timezone.utc)
    report_id = f"eval_{now:%Y%m%d_%H%M%S}"

    verdicts = [r.verdict for r in results]
    compliant = verdicts.count("compliant")
    partial = verdicts.count("partial")
    missing = verdicts.count("missing")
    not_applicable = verdicts.count("not_applicable")
    score = compute_compliance_score(results)

    if missing > 0:
        overall = "non_compliant"
    elif partial > 0:
        overall = "partial"
    else:
        overall = "compliant"

    findings: list[dict] = []
    finding_idx = 1
    chapter_evals: list[dict] = []

    for r in results:
        eval_entry: dict = {
            "chapter": r.display_name,
            "zone": r.zone,
            "paragraph_ids": r.paragraph_ids,
            "verdict": r.verdict,
            "confidence": r.confidence,
        }

        if r.verdict in ("missing", "partial"):
            fid = f"F{finding_idx:03d}"
            finding_idx += 1
            finding: dict = {
                "finding_id": fid,
                "ecb_chapter": r.display_name,
                "ecb_zone": r.zone,
                "ecb_paragraph_ids": r.paragraph_ids,
                "verdict": r.verdict,
                "confidence": r.confidence,
                "ecb_requirement_summary": r.ecb_requirement_summary,
                "gap_description": r.gap_description,
                "matched_excerpts": r.matched_excerpts,
                "recommendation": r.recommendation,
            }
            findings.append(finding)
            eval_entry["finding_id"] = fid

        chapter_evals.append(eval_entry)

    estimated_cost = (
        total_input_tokens / 1000 * _COST_PER_1K_INPUT
        + total_output_tokens / 1000 * _COST_PER_1K_OUTPUT
    )

    return ComplianceReport(
        report_id=report_id,
        generated_at=now.isoformat(),
        bank_document={
            "path": str(bank_doc_path),
            "size_bytes": bank_doc_size,
            "chunks": bank_chunks_count,
        },
        ecb_guide={
            "source": str(ecb_json_path),
            "version": "July 2025",
        },
        scope={
            "tags": scope_tags,
            "chapters_evaluated": chapters_evaluated,
            "chapters_skipped": chapters_skipped,
        },
        summary={
            "overall_verdict": overall,
            "compliant": compliant,
            "partial": partial,
            "missing": missing,
            "not_applicable": not_applicable,
            "compliance_score": score,
        },
        findings=findings,
        chapter_evaluations=chapter_evals,
        token_usage={
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "estimated_cost_usd": round(estimated_cost, 4),
        },
    )
