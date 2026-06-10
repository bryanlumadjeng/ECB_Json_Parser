"""Engagement setup: upload inputs, create a run, launch the pipeline."""

import subprocess
import sys

import streamlit as st
import yaml
from ui_common import APP_ROOT, RUNS_DIR

from egim_validator.runstate import RunPaths, list_runs, new_run_id, update_state

st.set_page_config(page_title="EGIM Validator", layout="wide")
st.title("EGIM Validator")
st.caption(
    "Validates model documentation against the ECB guide to internal models. "
    "Agent verdicts are drafts for the validator — review and override in the Review Workspace."
)

st.header("New validation run")

guide_file = st.file_uploader(
    "Parsed ECB guide (JSON from ecb_pdf_to_json.py)", type=["json"], key="guide"
)
doc_file = st.file_uploader(
    "Model documentation (.json with sections, or Markdown)", type=["json", "md", "markdown", "txt"], key="doc"
)
profile_file = st.file_uploader("Model profile (YAML)", type=["yaml", "yml"], key="profile")
config_file = st.file_uploader("Pipeline config override (optional YAML)", type=["yaml", "yml"], key="config")

if st.button("Create run and start pipeline", type="primary", disabled=not (guide_file and doc_file and profile_file)):
    profile_bytes = profile_file.getvalue()
    profile_data = yaml.safe_load(profile_bytes.decode("utf-8")) or {}
    model_name = profile_data.get("model_name", "run")

    paths = RunPaths(RUNS_DIR, new_run_id(model_name)).ensure()
    (paths.inputs / "guide_paragraphs.json").write_bytes(guide_file.getvalue())
    doc_suffix = "." + doc_file.name.rsplit(".", 1)[-1].lower()
    (paths.inputs / f"model_doc{doc_suffix}").write_bytes(doc_file.getvalue())
    (paths.inputs / "model_profile.yaml").write_bytes(profile_bytes)
    if config_file is not None:
        (paths.inputs / "config.yaml").write_bytes(config_file.getvalue())
    update_state(paths, run_id=paths.run_id, stage="created", model_name=model_name)

    log = open(paths.log, "ab")
    subprocess.Popen(
        [sys.executable, str(APP_ROOT / "runner.py"), "--runs-dir", str(RUNS_DIR), "--run-id", paths.run_id],
        cwd=APP_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # survives Streamlit reruns and page refreshes
    )
    st.session_state["selected_run"] = paths.run_id
    st.success(f"Run **{paths.run_id}** started — follow it on the Run Monitor page.")

st.header("Existing runs")
runs = list_runs(RUNS_DIR)
if runs:
    st.dataframe(
        [
            {
                "run_id": r["run_id"],
                "model": r.get("model_name", ""),
                "stage": r.get("stage", ""),
                "assessed": r.get("assessed", 0),
                "needs_review": r.get("needs_review", ""),
                "updated": r.get("updated_at", ""),
            }
            for r in runs
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No runs yet.")
