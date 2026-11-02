"""Tab 4: Compliance Flags - security and regulatory risk flags + Business Rule Fidelity."""

import streamlit as st
import pandas as pd


VERDICT_DISPLAY = {
    "faithful": "✅ Faithful",
    "incorrect": "⚠️ Implemented but incorrect",
    "missing": "❌ Missing",
    "undetermined": "❔ Undetermined",
}
METHOD_DISPLAY = {
    "ast": "AST (deterministic)",
    "llm": "LLM judge",
    "none": "—",
}


def _verdict(r: dict) -> str:
    """v2 results carry `verdict`; fall back to v1 implemented/correct flags."""
    if "verdict" in r:
        return r["verdict"]
    if r.get("implemented") and r.get("correct"):
        return "faithful"
    if r.get("implemented"):
        return "incorrect"
    return "missing"


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

            icon = "🔴" if severity == "critical" else "🟡"

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
        ("Business Rule Fidelity", "AST boundary check for numeric thresholds, LLM judge for the rest"),
    ]
    for name, desc in checks:
        st.markdown(f"- **{name}:** {desc}")

    # Business Rule Fidelity
    st.divider()
    st.subheader("Business Rule Fidelity")
    st.markdown(
        '*"Tests passing" ≠ "Logic is correct"* — '
        "each condition of the rule spec is checked against the generated code. "
        "Numeric thresholds are verified deterministically from the AST "
        "(boundary placement); remaining conditions go to an LLM judge."
    )

    fidelity_results = result.get("fidelity_results", [])
    fidelity_score = result.get("fidelity_score", 0.0)

    if fidelity_results:
        m1, m2, m3 = st.columns(3)
        m1.metric("Fidelity (all conditions)", f"{fidelity_score:.0%}")
        rule_score = metrics.get("fidelity_rule_score")
        m2.metric(
            "Fidelity (rule-origin only)",
            f"{rule_score:.0%}" if rule_score is not None else "n/a",
        )
        method_counts = metrics.get("fidelity_method_counts", {})
        m3.metric(
            "Decided by AST",
            f"{method_counts.get('ast', 0)}/{len(fidelity_results)}",
        )

        rows = []
        for r in fidelity_results:
            rows.append({
                "Condition": r.get("condition_id", "?"),
                "Source": r.get("source", "unknown"),
                "Status": VERDICT_DISPLAY.get(_verdict(r), _verdict(r)),
                "Method": METHOD_DISPLAY.get(r.get("method"), r.get("method", "LLM (v1)")),
                "Evidence": r.get("evidence", ""),
            })

        fid_df = pd.DataFrame(rows)
        st.dataframe(fid_df, use_container_width=True, hide_index=True)
        st.caption(
            "Source: 'rule' = stated in the original rule text, "
            "'derived' = validation constraint added during spec interpretation."
        )
    else:
        st.info("No fidelity data. Run the pipeline first.")
