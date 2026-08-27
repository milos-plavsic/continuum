# Supplier Assurance & Onboarding Agent

## User outcome

A procurement operator supplies one onboarding goal. The agent validates the
legal entity and EU VAT identifier, assesses the bounded supplier packet,
produces a cited decision pack, and—only after deterministic policy admission—
creates one sandbox vendor record. Continuum preserves that useful workflow if
the active agent fails, is compromised, or loses authority midway through it.

## Canonical judge scenario

The on-camera application uses public identifiers for Siemens
Aktiengesellschaft solely to demonstrate official GLEIF and VIES lookups. Every
other application statement is synthetic, the scope is `SANDBOX_ONLY`, no
message is sent to the company, and no real procurement relationship is claimed
or created.

The workflow is:

1. Preserve the supplier-assurance obligation and exact application digest.
2. Detect the expected event that did not arrive.
3. Investigate the compromised predecessor and select an eligible successor.
4. Fence v17 and transfer only the obligation plus application provenance.
5. Read the exact LEI record from GLEIF and exact VAT result from EU VIES.
6. Hash both normalized tool observations.
7. Invoke Gemini 3.6 through Google ADK to produce a structured, cited decision.
8. Independently admit or hold that model output with deterministic checks.
9. Persist the admitted decision-pack digest through the selected workload identity.
10. Execute and reconcile one idempotent Firestore sandbox vendor creation.
11. Independently read authority, supplier-assurance, and provider state before
    issuing the Continuity Attestation.

## Authority boundary

Gemini can compare evidence, explain risk, and recommend `ONBOARD` or `HOLD`.
It cannot approve succession, grant capabilities, widen memory, execute a tool
with side effects, or attest success. External registry calls are read-only.
The action gateway accepts only a selected, active service identity at the
current epoch with matching policy, application, decision-pack, context, and
idempotency bindings.

## Failure behavior

- GLEIF or VIES unavailable: hold; no onboarding effect.
- LEI, legal name, or country mismatch: hold.
- Invalid VAT result: hold.
- Missing control or citation: hold.
- Duplicate or substituted evidence reference: hold.
- Model recommendation contradicts a tool result: hold.
- Real-world scope requested by the demo packet: hold.
- Stale predecessor attempts action or memory: deny before retrieval/execution.
- Duplicate delivery: reconcile the prior sandbox effect; do not repeat it.
- Missing or contradictory verifier reads: `INCONCLUSIVE` or `FAILED`, never
  `VERIFIED`.

## Official read-only sources

- GLEIF API: `https://api.gleif.org/api/v1/lei-records/{lei}`
- European Commission VIES:
  `https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number`

No credentials are embedded for either source. Cloud workloads use Application
Default Credentials only for Google resources.
