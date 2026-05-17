"""Tab 1: Rule Input - run the 6-node pipeline on a business rule."""

import streamlit as st

from scenarios.definitions import get_all_scenarios
from core.graph import run_pipeline
from evaluation.metrics import compute_metrics


def render():
    st.subheader("Business Rule Input")

    col1, col2 = st.columns([3, 1])

    with col1:
        # Preset scenarios
        scenarios = get_all_scenarios()
        options = ["Custom rule"] + [
            f"{s['scenario_id']} [{s['complexity']}] {s['raw_rule']}"
            for s in scenarios
        ]
        selected = st.selectbox("Select a scenario or enter custom rule:", options)

        if selected == "Custom rule":
            rule_text = st.text_area(
                "Enter business rule (Korean):",
                height=100,
                placeholder="Example: 갱신 시 65세 이상 보험료 15% 인상, 5년 무사고 시 10%만",
            )
            scenario_id = "custom"
            complexity = "custom"
        else:
            idx = options.index(selected) - 1
            scenario = scenarios[idx]
            rule_text = scenario["raw_rule"]
            scenario_id = scenario["scenario_id"]
            complexity = scenario["complexity"]
            st.info(f"Rule: {rule_text}")

    with col2:
        st.markdown("**Pipeline Nodes**")
        st.markdown("""
        1. Rule Interpreter
        2. Code Generator
        3. Test Generator
        4. Test Runner
        5. Compliance Checker
        6. Doc Generator
        """)

    if st.button("Run Pipeline", type="primary", use_container_width=True):
        if not rule_text.strip():
            st.error("Please enter a business rule.")
            return

        with st.status("Running 6-node pipeline...", expanded=True) as status:
            st.write("Node 1: Interpreting business rule...")
            try:
                final_state = run_pipeline(
                    raw_rule=rule_text,
                    scenario_id=scenario_id,
                    complexity=complexity,
                )
                st.session_state["pipeline_result"] = final_state
                st.session_state["pipeline_metrics"] = compute_metrics(final_state)
                status.update(label="Pipeline completed", state="complete")
            except Exception as e:
                status.update(label="Pipeline failed", state="error")
                st.error(f"Error: {e}")
                return

        # Show summary
        metrics = st.session_state["pipeline_metrics"]
        result = st.session_state["pipeline_result"]

        st.divider()
        st.subheader("Pipeline Result Summary")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", result.get("status", "unknown"))
        c2.metric(
            "Tests",
            f"{metrics['passed_tests']}/{metrics['total_tests']}",
        )
        c3.metric("Self-fix", metrics["self_fix_count"])
        c4.metric("Flags", metrics["total_flags"])

        if result.get("all_tests_passed"):
            st.success("All tests passed on first attempt.")
        elif result.get("status") == "manual_required":
            st.warning("Manual development required. Self-fix exhausted (3 attempts).")
        else:
            st.info(f"Pipeline status: {result.get('status')}")

    elif "pipeline_result" in st.session_state:
        metrics = st.session_state["pipeline_metrics"]
        result = st.session_state["pipeline_result"]

        st.divider()
        st.subheader("Last Pipeline Result")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", result.get("status", "unknown"))
        c2.metric("Tests", f"{metrics['passed_tests']}/{metrics['total_tests']}")
        c3.metric("Self-fix", metrics["self_fix_count"])
        c4.metric("Flags", metrics["total_flags"])
