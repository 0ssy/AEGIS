
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import queue_worker


class FakeQueue:

    def __init__(self, acknowledge_result=True):
        self.acknowledge_result = acknowledge_result
        self.acknowledged = []
        self.released = []

    def acknowledge(self, message_id):
        self.acknowledged.append(message_id)
        return self.acknowledge_result

    def release(self, message_id, delay_seconds=0):
        self.released.append((message_id, delay_seconds))


class FakeStore:

    def __init__(self):
        self.records = {}

    def get(self, record_id):
        return self.records.get(record_id)

    def save(self, record):
        record_id = record["record_id"]

        if record_id in self.records:
            raise ValueError("Duplicate record")

        self.records[record_id] = record

        return record_id


class TestQueueWorkerReliability(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()

        self.log_directory = Path(self.temp_directory.name)
        self.processed_log = (
            self.log_directory / "processed_telemetry.jsonl"
        )

        self.queue = FakeQueue()
        self.store = FakeStore()

        self.message = {
            "message_id": "message-001",
            "attempts": 1,
            "body": {
                "event_id": "event-001",
                "timestamp": "2026-11-18T10:00:00+00:00",
                "machine": {
                    "hostname": "IGGY"
                },
                "cpu": {
                    "usage_percent": 25.0
                },
                "memory": {
                    "usage_percent": 60.0
                },
                "disk": {
                    "usage_percent": 50.0
                },
                "processes": []
            }
        }

        self.processed_record = {
            "record_id": "event-001",
            "machine": "IGGY",
            "timestamp": "2026-11-18T10:00:00+00:00",
            "processed_at": "2026-11-18T10:01:00+00:00",
            "metrics": {
                "cpu_usage_percent": 25.0,
                "memory_usage_percent": 60.0,
                "disk_usage_percent": 50.0,
                "process_count": 0
            },
            "processing_status": "PROCESSED"
        }

        self.processor_response = {
            "statusCode": 200,
            "body": json.dumps(self.processed_record)
        }

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_successful_processing_persists_and_acknowledges(self):
        with patch.object(
            queue_worker,
            "lambda_handler",
            return_value=self.processor_response
        ), patch.object(
            queue_worker,
            "LOG_DIRECTORY",
            self.log_directory
        ), patch.object(
            queue_worker,
            "PROCESSED_LOG",
            self.processed_log
        ):
            queue_worker.process_message(
                self.queue,
                self.message,
                self.store
            )

        self.assertIn("event-001", self.store.records)
        self.assertEqual(self.queue.acknowledged, ["message-001"])
        self.assertEqual(self.queue.released, [])

        self.assertTrue(self.processed_log.exists())

        with self.processed_log.open(encoding="utf-8") as file:
            records = file.readlines()

        self.assertEqual(len(records), 1)

    def test_failed_processing_releases_message(self):
        with patch.object(
            queue_worker,
            "lambda_handler",
            side_effect=RuntimeError("Processing failed")
        ):
            queue_worker.process_message(
                self.queue,
                self.message,
                self.store
            )

        self.assertEqual(self.queue.acknowledged, [])
        self.assertEqual(
            self.queue.released,
            [("message-001", queue_worker.RETRY_DELAY_SECONDS)]
        )

    def test_max_attempts_uses_longer_retry_delay(self):
        self.message["attempts"] = queue_worker.MAX_ATTEMPTS

        with patch.object(
            queue_worker,
            "lambda_handler",
            side_effect=RuntimeError("Repeated failure")
        ):
            queue_worker.process_message(
                self.queue,
                self.message,
                self.store
            )

        self.assertEqual(
            self.queue.released,
            [
                (
                    "message-001",
                    queue_worker.FINAL_RETRY_DELAY_SECONDS
                )
            ]
        )

    def test_existing_record_is_not_written_twice(self):
        self.store.records["event-001"] = self.processed_record

        with patch.object(
            queue_worker,
            "LOG_DIRECTORY",
            self.log_directory
        ), patch.object(
            queue_worker,
            "PROCESSED_LOG",
            self.processed_log
        ):
            saved = queue_worker.save_processed_record(
                self.processed_record,
                self.store
            )

        self.assertFalse(saved)
        self.assertFalse(self.processed_log.exists())
        self.assertEqual(len(self.store.records), 1)

    def test_missing_event_id_is_rejected(self):
        invalid_record = dict(self.processed_record)
        invalid_record["record_id"] = None

        with self.assertRaises(ValueError):
            queue_worker.save_processed_record(
                invalid_record,
                self.store
            )

    def test_failed_acknowledgement_does_not_duplicate_database_record(self):
        self.queue.acknowledge_result = False

        with patch.object(
            queue_worker,
            "lambda_handler",
            return_value=self.processor_response
        ), patch.object(
            queue_worker,
            "LOG_DIRECTORY",
            self.log_directory
        ), patch.object(
            queue_worker,
            "PROCESSED_LOG",
            self.processed_log
        ):
            queue_worker.process_message(
                self.queue,
                self.message,
                self.store
            )

        self.assertEqual(len(self.store.records), 1)

        # Simulate delivery of the same message again.
        self.queue = FakeQueue()

        with patch.object(
            queue_worker,
            "lambda_handler",
            return_value=self.processor_response
        ), patch.object(
            queue_worker,
            "LOG_DIRECTORY",
            self.log_directory
        ), patch.object(
            queue_worker,
            "PROCESSED_LOG",
            self.processed_log
        ):
            queue_worker.process_message(
                self.queue,
                self.message,
                self.store
            )

        self.assertEqual(len(self.store.records), 1)

        with self.processed_log.open(encoding="utf-8") as file:
            records = file.readlines()

        self.assertEqual(len(records), 1)
        self.assertEqual(self.queue.acknowledged, ["message-001"])


if __name__ == "__main__":
    unittest.main()
