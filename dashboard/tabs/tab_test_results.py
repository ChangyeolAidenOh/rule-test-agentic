"""Tab 3: Test Results - pass/fail status and self-correction history."""

import streamlit as st
import pandas as pd


def render():
    st.subheader("Test Results")

    if "pipeline_result" not in st.session_state:
        st.info("Run the pipeline in the 'Rule Input' tab first.")
        return

    result = st.session_state["pipeline_result"]
    metrics = st.session_state["pipeline_metrics"]

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Tests", metrics["total_tests"])
    c2.metric("Passed", metrics["passed_tests"])
    c3.metric("Pass Rate", f"{metrics['test_pass_rate']:.0%}")
    c4.metric("Self-fix Attempts", metrics["self_fix_count"])

    st.divider()

    # Test results table
    test_results = result.get("test_results", [])
    if test_results:
        st.markdown("**Individual Test Results**")

        rows = []
        for r in test_results:
            test_id = r.get("test_id", "unknown")
            # Determine category from test name
            category = "other"
            for cat in ["normal", "boundary", "exception", "error"]:
                if cat in test_id.lower():
                    category = cat
                    break

            rows.append({
                "Test": test_id,
                "Category": category.capitalize(),
                "Status": "PASS" if r.get("passed") else "FAIL",
                "Error": r.get("error_message", "")[:100] if not r.get("passed") else "",
            })

        df = pd.DataFrame(rows)

        # Color-code status
        def highlight_status(val):
            if val == "PASS":
                return "background-color: #d4edda; color: #155724"
            elif val == "FAIL":
                return "background-color: #f8d7da; color: #721c24"
            return ""

        styled = df.style.map(highlight_status, subset=["Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Category breakdown
        st.markdown("**Coverage by Category**")
        coverage = metrics.get("test_coverage_by_category", {})
        if coverage:
            cov_df = pd.DataFrame([
                {"Category": k.capitalize(), "Count": v}
                for k, v in coverage.items()
            ])
            st.bar_chart(cov_df.set_index("Category"), height=250)
    else:
        st.warning("No test results available.")

    # Test code
    test_code = result.get("test_code", "")
    if test_code:
        with st.expander("Generated Test Code", expanded=False):
            st.code(test_code, language="python", line_numbers=True)

    # Self-correction history
    fix_history = result.get("fix_history", [])
    if fix_history:
        st.divider()
        st.markdown("**Self-Correction History**")
        for h in fix_history:
            with st.expander(f"Attempt {h.get('attempt', '?')}"):
                st.markdown("**Error:**")
                st.code(h.get("error", ""), language="text")
                if h.get("previous_code"):
                    st.markdown("**Previous Code (first 30 lines):**")
                    lines = h["previous_code"].split("\n")[:30]
                    st.code("\n".join(lines), language="python")
    elif metrics["self_fix_count"] == 0:
        st.success("No self-correction needed. Code passed all tests on first attempt.")
