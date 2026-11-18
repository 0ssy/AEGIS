
import tempfile
import unittest
from pathlib import Path

from backend.telemetry_store import TelemetryStore


class TestTelemetryStore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        database_path = Path(self.temp_dir.name) / "test_telemetry.db"

        self.store = TelemetryStore(database_path)

        self.record = {
            "record_id": "event-001",
            "machine": "IGGY",
            "timestamp": "2026-11-18T10:00:00+00:00",
            "processed_at": "2026-11-18T10:00:01+00:00",
            "metrics": {
                "cpu_usage_percent": 45.5,
                "memory_usage_percent": 67.2,
                "disk_usage_percent": 72.1,
                "process_count": 18
            },
            "processing_status": "PROCESSED"
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_record(self):
        record_id = self.store.save(self.record)

        self.assertEqual(record_id, "event-001")
        self.assertEqual(self.store.count(), 1)

    def test_get_record(self):
        self.store.save(self.record)

        result = self.store.get("event-001")

        self.assertEqual(result, self.record)

    def test_get_missing_record(self):
        result = self.store.get("missing-event")

        self.assertIsNone(result)

    def test_get_by_machine(self):
        self.store.save(self.record)

        result = self.store.get_by_machine("IGGY")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["machine"], "IGGY")

    def test_get_recent_records(self):
        self.store.save(self.record)

        result = self.store.get_recent(limit=10)

        self.assertEqual(len(result), 1)

    def test_delete_record(self):
        self.store.save(self.record)

        deleted = self.store.delete("event-001")

        self.assertTrue(deleted)
        self.assertEqual(self.store.count(), 0)

    def test_delete_missing_record(self):
        deleted = self.store.delete("missing-event")

        self.assertFalse(deleted)

    def test_reject_non_dictionary(self):
        with self.assertRaises(ValueError):
            self.store.save("invalid")

    def test_reject_missing_fields(self):
        with self.assertRaises(ValueError):
            self.store.save({
                "record_id": "event-002"
            })

    def test_reject_empty_record_id(self):
        invalid_record = self.record.copy()
        invalid_record["record_id"] = ""

        with self.assertRaises(ValueError):
            self.store.save(invalid_record)

    def test_reject_invalid_process_count(self):
        invalid_record = {
            **self.record,
            "metrics": {
                **self.record["metrics"],
                "process_count": -1
            }
        }

        with self.assertRaises(ValueError):
            self.store.save(invalid_record)

    def test_reject_duplicate_record_id(self):
        self.store.save(self.record)

        with self.assertRaises(Exception):
            self.store.save(self.record)

    def test_invalid_query_limit(self):
        with self.assertRaises(ValueError):
            self.store.get_recent(limit=0)

        with self.assertRaises(ValueError):
            self.store.get_by_machine("IGGY", limit=0)


if __name__ == "__main__":
    unittest.main()
