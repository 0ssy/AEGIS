
# Phase 2 — Telemetry Infrastructure

## Status

**Local implementation: Complete**

**AWS deployment: Pending**

Phase 2 establishes the telemetry collection, ingestion, processing, queuing, and persistence pipeline for AEGIS.

The implementation currently uses local Python services and SQLite to reproduce the core responsibilities of the planned AWS architecture without requiring paid cloud infrastructure.

## 1. Architecture

```text
Host Machine
     |
     v
Python Monitoring Agent
     |
     | HTTP POST
     v
Local Ingestion Server
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

## 2. Monitoring Agent

Location: `agents/python-agent/monitor.py`

The monitoring agent collects host-level telemetry using Python and psutil.

Collected information includes:

- CPU utilisation
- Logical and physical CPU cores
- Memory usage and availability
- Disk utilisation
- Running process information
- Machine hostname
- Operating system and architecture
- Collection timestamp

The agent stores telemetry locally in JSONL format.

When an ingestion endpoint is configured through `AEGIS_INGESTION_URL`, it transmits telemetry over HTTP.

The transport layer supports retries for temporary network failures and retryable HTTP responses.

## 3. Ingestion Service

Location: `backend/ingestion_server.py`

The ingestion service uses Python's standard HTTP server implementation.

Endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health and queue statistics |
| POST | `/telemetry` | Receive telemetry events |

The ingestion service:

1. Receives telemetry over HTTP.
2. Validates the payload structure.
3. Generates a unique event identifier.
4. Enqueues the event.
5. Persists the raw telemetry record.
6. Returns an HTTP 202 response when accepted.

The local server listens on `127.0.0.1:8765`.

## 4. Message Queue

Location: `backend/message_queue.py`

The local queue uses SQLite to implement persistent message handling.

Supported operations:

- Enqueue messages.
- Receive batches of messages.
- Track message processing status.
- Apply visibility timeouts.
- Acknowledge successful processing.
- Release failed messages for retry.
- Track queue statistics.

Messages use the following states:

- `QUEUED`
- `IN_FLIGHT`

The implementation provides persistent local queue behaviour inspired by Amazon SQS.

It is not an actual SQS deployment.

## 5. Telemetry Processor

Location: `backend/lambda_processor.py`

The processor exposes a Lambda-compatible handler:

`lambda_handler(event, context=None)`

It accepts telemetry directly or through an API Gateway-style event.

It validates input and transforms raw telemetry into a processed record containing:

- Record identifier
- Machine identifier
- Original timestamp
- Processing timestamp
- CPU utilisation
- Memory utilisation
- Disk utilisation
- Process count
- Processing status

The processor is currently executed locally by the queue worker, not deployed as an AWS Lambda function.

## 6. Queue Worker

Location: `backend/queue_worker.py`

The queue worker:

1. Receives queued telemetry.
2. Passes events to the processor.
3. Persists processed records.
4. Acknowledges successful messages.
5. Releases failed messages for retry.

Current reliability features include:

- Batch processing
- Visibility timeouts
- Retry delays
- Maximum processing attempts
- Idempotency checks against stored record identifiers

Messages exceeding the configured retry count are retained for later inspection with a longer retry delay.

A dedicated dead-letter queue is not yet implemented.

## 7. Telemetry Storage

Location: `backend/telemetry_store.py`

The local persistent telemetry store uses SQLite.

Database location:

`logs/aegis_telemetry.db`

The storage layer supports:

- Saving telemetry records
- Retrieving individual records
- Retrieving records by machine
- Retrieving recent records
- Paginated queries
- Time-range queries
- Record counting
- Record deletion

Indexes support machine-based and timestamp-based queries.

The SQLite implementation provides local persistence inspired by the planned DynamoDB role. It is not an actual DynamoDB deployment.

## 8. Configuration

The monitoring agent uses the following environment variable:

`AEGIS_INGESTION_URL`

Example:

```powershell
$env:AEGIS_INGESTION_URL="http://127.0.0.1:8765/telemetry"
```

Without this variable, the monitoring agent can continue collecting and saving telemetry locally.

## 9. Running the Pipeline

Start the ingestion server:

```powershell
python backend/ingestion_server.py
```

Start the queue worker in another terminal:

```powershell
python backend/queue_worker.py
```

Configure and run the monitoring agent in a third terminal:

```powershell
$env:AEGIS_INGESTION_URL="http://127.0.0.1:8765/telemetry"
python agents/python-agent/monitor.py
```

## 10. Testing and Verification

The complete project test suite was run after Phase 2 implementation.

Recorded result:

**99 tests passed.**

The live local pipeline was also exercised.

The recorded verification included:

- Successful telemetry collection.
- Successful HTTP transmission.
- HTTP 202 ingestion responses.
- Queue processing.
- Persistent telemetry storage.
- Empty queue and no in-flight messages at the final queue check.
- 69 stored telemetry records at the final reported count.

These results describe the local test environment and are not AWS deployment results.

## 11. AWS Service Mapping

| Local implementation | Planned AWS service |
|---|---|
| Local HTTP ingestion server | API Gateway |
| Python telemetry processor | AWS Lambda |
| SQLite message queue | Amazon SQS |
| SQLite telemetry store | Amazon DynamoDB |
| Local JSONL telemetry logs | Amazon S3 / CloudWatch Logs |
| Python monitoring agent | Custom telemetry agent |

The AWS integrations remain pending.

## 12. Known Limitations

- No actual API Gateway deployment.
- No actual Lambda deployment.
- No actual SQS queue.
- No actual DynamoDB table.
- No distributed multi-node deployment verification.
- No dedicated dead-letter queue.
- No production AWS security configuration.

These are not represented as completed features.

## Conclusion

Phase 2 establishes the local telemetry infrastructure required for AEGIS.

The collection, ingestion, queueing, processing, persistence, and test workflows are implemented locally.

This provides the foundation for the intelligence capabilities in Phase 3.
