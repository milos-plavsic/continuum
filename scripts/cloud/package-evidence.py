#!/usr/bin/env python3
"""Build a content-addressed, offline-verifiable cloud evidence bundle."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from continuum.contract import canonical_bytes

NON_CLAIMS = ["global_credential_revocation", "tamper_proof",
              "third_party_interoperability", "universal_exactly_once"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def package(source: Path, destination: Path, *, project: str, region: str,
            run_id: str, trace_id: str, git_commit: str) -> dict:
    if source.resolve() == destination.resolve():
        raise ValueError("source and destination must differ")
    destination.mkdir(parents=True, exist_ok=True)
    objects_dir = destination / "objects"
    objects_dir.mkdir(exist_ok=True)
    objects = []
    for path in sorted(source.glob("*.json")):
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        target = objects_dir / digest
        if not target.exists():
            shutil.copyfile(path, target)
        objects.append({"object_id": path.stem, "kind": "captured_json",
                        "source_authority": _authority(path.stem),
                        "media_type": "application/json", "sha256": digest,
                        "size": len(data), "collected_at": _now()})
    bundle = {"schema": "continuum/cloud-evidence/0.1",
              "bundle_id": f"urn:uuid:{uuid4()}", "captured_at": _now(),
              "profile": "reference-google-cloud",
              "scope": {"project_id": project, "region": region, "run_id": run_id,
                        "trace_id": trace_id, "git_commit": git_commit,
                        "protocol": "continuum/0.1-draft"},
              "collector": {"name": "continuum-cloud-evidence", "version": "0.1",
                            "started_at": _now(), "finished_at": _now()},
              "objects": objects, "collection_errors": [],
              "declared_non_claims": NON_CLAIMS}
    digest = sha256(b"continuum-cloud-evidence\x000.1\x00" + canonical_bytes(bundle)).hexdigest()
    bundle["bundle_digest"] = {"alg": "sha-256", "value": digest}
    (destination / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle


def _authority(object_id: str) -> str:
    if object_id.startswith(("cloud-run-", "firestore-", "artifact-", "enabled-services", "iam-policy")):
        return "GOOGLE_API"
    if object_id.startswith(("pubsub-deliveries", "vertex-call", "trace-export")):
        return "CLOUD_LOG_EXPORT"
    return "APP_RESPONSE"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path); parser.add_argument("destination", type=Path)
    parser.add_argument("--project", required=True); parser.add_argument("--region", required=True)
    parser.add_argument("--run-id", required=True); parser.add_argument("--trace-id", required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    package(args.source, args.destination, project=args.project, region=args.region,
            run_id=args.run_id, trace_id=args.trace_id, git_commit=args.git_commit)


if __name__ == "__main__":
    main()
