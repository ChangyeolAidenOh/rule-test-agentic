"""Tab 4: Compliance Flags - security and regulatory risk flags."""

import streamlit as st
import pandas as pd


def render():
    st.subheader("Compliance Flags")

    if "pipeline_result" not in st.session_state:
        st.info("Run the pipeline in the 'Rule Input' tab first.")
        return

    result = st.session_state["pipeline_result"]
    metrics = st.session_state["pipeline_metrics"]

    # Summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Critical", metrics["critical_flags"])
    c2.metric("Warning", metrics["warning_flags"])
    c3.metric("Total", metrics["total_flags"])

    st.divider()

    flags = result.get("compliance_flags", [])
    if flags:
        st.markdown("**Detected Issues**")

        for flag in flags:
            severity = flag.get("severity", "info")
            category = flag.get("category", "unknown")
            description = flag.get("description", "")
            line_num = flag.get("line_number", "?")
            suggestion = flag.get("suggestion", "")

            if severity == "critical":
                icon = "🔴"
            else:
                icon = "🟡"

            with st.container(border=True):
                st.markdown(
                    f"{icon} **[{severity.upper()}]** {category} — Line {line_num}"
                )
                st.markdown(description)
                if suggestion:
                    st.markdown(f"*Suggestion:* {suggestion}")

        # Category distribution
        st.divider()
        st.markdown("**Flags by Category**")
        cat_counts = {}
        for f in flags:
            cat = f.get("category", "unknown")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        cat_df = pd.DataFrame([
            {"Category": k, "Count": v}
            for k, v in cat_counts.items()
        ])
        st.bar_chart(cat_df.set_index("Category"), height=200)

    else:
        st.success("No compliance flags detected.")

    # Compliance check categories
    st.divider()
    st.markdown("**Compliance Check Categories**")
    checks = [
        ("PII Logging Detection", "Scans print/logging statements for personal identifiers"),
        ("Float Arithmetic", "Detects float literals in monetary calculations"),
        ("Magic Numbers", "Flags hardcoded numeric values inside function bodies"),
        ("Exception Handling", "Checks for missing input validation in apply_rule()"),
        ("Business Rule Fidelity", "LLM-based condition-by-condition verification against rule spec"),
    ]
    for name, desc in checks:
        st.markdown(f"- **{name}:** {desc}")

    # Business Rule Fidelity
    st.divider()
    st.subheader("Business Rule Fidelity")
    st.markdown(
        '*"Tests passing" ≠ "Logic is correct"* — '
        "Fidelity checks each condition from the rule spec against the generated code."
    )

    fidelity_results = result.get("fidelity_results", [])
    fidelity_score = result.get("fidelity_score", 0.0)

    if fidelity_results:
        st.metric("Fidelity Score", f"{fidelity_score:.0%}")

        rows = []
        for r in fidelity_results:
            implemented = r.get("implemented", False)
            correct = r.get("correct", False)
            if implemented and correct:
                status = "Faithful"
                icon = "✅"
            elif implemented and not correct:
                status = "Implemented but incorrect"
                icon = "⚠️"
            else:
                status = "Missing"
                icon = "❌"

            rows.append({
                "Condition": r.get("condition_id", "?"),
                "Status": f"{icon} {status}",
                "Evidence": r.get("evidence", ""),
            })

        fid_df = pd.DataFrame(rows)
        st.dataframe(fid_df, use_container_width=True, hide_index=True)
    else:
        st.info("No fidelity data. Run the pipeline first.")
