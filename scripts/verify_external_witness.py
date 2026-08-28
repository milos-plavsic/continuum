#!/usr/bin/env python3
"""Audit external-witness status or verify one identity-pinned Sigstore statement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.external_witness import validate_review_request, verify_sigstore_statement


def validate_statement_schema(path: Path) -> None:
    schema = json.loads((ROOT / "schemas/external-witness-statement-v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    statement = json.loads(path.read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(statement),
                    key=lambda error: list(error.absolute_path))
    if errors:
        raise ValueError(f"WITNESS_JSON_SCHEMA_INVALID:{errors[0].json_path}:{errors[0].message}")


def audit_registry() -> dict[str, object]:
    registry = json.loads((ROOT / "config/external-witnesses.json").read_text())
    if set(registry) != {"schema", "status", "request", "accepted_witnesses"} or registry["schema"] != "continuum/external-witness-registry/1.0":
        raise ValueError("WITNESS_REGISTRY_SCHEMA_INVALID")
    request = json.loads((ROOT / registry["request"]).read_text())
    validate_review_request(request)
    accepted = registry["accepted_witnesses"]
    if not isinstance(accepted, list):
        raise ValueError("WITNESS_REGISTRY_SCHEMA_INVALID")
    expected = "ATTESTED" if accepted else "AWAITING_EXTERNAL_WITNESS"
    if registry["status"] != expected:
        raise ValueError("WITNESS_REGISTRY_STATUS_INVALID")
    for witness in accepted:
        if set(witness) != {"statement", "bundle", "identity", "issuer"}:
            raise ValueError("WITNESS_REGISTRY_ENTRY_INVALID")
        statement_path = ROOT / witness["statement"]
        validate_statement_schema(statement_path)
        verify_sigstore_statement(
            statement_path=statement_path, bundle_path=ROOT / witness["bundle"],
            request=request, expected_identity=witness["identity"],
            expected_issuer=witness["issuer"])
    return {"status": registry["status"], "accepted_witnesses": len(accepted),
            "request_digest": request["request_digest"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--statement", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--identity")
    parser.add_argument("--issuer")
    args = parser.parse_args()
    values = (args.statement, args.bundle, args.identity, args.issuer)
    try:
        if any(values):
            if not all(values):
                parser.error("--statement, --bundle, --identity and --issuer are required together")
            registry = json.loads((ROOT / "config/external-witnesses.json").read_text())
            request = json.loads((ROOT / registry["request"]).read_text())
            validate_statement_schema(args.statement)
            verified = verify_sigstore_statement(
                statement_path=args.statement, bundle_path=args.bundle, request=request,
                expected_identity=args.identity, expected_issuer=args.issuer)
            output = {"status": "VERIFIED_SIGNATURE", "statement_digest": verified["statement_digest"]}
        else:
            output = audit_registry()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
