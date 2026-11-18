
import tempfile
import unittest
from pathlib import Path

from backend.telemetry_store import TelemetryStore


class TestTelemetryQueries(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "telemetry.db"

        self.store = TelemetryStore(database_path)

        self.records = [
            self.create_record(
                "event-001",
                "IGGY",
                "2026-11-18T10:00:00+00:00"
            ),
            self.create_record(
                "event-002",
                "IGGY",
                "2026-11-18T11:00:00+00:00"
            ),
            self.create_record(
                "event-003",
                "PROMETHEUS",
                "2026-11-18T12:00:00+00:00"
            ),
            self.create_record(
                "event-004",
                "IGGY",
                "2026-11-18T13:00:00+00:00"
            ),
            self.create_record(
                "event-005",
                "PROMETHEUS",
                "2026-11-18T14:00:00+00:00"
            )
        ]

        for record in self.records:
            self.store.save(record)

    def tearDown(self):
        self.temp_directory.cleanup()

    @staticmethod
    def create_record(record_id, machine, timestamp):
        return {
            "record_id": record_id,
            "machine": machine,
            "timestamp": timestamp,
            "processed_at": "2026-11-18T15:00:00+00:00",
            "metrics": {
                "cpu_usage_percent": 25.0,
                "memory_usage_percent": 60.0,
                "disk_usage_percent": 50.0,
                "process_count": 10
            },
            "processing_status": "PROCESSED"
        }

    def test_time_range_returns_matching_records(self):
        results = self.store.get_by_time_range(
            "2026-11-18T11:00:00+00:00",
            "2026-11-18T13:00:00+00:00"
        )

        self.assertEqual(
            len(results),
            3
        )

        self.assertEqual(
            {record["record_id"] for record in results},
            {"event-002", "event-003", "event-004"}
        )

    def test_time_range_excludes_records_outside_range(self):
        results = self.store.get_by_time_range(
            "2026-11-18T11:30:00+00:00",
            "2026-11-18T13:30:00+00:00"
        )

        record_ids = {
            record["record_id"]
            for record in results
        }

        self.assertEqual(
            record_ids,
            {"event-003", "event-004"}
        )

    def test_time_range_filters_by_machine(self):
        results = self.store.get_by_time_range(
            "2026-11-18T10:00:00+00:00",
            "2026-11-18T14:00:00+00:00",
            machine="IGGY"
        )

        self.assertEqual(
            len(results),
            3
        )

        self.assertTrue(
            all(record["machine"] == "IGGY" for record in results)
        )

    def test_time_range_results_are_newest_first(self):
        results = self.store.get_by_time_range(
            "2026-11-18T10:00:00+00:00",
            "2026-11-18T14:00:00+00:00"
        )

        self.assertEqual(
            [record["record_id"] for record in results],
            [
                "event-005",
                "event-004",
                "event-003",
                "event-002",
                "event-001"
            ]
        )

    def test_time_range_supports_pagination(self):
        results = self.store.get_by_time_range(
            "2026-11-18T10:00:00+00:00",
            "2026-11-18T14:00:00+00:00",
            limit=2,
            offset=1
        )

        self.assertEqual(
            [record["record_id"] for record in results],
            ["event-004", "event-003"]
        )

    def test_time_range_supports_different_timezone_offsets(self):
        results = self.store.get_by_time_range(
            "2026-11-18T13:00:00+03:00",
            "2026-11-18T17:00:00+03:00"
        )

        self.assertEqual(
            len(results),
            5
        )

    def test_time_range_returns_empty_for_no_matches(self):
        results = self.store.get_by_time_range(
            "2026-11-19T10:00:00+00:00",
            "2026-11-19T12:00:00+00:00"
        )

        self.assertEqual(results, [])

    def test_time_range_rejects_start_after_end(self):
        with self.assertRaises(ValueError):
            self.store.get_by_time_range(
                "2026-11-18T14:00:00+00:00",
                "2026-11-18T10:00:00+00:00"
            )

    def test_time_range_rejects_invalid_timestamp(self):
        with self.assertRaises(ValueError):
            self.store.get_by_time_range(
                "not-a-timestamp",
                "2026-11-18T14:00:00+00:00"
            )

    def test_page_returns_limited_records(self):
        results = self.store.get_page(limit=2)

        self.assertEqual(
            len(results),
            2
        )

        self.assertEqual(
            [record["record_id"] for record in results],
            ["event-005", "event-004"]
        )

    def test_page_uses_offset(self):
        results = self.store.get_page(
            limit=2,
            offset=2
        )

        self.assertEqual(
            [record["record_id"] for record in results],
            ["event-003", "event-002"]
        )

    def test_page_filters_by_machine(self):
        results = self.store.get_page(
            limit=10,
            machine="IGGY"
        )

        self.assertEqual(
            len(results),
            3
        )

        self.assertTrue(
            all(record["machine"] == "IGGY" for record in results)
        )

    def test_page_returns_empty_when_offset_exceeds_records(self):
        results = self.store.get_page(
            limit=2,
            offset=100
        )

        self.assertEqual(results, [])

    def test_page_rejects_zero_limit(self):
        with self.assertRaises(ValueError):
            self.store.get_page(limit=0)

    def test_page_rejects_negative_offset(self):
        with self.assertRaises(ValueError):
            self.store.get_page(offset=-1)

    def test_page_rejects_invalid_machine(self):
        with self.assertRaises(ValueError):
            self.store.get_page(machine="")

    def test_time_range_rejects_zero_limit(self):
        with self.assertRaises(ValueError):
            self.store.get_by_time_range(
                "2026-11-18T10:00:00+00:00",
                "2026-11-18T14:00:00+00:00",
                limit=0
            )


if __name__ == "__main__":
    unittest.main()
