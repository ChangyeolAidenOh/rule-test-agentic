"""LLM utility wrapper for Anthropic API calls."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import ANTHROPIC_API_KEY, NODE_MODELS


def get_llm(node_name: str, temperature: float = 0.0) -> ChatAnthropic:
    """Get LLM instance for a specific node."""
    model = NODE_MODELS.get(node_name)
    if model is None:
        raise ValueError(f"Unknown node: {node_name}")
    return ChatAnthropic(
        model=model,
        api_key=ANTHROPIC_API_KEY,
        temperature=temperature,
        max_tokens=16384,
    )


def invoke_llm(
    node_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
) -> str:
    """Invoke LLM and return text response."""
    llm = get_llm(node_name, temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    return response.content
