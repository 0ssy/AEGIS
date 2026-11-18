
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.message_queue import AegisMessageQueue
from backend.queue_worker import process_message


class TestQueueWorker(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_directory.name) / "queue.db"
        self.queue = AegisMessageQueue(self.database)

        self.message = {
            "message_id": "test-message-001",
            "attempts": 1,
            "body": {
                "timestamp": "2026-11-18T14:28:17.649384+00:00",
                "machine": {"hostname": "IGGY"},
                "cpu": {"usage_percent": 25.5},
                "memory": {"usage_percent": 80.2},
                "disk": {"usage_percent": 52.4},
                "processes": [{"pid": 100}]
            }
        }

        self.output_file = (
            Path(self.temp_directory.name) / "processed.jsonl"
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_successful_processing(self):
        message_id = self.queue.enqueue(self.message["body"])
        received = self.queue.receive_messages()[0]

        with patch(
            "backend.queue_worker.PROCESSED_LOG",
            self.output_file
        ):
            process_message(self.queue, received)

        self.assertEqual(self.queue.get_queue_stats()["total"], 0)

        records = [
            json.loads(line)
            for line in self.output_file.read_text().splitlines()
        ]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["machine"], "IGGY")
        self.assertEqual(records[0]["processing_status"], "PROCESSED")

    def test_failed_processing_releases_message(self):
        message_id = self.queue.enqueue(self.message["body"])
        received = self.queue.receive_messages()[0]

        with patch(
            "backend.queue_worker.lambda_handler",
            side_effect=ValueError("Processing failure")
        ):
            with patch(
                "backend.queue_worker.PROCESSED_LOG",
                self.output_file
            ):
                process_message(self.queue, received)

        stats = self.queue.get_queue_stats()

        self.assertEqual(stats["queued"], 1)
        self.assertEqual(stats["in_flight"], 0)

    def test_invalid_telemetry_is_not_acknowledged(self):
        message_id = self.queue.enqueue({"invalid": True})
        received = self.queue.receive_messages()[0]

        with patch(
            "backend.queue_worker.PROCESSED_LOG",
            self.output_file
        ):
            process_message(self.queue, received)

        stats = self.queue.get_queue_stats()

        self.assertEqual(stats["queued"], 1)
        self.assertEqual(stats["total"], 1)


if __name__ == "__main__":
    unittest.main()
