
import json
from datetime import datetime, timezone


def lambda_handler(event, context=None):
    """
    AEGIS telemetry processing handler.

    Accepts a telemetry record directly or through an
    API Gateway-style event containing a JSON body.
    """

    try:
        if isinstance(event, dict) and "body" in event:
            body = event["body"]

            if isinstance(body, str):
                telemetry = json.loads(body)
            elif isinstance(body, dict):
                telemetry = body
            else:
                return response(400, {
                    "error": "Invalid event body"
                })
        else:
            telemetry = event

        if not isinstance(telemetry, dict):
            return response(400, {
                "error": "Telemetry must be a JSON object"
            })

        required_fields = [
            "timestamp",
            "machine",
            "cpu",
            "memory",
            "disk",
            "processes"
        ]

        missing = [
            field for field in required_fields
            if field not in telemetry
        ]

        if missing:
            return response(400, {
                "error": "Missing required fields",
                "missing_fields": missing
            })

        if not isinstance(telemetry["machine"], dict):
            return response(400, {"error": "Invalid machine data"})

        for field in ("cpu", "memory", "disk"):
            if not isinstance(telemetry[field], dict):
                return response(400, {
                    "error": f"Invalid {field} data"
                })

        if not isinstance(telemetry["processes"], list):
            return response(400, {
                "error": "Invalid processes data"
            })

        processed_record = {
            "record_id": telemetry.get("event_id"),
            "machine": telemetry["machine"].get(
                "hostname", "UNKNOWN"
            ),
            "timestamp": telemetry["timestamp"],
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "cpu_usage_percent": telemetry["cpu"].get(
                    "usage_percent"
                ),
                "memory_usage_percent": telemetry["memory"].get(
                    "usage_percent"
                ),
                "disk_usage_percent": telemetry["disk"].get(
                    "usage_percent"
                ),
                "process_count": len(telemetry["processes"])
            },
            "processing_status": "PROCESSED"
        }

        return response(200, processed_record)

    except json.JSONDecodeError:
        return response(400, {"error": "Malformed JSON"})

    except Exception as error:
        return response(500, {
            "error": "Telemetry processing failed",
            "details": str(error)
        })


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }
