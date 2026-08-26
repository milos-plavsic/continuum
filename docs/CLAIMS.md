# Evidence-backed claim matrix

| Claim | Profile | Required evidence | Current repository status |
|---|---|---|---|
| Obligation survives succession | `reference-local` | deterministic scenario and linked contract | Verified by release gate |
| No overlapping executable authority | `reference-local` | epoch-fence denial and successor activation | Verified by tests |
| Revoked memory is filtered before retrieval | `reference-local` | denial with zero candidates examined | Verified by tests |
| One externally observed sandbox effect | `reference-local` | persistent provider reconciliation and redelivery | Verified by tests |
| C0–C6 contract chain | `reference-local` | six artifacts and independent verifier principal | Verified by conformance suite |
| Distinct deployed workload identities | `reference-google-cloud` | Cloud Run API plus workload-derived actors | Previous run superseded; final-commit recapture required |
| Live Gemini 3.5+ through Google ADK | `reference-google-cloud` | correlated Vertex call and admitted cited plan | Previous run superseded; final-commit recapture required |
| Pub/Sub redelivery causes one provider effect | `reference-google-cloud` | inbox delivery count, lifecycle transition and direct provider read | Fresh final-commit capture required |
| Verifier alone issues artifact six | `reference-google-cloud` | five claims plus read-only authority/compliance/provider reads | Fresh final-commit capture required |
| End-to-end Cloud Trace | `reference-google-cloud` | real OTel spans fetched from the Cloud Trace API | Fresh final-commit capture required |

The offline verifier may issue `PASS` only when every mandatory cloud object is
present, content-addressed, and semantically consistent. Missing evidence is
`NOT_ASSESSED`; observed contradiction or mutation is `FAIL`. A local result is
never promoted into the cloud profile.

The exact deployment identifiers, bundle UUID, report digest, and evidence
retention policy are recorded in [CLOUD_PROOF.md](CLOUD_PROOF.md). Cloud claims
must be recaptured whenever the deployed source commit or image digest changes.
