# LinkedIn post

Published at: https://www.linkedin.com/feed/update/urn:li:share:7498513309642616832/

What happens when an autonomous agent fails halfway through an obligation that
the organization still has to keep?

Most recovery systems restart a process. They do not prove that the obligation
survived, that the old agent lost authority, that poisoned context stayed
behind, or that a retried action happened only once.

I built **Continuum** for that gap.

In one live Google Cloud workflow, Continuum detects missing evidence rather
than waiting for an explicit crash, uses Google ADK and Gemini 3.6 to select an
eligible successor from deployment-backed candidates, fences the predecessor,
reconstructs only authorized context, survives deliberate Pub/Sub redelivery,
and completes one provider effect. A separately deployed read-only verifier—not
the executor—then issues `VERIFIED`, `FAILED`, or `INCONCLUSIVE`.

The signature moment is deliberately simple:

**The agent failed. The promise did not.**

I also added a verifier-gated learning branch. Only a genuinely verified result
can reach Gemma 4; its cited plan must pass deterministic admission before Veo
3.1 and Lyria 3 render a content-addressed resilience brief. That media is
explicitly derivative: it can explain an incident, but can never become
authority or evidence.

Continuum is a new implementation for the All Things Agentic Hackathon. I hope
its Continuity Contract can eventually contribute to a practical standard for
safe agent succession—and be replaced when a demonstrably stronger standard
earns that right. Even standards should have succession plans.

Live showcase: https://continuum-showcase-rdzvxiysbq-ew.a.run.app

Repository and reproducible cloud proof:
https://github.com/milos-plavsic/continuum

Verifier-gated Gemma, Veo, and Lyria proof:
https://github.com/milos-plavsic/continuum/releases/tag/multimodal-proof-8bec862

#AllThingsAgenticHackathon #GoogleCloud #Gemini #AgenticAI #AISafety

## Demo reveal post

Published at: https://www.linkedin.com/feed/update/urn:li:share:7498526232247169024/

Image: `docs/submission/continuum-devpost-thumbnail.png`

Alt text: Continuum: a verified promise crosses a fortified bridge from a
failed predecessor agent to a secured successor agent.

Most agent demos begin with: “Assume the agent works.”

I started with the opposite.

Continuum is now live on Devpost. It is a continuity protocol for obligations
that outlive the autonomous agent assigned to them.

In one canonical Google Cloud run, a predecessor misses required evidence.
Continuum detects the absence, uses Google ADK and Gemini 3.6 to choose an
eligible successor, fences the old identity, transfers only authorized context,
survives deliberate Pub/Sub redelivery, and still produces one external effect.
A separate read-only verifier—not the executor—issues the final verdict.

The agent failed. The promise did not.

Built as a new implementation for the All Things Agentic Hackathon, with an
intentionally portable contract and a Google Cloud reference binding.

Devpost: https://devpost.com/software/continuum-lq35x2

Live showcase: https://continuum-showcase-rdzvxiysbq-ew.a.run.app

Technical write-up:
https://dev.to/milos-plavsic/the-agent-failed-the-promise-did-not-building-verifiable-agent-succession-oe4

#AllThingsAgenticHackathon #GoogleCloud #Gemini #AgenticAI #AISafety
