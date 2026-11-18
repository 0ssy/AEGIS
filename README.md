
# AEGIS
### Distributed Cloud Intelligence & Reliability Platform

AEGIS is a cloud reliability and infrastructure intelligence platform designed to monitor distributed systems, detect abnormal behaviour, investigate incidents, identify potential root causes, and support controlled recovery.

The project explores how telemetry, anomaly detection, incident correlation, and automated operational workflows can work together to improve infrastructure reliability and developer experience.

## Project Status

AEGIS is under active development.

- Phase 1 — Cloud Foundations: Local development foundation established; AWS infrastructure deployment remains pending.
- Phase 2 — Telemetry Infrastructure: Local implementation completed and tested.
- Phase 3 — Intelligence: Planned / under development.
- Phase 4 — Automated Recovery: Planned.
- Phase 5 — Security and Reliability: Planned.
- Phase 6 — Production-Style Deployment: Planned.

**Important:** The current implementation runs locally. AWS services listed in the roadmap have not yet been deployed.

## Architecture

The current local telemetry pipeline:

```text
Python Monitoring Agent
        |
        v
Local HTTP Ingestion Server
        |
        v
SQLite Message Queue
        |
        v
Queue Worker
        |
        v
Telemetry Processor
        |
        v
SQLite Telemetry Store
```

Telemetry is collected from the host machine, transmitted to the ingestion service, queued for processing, and stored for later analysis.

## Implemented Components

### Monitoring Agent
- CPU utilisation
- Memory utilisation
- Disk utilisation
- Process information
- Machine and operating system information
- Local JSONL telemetry logging
- HTTP telemetry transmission
- Retry handling

### Ingestion Infrastructure
- Local HTTP ingestion server
- Telemetry validation
- Event identification
- Message queue integration

### Processing Infrastructure
- Lambda-compatible Python processor
- Persistent SQLite message queue
- Queue worker
- Message acknowledgement and retry handling

### Telemetry Storage
- SQLite persistence
- Machine-based queries
- Recent telemetry queries
- Pagination
- Time-range queries
- Indexed database fields

### Intelligence and Remediation
The repository also contains initial implementations of:
- Anomaly detection
- Incident correlation
- Root-cause analysis
- Remediation workflows
- Approval control
- Execution handling

These components will be reviewed and developed further in their respective roadmap phases.

## Technology Stack

- Python
- SQLite
- HTTP
- psutil
- JSON / JSONL
- unittest

## Running Locally

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the monitoring dependency:

```powershell
pip install psutil
```

Start the ingestion server:

```powershell
python backend/ingestion_server.py
```

In a second terminal, activate the same virtual environment and start the worker:

```powershell
python backend/queue_worker.py
```

In a third terminal, configure the ingestion endpoint and run the monitoring agent:

```powershell
$env:AEGIS_INGESTION_URL="http://127.0.0.1:8765/telemetry"
python agents/python-agent/monitor.py
```

## Tests

Run the complete test suite:

```powershell
python -m unittest discover -s tests -v
```

Latest recorded result: **99 tests passed**.

## Original Development Roadmap

### Phase 1 — Cloud Foundations
- Create and secure an AWS account.
- Learn IAM, VPC, EC2 and S3.
- Set up Terraform.
- Deploy a basic Python application.
- Configure CloudWatch.

### Phase 2 — Telemetry Infrastructure
- Build the Python monitoring agent.
- Collect system metrics.
- Send events through API Gateway.
- Process events with Lambda.
- Introduce SQS and DynamoDB.

### Phase 3 — Intelligence
- Build anomaly detection algorithms.
- Create service dependency graphs.
- Implement incident correlation.
- Generate root-cause hypotheses.

### Phase 4 — Automated Recovery
- Create remediation workflows.
- Integrate EventBridge.
- Implement approval mechanisms.
- Verify recovery automatically.

### Phase 5 — Security and Reliability
- Implement least-privilege IAM.
- Add encryption and audit logs.
- Test failure scenarios.
- Introduce dead-letter queues.
- Test disaster recovery.

### Phase 6 — Production-Style Deployment
- Build the React dashboard.
- Implement authentication.
- Configure CI/CD.
- Add automated tests.
- Deploy a complete demonstration environment.

## Development Principle

AEGIS is intended to work above cloud infrastructure providers rather than recreate their underlying services.

Its long-term direction is to make infrastructure operations more understandable, observable, predictable, and reliable.

## License

License to be determined.
```


