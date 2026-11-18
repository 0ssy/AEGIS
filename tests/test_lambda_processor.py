
import json
import unittest

from backend.lambda_processor import lambda_handler


class TestLambdaProcessor(unittest.TestCase):

    def setUp(self):
        self.telemetry = {
            "timestamp": "2026-11-18T14:28:17.649384+00:00",
            "machine": {
                "hostname": "IGGY"
            },
            "cpu": {
                "usage_percent": 25.5
            },
            "memory": {
                "usage_percent": 80.2
            },
            "disk": {
                "usage_percent": 52.4
            },
            "processes": [
                {"pid": 100},
                {"pid": 200}
            ]
        }

    def test_direct_telemetry_processing(self):
        result = lambda_handler(self.telemetry)

        self.assertEqual(result["statusCode"], 200)

        body = json.loads(result["body"])

        self.assertEqual(body["machine"], "IGGY")
        self.assertEqual(
            body["metrics"]["cpu_usage_percent"], 25.5
        )
        self.assertEqual(body["metrics"]["process_count"], 2)
        self.assertEqual(body["processing_status"], "PROCESSED")

    def test_api_gateway_style_event(self):
        event = {
            "body": json.dumps(self.telemetry)
        }

        result = lambda_handler(event)

        self.assertEqual(result["statusCode"], 200)

    def test_dictionary_body(self):
        event = {
            "body": self.telemetry
        }

        result = lambda_handler(event)

        self.assertEqual(result["statusCode"], 200)

    def test_missing_fields(self):
        invalid = {"timestamp": self.telemetry["timestamp"]}

        result = lambda_handler(invalid)

        self.assertEqual(result["statusCode"], 400)

    def test_invalid_machine(self):
        invalid = self.telemetry.copy()
        invalid["machine"] = "IGGY"

        result = lambda_handler(invalid)

        self.assertEqual(result["statusCode"], 400)

    def test_invalid_processes(self):
        invalid = self.telemetry.copy()
        invalid["processes"] = {}

        result = lambda_handler(invalid)

        self.assertEqual(result["statusCode"], 400)

    def test_malformed_json(self):
        result = lambda_handler({"body": "{invalid json"})

        self.assertEqual(result["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
