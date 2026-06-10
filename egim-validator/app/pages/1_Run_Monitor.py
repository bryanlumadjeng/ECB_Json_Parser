"""Live view of a running (or finished) pipeline. Polls the run directory."""

import streamlit as st
from ui_common import select_run

from egim_validator.runstate import STAGES, load_assessments, read_state

st.set_page_config(page_title="Run Monitor", layout="wide")
st.title("Run Monitor")

paths = select_run()
if paths is None:
    st.stop()


@st.fragment(run_every="3s")
def monitor():
    state = read_state(paths)
    stage = state.get("stage", "?")

    cols = st.columns(4)
    cols[0].metric("Stage", stage)
    cols[1].metric("To assess", state.get("to_assess", "—"))
    records = load_assessments(paths)
    assessed = sum(1 for r in records.values() if r.status is not None)
    cols[2].metric("Assessed", assessed)
    cols[3].metric("Needs review", sum(1 for r in records.values() if r.needs_review))

    if stage in STAGES:
        st.progress((STAGES.index(stage) + 1) / (len(STAGES) + 1), text=f"Pipeline stage: {stage}")
    elif stage == "done":
        st.progress(1.0, text="Pipeline finished")
    elif stage == "error":
        st.error("Pipeline failed:\n\n```\n" + state.get("error", "unknown") + "\n```")

    if state.get("batch_id"):
        st.caption(
            f"Anthropic batch `{state['batch_id']}` — {state.get('batch_status', '')} · "
            f"processing {state.get('batch_processing', 0)} · "
            f"succeeded {state.get('batch_succeeded', 0)} · "
            f"errored {state.get('batch_errored', 0)}"
        )

    if records:
        st.subheader("Per-paragraph status")
        st.dataframe(
            [
                {
                    "ref": r.ref,
                    "chapter": r.chapter,
                    "applicable": r.applicability.applicable,
                    "status": r.status.value if r.status else "",
                    "confidence": r.confidence.value if r.confidence else "",
                    "verified": r.all_evidence_verified,
                    "needs_review": r.needs_review,
                    "flags": "; ".join(r.flags),
                }
                for r in sorted(records.values(), key=lambda x: x.ref)
            ],
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    if paths.log.exists():
        with st.expander("Runner log (tail)"):
            st.code("\n".join(paths.log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))


monitor()
