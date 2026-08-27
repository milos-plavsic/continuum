# Evidence and build provenance

Continuum separates three assurance questions that are often collapsed into
one word, “proof”.

1. **Content integrity** — the offline verifier recomputes every object and
   bundle digest.
2. **Semantic consistency** — it cross-checks run, trace, service identity,
   revision, image, event, delivery, effect, selection, and contract links.
3. **Capture and build provenance** — Google APIs identify live resources;
   Cloud Build emits a signed SLSA v1 DSSE statement for the immutable image.

An offline `PASS` answers only the first two questions. It does not reperform
the Google API reads and cannot prove that a self-contained archive was captured
from the cloud. Its report therefore says
`evidence_capture_not_reperformed: true` and marks capture provenance
`NOT_REPERFORMED`.

## Trusted build path

[`deploy/cloudbuild.yaml`](../deploy/cloudbuild.yaml) publishes through the
Cloud Build `images` field and requests `VERIFIED` provenance. Deployment
resolves the tag to a digest, refuses missing provenance, and deploys that
digest—not a mutable tag—to all five Cloud Run services. The collector reads
each ready revision from the Cloud Run API and captures Artifact Registry's
`provenance_summary`. Offline verification decodes the SLSA v1 subject and
requires it to equal the one digest reported by every revision.

Signature authenticity is independently reproducible with the official SLSA
verifier; it is not implied by the offline semantic check. The repository wraps
the official command without weakening its source or builder checks:

```bash
export CONTINUUM_IMAGE_AT_DIGEST="$IMAGE_AT_DIGEST"
export CONTINUUM_EXPECTED_SOURCE_URI="$EXPECTED_SOURCE_URI"
bash scripts/cloud/verify-build-provenance.sh
```

The strongest live demonstration is the conjunction of five independently read
Cloud Run revision/identity records, one shared immutable image digest, the
Google-signed SLSA statement for that digest, exact-run Firestore/Logging/Trace
reads, and an independently issued continuity attestation. No single object
proves the entire system claim.
