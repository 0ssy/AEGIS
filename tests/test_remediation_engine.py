
import unittest

from remediation.remediation_engine import generate_plan


class TestRemediationEngine(unittest.TestCase):

    def setUp(self):
        self.incident = {
            "incident_id": "incident-001",
            "machine": "IGGY",
            "severity": "MEDIUM"
        }

        self.analysis = {
            "incident_id": "incident-001",
            "hypotheses": [
                {
                    "rule_id": "SUSTAINED_MEMORY_PRESSURE",
                    "confidence": "HIGH",
                    "evidence": {"memory_usage": 95.8}
                }
            ]
        }

    def test_generates_recommendation(self):
        plan = generate_plan(self.incident, self.analysis)

        self.assertEqual(len(plan["recommendations"]), 1)
        self.assertEqual(
            plan["recommendations"][0]["action"],
            "INSPECT_MEMORY_CONSUMING_PROCESSES"
        )

    def test_requires_human_approval(self):
        plan = generate_plan(self.incident, self.analysis)

        self.assertTrue(plan["approval_required"])
        self.assertEqual(
            plan["execution_mode"],
            "MANUAL_APPROVAL_REQUIRED"
        )

    def test_does_not_execute_actions(self):
        plan = generate_plan(self.incident, self.analysis)

        self.assertEqual(plan["execution_status"], "NOT_EXECUTED")

    def test_preserves_evidence(self):
        plan = generate_plan(self.incident, self.analysis)

        self.assertEqual(
            plan["recommendations"][0]["evidence"]["memory_usage"],
            95.8
        )

    def test_ignores_unknown_rules(self):
        analysis = {
            "incident_id": "incident-001",
            "hypotheses": [
                {"rule_id": "UNKNOWN_RULE"}
            ]
        }

        plan = generate_plan(self.incident, analysis)

        self.assertEqual(len(plan["recommendations"]), 0)

    def test_rejects_mismatched_incidents(self):
        analysis = {
            "incident_id": "different-incident",
            "hypotheses": []
        }

        with self.assertRaises(ValueError):
            generate_plan(self.incident, analysis)


if __name__ == "__main__":
    unittest.main()
