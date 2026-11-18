
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone, timedelta


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TELEMETRY_FILE = PROJECT_ROOT / "logs" / "telemetry.jsonl"
INCIDENT_FILE = PROJECT_ROOT / "logs" / "incidents.jsonl"
ANALYSIS_FILE = PROJECT_ROOT / "logs" / "root_cause_analysis.jsonl"

ANALYSIS_WINDOW_MINUTES = 5

MEMORY_PRESSURE_THRESHOLD = 90
CPU_PRESSURE_THRESHOLD = 85
DISK_PRESSURE_THRESHOLD = 90

INCREASING_MEMORY_DIFFERENCE = 5


def parse_timestamp(value):
    """Parse a timezone-aware ISO timestamp."""

    try:
        timestamp = datetime.fromisoformat(value)

        if timestamp.tzinfo is None:
            raise ValueError("Timestamp must include timezone")

        return timestamp

    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid or timezone-naive timestamp: {value}"
        ) from error


def analyze_incident(incident, telemetry):
    """Analyze telemetry around an incident and generate hypotheses."""

    machine = incident["machine"]

    incident_start = parse_timestamp(incident["started_at"])
    incident_end = parse_timestamp(
        incident.get("last_event_at", incident["started_at"])
    )

    if incident_end < incident_start:
        raise ValueError(
            "Incident end time cannot be earlier than start time"
        )

    window_start = incident_start - timedelta(
        minutes=ANALYSIS_WINDOW_MINUTES
    )

    window_end = incident_end + timedelta(
        minutes=ANALYSIS_WINDOW_MINUTES
    )

    records = []

    for record in telemetry:

        if record.get("machine", {}).get("hostname") != machine:
            continue

        timestamp = parse_timestamp(record.get("timestamp"))

        if window_start <= timestamp <= window_end:
            records.append((timestamp, record))

    records.sort(key=lambda item: item[0])

    filtered_records = [
        record for _, record in records
    ]

    analysis = {
        "analysis_id": str(uuid.uuid4()),
        "incident_id": incident["incident_id"],
        "machine": machine,
        "analysis_window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "telemetry_records_analyzed": len(filtered_records),
        "resources_analyzed": sorted(
            set(incident.get("affected_resources", []))
        ),
        "hypotheses": [],
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }

    if not filtered_records:
        return analysis

    memory_values = [
        record["memory"]["usage_percent"]
        for record in filtered_records
        if "memory" in record
    ]

    cpu_values = [
        record["cpu"]["usage_percent"]
        for record in filtered_records
        if "cpu" in record
    ]

    disk_values = [
        record["disk"]["usage_percent"]
        for record in filtered_records
        if "disk" in record
    ]

    # Rule 1: Sustained memory pressure.
    if (
        len(memory_values) >= 2
        and sum(
            value >= MEMORY_PRESSURE_THRESHOLD
            for value in memory_values
        ) >= 2
    ):

        analysis["hypotheses"].append({
            "rule_id": "SUSTAINED_MEMORY_PRESSURE",
            "explanation": (
                "Memory usage remained above the configured "
                "pressure threshold across multiple observations."
            ),
            "evidence": {
                "threshold_percent": MEMORY_PRESSURE_THRESHOLD,
                "observed_values": memory_values
            },
            "confidence": "HIGH"
        })

    # Rule 2: Increasing memory usage.
    if (
        len(memory_values) >= 2
        and memory_values[-1] - memory_values[0]
        >= INCREASING_MEMORY_DIFFERENCE
    ):

        analysis["hypotheses"].append({
            "rule_id": "MEMORY_USAGE_INCREASING",
            "explanation": (
                "Memory utilization increased significantly "
                "during the observation period."
            ),
            "evidence": {
                "initial_percent": memory_values[0],
                "final_percent": memory_values[-1],
                "increase_percent": (
                    memory_values[-1] - memory_values[0]
                )
            },
            "confidence": "MEDIUM"
        })

    # Rule 3: Multiple resource pressure.
    if (
        cpu_values
        and memory_values
        and max(cpu_values) >= CPU_PRESSURE_THRESHOLD
        and max(memory_values) >= MEMORY_PRESSURE_THRESHOLD
    ):

        analysis["hypotheses"].append({
            "rule_id": "MULTIPLE_RESOURCE_PRESSURE",
            "explanation": (
                "Both CPU and memory exceeded their configured "
                "pressure thresholds during the observation period."
            ),
            "evidence": {
                "maximum_cpu_percent": max(cpu_values),
                "maximum_memory_percent": max(memory_values)
            },
            "confidence": "MEDIUM"
        })

    # Rule 4: Disk pressure.
    if (
        disk_values
        and max(disk_values) >= DISK_PRESSURE_THRESHOLD
    ):

        analysis["hypotheses"].append({
            "rule_id": "DISK_PRESSURE",
            "explanation": (
                "Disk utilization exceeded the configured "
                "pressure threshold."
            ),
            "evidence": {
                "threshold_percent": DISK_PRESSURE_THRESHOLD,
                "maximum_observed_percent": max(disk_values)
            },
            "confidence": "HIGH"
        })

    return analysis


def load_jsonl(path):
    """Load JSON records from a JSONL file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    records = []

    with path.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                records.append(json.loads(line))

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number} in {path}"
                ) from error

    return records


def save_analysis(analysis):
    """Append analysis results to persistent history."""

    ANALYSIS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with ANALYSIS_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(analysis) + "\n")


def main():

    print("===================================")
    print("     AEGIS ROOT CAUSE INTELLIGENCE")
    print("===================================")

    incidents = load_jsonl(INCIDENT_FILE)
    telemetry = load_jsonl(TELEMETRY_FILE)

    if not incidents:
        print("No incidents available for analysis.")
        return

    incident = incidents[-1]

    analysis = analyze_incident(
        incident,
        telemetry
    )

    save_analysis(analysis)

    print(f"\nIncident: {analysis['incident_id']}")
    print(f"Machine: {analysis['machine']}")

    print(
        f"Telemetry records analyzed: "
        f"{analysis['telemetry_records_analyzed']}"
    )

    print(
        f"Analysis window: "
        f"{analysis['analysis_window']['start']} "
        f"to {analysis['analysis_window']['end']}"
    )

    print(
        f"Hypotheses generated: "
        f"{len(analysis['hypotheses'])}"
    )

    for hypothesis in analysis["hypotheses"]:

        print("\n[ROOT CAUSE HYPOTHESIS]")

        print(f"Rule: {hypothesis['rule_id']}")
        print(f"Explanation: {hypothesis['explanation']}")
        print(f"Confidence: {hypothesis['confidence']}")
        print(f"Evidence: {hypothesis['evidence']}")

    if not analysis["hypotheses"]:
        print("\nInsufficient evidence for a root-cause hypothesis.")

    print(f"\nAnalysis saved to: {ANALYSIS_FILE}")


if __name__ == "__main__":
    main()
