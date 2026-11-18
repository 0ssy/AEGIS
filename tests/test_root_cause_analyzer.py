
import unittest

from intelligence.root_cause_analyzer import analyze_incident


class TestRootCauseAnalysis(unittest.TestCase):

    def setUp(self):
        self.incident = {
            "incident_id": "incident-001",
            "machine": "IGGY",
            "affected_resources": ["memory"],
            "event_ids": ["event-001"],
            "started_at": "2026-11-14T09:00:00+00:00",
            "last_event_at": "2026-11-14T09:00:00+00:00"
        }

    def make_telemetry(
        self,
        memory,
        cpu=40,
        disk=52,
        timestamp="2026-11-14T09:00:00+00:00",
        machine="IGGY"
    ):
        return {
            "timestamp": timestamp,
            "machine": {
                "hostname": machine
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

    def test_detects_memory_pressure(self):
        telemetry = [
            self.make_telemetry(92),
            self.make_telemetry(93),
            self.make_telemetry(92)
        ]

        result = analyze_incident(self.incident, telemetry)

        self.assertTrue(result["hypotheses"])
        self.assertIn("memory", result["resources_analyzed"])

    def test_detects_increasing_memory_usage(self):
        telemetry = [
            self.make_telemetry(80),
            self.make_telemetry(85),
            self.make_telemetry(92)
        ]

        result = analyze_incident(self.incident, telemetry)

        hypothesis_ids = [
            item["rule_id"] for item in result["hypotheses"]
        ]

        self.assertIn(
            "MEMORY_USAGE_INCREASING",
            hypothesis_ids
        )

    def test_ignores_other_machines(self):
        telemetry = [
            self.make_telemetry(95, machine="SERVER-2")
        ]

        result = analyze_incident(self.incident, telemetry)

        self.assertEqual(result["telemetry_records_analyzed"], 0)

    def test_handles_missing_telemetry(self):
        result = analyze_incident(self.incident, [])

        self.assertEqual(result["telemetry_records_analyzed"], 0)
        self.assertEqual(result["hypotheses"], [])

    def test_identifies_multiple_resource_pressure(self):
        self.incident["affected_resources"] = ["memory", "cpu"]

        telemetry = [
            self.make_telemetry(95, cpu=92),
            self.make_telemetry(96, cpu=94)
        ]

        result = analyze_incident(self.incident, telemetry)

        self.assertIn("cpu", result["resources_analyzed"])
        self.assertIn("memory", result["resources_analyzed"])

    def test_excludes_telemetry_outside_incident_window(self):
        telemetry = [
            self.make_telemetry(
                99,
                timestamp="2026-11-14T08:00:00+00:00"
            ),
            self.make_telemetry(
                70,
                timestamp="2026-11-14T09:00:00+00:00"
            )
        ]

        result = analyze_incident(self.incident, telemetry)

        self.assertEqual(result["telemetry_records_analyzed"], 1)

        self.assertEqual(result["hypotheses"], [])


if __name__ == "__main__":
    unittest.main()
