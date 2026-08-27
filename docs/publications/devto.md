---
title: "The Agent Failed. The Promise Did Not: Building Verifiable Agent Succession"
published: true
description: "How Continuum carries obligations across autonomous-agent failure without transferring stale authority, poisoned context, or duplicate effects."
tags: ai, googlecloud, agents, security
cover_image: "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/ln4arpyalu3p8hfu9jq2.png"
---

Published at: https://dev.to/milos-plavsic/the-agent-failed-the-promise-did-not-building-verifiable-agent-succession-oe4

This article was created for the purpose of entering the **All Things Agentic Hackathon**.

Autonomous agents are increasingly trusted with work that outlives one model
call: onboarding a supplier, renewing a contract, gathering compliance
evidence, or completing a regulated handoff. Those workflows create an awkward
question. What happens when the agent disappears, is compromised, or must be
replaced while the obligation remains real?

Restarting is not continuity. A durable queue can still replay an effect. A
persistent memory can preserve revoked or poisoned context. A new agent can
overlap authority with its predecessor. And an executor that verifies its own
success has produced an assertion, not independent evidence.

I built [Continuum](https://github.com/milos-plavsic/continuum) to make that
boundary explicit.

## The vertical slice

The reference incident is a synthetic €250,000 supplier-onboarding obligation.
The agent expects compliance evidence before a persisted deadline. Nothing
arrives—and, importantly, no explicit failure event appears.

Cloud Tasks crosses the real deadline. The Negative Space Sentinel converts the
absence into an append-only event, and Pub/Sub deliberately redelivers it after
the first delivery fails. A deterministic eligibility gate evaluates three
deployed successor records across health, capability, jurisdiction, contract
compatibility, scope, and trust.

Only eligible candidates reach Google ADK and Gemini 3.6 Flash. Gemini must cite
the incident and candidate evidence, and its choice is causal: it determines
which eligible workload is proposed for activation. But the model is not an
authority boundary. Deterministic policy independently validates the result,
advances the authority epoch with compare-and-swap semantics, and fences the
predecessor.

The successor receives a minimum-context receipt. Verified facts cross the
boundary; raw prompt injection, a secret, unsupported model inference, and
revoked memory do not. The action gateway checks workload identity, current
epoch, policy, compliance evidence, context receipt, request digest, and
idempotency in one Firestore transaction. Two deliveries produce one observed
provider effect under the demonstrated failure model.

## Verification belongs outside execution

Continuum exports five content-addressed control artifacts: the obligation,
authority grant, succession manifest, revocation proof, and execution receipt.
A separately deployed Cloud Run verifier has a distinct read-only identity. It
recomputes digests and directly reads authority, compliance, and provider state.
Only that verifier may issue artifact six: `VERIFIED`, `FAILED`, or
`INCONCLUSIVE`.

This three-valued result matters. Missing provider truth is not success, but it
is not necessarily proof of failure either. `INCONCLUSIVE` holds further
learning and consequential claims until evidence exists.

The accepted cloud run binds one immutable image to five private Cloud Run
revisions, distinct workload identities, Firestore state, deliberate Pub/Sub
redelivery, one provider effect, predecessor denial, and 104 correlated
OpenTelemetry spans. The proof packet is downloadable and can be checked
without Google credentials.

## Learning without letting media rewrite history

Post-incident learning created a second design problem. Multimodal output can be
useful for human training, but generated media must not drift back into the
control plane as authority or evidence.

The Antibody Foundry therefore starts only from a verifier-issued `VERIFIED`
bundle. It reduces that bundle to five bounded, non-sensitive facts. Gemma 4
creates a structured lesson, regression test, video prompt, and music prompt,
and must cite every fact exactly once. Deterministic admission rejects missing
citations, extra fields, oversized text, or sensitive prompt terms.

Only then are the admitted prompts sent to Veo 3.1 Lite and Lyria 3. Their
outputs are stored under the same request digest with create-only,
content-addressed naming. The final receipt is marked
`DERIVED_NOT_AUTHORITY_OR_EVIDENCE`. The branch can explain what happened; it
cannot select a successor, grant authority, execute an action, or attest the
outcome it depicts.

That causal sequence is the important part. Gemma, Veo, and Lyria are not three
decorative API calls. Each downstream request exists only because the same
independently verified incident passed the prior boundary.

## Production discipline in a hackathon build

The public repository includes a cloud-neutral three-call SDK and portable
Continuity Contract, so adopting the protocol does not require moving a domain
model to Google Cloud. Google Cloud is the reference binding and the source of
deployment evidence, not a portability claim.

The complete quality gate runs in GitHub Actions, executes 151 tests, enforces
genuine 100.0% statement and branch coverage without exclusions, runs C0–C6
contract conformance, checks release invariants, rejects committed credentials
or generated cloud state, and builds the non-root container image.

Equally important are the limits. The provider effect is a controlled Firestore
sandbox record, not a third-party procurement API. The project proves one
regional reference profile, not Byzantine consensus, universal exactly-once
execution, or third-party interoperability. The Continuity Contract is a
proposal, not an adopted standard.

## What I learned

Persistence is not memory, and memory is not continuity. Continuity requires an
explicit separation between institutional obligation, model recommendation,
authority, execution, and independent verdict.

I also learned that bounded AI is often more convincing than performative
autonomy. Gemini changes the outcome, but deterministic gates constrain what it
is allowed to change. Gemma, Veo, and Lyria make verified learning more legible,
but cannot rewrite operational truth.

The long-term ambition is straightforward: make safe succession a normal
property of serious agent systems. And if a better-founded standard eventually
replaces this proposal, that would be success. Even standards should have
succession plans.

- [Live read-only showcase](https://continuum-showcase-rdzvxiysbq-ew.a.run.app)
- [Source, architecture, tests, and proof](https://github.com/milos-plavsic/continuum)
- [Verifier-gated Gemma, Veo, and Lyria proof](https://github.com/milos-plavsic/continuum/releases/tag/multimodal-proof-8bec862)
