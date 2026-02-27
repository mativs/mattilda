import ast
from pathlib import Path


DB_SESSION_METHODS = {
    "add",
    "add_all",
    "commit",
    "delete",
    "execute",
    "flush",
    "get",
    "query",
    "refresh",
}


def _test_files() -> list[Path]:
    root = Path(__file__).resolve().parent
    return sorted(
        path
        for path in root.rglob("test_*.py")
        if path.name != "conftest.py" and "helpers" not in path.parts and path.name != "test_compliance_rules.py"
    )


def _db_session_calls_in_test_functions(file_path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    violations: list[tuple[str, int]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        for subnode in ast.walk(node):
            if not isinstance(subnode, ast.Call):
                continue
            func = subnode.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "db_session"
                and func.attr in DB_SESSION_METHODS
            ):
                violations.append((node.name, subnode.lineno))
    return violations


def test_no_direct_db_session_calls_inside_test_functions():
    """
    Validate test methods avoid direct db_session operations.

    1. Discover all backend test files excluding conftest and helpers.
    2. Parse each file AST and inspect only test_* function bodies.
    3. Detect any direct db_session DB operation call usage.
    4. Validate no violations exist and report actionable locations otherwise.
    """
    errors: list[str] = []
    for file_path in _test_files():
        for test_name, line in _db_session_calls_in_test_functions(file_path):
            errors.append(f"{file_path.relative_to(Path(__file__).resolve().parent)}:{line} in {test_name}")
    assert not errors, "Direct db_session calls found in test methods:\n" + "\n".join(errors)
