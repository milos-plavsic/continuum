# Evidence-backed claim matrix

| Claim | Profile | Required evidence | Current repository status |
|---|---|---|---|
| Obligation survives succession | `reference-local` | deterministic scenario and linked contract | Verified by release gate |
| No overlapping executable authority | `reference-local` | epoch-fence denial and successor activation | Verified by tests |
| Revoked memory is filtered before retrieval | `reference-local` | denial with zero candidates examined | Verified by tests |
| One externally observed sandbox effect | `reference-local` | persistent provider reconciliation and redelivery | Verified by tests |
| C0–C6 contract chain | `reference-local` | six artifacts and independent verifier principal | Verified by conformance suite |
| Distinct deployed workload identities | `reference-google-cloud` | Cloud Run service exports and observed token identities | Verified by canonical run `run-20260825T233359Z` |
| Live Gemini 3.5+ through Google ADK | `reference-google-cloud` | correlated Vertex call and cited proposal | Verified with `gemini-3.6-flash` in the canonical run |
| Pub/Sub redelivery with one provider effect | `reference-google-cloud` | publish/log deliveries, durable receipt, provider observation | Verified by two deliveries and one effect receipt in the canonical run |
| End-to-end Cloud Observability trace | `reference-google-cloud` | ordered correlated spans from investigation through verification | Verified by correlated trace export in the canonical run |

The offline verifier may issue `PASS` only when every mandatory cloud object is
present, content-addressed, and semantically consistent. Missing evidence is
`NOT_ASSESSED`; observed contradiction or mutation is `FAIL`. A local result is
never promoted into the cloud profile.

The exact deployment identifiers, bundle UUID, report digest, and evidence
retention policy are recorded in [CLOUD_PROOF.md](CLOUD_PROOF.md). Cloud claims
must be recaptured whenever the deployed source commit or image digest changes.
