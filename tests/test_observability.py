from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI

from continuum.observability import configure_cloud_tracing, lifecycle_span


class ObservabilityTests(unittest.TestCase):
    def test_configuration_is_opt_in_and_uses_cloud_trace_batch_export(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(configure_cloud_tracing(FastAPI()))
        app = FastAPI()
        with patch.dict(os.environ, {"CONTINUUM_OBSERVABILITY_ENABLED": "true",
                                     "GOOGLE_CLOUD_PROJECT": "p", "OTEL_SERVICE_NAME": "service",
                                     "GIT_SHA": "a" * 40}), \
             patch("opentelemetry.exporter.cloud_trace.CloudTraceSpanExporter", return_value=Mock()) as exporter, \
             patch("opentelemetry.sdk.trace.export.BatchSpanProcessor", return_value=Mock()), \
             patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app") as instrument:
            self.assertTrue(configure_cloud_tracing(app))
            exporter.assert_called_once_with(project_id="p")
            instrument.assert_called_once()
            self.assertTrue(configure_cloud_tracing(FastAPI()))

    def test_lifecycle_span_sets_owned_run_attributes(self):
        uncorrelated = lifecycle_span("continuum.local", run_id="r", phase="LOCAL")
        uncorrelated.__exit__(None, None, None)
        manager = lifecycle_span("continuum.test", run_id="r", phase="TEST", trace_id="a" * 32)
        manager.__exit__(None, None, None)
        with self.assertRaisesRegex(ValueError, "TRACE_ID_INVALID"):
            lifecycle_span("continuum.test", run_id="r", phase="TEST", trace_id="bad")


if __name__ == "__main__":
    unittest.main()
