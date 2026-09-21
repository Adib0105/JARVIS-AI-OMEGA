"""Trusted hello fixture only. Not evidence of production execution isolation."""
import subprocess
import sys
from pathlib import Path
from jarvis.self_development.tester import CheckResult

def run_fixture(self, name, args, cwd):
    cwd = Path(cwd)
    allowed = {"hello.py", "tests/test_hello.py"}
    files = {p.relative_to(cwd).as_posix() for p in cwd.rglob("*.py")}
    if files != allowed:
        raise AssertionError("Trusted fixture runner only accepts the reviewed hello fixture")
    hello = cwd.joinpath("hello.py").read_text()
    if hello not in {"def greet():\n    return 'old'\n", "def greet():\n    return 'new'\n"}:
        raise AssertionError("Unexpected executable fixture")
    test = cwd.joinpath("tests/test_hello.py").read_text()
    import ast
    tree = ast.parse(test)
    # Test fixture imports are fixed, no arbitrary imports/code supplied by a user.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and [x.name for x in node.names] != ['unittest']:
            raise AssertionError('Unexpected fixture import')
        if isinstance(node, ast.ImportFrom) and node.module != 'hello':
            raise AssertionError('Unexpected fixture import')
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id == 'greet' or isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual'):
            raise AssertionError('Unexpected fixture call')
    proc = subprocess.run([sys.executable, *args], cwd=cwd, text=True, capture_output=True, timeout=10)
    return CheckResult(name, proc.returncode == 0, proc.returncode, 0.0, proc.stdout, proc.stderr)
