"""Load the three pipeline inputs: parsed ECB guide, model documentation, model profile.

The guide JSON is the unmodified output of ``ecb_pdf_to_json.py`` (the ECB_Json_Parser
project) — that parser is run once per guide version and is not part of this app.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .schemas import DocSection, GuideParagraph, ModelDoc, ModelProfile


def load_guide(path: str | Path) -> list[GuideParagraph]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    paragraphs = data["paragraphs"] if isinstance(data, dict) else data
    return [GuideParagraph.model_validate(p) for p in paragraphs]


def load_model_doc(path: str | Path) -> ModelDoc:
    path = Path(path)
    if path.suffix.lower() in (".md", ".markdown", ".txt"):
        return _model_doc_from_markdown(path.read_text(encoding="utf-8"), title=path.stem)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"sections": data}
    sections = []
    for i, s in enumerate(data.get("sections", []), start=1):
        sections.append(
            DocSection(
                id=str(s.get("id") or f"S{i:03d}"),
                heading=str(s.get("heading") or s.get("title") or f"Section {i}"),
                text=str(s.get("text") or s.get("content") or ""),
            )
        )
    return ModelDoc(title=data.get("title", path.stem), sections=sections)


_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)


def _model_doc_from_markdown(text: str, title: str = "Model documentation") -> ModelDoc:
    """Split a Markdown document into sections at heading lines (#, ##, ###, ####)."""
    matches = list(_HEADING_RE.finditer(text))
    sections: list[DocSection] = []
    if not matches:
        sections.append(DocSection(id="S001", heading=title, text=text.strip()))
        return ModelDoc(title=title, sections=sections)

    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(DocSection(id="S000", heading="Preamble", text=preamble))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end].strip()
        sections.append(DocSection(id=f"S{i + 1:03d}", heading=m.group(2), text=body))
    return ModelDoc(title=title, sections=sections)


def load_profile(path: str | Path) -> ModelProfile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return ModelProfile.model_validate(data)


def render_model_doc(doc: ModelDoc) -> str:
    """Render the documentation as the XML-ish block placed in the cached system prefix."""
    parts = [f"<model_documentation title={doc.title!r}>"]
    for s in doc.sections:
        parts.append(f'<section id="{s.id}" heading="{s.heading}">')
        parts.append(s.text)
        parts.append("</section>")
    parts.append("</model_documentation>")
    return "\n".join(parts)
