
import json
import os
import uuid
import tempfile

from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PLAN_FILE = PROJECT_ROOT / "logs" / "remediation_plans.jsonl"
APPROVAL_FILE = PROJECT_ROOT / "logs" / "remediation_approvals.jsonl"
EXECUTION_FILE = PROJECT_ROOT / "logs" / "remediation_executions.jsonl"

SUPPORTED_ACTIONS = {
    "INSPECT_MEMORY_CONSUMING_PROCESSES"
}


def read_jsonl(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


@contextmanager
def execution_lock():
    lock_file = EXECUTION_FILE.with_suffix(".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with lock_file.open("a+b") as file:
        if file.seek(0, os.SEEK_END) == 0:
            file.write(b"\0")
            file.flush()

        file.seek(0)

        if os.name == "nt":
            import msvcrt
            msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)

        try:
            yield
        finally:
            file.seek(0)

            if os.name == "nt":
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def atomic_write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp"
        ) as temporary_file:

            temporary_path = Path(temporary_file.name)

            for record in records:
                temporary_file.write(json.dumps(record) + "\n")

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def append_audit_record(record):
    EXECUTION_FILE.parent.mkdir(parents=True, exist_ok=True)

    with EXECUTION_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
        file.flush()
        os.fsync(file.fileno())


def get_process_diagnostics():
    try:
        import psutil
    except ImportError as error:
        raise RuntimeError(
            "Install psutil using: pip install psutil"
        ) from error

    processes = []

    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = process.info
            memory = info.get("memory_info")

            if memory:
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "memory_mb": round(
                        memory.rss / (1024 * 1024), 2
                    )
                })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(
        key=lambda item: item["memory_mb"],
        reverse=True
    )

    return processes[:10]


def reconcile_execution_state(plans, executions):
    """Recover plan status from successful execution audit records."""

    changed = False

    for plan in plans:
        plan_id = plan.get("plan_id")

        successful_records = [
            record for record in executions
            if record.get("plan_id") == plan_id
            and record.get("execution_status") == "SUCCESS"
        ]

        if not successful_records:
            continue

        if len(successful_records) > 1:
            raise ValueError(
                f"Multiple successful execution records found for {plan_id}."
            )

        execution = successful_records[0]

        if plan.get("execution_status") == "NOT_EXECUTED":
            plan["execution_status"] = "EXECUTED"
            plan["execution_id"] = execution["execution_id"]
            plan["executed_at"] = execution["executed_at"]
            changed = True

        elif plan.get("execution_status") == "EXECUTED":
            if plan.get("execution_id") != execution.get("execution_id"):
                raise ValueError(
                    f"Execution ID mismatch for plan {plan_id}."
                )

    if changed:
        atomic_write_jsonl(PLAN_FILE, plans)

    return changed


def execute_plan(plan_id):
    with execution_lock():

        plans = read_jsonl(PLAN_FILE)
        approvals = read_jsonl(APPROVAL_FILE)
        executions = read_jsonl(EXECUTION_FILE)

        reconcile_execution_state(plans, executions)

        matching_plans = [
            plan for plan in plans
            if plan.get("plan_id") == plan_id
        ]

        if not matching_plans:
            raise ValueError("Remediation plan not found.")

        if len(matching_plans) != 1:
            raise ValueError("Duplicate plan IDs found.")

        plan = matching_plans[0]

        if plan.get("execution_status") != "NOT_EXECUTED":
            raise ValueError("Plan is not eligible for execution.")

        if not plan.get("approval_required"):
            raise PermissionError("Plan does not require approval.")

        approval = next(
            (
                item for item in approvals
                if item.get("plan_id") == plan_id
                and item.get("approved") is True
            ),
            None
        )

        if not approval:
            raise PermissionError("No valid approval found.")

        if any(
            item.get("plan_id") == plan_id
            for item in executions
        ):
            raise ValueError("This plan already has an execution record.")

        recommendations = plan.get("recommendations", [])

        if not recommendations:
            raise ValueError("Plan contains no recommendations.")

        for recommendation in recommendations:
            if recommendation.get("action") not in SUPPORTED_ACTIONS:
                raise ValueError(
                    f"Unsupported action: {recommendation.get('action')}"
                )

        results = []

        for recommendation in recommendations:
            action = recommendation["action"]

            if action == "INSPECT_MEMORY_CONSUMING_PROCESSES":
                processes = get_process_diagnostics()

                results.append({
                    "action": action,
                    "status": "SUCCESS",
                    "result": processes
                })

        execution_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        execution = {
            "execution_id": execution_id,
            "plan_id": plan_id,
            "incident_id": plan["incident_id"],
            "approval_id": approval["approval_id"],
            "executed_at": timestamp,
            "execution_status": "SUCCESS",
            "results": results
        }

        append_audit_record(execution)

        plan["execution_status"] = "EXECUTED"
        plan["execution_id"] = execution_id
        plan["executed_at"] = timestamp

        atomic_write_jsonl(PLAN_FILE, plans)

        return execution


def main():
    print("===================================")
    print("       AEGIS EXECUTION ENGINE")
    print("===================================")

    plans = read_jsonl(PLAN_FILE)
    executions = read_jsonl(EXECUTION_FILE)

    if not plans:
        print("No remediation plans found.")
        return

    try:
        if reconcile_execution_state(plans, executions):
            print("\n[RECOVERY] Execution states reconciled.")

        plans = read_jsonl(PLAN_FILE)
        plan = plans[-1]

        print(f"\nPlan ID: {plan['plan_id']}")
        print(f"Machine: {plan['machine']}")
        print(f"Status: {plan['execution_status']}")

        if plan["execution_status"] == "EXECUTED":
            print("\n[BLOCKED] This plan has already been executed.")
            return

        confirmation = input(
            "\nExecute approved diagnostic actions? (yes/no): "
        ).strip().lower()

        if confirmation != "yes":
            print("Execution cancelled.")
            return

        execution = execute_plan(plan["plan_id"])

        print("\n[EXECUTION SUCCESSFUL]")
        print(f"Execution ID: {execution['execution_id']}")

        for result in execution["results"]:
            print(f"\nAction: {result['action']}")

            for process in result["result"]:
                print(
                    f"PID: {process['pid']} | "
                    f"{process['name']} | "
                    f"{process['memory_mb']} MB"
                )

        print("\nPlan status: EXECUTED")
        print(f"Audit record: {EXECUTION_FILE}")

    except (ValueError, PermissionError, RuntimeError) as error:
        print(f"\n[EXECUTION REJECTED] {error}")


if __name__ == "__main__":
    main()
