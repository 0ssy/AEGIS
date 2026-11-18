
import json
import time
from pathlib import Path

if __package__:
    from .message_queue import AegisMessageQueue
    from .lambda_processor import lambda_handler
    from .telemetry_store import TelemetryStore
else:
    from message_queue import AegisMessageQueue
    from lambda_processor import lambda_handler
    from telemetry_store import TelemetryStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
PROCESSED_LOG = LOG_DIRECTORY / "processed_telemetry.jsonl"

MAX_MESSAGES = 5
VISIBILITY_TIMEOUT = 30
POLL_INTERVAL = 3
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
FINAL_RETRY_DELAY_SECONDS = 60


def save_processed_record(record, store=None):
    """
    Persist a processed record.

    The SQLite store is the primary persistent storage.
    Existing records are not written again, preventing duplicate
    database records and duplicate JSONL entries during retries.
    """
    record_id = record.get("record_id")

    if not record_id:
        raise ValueError("Processed record has no event ID")

    if store is not None:
        existing_record = store.get(record_id)

        if existing_record is not None:
            return False

        store.save(record)

    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    with PROCESSED_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")

    return True


def process_message(queue, message, store=None):
    message_id = message["message_id"]
    attempts = message["attempts"]

    try:
        telemetry = dict(message["body"])

        # Preserve existing event IDs.
        # Older queued messages receive their stable queue ID.
        telemetry.setdefault("event_id", message_id)

        result = lambda_handler(telemetry)

        if result["statusCode"] != 200:
            raise ValueError(
                f"Processor returned status {result['statusCode']}: "
                f"{result['body']}"
            )

        processed_record = json.loads(result["body"])

        save_processed_record(processed_record, store)

        if queue.acknowledge(message_id):
            print(
                f"[PROCESSED] {processed_record['machine']} | "
                f"Event: {processed_record['record_id']} | "
                f"Message: {message_id}"
            )
        else:
            print(
                f"[ACKNOWLEDGEMENT FAILED] Message: {message_id}"
            )

    except Exception as error:
        print(
            f"[FAILED] Message: {message_id} | "
            f"Attempt: {attempts} | Error: {error}"
        )

        if attempts >= MAX_ATTEMPTS:
            print(
                f"[MAX ATTEMPTS] Message retained for later inspection: "
                f"{message_id}"
            )

            queue.release(
                message_id,
                delay_seconds=FINAL_RETRY_DELAY_SECONDS
            )
        else:
            queue.release(
                message_id,
                delay_seconds=RETRY_DELAY_SECONDS
            )


def run_worker():
    queue = AegisMessageQueue()
    store = TelemetryStore()

    print("=" * 45)
    print("          AEGIS QUEUE WORKER")
    print("=" * 45)
    print(f"Maximum messages per batch: {MAX_MESSAGES}")
    print(f"Visibility timeout: {VISIBILITY_TIMEOUT}s")
    print(f"Maximum attempts: {MAX_ATTEMPTS}")
    print(f"Stored telemetry records: {store.count()}")
    print("Persistent storage: ENABLED")
    print("Idempotent processing: ENABLED")
    print("Waiting for messages...")
    print("Press CTRL+C to stop.")
    print("=" * 45)

    try:
        while True:
            messages = queue.receive_messages(
                max_messages=MAX_MESSAGES,
                visibility_timeout=VISIBILITY_TIMEOUT
            )

            if not messages:
                time.sleep(POLL_INTERVAL)
                continue

            for message in messages:
                process_message(queue, message, store)

    except KeyboardInterrupt:
        print("\nAEGIS queue worker stopped.")


if __name__ == "__main__":
    run_worker()
