# External witness protocol

The current Google Cloud packet is first-party evidence. Its offline verifier recomputes
digests and checks declared semantic relationships, but cannot prove who captured the API
responses or that the infrastructure was uncompromised. Continuum therefore treats an
external witness as a separate, optional assurance profile—not as decorative approval.

Current status: **AWAITING_EXTERNAL_WITNESS**.

## Reviewer procedure

1. Read `docs/review/external-witness-request.json`, verify its `request_digest`, and
   download the exact `cloud-proof-d4d7d52` archive from the public release.
2. Verify the archive SHA-256 before extracting it. Run its credential-free verifier from
   a clean checkout, then mutate at least one mandatory object and confirm fail-closed output.
3. Complete a statement matching `schemas/external-witness-statement-v1.schema.json`.
   Every assessed claim needs its own status, finding and evidence references. Capture
   provenance should remain `NOT_ASSESSED` unless the reviewer has independent evidence.
4. Compute `statement_digest` over strict canonical JSON with that field omitted.
5. Sign the exact statement with Sigstore keyless signing:

   ```bash
   cosign sign-blob statement.json --bundle statement.sigstore.json
   ```

6. Send the statement, Sigstore bundle, exact certificate identity and OIDC issuer for
   maintainer review. The verifier pins both values; it does not trust identity text inside
   the statement by itself.

## Verification

```bash
uv run --extra test --extra signatures python scripts/verify_external_witness.py \
  --statement statement.json \
  --bundle statement.sigstore.json \
  --identity 'EXPECTED_FULCIO_CERTIFICATE_IDENTITY' \
  --issuer 'EXPECTED_OIDC_ISSUER'
```

The command first validates exact subject, scope, conflicts, timestamps and canonical digest,
then invokes `cosign verify-blob` with pinned identity and issuer. Cosign verifies the Fulcio
certificate and transparency bundle. A failed or expired statement cannot enter the registry.

Acceptance is a governance action: add the reviewed files and identity policy to
`config/external-witnesses.json` in a pull request, run all required checks, and record the
reviewer's relationship accurately. A locally generated fixture, maintainer signature,
GitHub CI run, or internal verifier verdict can never change status to `ATTESTED`.

Even an accepted witness proves only the reviewer's bounded statement over this exact request.
It is not Byzantine consensus, formal certification, standards adoption, legal advice, or a
guarantee that every declared trust root was uncompromised.
