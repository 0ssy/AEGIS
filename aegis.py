
import argparse
import socket
import sys
import time

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
AGENT_DIRECTORY = PROJECT_ROOT / "agents" / "python-agent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(AGENT_DIRECTORY))


import monitor

from intelligence import anomaly_detector
from intelligence import incident_correlator
from intelligence import root_cause_analyzer

from remediation import remediation_engine
from remediation import approval_controller
from remediation import execution_engine


class AEGIS:

    def __init__(self, samples=3, interval=5):

        self.samples = samples
        self.interval = interval

        self.telemetry = []
        self.anomalies = []
        self.incidents = []
        self.analyses = []
        self.plans = []

    def banner(self):

        print("=" * 50)
        print("              AEGIS")
        print("       AUTONOMOUS DEFENSE SYSTEM")
        print("=" * 50)

        print(f"Machine: {socket.gethostname()}")
        print(f"Telemetry samples: {self.samples}")
        print(f"Collection interval: {self.interval}s")

        print("=" * 50)

    def collect_telemetry(self):

        print("\n[STAGE 1] TELEMETRY COLLECTION")

        for index in range(self.samples):

            telemetry = monitor.collect_metrics()
            monitor.save_telemetry(telemetry)

            self.telemetry.append(telemetry)

            print(
                f"Sample {index + 1}/{self.samples} | "
                f"CPU: {telemetry['cpu']['usage_percent']}% | "
                f"RAM: {telemetry['memory']['usage_percent']}% | "
                f"DISK: {telemetry['disk']['usage_percent']}%"
            )

            if index < self.samples - 1:
                time.sleep(self.interval)

        print("[SUCCESS] Telemetry collection completed.")

    def detect_anomalies(self):

        print("\n[STAGE 2] ANOMALY DETECTION")

        records = anomaly_detector.load_telemetry()

        detected = anomaly_detector.detect_sustained_anomalies(
            records
        )

        new_anomalies = anomaly_detector.filter_new_anomalies(
            detected
        )

        anomaly_detector.save_anomalies(new_anomalies)

        self.anomalies = new_anomalies

        print(f"Records analyzed: {len(records)}")
        print(f"New anomalies: {len(new_anomalies)}")

        for anomaly in new_anomalies:

            print(
                f"[ANOMALY] {anomaly['resource'].upper()} | "
                f"{anomaly['observed_percent']}% | "
                f"{anomaly['machine']}"
            )

        if not new_anomalies:
            print("[INFO] No new anomalies detected.")

        return new_anomalies

    def correlate_incidents(self):

        print("\n[STAGE 3] INCIDENT CORRELATION")

        events = incident_correlator.load_anomalies()

        existing_event_ids = (
            incident_correlator.load_existing_incident_events()
        )

        new_events = [
            event for event in events
            if event["event_id"] not in existing_event_ids
        ]

        if not new_events:

            print("[INFO] No unprocessed anomaly events.")
            return []

        groups = incident_correlator.correlate_events(
            new_events
        )

        self.incidents = [
            incident_correlator.build_incident(group)
            for group in groups
        ]

        incident_correlator.save_incidents(self.incidents)

        print(f"New incidents: {len(self.incidents)}")

        for incident in self.incidents:

            print("\n[INCIDENT CREATED]")

            print(f"ID: {incident['incident_id']}")
            print(f"Machine: {incident['machine']}")
            print(f"Severity: {incident['severity']}")

            print(
                f"Resources: {incident['affected_resources']}"
            )

        return self.incidents

    def analyze_root_causes(self):

        print("\n[STAGE 4] ROOT-CAUSE ANALYSIS")

        telemetry = root_cause_analyzer.load_jsonl(
            root_cause_analyzer.TELEMETRY_FILE
        )

        for incident in self.incidents:

            analysis = root_cause_analyzer.analyze_incident(
                incident,
                telemetry
            )

            root_cause_analyzer.save_analysis(analysis)

            self.analyses.append(analysis)

            print(f"\nIncident: {incident['incident_id']}")

            print(
                f"Telemetry analyzed: "
                f"{analysis['telemetry_records_analyzed']}"
            )

            print(
                f"Hypotheses: {len(analysis['hypotheses'])}"
            )

            for hypothesis in analysis["hypotheses"]:

                print(
                    f"[HYPOTHESIS] {hypothesis['rule_id']} | "
                    f"Confidence: {hypothesis['confidence']}"
                )

        return self.analyses

    def generate_remediation_plans(self):

        print("\n[STAGE 5] REMEDIATION PLANNING")

        for incident, analysis in zip(
            self.incidents,
            self.analyses
        ):

            plan = remediation_engine.generate_plan(
                incident,
                analysis
            )

            if not plan["recommendations"]:

                print(
                    f"[INFO] No actionable recommendations "
                    f"for incident {incident['incident_id']}."
                )

                continue

            remediation_engine.save_plan(plan)

            self.plans.append(plan)

            print("\n[PLAN CREATED]")

            print(f"Plan ID: {plan['plan_id']}")
            print(f"Machine: {plan['machine']}")

            for recommendation in plan["recommendations"]:

                print(
                    f"- {recommendation['action']} "
                    f"| Risk: {recommendation['risk']}"
                )

            print("Execution: NOT_EXECUTED")
            print("Approval: REQUIRED")

        return self.plans

    def approve_and_execute(self):

        print("\n[STAGE 6] HUMAN APPROVAL AND EXECUTION")

        if not self.plans:

            print("[INFO] No remediation plans to process.")
            return

        for plan in self.plans:

            print("\n" + "-" * 45)
            print(f"Plan: {plan['plan_id']}")
            print(f"Machine: {plan['machine']}")

            unsupported_actions = [
                item["action"]
                for item in plan["recommendations"]
                if item["action"]
                not in execution_engine.SUPPORTED_ACTIONS
            ]

            if unsupported_actions:

                print("[MANUAL REVIEW REQUIRED]")
                print("Unsupported execution actions:")

                for action in unsupported_actions:
                    print(f"- {action}")

                print("No approval or execution attempted.")
                continue

            print("\nRecommendations:")

            for item in plan["recommendations"]:

                print(
                    f"- {item['action']}: "
                    f"{item['description']}"
                )

            confirmation = input(
                "\nApprove this remediation plan? (yes/no): "
            ).strip().lower()

            if confirmation != "yes":

                print("[DECLINED] No execution performed.")
                continue

            try:

                approval = approval_controller.record_approval(
                    plan
                )

                print("[APPROVED]")
                print(f"Approval ID: {approval['approval_id']}")

                execution = execution_engine.execute_plan(
                    plan["plan_id"]
                )

                print("\n[EXECUTION SUCCESSFUL]")

                print(
                    f"Execution ID: "
                    f"{execution['execution_id']}"
                )

                print(
                    f"Status: "
                    f"{execution['execution_status']}"
                )

            except (
                ValueError,
                PermissionError,
                RuntimeError
            ) as error:

                print(f"[EXECUTION REJECTED] {error}")

    def run(self):

        self.banner()

        self.collect_telemetry()
        self.detect_anomalies()
        self.correlate_incidents()

        if not self.incidents:

            print("\n[AEGIS] No new incidents.")
            print("[AEGIS] Pipeline completed.")
            return

        self.analyze_root_causes()
        self.generate_remediation_plans()
        self.approve_and_execute()

        print("\n" + "=" * 50)
        print("          AEGIS PIPELINE COMPLETE")
        print("=" * 50)


def main():

    parser = argparse.ArgumentParser(
        description="AEGIS Autonomous Defense System"
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Number of telemetry samples to collect."
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds between telemetry samples."
    )

    args = parser.parse_args()

    if args.samples < 1:
        parser.error("--samples must be at least 1")

    if args.interval < 1:
        parser.error("--interval must be at least 1")

    system = AEGIS(
        samples=args.samples,
        interval=args.interval
    )

    system.run()


if __name__ == "__main__":
    main()
