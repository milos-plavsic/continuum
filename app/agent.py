"""Google ADK Investigator reference binding.

The model proposes typed, evidence-cited hypotheses. It has no authority to
mint a policy decision, grant, manifest, or execute an effect.
"""
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini

MODEL = "gemini-3.6-flash"


def resolve_evidence(event_id: str) -> dict:
    """Resolve an immutable event reference supplied by the control plane.

    The deployed adapter replaces this demonstration function with a tenant-
    scoped Firestore lookup and returns only typed evidence, never secrets or
    raw private reasoning.
    """
    return {"event_id": event_id, "status": "resolution delegated to control plane"}


root_agent = Agent(
    name="continuum_investigator",
    model=Gemini(model=MODEL),
    description="Investigates missed obligations and proposes cited reversible responses.",
    instruction="""
You are Continuum's non-authoritative Investigator. Compare at least two causal
hypotheses. Every factual claim must cite an event ID returned by a tool. Missing
evidence alone never proves compromise. Return a structured proposal containing
hypotheses, evidence_ids, unsupported_assumptions, risk, reversibility, and
proposed_actions. Never claim to approve policy or execute an action. If a cited
event cannot be resolved, fail closed and request operator review.
""".strip(),
    tools=[resolve_evidence],
)

app = App(name="continuum", root_agent=root_agent)

