# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Campaign Optimization Agent — Strands SDK entry point.

Usage:
    uv run python -m agent.main                         # interactive CLI
    uv run python -m agent.main --query "show metrics for campaign 4782"  # single query
"""

import argparse
import io
import json
import os
import sys

# Fix Windows console encoding for emoji output from LLM
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from strands import Agent
from strands.models.bedrock import BedrockModel

from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS


def build_session_context(trader_id: str = "trader_alpha") -> str:
    """Build a session context block from trader profile data."""
    from agent.data_loader import load_trader_profiles

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


def create_agent(trader_id: str = "trader_alpha") -> Agent:
    """Create and return a configured Campaign Optimization Agent."""
    model = BedrockModel(
        model_id="global.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="us-west-2",
    )

    session_ctx = build_session_context(trader_id)
    full_prompt = SYSTEM_PROMPT
    if session_ctx:
        full_prompt += f"\n\n## Current Session Context\n\n```json\n{session_ctx}\n```"

    agent = Agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=full_prompt,
    )
    return agent


def run_interactive(agent: Agent) -> None:
    """Run the agent in an interactive CLI loop."""
    print("\n=== Campaign Optimization Agent (Strands SDK) ===")
    print("Type your question, or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("Trader> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        response = agent(user_input)
        print(f"\nAgent> {response.message['content'][0]['text']}\n")


def run_single(agent: Agent, query: str) -> None:
    """Run a single query and print the result."""
    response = agent(query)
    print(response.message["content"][0]["text"])


def main():
    parser = argparse.ArgumentParser(description="Campaign Optimization Agent")
    parser.add_argument("--query", "-q", type=str, help="Single query (non-interactive)")
    parser.add_argument("--trader", "-t", type=str, default="trader_alpha", help="Trader ID for session context")
    args = parser.parse_args()

    agent = create_agent(trader_id=args.trader)

    if args.query:
        run_single(agent, args.query)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
