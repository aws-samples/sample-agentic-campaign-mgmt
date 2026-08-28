# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler for Bedrock AgentCore action group — Campaign Optimization.

Differences from examples/sample_lambda_function.py:
  - diagnose_campaign_issue() is backed by the XGBoost ML model
    (ml/diagnose_campaign_ml.py) deployed on SageMaker.
  - generate_recommendation() is backed by the Random Forest ML model
    (ml/recommendation_ml.py) deployed on SageMaker.
  - Both tools follow the same pattern: Lambda -> SageMaker Endpoint.

Container directory layout (see Dockerfile):
    /var/task/
        handler.py                  <- this file
        ml/
            diagnose_campaign_ml.py
            recommendation_ml.py
            model/                  <- .pkl files + feature_names.json
        data/                       <- JSON files (stand-in for DynamoDB in PoC)
"""
import json
import os
from typing import Any, Dict

from ml.diagnose_campaign_ml import diagnose_campaign_issue_ml
from ml.recommendation_ml import generate_recommendation_ml

DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "prototype-v1", "data"),
)


# ============================================================================
# Data loaders (simulate DynamoDB / Redis reads in PoC)
# ============================================================================

def load_campaigns():
    """Load campaigns data (simulates DynamoDB read)."""
    with open(os.path.join(DATA_DIR, "campaigns.json"), encoding="utf-8") as f:
        return json.load(f)


def load_campaign_configs():
    """Load campaign configurations (simulates DynamoDB read)."""
    with open(os.path.join(DATA_DIR, "campaign_configs.json"), encoding="utf-8") as f:
        return json.load(f)


def load_market_intelligence():
    """Load market intelligence data (simulates Redis / DynamoDB read)."""
    with open(os.path.join(DATA_DIR, "market_intelligence.json"), encoding="utf-8") as f:
        return json.load(f)


def load_historical_outcomes():
    """Load historical outcomes (simulates Athena query)."""
    with open(os.path.join(DATA_DIR, "historical_outcomes.json"), encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Action handlers
# ============================================================================

def get_campaign_metrics(campaign_id: str, time_range: str = "current") -> Dict:
    """
    Action: get_campaign_metrics

    Retrieve current performance metrics for a specific campaign.
    """
    campaigns = load_campaigns()
    campaign = next((c for c in campaigns if c["campaign_id"] == campaign_id), None)

    if not campaign:
        return {"error": "Campaign not found", "campaign_id": campaign_id}

    impressions_delivered = int(campaign["impressions_goal"] * campaign["delivery_pct"])
    clicks = int(impressions_delivered * campaign["ctr"])
    spend = campaign["budget_total"] * campaign["delivery_pct"]

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign["campaign_name"],
        "status": campaign["status"],
        "delivery_metrics": {
            "impressions_delivered": impressions_delivered,
            "impressions_goal": campaign["impressions_goal"],
            "delivery_pct": campaign["delivery_pct"],
            "expected_delivery_pct": campaign["expected_pct"],
            "delivery_variance": campaign["delivery_pct"] - campaign["expected_pct"],
            "on_track": 0.90 <= campaign["delivery_pct"] / campaign["expected_pct"] <= 1.10,
        },
        "engagement_metrics": {
            "clicks": clicks,
            "conversions": (
                int(clicks * campaign["conversion_rate"])
                if campaign["conversion_rate"] > 0 else 0
            ),
            "ctr": campaign["ctr"],
            "conversion_rate": campaign["conversion_rate"],
        },
        "financial_metrics": {
            "spend": round(spend, 2),
            "budget_total": campaign["budget_total"],
            "budget_daily": campaign["budget_daily"],
            "avg_cpm": (
                round(spend / (impressions_delivered / 1000), 2)
                if impressions_delivered > 0 else 0
            ),
            "avg_cpc": round(spend / clicks, 2) if clicks > 0 else 0,
        },
        "auction_metrics": {
            "win_rate": campaign["win_rate"],
            "avg_bid": campaign["current_bid"],
        },
        "time_context": {
            "flight_start": campaign["flight_start"],
            "flight_end": campaign["flight_end"],
            "days_elapsed": campaign["days_elapsed"],
            "days_remaining": campaign["days_remaining"],
            "hours_remaining": campaign["days_remaining"] * 24,
        },
        "data_freshness": "2026-02-17T09:00:00Z",
    }


def diagnose_campaign_issue(campaign_id: str) -> Dict:
    """
    Action: diagnose_campaign_issue

    Delegates to the XGBoost ML model. Returns the same response schema as the
    original rule-based implementation so the Bedrock agent needs no changes.
    """
    return diagnose_campaign_issue_ml(campaign_id)


def generate_recommendation(campaign_id: str, issue_type: str = None) -> Dict:
    """
    Action: generate_recommendation

    Delegates to the Random Forest ML model. Returns actionable recommendations
    based on ML diagnosis + market intelligence + historical outcomes.
    """
    return generate_recommendation_ml(campaign_id, issue_type)


def get_market_intelligence(
    geo: str = None,
    industry: str = None,
    campaign_id: str = None,
) -> Dict:
    """
    Action: get_market_intelligence

    Get current market conditions for a specific geo/industry combination.
    """
    markets = load_market_intelligence()

    if campaign_id and not (geo and industry):
        campaigns = load_campaigns()
        campaign = next((c for c in campaigns if c["campaign_id"] == campaign_id), None)
        if campaign:
            geo = campaign["geo"]
            industry = campaign["industry"]

    if not geo or not industry:
        return {"error": "Must provide geo and industry, or campaign_id"}

    market_key = f"{industry}_{geo.lower().replace(' ', '_')}_dma"
    market = next((m for m in markets if m["market_segment"] == market_key), None)

    if not market:
        return {"error": f"Market data not found for {geo} + {industry}"}

    return market


# ============================================================================
# Lambda entry point
# ============================================================================

def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    Main Lambda handler for Bedrock AgentCore action group.

    Expected event structure (Bedrock AgentCore function-calling format):
        {
            "messageVersion": "1.0",
            "actionGroup": "campaign_data",
            "function": "diagnose_campaign_issue",
            "parameters": [
                {"name": "campaign_id", "type": "string", "value": "4782"}
            ]
        }
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        function_name = event.get("function")
        parameters = {
            param["name"]: param["value"]
            for param in event.get("parameters", [])
        }

        print(f"Function: {function_name}, Parameters: {parameters}")

        dispatch = {
            "get_campaign_metrics":    get_campaign_metrics,
            "diagnose_campaign_issue": diagnose_campaign_issue,
            "generate_recommendation": generate_recommendation,
            "get_market_intelligence": get_market_intelligence,
        }

        handler_fn = dispatch.get(function_name)
        if not handler_fn:
            return _error_response(f"Unknown function: {function_name}", event)

        result = handler_fn(**parameters)
        return _success_response(result, event)

    except Exception as exc:  # pylint: disable=broad-except
        import traceback
        traceback.print_exc()
        return _error_response(str(exc), event)


# ============================================================================
# Bedrock response helpers
# ============================================================================

def _success_response(data: Dict, event: Dict) -> Dict:
    """Wrap a result dict in the Bedrock AgentCore SUCCESS response envelope."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "campaign_data"),
            "function": event.get("function", "unknown"),
            "functionResponse": {
                "responseState": "SUCCESS",
                "responseBody": {"TEXT": {"body": json.dumps(data)}},
            },
        },
    }


