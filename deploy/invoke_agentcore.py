# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Invoke the Campaign Optimization Agent on AgentCore Runtime.

Usage:
    uv run python deploy/invoke_agentcore.py "Show me metrics for campaign 4782"
    uv run python deploy/invoke_agentcore.py "Diagnose campaign 4782 and recommend a fix"
"""

import json
import sys
import uuid
import os

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
AGENT_NAME = "campaign-optimization-agent"


def get_agent_arn() -> str:
    """Look up the agent runtime ARN by name."""
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    runtimes = client.list_agent_runtimes()
    for rt in runtimes.get("agentRuntimeSummaries", []):
        if rt["agentRuntimeName"] == AGENT_NAME:
            return rt["agentRuntimeArn"]
    raise RuntimeError(f"No runtime found with name '{AGENT_NAME}'. Deploy first.")


def invoke(prompt: str) -> str:
    """Invoke the deployed agent and return the response."""
    agent_arn = get_agent_arn()
    client = boto3.client("bedrock-agentcore", region_name=REGION)

    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=payload,
        qualifier="DEFAULT",
    )

    content = []
    for chunk in response.get("response", []):
        content.append(chunk.decode("utf-8"))

    result = json.loads("".join(content))
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python deploy/invoke_agentcore.py \"<prompt>\"")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    print(f"Prompt: {prompt}\n")

    result = invoke(prompt)

    # Extract text from the agent response
    message = result.get("result", {})
    if isinstance(message, dict):
        for block in message.get("content", []):
            if "text" in block:
                print(block["text"])
    else:
        print(result)


if __name__ == "__main__":
    main()
