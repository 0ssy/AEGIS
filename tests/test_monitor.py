
import sys
import json
import unittest
import tempfile

from pathlib import Path
from datetime import datetime

from unittest.mock import patch

# Make the monitoring agent importable.
AGENT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "agents"
    / "python-agent"
)

sys.path.insert(0, str(AGENT_DIRECTORY))

import monitor


class TestTelemetryCollection(unittest.TestCase):

    def test_required_telemetry_fields_exist(self):
        telemetry = monitor.collect_metrics()

        self.assertIn("timestamp", telemetry)
        self.assertIn("machine", telemetry)
        self.assertIn("cpu", telemetry)
        self.assertIn("memory", telemetry)
        self.assertIn("disk", telemetry)

    def test_timestamp_is_valid(self):
        telemetry = monitor.collect_metrics()

        timestamp = datetime.fromisoformat(
            telemetry["timestamp"]
        )

        self.assertIsNotNone(timestamp.tzinfo)

    def test_resource_percentages_are_valid(self):
        telemetry = monitor.collect_metrics()

        resources = ["cpu", "memory", "disk"]

        for resource in resources:
            usage = telemetry[resource]["usage_percent"]

            self.assertGreaterEqual(usage, 0)
            self.assertLessEqual(usage, 100)

    def test_machine_identity_exists(self):
        telemetry = monitor.collect_metrics()

        self.assertTrue(
            telemetry["machine"]["hostname"]
        )

        self.assertTrue(
            telemetry["machine"]["operating_system"]
        )

    def test_telemetry_is_saved_as_jsonl(self):

        with tempfile.TemporaryDirectory() as temp_dir:

            test_directory = Path(temp_dir)
            test_file = test_directory / "test.jsonl"

            with patch.object(
                monitor, "LOG_DIRECTORY", test_directory
            ), patch.object(
                monitor, "LOG_FILE", test_file
            ):

                record_one = monitor.collect_metrics()
                record_two = monitor.collect_metrics()

                monitor.save_telemetry(record_one)
                monitor.save_telemetry(record_two)

                with test_file.open(
                    "r", encoding="utf-8"
                ) as file:
                    records = file.readlines()

                self.assertEqual(len(records), 2)

                for record in records:
                    parsed = json.loads(record)
                    self.assertIn("timestamp", parsed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
