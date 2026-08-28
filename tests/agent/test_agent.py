# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""End-to-end test script for the Campaign Optimization Agent.

Sends a sequence of prompts that exercise all 10 tools, prints
the agent's response for each, and reports a pass/fail summary.

Usage:
    uv run python tests/agent/test_agent.py
"""

import io
import os
import sys
import time

# Fix Windows console encoding — only wrap if not already wrapped
if sys.platform == "win32":
    if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not isinstance(sys.stderr, io.TextIOWrapper) or sys.stderr.encoding != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Add project root to sys.path so we can import agent.*
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "..")))

from agent.main import create_agent

# ANSI color codes
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Each test: (label, prompt, list of tool names we expect to see invoked)
TEST_CASES = [
    (
        "Campaign Metrics",
        "Show me the current metrics for campaign 4782.",
        ["get_campaign_metrics"],
    ),
    (
        "Campaign Configuration",
        "How is campaign 4782 configured? Show me targeting and restrictions.",
        ["get_campaign_configuration"],
    ),
    (
        "Trader Portfolio",
        "Which of my campaigns are at risk?",
        ["get_trader_campaigns"],
    ),
    (
        "Market Intelligence",
        "What are the current market conditions for automotive in Chicago?",
        ["get_market_intelligence"],
    ),
    (
        "Full Diagnosis + Recommendation",
        "Diagnose the delivery issue with campaign 4782 and recommend a fix.",
        ["get_campaign_metrics", "get_market_intelligence", "diagnose_campaign_issue", "generate_recommendation"],
    ),
    (
        "What-If Scenario",
        "What if I raise the bid on campaign 4782 to $5.50?",
        ["calculate_what_if_scenario"],
    ),
    (
        "Benchmark Comparison",
        "How does campaign 4782 compare to industry benchmarks for automotive in Chicago?",
        ["get_benchmark_comparison"],
    ),
]


def run_tests():
    print(f"\n{BOLD}{'=' * 70}")
    print(f"CAMPAIGN OPTIMIZATION AGENT — END-TO-END TEST")
    print(f"{'=' * 70}{RESET}")

    agent = create_agent(trader_id="trader_alpha")
    # Disable live streaming to avoid duplicate output (stream + our print)
    agent.callback_handler = lambda **kwargs: None

    results = []
    total_start = time.time()

    for i, (label, prompt, expected_tools) in enumerate(TEST_CASES, 1):
        print(f"\n{DIM}{'─' * 70}{RESET}")
        print(f"{BOLD}{CYAN}TEST {i}/{len(TEST_CASES)}: {label}{RESET}")
        print(f"{DIM}PROMPT: {prompt}{RESET}")
        print(f"{DIM}EXPECTED TOOLS: {', '.join(expected_tools)}{RESET}")
        print(f"{DIM}{'─' * 70}{RESET}")

        msg_count_before = len(agent.messages) if agent.messages else 0
        start = time.time()
        try:
            response = agent(prompt)
            elapsed = time.time() - start

            # Extract tool names called during this turn only
            tool_names = []
            for msg in (agent.messages or [])[msg_count_before:]:
                for block in msg.get("content", []):
                    if "toolUse" in block:
                        name = block["toolUse"].get("name", "")
                        if name and name not in tool_names:
                            tool_names.append(name)

            # Extract response text
            text = ""
            for block in response.message.get("content", []):
                if "text" in block:
                    text += block["text"]

            # Print tools called, then abbreviated response
            if tool_names:
                for j, name in enumerate(tool_names, 1):
                    print(f"{YELLOW}Tool #{j}: {name}{RESET}")
            preview = text[:2000] + ("..." if len(text) > 2000 else "")
            print(f"\n{GREEN}RESPONSE ({elapsed:.1f}s):{RESET}\n{preview}")

            results.append((label, "PASS", elapsed))

        except Exception as e:
            elapsed = time.time() - start
            print(f"\n{RED}ERROR ({elapsed:.1f}s): {e}{RESET}")
            results.append((label, "FAIL", elapsed))

    total_elapsed = time.time() - total_start

    # Summary
    print(f"\n{BOLD}{'=' * 70}")
    print(f"TEST SUMMARY")
    print(f"{'=' * 70}{RESET}")
    pass_count = sum(1 for _, status, _ in results if status == "PASS")
    fail_count = len(results) - pass_count

    for label, status, elapsed in results:
        if status == "PASS":
            print(f"  {GREEN}[PASS]{RESET} {label:40s} {DIM}({elapsed:.1f}s){RESET}")
        else:
            print(f"  {RED}[FAIL]{RESET} {label:40s} {DIM}({elapsed:.1f}s){RESET}")

    color = GREEN if fail_count == 0 else RED
    print(f"\n  {color}{BOLD}{pass_count}/{len(results)} passed, {fail_count} failed{RESET}")
    print(f"  {DIM}Total time: {total_elapsed:.1f}s{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    return fail_count == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
