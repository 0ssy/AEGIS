
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUEUE_DATABASE = PROJECT_ROOT / "logs" / "aegis_queue.db"


class AegisMessageQueue:

    def __init__(self, database_path=QUEUE_DATABASE):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
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
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    available_at REAL NOT NULL,
                    locked_until REAL
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_status
                ON messages(status, available_at)
            """)

    def enqueue(self, message):
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")

        message_id = str(uuid.uuid4())
        now = time.time()

        with self.connect() as connection:
            connection.execute("""
                INSERT INTO messages (
                    message_id,
                    body,
                    status,
                    attempts,
                    created_at,
                    available_at
                )
                VALUES (?, ?, 'QUEUED', 0, ?, ?)
            """, (
                message_id,
                json.dumps(message),
                now,
                now
            ))

        return message_id

    def receive_messages(
        self,
        max_messages=1,
        visibility_timeout=30
    ):
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")

        if visibility_timeout < 1:
            raise ValueError("visibility_timeout must be at least 1")

        now = time.time()
        messages = []

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            rows = connection.execute("""
                SELECT *
                FROM messages
                WHERE (
                    status = 'QUEUED'
                    AND available_at <= ?
                )
                OR (
                    status = 'IN_FLIGHT'
                    AND locked_until <= ?
                )
                ORDER BY created_at ASC
                LIMIT ?
            """, (now, now, max_messages)).fetchall()

            for row in rows:
                connection.execute("""
                    UPDATE messages
                    SET status = 'IN_FLIGHT',
                        attempts = attempts + 1,
                        locked_until = ?
                    WHERE message_id = ?
                """, (
                    now + visibility_timeout,
                    row["message_id"]
                ))

                messages.append({
                    "message_id": row["message_id"],
                    "body": json.loads(row["body"]),
                    "attempts": row["attempts"] + 1
                })

        return messages

    def acknowledge(self, message_id):
        with self.connect() as connection:
            cursor = connection.execute("""
                DELETE FROM messages
                WHERE message_id = ?
                AND status = 'IN_FLIGHT'
            """, (message_id,))

            return cursor.rowcount == 1

    def release(self, message_id, delay_seconds=0):
        if delay_seconds < 0:
            raise ValueError("Delay cannot be negative")

        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE messages
                SET status = 'QUEUED',
                    available_at = ?,
                    locked_until = NULL
                WHERE message_id = ?
                AND status = 'IN_FLIGHT'
            """, (
                time.time() + delay_seconds,
                message_id
            ))

            return cursor.rowcount == 1

    def get_queue_stats(self):
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT status, COUNT(*) AS total
                FROM messages
                GROUP BY status
            """).fetchall()

        stats = {
            "queued": 0,
            "in_flight": 0
        }

        for row in rows:
            if row["status"] == "QUEUED":
                stats["queued"] = row["total"]
            elif row["status"] == "IN_FLIGHT":
                stats["in_flight"] = row["total"]

        stats["total"] = stats["queued"] + stats["in_flight"]

        return stats


if __name__ == "__main__":
    queue = AegisMessageQueue()
    print("AEGIS queue initialized.")
    print("Queue statistics:", queue.get_queue_stats())
