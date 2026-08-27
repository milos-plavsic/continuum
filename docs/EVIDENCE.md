# Evidence and incident admission profile

Continuum Evidence Descriptor 1 gives every policy input a closed, versioned
record: evidence ID and type, subject, issuer, source authority, observation and
expiry instants, RFC 8785 payload digest, authentication reference, and trust
policy version. The normative machine-readable shape is
[`schemas/evidence-descriptor-v1.schema.json`](../schemas/evidence-descriptor-v1.schema.json);
the published vector is
[`fixtures/evidence-descriptor-v1.json`](../fixtures/evidence-descriptor-v1.json).

The host—not Gemini—evaluates that record against a versioned allowlist. It
rejects unknown types or issuers, untrusted source authorities or authentication
kinds, stale/future/expired evidence, duplicate IDs, subject mismatch, and
payload substitution with stable reason codes. The resulting validation receipt
binds the ordered records, assessment time, policy, and per-record outcomes.

Incident Policy 1 then correlates trusted signals and emits exactly one of two
admission sets:

- all three trusted compromise signals: succession or operator review;
- anything else: operator review only.

Gemini receives this immutable result and may explain or choose inside that set.
It cannot define the evidence policy, classify the incident, add a remediation,
grant authority, execute an effect, or attest success. The independent verifier
re-parses the exported records and recomputes both receipts before issuing the
sixth artifact.

## Assurance boundary

Digest validation proves integrity and internal linkage. It does not by itself
prove where bytes were captured. Live provenance comes from direct reads by the
separate verifier, Cloud Run workload identities, immutable revision/image
bindings, and Google-signed SLSA subject verification. Claims intentionally keep
these layers separate:

1. schema validity;
2. payload and artifact integrity;
3. semantic agreement with independently read provider state;
4. capture/build provenance from the owning platform.

No archive can promote itself from layers 1–2 to layer 4 merely by being
self-consistent.
