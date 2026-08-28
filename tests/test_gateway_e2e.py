# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
End-to-end test: Agent -> AgentCore Gateway (MCP) -> Lambda -> ML diagnosis -> Agent

Tests at 4 layers:
  1. Local handler:   gateway_handler functions directly
  2. Lambda invoke:   AWS Lambda via boto3 (no Gateway)
  3. Gateway MCP:     list/call tools through the MCP endpoint
  4. Full agent E2E:  Strands agent with Gateway tools answers a diagnosis prompt

Usage:
    # Run all layers (requires deployed Gateway — see deploy/deploy_gateway.py)
    uv run python tests/test_gateway_e2e.py

    # Run only local tests (no AWS needed)
    uv run python tests/test_gateway_e2e.py --local-only

    # Run specific layer
    uv run python tests/test_gateway_e2e.py --layer 3
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "lambda"))

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
GATEWAY_LAMBDA_NAME = "campaign-opt-gateway-tools"
CONFIG_FILE = REPO_ROOT / "gateway_config.json"

LABEL_PASS = "[PASS]"  # nosec B105 - test status indicator, not a credential
LABEL_FAIL = "[FAIL]"
LABEL_SKIP = "[SKIP]"
results = []


def report(layer, test_name, passed, detail=""):
    status = LABEL_PASS if passed else LABEL_FAIL
    results.append((layer, test_name, passed))
    print(f"  {status} {test_name}")
    if detail:
        print(f"         {detail}")


# ── Layer 1: Local handler ───────────────────────────────────────────────────
def test_layer1_local():
    print("\n" + "=" * 60)
    print("Layer 1: Local Gateway Handler")
    print("=" * 60)

    from gateway_handler import DISPATCH

    # Test diagnose_campaign_issue
    result = DISPATCH["diagnose_campaign_issue"](campaign_id="4782")
    has_issues = result.get("has_issues")
    primary = result.get("primary_issue", {})
    report(1, "diagnose_campaign_issue returns result", result is not None)
    report(1, "has_issues is True", has_issues is True)
    report(1, "primary_issue has issue_type",
           "issue_type" in primary,
           f"issue_type={primary.get('issue_type')}")
    report(1, "confidence score present",
           "confidence" in primary,
           f"confidence={primary.get('confidence')}")

    # Test get_campaign_metrics
    metrics = DISPATCH["get_campaign_metrics"](campaign_id="4782")
    report(1, "get_campaign_metrics returns campaign_id",
           metrics.get("campaign_id") == "4782")

    # Test generate_recommendation
    rec = DISPATCH["generate_recommendation"](campaign_id="4782")
    report(1, "generate_recommendation returns result",
           rec.get("campaign_id") == "4782")

    # Test get_market_intelligence
    market = DISPATCH["get_market_intelligence"](campaign_id="4782")
    report(1, "get_market_intelligence returns result",
           "error" not in market or "market_segment" in market)


# ── Layer 2: Lambda invoke ───────────────────────────────────────────────────
def test_layer2_lambda():
    print("\n" + "=" * 60)
    print("Layer 2: AWS Lambda Direct Invoke")
    print("=" * 60)

    import boto3
    lam = boto3.client("lambda", region_name=REGION)

    # Check if Lambda exists
    try:
        lam.get_function(FunctionName=GATEWAY_LAMBDA_NAME)
    except lam.exceptions.ResourceNotFoundException:
        print(f"  {LABEL_SKIP} Lambda {GATEWAY_LAMBDA_NAME} not deployed. Run deploy/deploy_gateway.py first.")
        return

    # Invoke with diagnose payload
    # Note: without Gateway context, the handler can't resolve tool name from context.
    # But the event still gets passed. We test that Lambda runs without error.
    resp = lam.invoke(
        FunctionName=GATEWAY_LAMBDA_NAME,
        Payload=json.dumps({"campaign_id": "4782"}).encode(),
    )
    status_code = resp["StatusCode"]
    payload = json.loads(resp["Payload"].read())
    report(2, "Lambda invokes successfully", status_code == 200,
           f"StatusCode={status_code}")
    report(2, "Lambda returns JSON response", isinstance(payload, dict),
           f"keys={list(payload.keys())[:5]}")

    # The handler won't know which tool to call without context,
    # so it may return an error about unknown tool — that's expected.
    # What matters is the Lambda itself runs.
    print(f"         Response: {json.dumps(payload)[:200]}")


