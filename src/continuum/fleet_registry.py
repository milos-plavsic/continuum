"""Provider-neutral, cross-department successor catalogue."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterable, Protocol

from .models import digest
from .succession_selection import SuccessorCandidate, SuccessionRequirements


@dataclass(frozen=True)
class FleetPublication:
    department: str
    owner: str
    published_at: str
    candidate: SuccessorCandidate

    @property
    def publication_id(self) -> str:
        return digest({"department": self.department, "owner": self.owner,
                       "published_at": self.published_at,
                       "candidate": asdict(self.candidate)})


class FleetCatalog(Protocol):
    def discover(self, requirements: SuccessionRequirements) -> tuple[SuccessorCandidate, ...]: ...


class InMemoryFleetCatalog:
    def __init__(self, publications: Iterable[FleetPublication]):
        self.publications = tuple(publications)
        if len({item.publication_id for item in self.publications}) != len(self.publications):
            raise ValueError("FLEET_PUBLICATION_DUPLICATE")

    def discover(self, requirements: SuccessionRequirements) -> tuple[SuccessorCandidate, ...]:
        # Discovery is broad; deterministic eligibility remains a separate gate.
        return tuple(sorted((item.candidate for item in self.publications
                             if item.candidate.tenant_id == requirements.tenant_id),
                            key=lambda item: item.principal_id))


class FirestoreFleetCatalog:
    COLLECTION = "continuity_fleet_catalog"

    def __init__(self, client: Any):
        self.client = client

    def publish(self, publication: FleetPublication) -> str:
        ref = self.client.collection(self.COLLECTION).document(publication.publication_id)
        candidate = json.loads(json.dumps(asdict(publication.candidate),
                                          default=lambda item: item.value))
        body = {"department": publication.department, "owner": publication.owner,
                "published_at": publication.published_at, "candidate": candidate}
        snapshot = ref.get()
        if snapshot.exists and snapshot.to_dict() != body:
            raise ValueError("FLEET_PUBLICATION_CONFLICT")
        if not snapshot.exists:
            ref.create(body)
        return publication.publication_id

    def discover(self, requirements: SuccessionRequirements) -> tuple[SuccessorCandidate, ...]:
        snapshots = self.client.collection(self.COLLECTION).where(
            "candidate.tenant_id", "==", requirements.tenant_id).stream()
        # Publications are immutable.  A redeploy may therefore leave several
        # historical publications for one logical principal.  Discovery exposes
        # exactly the newest publication per principal; the policy layer still
        # rejects duplicate principals in its input as an integrity invariant.
        newest: dict[str, tuple[Any, str, SuccessorCandidate]] = {}
        for snapshot in snapshots:
            body = snapshot.to_dict()["candidate"]
            for field in ("capabilities", "memory_scopes", "authority_domains", "jurisdictions",
                          "contract_profiles", "evidence_refs"):
                body[field] = tuple(body[field])
            from .models import AgentStatus
            body["status"] = AgentStatus(body["status"])
            candidate = SuccessorCandidate(**body)
            created_at = getattr(snapshot, "create_time", None)
            ordering = (created_at or "", str(getattr(snapshot, "id", "")))
            current = newest.get(candidate.principal_id)
            if current is None or ordering > current[:2]:
                newest[candidate.principal_id] = (*ordering, candidate)
        return tuple(sorted((item[2] for item in newest.values()),
                            key=lambda item: item.principal_id))
