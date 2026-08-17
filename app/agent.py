"""Google ADK Investigator reference binding.

The model proposes typed, evidence-cited hypotheses. It has no authority to
mint a policy decision, grant, manifest, or execute an effect.
"""
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from pydantic import BaseModel, ConfigDict

MODEL = "gemini-3.6-flash"


class EvidenceProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypotheses: list[str]
    evidence_ids: list[str]
    unsupported_assumptions: list[str]
    risk: str
    reversibility: str
    proposed_actions: list[str]


root_agent = Agent(
    name="continuum_investigator",
    model=Gemini(model=MODEL),
    description="Investigates missed obligations and proposes cited reversible responses.",
    instruction="""
You are Continuum's non-authoritative Investigator. Compare at least two causal
hypotheses. Every factual claim must cite an immutable event ID present in the
control plane's supplied evidence. Missing evidence alone never proves compromise.
Return a structured proposal containing
hypotheses, evidence_ids, unsupported_assumptions, risk, reversibility, and
proposed_actions. Never claim to approve policy or execute an action. If cited
evidence is missing, fail closed and request operator review.
""".strip(),
    output_schema=EvidenceProposal,
)

app = App(name="continuum", root_agent=root_agent)
