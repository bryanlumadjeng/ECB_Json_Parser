"""Stage 4 — citation verification (programmatic, no LLM).

Every evidence quote is matched back into the model documentation. This is the
anti-hallucination gate: an assessment whose quotes cannot be found is flagged and its
verdict is not trusted until a human looks at it.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..schemas import AssessmentRecord, EvidenceRecord, ModelDoc


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def match_quote(quote: str, section_text: str, threshold: float = 0.85) -> tuple[bool, float]:
    """Return (verified, score). Exact normalized substring scores 1.0; otherwise the
    best fuzzy ratio over sliding windows of the section text."""
    nq, nt = _normalize(quote), _normalize(section_text)
    if not nq or not nt:
        return False, 0.0
    if nq in nt:
        return True, 1.0

    window = len(nq) + max(10, len(nq) // 5)
    step = max(1, len(nq) // 4)
    best = 0.0
    for start in range(0, max(1, len(nt) - len(nq) + 1), step):
        ratio = SequenceMatcher(None, nq, nt[start : start + window]).ratio()
        if ratio > best:
            best = ratio
            if best >= 0.999:
                break
    return best >= threshold, round(best, 3)


def verify_record(record: AssessmentRecord, doc: ModelDoc, threshold: float = 0.85) -> AssessmentRecord:
    sections = doc.section_by_id()
    full_text = "\n".join(s.text for s in doc.sections)
    verified_evidence: list[EvidenceRecord] = []

    for ev in record.evidence:
        section = sections.get(ev.section_id)
        if section is not None:
            ok, score = match_quote(ev.quote, section.text, threshold)
        else:
            ok, score = False, 0.0
        if not ok:
            # Quote not in the cited section — check whether it exists elsewhere
            # (wrong section id is a lesser offence than a fabricated quote).
            ok_anywhere, score_anywhere = match_quote(ev.quote, full_text, threshold)
            if ok_anywhere:
                record.flags.append(f"quote found but not in cited section '{ev.section_id}'")
                ok, score = True, score_anywhere
        verified_evidence.append(
            EvidenceRecord(quote=ev.quote, section_id=ev.section_id, verified=ok, match_score=score)
        )

    record.evidence = verified_evidence
    failed = [e for e in verified_evidence if e.verified is False]
    if failed:
        record.needs_review = True
        record.flags.append(f"{len(failed)} unverifiable quote(s) — verdict not trusted")
    return record
