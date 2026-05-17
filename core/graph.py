"""LangGraph orchestrator - 6-node pipeline with self-correction loop."""

from langgraph.graph import END, StateGraph

from core.state import PipelineState
from nodes.rule_interpreter import rule_interpreter
from nodes.code_generator import code_generator
from nodes.test_generator import test_generator
from nodes.test_runner import test_runner
from nodes.compliance_checker import compliance_checker
from nodes.doc_generator import doc_generator


def _should_fix_or_continue(state: PipelineState) -> str:
    """Route after test runner: fix, manual, or continue."""
    status = state.get("status", "")
    if status == "tests_passed":
        return "compliance"
    elif status == "fix_needed":
        return "fix"
    else:
        # manual_required or error
        return "compliance"


def build_graph() -> StateGraph:
    """Build the 6-node pipeline graph with self-correction loop."""
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("rule_interpreter", rule_interpreter)
    graph.add_node("code_generator", code_generator)
    graph.add_node("test_generator", test_generator)
    graph.add_node("test_runner", test_runner)
    graph.add_node("compliance_checker", compliance_checker)
    graph.add_node("doc_generator", doc_generator)

    # Define edges
    graph.set_entry_point("rule_interpreter")
    graph.add_edge("rule_interpreter", "code_generator")
    graph.add_edge("code_generator", "test_generator")
    graph.add_edge("test_generator", "test_runner")

    # Conditional edge after test runner: fix loop or continue
    graph.add_conditional_edges(
        "test_runner",
        _should_fix_or_continue,
        {
            "fix": "code_generator",      # Self-correction loop
            "compliance": "compliance_checker",
        },
    )

    graph.add_edge("compliance_checker", "doc_generator")
    graph.add_edge("doc_generator", END)

    return graph.compile()


def run_pipeline(raw_rule: str, scenario_id: str = "", complexity: str = "") -> PipelineState:
    """Run the full pipeline for a single business rule."""
    app = build_graph()

    initial_state: PipelineState = {
        "raw_rule": raw_rule,
        "scenario_id": scenario_id,
        "complexity": complexity,
        "fix_attempt": 0,
        "fix_history": [],
        "status": "running",
    }

    final_state = app.invoke(initial_state)
    return final_state
