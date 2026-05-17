import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model configuration
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

# Node-to-model mapping
NODE_MODELS = {
    "rule_interpreter": MODEL_SONNET,
    "code_generator": MODEL_SONNET,
    "test_generator": MODEL_SONNET,
    "compliance_checker": MODEL_HAIKU,
    "doc_generator": MODEL_HAIKU,
}

# Sandbox settings
SANDBOX_TIMEOUT_SECONDS = 30
MAX_SELF_FIX_ATTEMPTS = 3
ALLOWED_IMPORTS = {
    "math", "decimal", "datetime", "dataclasses",
    "typing", "enum", "collections", "functools",
    "copy", "json", "re",
}

# Temperature settings
TEMPERATURE_CODE = 0.0
TEMPERATURE_REASONING = 0.2
TEMPERATURE_DOCS = 0.3
