# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler for API Gateway REST API proxy integration — get_campaign_metrics.

This handler demonstrates the API Gateway target type for AgentCore Gateway.
API Gateway auto-discovers REST endpoints and maps them to MCP tools.

Event format (API Gateway proxy integration v1):
    {
        "httpMethod": "POST",
        "path": "/campaign-metrics",
        "body": "{\"campaign_id\": \"4782\", \"time_range\": \"current\"}",
        "queryStringParameters": {"campaign_id": "4782"},
        ...
    }

Returns API Gateway proxy response:
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

from handler import get_campaign_metrics


def lambda_handler(event, context):
    """API Gateway proxy integration handler for get_campaign_metrics."""
    print(f"[apigw_handler] event: {json.dumps(event)}")

    try:
        # Extract parameters from POST body or query string
        body = {}
        if event.get("body"):
            body = json.loads(event["body"])

        query = event.get("queryStringParameters") or {}

        campaign_id = body.get("campaign_id") or query.get("campaign_id")
        if not campaign_id:
            return _response(400, {"error": "campaign_id is required"})

        kwargs = {"campaign_id": campaign_id}
        time_range = body.get("time_range") or query.get("time_range")
        if time_range:
            kwargs["time_range"] = time_range

        result = get_campaign_metrics(**kwargs)
        return _response(200, result)

    except Exception as exc:
        traceback.print_exc()
        return _response(500, {"error": str(exc)})


def _response(status_code, body):
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
