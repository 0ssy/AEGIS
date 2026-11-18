
import json
import os
import platform
import socket
import time
import urllib.error
import urllib.request

from datetime import datetime, timezone
from pathlib import Path

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOG_DIRECTORY = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIRECTORY / "telemetry.jsonl"

COLLECTION_INTERVAL = 5
TOP_PROCESSES_LIMIT = 10

# Telemetry transport configuration.
INGESTION_URL = os.getenv("AEGIS_INGESTION_URL", "").strip()
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

# Keep process objects between collection cycles.
PROCESS_TRACKERS = {}


def collect_processes():
    """Collect resource usage for running processes."""

    processes = []
    active_pids = set()

    for process in psutil.process_iter(
        ["pid", "name", "memory_info"]
    ):

        try:
            pid = process.info["pid"]
            active_pids.add(pid)

            tracked_process = PROCESS_TRACKERS.get(pid)

            if tracked_process is None:
                tracked_process = psutil.Process(pid)
                PROCESS_TRACKERS[pid] = tracked_process

            memory_info = process.info["memory_info"]

            if memory_info is None:
                continue

            memory_bytes = memory_info.rss

            cpu_percent = tracked_process.cpu_percent(
                interval=None
            )

            processes.append({
                "pid": pid,
                "name": process.info["name"] or "Unknown",
                "memory_bytes": memory_bytes,
                "memory_mb": round(
                    memory_bytes / (1024 * 1024), 2
                ),
                "cpu_percent": cpu_percent
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess
        ):
            continue

    for pid in list(PROCESS_TRACKERS):

        if pid not in active_pids:
            PROCESS_TRACKERS.pop(pid, None)

    processes.sort(
        key=lambda process: process["memory_bytes"],
        reverse=True
    )

    return processes[:TOP_PROCESSES_LIMIT]


def collect_metrics():
    """Collect system and process telemetry."""

    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    disk = psutil.disk_usage(
        str(Path.home().anchor)
    )

    processes = collect_processes()

    telemetry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "machine": {
            "hostname": socket.gethostname(),
            "operating_system": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine()
        },

        "cpu": {
            "usage_percent": cpu_usage,
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False)
        },

        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_bytes": memory.used,
            "usage_percent": memory.percent
        },

        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "usage_percent": disk.percent
        },

        "processes": processes
    }

    return telemetry


def save_telemetry(telemetry):
    """Append one telemetry record to local JSONL history."""

    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(telemetry) + "\n")


def transmit_telemetry(telemetry):
    """
    Send telemetry to the configured ingestion endpoint.

    Returns a result describing whether transmission succeeded.
    Local telemetry is preserved independently.
    """

    if not INGESTION_URL:
        return {
            "success": False,
            "status": "NOT_CONFIGURED",
            "message": "No ingestion endpoint configured."
        }

    payload = json.dumps(telemetry).encode("utf-8")

    request = urllib.request.Request(
        INGESTION_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    for attempt in range(MAX_RETRIES):

        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT
            ) as response:

                status_code = response.status

                if 200 <= status_code < 300:
                    return {
                        "success": True,
                        "status": "DELIVERED",
                        "http_status": status_code
                    }

                return {
                    "success": False,
                    "status": "HTTP_ERROR",
                    "http_status": status_code
                }

        except urllib.error.HTTPError as error:

            if error.code not in (408, 429) and error.code < 500:
                return {
                    "success": False,
                    "status": "HTTP_ERROR",
                    "http_status": error.code
                }

            if attempt == MAX_RETRIES - 1:
                return {
                    "success": False,
                    "status": "DELIVERY_FAILED",
                    "message": str(error)
                }

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError
        ) as error:

            if attempt == MAX_RETRIES - 1:
                return {
                    "success": False,
                    "status": "DELIVERY_FAILED",
                    "message": str(error)
                }

        delay = RETRY_BACKOFF_SECONDS * (2 ** attempt)
        time.sleep(delay)

    return {
        "success": False,
        "status": "DELIVERY_FAILED"
    }


def main():

    print("===================================")
    print("       AEGIS TELEMETRY AGENT")
    print("===================================")

    print(f"Machine: {socket.gethostname()}")
    print(f"Interval: {COLLECTION_INTERVAL} seconds")
    print(f"Process limit: {TOP_PROCESSES_LIMIT}")
    print(f"Log file: {LOG_FILE}")

    if INGESTION_URL:
        print(f"Ingestion endpoint: {INGESTION_URL}")
    else:
        print("Ingestion endpoint: Not configured")

    print("Press CTRL+C to stop monitoring.\n")

    try:

        while True:

            telemetry = collect_metrics()

            # Local persistence happens before transmission.
            save_telemetry(telemetry)

            print(
                f"[{telemetry['timestamp']}] "
                f"CPU: {telemetry['cpu']['usage_percent']}% | "
                f"RAM: {telemetry['memory']['usage_percent']}% | "
                f"Disk: {telemetry['disk']['usage_percent']}% | "
                f"Processes: {len(telemetry['processes'])}"
            )

            if INGESTION_URL:

                result = transmit_telemetry(telemetry)

                print(
                    f"[TRANSPORT] {result['status']}"
                )

                if not result["success"]:
                    print(
                        f"[TRANSPORT WARNING] "
                        f"{result.get('message', 'Transmission unsuccessful.')}"
                    )

            time.sleep(COLLECTION_INTERVAL)

    except KeyboardInterrupt:

        print("\nAEGIS monitoring stopped.")
        print(f"Telemetry saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
