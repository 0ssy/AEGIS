
import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from intelligence import anomaly_detector


def make_record(cpu=30, memory=50, disk=40):
    """Create synthetic telemetry records for testing."""

    return {
        "timestamp": "2026-11-14T10:00:00+00:00",
        "machine": {
            "hostname": "TEST-MACHINE"
        },
        "cpu": {
            "usage_percent": cpu
        },
        "memory": {
            "usage_percent": memory
        },
        "disk": {
            "usage_percent": disk
        }
    }


class TestAnomalyDetection(unittest.TestCase):

    def test_single_spike_does_not_trigger_alert(self):

        records = [
            make_record(cpu=95),
            make_record(cpu=30),
            make_record(cpu=30),
        ]

        alerts = anomaly_detector.detect_sustained_anomalies(
            records
        )

        self.assertEqual(alerts, [])

    def test_three_consecutive_high_samples_trigger_alert(self):

        records = [
            make_record(memory=92),
            make_record(memory=94),
            make_record(memory=96),
        ]

        alerts = anomaly_detector.detect_sustained_anomalies(
            records
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["resource"], "memory")
        self.assertEqual(alerts[0]["observed_percent"], 96)

    def test_normal_reading_resets_consecutive_count(self):

        records = [
            make_record(memory=92),
            make_record(memory=85),
            make_record(memory=93),
            make_record(memory=95),
        ]

        alerts = anomaly_detector.detect_sustained_anomalies(
            records
        )

        self.assertEqual(alerts, [])

    def test_cpu_and_memory_trigger_separate_alerts(self):

        records = [
            make_record(cpu=90, memory=92),
            make_record(cpu=91, memory=93),
            make_record(cpu=92, memory=94),
        ]

        alerts = anomaly_detector.detect_sustained_anomalies(
            records
        )

        resources = {
            alert["resource"] for alert in alerts
        }

        self.assertEqual(resources, {"cpu", "memory"})

    def test_threshold_boundary_triggers_alert(self):

        records = [
            make_record(memory=90),
            make_record(memory=90),
            make_record(memory=90),
        ]

        alerts = anomaly_detector.detect_sustained_anomalies(
            records
        )

        self.assertEqual(len(alerts), 1)

    def test_new_anomaly_is_not_a_duplicate(self):

        alert = {
            "event_id": "test-event-001",
            "machine": "TEST-MACHINE",
            "resource": "memory",
            "started_at": "2026-11-14T10:00:00+00:00"
        }

        with tempfile.TemporaryDirectory() as temp_dir:

            test_file = Path(temp_dir) / "anomalies.jsonl"

            with patch.object(
                anomaly_detector,
                "ANOMALY_FILE",
                test_file
            ):

                filtered = anomaly_detector.filter_new_anomalies(
                    [alert]
                )

                self.assertEqual(len(filtered), 1)

    def test_existing_anomaly_is_deduplicated(self):

        alert = {
            "event_id": "test-event-001",
            "machine": "TEST-MACHINE",
            "resource": "memory",
            "started_at": "2026-11-14T10:00:00+00:00"
        }

        with tempfile.TemporaryDirectory() as temp_dir:

            test_file = Path(temp_dir) / "anomalies.jsonl"

            with test_file.open(
                "w", encoding="utf-8"
            ) as file:

                file.write(json.dumps(alert) + "\n")

            with patch.object(
                anomaly_detector,
                "ANOMALY_FILE",
                test_file
            ):

                filtered = anomaly_detector.filter_new_anomalies(
                    [alert]
                )

                self.assertEqual(filtered, [])

    def test_different_resource_is_not_a_duplicate(self):

        existing_alert = {
            "event_id": "test-event-001",
            "machine": "TEST-MACHINE",
            "resource": "memory",
            "started_at": "2026-11-14T10:00:00+00:00"
        }

        new_alert = {
            "event_id": "test-event-002",
            "machine": "TEST-MACHINE",
            "resource": "cpu",
            "started_at": "2026-11-14T10:00:00+00:00"
        }

        with tempfile.TemporaryDirectory() as temp_dir:

            test_file = Path(temp_dir) / "anomalies.jsonl"

            with test_file.open(
                "w", encoding="utf-8"
            ) as file:

                file.write(json.dumps(existing_alert) + "\n")

            with patch.object(
                anomaly_detector,
                "ANOMALY_FILE",
                test_file
            ):

                filtered = anomaly_detector.filter_new_anomalies(
                    [new_alert]
                )

                self.assertEqual(len(filtered), 1)
                self.assertEqual(
                    filtered[0]["resource"],
                    "cpu"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
