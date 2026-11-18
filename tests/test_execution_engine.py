
import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from remediation import execution_engine as engine


class TestExecutionEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.plan_file = Path(self.temp_dir.name) / "plans.jsonl"
        self.approval_file = Path(self.temp_dir.name) / "approvals.jsonl"
        self.execution_file = Path(self.temp_dir.name) / "executions.jsonl"

        self.original_paths = (
            engine.PLAN_FILE,
            engine.APPROVAL_FILE,
            engine.EXECUTION_FILE
        )
        self.addCleanup(self.restore_engine_paths)

        engine.PLAN_FILE = self.plan_file
        engine.APPROVAL_FILE = self.approval_file
        engine.EXECUTION_FILE = self.execution_file

        self.plan = {
            "plan_id": "plan-001",
            "incident_id": "incident-001",
            "machine": "IGGY",
            "execution_status": "NOT_EXECUTED",
            "approval_required": True,
            "recommendations": [
                {"action": "INSPECT_MEMORY_CONSUMING_PROCESSES"}
            ]
        }

        self.approval = {
            "approval_id": "approval-001",
            "plan_id": "plan-001",
            "approved": True
        }

        self.write_jsonl(self.plan_file, [self.plan])
        self.write_jsonl(self.approval_file, [self.approval])

    def restore_engine_paths(self):
        (
            engine.PLAN_FILE,
            engine.APPROVAL_FILE,
            engine.EXECUTION_FILE
        ) = self.original_paths

    @staticmethod
    def write_jsonl(path, records):
        with path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record) + "\n")

    def successful_execution(self, execution_id="execution-001"):
        return {
            "execution_id": execution_id,
            "plan_id": "plan-001",
            "incident_id": "incident-001",
            "approval_id": "approval-001",
            "executed_at": "2026-11-14T18:00:00+00:00",
            "execution_status": "SUCCESS",
            "results": []
        }

    @patch.object(engine, "get_process_diagnostics", return_value=[])
    def test_approved_plan_executes(self, mock_diagnostics):
        result = engine.execute_plan("plan-001")

        self.assertEqual(result["execution_status"], "SUCCESS")
        mock_diagnostics.assert_called_once()

        updated_plans = engine.read_jsonl(self.plan_file)
        self.assertEqual(updated_plans[0]["execution_status"], "EXECUTED")

    def test_unapproved_plan_is_rejected(self):
        self.write_jsonl(self.approval_file, [])

        with self.assertRaises(PermissionError):
            engine.execute_plan("plan-001")

    def test_unknown_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            engine.execute_plan("unknown-plan")

    def test_duplicate_execution_is_rejected(self):
        self.write_jsonl(
            self.execution_file,
            [{"plan_id": "plan-001"}]
        )

        with self.assertRaises(ValueError):
            engine.execute_plan("plan-001")

    def test_unsupported_action_is_rejected(self):
        self.plan["recommendations"][0]["action"] = "DELETE_SYSTEM_FILES"
        self.write_jsonl(self.plan_file, [self.plan])

        with self.assertRaises(ValueError):
            engine.execute_plan("plan-001")

    @patch.object(engine, "get_process_diagnostics", return_value=[])
    def test_execution_is_audited(self, mock_diagnostics):
        engine.execute_plan("plan-001")

        records = engine.read_jsonl(self.execution_file)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["plan_id"], "plan-001")
        self.assertEqual(records[0]["approval_id"], "approval-001")

    def test_successful_audit_reconciles_plan_status(self):
        execution = self.successful_execution()

        self.write_jsonl(self.execution_file, [execution])

        plans = engine.read_jsonl(self.plan_file)

        changed = engine.reconcile_execution_state(
            plans,
            [execution]
        )

        updated_plans = engine.read_jsonl(self.plan_file)

        self.assertTrue(changed)
        self.assertEqual(updated_plans[0]["execution_status"], "EXECUTED")
        self.assertEqual(
            updated_plans[0]["execution_id"],
            "execution-001"
        )
        self.assertEqual(
            updated_plans[0]["executed_at"],
            execution["executed_at"]
        )

    def test_mismatched_execution_id_is_rejected(self):
        execution = self.successful_execution()

        self.plan["execution_status"] = "EXECUTED"
        self.plan["execution_id"] = "different-execution"
        self.write_jsonl(self.plan_file, [self.plan])
        self.write_jsonl(self.execution_file, [execution])

        plans = engine.read_jsonl(self.plan_file)

        with self.assertRaises(ValueError):
            engine.reconcile_execution_state(plans, [execution])

    def test_duplicate_successful_audit_records_are_rejected(self):
        execution_one = self.successful_execution("execution-001")
        execution_two = self.successful_execution("execution-002")

        self.write_jsonl(
            self.execution_file,
            [execution_one, execution_two]
        )

        plans = engine.read_jsonl(self.plan_file)

        with self.assertRaises(ValueError):
            engine.reconcile_execution_state(
                plans,
                [execution_one, execution_two]
            )


if __name__ == "__main__":
    unittest.main()
