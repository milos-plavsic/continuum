# Evidence-backed claim matrix

| Claim | Profile | Required evidence | Current repository status |
|---|---|---|---|
| Obligation survives succession | `reference-local` | deterministic scenario and linked contract | Verified by release gate |
| No overlapping executable authority | `reference-local` | epoch-fence denial and successor activation | Verified by tests |
| Revoked memory is filtered before retrieval | `reference-local` | denial with zero candidates examined | Verified by tests |
| One externally observed sandbox effect | `reference-local` | persistent provider reconciliation and redelivery | Verified by tests |
| C0–C6 contract chain | `reference-local` | six artifacts and independent verifier principal | Verified by conformance suite |
| Distinct deployed workload identities | `reference-google-cloud` | Cloud Run service exports and observed token identities | Requires live capture |
| Live Gemini 3.5+ through Google ADK | `reference-google-cloud` | correlated Vertex call and cited proposal | Requires live capture |
| Pub/Sub redelivery with one provider effect | `reference-google-cloud` | publish/log deliveries, durable receipt, provider observation | Requires live capture |
| End-to-end Cloud Observability trace | `reference-google-cloud` | ordered correlated spans from investigation through verification | Requires live capture |

The offline verifier may issue `PASS` only when every mandatory cloud object is
present, content-addressed, and semantically consistent. Missing evidence is
`NOT_ASSESSED`; observed contradiction or mutation is `FAIL`. A local result is
never promoted into the cloud profile.
