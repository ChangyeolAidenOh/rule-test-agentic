"""Tab 2: Generated Code - display with syntax highlighting."""

import json
import streamlit as st


def render():
    st.subheader("Generated Code")

    if "pipeline_result" not in st.session_state:
        st.info("Run the pipeline in the 'Rule Input' tab first.")
        return

    result = st.session_state["pipeline_result"]

    # Rule spec
    rule_spec = result.get("rule_spec", {})
    if rule_spec:
        with st.expander("Structured Rule Specification (JSON)", expanded=False):
            st.json(rule_spec)

    # Generated code
    code = result.get("generated_code", "")
    if code:
        st.markdown("**Python Code Draft**")
        st.markdown(
            "> This code is auto-generated and requires developer review "
            "before deployment."
        )

        edit_mode = st.toggle("Edit mode", value=False)

        if edit_mode:
            edited_code = st.text_area(
                "Edit code below:",
                value=code,
                height=500,
                key="code_editor",
            )
            if edited_code != code:
                st.session_state["pipeline_result"]["generated_code"] = edited_code
                st.success("Code updated in session. Re-run tests from Rule Input tab to validate.")
        else:
            st.code(code, language="python", line_numbers=True)

        # Code stats
        lines = code.strip().split("\n")
        functions = [l.strip() for l in lines if l.strip().startswith("def ")]
        classes = [l.strip() for l in lines if l.strip().startswith("class ")]
        constants = [
            l.strip() for l in lines
            if "=" in l and l.strip()[0].isupper() and not l.strip().startswith(("def", "class", "#", "\"", "'"))
        ]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Lines", len(lines))
        c2.metric("Functions", len(functions))
        c3.metric("Classes", len(classes))
        c4.metric("Constants", len(constants))

        if functions:
            with st.expander("Function List"):
                for f in functions:
                    st.code(f, language="python")
    else:
        st.warning("No code was generated.")
