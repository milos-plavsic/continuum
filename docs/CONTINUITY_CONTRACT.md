# Continuity Contract Profile 0.1-draft

Status: **open protocol proposal and reference implementation**. It is not an
adopted standard, has no third-party interoperability claim, and must not be
described as tamper-proof or universally exactly-once.

Normative terms **MUST**, **SHOULD**, and **MAY** use their RFC 2119 meanings.
The core is vendor-neutral; Google ADK, Gemini, and Google Cloud belong to the
Continuum reference binding.

## Common envelope

Every artifact carries protocol and immutable schema identifiers, artifact ID,
UTC issuance time, issuer, typed body, required features, namespaced extensions,
SHA-256 content digest, and optional signatures. IDs are opaque URIs and imply
no trust. Unknown required features or protocol versions fail closed.

Every security-relevant JSON value MUST use RFC 8785 JSON Canonicalization
Scheme (`urn:ietf:rfc:8785`). RFC 8785 constrains values to I-JSON, applies
ECMAScript number serialization, sorts properties by UTF-16 code units, and
emits UTF-8. Non-finite numbers, integers outside the interoperable domain,
lone surrogates, and non-string object keys fail closed. The digest input is:

```text
SHA-256("continuum-contract\0continuum/0.1-draft\0" || canonical unsigned envelope)
```

The digest excludes `digest` and `signatures`. It provides content addressing,
not authenticity. Cross-trust-boundary exchange MUST add a trusted asymmetric
signature binding. The reference supports Ed25519 signatures while leaving key
identity, rotation, revocation, and trust policy to the deployment.
Language-neutral conformance vectors are published in
[`fixtures/canonicalization-rfc8785-v1.json`](../fixtures/canonicalization-rfc8785-v1.json).

## Six portable artifacts

1. **Obligation** — immutable revision of institutional intent, owner epoch,
   completion criteria, permitted effects, deadline, and compensation mode.
2. **Authority Grant** — purpose-, tenant-, obligation-, capability-, memory-,
   principal-, epoch-, and time-bounded authority.
3. **Succession Manifest** — predecessor/successor epochs, obligation and grant
   digests, explicit exclusions, in-flight effects, evidence, and policy binding.
4. **Revocation Proof** — observations showing action and memory boundaries
   enforced the fence. It does not claim global credential invalidation.
5. **Execution Receipt** — idempotency/request binding, provider operation,
   disposition, and reconcilable resource reference.
6. **Continuity Attestation** — independently verified chain from obligation to
   policy, revocation, manifest, execution, provider observation, and outcome.

## Authority semantics

Authority is scoped by `(tenant, authority_domain, principal, epoch)`. The
registry maintains one monotonic epoch per `(tenant, authority_domain)` using a
serializable transaction or compare-and-swap. Epochs never decrement or repeat.
Fencing is immediate application authorization; workload credential revocation
is a separate IAM process.

Every governed request carries authenticated principal binding, tenant,
authority domain, epoch, obligation and grant references, decision binding,
trace ID, and an idempotency key for effects. The gateway MUST resolve identity
server-side and deny mismatches before provider access or memory retrieval.

## Separation of duties

```text
Investigator proposes with citations
Policy evaluator authorizes deterministically
Registry fences and transfers authority
Gateway executes through a conforming adapter
Independent verifier observes provider state
Attestor seals the evidence chain
```

An executor cannot issue a `VERIFIED` attestation about its own effect.
Signatures prove signer/content binding; they do not prove that claims are true
or complete.

## Bounded effect guarantee

For effects routed exclusively through a conforming gateway, a stable
idempotency key, canonical request digest, durable execution intent, and
reconcilable provider adapter yield at most one externally observed effect under
the declared failure model. An `UNKNOWN` outcome must be reconciled and must not
be retried blindly.

## Compatibility

Breaking semantic, required-field, or canonicalization changes require a new
major protocol version. Optional compatible features require negotiation through
`required_features`. Unknown top-level and body fields are rejected; extensions
live only in the digested `extensions` map and cannot change base semantics
unless negotiated.

The normative machine-readable envelope is
[`schemas/continuity-contract/0.1/contract.schema.json`](../schemas/continuity-contract/0.1/contract.schema.json).
