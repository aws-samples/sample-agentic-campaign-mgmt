# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tool Group 1: Campaign Data Access (4 tools).

These tools provide read access to campaign metrics, configuration,
trader portfolios, and historical time-series data.
"""

import json
import random
from strands import tool

from agent.data_loader import (
    find_campaign,
    find_config,
    load_campaigns,
    load_trader_profiles,
)


@tool
def get_campaign_metrics(campaign_id: str) -> str:
    """Returns real-time performance metrics for a campaign: impressions delivered vs. goal,
    delivery_pct, expected_pct, win rate, spend, CTR, current bid, and days remaining.
    **Call this first** whenever a campaign ID is mentioned, or before calling diagnose or recommend.
    Required: campaign_id."""
    campaign = find_campaign(campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found", "campaign_id": campaign_id})

    impressions_delivered = int(campaign["impressions_goal"] * campaign["delivery_pct"])
    clicks = int(impressions_delivered * campaign["ctr"])
    spend = campaign["budget_total"] * campaign["delivery_pct"]

    result = {
        "campaign_id": campaign_id,
        "campaign_name": campaign["campaign_name"],
        "status": campaign["status"],
        "delivery": {
            "impressions_delivered": impressions_delivered,
            "impressions_goal": campaign["impressions_goal"],
            "delivery_pct": campaign["delivery_pct"],
            "expected_pct": campaign["expected_pct"],
            "delivery_variance": round(campaign["delivery_pct"] - campaign["expected_pct"], 4),
        },
        "engagement": {
            "clicks": clicks,
            "ctr": campaign["ctr"],
            "conversion_rate": campaign["conversion_rate"],
        },
        "financials": {
            "spend": round(spend, 2),
            "budget_total": campaign["budget_total"],
            "current_bid": campaign["current_bid"],
        },
        "auction": {
            "win_rate": campaign["win_rate"],
        },
        "time_context": {
            "days_elapsed": campaign["days_elapsed"],
            "days_remaining": campaign["days_remaining"],
            "days_total": campaign["days_total"],
            "flight_start": campaign["flight_start"],
            "flight_end": campaign["flight_end"],
        },
    }
    return json.dumps(result)


@tool
def get_campaign_configuration(campaign_id: str) -> str:
    """Returns the campaign setup: geo targeting, demographics, interests, bid strategy,
    current bid, budget, flight dates, and client-imposed restrictions (e.g., geo_locked).
    Use when the user asks how a campaign is configured, or when diagnosis requires knowing
    whether changes are restricted. Required: campaign_id."""
    config = find_config(campaign_id)
    if not config:
        return json.dumps({"error": "Configuration not found", "campaign_id": campaign_id})

    result = {
        "campaign_id": config["campaign_id"],
        "campaign_name": config["campaign_name"],
        "status": config["status"],
        "industry": config["industry"],
        "objective": config["objective"],
        "targeting": config["targeting"],
        "bidding": {
            "strategy": config["bidding"]["strategy"],
            "current_bid": config["bidding"]["current_bid"],
            "bid_floor": config["bidding"]["bid_floor"],
            "bid_ceiling": config["bidding"]["bid_ceiling"],
        },
        "budget": config["budget"],
        "flight": {
            "start": config["flight"]["start"],
            "end": config["flight"]["end"],
        },
        "client_restrictions": config["client_restrictions"],
    }
    return json.dumps(result)


@tool
def get_trader_campaigns(trader_id: str, status_filter: str = "") -> str:
    """Returns all campaigns managed by a trader with delivery status, pacing, win rate,
    bid, and risk classification for each. Use to answer portfolio-level questions
    ('which of my campaigns are at risk?') or to surface campaigns needing attention.
    Required: trader_id. Optional: status_filter (at_risk | on_track | ahead)."""
    profiles = load_trader_profiles()
    trader = next((t for t in profiles if t["trader_id"] == trader_id), None)
    if not trader:
        return json.dumps({"error": "Trader not found", "trader_id": trader_id})

    campaigns = load_campaigns()
    trader_campaigns = [c for c in campaigns if c["trader_id"] == trader_id]

    results = []
    for c in trader_campaigns:
        pace_ratio = c["delivery_pct"] / c["expected_pct"] if c["expected_pct"] > 0 else 1.0
        if pace_ratio < 0.80:
            risk = "at_risk"
        elif pace_ratio > 1.10:
            risk = "ahead"
        else:
            risk = "on_track"

        if status_filter and risk != status_filter:
            continue

        results.append({
            "campaign_id": c["campaign_id"],
            "campaign_name": c["campaign_name"],
            "status": c["status"],
            "delivery_pct": c["delivery_pct"],
            "expected_pct": c["expected_pct"],
            "win_rate": c["win_rate"],
            "current_bid": c["current_bid"],
            "days_remaining": c["days_remaining"],
            "risk_classification": risk,
        })

    return json.dumps({
        "trader_id": trader_id,
        "trader_name": trader["name"],
        "total_campaigns": len(results),
        "campaigns": results,
    })


@tool
def get_campaign_history(campaign_id: str, days_back: int = 7) -> str:
    """Returns daily time-series data for a campaign: impressions, spend, win rate,
    and bid changes across the flight. Use when the user asks about performance trends,
    how a campaign has evolved, or when historical context is needed before diagnosis.
    Required: campaign_id. Optional: days_back."""
    campaign = find_campaign(campaign_id)
    if not campaign:
        return json.dumps({"error": "Campaign not found", "campaign_id": campaign_id})

    # Synthesize daily history from the campaign snapshot
    days = min(days_back, campaign["days_elapsed"])
    daily = []
    base_delivery = campaign["delivery_pct"] / max(campaign["days_elapsed"], 1)
    base_win = campaign["win_rate"]
    base_bid = campaign["current_bid"]

    for day in range(1, days + 1):
        jitter = random.uniform(-0.02, 0.02)
        daily.append({
            "day": day,
            "impressions": int(campaign["impressions_goal"] * (base_delivery + jitter)),
            "spend": round(campaign["budget_daily"] * (base_delivery / (1 / campaign["days_total"]) + jitter), 2),
            "win_rate": round(base_win + random.uniform(-0.01, 0.01), 4),
            "bid": round(base_bid + random.uniform(-0.10, 0.10), 2),
        })

    return json.dumps({
        "campaign_id": campaign_id,
        "campaign_name": campaign["campaign_name"],
        "days_returned": len(daily),
        "daily_data": daily,
    })
