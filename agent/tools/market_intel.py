# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tool Group 3: Market Intelligence (3 tools).

These tools provide market conditions, benchmark comparisons,
and historical similarity searches.
"""

import json
from strands import tool

from agent.data_loader import (
    find_campaign,
    find_market,
    load_historical_outcomes,
)


@tool
def get_market_intelligence(industry: str, geo: str) -> str:
    """Returns current market conditions for a campaign's targeting segment: CPM floor price,
    active competitor count, competitor change in 24h, available impressions, demand/supply
    ratio, and CPM percentiles (P25/P50/P90).
    **Call in parallel with get_campaign_metrics** when diagnosis or a market comparison
    is needed — these tools are independent. Required: industry, geo."""
    market = find_market(industry, geo)
    if not market:
        return json.dumps({"error": f"No market data for {industry}/{geo}"})

    return json.dumps({
        "market_segment": market["market_segment"],
        "geo": market["geo"],
        "industry": market["industry"],
        "cpm_floor": market["pricing_intelligence"]["current_cpm_floor"],
        "cpm_percentiles": market["pricing_intelligence"]["cpm_percentiles"],
        "cpm_change_pct": market["pricing_intelligence"]["cpm_change_pct"],
        "active_competitors": market["competitive_landscape"]["active_competitors"],
        "competitor_change_24h": market["competitive_landscape"]["competitor_change_24h"],
        "competition_level": market["competitive_landscape"]["competition_level"],
        "available_impressions_24h": market["inventory_availability"]["available_impressions_24h"],
        "demand_supply_ratio": market["inventory_availability"]["demand_supply_ratio"],
    })


@tool
def get_benchmark_comparison(campaign_id: str, industry: str, geo: str) -> str:
    """Compares a campaign's win rate, CTR, and CPM against industry averages for its
    segment and returns percentile rank for each metric. Use when the user asks how
    competitive a campaign is, whether its numbers are normal, or to contextualize a
    low win rate. Required: campaign_id, industry, geo."""
    campaign = find_campaign(campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found", "campaign_id": campaign_id})

    market = find_market(industry, geo)
    if not market:
        return json.dumps({"error": f"No market data for {industry}/{geo}"})

    benchmarks = market["performance_benchmarks"]
    spend = campaign["budget_total"] * campaign["delivery_pct"]
    impressions = campaign["impressions_goal"] * campaign["delivery_pct"]
    actual_cpm = (spend / (impressions / 1000)) if impressions > 0 else 0

    def _percentile_rank(actual: float, avg: float) -> int:
        ratio = actual / avg if avg > 0 else 1.0
        if ratio >= 1.5:
            return 90
        if ratio >= 1.2:
            return 75
        if ratio >= 0.9:
            return 50
        if ratio >= 0.7:
            return 25
        return 10

    return json.dumps({
        "campaign_id": campaign_id,
        "campaign_name": campaign["campaign_name"],
        "benchmarks": {
            "win_rate": {
                "campaign": campaign["win_rate"],
                "industry_avg": benchmarks["industry_avg_win_rate"],
                "percentile": _percentile_rank(campaign["win_rate"], benchmarks["industry_avg_win_rate"]),
            },
            "ctr": {
                "campaign": campaign["ctr"],
                "industry_avg": benchmarks["industry_avg_ctr"],
                "percentile": _percentile_rank(campaign["ctr"], benchmarks["industry_avg_ctr"]),
            },
            "cpm": {
                "campaign": round(actual_cpm, 2),
                "industry_avg": benchmarks["industry_avg_cpm"],
                "percentile": _percentile_rank(actual_cpm, benchmarks["industry_avg_cpm"]),
            },
        },
    })


@tool
def find_similar_campaigns(diagnosis_type: str, metrics: str, market: str) -> str:
    """Searches historical campaign records for past campaigns with similar characteristics
    (same diagnosis type, comparable bid gap, same industry and geo, similar flight stage).
    Returns ranked results with similarity scores, intervention applied, and outcome.
    Used by generate_recommendation to establish confidence score and surface historical
    precedents for the trader. Required: diagnosis_type, metrics, market."""
    historical = load_historical_outcomes()

    # Parse metrics and market if provided as JSON strings
    try:
        metrics_data = json.loads(metrics) if isinstance(metrics, str) else metrics
    except json.JSONDecodeError:
        metrics_data = {}
    try:
        market_data = json.loads(market) if isinstance(market, str) else market
    except json.JSONDecodeError:
        market_data = {}

    industry = market_data.get("industry", "")
    geo = market_data.get("geo", "")

    # Filter and score
    results = []
    for h in historical:
        score = 0.0
        if h.get("industry") == industry:
            score += 0.3
        if h.get("geo") == geo:
            score += 0.2
        if h.get("intervention", {}).get("type") == "bid_adjustment" and diagnosis_type == "bid_too_low":
            score += 0.3
        if h.get("outcome", {}).get("outcome_status") == "success":
            score += 0.2

        if score >= 0.4:
            results.append({
                "campaign_id": h["campaign_id"],
                "campaign_name": h["campaign_name"],
                "industry": h["industry"],
                "geo": h["geo"],
                "similarity_score": round(score, 2),
                "intervention": h.get("intervention", {}),
                "outcome": h.get("outcome", {}),
            })

    results.sort(key=lambda x: x["similarity_score"], reverse=True)

    return json.dumps({
        "diagnosis_type": diagnosis_type,
        "matches_found": len(results),
        "similar_campaigns": results[:10],
    })
