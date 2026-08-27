# Trust assumptions and proof ceiling

Continuum does not prove that every upstream fact or infrastructure component is
honest. It proves a narrower and useful statement: under the declared trust roots,
the captured objects are content-addressed and semantically consistent with one
governed succession lifecycle.

The normative machine-readable profile is
[`trust-profile.json`](trust-profile.json). It names each trust root, why it is
needed, and what a compromise would invalidate.

## What the accepted verifier can establish

- Every mandatory object matches its recorded digest.
- The named identities, authority epochs, successor, context receipt, provider
  observation and attestation agree.
- The executor did not author the verifier-only sixth artifact.
- The observed provider state contains one effect and the predecessor is denied at
  the demonstrated gateways.

## What it cannot establish by itself

- That a downloaded archive was captured from live cloud APIs rather than assembled
  by another producer. The separately readable Cloud Run identities and Google API
  views are the capture-provenance evidence.
- That GLEIF, VIES, GitHub, Gemini or Google Cloud is uncompromised or factually
  infallible.
- Byzantine consensus, universal exactly-once execution, or correctness outside the
  declared gateway/provider model.

Signatures authenticate bytes and principals; they do not make upstream facts true.
Gemini is an advisory optimizer among policy-eligible candidates, never a trust root
for authority, execution or attestation.
