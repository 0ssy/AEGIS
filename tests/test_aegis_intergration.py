
import unittest
from unittest.mock import patch

import aegis


class TestAEGISIntegration(unittest.TestCase):

    def setUp(self):
        self.system = aegis.AEGIS(samples=1, interval=1)

    @patch("aegis.monitor.collect_metrics")
    @patch("aegis.monitor.save_telemetry")
    def test_telemetry_collection(self, mock_save, mock_collect):

        mock_collect.return_value = {
            "timestamp": "2026-11-14T10:00:00+00:00",
            "cpu": {"usage_percent": 20},
            "memory": {"usage_percent": 40},
            "disk": {"usage_percent": 50}
        }

        self.system.collect_telemetry()

        self.assertEqual(len(self.system.telemetry), 1)
        mock_save.assert_called_once()

    @patch("aegis.anomaly_detector.load_telemetry")
    @patch("aegis.anomaly_detector.detect_sustained_anomalies")
    @patch("aegis.anomaly_detector.filter_new_anomalies")
    @patch("aegis.anomaly_detector.save_anomalies")
    def test_anomaly_detection(
        self,
        mock_save,
        mock_filter,
        mock_detect,
        mock_load
    ):

        anomaly = {
            "event_id": "event-1",
            "resource": "memory",
            "observed_percent": 95.8,
            "machine": "TEST"
        }

        mock_load.return_value = [{"timestamp": "test"}]
        mock_detect.return_value = [anomaly]
        mock_filter.return_value = [anomaly]

        result = self.system.detect_anomalies()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event_id"], "event-1")
        mock_save.assert_called_once()

    @patch("aegis.incident_correlator.load_anomalies")
    @patch("aegis.incident_correlator.load_existing_incident_events")
    @patch("aegis.incident_correlator.correlate_events")
    @patch("aegis.incident_correlator.build_incident")
    @patch("aegis.incident_correlator.save_incidents")
    def test_incident_correlation(
        self,
        mock_save,
        mock_build,
        mock_correlate,
        mock_existing,
        mock_load
    ):

        event = {"event_id": "event-1"}

        mock_load.return_value = [event]
        mock_existing.return_value = set()
        mock_correlate.return_value = [[event]]

        mock_build.return_value = {
            "incident_id": "incident-1",
            "machine": "TEST",
            "severity": "MEDIUM",
            "affected_resources": ["memory"]
        }

        result = self.system.correlate_incidents()

        self.assertEqual(len(result), 1)
        mock_save.assert_called_once()

    @patch("aegis.root_cause_analyzer.load_jsonl")
    @patch("aegis.root_cause_analyzer.analyze_incident")
    @patch("aegis.root_cause_analyzer.save_analysis")
    def test_root_cause_analysis(
        self,
        mock_save,
        mock_analyze,
        mock_load
    ):

        self.system.incidents = [
            {"incident_id": "incident-1"}
        ]

        mock_load.return_value = [{"timestamp": "test"}]

        mock_analyze.return_value = {
            "incident_id": "incident-1",
            "telemetry_records_analyzed": 1,
            "hypotheses": []
        }

        result = self.system.analyze_root_causes()

        self.assertEqual(len(result), 1)
        mock_save.assert_called_once()

    @patch("aegis.remediation_engine.generate_plan")
    @patch("aegis.remediation_engine.save_plan")
    def test_remediation_planning(self, mock_save, mock_generate):

        self.system.incidents = [
            {"incident_id": "incident-1"}
        ]

        self.system.analyses = [
            {"incident_id": "incident-1"}
        ]

        mock_generate.return_value = {
            "plan_id": "plan-1",
            "machine": "TEST",
            "recommendations": [
                {
                    "action": "INSPECT_MEMORY_CONSUMING_PROCESSES",
                    "risk": "LOW",
                    "description": "Inspect memory usage"
                }
            ]
        }

        result = self.system.generate_remediation_plans()

        self.assertEqual(len(result), 1)
        mock_save.assert_called_once()

    @patch("builtins.input", return_value="no")
    def test_declined_approval_does_not_execute(self, mock_input):

        self.system.plans = [
            {
                "plan_id": "plan-1",
                "machine": "TEST",
                "recommendations": [
                    {
                        "action": "INSPECT_MEMORY_CONSUMING_PROCESSES",
                        "description": "Inspect memory usage"
                    }
                ]
            }
        ]

        with patch(
            "aegis.execution_engine.execute_plan"
        ) as mock_execute:

            self.system.approve_and_execute()

            mock_execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
