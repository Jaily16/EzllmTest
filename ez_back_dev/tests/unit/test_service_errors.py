import ast
from pathlib import Path


from repo_paths import BACKEND_ROOT

SERVICE_ROOT = BACKEND_ROOT / "service"


def _exception_name(handler: ast.ExceptHandler) -> str | None:
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    if isinstance(handler.type, ast.Attribute):
        return handler.type.attr
    return None


def test_llm_services_do_not_swallow_typed_llm_errors():
    failures = []
    for path in sorted(SERVICE_ROOT.glob("llm*Service.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            names = [_exception_name(handler) for handler in node.handlers]
            if "Exception" in names:
                exception_index = names.index("Exception")
                if "LLMError" not in names[:exception_index]:
                    failures.append(f"{path.name}:{node.lineno}")

    assert failures == [], "Typed LLM errors are swallowed at: " + ", ".join(failures)
