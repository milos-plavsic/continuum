#!/usr/bin/env python3
"""Validate and render Continuum's canonical environment-variable inventory."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "config/environment.json"
SCHEMA = ROOT / "schemas/environment-inventory-v1.schema.json"
DOCUMENT = ROOT / "docs/CONFIGURATION.md"
CONTROLLED = re.compile(
    r"^(?:CONTINUUM_[A-Z0-9_]+|GOOGLE_CLOUD_[A-Z0-9_]+|"
    r"GOOGLE_GENAI_[A-Z0-9_]+|K_(?:SERVICE|REVISION)|GIT_SHA|"
    r"OTEL_SERVICE_NAME|PORT)$")
SHELL_ENV = re.compile(
    r"\$(?:\{)?((?:CONTINUUM|GOOGLE_CLOUD|GOOGLE_GENAI|K|OTEL)_[A-Z0-9_]+|GIT_SHA|PORT)")
SCAN_ROOTS = ("app", "src", "scripts", "deploy", ".github", "Dockerfile", "compose.local.yaml")


def _literal_name(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def python_environment_reads(path: Path) -> set[str]:
    """Return statically named environment reads from one Python file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                    and func.value.id == "os" and func.attr == "getenv"):
                name = _literal_name(node.args[0])
                if name:
                    names.add(name)
            if (isinstance(func, ast.Attribute) and func.attr == "get"
                    and isinstance(func.value, ast.Attribute)
                    and isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "os" and func.value.attr == "environ"):
                name = _literal_name(node.args[0])
                if name:
                    names.add(name)
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"
                and node.value.attr == "environ"):
            name = _literal_name(node.slice)
            if name:
                names.add(name)
    return {name for name in names if CONTROLLED.fullmatch(name)}


def source_environment_reads(root: Path = ROOT) -> set[str]:
    """Find controlled environment reads across supported source and operator files."""
    names: set[str] = set()
    for relative in SCAN_ROOTS:
        candidate = root / relative
        paths = [candidate] if candidate.is_file() else sorted(candidate.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix in {".pyc", ".png"}:
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            if path.suffix == ".py":
                names.update(python_environment_reads(path))
            else:
                names.update(name for name in SHELL_ENV.findall(text)
                             if CONTROLLED.fullmatch(name))
            if path == root / "deploy/cloud.env.example":
                names.update(line.split("=", 1)[0] for line in text.splitlines()
                             if CONTROLLED.fullmatch(line.split("=", 1)[0]))
            if path == root / "compose.local.yaml":
                names.update(match.group(1) for match in
                             re.finditer(r"^\s{6}([A-Z][A-Z0-9_]+):", text, re.MULTILINE)
                             if CONTROLLED.fullmatch(match.group(1)))
    return names


def load_and_validate() -> tuple[dict, list[str]]:
    """Validate schema and project-specific safety invariants."""
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    inventory = json.loads(INVENTORY.read_text())
    errors = [f"schema:{error.json_path}:{error.message}" for error in
              sorted(Draft202012Validator(schema).iter_errors(inventory),
                     key=lambda error: list(error.absolute_path))]
    variables = inventory.get("variables", [])
    names = [item.get("name") for item in variables]
    if names != sorted(names):
        errors.append("inventory:not-sorted")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    errors.extend(f"inventory:duplicate:{name}" for name in duplicates)
    declared = set(names)
    errors.extend(f"inventory:undeclared-source-read:{name}" for name in
                  sorted(source_environment_reads() - declared))
    for item in variables:
        name = item.get("name", "")
        if item.get("sensitivity") == "secret":
            if "default" in item:
                errors.append(f"inventory:secret-default:{name}")
            if item.get("evidence_policy") != "forbid":
                errors.append(f"inventory:secret-evidence-policy:{name}")
        for consumer in item.get("consumers", []):
            if not (ROOT / consumer).exists():
                errors.append(f"inventory:missing-consumer:{name}:{consumer}")
    return inventory, errors


def render(inventory: dict) -> str:
    """Render the deterministic human operator reference."""
    lines = [
        "# Configuration inventory", "",
        "Generated from `config/environment.json` by `scripts/check_configuration.py`.",
        "Edit the JSON inventory, not this table. Values are never captured here.", "",
        "Secrets have no defaults and are forbidden from public evidence. `required_in` names",
        "the profiles in which an operator or platform must supply the value; an empty list",
        "means optional. See `docs/CI_ASSURANCE.md` for profile boundaries.", "",
        "| Variable | Owner / kind | Type | Required in | Default | Sensitivity / evidence | Description |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in inventory["variables"]:
        required = ", ".join(item["required_in"]) or "optional"
        default = str(item.get("default", "—")).lower()
        lines.append(
            f"| `{item['name']}` | {item['owner']} / {item['kind']} | {item['type']} | "
            f"{required} | `{default}` | {item['sensitivity']} / {item['evidence_policy']} | "
            f"{item['description']} |")
    lines.extend(["", "## Machine checks", "", "```bash",
                  "uv run --extra test python scripts/check_configuration.py --check",
                  "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    inventory, errors = load_and_validate()
    expected = render(inventory)
    if args.write:
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        DOCUMENT.write_text(expected)
        print(f"wrote {DOCUMENT.relative_to(ROOT)}")
        return 0
    if not DOCUMENT.exists() or DOCUMENT.read_text() != expected:
        errors.append("inventory:generated-document-stale")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASS", "variables": len(inventory["variables"]),
                      "source_reads": len(source_environment_reads())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
