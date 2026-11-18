
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TELEMETRY_FILE = PROJECT_ROOT / "logs" / "telemetry.jsonl"
ANOMALY_FILE = PROJECT_ROOT / "logs" / "anomalies.jsonl"


# Initial detection rules.
THRESHOLDS = {
    "cpu": 85,
    "memory": 90,
    "disk": 90,
}

CONSECUTIVE_SAMPLES = 3


def load_telemetry():
    """Load telemetry records from the JSONL history."""

    if not TELEMETRY_FILE.exists():
        raise FileNotFoundError(
            f"Telemetry file not found: {TELEMETRY_FILE}"
        )

    records = []

    with TELEMETRY_FILE.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                records.append(json.loads(line))

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}"
                ) from error

    return records


def detect_sustained_anomalies(records):
    """Detect resources that remain above their thresholds."""

    alerts = []

    for resource, threshold in THRESHOLDS.items():

        consecutive_count = 0
        streak_start = None
        alert_created = False

        for record in records:

            usage = record[resource]["usage_percent"]

            if usage >= threshold:

                consecutive_count += 1

                if consecutive_count == 1:
                    streak_start = record["timestamp"]

                if (
                    consecutive_count >= CONSECUTIVE_SAMPLES
                    and not alert_created
                ):

                    alerts.append({
                        "event_id": str(uuid.uuid4()),
                        "event_type": "RESOURCE_ANOMALY",
                        "resource": resource,
                        "threshold_percent": threshold,
                        "observed_percent": usage,
                        "consecutive_samples": consecutive_count,
                        "started_at": streak_start,
                        "detected_at": record["timestamp"],
                        "machine": record["machine"]["hostname"],
                        "recorded_at": datetime.now(
                            timezone.utc
                        ).isoformat()
                    })

                    alert_created = True

            else:

                consecutive_count = 0
                streak_start = None
                alert_created = False

    return alerts


def load_existing_event_keys():
    """Load identifiers for previously recorded anomalies."""

    existing_keys = set()

    if not ANOMALY_FILE.exists():
        return existing_keys

    with ANOMALY_FILE.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                event = json.loads(line)

                key = (
                    event["machine"],
                    event["resource"],
                    event["started_at"]
                )

                existing_keys.add(key)

            except (json.JSONDecodeError, KeyError) as error:
                raise ValueError(
                    f"Invalid anomaly event on line {line_number}"
                ) from error

    return existing_keys


def filter_new_anomalies(alerts):
    """Remove anomalies that have already been recorded."""

    existing_keys = load_existing_event_keys()

    new_alerts = []

    for alert in alerts:

        key = (
            alert["machine"],
            alert["resource"],
            alert["started_at"]
        )

        if key not in existing_keys:

            new_alerts.append(alert)
            existing_keys.add(key)

    return new_alerts


def save_anomalies(alerts):
    """Persist new anomalies as JSONL events."""

    if not alerts:
        return

    ANOMALY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with ANOMALY_FILE.open("a", encoding="utf-8") as file:

        for alert in alerts:
            file.write(json.dumps(alert) + "\n")


def main():

    print("===================================")
    print("       AEGIS ANOMALY DETECTOR")
    print("===================================")

    records = load_telemetry()

    alerts = detect_sustained_anomalies(records)

    new_alerts = filter_new_anomalies(alerts)

    print(f"Telemetry records analyzed: {len(records)}")

    if not new_alerts:

        print("No new anomalies detected.")
        print("Existing events were not duplicated.")

        return

    save_anomalies(new_alerts)

    print(f"\nNew anomalies detected: {len(new_alerts)}")

    for alert in new_alerts:

        print("\n[ANOMALY DETECTED]")

        print(f"Event ID: {alert['event_id']}")
        print(f"Resource: {alert['resource'].upper()}")
        print(f"Threshold: {alert['threshold_percent']}%")
        print(f"Observed: {alert['observed_percent']}%")
        print(f"Machine: {alert['machine']}")
        print(f"Started: {alert['started_at']}")
        print(f"Detected: {alert['detected_at']}")

    print(f"\nEvents saved to: {ANOMALY_FILE}")


if __name__ == "__main__":
    main()
