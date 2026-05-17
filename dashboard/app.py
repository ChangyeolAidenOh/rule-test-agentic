"""Streamlit dashboard for Insurance Rule-to-Test Agentic Coding PoC."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(
    page_title="Insurance Agentic Dev PoC",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #555;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        border-left: 4px solid #0066cc;
    }
    .pass-badge {
        background: #d4edda;
        color: #155724;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .fail-badge {
        background: #f8d7da;
        color: #721c24;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .warning-badge {
        background: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">Insurance Rule-to-Test Agentic Coding PoC</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Developer-in-the-loop: Business rule to code/test/doc draft generation</div>', unsafe_allow_html=True)

# Import tabs
from dashboard.tabs.tab_rule_input import render as render_rule_input
from dashboard.tabs.tab_generated_code import render as render_generated_code
from dashboard.tabs.tab_test_results import render as render_test_results
from dashboard.tabs.tab_compliance import render as render_compliance
from dashboard.tabs.tab_documentation import render as render_documentation
from dashboard.tabs.tab_evaluation import render as render_evaluation

# Tab layout
tabs = st.tabs([
    "Rule Input",
    "Generated Code",
    "Test Results",
    "Compliance Flags",
    "Documentation",
    "Evaluation",
])

with tabs[0]:
    render_rule_input()

with tabs[1]:
    render_generated_code()

with tabs[2]:
    render_test_results()

with tabs[3]:
    render_compliance()

with tabs[4]:
    render_documentation()

with tabs[5]:
    render_evaluation()
