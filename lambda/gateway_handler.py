# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler for AgentCore Gateway — Campaign Optimization tools.

Unlike handler.py (which uses the Bedrock Agents Action Group event format),
this handler uses the AgentCore Gateway Lambda target format:

  Event:   flat dict of input properties  (e.g. {"campaign_id": "4782"})
  Context: tool name in context.client_context.custom['bedrockAgentCoreToolName']
           formatted as  ${target_name}___${tool_name}
  Return:  plain JSON dict (no Bedrock Agents response envelope)

Deploy as a SEPARATE Lambda function alongside the existing one, or point
the Gateway target at the same function with this handler path:
  lambda/gateway_handler.lambda_handler
"""
import json
import traceback

from handler import (
    get_campaign_metrics,
    diagnose_campaign_issue,
    generate_recommendation,
    get_market_intelligence,
)

TOOL_DELIMITER = "___"

DISPATCH = {
    "get_campaign_metrics": get_campaign_metrics,
    "diagnose_campaign_issue": diagnose_campaign_issue,
    "generate_recommendation": generate_recommendation,
    "get_market_intelligence": get_market_intelligence,
}


def lambda_handler(event, context):
    """
    AgentCore Gateway Lambda target handler.

    Gateway sends:
      event  = {"campaign_id": "4782"}          (flat input properties)
      context.client_context.custom = {
          "bedrockAgentCoreToolName": "CampaignTools___get_campaign_metrics",
          "bedrockAgentCoreGatewayId": "...",
          ...
      }

    Returns: plain JSON dict
    """
    print(f"[gateway_handler] event: {json.dumps(event)}")

    try:
        # Extract tool name from context (strip target prefix)
        custom = getattr(context, "client_context", None)
        custom = getattr(custom, "custom", None) or {}
        original_tool_name = custom.get("bedrockAgentCoreToolName", "")

        if TOOL_DELIMITER in original_tool_name:
            tool_name = original_tool_name.split(TOOL_DELIMITER, 1)[1]
        else:
            tool_name = original_tool_name

        print(f"[gateway_handler] tool: {tool_name}, params: {event}")

        handler_fn = DISPATCH.get(tool_name)
        if not handler_fn:
            return {"error": f"Unknown tool: {tool_name}"}

        return handler_fn(**event)

    except Exception as exc:
        traceback.print_exc()
        return {"error": str(exc)}
