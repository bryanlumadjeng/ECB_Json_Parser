"""Generate and download exports. Validator overrides are merged over agent verdicts."""

import streamlit as st
from ui_common import select_run

from egim_validator.ingest import load_profile
from egim_validator.runstate import load_assessments, load_overrides
from egim_validator.stages import report

st.set_page_config(page_title="Export", layout="wide")
st.title("Export")

paths = select_run()
if paths is None:
    st.stop()

records = load_assessments(paths)
if not records:
    st.info("No assessments yet for this run.")
    st.stop()

overrides = load_overrides(paths)
profile_path = paths.inputs / "model_profile.yaml"
model_name = load_profile(profile_path).model_name if profile_path.exists() else paths.run_id

rows = report.build_rows(list(records.values()), overrides)
st.caption(f"{len(rows)} rows · {len(overrides)} validator decisions merged")

if st.button("Generate exports", type="primary"):
    xlsx = report.to_excel(rows, paths.exports / "traceability_matrix.xlsx")
    js = report.to_json(rows, paths.exports / "traceability_matrix.json")
    md = report.to_markdown_summary(rows, paths.exports / "summary.md", model_name)
    st.success("Exports generated.")

for name, mime in [
    ("traceability_matrix.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("traceability_matrix.json", "application/json"),
    ("summary.md", "text/markdown"),
]:
    f = paths.exports / name
    if f.exists():
        st.download_button(f"Download {name}", f.read_bytes(), file_name=f"{paths.run_id}_{name}", mime=mime)

summary_file = paths.exports / "summary.md"
if summary_file.exists():
    st.divider()
    st.markdown(summary_file.read_text(encoding="utf-8"))
