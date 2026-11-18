
import json
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from message_queue import AegisMessageQueue


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
RAW_TELEMETRY_LOG = LOG_DIRECTORY / "ingested_telemetry.jsonl"

HOST = "127.0.0.1"
PORT = 8765
MAX_REQUEST_SIZE = 1_000_000

REQUIRED_FIELDS = {
    "timestamp",
    "machine",
    "cpu",
    "memory",
    "disk",
    "processes"
}

message_queue = AegisMessageQueue()


def validate_telemetry(telemetry):
    if not isinstance(telemetry, dict):
        return False, "Telemetry must be a JSON object"

    missing_fields = REQUIRED_FIELDS - telemetry.keys()

    if missing_fields:
        return False, f"Missing required fields: {sorted(missing_fields)}"

    if not isinstance(telemetry["machine"], dict):
        return False, "Machine must be an object"

    if not isinstance(telemetry["cpu"], dict):
        return False, "CPU metrics must be an object"

    if not isinstance(telemetry["memory"], dict):
        return False, "Memory metrics must be an object"

    if not isinstance(telemetry["disk"], dict):
        return False, "Disk metrics must be an object"

    if not isinstance(telemetry["processes"], list):
        return False, "Processes must be a list"

    return True, None


def save_raw_telemetry(telemetry):
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    with RAW_TELEMETRY_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(telemetry) + "\n")


class AegisIngestionHandler(BaseHTTPRequestHandler):

    def send_json(self, status_code, response):
        payload = json.dumps(response).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path != "/health":
            self.send_json(404, {"error": "Endpoint not found"})
            return

        self.send_json(200, {
            "service": "AEGIS Telemetry Ingestion",
            "status": "HEALTHY",
            "queue": message_queue.get_queue_stats()
        })

    def do_POST(self):
        if self.path != "/telemetry":
            self.send_json(404, {"error": "Endpoint not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid Content-Length"})
            return

        if content_length < 1:
            self.send_json(400, {"error": "Request body is empty"})
            return

        if content_length > MAX_REQUEST_SIZE:
            self.send_json(413, {"error": "Request body too large"})
            return

        try:
            raw_body = self.rfile.read(content_length)
            telemetry = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Invalid JSON"})
            return

        valid, error = validate_telemetry(telemetry)

        if not valid:
            self.send_json(400, {"error": error})
            return

        telemetry["event_id"] = str(uuid.uuid4())

        try:
            message_id = message_queue.enqueue(telemetry)
            save_raw_telemetry(telemetry)

            print(
                f"[INGESTED] "
                f"{telemetry['machine'].get('hostname', 'UNKNOWN')} | "
                f"[QUEUED] {message_id} | "
                f"[EVENT] {telemetry['event_id']}"
            )

            self.send_json(202, {
                "status": "ACCEPTED",
                "message_id": message_id,
                "event_id": telemetry["event_id"],
                "processing_status": "QUEUED",
                "received_at": datetime.now(timezone.utc).isoformat()
            })

        except Exception as error:
            print(f"[INGESTION ERROR] {error}")

            self.send_json(500, {
                "error": "Failed to queue telemetry"
            })

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}")


def run_server():
    server = ThreadingHTTPServer(
        (HOST, PORT),
        AegisIngestionHandler
    )

    print("=" * 45)
    print("       AEGIS INGESTION SERVER")
    print("=" * 45)
    print(f"Host: {HOST}")
    print(f"Port: {PORT}")
    print("Health endpoint: /health")
    print("Telemetry endpoint: /telemetry")
    print("Queue integration: ENABLED")
    print("Event IDs: ENABLED")
    print("Press CTRL+C to stop.")
    print("=" * 45)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAEGIS ingestion server stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