def _error_response(error_message: str, event: Dict) -> Dict:
    """Wrap an error message in the Bedrock AgentCore FAILURE response envelope."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "unknown"),
            "function": event.get("function", "unknown"),
            "functionResponse": {
                "responseState": "FAILURE",
                "responseBody": {"TEXT": {"body": json.dumps({"error": error_message})}},
            },
        },
    }


# ============================================================================
# Local smoke test
# ============================================================================

if __name__ == "__main__":
    """Quick local test — runs all 4 actions against campaign #4782."""

    print("=" * 70)
    print("LOCAL SMOKE TEST — ML Lambda Handler")
    print("=" * 70)

    for fn, params in [
        ("get_campaign_metrics",    [{"name": "campaign_id", "value": "4782"}]),
        ("diagnose_campaign_issue", [{"name": "campaign_id", "value": "4782"}]),
        ("generate_recommendation", [{"name": "campaign_id", "value": "4782"}]),
        ("get_market_intelligence", [{"name": "campaign_id", "value": "4782"}]),
    ]:
        print(f"\n--- {fn} ---")
        evt = {"function": fn, "actionGroup": "campaign_data", "parameters": params}
        resp = lambda_handler(evt, None)
        body = json.loads(resp["response"]["functionResponse"]["responseBody"]["TEXT"]["body"])
        print(json.dumps(body, indent=2))

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
