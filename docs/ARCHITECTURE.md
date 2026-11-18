
# AEGIS — System Architecture

## 1. Overview

AEGIS is designed as a distributed cloud intelligence and reliability platform.

Its architecture is intended to support telemetry collection, event processing, infrastructure intelligence, incident investigation, and controlled remediation.

The current implementation is a local Python-based system.

## 2. Current Architecture

```text
                  HOST MACHINE
                       |
                       v
              PYTHON MONITORING AGENT
                       |
                       | HTTP
                       v
               INGESTION SERVER
                       |
                       v
                MESSAGE QUEUE
                       |
                       v
                 QUEUE WORKER
                       |
                       v
               TELEMETRY PROCESSOR
                       |
                       v
                TELEMETRY STORE
                       |
                       v
                 INTELLIGENCE
                       |
                       v
                 REMEDIATION
```

## 3. Repository Structure

```text
AEGIS/
|
|-- agents/
|   |-- python-agent/
|       |-- monitor.py
|
|-- backend/
|   |-- ingestion_server.py
|   |-- lambda_processor.py
|   |-- message_queue.py
|   |-- queue_worker.py
|   |-- telemetry_store.py
|
|-- intelligence/
|   |-- anomaly_detector.py
|   |-- incident_correlator.py
|   |-- root_cause_analyzer.py
|
|-- remediation/
|   |-- approval_controller.py
|   |-- execution_engine.py
|   |-- remediation_engine.py
|
|-- tests/
|
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- PHASE-1-CLOUD-FOUNDATIONS.md
|   |-- PHASE-2-TELEMETRY.md
|
|-- infrastructure/
|
|-- logs/
|
|-- aegis.py
|-- README.md
|-- .gitignore
```

Local runtime data and generated databases under `logs/` are excluded from version control.

## 4. Component Responsibilities

### Agents
Collect infrastructure telemetry from monitored machines.

### Backend
Receives telemetry, validates events, queues messages, processes records, and stores telemetry.

### Intelligence
Analyses telemetry to identify anomalies, correlate incidents, and generate root-cause hypotheses.

### Remediation
Provides the foundation for controlled operational actions, approval, and execution.

### Tests
Verify component behaviour and integration.

### Infrastructure
Reserved for infrastructure definitions and deployment configuration.

### Documentation
Records architecture, implementation status, operational instructions, and development phases.

## 5. Planned Cloud Architecture

The long-term AWS architecture maps local responsibilities to managed services:

| Responsibility | Planned AWS technology |
|---|---|
| Compute | ECS Fargate |
| API ingestion | API Gateway |
| Event processing | AWS Lambda |
| Message delivery | Amazon SQS |
| Event routing | Amazon EventBridge |
| Structured storage | Amazon DynamoDB |
| Object storage | Amazon S3 |
| Monitoring | Amazon CloudWatch |
| Infrastructure | Terraform |
| Access control | IAM |

These are planned integrations, not currently deployed infrastructure.

## 6. Architectural Principles

AEGIS is being developed around the following principles:

- **Observability:** Infrastructure behaviour should be measurable.
- **Reliability:** Failures should be detected and investigated systematically.
- **Traceability:** Operational events and decisions should retain their evidence.
- **Controlled automation:** Remediation should be subject to appropriate approval and verification.
- **Developer experience:** Infrastructure operations should be understandable and manageable.
- **Provider independence:** Core intelligence should not depend entirely on one cloud provider.

## 7. Development Direction

The architecture follows the original six-phase roadmap:

1. Cloud Foundations.
2. Telemetry Infrastructure.
3. Intelligence.
4. Automated Recovery.
5. Security and Reliability.
6. Production-Style Deployment.

The local implementation provides a foundation for developing and testing these capabilities before cloud deployment.
