
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INCIDENT_FILE = PROJECT_ROOT / "logs" / "incidents.jsonl"
ANALYSIS_FILE = PROJECT_ROOT / "logs" / "root_cause_analysis.jsonl"
PLAN_FILE = PROJECT_ROOT / "logs" / "remediation_plans.jsonl"


REMEDIATION_RULES = {
    "SUSTAINED_MEMORY_PRESSURE": {
        "action": "INSPECT_MEMORY_CONSUMING_PROCESSES",
        "description": (
            "Inspect processes consuming the most memory "
            "and identify abnormal memory growth."
        ),
        "risk": "LOW"
    },

    "MEMORY_USAGE_INCREASING": {
        "action": "INVESTIGATE_MEMORY_GROWTH",
        "description": (
            "Investigate processes with increasing memory "
            "consumption and check for possible memory leaks."
        ),
        "risk": "LOW"
    },

    "MULTIPLE_RESOURCE_PRESSURE": {
        "action": "INSPECT_SYSTEM_RESOURCE_CONSUMPTION",
        "description": (
            "Inspect CPU-intensive and memory-intensive "
            "processes to identify resource contention."
        ),
        "risk": "LOW"
    },

    "DISK_PRESSURE": {
        "action": "INSPECT_DISK_USAGE",
        "description": (
            "Identify directories and files consuming disk "
            "space before considering cleanup."
        ),
        "risk": "LOW"
    }
}


def load_jsonl(path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    records = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}: {path}"
                ) from error

    return records


def generate_plan(incident, analysis):
    """Generate a human-approved remediation plan."""

    if incident["incident_id"] != analysis["incident_id"]:
        raise ValueError("Incident and analysis IDs do not match.")

    recommendations = []

    for hypothesis in analysis.get("hypotheses", []):
        rule_id = hypothesis.get("rule_id")

        rule = REMEDIATION_RULES.get(rule_id)

        if rule is None:
            continue

        recommendations.append({
            "recommendation_id": str(uuid.uuid4()),
            "action": rule["action"],
            "description": rule["description"],
            "risk": rule["risk"],
            "confidence": hypothesis.get("confidence", "UNKNOWN"),
            "source_rule": rule_id,
            "evidence": hypothesis.get("evidence", {})
        })

    return {
        "plan_id": str(uuid.uuid4()),
        "incident_id": incident["incident_id"],
        "machine": incident["machine"],
        "incident_severity": incident["severity"],
        "recommendations": recommendations,
        "execution_mode": "MANUAL_APPROVAL_REQUIRED",
        "approval_required": True,
        "execution_status": "NOT_EXECUTED",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


def save_plan(plan):
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)

    with PLAN_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(plan) + "\n")


def main():
    print("===================================")
    print("      AEGIS REMEDIATION ENGINE")
    print("===================================")

    incidents = load_jsonl(INCIDENT_FILE)
    analyses = load_jsonl(ANALYSIS_FILE)

    if not incidents:
        print("No incidents available.")
        return

    if not analyses:
        print("No root-cause analyses available.")
        return

    incident = incidents[-1]

    matching_analyses = [
        analysis for analysis in analyses
        if analysis.get("incident_id") == incident["incident_id"]
    ]

    if not matching_analyses:
        print("No root-cause analysis found for the latest incident.")
        return

    analysis = matching_analyses[-1]

    plan = generate_plan(incident, analysis)

    save_plan(plan)

    print(f"\nIncident: {plan['incident_id']}")
    print(f"Machine: {plan['machine']}")
    print(f"Recommendations: {len(plan['recommendations'])}")

    for recommendation in plan["recommendations"]:
        print("\n[REMEDIATION RECOMMENDATION]")
        print(f"Action: {recommendation['action']}")
        print(f"Description: {recommendation['description']}")
        print(f"Risk: {recommendation['risk']}")
        print(f"Confidence: {recommendation['confidence']}")

    print("\nExecution: NOT EXECUTED")
    print("Human approval required.")

    print(f"\nPlan saved to: {PLAN_FILE}")


if __name__ == "__main__":
    main()
