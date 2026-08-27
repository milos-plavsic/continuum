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

Signature authenticity is not implied by the offline semantic check. The
repository provides two deliberately separate checks. First, the official SLSA
verifier checks signature, builder and source together and succeeds only when
its output contains an explicit terminal `PASSED` (not merely process status
zero):

```bash
export CONTINUUM_IMAGE_AT_DIGEST="$IMAGE_AT_DIGEST"
export CONTINUUM_EXPECTED_SOURCE_URI="$EXPECTED_SOURCE_URI"
bash scripts/cloud/verify-build-provenance.sh
```

Cloud Build jobs started from a connected GitHub trigger carry a GitHub
`buildConfigSource` and can satisfy that complete check. A manual
`gcloud builds submit` instead records the exact uploaded Cloud Storage tarball;
it does **not** cryptographically establish that the tarball came from the named
GitHub commit. For that path, the following narrower check independently fetches
Google's pinned Hosted Worker public key, reconstructs the DSSE PAE bytes,
requires a SLSA v1 statement whose subject is the requested image digest, and
verifies the signature with OpenSSL:

```bash
export CONTINUUM_IMAGE_AT_DIGEST="$IMAGE_AT_DIGEST"
bash scripts/cloud/verify-google-build-signature.sh
```

That result authenticates Google's builder statement and its immutable image
subject. It is not relabelled as GitHub-source provenance. A release claiming
cryptographic GitHub-to-image provenance must be built by the connected trigger
and pass the first command against `github.com/milos-plavsic/continuum`.

The strongest live demonstration is the conjunction of five independently read
Cloud Run revision/identity records, one shared immutable image digest, the
Google-signed SLSA statement for that digest, exact-run Firestore/Logging/Trace
reads, and an independently issued continuity attestation. No single object
proves the entire system claim.
