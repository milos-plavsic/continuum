# Evidence-backed claim matrix

| Claim | Profile | Required evidence | Current repository status |
|---|---|---|---|
| Obligation survives succession | `reference-local` | deterministic scenario and linked contract | Verified by release gate |
| No overlapping executable authority | `reference-local` | epoch-fence denial and successor activation | Verified by tests |
| Revoked memory is filtered before retrieval | `reference-local` | denial with zero candidates examined | Verified by tests |
| One externally observed sandbox effect | `reference-local` | persistent provider reconciliation and redelivery | Verified by tests |
| C0–C6 contract chain | `reference-local` | six artifacts and independent verifier principal | Verified by conformance suite |
| Successor is discovered rather than fixed | `reference-local` | three immutable candidates, deterministic assessment receipt, bounded choice | Verified by selection and lifecycle tests |
| Gemini choice is causal but cannot mint authority | `reference-local` | model ablation, complete evidence manifest, selective claim-linked citations, unknown/ineligible/citation denials | Verified by adversarial tests; admission is not described as proof of model reasoning |
| Incident policy is outside the model | `reference-local` | formal records, trust receipt, incident receipt, immutable allowed-remediation set, verifier recomputation | Verified by truth-table and exported-chain mutation tests |
| Evidence trust and freshness are explicit | `continuum/evidence-descriptor/1` | closed schema, golden vector, stable issuer/source/authentication/time/digest reasons | Verified by exhaustive boundary tests |
| Only minimum authorized context crosses | `reference-local` | reconstruction decisions and verifier-recomputed receipt | Verified for two included and four excluded canonical items |
| Migration-free adoption surface | `continuum-local-sdk/1` | isolated three-call consumer with no Google import or credentials | Verified by subprocess and idempotency tests |
| Second-domain reuse | `continuum-local-sdk/1` | incident-remediation rollback consumer using the same three calls | Verified without procurement or Google dependencies |
| Concurrent one-effect invariant | `continuum/concurrent-stress/1` | 16 obligations, 128 barrier-synchronized attempts, semantic-conflict injection | Verified locally: 16 effects, 112 deduplications, 16 rejected substitutions |
| Complete credential-free lifecycle | `reference-local-container/1` | hardened read-only non-root container reaches independent local verification | Verified by container smoke; not cloud proof |
| Ten declared failure modes are safe or explicit | `resilience-local/1` | distinct input/result digests and measured outcomes | Verified; zero duplicate effects, ambiguity holds |
| Multi-witness evidence aggregation | `optional-witness/1` | distinct principals, same bundle, configured threshold, dissent | Verified locally; explicitly not Byzantine consensus |
| Distinct deployed workload identities | `reference-google-cloud` | Cloud Run API plus workload-derived actors | Verified for release `5e579f4`, including separate v18 and v19 successors |
| Live Gemini 3.5+ through Google ADK | `reference-google-cloud` | correlated Vertex call and admitted cited plan | Verified: `gemini-3.6-flash` selected v18 from the eligible v18/v19 set with exact deployment citations |
| Pub/Sub redelivery causes one provider effect | `reference-google-cloud` | inbox delivery count, lifecycle transition and direct provider read | Verified: one message, two deliveries, one effect |
| Verifier alone issues artifact six | `reference-google-cloud` | five claims plus read-only authority/compliance/provider reads | Verified by separate verifier identity and final bundle |
| Minimum-context cloud succession | `reference-google-cloud` | content-addressed inclusion/exclusion receipt recomputed by verifier | Verified: two included, four excluded before retrieval |
| End-to-end Cloud Trace | `reference-google-cloud` | real OTel spans fetched from the Cloud Trace API | Verified: 124 spans under trace `d9ea0337…` |
| Practical Supplier Assurance Agent | `reference-google-cloud` | official GLEIF and VIES observations, ADK/Gemini decision pack, deterministic admission, one sandbox effect, independent decision-pack binding | Verified in release `5e579f4`: successor identity, source receipts, sandbox scope and decision-pack digest are mandatory offline checks |
| Immutable build subject | `reference-google-cloud` | Google-signed SLSA v1 DSSE statement plus five revision reads | Verified for release `5e579f4`: Google Hosted Worker signature authenticates the image subject; manual source upload is explicitly not claimed as GitHub-source provenance |

The offline verifier may issue `PASS` only when every mandatory cloud object is
present, content-addressed, and semantically consistent. It does not reperform
capture or authenticate Google signatures; build authenticity is a separate
SLSA verification step in [PROVENANCE.md](PROVENANCE.md). Missing evidence is
`NOT_ASSESSED`; observed contradiction or mutation is `FAIL`. A local result is
never promoted into the cloud profile.

The exact deployment identifiers, bundle UUID, report digest, and evidence
retention policy are recorded in [CLOUD_PROOF.md](CLOUD_PROOF.md). Cloud claims
must be recaptured whenever the deployed source commit or image digest changes.
The golden-standard cloud claims—v19 warm-successor identity, dynamic bounded
selection, reconstruction receipt and supplier decision pack—are covered by the exact-commit `5e579f4`
capture. They do not transfer to a newer deployment without recapture.
