"""Idempotent adapter for a real, reversible external work queue."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Callable
from urllib.request import Request, urlopen

from .contract import canonical_bytes


class GitHubIssueWorkQueue:
    """Converge one pre-provisioned sandbox issue to a deterministic desired state.

    PATCH is deliberately used instead of issue creation: redelivery converges on
    one resource, and the effect is reversible by closing the sandbox issue.
    """
    def __init__(self, *, repository: str, issue_number: int, token: str,
                 opener: Callable[..., Any] = urlopen):
        # Secret Manager values are opaque bytes and CLI-fed secrets commonly
        # retain one terminal newline.  Normalize only surrounding whitespace;
        # reject any remaining whitespace so an invalid bearer value fails at
        # configuration time instead of surfacing as a misleading provider 409.
        normalized_token = token.strip()
        if (repository.count("/") != 1 or issue_number <= 0 or not normalized_token
                or any(character.isspace() for character in normalized_token)):
            raise ValueError("EXTERNAL_QUEUE_CONFIG_INVALID")
        self.repository, self.issue_number, self.token, self.opener = (
            repository, issue_number, normalized_token, opener)
        self.url = f"https://api.github.com/repos/{repository}/issues/{issue_number}"

    def converge(self, request: dict[str, Any]) -> dict[str, Any]:
        marker = sha256(canonical_bytes({
            "run_id": request["run_id"], "request_digest": request["request_digest"]
        })).hexdigest()
        body = ("Continuum sandbox work item — no real supplier relationship.\n\n"
                f"Run: `{request['run_id']}`\nRequest: `{request['request_digest']}`\n"
                f"Compliance: `{request['compliance_evidence_id']}`\nMarker: `{marker}`")
        payload = {"state": "open", "title": "[Continuum sandbox] supplier review queue",
                   "body": body, "labels": ["continuum-sandbox"]}
        http = Request(self.url, data=canonical_bytes(payload), method="PATCH", headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28",
        })
        with self.opener(http, timeout=30) as response:
            result = json.loads(response.read())
        if (result.get("state") != "open" or result.get("body") != body or
                result.get("title") != payload["title"]):
            raise ValueError("EXTERNAL_QUEUE_RECONCILIATION_FAILED")
        return {"provider": "github-issues", "provider_ref": result["html_url"],
                "resource_id": str(result["number"]), "state": "OPEN",
                "idempotency_marker": marker, "reversible_action": "close issue"}
