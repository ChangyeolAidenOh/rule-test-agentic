"""Tab 5: Documentation - auto-generated developer review document."""

import streamlit as st


def render():
    st.subheader("Documentation")

    if "pipeline_result" not in st.session_state:
        st.info("Run the pipeline in the 'Rule Input' tab first.")
        return

    result = st.session_state["pipeline_result"]
    documentation = result.get("documentation", "")

    if documentation:
        st.warning(
            "This document is auto-generated. All code and tests require "
            "developer review and approval before deployment."
        )
        st.markdown(documentation)
    else:
        st.warning("No documentation was generated.")
