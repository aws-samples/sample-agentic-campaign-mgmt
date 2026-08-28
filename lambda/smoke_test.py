# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
smoke_test.py - Invoke the deployed Lambda and print the diagnosis result.

Works on Windows and Mac. No shell, no AWS CLI required.

Usage:
    uv run python lambda/smoke_test.py
    uv run python lambda/smoke_test.py --campaign-id 1234

Override defaults via environment variables:
    REGION=us-west-2 FUNCTION_NAME=my-fn uv run python lambda/smoke_test.py
"""
import argparse
import json
import os

import boto3

REGION        = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
FUNCTION_NAME = os.environ.get("FUNCTION_NAME", "campaign-opt-diagnose-ml")


def invoke(function_name: str, campaign_id: str) -> dict:
    """Invoke the Lambda with the given tool function and return the parsed body."""
    client = boto3.client("lambda", region_name=REGION)

    payload = json.dumps({
        "function": function_name,
        "actionGroup": "campaign_analysis",
        "parameters": [{"name": "campaign_id", "type": "string", "value": campaign_id}],
    })

    response = client.invoke(
        FunctionName=FUNCTION_NAME,
        Payload=payload.encode(),
    )

    raw = json.loads(response["Payload"].read())

    # Check for Lambda-level errors (e.g. unhandled exception)
    if "FunctionError" in response:
        print("Lambda returned a function error:")
        print(json.dumps(raw, indent=2))
        raise RuntimeError(raw.get("errorMessage", "Unknown Lambda error"))

    body = raw["response"]["functionResponse"]["responseBody"]["TEXT"]["body"]
    return json.loads(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the campaign optimization Lambda endpoint.")
    parser.add_argument("--campaign-id", default="4782", help="Campaign ID to diagnose (default: 4782)")
    parser.add_argument("--recommend", action="store_true", help="Also test generate_recommendation")
    args = parser.parse_args()

    print(f"Function: {FUNCTION_NAME}  |  Region: {REGION}")
    print(f"Campaign: {args.campaign_id}")

    # --- Diagnosis ---
    print(f"\n{'='*60}")
    print("TEST 1: diagnose_campaign_issue")
    print(f"{'='*60}\n")
    diag = invoke("diagnose_campaign_issue", args.campaign_id)
    print(json.dumps(diag, indent=2))

    # --- Recommendation (optional) ---
    if args.recommend:
        print(f"\n{'='*60}")
        print("TEST 2: generate_recommendation")
        print(f"{'='*60}\n")
        rec = invoke("generate_recommendation", args.campaign_id)
        print(json.dumps(rec, indent=2))

        # Surface value source clearly
        pred_val = rec.get("rationale", {}).get("ml_value_prediction", {}).get("predicted_value")
        action = rec.get("recommendation", {}).get("type", "?")
        if pred_val is not None:
            print(f"\n  ✓ Regression VALUE SOURCE: ML-predicted ({action} = {pred_val})")
        else:
            print(f"\n  ⚠ Regression VALUE SOURCE: heuristic fallback ({action} — v2 container, regression not supported)")


if __name__ == "__main__":
    main()
