"""AST-based import validation for sandbox security."""

import ast

from config.settings import ALLOWED_IMPORTS


def check_imports(
    code: str,
    extra_allowed: set[str] | None = None,
) -> tuple[bool, list[str]]:
    """Check if code only uses allowed imports.

    Args:
        code: Python source code to check.
        extra_allowed: Additional module names to allow (e.g., for test code).

    Returns:
        (is_safe, violations): True if all imports are allowed,
        list of violation descriptions.
    """
    allowed = ALLOWED_IMPORTS | (extra_allowed or set())
    violations = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in allowed:
                    violations.append(
                        f"Disallowed import: '{alias.name}' (line {node.lineno})"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module not in allowed:
                    violations.append(
                        f"Disallowed import: 'from {node.module}' (line {node.lineno})"
                    )

    is_safe = len(violations) == 0
    return is_safe, violations
