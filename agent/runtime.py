# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""AgentCore Runtime entrypoint for the Campaign Optimization Agent.

This module wraps the existing Strands agent with the BedrockAgentCoreApp
HTTP server, exposing it on 0.0.0.0:8080 as required by AgentCore Runtime.

When GATEWAY_MCP_URL is set, tools registered in AgentCore Gateway are
loaded via MCP and replace their local equivalents (diagnose_campaign_issue,
get_campaign_metrics, etc.). Other tools remain local.

Usage:
    Local dev:   agentcore dev
    Deploy:      agentcore launch
    Invoke:      agentcore invoke '{"prompt": "Show me metrics for campaign 4782"}'
"""

import json
import os
import sys

# Fix encoding on Windows dev machines
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from strands import Agent
from strands.models.bedrock import BedrockModel

from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS
from agent.data_loader import load_trader_profiles
from agent.gateway_tools import load_gateway_tools, GATEWAY_TOOL_NAMES

from bedrock_agentcore.runtime import BedrockAgentCoreApp


def _build_session_context(trader_id: str = "trader_alpha") -> str:
    """Build a session context block from trader profile data."""
    profiles = load_trader_profiles()
    trader = next((t for t in profiles if t["trader_id"] == trader_id), None)
    if not trader:
        return ""

    detail_pref = trader.get("recommendation_preferences", {}).get("detail_level", "moderate")
    detail_map = {"detailed": "high", "brief": "low", "moderate": "high"}

    return json.dumps({
        "trader_id": trader["trader_id"],
        "trader_name": trader["name"],
        "detail_preference": detail_map.get(detail_pref, "high"),
    })


def _resolve_tools():
    """Resolve tool list: Gateway MCP tools (if configured) + remaining local tools."""
    mcp_client, gateway_tools = load_gateway_tools()

    if gateway_tools:
        # Strip the target prefix to get bare tool names for comparison
        gw_names = set()
        for t in gateway_tools:
            name = t.tool_name
            if "___" in name:
                name = name.split("___", 1)[1]
            gw_names.add(name)

        # Keep local tools that are NOT replaced by Gateway
        local_tools = [
            t for t in ALL_TOOLS
            if getattr(t, "__name__", getattr(t, "name", "")) not in gw_names
        ]
        tools = list(gateway_tools) + local_tools
        print(f"[runtime] Using {len(gateway_tools)} Gateway tools + "
              f"{len(local_tools)} local tools")
    else:
        mcp_client = None
        tools = ALL_TOOLS
        print(f"[runtime] Using {len(tools)} local tools (no Gateway configured)")

    return mcp_client, tools


def _create_agent(trader_id: str = "trader_alpha") -> tuple:
    """Create a configured Campaign Optimization Agent.

    Returns (agent, mcp_client) — caller should close mcp_client on shutdown.
    """
    model = BedrockModel(
        model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )

    session_ctx = _build_session_context(trader_id)
    full_prompt = SYSTEM_PROMPT
    if session_ctx:
        full_prompt += f"\n\n## Current Session Context\n\n```json\n{session_ctx}\n```"

    mcp_client, tools = _resolve_tools()

    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=full_prompt,
    )
    return agent, mcp_client


# Create the agent once at module load (reused across invocations)
agent, _mcp_client = _create_agent()

# --- AgentCore Runtime app ---
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context):
    """Handler for AgentCore Runtime /invocations endpoint.

    Expected payload: {"prompt": "...", "trader_id": "..." (optional)}
    """
    prompt = payload.get(
        "prompt",
        "No prompt found in input. Please send a JSON payload with a 'prompt' key.",
    )

    result = agent(prompt)

    # Return structured response
    return {
        "result": result.message,
    }


if __name__ == "__main__":
    app.run()
