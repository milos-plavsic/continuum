from __future__ import annotations

from continuum.incident_policy import assess_incident, describe_lifecycle_events


def incident_extension(subject: str = "obl-1") -> dict:
    assessed_at = "2026-08-17T10:05:00Z"
    events = [
        {"event_id": "event-document", "event_type": "document.injection_detected",
         "source": "document-ingress", "subject": subject},
        {"event_id": "event-denial", "event_type": "action.denied",
         "source": "action-gateway", "subject": subject},
        {"event_id": "event-missed", "event_type": "expectation.missed",
         "source": "negative-space-sentinel", "subject": subject},
    ]
    records = describe_lifecycle_events(events, subject=subject, assessed_at=assessed_at)
    assessment, validation = assess_incident(records, assessed_at=assessed_at, subject=subject)
    return {"subject": subject, "records": [item.to_dict() for item in records],
            "evidence_validation": validation,
            "incident_assessment": assessment.to_dict()}
