"""Black-box conformance harness for the reference-local profile."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from typing import Callable

from .contract import ContractError, canonical_bytes, validate_envelope
from .core import ActionGateway, AgentRegistry, VendorRegistry
from .models import AgentStatus, AgentVersion, Denied
from .scenario import run_scenario
from .standard import build_contract_bundle, verify_bundle
from .recovery import InjectedCrash, RecoveryRuntime

LEVEL_CASES = {
    "C0": ["O01", "O02", "O03"],
    "C1": ["R01", "R02"],
    "C2": ["F01", "F02"],
    "C3": ["M01", "M02", "M03", "M04"],
    "C4": ["I01", "I02", "I03"],
    "C5": ["G01", "G02", "G03", "G04"],
    "C6": ["A01", "A02", "A03"],
}


@dataclass
class CaseResult:
    id: str
    level: str
    status: str
    assertion: str
    observed: str
    duration_ms: int
    evidence_sha256: str


def _run(case_id: str, level: str, assertion: str, fn: Callable[[], object]) -> CaseResult:
    started = time.perf_counter_ns()
    try:
        observed = fn()
        status = "PASS" if bool(observed) else "FAIL"
        rendered = json.dumps(observed, sort_keys=True, default=str)
    except Exception as error:
        status, rendered = "FAIL", f"{type(error).__name__}:{error}"
    duration = (time.perf_counter_ns() - started) // 1_000_000
    return CaseResult(case_id, level, status, assertion, rendered, duration,
                      sha256(rendered.encode()).hexdigest())


def run_conformance(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cases: list[CaseResult] = []
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        bundle = build_contract_bundle(root / "bundle")
        canonical = run_scenario(root / "canonical")

        def add(level: str, case_id: str, assertion: str, fn: Callable[[], object]) -> None:
            cases.append(_run(case_id, level, assertion, fn))

        add("C0", "O01", "six typed artifacts form a complete verified bundle", lambda: (verify_bundle(bundle) is None and len(bundle["artifacts"]) == 6))
        def mutation_detected() -> bool:
            changed = deepcopy(bundle["artifacts"][0]); changed["body"]["description"] = "tampered"
            try: validate_envelope(changed)
            except ContractError as error: return str(error) == "DIGEST_MISMATCH"
            return False
        add("C0", "O02", "artifact mutation invalidates its digest", mutation_detected)
        add("C0", "O03", "independent replay yields identical timeline", lambda: canonical["timeline"] == run_scenario(root / "replay")["timeline"])

        add("C1", "R01", "obligation reaches a visible verified terminal state", lambda: canonical["obligation_status"] == "DISCHARGED")
        add("C1", "R02", "crash after fencing resumes from durable journal", lambda: _crash_resume(root / "r02"))
        add("C2", "F01", "stale predecessor is denied at action boundary", lambda: "STALE_FENCE" in canonical["denials"])
        add("C2", "F02", "competing successor admission yields one winner", _one_successor_wins)
        add("C3", "M01", "revoked identity exposes zero retrieval candidates", lambda: canonical["revoked_candidates_exposed"] == 0 and "GRANT_REVOKED" in canonical["denials"])
        add("C3", "M02", "manifest explicitly excludes dangerous context", lambda: _manifest_exclusions(bundle))
        add("C3", "M03", "cross-tenant authorization is non-disclosing", _cross_tenant_denied)
        add("C3", "M04", "expired or altered-purpose grant fails before use", lambda: _grant_bounds(bundle))
        add("C4", "I01", "redelivery creates one external effect", lambda: canonical["vendor_count"] == 1 and canonical["duplicate_returned_prior_result"])
        add("C4", "I02", "same key with changed request is rejected", lambda: _idempotency_conflict(root / "i02"))
        add("C4", "I03", "gateway restart reconciles durable provider record", lambda: _restart_reconciliation(root / "i03"))
        add("C5", "G01", "silence alone cannot authorize quarantine", lambda: run_scenario(root / "g01", signals=("missed_evidence",))["outcome"] == "INVESTIGATE_HOLD")
        add("C5", "G02", "correlated evidence deterministically authorizes succession", lambda: canonical["outcome"] == "VERIFIED")
        add("C5", "G03", "unsupported required feature fails closed", lambda: _unsupported_feature(bundle))
        add("C5", "G04", "fabricated evidence citation fails closed", _fabricated_citation)
        add("C6", "A01", "attestation links all six independently verified artifacts", lambda: verify_bundle(bundle) is None)
        add("C6", "A02", "broken reference is rejected", lambda: _broken_reference(bundle))
        add("C6", "A03", "executor cannot self-attest verified", lambda: _self_attestation_rejected(bundle))

    levels: dict[str, dict] = {}
    contiguous = True
    highest = None
    for level, required in LEVEL_CASES.items():
        failed = [case.id for case in cases if case.id in required and case.status != "PASS"]
        status = "PASS" if contiguous and not failed else "FAIL"
        levels[level] = {"status": status, "required_cases": required, "failed_cases": failed}
        if status == "PASS": highest = level
        else: contiguous = False
    report = {
        "schema_version": "continuity-conformance-report/0.1-draft",
        "suite": {"name": "Continuity Conformance", "version": "0.1-draft",
                  "spec_digest": sha256(b"continuum/0.1-draft").hexdigest()},
        "implementation": {"name": "Continuum", "version": "0.1.0"},
        "profile": "reference-local", "cases": [asdict(case) for case in cases],
        "levels": levels, "highest_level": highest,
        "claims": {
            "effect_scope": "sandbox provider through Continuum ActionGateway",
            "identity_boundary": "logical registry epoch; not cloud workload authentication",
            "memory_boundary": "in-process pre-retrieval grant check; not a vector database",
            "authenticity": "content digests; Ed25519 support tested separately; no external trust anchor",
        },
        "non_claims": ["third-party interoperability", "Google Cloud conformance", "live-model conformance", "universal exactly-once", "global credential revocation"],
    }
    unsigned = canonical_bytes(report)
    report["report_digest"] = {"alg": "sha-256", "value": sha256(unsigned).hexdigest()}
    (output / "conformance-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _roundtrip_bundle(bundle: dict) -> bool:
    loaded = json.loads(json.dumps(bundle, sort_keys=True))
    verify_bundle(loaded)
    return canonical_bytes(loaded) == canonical_bytes(bundle)


def _crash_resume(path: Path) -> bool:
    path.mkdir(parents=True); db = path / "journal.sqlite3"
    first = RecoveryRuntime(db); first.initialize("s1")
    try: first.resume("s1", fault_after="FENCED")
    except InjectedCrash: pass
    first.close()
    second = RecoveryRuntime(db)
    state = second.resume("s1")
    second.close()
    return state == ("VERIFIED", "v18", 42, "DISCHARGED")


def _manifest_exclusions(bundle: dict) -> bool:
    manifest = next(a for a in bundle["artifacts"] if a["artifact_type"] == "succession_manifest")
    values = {item["reference_or_class"] for item in manifest["body"]["excluded_context"]}
    return {"raw_untrusted_document", "secret", "revoked_private_notes"}.issubset(values)


def _registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(AgentVersion("procurement", "v1", "acme", AgentStatus.ACTIVE, 7, "sha256:a", "v1@acme", ("vendor.create",), ("approved",)))
    return registry


def _cross_tenant_denied() -> bool:
    try: _registry().authorize("other", "v1", 7, "vendor.create")
    except Denied as error: return error.reason == "RESOURCE_NOT_FOUND"
    return False


def _one_successor_wins() -> bool:
    registry = _registry()
    registry.fence("v1", 7)
    registry.register(AgentVersion("procurement", "v2", "acme", AgentStatus.REGISTERED, 0, "sha256:b", "v2@acme", ("vendor.create",), ("approved",), "v1"))
    registry.register(AgentVersion("procurement", "v3", "acme", AgentStatus.REGISTERED, 0, "sha256:c", "v3@acme", ("vendor.create",), ("approved",), "v1"))
    registry.activate("v2", 8)
    try: registry.activate("v3", 8)
    except ValueError as error:
        return str(error) == "ACTIVE_VERSION_EXISTS" and registry.get("v2").status == AgentStatus.ACTIVE
    return False


def _grant_bounds(bundle: dict) -> bool:
    from .contract import authorize_grant
    grant = next(a for a in bundle["artifacts"] if a["artifact_type"] == "authority_grant")
    args = dict(tenant_id="acme", principal="urn:continuum:principal:acme:procurement:v18",
                authority_domain="urn:continuum:authority:acme:procurement-agent", epoch=42,
                obligation_id="urn:continuum:obligation:acme:vendor-042", capability="vendor.create",
                memory_scope="vendor.approved", purpose="complete vendor-042 onboarding")
    authorize_grant(grant, now="2026-08-17T10:30:00Z", **args)
    failures = 0
    for check_time, changed in [("2026-08-17T12:00:00Z", args),
                                ("2026-08-17T10:30:00Z", args | {"purpose": "export all vendors"})]:
        try: authorize_grant(grant, now=check_time, **changed)
        except ContractError: failures += 1
    return failures == 2


def _fabricated_citation() -> bool:
    from .core import decide_compromise
    try: decide_compromise({"injection": "nonexistent", "anomalous_action": "e2", "missed_evidence": "e3"}, {"e2", "e3"})
    except Denied as error: return error.reason == "FABRICATED_EVIDENCE_CITATION"
    return False


def _idempotency_conflict(path: Path) -> bool:
    path.mkdir(parents=True); registry = _registry(); gateway = ActionGateway(registry, VendorRegistry(path / "provider.sqlite3"))
    base = dict(tenant="acme", version="v1", epoch=7, vendor="one", idempotency_key="key", decision_id="decision")
    gateway.create_vendor(**base)
    try: gateway.create_vendor(**(base | {"vendor": "two"}))
    except Denied as error:
        gateway.provider.close()
        return error.reason == "IDEMPOTENCY_KEY_CONFLICT"
    gateway.provider.close()
    return False


def _restart_reconciliation(path: Path) -> bool:
    path.mkdir(parents=True); registry = _registry(); provider = VendorRegistry(path / "provider.sqlite3")
    args = dict(tenant="acme", version="v1", epoch=7, vendor="one", idempotency_key="key", decision_id="decision")
    first, duplicate1 = ActionGateway(registry, provider).create_vendor(**args)
    second, duplicate2 = ActionGateway(registry, provider).create_vendor(**args)
    result = first == second and not duplicate1 and duplicate2 and provider.count() == 1
    provider.close()
    return result


def _unsupported_feature(bundle: dict) -> bool:
    changed = deepcopy(bundle["artifacts"][0]); changed["required_features"] = ["urn:unknown:critical"]
    changed["digest"]["value"] = __import__("continuum.contract", fromlist=["artifact_digest"]).artifact_digest(changed)
    try: validate_envelope(changed)
    except ContractError as error: return str(error) == "UNSUPPORTED_REQUIRED_FEATURE"
    return False


def _broken_reference(bundle: dict) -> bool:
    changed = deepcopy(bundle); att = next(a for a in changed["artifacts"] if a["artifact_type"] == "continuity_attestation")
    att["body"]["obligation"]["digest"]["value"] = "0" * 64
    from .contract import artifact_digest
    att["digest"]["value"] = artifact_digest(att)
    try: verify_bundle(changed)
    except ContractError as error: return str(error) == "BROKEN_ARTIFACT_REFERENCE"
    return False


def _self_attestation_rejected(bundle: dict) -> bool:
    changed = deepcopy(bundle); att = next(a for a in changed["artifacts"] if a["artifact_type"] == "continuity_attestation")
    att["body"]["verification"]["verifier_principal"] = "urn:continuum:principal:acme:procurement:v18"
    from .contract import artifact_digest
    att["digest"]["value"] = artifact_digest(att)
    try: verify_bundle(changed)
    except ContractError as error: return str(error) == "EXECUTOR_SELF_ATTESTATION"
    return False
