# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Load tools from AgentCore Gateway via MCP protocol.

When GATEWAY_MCP_URL is set, this module connects to the Gateway and
returns MCP-backed tool objects that can be passed to the Strands Agent.

The Gateway tools (get_campaign_metrics, diagnose_campaign_issue,
generate_recommendation, get_market_intelligence) replace their local
equivalents, while other tools remain local.

Usage in runtime.py:
    from agent.gateway_tools import load_gateway_tools
    gateway_tools = load_gateway_tools()  # returns [] if no URL configured
"""
import os
from typing import Optional
from urllib.parse import urlparse

# Gateway tools that replace local equivalents
GATEWAY_TOOL_NAMES = {
    "get_campaign_metrics",
    "diagnose_campaign_issue",
    "generate_recommendation",
    "get_market_intelligence",
}


import httpx


class SigV4Auth(httpx.Auth):
    """httpx.Auth subclass that signs requests with AWS SigV4 for IAM-authed Gateways."""

    def __init__(self, region: str = "us-west-2", service: str = "bedrock-agentcore"):
        import botocore.session
        self._session = botocore.session.get_session()
        self._credentials = self._session.get_credentials()
        self._region = region
        self._service = service

    def auth_flow(self, request: httpx.Request):
        """Sign each outgoing request with SigV4."""
        from botocore.auth import SigV4Auth as BotoSigV4Auth
        from botocore.awsrequest import AWSRequest

        # Build an AWSRequest from the httpx request
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content or b"",
            headers=dict(request.headers),
        )

        # Sign it
        credentials = self._credentials.get_frozen_credentials()
        signer = BotoSigV4Auth(credentials, self._service, self._region)
        signer.add_auth(aws_request)

        # Copy signed headers back to the httpx request
        for key, value in aws_request.headers.items():
            request.headers[key] = value

        yield request


def load_gateway_tools(gateway_url: Optional[str] = None) -> tuple:
    """
    Connect to AgentCore Gateway and return (mcp_client, tools).

    Returns (None, []) if no gateway URL is configured.
    The caller must keep the mcp_client alive (use as context manager).

    Auth modes:
      - GATEWAY_ACCESS_TOKEN set → Bearer token (JWT auth)
      - Otherwise → SigV4 signing (IAM auth)
    """
    url = gateway_url or os.environ.get("GATEWAY_MCP_URL")
    if not url:
        return None, []

    from strands.tools.mcp.mcp_client import MCPClient
    from mcp.client.streamable_http import streamablehttp_client

    region = os.environ.get("AWS_REGION", "us-west-2")

    def _create_transport():
        token = os.environ.get("GATEWAY_ACCESS_TOKEN")
        if token:
            # JWT auth mode
            return streamablehttp_client(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            # IAM auth mode — sign requests with SigV4
            import httpx
            auth = SigV4Auth(region=region)
            return streamablehttp_client(url, auth=auth)

    mcp_client = MCPClient(_create_transport)
    mcp_client.__enter__()

    tools = mcp_client.list_tools_sync()
    print(f"[gateway_tools] Loaded {len(tools)} tools from Gateway: "
          f"{[t.tool_name for t in tools]}")

    return mcp_client, tools
