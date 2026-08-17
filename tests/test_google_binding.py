from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from continuum.google_binding import GoogleBindingConfig, PubSubLifecyclePublisher


class _Future:
    def result(self, timeout):
        return f"message:{timeout}"


class _Publisher:
    def __init__(self):
        self.call = None

    def topic_path(self, project, topic):
        return f"projects/{project}/topics/{topic}"

    def publish(self, path, data, **attributes):
        self.call = (path, data, attributes)
        return _Future()


class GoogleBindingTests(unittest.TestCase):
    def test_pubsub_adapter_publishes_canonical_event_and_trace_attributes(self):
        client = _Publisher()
        adapter = PubSubLifecyclePublisher(GoogleBindingConfig("project", "events"), client)
        message = adapter.publish({"event_type": "identity.fenced", "correlation_id": "trace-1", "schema_version": 1})
        self.assertEqual(message, "message:30")
        self.assertEqual(client.call[0], "projects/project/topics/events")
        self.assertEqual(client.call[2]["correlation_id"], "trace-1")
        self.assertEqual(client.call[1], b'{"correlation_id":"trace-1","event_type":"identity.fenced","schema_version":1}')


if __name__ == "__main__":
    unittest.main()
