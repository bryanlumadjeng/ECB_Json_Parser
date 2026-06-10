"""Review workspace: filter the matrix, inspect evidence side-by-side, override verdicts.

Overrides are written to overrides.json — agent output is never mutated, preserving the
audit trail of machine verdict vs human decision.
"""

import pandas as pd
import streamlit as st
from ui_common import select_run

from egim_validator.ingest import load_model_doc
from egim_validator.runstate import load_assessments, load_overrides, save_override
from egim_validator.schemas import CoverageStatus, Override, ReviewState, final_status

st.set_page_config(page_title="Review Workspace", layout="wide")
st.title("Review Workspace")

paths = select_run()
if paths is None:
    st.stop()

records = load_assessments(paths)
overrides = load_overrides(paths)
if not records:
    st.info("No assessments yet for this run.")
    st.stop()


@st.cache_resource
def get_doc(run_root: str):
    inputs = paths.inputs
    doc_file = next((f for f in inputs.iterdir() if f.stem == "model_doc"), None)
    return load_model_doc(doc_file) if doc_file else None


doc = get_doc(str(paths.root))
sections = doc.section_by_id() if doc else {}

# ----------------------------------------------------------------------------- filters
f1, f2, f3, f4 = st.columns(4)
status_filter = f1.multiselect("Agent status", [s.value for s in CoverageStatus])
chapter_filter = f2.multiselect("Chapter", sorted({r.chapter or "" for r in records.values()}))
review_filter = f3.multiselect("Review state", [s.value for s in ReviewState])
only_flagged = f4.checkbox("Needs review only")

rows = []
for r in sorted(records.values(), key=lambda x: x.ref):
    ov = overrides.get(r.ref)
    review_state = ov.review_state.value if ov else ReviewState.pending.value
    if status_filter and (r.status.value if r.status else "") not in status_filter:
        continue
    if chapter_filter and (r.chapter or "") not in chapter_filter:
        continue
    if review_filter and review_state not in review_filter:
        continue
    if only_flagged and not r.needs_review:
        continue
    fs = final_status(r, ov)
    rows.append(
        {
            "ref": r.ref,
            "chapter": r.chapter,
            "section": r.section,
            "agent status": r.status.value if r.status else "",
            "final status": fs.value if fs else "",
            "review": review_state,
            "conf": r.confidence.value if r.confidence else "",
            "verified": r.all_evidence_verified,
            "needs_review": r.needs_review,
        }
    )

st.caption(f"{len(rows)} of {len(records)} paragraphs shown — select a row to review it.")
event = st.dataframe(
    pd.DataFrame(rows),
    use_container_width=True,
    hide_index=True,
    height=320,
    on_select="rerun",
    selection_mode="single-row",
)

selected_ref = None
if event.selection.rows:
    selected_ref = rows[event.selection.rows[0]]["ref"]

if selected_ref is None:
    st.stop()

record = records[selected_ref]
override = overrides.get(selected_ref)

st.divider()
left, right = st.columns(2, gap="large")

with left:
    st.subheader(f"{record.ref} — ECB guide")
    st.caption(f"{record.chapter or ''} / {record.section or ''} · para {record.paragraph_number or '-'}")
    st.markdown(record.paragraph_text)
    if record.obligations:
        st.markdown("**Obligations**")
        for o in record.obligations:
            st.markdown(f"- {o}")
    st.markdown("**Agent verdict**")
    st.markdown(
        f"Status: `{record.status.value if record.status else '—'}` · "
        f"confidence: `{record.confidence.value if record.confidence else '—'}`"
    )
    st.markdown(record.rationale or "_no rationale_")
    if record.review_challenge:
        icon = "✅" if record.review_upheld else "⚠️"
        st.markdown(f"**Adversarial review** {icon}: {record.review_challenge}")
    if record.open_questions:
        st.markdown("**Open questions for the model owner**")
        for q in record.open_questions:
            st.markdown(f"- {q}")
    if record.flags:
        st.warning("; ".join(record.flags))

with right:
    st.subheader("Evidence in model documentation")
    if not record.evidence:
        st.info("No evidence cited.")
    for ev in record.evidence:
        badge = "✅" if ev.verified else ("❌" if ev.verified is False else "·")
        score = f" (match {ev.match_score})" if ev.match_score is not None else ""
        st.markdown(f"{badge} **[{ev.section_id}]**{score}")
        section = sections.get(ev.section_id)
        if section is None:
            st.error(f"Cited section '{ev.section_id}' not found in the documentation.")
            st.markdown(f"> {ev.quote}")
            continue
        text = section.text
        if ev.quote in text:
            # highlight the quote in context
            text = text.replace(ev.quote, f" **:orange[{ev.quote}]** ", 1)
            with st.expander(f"{section.heading}", expanded=True):
                st.markdown(text)
        else:
            st.markdown(f"> {ev.quote}")
            with st.expander(f"{section.heading} (quote not exact — fuzzy match)"):
                st.markdown(text)

st.divider()
st.subheader("Validator decision")
c1, c2 = st.columns(2)
status_options = ["(keep agent status)"] + [s.value for s in CoverageStatus]
current_status = override.status.value if override and override.status else "(keep agent status)"
new_status = c1.selectbox("Override status", status_options, index=status_options.index(current_status))
current_review = override.review_state if override else ReviewState.pending
new_review = c2.radio(
    "Review state",
    [s.value for s in ReviewState],
    index=[s.value for s in ReviewState].index(current_review.value),
    horizontal=True,
)
notes = st.text_area("Notes", value=override.notes if override else "", height=100)

if st.button("Save decision", type="primary"):
    save_override(
        paths,
        Override(
            ref=selected_ref,
            status=None if new_status == "(keep agent status)" else CoverageStatus(new_status),
            review_state=ReviewState(new_review),
            notes=notes,
        ),
    )
    st.success(f"Saved decision for {selected_ref}.")
    st.rerun()
