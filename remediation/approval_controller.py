
import json
import uuid

from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PLAN_FILE = PROJECT_ROOT / "logs" / "remediation_plans.jsonl"
APPROVAL_FILE = PROJECT_ROOT / "logs" / "remediation_approvals.jsonl"


def read_jsonl(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def record_approval(plan):
    approvals = read_jsonl(APPROVAL_FILE)

    existing = next(
        (
            item for item in approvals
            if item["plan_id"] == plan["plan_id"]
        ),
        None
    )

    if existing:
        raise ValueError("This plan has already been approved.")

    approval = {
        "approval_id": str(uuid.uuid4()),
        "plan_id": plan["plan_id"],
        "incident_id": plan["incident_id"],
        "approved": True,
        "approved_by": "LOCAL_OPERATOR",
        "approved_at": datetime.now(timezone.utc).isoformat()
    }

    APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    with APPROVAL_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(approval) + "\n")

    return approval


def main():
    print("===================================")
    print("       AEGIS APPROVAL CONTROLLER")
    print("===================================")

    plans = read_jsonl(PLAN_FILE)

    if not plans:
        print("No remediation plans found.")
        return

    plan = plans[-1]

    if plan.get("execution_status") != "NOT_EXECUTED":
        print("Plan is not eligible for approval.")
        return

    if not plan.get("approval_required"):
        print("Approval is not required.")
        return

    print(f"\nPlan ID: {plan['plan_id']}")
    print(f"Machine: {plan['machine']}")

    for item in plan["recommendations"]:
        print(f"- {item['action']}: {item['description']}")

    confirmation = input("\nApprove? (yes/no): ").strip().lower()

    if confirmation != "yes":
        print("Approval declined. No changes made.")
        return

    try:
        approval = record_approval(plan)
        print("\n[APPROVAL RECORDED]")
        print(f"Approval ID: {approval['approval_id']}")

    except ValueError as error:
        print(f"\n[REJECTED] {error}")


if __name__ == "__main__":
    main()
