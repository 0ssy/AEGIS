
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "logs" / "aegis_telemetry.db"


class TelemetryStore:

    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(
            self.database_path,
            timeout=30
        )
        connection.row_factory = sqlite3.Row

        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    record_id TEXT PRIMARY KEY,
                    machine TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    cpu_usage_percent REAL,
                    memory_usage_percent REAL,
                    disk_usage_percent REAL,
                    process_count INTEGER NOT NULL,
                    processing_status TEXT NOT NULL,
                    record_json TEXT NOT NULL
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_machine
                ON telemetry(machine)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp
                ON telemetry(timestamp)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_machine_timestamp
                ON telemetry(machine, timestamp DESC, record_id DESC)
            """)

    @staticmethod
    def _validate_limit_offset(limit, offset):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("Limit must be a positive integer")

        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("Offset must be a non-negative integer")

    @staticmethod
    def _normalize_timestamp(value, field_name):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty ISO-8601 string")

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                f"{field_name} must be a valid ISO-8601 timestamp"
            ) from error

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).isoformat()

    def save(self, record):
        if not isinstance(record, dict):
            raise ValueError("Record must be a dictionary")

        required_fields = {
            "record_id",
            "machine",
            "timestamp",
            "processed_at",
            "metrics",
            "processing_status"
        }

        missing_fields = required_fields - record.keys()

        if missing_fields:
            raise ValueError(
                f"Missing required fields: {sorted(missing_fields)}"
            )

        metrics = record["metrics"]

        if not isinstance(metrics, dict):
            raise ValueError("Metrics must be a dictionary")

        record_id = record["record_id"]

        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Record ID must be a non-empty string")

        if not isinstance(record["machine"], str) or not record["machine"].strip():
            raise ValueError("Machine must be a non-empty string")

        if not isinstance(record["timestamp"], str):
            raise ValueError("Timestamp must be a string")

        if not isinstance(record["processed_at"], str):
            raise ValueError("Processed-at value must be a string")

        process_count = metrics.get("process_count")

        if (
            isinstance(process_count, bool)
            or not isinstance(process_count, int)
            or process_count < 0
        ):
            raise ValueError("Process count must be a non-negative integer")

        with self.connect() as connection:
            connection.execute("""
                INSERT INTO telemetry (
                    record_id,
                    machine,
                    timestamp,
                    processed_at,
                    cpu_usage_percent,
                    memory_usage_percent,
                    disk_usage_percent,
                    process_count,
                    processing_status,
                    record_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                record["machine"],
                record["timestamp"],
                record["processed_at"],
                metrics.get("cpu_usage_percent"),
                metrics.get("memory_usage_percent"),
                metrics.get("disk_usage_percent"),
                process_count,
                record["processing_status"],
                json.dumps(record)
            ))

        return record_id

    def get(self, record_id):
        with self.connect() as connection:
            row = connection.execute("""
                SELECT record_json
                FROM telemetry
                WHERE record_id = ?
            """, (record_id,)).fetchone()

        if row is None:
            return None

        return json.loads(row["record_json"])

    def get_by_machine(self, machine, limit=100):
        self._validate_limit_offset(limit, 0)

        with self.connect() as connection:
            rows = connection.execute("""
                SELECT record_json
                FROM telemetry
                WHERE machine = ?
                ORDER BY timestamp DESC, record_id DESC
                LIMIT ?
            """, (machine, limit)).fetchall()

        return [
            json.loads(row["record_json"])
            for row in rows
        ]

    def get_recent(self, limit=100):
        self._validate_limit_offset(limit, 0)

        with self.connect() as connection:
            rows = connection.execute("""
                SELECT record_json
                FROM telemetry
                ORDER BY timestamp DESC, record_id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [
            json.loads(row["record_json"])
            for row in rows
        ]

    def get_page(self, limit=100, offset=0, machine=None):
        """
        Retrieve a page of telemetry records.

        Results are ordered newest first.
        An optional machine filter restricts the results.
        """
        self._validate_limit_offset(limit, offset)

        if machine is not None:
            if not isinstance(machine, str) or not machine.strip():
                raise ValueError("Machine must be a non-empty string")

            query = """
                SELECT record_json
                FROM telemetry
                WHERE machine = ?
                ORDER BY timestamp DESC, record_id DESC
                LIMIT ? OFFSET ?
            """
            parameters = (machine, limit, offset)

        else:
            query = """
                SELECT record_json
                FROM telemetry
                ORDER BY timestamp DESC, record_id DESC
                LIMIT ? OFFSET ?
            """
            parameters = (limit, offset)

        with self.connect() as connection:
            rows = connection.execute(
                query,
                parameters
            ).fetchall()

        return [
            json.loads(row["record_json"])
            for row in rows
        ]

    def get_by_time_range(
        self,
        start_time,
        end_time,
        machine=None,
        limit=100,
        offset=0
    ):
        """
        Retrieve telemetry within an inclusive time range.

        Timestamps are normalized to UTC before comparison.
        Results are ordered newest first.
        Supports optional machine filtering and pagination.
        """
        self._validate_limit_offset(limit, offset)

        start_time = self._normalize_timestamp(
            start_time,
            "Start time"
        )

        end_time = self._normalize_timestamp(
            end_time,
            "End time"
        )

        if start_time > end_time:
            raise ValueError("Start time cannot be later than end time")

        if machine is not None:
            if not isinstance(machine, str) or not machine.strip():
                raise ValueError("Machine must be a non-empty string")

            query = """
                SELECT record_json
                FROM telemetry
                WHERE timestamp >= ?
                  AND timestamp <= ?
                  AND machine = ?
                ORDER BY timestamp DESC, record_id DESC
                LIMIT ? OFFSET ?
            """
            parameters = (
                start_time,
                end_time,
                machine,
                limit,
                offset
            )

        else:
            query = """
                SELECT record_json
                FROM telemetry
                WHERE timestamp >= ?
                  AND timestamp <= ?
                ORDER BY timestamp DESC, record_id DESC
                LIMIT ? OFFSET ?
            """
            parameters = (
                start_time,
                end_time,
                limit,
                offset
            )

        with self.connect() as connection:
            rows = connection.execute(
                query,
                parameters
            ).fetchall()

        return [
            json.loads(row["record_json"])
            for row in rows
        ]

    def count(self):
        with self.connect() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS total
                FROM telemetry
            """).fetchone()

        return row["total"]

    def delete(self, record_id):
        with self.connect() as connection:
            cursor = connection.execute("""
                DELETE FROM telemetry
                WHERE record_id = ?
            """, (record_id,))

        return cursor.rowcount == 1


if __name__ == "__main__":
    store = TelemetryStore()

    print("=" * 40)
    print("       AEGIS TELEMETRY STORE")
    print("=" * 40)
    print(f"Database: {store.database_path}")
    print(f"Stored records: {store.count()}")
    print("Pagination: ENABLED")
    print("Time-range queries: ENABLED")