# ── Layer 3: Gateway MCP ─────────────────────────────────────────────────────
def test_layer3_gateway_mcp():
    print("\n" + "=" * 60)
    print("Layer 3: AgentCore Gateway MCP Protocol")
    print("=" * 60)

    if not CONFIG_FILE.exists():
        print(f"  {LABEL_SKIP} No gateway_config.json. Run deploy/deploy_gateway.py first.")
        return

    config = json.loads(CONFIG_FILE.read_text())
    gateway_url = config.get("gateway_url")
    if not gateway_url:
        print(f"  {LABEL_SKIP} No gateway_url in config.")
        return

    print(f"  Gateway URL: {gateway_url}")

    try:
        from strands.tools.mcp.mcp_client import MCPClient
        from mcp.client.streamable_http import streamablehttp_client
        from agent.gateway_tools import SigV4Auth
    except ImportError:
        print(f"  {LABEL_SKIP} strands-agents or mcp not installed.")
        return

    def _create_transport():
        token = os.environ.get("GATEWAY_ACCESS_TOKEN")
        if token:
            return streamablehttp_client(
                gateway_url,
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            # IAM auth — sign with SigV4
            auth = SigV4Auth(region=REGION)
            return streamablehttp_client(gateway_url, auth=auth)

    mcp_client = MCPClient(_create_transport)

    try:
        with mcp_client:
            # List tools
            tools = mcp_client.list_tools_sync()
            tool_names = [t.tool_name for t in tools]
            report(3, "Gateway returns tools", len(tools) > 0,
                   f"tools={tool_names}")

            # Check expected tools are present (with or without prefix)
            expected = {"diagnose_campaign_issue", "get_campaign_metrics",
                        "generate_recommendation", "get_market_intelligence"}
            found = set()
            for name in tool_names:
                bare = name.split("___")[-1] if "___" in name else name
                if bare in expected:
                    found.add(bare)
            report(3, "All 4 expected tools registered",
                   found == expected,
                   f"found={found}, missing={expected - found}")

            # Call diagnose_campaign_issue through MCP
            diag_tool_name = next(
                (n for n in tool_names if "diagnose_campaign_issue" in n), None
            )
            if diag_tool_name:
                print(f"\n  Calling tool: {diag_tool_name}")
                call_result = mcp_client.call_tool_sync(
                    tool_use_id="test-001",
                    name=diag_tool_name,
                    arguments={"campaign_id": "4782"},
                )
                # Parse the result (may be dict or object depending on SDK version)
                result_text = ""
                content = (
                    call_result.get("content", [])
                    if isinstance(call_result, dict)
                    else getattr(call_result, "content", [])
                )
                for block in content:
                    text = (
                        block.get("text", "")
                        if isinstance(block, dict)
                        else getattr(block, "text", "")
                    )
                    if text:
                        result_text = text
                        break

                result_data = json.loads(result_text) if result_text else {}

                report(3, "diagnose_campaign_issue via MCP returns data",
                       bool(result_data),
                       f"has_issues={result_data.get('has_issues')}")
                report(3, "ML confidence present in MCP result",
                       "confidence" in result_data.get("primary_issue", {}),
                       f"confidence={result_data.get('primary_issue', {}).get('confidence')}")
            else:
                report(3, "diagnose_campaign_issue tool found", False,
                       "Tool not in gateway")

    except Exception as e:
        report(3, "Gateway MCP connection", False, str(e))


# ── Layer 4: Full Agent E2E ──────────────────────────────────────────────────
def test_layer4_agent_e2e():
    print("\n" + "=" * 60)
    print("Layer 4: Full Agent E2E (Agent -> Gateway -> Lambda -> Response)")
    print("=" * 60)

    if not CONFIG_FILE.exists():
        print(f"  {LABEL_SKIP} No gateway_config.json. Run deploy/deploy_gateway.py first.")
        return

    config = json.loads(CONFIG_FILE.read_text())
    gateway_url = config.get("gateway_url")
    if not gateway_url:
        print(f"  {LABEL_SKIP} No gateway_url in config.")
        return

    # Set env var so the agent uses Gateway tools
    os.environ["GATEWAY_MCP_URL"] = gateway_url
    print(f"  GATEWAY_MCP_URL={gateway_url}")

    try:
        from strands import Agent
        from strands.models.bedrock import BedrockModel
        from agent.gateway_tools import load_gateway_tools, GATEWAY_TOOL_NAMES
        from agent.tools import ALL_TOOLS

        # Load Gateway tools
        mcp_client, gateway_tools = load_gateway_tools(gateway_url)
        report(4, "Gateway tools loaded via MCPClient",
               len(gateway_tools) > 0,
               f"count={len(gateway_tools)}")

        if not gateway_tools:
            return

        # Build merged tool list (same logic as runtime.py)
        gw_names = set()
        for t in gateway_tools:
            name = t.tool_name
            if "___" in name:
                name = name.split("___", 1)[1]
            gw_names.add(name)

        local_tools = [
            t for t in ALL_TOOLS
            if getattr(t, "__name__", getattr(t, "name", "")) not in gw_names
        ]
        all_tools = list(gateway_tools) + local_tools
        report(4, "Tool merge: Gateway + local",
               len(all_tools) > len(gateway_tools),
               f"gateway={len(gateway_tools)}, local={len(local_tools)}, total={len(all_tools)}")

        # Create agent
        model = BedrockModel(
            model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
            region_name=REGION,
        )
        agent = Agent(
            model=model,
            tools=all_tools,
            system_prompt="You are a campaign optimization assistant. Be concise.",
        )
        # Suppress live streaming to avoid duplicate output (stream + our print)
        agent.callback_handler = lambda **_: None

        # Send diagnosis prompt
        prompt = "Diagnose campaign 4782 and tell me what's wrong."
        print(f"\n  Prompt: {prompt}")
        print("  Waiting for agent response...\n")

        start = time.time()
        result = agent(prompt)
        elapsed = time.time() - start

        response_text = ""
        if hasattr(result, "message"):
            msg = result.message
            if isinstance(msg, dict) and "content" in msg:
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        response_text += block["text"]
            elif isinstance(msg, str):
                response_text = msg
        # Fallback: try str(result) if message parsing yielded nothing
        if not response_text:
            response_text = str(result)
        # Also try result.text or result.response
        if not response_text or len(response_text) < 10:
            for attr in ("text", "response", "output"):
                val = getattr(result, attr, None)
                if val and isinstance(val, str) and len(val) > len(response_text):
                    response_text = val

        report(4, "Agent produced a response",
               len(response_text) > 50,
               f"length={len(response_text)} chars, time={elapsed:.1f}s")

        # Check response mentions key diagnosis terms
        response_lower = response_text.lower()
        mentions_bid = "bid" in response_lower
        mentions_delivery = "delivery" in response_lower or "under" in response_lower
        report(4, "Response mentions bid issue",
               mentions_bid,
               f"contains 'bid': {mentions_bid}")
        report(4, "Response mentions delivery problem",
               mentions_delivery,
               f"contains 'delivery': {mentions_delivery}")

        # Print truncated response
        print(f"\n  --- Agent Response (first 500 chars) ---")
        print(f"  {response_text[:500]}")
        print(f"  --- End ---")

        # Cleanup
        if mcp_client:
            mcp_client.__exit__(None, None, None)

    except Exception as e:
        import traceback
        traceback.print_exc()
        report(4, "Agent E2E execution", False, str(e))
    finally:
        os.environ.pop("GATEWAY_MCP_URL", None)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="E2E Gateway test suite")
    parser.add_argument("--local-only", action="store_true",
                        help="Run only Layer 1 (no AWS needed)")
    parser.add_argument("--layer", type=int, choices=[1, 2, 3, 4],
                        help="Run only a specific layer")
    args = parser.parse_args()

    print("=" * 60)
    print("AgentCore Gateway E2E Test Suite")
    print("=" * 60)

    if args.local_only:
        test_layer1_local()
    elif args.layer:
        {1: test_layer1_local,
         2: test_layer2_lambda,
         3: test_layer3_gateway_mcp,
         4: test_layer4_agent_e2e}[args.layer]()
    else:
        test_layer1_local()
        test_layer2_lambda()
        test_layer3_gateway_mcp()
        test_layer4_agent_e2e()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, _, p in results if p)
    failed = sum(1 for _, _, p in results if not p)
    total = len(results)
    for layer, name, p in results:
        print(f"  L{layer} {LABEL_PASS if p else LABEL_FAIL} {name}")
    print(f"\n  {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
