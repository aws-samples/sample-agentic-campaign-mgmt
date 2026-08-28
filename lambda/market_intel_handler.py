# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler for Function URL — get_market_intelligence.

This handler demonstrates the OpenAPI Schema target type for AgentCore Gateway.
The Gateway reads an OpenAPI spec (from S3) to discover tool schemas, then
routes HTTP requests to this Lambda Function URL as the backend.

Event format (Lambda Function URL / API Gateway v2 payload):
    {
        "version": "2.0",
        "requestContext": {"http": {"method": "POST", "path": "/"}},
        "headers": {"content-type": "application/json"},
        "body": "{\"campaign_id\": \"4782\"}",
        "isBase64Encoded": false
    }

Returns:
    {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": "{...}"
    }

Deploy:
    uv run python deploy/deploy_multi_target_gateway.py
"""
import json
import traceback

from handler import get_market_intelligence


def lambda_handler(event, context):
    """Function URL handler for get_market_intelligence."""
    print(f"[market_intel_handler] event: {json.dumps(event)}")

    try:
        body = {}
        if event.get("body"):
            raw = event["body"]
            if event.get("isBase64Encoded"):
                import base64
                raw = base64.b64decode(raw).decode("utf-8")
            body = json.loads(raw)

        result = get_market_intelligence(**body)
        return _response(200, result)

    except Exception as exc:
        traceback.print_exc()
        return _response(500, {"error": str(exc)})


def _response(status_code, body):
    """Build a Function URL / API Gateway v2 response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
