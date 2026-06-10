"""Stage 1 — guide preprocessing: classify every EGIM paragraph into a checklist row.

Runs once per guide version; the result is cached on disk keyed by the SHA-256 of the
guide JSON, so repeated engagements against the same guide are free.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import llm
from ..config import Config
from ..schemas import GuideParagraph, Requirement, RequirementExtraction, RequirementKind

SYSTEM = """\
You are assisting a bank model validator. You will receive one paragraph of the
ECB guide to internal models (EGIM). Classify it for use in a compliance checklist.

Rules:
- kind = "requirement" when the paragraph imposes an obligation on institutions
  (typically "institutions should/must/are required to ...").
- kind = "expectation" for softer supervisory expectations ("the ECB considers it good
  practice ...", "institutions are encouraged to ...").
- kind = "background" for scope statements, definitions, legal references and narrative
  with nothing an institution must evidence in its model documentation.
- obligations: split compound requirements into atomic, independently checkable items,
  phrased as "The institution ..." statements. Empty for background paragraphs.
- model_types: which internal-model types the paragraph applies to. Use ["general"] when
  it applies to all internal models. Use the specific risk type(s) when the chapter or
  wording targets credit risk (IRB), market risk (IMA) or counterparty credit risk (IMM).
"""


def guide_fingerprint(guide_path: str | Path) -> str:
    return hashlib.sha256(Path(guide_path).read_bytes()).hexdigest()[:16]


def _cache_path(cache_dir: Path, fingerprint: str) -> Path:
    return cache_dir / f"requirements_{fingerprint}.json"


def load_cached_requirements(cache_dir: Path, fingerprint: str) -> list[Requirement] | None:
    path = _cache_path(cache_dir, fingerprint)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Requirement.model_validate(r) for r in data]


def save_requirements(cache_dir: Path, fingerprint: str, requirements: list[Requirement]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in requirements]
    _cache_path(cache_dir, fingerprint).write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _user_content(p: GuideParagraph) -> str:
    return (
        f"Chapter: {p.chapter or '-'}\n"
        f"Section: {p.section or '-'}\n"
        f"Paragraph number: {p.paragraph_number or '-'}\n\n"
        f"Paragraph text:\n{p.text}"
    )


def extract_requirements(
    paragraphs: list[GuideParagraph], config: Config, on_progress=None
) -> list[Requirement]:
    by_ref = {p.ref: p for p in paragraphs}
    requests = [
        llm.structured_request(
            p.ref,
            model=config.extract_model,
            system=SYSTEM,
            user_content=_user_content(p),
            schema_model=RequirementExtraction,
            max_tokens=config.extract_max_tokens,
        )
        for p in paragraphs
    ]
    results = llm.run_structured_batch(
        requests,
        RequirementExtraction,
        poll_seconds=config.batch_poll_seconds,
        on_poll=on_progress,
    )

    requirements: list[Requirement] = []
    for ref, paragraph in by_ref.items():
        parsed, err = results.get(ref, (None, "missing from batch results"))
        if parsed is None:
            # Fail safe: keep the paragraph in the checklist as an unclassified requirement
            # rather than silently dropping a guide paragraph.
            parsed = RequirementExtraction(
                kind=RequirementKind.requirement,
                summary=f"[extraction failed: {err}]",
                obligations=[],
                topics=[],
                model_types=[],
            )
        requirements.append(Requirement(ref=ref, paragraph=paragraph, extraction=parsed))
    requirements.sort(key=lambda r: r.paragraph.id)
    return requirements
