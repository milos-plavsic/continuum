"""Owned OpenTelemetry setup for Cloud Trace; no synthetic trace claims."""
from __future__ import annotations

import os
from hashlib import sha256
from typing import Any


def configure_cloud_tracing(app: Any) -> bool:
    if os.getenv("CONTINUUM_OBSERVABILITY_ENABLED", "").lower() != "true":
        return False
    from opentelemetry import trace
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider(resource=Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", "continuum"),
            "service.version": os.getenv("GIT_SHA", "unknown"),
            "cloud.provider": "gcp",
        }))
        provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter(
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT") or None)))
        trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())
    return True


def lifecycle_span(name: str, *, run_id: str, phase: str,
                   trace_id: str | None = None) -> Any:
    from opentelemetry import trace
    context = None
    if trace_id is not None:
        if len(trace_id) != 32 or any(character not in "0123456789abcdef" for character in trace_id):
            raise ValueError("TRACE_ID_INVALID")
        span_id = int.from_bytes(sha256(f"{run_id}\0{phase}".encode()).digest()[:8], "big") or 1
        parent = trace.NonRecordingSpan(trace.SpanContext(
            trace_id=int(trace_id, 16), span_id=span_id, is_remote=True,
            trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED), trace_state=trace.TraceState()))
        context = trace.set_span_in_context(parent)
    span = trace.get_tracer("continuum.lifecycle").start_as_current_span(name, context=context)
    active = span.__enter__()
    active.set_attribute("continuum.run_id", run_id)
    active.set_attribute("continuum.phase", phase)
    return span
