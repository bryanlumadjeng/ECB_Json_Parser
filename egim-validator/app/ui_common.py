"""Shared helpers for the Streamlit pages."""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import streamlit as st  # noqa: E402

from egim_validator.runstate import RunPaths, list_runs  # noqa: E402

RUNS_DIR = APP_ROOT / "runs"


def select_run(label: str = "Run") -> RunPaths | None:
    runs = list_runs(RUNS_DIR)
    if not runs:
        st.info("No runs yet — create one on the Home page.")
        return None
    options = {f"{r['run_id']}  ·  {r.get('model_name', '')}  ·  {r.get('stage', '?')}": r["run_id"] for r in runs}
    default = st.session_state.get("selected_run")
    keys = list(options)
    index = next((i for i, k in enumerate(keys) if options[k] == default), 0)
    choice = st.selectbox(label, keys, index=index)
    run_id = options[choice]
    st.session_state["selected_run"] = run_id
    return RunPaths(RUNS_DIR, run_id)
