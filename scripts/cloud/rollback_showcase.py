#!/usr/bin/env python3
"""Fail-closed, dry-run-by-default traffic rollback for the public showcase."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _gcloud(*arguments: str) -> dict[str, Any]:
    result = subprocess.run(
        ["gcloud", *arguments, "--format=json"], check=True, capture_output=True, text=True
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("GCLOUD_RESPONSE_NOT_OBJECT")
    return value


def _current_revision(service: dict[str, Any]) -> str:
    traffic = service.get("status", {}).get("traffic", [])
    exact = [item.get("revisionName") for item in traffic if item.get("percent") == 100]
    if len(exact) == 1 and exact[0]:
        return str(exact[0])
    raise ValueError("CURRENT_TRAFFIC_NOT_EXACTLY_ONE_REVISION")


def _validate_revision(
    revision: dict[str, Any], *, service: str, target: str, expected_identity: str
) -> None:
    metadata = revision.get("metadata", {})
    if metadata.get("name") != target:
        raise ValueError("TARGET_REVISION_IDENTITY_MISMATCH")
    if metadata.get("labels", {}).get("serving.knative.dev/service") != service:
        raise ValueError("TARGET_REVISION_WRONG_SERVICE")
    if revision.get("spec", {}).get("serviceAccountName") != expected_identity:
        raise ValueError("TARGET_REVISION_WRONG_IDENTITY")
    ready = [
        condition for condition in revision.get("status", {}).get("conditions", [])
        if condition.get("type") == "Ready"
    ]
    if len(ready) != 1 or ready[0].get("status") != "True":
        raise ValueError("TARGET_REVISION_NOT_READY")


def _validate_iam(
    service_policy: dict[str, Any], project_policy: dict[str, Any], *, identity: str
) -> None:
    service_bindings = service_policy.get("bindings", [])
    if service_bindings != [{"members": ["allUsers"], "role": "roles/run.invoker"}]:
        raise ValueError("SHOWCASE_SERVICE_IAM_NOT_EXACT")
    member = f"serviceAccount:{identity}"
    if any(member in binding.get("members", []) for binding in project_policy.get("bindings", [])):
        raise ValueError("SHOWCASE_IDENTITY_HAS_PROJECT_ROLE")


def _read_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - fixed Cloud Run URL from gcloud
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("BUILD_INFO_NOT_OBJECT")
    return value


def _wait_for_build_info(url: str, target: str) -> dict[str, Any]:
    last_error = "no response"
    for _ in range(10):
        try:
            value = _read_json(f"{url}/build-info")
            if value.get("role") == "showcase" and value.get("revision") == target:
                return value
            last_error = f"served {value.get('revision')!r}"
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            last_error = str(error)
        time.sleep(2)
    raise ValueError(f"ROLLED_BACK_REVISION_NOT_SERVED:{last_error}")


def _assert_mutation_absent(url: str) -> None:
    request = Request(
        f"{url}/cloud-smoke/start",
        data=b'{"run_id":"rollback-security-probe"}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5):  # noqa: S310 - fixed Cloud Run URL from gcloud
            raise ValueError("SHOWCASE_MUTATION_ROUTE_UNEXPECTEDLY_REACHABLE")
    except HTTPError as error:
        if error.code != 404:
            raise ValueError(f"SHOWCASE_MUTATION_ROUTE_STATUS_{error.code}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a known-good showcase revision and optionally move 100% traffic."
    )
    parser.add_argument("--project", default=os.getenv("CONTINUUM_PROJECT_ID"))
    parser.add_argument("--region", default=os.getenv("CONTINUUM_REGION"))
    parser.add_argument("--service", default="continuum-showcase")
    parser.add_argument("--target-revision", required=True)
    parser.add_argument("--apply", action="store_true", help="perform the traffic update")
    parser.add_argument("--receipt", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.project or not args.region:
        raise ValueError("PROJECT_AND_REGION_REQUIRED")
    if args.service != "continuum-showcase":
        raise ValueError("ONLY_DEDICATED_SHOWCASE_MAY_BE_ROLLED_BACK")
    revision_pattern = rf"^{re.escape(args.service)}-[0-9]{{5}}-[a-z0-9]{{3}}$"
    if not re.fullmatch(revision_pattern, args.target_revision):
        raise ValueError("TARGET_REVISION_FORMAT_INVALID")
    identity = f"continuum-showcase@{args.project}.iam.gserviceaccount.com"
    common = ("--project", args.project, "--region", args.region)
    service_state = _gcloud("run", "services", "describe", args.service, *common)
    target_state = _gcloud("run", "revisions", "describe", args.target_revision, *common)
    _validate_revision(
        target_state, service=args.service, target=args.target_revision,
        expected_identity=identity,
    )
    service_policy = _gcloud(
        "run", "services", "get-iam-policy", args.service, *common
    )
    project_policy = _gcloud("projects", "get-iam-policy", args.project, "--project", args.project)
    _validate_iam(service_policy, project_policy, identity=identity)
    before = _current_revision(service_state)
    url = service_state.get("status", {}).get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("SHOWCASE_URL_INVALID")
    plan = {
        "schema": "continuum/showcase-rollback/1",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "project": args.project,
        "region": args.region,
        "service": args.service,
        "identity": identity,
        "before_revision": before,
        "target_revision": args.target_revision,
        "preflight": {
            "target_belongs_to_service": True,
            "target_ready": True,
            "target_uses_no_role_identity": True,
            "service_iam_exact": True,
            "identity_has_zero_project_roles": True,
        },
    }
    if not args.apply:
        print(json.dumps(plan, indent=2))
        print("DRY RUN ONLY: rerun with --apply to move traffic.", file=sys.stderr)
        return 0
    subprocess.run(
        [
            "gcloud", "run", "services", "update-traffic", args.service,
            "--project", args.project, "--region", args.region,
            "--to-revisions", f"{args.target_revision}=100", "--quiet",
        ],
        check=True,
    )
    build_info = _wait_for_build_info(url, args.target_revision)
    _assert_mutation_absent(url)
    final_service_policy = _gcloud(
        "run", "services", "get-iam-policy", args.service, *common
    )
    final_project_policy = _gcloud(
        "projects", "get-iam-policy", args.project, "--project", args.project
    )
    _validate_iam(final_service_policy, final_project_policy, identity=identity)
    plan.update({
        "status": "PASS",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "served_build_info": build_info,
        "postconditions": {
            "target_served": True,
            "mutation_route_status": 404,
            "service_iam_exact": True,
            "identity_has_zero_project_roles": True,
        },
    })
    receipt = args.receipt or Path(
        f"artifacts/cloud/showcase-rollback-{args.target_revision}.json"
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_suffix(receipt.suffix + ".tmp")
    temporary.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    temporary.replace(receipt)
    print(json.dumps(plan, indent=2))
    print(f"rollback verification receipt: {receipt}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as error:
        print(f"showcase rollback: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
