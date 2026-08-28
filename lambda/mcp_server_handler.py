# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler implementing the MCP JSON-RPC protocol — generate_recommendation.

This handler demonstrates the MCP Server target type for AgentCore Gateway.
The Gateway connects to this Lambda Function URL as a remote MCP server,
sending JSON-RPC messages for tool discovery (tools/list) and invocation
(tools/call).

MCP Streamable HTTP transport:
    - Client POSTs JSON-RPC requests to the endpoint
    - Server responds with JSON-RPC results
    - Supports: initialize, notifications/initialized, tools/list, tools/call

Event format (Lambda Function URL):
    {
        "version": "2.0",
        "requestContext": {"http": {"method": "POST", "path": "/"}},
        "headers": {"content-type": "application/json"},
        "body": "{\"jsonrpc\": \"2.0\", \"method\": \"tools/list\", \"id\": 1}",
        "isBase64Encoded": false
    }

Deploy:
    uv run python deploy/deploy_multi_target_gateway.py
"""
import json
import traceback

from handler import generate_recommendation

# MCP protocol version
PROTOCOL_VERSION = "2025-03-26"

# Tool definition exposed by this MCP server
TOOL_DEFINITIONS = [
    {
        "name": "generate_recommendation",
        "description": (
            "Generate specific, actionable recommendations to fix campaign "
            "issues. Uses ML diagnosis + market intelligence + historical "
            "outcomes to produce bid adjustments, targeting changes, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (e.g. '4782')",
                },
                "issue_type": {
                    "type": "string",
                    "description": "Optional: specific issue type to address",
                },
            },
            "required": ["campaign_id"],
        },
    },
]

# Server capabilities
SERVER_INFO = {
    "protocolVersion": PROTOCOL_VERSION,
    "capabilities": {
        "tools": {"listChanged": False},
    },
    "serverInfo": {
        "name": "campaign-opt-recommendation-mcp",
        "version": "1.0.0",
    },
}


def lambda_handler(event, context):
    """MCP JSON-RPC server handler via Lambda Function URL."""
    print(f"[mcp_server_handler] event keys: {list(event.keys())}")

    try:
        # Parse the JSON-RPC request body
        raw_body = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            import base64
            raw_body = base64.b64decode(raw_body).decode("utf-8")

        request = json.loads(raw_body)
        method = request.get("method", "")
        req_id = request.get("id")

        print(f"[mcp_server_handler] method={method}, id={req_id}")

        # Route by JSON-RPC method
        if method == "initialize":
            return _jsonrpc_response(req_id, SERVER_INFO)

        elif method == "notifications/initialized":
            # Notification — no response required (but Function URL needs a return)
            return {"statusCode": 200, "body": "", "headers": _headers()}

        elif method == "tools/list":
            return _jsonrpc_response(req_id, {"tools": TOOL_DEFINITIONS})

        elif method == "tools/call":
            return _handle_tool_call(request, req_id)

        elif method == "ping":
            return _jsonrpc_response(req_id, {})

        else:
            return _jsonrpc_error(
                req_id, -32601, f"Method not found: {method}"
            )

    except json.JSONDecodeError as exc:
        return _jsonrpc_error(None, -32700, f"Parse error: {exc}")
    except Exception as exc:
        traceback.print_exc()
        return _jsonrpc_error(None, -32603, f"Internal error: {exc}")


def _handle_tool_call(request, req_id):
    """Handle tools/call — dispatch to generate_recommendation."""
    params = request.get("params", {})
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name != "generate_recommendation":
        return _jsonrpc_error(
            req_id, -32602, f"Unknown tool: {tool_name}"
        )

    result = generate_recommendation(**arguments)
    return _jsonrpc_response(req_id, {
        "content": [
            {"type": "text", "text": json.dumps(result)},
        ],
    })


def _headers():
    return {"Content-Type": "application/json"}


def _jsonrpc_response(req_id, result):
    """Build a JSON-RPC 2.0 success response wrapped in Function URL format."""
    body = {"jsonrpc": "2.0", "id": req_id, "result": result}
    return {
        "statusCode": 200,
        "headers": _headers(),
        "body": json.dumps(body),
    }


def _jsonrpc_error(req_id, code, message):
    """Build a JSON-RPC 2.0 error response."""
    body = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }
    return {
        "statusCode": 200,  # JSON-RPC errors use 200 status with error in body
        "headers": _headers(),
        "body": json.dumps(body),
    }
