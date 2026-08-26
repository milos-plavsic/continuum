"""Google ADK Investigator reference binding.

The model proposes typed, evidence-cited hypotheses. It has no authority to
mint a policy decision, grant, manifest, or execute an effect.
"""
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

MODEL = "gemini-3.6-flash"


class EvidenceProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypotheses: list[str]
    evidence_ids: list[str]
    unsupported_assumptions: list[str]
    risk: str
    reversibility: str
    proposed_actions: list[Literal[
        "initiate_governed_succession", "request_operator_review"
    ]] = Field(min_length=1, max_length=1)
    successor_choice: "SuccessorChoice"


class SuccessorChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_candidate_id: str
    candidate_evidence_refs: list[str] = Field(min_length=1)
    rationale: str
    objective: str


root_agent = Agent(
    name="continuum_investigator",
    model=Gemini(model=MODEL),
    description="Investigates missed obligations and proposes cited reversible responses.",
    instruction="""
You are Continuum's non-authoritative Investigator. Compare at least two causal
hypotheses. Every factual claim must cite an immutable event ID present in the
control plane's supplied evidence. Missing evidence alone never proves compromise.
Apply this deterministic recommendation table to the supplied event_type values:
- if and only if all three exact types document.injection_detected,
  action.denied, and expectation.missed are present and every one is cited,
  propose exactly initiate_governed_succession;
- for every other set, propose exactly request_operator_review.
Return a structured proposal containing
hypotheses, evidence_ids, unsupported_assumptions, risk, reversibility, and
proposed_actions. Also choose exactly one record from eligible_candidates. Optimize
the supplied selection_objective, preferring the highest trust_score; copy that
record's exact candidate_id and every evidence_refs value into successor_choice.
Never invent a candidate or cite a candidate filtered out by the control plane.
Never claim to approve policy or execute an action. If cited
evidence is missing, fail closed and propose exactly request_operator_review.
When and only when the correlated evidence supports controlled replacement,
propose exactly initiate_governed_succession. These are the only action names.
""".strip(),
    output_schema=EvidenceProposal,
    generate_content_config=GenerateContentConfig(temperature=0, seed=1),
)

app = App(name="continuum", root_agent=root_agent)
