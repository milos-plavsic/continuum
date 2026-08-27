#!/usr/bin/env python3
"""Validate and package independently inspectable coverage evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "continuum"


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_inventory() -> list[str]:
    return sorted(_relative(path) for path in SOURCE_ROOT.rglob("*.py"))


def _measured_path(name: str) -> str:
    path = Path(name)
    return _relative(path if path.is_absolute() else ROOT / path)


def _test_count() -> int:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"))
    if loader.errors:
        raise ValueError("TEST_DISCOVERY_FAILED:" + " | ".join(loader.errors))
    return suite.countTestCases()


def _source_tree_digest(inventory: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in inventory:
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(_sha256(ROOT / relative).encode("ascii") + b"\n")
    return "sha256:" + digest.hexdigest()


def build_evidence(coverage_json: Path, output: Path) -> dict[str, object]:
    report = json.loads(coverage_json.read_text(encoding="utf-8"))
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    coverage_config = config["tool"]["coverage"]
    run_config = coverage_config["run"]
    report_config = coverage_config["report"]
    source_inventory = _source_inventory()
    measured_inventory = sorted(_measured_path(name) for name in report["files"])
    pragma_hits = [
        f"{relative}:{line_number}"
        for relative in source_inventory
        for line_number, line in enumerate(
            (ROOT / relative).read_text(encoding="utf-8").splitlines(), 1
        )
        if "pragma: no cover" in line.lower()
    ]
    totals = report["totals"]
    checks = {
        "branch_measurement_enabled": run_config.get("branch") is True,
        "coverage_source_is_complete_package": run_config.get("source") == ["src/continuum"],
        "no_configured_source_omissions": not run_config.get("omit"),
        "no_configured_report_exclusions": not report_config.get("exclude_lines"),
        "no_source_coverage_pragmas": not pragma_hits,
        "every_source_module_measured": measured_inventory == source_inventory,
        "no_unexpected_module_measured": measured_inventory == source_inventory,
        "no_missing_statements": totals["missing_lines"] == 0,
        "no_missing_branches": totals["missing_branches"] == 0,
        "statement_gate_is_100": report_config.get("fail_under") == 100,
        "reported_percent_is_100": totals["percent_covered"] == 100.0,
    }
    evidence: dict[str, object] = {
        "schema": "continuum/coverage-evidence/1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": "every Python module under src/continuum",
        "source_tree_digest": _source_tree_digest(source_inventory),
        "test_count": _test_count(),
        "totals": {
            "statements": totals["num_statements"],
            "covered_statements": totals["covered_lines"],
            "missing_statements": totals["missing_lines"],
            "branches": totals["num_branches"],
            "covered_branches": totals["covered_branches"],
            "missing_branches": totals["missing_branches"],
            "coverage_percent": totals["percent_covered"],
        },
        "checks": checks,
        "source_inventory": source_inventory,
        "measured_inventory": measured_inventory,
        "coverage_pragma_hits": pragma_hits,
        "generator": {
            "coverage_version": report["meta"]["version"],
            "branch_coverage": report["meta"]["branch_coverage"],
            "show_contexts": report["meta"]["show_contexts"],
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    evidence_path = output / "coverage-evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    summary = [
        "# Continuum coverage evidence",
        "",
        f"Status: **{evidence['status']}**",
        "",
        f"Scope: `{evidence['scope']}` ({len(source_inventory)} modules).",
        f"Tests discovered: **{evidence['test_count']}**.",
        (f"Statements: **{totals['covered_lines']}/{totals['num_statements']}**; "
         f"branches: **{totals['covered_branches']}/{totals['num_branches']}**; "
         f"combined coverage: **{totals['percent_covered']:.1f}%**."),
        "",
        "The machine-readable evidence verifies exact source/measured inventories, branch",
        "measurement, a 100% failure threshold, no configured omissions or exclusions, and",
        "no `pragma: no cover` shortcuts. `coverage.xml`, `coverage.json`, and `html/` are",
        "included for independent inspection.",
        "",
        "## Checks",
        "",
        *[f"- {'PASS' if passed else 'FAIL'} — `{name}`" for name, passed in checks.items()],
        "",
    ]
    (output / "README.md").write_text("\n".join(summary), encoding="utf-8")
    if evidence["status"] != "PASS":
        raise ValueError("coverage evidence failed: " + ", ".join(
            name for name, passed in checks.items() if not passed
        ))
    return evidence


def write_checksums(output: Path) -> None:
    manifest = output / "SHA256SUMS"
    files = sorted(
        path for path in output.rglob("*") if path.is_file() and path != manifest
    )
    manifest.write_text(
        "".join(f"{_sha256(path)}  {path.relative_to(output).as_posix()}\n" for path in files),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = build_evidence(args.coverage_json.resolve(), args.output.resolve())
        write_checksums(args.output.resolve())
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"coverage evidence: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "coverage evidence: PASS: "
        f"{evidence['test_count']} tests; {evidence['totals']['coverage_percent']:.1f}% "
        "statement/branch aggregate; complete src/continuum inventory"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
