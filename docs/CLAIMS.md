# Evidence-backed claim matrix

| Claim | Profile | Required evidence | Current repository status |
|---|---|---|---|
| Obligation survives succession | `reference-local` | deterministic scenario and linked contract | Verified by release gate |
| No overlapping executable authority | `reference-local` | epoch-fence denial and successor activation | Verified by tests |
| Revoked memory is filtered before retrieval | `reference-local` | denial with zero candidates examined | Verified by tests |
| One externally observed sandbox effect | `reference-local` | persistent provider reconciliation and redelivery | Verified by tests |
| C0–C6 contract chain | `reference-local` | six artifacts and independent verifier principal | Verified by conformance suite |
| Successor is discovered rather than fixed | `reference-local` | three immutable candidates, deterministic assessment receipt, bounded choice | Verified by selection and lifecycle tests |
| Gemini choice is causal but cannot mint authority | `reference-local` | model ablation plus unknown/ineligible/citation denials | Verified by adversarial tests |
| Only minimum authorized context crosses | `reference-local` | reconstruction decisions and verifier-recomputed receipt | Verified for two included and four excluded canonical items |
| Migration-free adoption surface | `continuum-local-sdk/1` | isolated three-call consumer with no Google import or credentials | Verified by subprocess and idempotency tests |
| Ten declared failure modes are safe or explicit | `resilience-local/1` | distinct input/result digests and measured outcomes | Verified; zero duplicate effects, ambiguity holds |
| Multi-witness evidence aggregation | `optional-witness/1` | distinct principals, same bundle, configured threshold, dissent | Verified locally; explicitly not Byzantine consensus |
| Distinct deployed workload identities | `reference-google-cloud` | Cloud Run API plus workload-derived actors | Verified for release `0ceda49`, including separate v18 and v19 successors |
| Live Gemini 3.5+ through Google ADK | `reference-google-cloud` | correlated Vertex call and admitted cited plan | Verified: `gemini-3.6-flash` selected v18 from the eligible v18/v19 set with exact deployment citations |
| Pub/Sub redelivery causes one provider effect | `reference-google-cloud` | inbox delivery count, lifecycle transition and direct provider read | Verified: one message, two deliveries, one effect |
| Verifier alone issues artifact six | `reference-google-cloud` | five claims plus read-only authority/compliance/provider reads | Verified by separate verifier identity and final bundle |
| Minimum-context cloud succession | `reference-google-cloud` | content-addressed inclusion/exclusion receipt recomputed by verifier | Verified: two included, four excluded before retrieval |
| End-to-end Cloud Trace | `reference-google-cloud` | real OTel spans fetched from the Cloud Trace API | Verified: 104 spans under trace `caa315c2…` |
| Practical Supplier Assurance Agent | `reference-google-cloud-next` | official GLEIF and VIES observations, ADK/Gemini decision pack, deterministic admission, one sandbox effect, independent decision-pack binding | Implemented with 100% local branch coverage; cloud claim intentionally pending fresh exact-commit deployment and capture |

The offline verifier may issue `PASS` only when every mandatory cloud object is
present, content-addressed, and semantically consistent. Missing evidence is
`NOT_ASSESSED`; observed contradiction or mutation is `FAIL`. A local result is
never promoted into the cloud profile.

The exact deployment identifiers, bundle UUID, report digest, and evidence
retention policy are recorded in [CLOUD_PROOF.md](CLOUD_PROOF.md). Cloud claims
must be recaptured whenever the deployed source commit or image digest changes.
The golden-standard cloud claims—v19 warm-successor identity, dynamic bounded
selection and reconstruction receipt—are covered by the exact-commit `0ceda49`
capture. They do not transfer to a newer deployment without recapture.
