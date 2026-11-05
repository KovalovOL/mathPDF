"""Static dependency/contract checks, separate from behavioral acceptance tests."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDK_MODULES = {
    "fastapi",
    "starlette",
    "httpx",
    "openai",
    "google",
    "boto3",
    "botocore",
    "playwright",
    "pdfminer",
    "fontTools",
    "psycopg",
}


def modules(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.module or "", node.lineno
            if any(alias.name == "*" for alias in node.names):
                yield "*", node.lineno
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno


def dependencies():
    failures = []
    for path in (ROOT / "back/app").rglob("*.py"):
        parts = path.relative_to(ROOT / "back/app").parts
        domain = len(parts) > 1 and parts[0] not in {
            "bootstrap",
            "core",
            "infrastructure",
            "application",
        }
        handler = path.name.endswith("handler.py")
        for module, line in modules(path):
            forbidden = module == "*" or module.startswith("formula_lab")
            if domain and not handler:
                forbidden |= module.split(".")[0] in SDK_MODULES
                forbidden |= module.startswith(
                    ("app.bootstrap", "app.infrastructure", "app.application")
                )
                forbidden |= module.endswith(".handler")
            if parts[0] in {"core", "application"}:
                forbidden |= module.startswith(("app.bootstrap", "app.infrastructure"))
            if forbidden:
                failures.append(
                    f"{path.relative_to(ROOT)}:{line}: forbidden dependency {module}"
                )
    return failures


def routes():
    result = {("GET", "/"), ("GET", "/workspace")}
    for path in (ROOT / "back/app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Attribute)
                or node.func.attr != "add_api_route"
            ):
                continue
            route = ast.literal_eval(node.args[0])
            methods = next(
                ast.literal_eval(k.value) for k in node.keywords if k.arg == "methods"
            )
            result.update((method, route) for method in methods)
    return result


def digests(baseline):
    failures = []
    for name, expected in baseline["fixtures"].items():
        for root in ["tests/fixtures/study-sets", "back/tests/fixtures/study-sets"]:
            path = ROOT / root / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                failures.append(f"Historical fixture changed: {path.relative_to(ROOT)}")
    for name, expected in baseline["prompts"].items():
        path = ROOT / "back/app/generation/prompts" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"Prompt text changed: {name}")
    return failures


def isolation():
    failures = []
    for path in (ROOT / "back/app").rglob("*"):
        if path.is_file() and path.suffix in {".html", ".css", ".js", ".mjs"}:
            failures.append(f"Frontend asset inside backend: {path.relative_to(ROOT)}")
    for path in (ROOT / "front/app").rglob("*.js"):
        if any(
            marker in path.read_text()
            for marker in ["back/app/", "formula_lab/", "../back/"]
        ):
            failures.append(f"Frontend source coupling: {path.relative_to(ROOT)}")
    for path in (ROOT / "back/app/application/use_cases").glob("*.py"):
        classes = [
            n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef)
        ]
        if path.name != "__init__.py" and len(classes) != 1:
            failures.append(
                f"Use case file must own one operation: {path.relative_to(ROOT)}"
            )
    return failures


def inspect():
    baseline = json.loads((ROOT / "contracts/http/refactor-baseline.json").read_text())
    actual = routes()
    missing = {(r["method"], r["path"]) for r in baseline["routes"]} - actual
    failures = dependencies() + digests(baseline) + isolation()
    failures.extend(
        f"Missing HTTP route: {method} {path}" for method, path in sorted(missing)
    )
    return {
        "routes": len(actual),
        "historical_fixtures": len(baseline["fixtures"]),
        "prompt_files": len(baseline["prompts"]),
        "violations": failures,
    }


if __name__ == "__main__":
    result = inspect()
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["violations"]))
