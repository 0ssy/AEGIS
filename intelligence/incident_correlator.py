
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ANOMALY_FILE = PROJECT_ROOT / "logs" / "anomalies.jsonl"
INCIDENT_FILE = PROJECT_ROOT / "logs" / "incidents.jsonl"

CORRELATION_WINDOW_MINUTES = 5


def load_anomalies():
    """Load anomaly events and remove logical duplicates."""

    if not ANOMALY_FILE.exists():
        raise FileNotFoundError(
            f"Anomaly file not found: {ANOMALY_FILE}"
        )

    events = []
    seen_keys = set()

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

                if key not in seen_keys:
                    events.append(event)
                    seen_keys.add(key)

            except (json.JSONDecodeError, KeyError) as error:
                raise ValueError(
                    f"Invalid anomaly event on line {line_number}"
                ) from error

    return events


def load_existing_incident_events():
    """Collect event IDs already assigned to incidents."""

    existing_event_ids = set()

    if not INCIDENT_FILE.exists():
        return existing_event_ids

    with INCIDENT_FILE.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                incident = json.loads(line)

                existing_event_ids.update(
                    incident["event_ids"]
                )

            except (json.JSONDecodeError, KeyError) as error:
                raise ValueError(
                    f"Invalid incident on line {line_number}"
                ) from error

    return existing_event_ids


def correlate_events(events):
    """Group anomalies by machine and correlation time window."""

    machine_events = {}

    # First, separate events by machine.
    for event in events:

        try:
            timestamp = datetime.fromisoformat(
                event["detected_at"]
            )

            if timestamp.tzinfo is None:
                raise ValueError(
                    "Timestamp must include timezone"
                )

            machine = event["machine"]

        except (KeyError, ValueError, TypeError) as error:
            raise ValueError(
                "Anomaly event contains invalid machine or timestamp data"
            ) from error

        machine_events.setdefault(machine, []).append(
            (timestamp, event)
        )

    incidents = []

    # Then correlate each machine independently.
    for machine, machine_records in machine_events.items():

        machine_records.sort(
            key=lambda item: item[0]
        )

        current_group = []
        group_start = None

        for timestamp, event in machine_records:

            if not current_group:

                current_group = [event]
                group_start = timestamp

                continue

            elapsed_minutes = (
                timestamp - group_start
            ).total_seconds() / 60

            if elapsed_minutes <= CORRELATION_WINDOW_MINUTES:

                current_group.append(event)

            else:

                incidents.append(current_group)

                current_group = [event]
                group_start = timestamp

        if current_group:
            incidents.append(current_group)

    # Keep the resulting groups in chronological order.
    incidents.sort(
        key=lambda group: min(
            datetime.fromisoformat(event["detected_at"])
            for event in group
        )
    )

    return incidents


def build_incident(events):
    """Convert a group of anomalies into an incident record."""

    resources = sorted({
        event["resource"] for event in events
    })

    timestamps = [
        datetime.fromisoformat(event["detected_at"])
        for event in events
    ]

    return {
        "incident_id": str(uuid.uuid4()),
        "incident_type": "RESOURCE_PRESSURE",
        "machine": events[0]["machine"],
        "severity": (
            "HIGH" if len(resources) >= 2 else "MEDIUM"
        ),
        "affected_resources": resources,
        "event_ids": [
            event["event_id"] for event in events
        ],
        "event_count": len(events),
        "started_at": min(timestamps).isoformat(),
        "last_event_at": max(timestamps).isoformat(),
        "correlated_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


def save_incidents(incidents):
    """Append new incident records to persistent storage."""

    if not incidents:
        return

    INCIDENT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with INCIDENT_FILE.open("a", encoding="utf-8") as file:

        for incident in incidents:
            file.write(json.dumps(incident) + "\n")


def main():

    print("===================================")
    print("       AEGIS INCIDENT ENGINE")
    print("===================================")

    events = load_anomalies()

    existing_event_ids = load_existing_incident_events()

    new_events = [
        event for event in events
        if event["event_id"] not in existing_event_ids
    ]

    print(f"Anomaly events loaded: {len(events)}")
    print(f"Unprocessed events: {len(new_events)}")

    if not new_events:

        print("No new events to correlate.")
        return

    groups = correlate_events(new_events)

    incidents = [
        build_incident(group)
        for group in groups
    ]

    save_incidents(incidents)

    print(f"\nIncidents generated: {len(incidents)}")

    for incident in incidents:

        print("\n[INCIDENT CREATED]")

        print(f"Incident ID: {incident['incident_id']}")
        print(f"Machine: {incident['machine']}")
        print(f"Severity: {incident['severity']}")

        print(
            f"Affected resources: "
            f"{', '.join(incident['affected_resources'])}"
        )

        print(f"Events correlated: {incident['event_count']}")

    print(f"\nIncident history: {INCIDENT_FILE}")


if __name__ == "__main__":
    main()
