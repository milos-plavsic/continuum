"""Single machine-checked truth for mutable submission release facts."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "continuum/submission-release/1"
JUDGE_FACING_PATHS = (
    "README.md",
    "devpost-submission.md",
    "docs/HACKATHON_COMPLIANCE.md",
    "src/continuum/static/public_showcase.html",
)
REQUIRED_TOP_LEVEL = {"schema", "application", "run", "proof", "quality", "showcase",
                      "superseded_markers"}
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class ReleaseTruthError(ValueError):
    """The submission release manifest or one of its projections is invalid."""


def load_release_truth(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != REQUIRED_TOP_LEVEL:
        raise ReleaseTruthError("RELEASE_TRUTH_SCHEMA_INVALID")
    if value["schema"] != SCHEMA:
        raise ReleaseTruthError("RELEASE_TRUTH_VERSION_UNSUPPORTED")
    application, run, proof, quality, showcase = (
        value["application"], value["run"], value["proof"], value["quality"], value["showcase"])
    if set(application) != {"source_commit", "image_digest"}:
        raise ReleaseTruthError("APPLICATION_RELEASE_INVALID")
    if not COMMIT.fullmatch(application["source_commit"]) or not SHA256.fullmatch(
            application["image_digest"]):
        raise ReleaseTruthError("APPLICATION_IDENTITY_INVALID")
    if set(run) != {"id", "trace_id", "required_object_count", "trace_span_count",
                   "offline_verdict"}:
        raise ReleaseTruthError("RUN_RELEASE_INVALID")
    if (not run["id"] or not re.fullmatch(r"[0-9a-f]{32}", run["trace_id"]) or
            not all(isinstance(run[name], int) and run[name] > 0 for name in (
                "required_object_count", "trace_span_count")) or run["offline_verdict"] != "PASS"):
        raise ReleaseTruthError("RUN_IDENTITY_INVALID")
    if (set(proof) != {"release_tag", "archive_sha256", "report_digest"} or
            not re.fullmatch(r"[0-9a-f]{64}", proof["archive_sha256"]) or
            not SHA256.fullmatch(proof["report_digest"])):
        raise ReleaseTruthError("PROOF_RELEASE_INVALID")
    if (set(quality) != {"test_count", "statement_coverage", "branch_coverage"} or
            not isinstance(quality["test_count"], int) or quality["test_count"] <= 0 or
            quality["statement_coverage"] != "100.0%" or quality["branch_coverage"] != "100.0%"):
        raise ReleaseTruthError("QUALITY_RELEASE_INVALID")
    if (set(showcase) != {"url", "source_commit", "revision", "image_digest"} or
            not showcase["url"].startswith("https://") or
            not COMMIT.fullmatch(showcase["source_commit"]) or
            not SHA256.fullmatch(showcase["image_digest"])):
        raise ReleaseTruthError("SHOWCASE_RELEASE_INVALID")
    markers = value["superseded_markers"]
    if not isinstance(markers, list) or not markers or any(
            not isinstance(item, str) or not item for item in markers):
        raise ReleaseTruthError("SUPERSEDED_MARKERS_INVALID")
    return value


def release_summary(value: dict[str, Any]) -> str:
    """Return the canonical terse release sentence for judge-facing prose."""
    app, run, proof, quality, showcase = (value["application"], value["run"], value["proof"],
                                          value["quality"], value["showcase"])
    return (
        f"application `{app['source_commit'][:7]}` · "
        f"{run['required_object_count']} required objects · "
        f"{run['trace_span_count']} correlated spans · offline `{run['offline_verdict']}` · "
        f"{quality['test_count']} tests at {quality['statement_coverage']} statement/branch coverage · "
        f"proof `{proof['release_tag']}` · showcase `{showcase['revision']}`"
    )


def audit_judge_surfaces(root: Path, value: dict[str, Any]) -> tuple[str, ...]:
    """Reject stale facts and require the canonical release identifiers everywhere needed."""
    failures: list[str] = []
    for relative in JUDGE_FACING_PATHS:
        path = root / relative
        if not path.is_file():
            failures.append(f"MISSING_JUDGE_SURFACE:{relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in value["superseded_markers"]:
            if marker in text:
                failures.append(f"SUPERSEDED_RELEASE_FACT:{relative}:{marker}")
    required = {
        "README.md": (value["application"]["source_commit"][:7], value["proof"]["release_tag"],
                      str(value["quality"]["test_count"])),
        "devpost-submission.md": (value["application"]["source_commit"][:7],
                                  value["proof"]["release_tag"],
                                  value["showcase"]["revision"]),
        "docs/HACKATHON_COMPLIANCE.md": (str(value["quality"]["test_count"]),),
        "src/continuum/static/public_showcase.html": (
            value["application"]["source_commit"][:7], value["proof"]["release_tag"]),
    }
    for relative, markers in required.items():
        if not (root / relative).is_file():
            continue
        text = (root / relative).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                failures.append(f"CURRENT_RELEASE_FACT_MISSING:{relative}:{marker}")
    return tuple(sorted(failures))
