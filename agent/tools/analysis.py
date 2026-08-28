# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tool Group 2: Analysis & Diagnosis (3 tools).

These tools perform root-cause analysis, generate recommendations,
and compute what-if projections for campaign changes.

Diagnosis delegates to the ML engine in ml/diagnose_campaign_ml.py
rather than duplicating rule-based heuristics.
"""

import json
from strands import tool

from agent.data_loader import (
    find_campaign,
    find_config,
    find_market,
    load_historical_outcomes,
)
from ml.diagnose_campaign_ml import build_features, predict


def _run_ml_diagnosis(campaign: dict, market: dict) -> dict:
    """Run the ML diagnosis model and return primary_issue + confidence + evidence."""
    features = build_features(campaign, market)
    result = predict(features)
    return {
        "primary_issue": result["primary_issue"],
        "confidence": result["confidence"],
        "evidence": result["features_used"],
        "class_probabilities": result.get("class_probabilities", {}),
    }


@tool
def diagnose_campaign_issue(campaign_id: str, metrics: str, market: str) -> str:
    """Analyzes a campaign's metrics against market conditions to identify the root cause
    of underdelivery. Returns: primary_issue (bid_too_low | competitive_pressure |
    inventory_shortage | creative_fatigue | targeting_too_narrow | pacing_issue |
    budget_exhausted_early | frequency_cap_blocking | daypart_restriction |
    publisher_exclusion | geo_over_served | device_mismatch | no_bid_response),
    confidence (0-1), and supporting evidence.
    **Always call get_campaign_metrics and get_market_intelligence before this tool**
    — their outputs are required inputs.
    Required: campaign_id, metrics, market."""
    campaign = find_campaign(campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found", "campaign_id": campaign_id})

    market_data = find_market(campaign["industry"], campaign["geo"])
    if not market_data:
        return json.dumps({"error": "Market data not found for campaign segment"})

    diagnosis = _run_ml_diagnosis(campaign, market_data)

    return json.dumps({
        "campaign_id": campaign_id,
        "campaign_name": campaign["campaign_name"],
        "model": "xgboost_v1",
        **diagnosis,
    })


@tool
def generate_recommendation(campaign_id: str, diagnosis: str, metrics: str, market: str) -> str:
    """Generates a specific, data-backed action to resolve a diagnosed campaign issue.
    Returns: recommended action (bid value, publisher list, or geo expansion),
    expected_outcomes (win rate, final delivery %, recovery time, budget impact),
    confidence score, and rationale including similar campaign count.
    **Requires diagnosis output from diagnose_campaign_issue.**
    Required: campaign_id, diagnosis, metrics, market."""
    campaign = find_campaign(campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found", "campaign_id": campaign_id})

    config = find_config(campaign_id)
    market_data = find_market(campaign["industry"], campaign["geo"])
    if not market_data:
        return json.dumps({"error": "Market data not found for campaign segment"})

    diag = _run_ml_diagnosis(campaign, market_data)
    issue = diag["primary_issue"]

    if issue in ("no_issue_detected",):
        return json.dumps({
            "campaign_id": campaign_id,
            "recommendation": None,
            "message": "Campaign is performing well — no recommendation needed.",
        })

    # Find similar historical campaigns
    historical = load_historical_outcomes()
    similar = [
        h for h in historical
        if h["industry"] == campaign["industry"]
        and h["geo"] == campaign["geo"]
        and h["outcome"]["outcome_status"] == "success"
    ]

    floor = market_data["pricing_intelligence"]["current_cpm_floor"]

    if issue == "bid_too_low":
        recommended_bid = round(floor * 1.08, 2)
        action = {
            "type": "bid_adjustment",
            "action": f"Increase bid from ${campaign['current_bid']:.2f} to ${recommended_bid:.2f}",
            "current_bid": campaign["current_bid"],
            "recommended_bid": recommended_bid,
        }
        expected = {
            "projected_win_rate": 0.28,
            "projected_final_delivery_pct": 0.92,
            "recovery_time_hours": 18,
            "budget_impact": round(
                (recommended_bid - campaign["current_bid"])
                * (campaign["impressions_goal"] * (1 - campaign["delivery_pct"]))
                / 1000, 2
            ),
        }
    elif issue == "competitive_pressure":
        recommended_bid = round(market_data["pricing_intelligence"]["cpm_percentiles"]["p75"], 2)
        action = {
            "type": "bid_adjustment",
            "action": f"Increase bid to P75 (${recommended_bid:.2f}) to outpace competitors",
            "current_bid": campaign["current_bid"],
            "recommended_bid": recommended_bid,
        }
        expected = {
            "projected_win_rate": 0.30,
            "projected_final_delivery_pct": 0.88,
            "recovery_time_hours": 24,
            "budget_impact": round(
                (recommended_bid - campaign["current_bid"])
                * (campaign["impressions_goal"] * (1 - campaign["delivery_pct"]))
                / 1000, 2
            ),
        }
    elif issue == "inventory_shortage":
        action = {
            "type": "geo_expansion",
            "action": "Expand targeting to adjacent DMAs to access more inventory",
        }
        expected = {
            "projected_win_rate": campaign["win_rate"] + 0.08,
            "projected_final_delivery_pct": 0.85,
            "recovery_time_hours": 36,
            "budget_impact": 0,
        }
    elif issue == "creative_fatigue":
        action = {
            "type": "creative_refresh",
            "action": "Rotate in new creative assets — CTR has declined while win rate remains healthy",
        }
        expected = {
            "projected_win_rate": campaign["win_rate"],
            "projected_final_delivery_pct": campaign["delivery_pct"] + 0.12,
            "recovery_time_hours": 12,
            "budget_impact": 0,
        }
    else:
        action = {
            "type": "manual_review",
            "action": f"Issue '{issue}' requires manual review — recommend checking pacing settings and targeting scope",
        }
        expected = {
            "projected_win_rate": campaign["win_rate"] + 0.05,
            "projected_final_delivery_pct": campaign["delivery_pct"] + 0.10,
            "recovery_time_hours": 24,
            "budget_impact": 0,
        }

    geo_locked = False
    if config and config.get("client_restrictions", {}).get("geo_locked"):
        geo_locked = True
        if action["type"] == "geo_expansion":
            action["warning"] = "This campaign is geo_locked — geo expansion requires client approval."

    success_rate = (
        len([h for h in similar if h["outcome"]["goal_achieved"]]) / max(len(similar), 1)
    )

    return json.dumps({
        "campaign_id": campaign_id,
        "recommendation": action,
        "expected_outcomes": expected,
        "confidence": diag["confidence"],
        "rationale": {
            "primary_issue": issue,
            "similar_campaigns_found": len(similar),
            "historical_success_rate": round(success_rate, 2),
            "geo_locked": geo_locked,
        },
    })


@tool
def calculate_what_if_scenario(campaign_id: str, proposed_change: str) -> str:
    """Projects the expected outcome if a specific change is applied to a campaign
    (e.g., 'what if I set bid to $5.25?'). Returns: predicted win rate, projected
    final delivery %, estimated recovery time, and budget impact. Use when the trader
    wants to evaluate a specific change before committing, or to power bid comparison
    ('show me $5.00 vs $5.50').
    Required: campaign_id, proposed_change (JSON with type and value, e.g.
    {\"type\": \"bid_adjustment\", \"value\": 5.25})."""
    campaign = find_campaign(campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found", "campaign_id": campaign_id})

    market_data = find_market(campaign["industry"], campaign["geo"])
    if not market_data:
        return json.dumps({"error": "Market data not found for campaign segment"})

    # Parse the proposed change
    try:
        change = json.loads(proposed_change) if isinstance(proposed_change, str) else proposed_change
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid proposed_change JSON format"})

    change_type = change.get("type", "bid_adjustment")
    change_value = change.get("value", 0)

    floor = market_data["pricing_intelligence"]["current_cpm_floor"]
    p50 = market_data["pricing_intelligence"]["cpm_percentiles"]["p50"]
    p75 = market_data["pricing_intelligence"]["cpm_percentiles"]["p75"]
    remaining_impressions = campaign["impressions_goal"] * (1 - campaign["delivery_pct"])

    if change_type == "bid_adjustment":
        new_bid = float(change_value)
        bid_ratio = new_bid / floor if floor > 0 else 1.0

        # Simple win-rate model: logistic-ish curve around the floor
        if bid_ratio < 0.80:
            predicted_win_rate = 0.05
        elif bid_ratio < 1.0:
            predicted_win_rate = 0.05 + (bid_ratio - 0.80) * 1.0
        elif bid_ratio < 1.20:
            predicted_win_rate = 0.25 + (bid_ratio - 1.0) * 0.75
        else:
            predicted_win_rate = min(0.50, 0.40 + (bid_ratio - 1.20) * 0.25)

        budget_impact = round((new_bid - campaign["current_bid"]) * remaining_impressions / 1000, 2)
        recovery_hours = max(6, int(48 * (1 - predicted_win_rate)))
        projected_delivery = min(1.0, campaign["delivery_pct"] + predicted_win_rate * 0.8 * (1 - campaign["delivery_pct"]))

        return json.dumps({
            "campaign_id": campaign_id,
            "scenario": {
                "type": "bid_adjustment",
                "current_bid": campaign["current_bid"],
                "proposed_bid": new_bid,
                "market_floor": floor,
                "market_p50": p50,
                "market_p75": p75,
            },
            "projections": {
                "predicted_win_rate": round(predicted_win_rate, 4),
                "projected_final_delivery_pct": round(projected_delivery, 4),
                "estimated_recovery_hours": recovery_hours,
                "budget_impact": budget_impact,
            },
        })

    return json.dumps({
        "campaign_id": campaign_id,
        "error": f"Unsupported change type: {change_type}. Supported: bid_adjustment.",
    })
