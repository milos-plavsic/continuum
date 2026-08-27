#!/usr/bin/env bash
set -euo pipefail

: "${CONTINUUM_IMAGE_AT_DIGEST:?set the immutable Artifact Registry image reference}"

for tool in gcloud openssl uv; do
  command -v "$tool" >/dev/null || {
    echo "$tool is required for Google DSSE signature verification" >&2
    exit 2
  }
done

work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT
provenance_file="$work_dir/provenance.json"
public_key="$work_dir/google-hosted-worker.pub"

gcloud artifacts docker images describe "$CONTINUUM_IMAGE_AT_DIGEST" \
  --show-provenance --format=json >"$provenance_file"

# Extract only the current SLSA v1 envelope, pin Google's published builder
# key, construct the DSSE pre-authentication encoding, and bind the statement's
# subject to the requested immutable image before checking the signature.
uv run python - "$provenance_file" "$work_dir" "$CONTINUUM_IMAGE_AT_DIGEST" <<'PY'
import base64
import json
from pathlib import Path
import sys

EXPECTED_KEY_ID = (
    "projects/verified-builder/locations/global/keyRings/attestor/"
    "cryptoKeys/google-hosted-worker/cryptoKeyVersions/1"
)

source = json.loads(Path(sys.argv[1]).read_text())
output = Path(sys.argv[2])
image = sys.argv[3]
expected_digest = image.rsplit("@sha256:", maxsplit=1)[-1]

occurrences = source.get("provenance_summary", {}).get("provenance", [])
matches = [
    item for item in occurrences
    if "inTotoSlsaProvenanceV1" in item.get("build", {})
]
if len(matches) != 1:
    raise SystemExit("expected exactly one SLSA v1 provenance occurrence")

envelope = matches[0].get("envelope", {})
signatures = envelope.get("signatures", [])
if len(signatures) != 1 or signatures[0].get("keyid") != EXPECTED_KEY_ID:
    raise SystemExit("unexpected Google Hosted Worker signing key")

def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

payload = decode(envelope["payload"])
signature = decode(signatures[0]["sig"])
statement = json.loads(payload)
if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
    raise SystemExit("unexpected SLSA predicate type")
if statement.get("predicate", {}).get("runDetails", {}).get("builder", {}).get("id") != \
        "https://cloudbuild.googleapis.com/GoogleHostedWorker":
    raise SystemExit("unexpected builder identity")
subjects = statement.get("subject", [])
if not any(item.get("digest", {}).get("sha256") == expected_digest for item in subjects):
    raise SystemExit("signed statement does not cover the requested image digest")

payload_type = envelope.get("payloadType", "").encode()
pae = (
    b"DSSEv1 " + str(len(payload_type)).encode() + b" " + payload_type + b" "
    + str(len(payload)).encode() + b" " + payload
)
(output / "pae.bin").write_bytes(pae)
(output / "signature.bin").write_bytes(signature)
PY

gcloud kms keys versions get-public-key 1 \
  --location=global \
  --keyring=attestor \
  --key=google-hosted-worker \
  --project=verified-builder \
  --output-file="$public_key"

verification_output="$(openssl dgst -sha256 -verify "$public_key" \
  -signature "$work_dir/signature.bin" "$work_dir/pae.bin")"
printf '%s\n' "$verification_output"
[[ "$verification_output" == "Verified OK" ]] || {
  echo "Google DSSE signature verification failed" >&2
  exit 1
}
