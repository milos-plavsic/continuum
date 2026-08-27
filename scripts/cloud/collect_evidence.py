#!/usr/bin/env python3
"""Read-only collection of one cloud run's verifier-ready evidence objects."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from typing import Any, NamedTuple, Protocol, Sequence


RUN_SERVICES = {
    "cloud-run-control": ("control", "continuum-control"),
    "cloud-run-v17": ("agent-v17", "continuum-agent-v17"),
    "cloud-run-v18": ("agent-v18", "continuum-agent-v18"),
    "cloud-run-v19": ("agent-v19", "continuum-agent-v19"),
    "cloud-run-verifier": ("verifier", "continuum-verifier"),
}
RUN_OBJECTS = (
    "firestore-event", "firestore-projection", "firestore-outbox",
    "pubsub-publish", "pubsub-deliveries", "vertex-call",
    "supplier-assurance", "contract-export",
    "model-armor", "external-work-item",
)


class CommandRunner(Protocol):
    def json(self, argv: Sequence[str]) -> Any: ...


class TraceReader(Protocol):
    def read(self, scope: "CaptureScope") -> dict[str, Any]: ...


class GoogleTraceReader:
    """Read the exact trace through the owning Cloud Trace API."""
    def read(self, scope: "CaptureScope") -> dict[str, Any]:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError
        from google.auth.transport.requests import AuthorizedSession
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/trace.readonly"])
        except DefaultCredentialsError:
            from google.oauth2.credentials import Credentials
            token = subprocess.run(
                ["gcloud", "auth", "print-access-token"], check=True,
                capture_output=True, text=True).stdout.strip()
            if not token:
                raise ValueError("GCLOUD_ACCESS_TOKEN_MISSING")
            credentials = Credentials(token=token)
        response = AuthorizedSession(credentials).get(
            f"https://cloudtrace.googleapis.com/v1/projects/{scope.project}/traces/{scope.trace_id}",
            timeout=30)
        response.raise_for_status()
        trace = response.json()
        if trace.get("traceId") != scope.trace_id:
            raise ValueError("TRACE_ID_MISMATCH")
        return {"run_id": scope.run_id, "trace_id": trace["traceId"],
                "spans": trace.get("spans", []), "source": "cloud-trace-api"}


class SubprocessRunner:
    """Command runner with no shell and no credential material in arguments."""

    def json(self, argv: Sequence[str]) -> Any:
        completed = subprocess.run(argv, check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)


class CaptureScope(NamedTuple):
    project: str
    region: str
    run_id: str
    trace_id: str


def _env(container: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in container.get("env", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("value"), str):
            values[item["name"]] = item["value"]
    return values


def _ready(service: dict[str, Any]) -> bool:
    conditions = service.get("status", {}).get("conditions", [])
    return any(item.get("type") == "Ready" and item.get("status") == "True"
               for item in conditions if isinstance(item, dict))


def _run_object(scope: CaptureScope, role: str, service: dict[str, Any],
                revision: dict[str, Any]) -> dict[str, Any]:
    template = service.get("spec", {}).get("template", {}).get("spec", {})
    containers = template.get("containers", [])
    container = containers[0] if isinstance(containers, list) and containers else {}
    env = _env(container if isinstance(container, dict) else {})
    image_reference = revision.get("status", {}).get("imageDigest")
    digest = image_reference
    if isinstance(digest, str) and "@sha256:" in digest:
        digest = digest.rsplit("@", 1)[1]
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ValueError("ready revision did not expose an immutable image digest")
    identity = template.get("serviceAccountName")
    if not isinstance(identity, str) or not identity:
        raise ValueError("service has no user-managed service identity")
    service_name = service.get("metadata", {}).get("name")
    revision_name = revision.get("metadata", {}).get("name")
    if not isinstance(service_name, str) or not service_name:
        raise ValueError("service name unavailable")
    if not isinstance(revision_name, str) or not revision_name:
        raise ValueError("ready revision name unavailable")
    return {
        "project_id": scope.project,
        "region": scope.region,
        "service": service_name,
        "revision": revision_name,
        "role": role,
        "ready": _ready(service),
        "service_account": identity,
        "image_digest": digest,
        "image_reference": image_reference,
        "build_info": {
            "git_commit": env.get("GIT_SHA", ""),
            "protocol": env.get("CONTINUUM_PROTOCOL", ""),
        },
    }


def _service_command(scope: CaptureScope, service_name: str) -> list[str]:
    return ["gcloud", "run", "services", "describe", service_name,
            "--project", scope.project, "--region", scope.region, "--format=json"]


def _log_command(scope: CaptureScope, object_id: str) -> list[str]:
    # Exact equality predicates prevent cross-run evidence mixing.
    query = (f'resource.type="cloud_run_revision" AND '
             f'jsonPayload.continuum_evidence.run_id="{scope.run_id}" AND '
             f'jsonPayload.continuum_evidence.object_id="{object_id}"')
    return ["gcloud", "logging", "read", query, "--project", scope.project,
            "--limit=2", "--order=desc", "--format=json"]


def _provenance_command(scope: CaptureScope, image_reference: str) -> list[str]:
    return ["gcloud", "artifacts", "docker", "images", "describe", image_reference,
            "--project", scope.project, "--show-provenance", "--format=json"]


def _logged_payload(entries: Any, scope: CaptureScope, object_id: str) -> dict[str, Any] | None:
    if not isinstance(entries, list) or not entries:
        return None
    matches: list[dict[str, Any]] = []
    for entry in entries:
        evidence = entry.get("jsonPayload", {}).get("continuum_evidence", {}) if isinstance(entry, dict) else {}
        if evidence.get("run_id") == scope.run_id and evidence.get("object_id") == object_id:
            payload = evidence.get("payload")
            if isinstance(payload, dict):
                matches.append(payload)
    if not matches:
        return None
    if len(matches) > 1 and matches[0] != matches[1]:
        raise ValueError("conflicting observations for the same run and object")
    return matches[0]


def collect(scope: CaptureScope, destination: Path, runner: CommandRunner,
            *, services: dict[str, tuple[str, str]] | None = None,
            trace_reader: TraceReader | None = None) -> dict[str, Any]:
    """Collect available objects; never invent a missing observation."""
    destination.mkdir(parents=True, exist_ok=True)
    service_map = services or RUN_SERVICES
    captured: list[str] = []
    unavailable: dict[str, str] = {}
    image_references: set[str] = set()
    for object_id, (role, service_name) in service_map.items():
        try:
            service = runner.json(_service_command(scope, service_name))
            revision_name = service.get("status", {}).get("latestReadyRevisionName")
            if not isinstance(revision_name, str) or not revision_name:
                raise ValueError("service has no latest ready revision")
            revision = runner.json([
                "gcloud", "run", "revisions", "describe", revision_name,
                "--project", scope.project, "--region", scope.region, "--format=json",
            ])
            run_object = _run_object(scope, role, service, revision)
            image_references.add(run_object["image_reference"])
            _write(destination, object_id, run_object)
            captured.append(object_id)
        except (KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            unavailable[object_id] = type(exc).__name__
    try:
        if len(image_references) != 1:
            raise ValueError("deployed services do not share exactly one immutable image")
        image_reference = next(iter(image_references))
        provenance = runner.json(_provenance_command(scope, image_reference))
        if (not isinstance(provenance, dict)
                or not provenance.get("provenance_summary", {}).get("provenance")):
            raise ValueError("signed build provenance unavailable")
        _write(destination, "build-provenance", provenance)
        captured.append("build-provenance")
    except (KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        unavailable["build-provenance"] = type(exc).__name__
    for object_id in RUN_OBJECTS:
        try:
            payload = _logged_payload(runner.json(_log_command(scope, object_id)), scope, object_id)
            if payload is None:
                unavailable[object_id] = "not_observed"
                continue
            _write(destination, object_id, payload)
            captured.append(object_id)
        except (KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            unavailable[object_id] = type(exc).__name__
    try:
        trace = (trace_reader or GoogleTraceReader()).read(scope)
        _write(destination, "trace-export", trace)
        captured.append("trace-export")
    except Exception as exc:
        unavailable["trace-export"] = type(exc).__name__
    report = {"schema": "continuum/cloud-evidence-capture/0.1",
              "read_only": True, "run_id": scope.run_id,
              "captured": sorted(captured), "unavailable": unavailable}
    (destination / ".capture-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _write(destination: Path, object_id: str, value: dict[str, Any]) -> None:
    (destination / f"{object_id}.json").write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--retry-seconds", type=float, default=2.0)
    for object_id, (_, default) in RUN_SERVICES.items():
        parser.add_argument(f"--{object_id.removeprefix('cloud-run-')}-service", default=default)
    args = parser.parse_args()
    services = {object_id: (role, getattr(args, f"{object_id.removeprefix('cloud-run-').replace('-', '_')}_service"))
                for object_id, (role, _) in RUN_SERVICES.items()}
    if args.attempts < 1 or args.retry_seconds < 0:
        raise SystemExit("attempts must be positive and retry-seconds non-negative")
    scope = CaptureScope(args.project, args.region, args.run_id, args.trace_id)
    runner = SubprocessRunner()
    for attempt in range(args.attempts):
        report = collect(scope, args.destination, runner, services=services)
        if not report["unavailable"] or attempt + 1 == args.attempts:
            break
        time.sleep(args.retry_seconds)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
