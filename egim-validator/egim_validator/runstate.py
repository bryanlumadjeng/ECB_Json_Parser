"""Run directory: the contract between the headless pipeline and the Streamlit UI.

The pipeline never talks to the UI directly. Both sides share ``runs/<run_id>/``:

    runs/<run_id>/
        state.json              pipeline-owned: stage, counts, batch ids, errors
        inputs/                 copies of guide / model_doc / profile / config
        assessments/<ref>.json  one record per assessed paragraph (written as they land)
        overrides.json          UI-owned: validator decisions, never touched by pipeline
        exports/                generated Excel / JSON / Markdown
        runner.log              pipeline stdout/stderr

All writes are atomic (tmp + os.replace), so the UI can poll at any moment.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schemas import AssessmentRecord, Override

STAGES = ["extract", "triage", "assess", "verify", "review", "report"]


class RunPaths:
    def __init__(self, runs_dir: str | Path, run_id: str):
        self.run_id = run_id
        self.root = Path(runs_dir) / run_id
        self.state = self.root / "state.json"
        self.inputs = self.root / "inputs"
        self.assessments = self.root / "assessments"
        self.overrides = self.root / "overrides.json"
        self.exports = self.root / "exports"
        self.log = self.root / "runner.log"

    def ensure(self) -> "RunPaths":
        for d in (self.root, self.inputs, self.assessments, self.exports):
            d.mkdir(parents=True, exist_ok=True)
        return self


def new_run_id(model_name: str = "run") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model_name.lower()).strip("-")[:30] or "run"
    return f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{slug}"


def _atomic_write(path: Path, payload: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def read_state(paths: RunPaths) -> dict:
    if not paths.state.exists():
        return {}
    try:
        return json.loads(paths.state.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}  # caught mid-replace on some filesystems; next poll wins


def update_state(paths: RunPaths, **updates) -> dict:
    state = read_state(paths)
    state.update(updates)
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _atomic_write(paths.state, json.dumps(state, ensure_ascii=False, indent=1))
    return state


def write_assessment(paths: RunPaths, record: AssessmentRecord) -> None:
    _atomic_write(
        paths.assessments / f"{record.ref}.json",
        record.model_dump_json(indent=1),
    )


def load_assessments(paths: RunPaths) -> dict[str, AssessmentRecord]:
    out: dict[str, AssessmentRecord] = {}
    if not paths.assessments.exists():
        return out
    for f in sorted(paths.assessments.glob("*.json")):
        try:
            record = AssessmentRecord.model_validate_json(f.read_text(encoding="utf-8"))
            out[record.ref] = record
        except Exception:
            continue  # partially written file; next poll wins
    return out


def load_overrides(paths: RunPaths) -> dict[str, Override]:
    if not paths.overrides.exists():
        return {}
    data = json.loads(paths.overrides.read_text(encoding="utf-8"))
    return {ref: Override.model_validate(o) for ref, o in data.items()}


def save_override(paths: RunPaths, override: Override) -> None:
    overrides = load_overrides(paths)
    overrides[override.ref] = override
    _atomic_write(
        paths.overrides,
        json.dumps({r: o.model_dump(mode="json") for r, o in overrides.items()}, ensure_ascii=False, indent=1),
    )


def list_runs(runs_dir: str | Path) -> list[dict]:
    runs_dir = Path(runs_dir)
    if not runs_dir.exists():
        return []
    out = []
    for d in sorted(runs_dir.iterdir(), reverse=True):
        if d.is_dir() and (d / "state.json").exists():
            paths = RunPaths(runs_dir, d.name)
            state = read_state(paths)
            state["run_id"] = d.name
            state["assessed"] = len(list(paths.assessments.glob("*.json"))) if paths.assessments.exists() else 0
            out.append(state)
    return out
