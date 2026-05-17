"""Tab 6: Evaluation - complexity-based performance comparison."""

import json
import os

import plotly.graph_objects as go
import streamlit as st
import pandas as pd


RESULTS_DIR = "results"
SUMMARY_FILE = os.path.join(RESULTS_DIR, "evaluation_summary.json")

COMPLEXITY_ORDER = ["simple", "medium", "complex", "hard"]
COMPLEXITY_COLORS = {
    "simple": "#28a745",
    "medium": "#ffc107",
    "complex": "#fd7e14",
    "hard": "#dc3545",
}


def _load_summary() -> list[dict]:
    """Load evaluation summary from file."""
    if not os.path.exists(SUMMARY_FILE):
        return []
    with open(SUMMARY_FILE) as f:
        return json.load(f)


def render():
    st.subheader("Evaluation Dashboard")
    st.markdown(
        "Performance comparison across 5 business rule scenarios by complexity level."
    )

    data = _load_summary()
    if not data:
        st.warning(
            f"No evaluation data found. Run `python main.py eval` first "
            f"to generate `{SUMMARY_FILE}`."
        )
        return

    # Sort by complexity order
    data.sort(key=lambda x: COMPLEXITY_ORDER.index(x.get("complexity", "simple")))

    # Summary table
    st.markdown("**Results Overview**")
    rows = []
    for d in data:
        fidelity = d.get("fidelity_score", 0.0)
        rows.append({
            "Scenario": d["scenario_id"],
            "Complexity": d["complexity"].capitalize(),
            "Tests": f"{d['passed_tests']}/{d['total_tests']}",
            "Pass Rate": f"{d['test_pass_rate']:.0%}",
            "Fidelity": f"{fidelity:.0%}",
            "1st Pass": "Yes" if d["first_pass_success"] else "No",
            "Self-fix": d["self_fix_count"],
            "Flags": d["total_flags"],
            "Time (s)": d.get("elapsed_seconds", "N/A"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Test pass rate by complexity
        fig = go.Figure()
        for d in data:
            color = COMPLEXITY_COLORS.get(d["complexity"], "#999")
            fig.add_trace(go.Bar(
                x=[d["scenario_id"]],
                y=[d["test_pass_rate"] * 100],
                name=f"{d['scenario_id']} ({d['complexity']})",
                marker_color=color,
                text=[f"{d['test_pass_rate']:.0%}"],
                textposition="outside",
            ))
        fig.update_layout(
            title="Test Pass Rate by Scenario",
            yaxis_title="Pass Rate (%)",
            yaxis_range=[0, 110],
            showlegend=False,
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Execution time by complexity
        fig2 = go.Figure()
        for d in data:
            color = COMPLEXITY_COLORS.get(d["complexity"], "#999")
            elapsed = d.get("elapsed_seconds", 0)
            fig2.add_trace(go.Bar(
                x=[d["scenario_id"]],
                y=[elapsed],
                name=f"{d['scenario_id']}",
                marker_color=color,
                text=[f"{elapsed:.0f}s"],
                textposition="outside",
            ))
        fig2.update_layout(
            title="Execution Time by Scenario",
            yaxis_title="Seconds",
            showlegend=False,
            height=350,
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Business Rule Fidelity
    st.markdown("**Business Rule Fidelity**")
    st.markdown(
        '*"Tests passing" ≠ "Logic is correct"* — '
        "Fidelity measures whether ALL conditions from the rule spec are correctly implemented."
    )
    fig_fid = go.Figure()
    for d in data:
        color = COMPLEXITY_COLORS.get(d["complexity"], "#999")
        fid = d.get("fidelity_score", 0.0) * 100
        fig_fid.add_trace(go.Bar(
            x=[d["scenario_id"]],
            y=[fid],
            name=f"{d['scenario_id']}",
            marker_color=color,
            text=[f"{fid:.0f}%"],
            textposition="outside",
        ))
    fig_fid.update_layout(
        title="Business Rule Fidelity by Scenario",
        yaxis_title="Fidelity (%)",
        yaxis_range=[0, 110],
        showlegend=False,
        height=350,
    )
    st.plotly_chart(fig_fid, use_container_width=True)

    st.divider()

    # Test coverage breakdown
    st.markdown("**Test Coverage by Category**")
    coverage_rows = []
    for d in data:
        cov = d.get("test_coverage_by_category", {})
        coverage_rows.append({
            "Scenario": d["scenario_id"],
            "Normal": cov.get("normal", 0),
            "Boundary": cov.get("boundary", 0),
            "Exception": cov.get("exception", 0),
            "Error": cov.get("error", 0),
        })

    cov_df = pd.DataFrame(coverage_rows)

    fig3 = go.Figure()
    categories = ["Normal", "Boundary", "Exception", "Error"]
    cat_colors = ["#0066cc", "#28a745", "#ffc107", "#dc3545"]
    for cat, color in zip(categories, cat_colors):
        fig3.add_trace(go.Bar(
            x=cov_df["Scenario"],
            y=cov_df[cat],
            name=cat,
            marker_color=color,
        ))
    fig3.update_layout(
        title="Test Coverage Distribution",
        barmode="stack",
        yaxis_title="Number of Tests",
        height=350,
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Compliance flags summary
    st.divider()
    st.markdown("**Compliance Flags Summary**")
    flag_rows = []
    for d in data:
        flag_rows.append({
            "Scenario": d["scenario_id"],
            "Critical": d.get("critical_flags", 0),
            "Warning": d.get("warning_flags", 0),
        })
    flag_df = pd.DataFrame(flag_rows)
    st.dataframe(flag_df, use_container_width=True, hide_index=True)

    # Key findings
    st.divider()
    st.markdown("**Key Findings**")

    total_scenarios = len(data)
    first_pass = sum(1 for d in data if d["first_pass_success"])
    total_tests = sum(d["total_tests"] for d in data)
    total_passed = sum(d["passed_tests"] for d in data)
    max_fix = max(d["self_fix_count"] for d in data)
    avg_fidelity = sum(d.get("fidelity_score", 0) for d in data) / total_scenarios

    st.markdown(f"""
    - **First-pass success rate:** {first_pass}/{total_scenarios} scenarios ({first_pass/total_scenarios:.0%})
    - **Total tests generated and passed:** {total_passed}/{total_tests}
    - **Average Business Rule Fidelity:** {avg_fidelity:.0%}
    - **Maximum self-fix attempts:** {max_fix}
    - **Complexity impact:** S3 (complex) required {[d.get('elapsed_seconds', 0) for d in data if d['scenario_id'] == 'S3'][0]:.0f}s vs S1 (simple) {[d.get('elapsed_seconds', 0) for d in data if d['scenario_id'] == 'S1'][0]:.0f}s
    """)
