"""First-party AST inventory; embedded browser callbacks are formatted before counting."""

import ast
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {".venv", "node_modules", "dist", "vendor", "__pycache__"}


def python_sources():
    for directory in ["back", "front", "infrastructure", "tests/integration"]:
        for path in (ROOT / directory).rglob("*.py"):
            if not EXCLUDED.intersection(path.relative_to(ROOT).parts):
                yield path


def python_inventory(paths):
    violations, snippets, count = [], [], 0
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                count += 1
                span = node.end_lineno - node.lineno + 1
                if span > 50:
                    violations.append(
                        {
                            "file": str(path.relative_to(ROOT)),
                            "line": node.lineno,
                            "name": node.name,
                            "lines": span,
                        }
                    )
            if isinstance(node, ast.Call):
                snippet = browser_snippet(path, node)
                if snippet:
                    snippets.append(snippet)
    return violations, snippets, count


def browser_snippet(path, call):
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in {
        "evaluate",
        "wait_for_function",
        "add_init_script",
    }:
        return None
    if (
        not call.args
        or not isinstance(call.args[0], ast.Constant)
        or not isinstance(call.args[0].value, str)
    ):
        return None
    return {
        "file": str(path.relative_to(ROOT)),
        "line": call.args[0].lineno,
        "source": call.args[0].value,
    }


def javascript_inventory(snippets):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
        json.dump(snippets, handle)
        handle.flush()
        process = subprocess.run(
            [
                "node",
                "front/scripts/function-inventory.mjs",
                "front/app",
                "front/scripts",
                "front/tests/fixtures",
                "back/tests/fixtures/browser",
                "--snippets",
                handle.name,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
    if process.returncode not in {0, 1} or not process.stdout.strip():
        raise RuntimeError(process.stderr)
    return json.loads(process.stdout)


def main():
    violations, snippets, count = python_inventory(list(python_sources()))
    violations.extend(javascript_inventory(snippets))
    print(
        json.dumps(
            {
                "python_functions": count,
                "embedded_callbacks": len(snippets),
                "violations": violations,
            },
            indent=2,
        )
    )
    return bool(violations)


if __name__ == "__main__":
    raise SystemExit(main())
