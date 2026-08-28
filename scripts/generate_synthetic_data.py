# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Synthetic Data Generator for Campaign Optimization Agent POC

Generates realistic campaign data, historical outcomes, market intelligence,
and trader profiles for testing the Bedrock Agent.

Usage:
    python generate_synthetic_data.py
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid


# Configuration
NUM_ACTIVE_CAMPAIGNS = 50
NUM_HISTORICAL_CAMPAIGNS = 100
NUM_TRADERS = 5

# Industry and targeting options
INDUSTRIES = ["automotive", "retail", "financial", "healthcare", "travel", "entertainment", "food_beverage"]
OBJECTIVES = ["awareness", "traffic", "conversions"]
GEO_MARKETS = ["Chicago", "New York", "Los Angeles", "Miami", "Dallas", "Atlanta", "Phoenix", "Denver", "Seattle", "Boston"]
CAMPAIGN_STATUSES = ["active", "paused", "completed"]


def random_date(start_days_ago=90, end_days_ago=0):
    """
    Return a random datetime between two offsets relative to now.

    Args:
        start_days_ago: How many days ago the window opens (default 90).
        end_days_ago:   How many days ago the window closes (default 0 = now).

    Returns:
        datetime: A random point within the specified window.
    """
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def generate_campaign_id():
    """
    Return a random 4-digit campaign ID string in the range 4000–9999.

    IDs below 4000 are reserved for historical_outcomes data so that
    active and historical datasets have non-overlapping ID spaces.
    """
    return str(random.randint(4000, 9999))


def generate_campaign_name(industry, geo):
    """
    Return a realistic campaign name for the given industry and geo.

    Names follow the pattern "{Brand} {Campaign Type} - {Geo}" using
    industry-specific brand and template lists. Used for display purposes only;
    the name has no effect on downstream logic.

    Args:
        industry: One of INDUSTRIES (e.g. "automotive", "retail").
        geo:      One of GEO_MARKETS (e.g. "Chicago").

    Returns:
        str: e.g. "Honda Spring Sale - Chicago"
    """
    templates = {
        "automotive": [
            "{brand} Spring Sale - {geo}",
            "{brand} Clearance Event - {geo}",
            "{brand} Test Drive Campaign - {geo}",
            "{brand} New Model Launch - {geo}"
        ],
        "retail": [
            "{brand} Holiday Sale - {geo}",
            "{brand} Back to School - {geo}",
            "{brand} Flash Sale - {geo}",
            "{brand} Summer Collection - {geo}"
        ],
        "financial": [
            "{brand} Mortgage Rates - {geo}",
            "{brand} Credit Card Offer - {geo}",
            "{brand} Investment Services - {geo}",
            "{brand} Personal Loans - {geo}"
        ],
        "healthcare": [
            "{brand} Health Insurance - {geo}",
            "{brand} Urgent Care - {geo}",
            "{brand} Wellness Program - {geo}",
            "{brand} Telemedicine - {geo}"
        ],
        "travel": [
            "{brand} Summer Vacation - {geo}",
            "{brand} Flight Deals - {geo}",
            "{brand} Hotel Booking - {geo}",
            "{brand} Cruise Packages - {geo}"
        ],
        "entertainment": [
            "{brand} Concert Series - {geo}",
            "{brand} Theater Production - {geo}",
            "{brand} Sports Events - {geo}",
            "{brand} Festival Tickets - {geo}"
        ],
        "food_beverage": [
            "{brand} Restaurant Week - {geo}",
            "{brand} New Menu Launch - {geo}",
            "{brand} Delivery Service - {geo}",
            "{brand} Catering Promo - {geo}"
        ]
    }

    brands = {
        "automotive": ["Honda", "Toyota", "Ford", "Chevrolet", "Nissan", "BMW"],
        "retail": ["Target", "Walmart", "Macy's", "Best Buy", "HomeGoods", "TJ Maxx"],
        "financial": ["Chase", "Bank of America", "Wells Fargo", "Citibank", "Capital One"],
        "healthcare": ["UnitedHealth", "Anthem", "Cigna", "Aetna", "Humana"],
        "travel": ["Expedia", "Booking.com", "Airbnb", "Delta", "United Airlines"],
        "entertainment": ["LiveNation", "AMC Theaters", "Local Arts Center", "Sports Arena"],
        "food_beverage": ["Local Restaurant", "Fast Casual Chain", "Coffee Shop", "Food Delivery"]
    }

    template = random.choice(templates.get(industry, templates["retail"]))
    brand = random.choice(brands.get(industry, brands["retail"]))

    return template.format(brand=brand, geo=geo)


def generate_active_campaigns(num_campaigns=50):
    """
    Generate a list of active campaign records simulating current DSP state.

    Two special campaigns are always included at fixed positions:
    - #4782 (Honda Spring Sale - Chicago): at-risk, bid below floor — used as
      the primary demo scenario for Journey 1 diagnosis and recommendation.
    - #5201 (Luxury Apartments - Miami): on-track — used as a healthy contrast.

    Remaining campaigns are randomly distributed across delivery statuses:
    60% on_track, 25% at_risk, 10% ahead, 5% critical.

    Each record contains the fields consumed by get_campaign_metrics() and
    diagnose_campaign_issue() in sample_lambda_function.py:
        campaign_id, campaign_name, industry, objective, geo, status,
        trader_id, client_id, priority, current_bid, budget_total,
        budget_daily, impressions_goal, days_total, days_elapsed,
        days_remaining, delivery_pct, expected_pct, win_rate, ctr,
        conversion_rate, flight_start, flight_end

    Args:
        num_campaigns: Total number of campaigns to generate (default 50).

    Returns:
        List[dict]: Campaign records. In production these would come from DynamoDB.
    """
    campaigns = []

    # Special campaigns from Journey 1
    special_campaigns = [
        {
            "campaign_id": "4782",
            "campaign_name": "Honda Spring Sale - Chicago",
            "industry": "automotive",
            "objective": "traffic",
            "geo": "Chicago",
            "status": "active",
            "trader_id": "trader_alpha",
            "client_id": "client_honda_001",
            "priority": "high",
            "current_bid": 4.20,
            "budget_total": 15000.00,
            "budget_daily": 2142.86,
            "impressions_goal": 500000,
            "days_total": 7,
            "days_elapsed": 3,
            "days_remaining": 4,
            "delivery_pct": 0.29,  # At risk!
            "expected_pct": 0.43,
            "win_rate": 0.08,
            "ctr": 0.007,
            "conversion_rate": 0,
            "flight_start": (datetime.now() - timedelta(days=3)).isoformat(),
            "flight_end": (datetime.now() + timedelta(days=4)).isoformat()
        },
        {
            "campaign_id": "5201",
            "campaign_name": "Luxury Apartments - Miami",
            "industry": "retail",
            "objective": "conversions",
            "geo": "Miami",
            "status": "active",
            "trader_id": "trader_bravo",
            "client_id": "client_realestate_002",
            "priority": "standard",
            "current_bid": 6.80,
            "budget_total": 25000.00,
            "budget_daily": 1666.67,
            "impressions_goal": 2500000,
            "days_total": 15,
            "days_elapsed": 8,
            "days_remaining": 7,
            "delivery_pct": 0.48,  # On track
            "expected_pct": 0.53,
            "win_rate": 0.28,
            "ctr": 0.007,
            "conversion_rate": 0.0151,
            "flight_start": (datetime.now() - timedelta(days=8)).isoformat(),
            "flight_end": (datetime.now() + timedelta(days=7)).isoformat()
        }
    ]

    campaigns.extend(special_campaigns)

    # Generate remaining campaigns
    traders = ["trader_alpha", "trader_bravo", "trader_delta", "trader_echo", "trader_charlie"]

    for i in range(num_campaigns - len(special_campaigns)):
        campaign_id = generate_campaign_id()
        industry = random.choice(INDUSTRIES)
        geo = random.choice(GEO_MARKETS)
        trader = random.choice(traders)
        objective = random.choice(OBJECTIVES)

        # Campaign timing
        days_total = random.choice([7, 10, 14, 21, 30])
        days_elapsed = random.randint(1, days_total - 1)
        days_remaining = days_total - days_elapsed

        # Budget
        budget_total = random.choice([5000, 10000, 15000, 20000, 25000, 30000, 50000, 75000, 100000])

        # Impressions goal based on budget (roughly $5 CPM average)
        impressions_goal = int(budget_total * 200)  # Assuming $5 CPM average

        # Current delivery (some on track, some at risk, some ahead)
        expected_progress = days_elapsed / days_total
        delivery_status = random.choices(
            ["on_track", "at_risk", "ahead", "critical"],
            weights=[0.60, 0.25, 0.10, 0.05]
        )[0]

        if delivery_status == "on_track":
            delivery_pct = expected_progress * random.uniform(0.90, 1.10)
        elif delivery_status == "at_risk":
            delivery_pct = expected_progress * random.uniform(0.50, 0.80)
        elif delivery_status == "ahead":
            delivery_pct = expected_progress * random.uniform(1.15, 1.35)
        else:  # critical
            delivery_pct = expected_progress * random.uniform(0.20, 0.45)

        delivery_pct = min(1.0, delivery_pct)  # Cap at 100%

        # Bid (related to market floor)
        market_floor = random.uniform(3.50, 8.00)

        if delivery_status in ["on_track", "ahead"]:
            current_bid = market_floor * random.uniform(1.05, 1.30)
            win_rate = random.uniform(0.22, 0.35)
        else:  # at_risk or critical
            current_bid = market_floor * random.uniform(0.75, 0.98)
            win_rate = random.uniform(0.05, 0.15)

        # Engagement metrics
        ctr = random.uniform(0.004, 0.012)  # 0.4% to 1.2%
        conversion_rate = random.uniform(0.01, 0.05) if objective == "conversions" else 0

        campaign = {
            "campaign_id": campaign_id,
            "campaign_name": generate_campaign_name(industry, geo),
            "industry": industry,
            "objective": objective,
            "geo": geo,
            "status": "active",
            "trader_id": trader,
            "client_id": f"client_{random.randint(100, 999)}",
            "priority": random.choice(["standard", "high", "critical"]),
            "current_bid": round(current_bid, 2),
            "budget_total": budget_total,
            "budget_daily": round(budget_total / days_total, 2),
            "impressions_goal": impressions_goal,
            "days_total": days_total,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "delivery_pct": round(delivery_pct, 3),
            "expected_pct": round(expected_progress, 3),
            "win_rate": round(win_rate, 3),
            "ctr": round(ctr, 5),
            "conversion_rate": round(conversion_rate, 4) if objective == "conversions" else 0,
            "flight_start": (datetime.now() - timedelta(days=days_elapsed)).isoformat(),
            "flight_end": (datetime.now() + timedelta(days=days_remaining)).isoformat()
        }

        campaigns.append(campaign)

    return campaigns


def generate_campaign_configurations(campaigns):
    """
    Generate a campaign configuration record for each active campaign.

    Configurations represent the setup decisions a trader makes before a campaign
    goes live — targeting, bidding strategy, budget pacing, and client restrictions.
    In production these would be stored in DynamoDB alongside the campaign record.

    Key fields generated per campaign:
        targeting:  geo (DMA), demographics, interests, device_types, custom_audiences
        bidding:    strategy (fixed_cpm), current_bid, bid_floor, bid_ceiling, bid_history
        budget:     type (lifetime), total, daily, pacing_strategy
        client_restrictions: geo_locked, budget_locked, targeting_locked, notes

    The geo_locked and budget_locked flags are used by generate_recommendation() to
    determine which intervention types are permissible for a given campaign.

    Args:
        campaigns: List of campaign dicts from generate_active_campaigns().

    Returns:
        List[dict]: One configuration record per campaign, same ordering.
    """
    configs = []

    for campaign in campaigns:
        config = {
            "campaign_id": campaign["campaign_id"],
            "campaign_name": campaign["campaign_name"],
            "client_id": campaign["client_id"],
            "trader_id": campaign["trader_id"],
            "status": campaign["status"],
            "created_at": (datetime.fromisoformat(campaign["flight_start"]) - timedelta(days=2)).isoformat(),

            "industry": campaign["industry"],
            "objective": campaign["objective"],
            "priority": campaign.get("priority", "standard"),

            "targeting": {
                "geo": {
                    "type": "dma",
                    "values": [campaign["geo"]],
                    "radius_miles": None
                },
                "demographics": {
                    "age_range": random.choice([[18, 34], [25, 44], [25, 54], [35, 65]]),
                    "gender": random.choice(["all", "male", "female"]),
                    "income": random.choice([["25k-50k", "50k-100k"], ["50k-100k", "100k+"], ["100k+"]])
                },
                "interests": random.sample(
                    ["shopping", "automotive", "travel", "finance", "health", "entertainment", "food", "sports"],
                    k=random.randint(2, 4)
                ),
                "device_types": random.choice([
                    ["desktop", "mobile", "tablet"],
                    ["mobile", "tablet"],
                    ["desktop", "mobile"]
                ]),
                "custom_audiences": [f"audience_{random.randint(1, 10)}"] if random.random() > 0.5 else []
            },

            "bidding": {
                "strategy": "fixed_cpm",
                "current_bid": campaign["current_bid"],
                "bid_floor": round(campaign["current_bid"] * 0.5, 2),
                "bid_ceiling": round(campaign["current_bid"] * 3.0, 2),
                "bid_history": [
                    {
                        "timestamp": campaign["flight_start"],
                        "bid": campaign["current_bid"],
                        "set_by": "trader",
                        "reason": "initial_setup"
                    }
                ]
            },

            "budget": {
                "type": "lifetime",
                "total": campaign["budget_total"],
                "daily": campaign["budget_daily"],
                "pacing_strategy": "even"
            },

            "flight": {
                "start": campaign["flight_start"],
                "end": campaign["flight_end"],
                "timezone": "America/Chicago"
            },

            "creative_ids": [f"creative_{random.randint(100, 999)}" for _ in range(random.randint(1, 3))],
            "creative_rotation": random.choice(["optimized", "even"]),

            "optimization": {
                "auto_optimize": False,
                "optimization_goal": campaign["impressions_goal"],
                "frequency_cap": {
                    "impressions": random.randint(3, 10),
                    "period": "24h"
                }
            },

            "client_restrictions": {
                "geo_locked": random.choice([True, False]),
                "budget_locked": random.choice([True, False]),
                "targeting_locked": False,
                "notes": random.choice([
                    "",
                    "Client specifically wants Denver metro only",
                    "Cannot expand geography - venue is local",
                    "Budget is fixed, no increases allowed"
                ])
            }
        }

        configs.append(config)

    return configs


def generate_historical_outcomes(num_campaigns=100):
    """
    Generate historical campaign records capturing the full intervention lifecycle.

    Each record represents a past campaign that experienced underdelivery, received
    an intervention (bid adjustment, targeting expansion, etc.), and has a recorded
    outcome. These records are used by find_similar_campaigns() to establish
    confidence scores and surface precedents for the agent's recommendations.

    Two fixed historical records are always included:
    - #4201 (Chevrolet February Event - Chicago): bid raised from $3.80 → $4.75, recovered to 95%
    - #3890 (Ford January Sale - Chicago): bid raised from $4.00 → $5.20, recovered to 112%

    Note: ~60% of generated interventions are bid_adjustment (the most common fix in
    CTV/OTT), with the remainder split across targeting_expansion, creative_refresh,
    and pacing_adjustment. The current training data for the ML model is derived from
    these records — if adding new issue types, extend intervention_type weights here.

    Outcome quality correlates with intervention timing: agent-recommended early
    interventions (before 50% of flight elapsed) have a higher success rate.

    Args:
        num_campaigns: Total historical records to generate (default 100).

    Returns:
        List[dict]: Historical outcome records. In production these come from Athena/S3.
            Each record contains: campaign_id, industry, geo, initial_state (bid,
            win_rate, delivery at intervention day), intervention (type, from/to bid,
            change_pct), outcome (final_delivery_pct, recovery_time_hours, goal_achieved).
    """
    outcomes = []

    # Include the successful examples from Journey 1
    special_outcomes = [
        {
            "campaign_id": "4201",
            "campaign_name": "Chevrolet February Event - Chicago",
            "run_date": "2026-02-01",
            "industry": "automotive",
            "geo": "Chicago",
            "objective": "traffic",
            "budget_total": 12000,
            "impressions_goal": 450000,
            "days_total": 7,
            "initial_state": {
                "day_3_delivery": 0.31,
                "day_3_win_rate": 0.09,
                "bid_at_day_3": 3.80,
                "market_floor_day_3": 4.50
            },
            "intervention": {
                "type": "bid_adjustment",
                "timestamp": "2026-02-03T10:00:00Z",
                "action": "increase_bid",
                "from_bid": 3.80,
                "to_bid": 4.75,
                "change_pct": 0.25,
                "recommended_by": "agent",
                "accepted_by": "trader_b"
            },
            "outcome": {
                "recovery_time_hours": 18,
                "final_delivery_pct": 0.95,
                "final_win_rate": 0.28,
                "budget_utilization": 0.98,
                "outcome_status": "success",
                "goal_achieved": True,
                "trader_satisfaction": 5
            },
            "similarity_score": 0.89
        },
        {
            "campaign_id": "3890",
            "campaign_name": "Ford January Sale - Chicago",
            "run_date": "2026-01-15",
            "industry": "automotive",
            "geo": "Chicago",
            "objective": "traffic",
            "budget_total": 18000,
            "impressions_goal": 600000,
            "days_total": 10,
            "initial_state": {
                "day_4_delivery": 0.28,
                "day_4_win_rate": 0.07,
                "bid_at_day_4": 4.00,
                "market_floor_day_4": 5.00
            },
            "intervention": {
                "type": "bid_adjustment",
                "timestamp": "2026-01-19T09:30:00Z",
                "action": "increase_bid",
                "from_bid": 4.00,
                "to_bid": 5.20,
                "change_pct": 0.30,
                "recommended_by": "agent",
                "accepted_by": "trader_a"
            },
            "outcome": {
                "recovery_time_hours": 24,
                "final_delivery_pct": 1.12,
                "final_win_rate": 0.32,
                "budget_utilization": 1.05,
                "outcome_status": "success",
                "goal_achieved": True,
                "trader_satisfaction": 5
            },
            "similarity_score": 0.85
        }
    ]

    outcomes.extend(special_outcomes)

    # Generate additional historical campaigns
    for i in range(num_campaigns - len(special_outcomes)):
        campaign_id = str(random.randint(1000, 3999))
        industry = random.choice(INDUSTRIES)
        geo = random.choice(GEO_MARKETS)
        objective = random.choice(OBJECTIVES)

        run_date = random_date(start_days_ago=180, end_days_ago=7)
        days_total = random.choice([7, 10, 14, 21, 30])
        budget_total = random.choice([5000, 10000, 15000, 20000, 30000, 50000])

        # Initial underdelivery situation
        initial_day = random.randint(2, int(days_total * 0.4))
        expected_delivery = initial_day / days_total
        initial_delivery = expected_delivery * random.uniform(0.30, 0.70)

        initial_bid = random.uniform(3.00, 6.00)
        market_floor = initial_bid * random.uniform(1.10, 1.40)

        # Intervention
        intervention_type = random.choice([
            "bid_adjustment", "bid_adjustment", "bid_adjustment",  # Most common
            "targeting_expansion", "creative_refresh", "pacing_adjustment"
        ])

        if intervention_type == "bid_adjustment":
            new_bid = market_floor * random.uniform(1.05, 1.25)
            change_pct = (new_bid - initial_bid) / initial_bid

            intervention = {
                "type": "bid_adjustment",
                "timestamp": (run_date + timedelta(days=initial_day)).isoformat(),
                "action": "increase_bid",
                "from_bid": round(initial_bid, 2),
                "to_bid": round(new_bid, 2),
                "change_pct": round(change_pct, 3),
                "recommended_by": random.choice(["agent", "trader"]),
                "accepted_by": random.choice(["trader_b", "trader_a", "trader_c"])
            }
        else:
            intervention = {
                "type": intervention_type,
                "timestamp": (run_date + timedelta(days=initial_day)).isoformat(),
                "action": intervention_type,
                "details": "Various adjustments made",
                "recommended_by": random.choice(["agent", "trader"]),
                "accepted_by": random.choice(["trader_b", "trader_a", "trader_c"])
            }

        # Outcome (mostly successful if intervention was timely)
        if intervention["recommended_by"] == "agent" and initial_day < days_total * 0.5:
            # Early intervention by agent = higher success rate
            final_delivery = random.uniform(0.88, 1.15)
            outcome_status = "success"
            goal_achieved = final_delivery >= 0.90
            trader_satisfaction = random.randint(4, 5)
            recovery_hours = random.randint(12, 36)
        else:
            # Later or trader-only intervention = lower success rate
            final_delivery = random.uniform(0.65, 1.05)
            outcome_status = "success" if final_delivery >= 0.90 else "partial"
            goal_achieved = final_delivery >= 0.90
            trader_satisfaction = random.randint(3, 4)
            recovery_hours = random.randint(24, 72)

        outcome = {
            "campaign_id": campaign_id,
            "campaign_name": generate_campaign_name(industry, geo),
            "run_date": run_date.strftime("%Y-%m-%d"),
            "industry": industry,
            "geo": geo,
            "objective": objective,
            "budget_total": budget_total,
            "impressions_goal": int(budget_total * 200),
            "days_total": days_total,
            "initial_state": {
                f"day_{initial_day}_delivery": round(initial_delivery, 3),
                f"day_{initial_day}_win_rate": round(random.uniform(0.05, 0.15), 3),
                f"bid_at_day_{initial_day}": round(initial_bid, 2),
                f"market_floor_day_{initial_day}": round(market_floor, 2)
            },
            "intervention": intervention,
            "outcome": {
                "recovery_time_hours": recovery_hours,
                "final_delivery_pct": round(final_delivery, 3),
                "final_win_rate": round(random.uniform(0.20, 0.35), 3),
                "budget_utilization": round(random.uniform(0.85, 1.10), 3),
                "outcome_status": outcome_status,
                "goal_achieved": goal_achieved,
                "trader_satisfaction": trader_satisfaction
            },
            "similarity_score": round(random.uniform(0.60, 0.95), 2)
        }

        outcomes.append(outcome)

    return outcomes


def generate_market_intelligence():
    """
    Generate market intelligence records for every geo × industry combination.

    One record is created for each of the 70 combinations (10 geos × 7 industries).
    The automotive/Chicago record is hardcoded to match campaign #4782's scenario
    (cpm_floor = $5.10, 12 competitors, demand_supply_ratio = 1.8).

    Each record is keyed by market_segment: "{industry}_{geo_lowercase}_dma"
    e.g. "automotive_chicago_dma". This key is how diagnose_campaign_issue()
    looks up market context for a campaign.

    Key fields per record:
        competitive_landscape:  active_competitors, competitor_change_24h, competition_level
        pricing_intelligence:   current_cpm_floor, cpm_floor_24h_ago, cpm_change_pct,
                                cpm_percentiles (p25/p50/p75/p90)
        inventory_availability: available_impressions_24h, demand_supply_ratio, inventory_tightness
        performance_benchmarks: industry_avg_win_rate, industry_avg_ctr, industry_avg_cpm

    In production, these records would be refreshed every 15–30 minutes from
    the DSP's real-time bid stream and stored in Redis or DynamoDB with a TTL.

    Returns:
        List[dict]: 70 market intelligence records.
    """
    markets = []

    # Special market for Campaign 4782
    markets.append({
        "market_segment": "automotive_chicago_dma",
        "timestamp": datetime.now().isoformat(),
        "geo": "Chicago",
        "industry": "automotive",
        "competitive_landscape": {
            "active_competitors": 12,
            "competitor_change_24h": 3,
            "competition_level": "high"
        },
        "pricing_intelligence": {
            "current_cpm_floor": 5.10,
            "cpm_floor_24h_ago": 4.85,
            "cpm_change_pct": 0.0515,
            "cpm_percentiles": {
                "p25": 4.80,
                "p50": 5.10,
                "p75": 6.20,
                "p90": 7.50
            }
        },
        "inventory_availability": {
            "available_impressions_24h": 2800000,
            "demand_supply_ratio": 1.8,
            "inventory_tightness": "high"
        },
        "performance_benchmarks": {
            "industry_avg_win_rate": 0.25,
            "industry_avg_ctr": 0.0059,
            "industry_avg_cpm": 5.45,
            "industry_avg_conversion_rate": 0.028
        }
    })

    # Generate markets for all geo/industry combinations
    for geo in GEO_MARKETS:
        for industry in INDUSTRIES:
            if geo == "Chicago" and industry == "automotive":
                continue  # Already added above

            markets.append({
                "market_segment": f"{industry}_{geo.lower().replace(' ', '_')}_dma",
                "timestamp": datetime.now().isoformat(),
                "geo": geo,
                "industry": industry,
                "competitive_landscape": {
                    "active_competitors": random.randint(5, 20),
                    "competitor_change_24h": random.randint(-2, 5),
                    "competition_level": random.choice(["low", "medium", "high"])
                },
                "pricing_intelligence": {
                    "current_cpm_floor": round(random.uniform(3.50, 8.00), 2),
                    "cpm_floor_24h_ago": round(random.uniform(3.00, 7.50), 2),
                    "cpm_change_pct": round(random.uniform(-0.05, 0.15), 4),
                    "cpm_percentiles": {
                        "p25": round(random.uniform(3.00, 5.00), 2),
                        "p50": round(random.uniform(4.50, 6.50), 2),
                        "p75": round(random.uniform(6.00, 8.00), 2),
                        "p90": round(random.uniform(7.50, 10.00), 2)
                    }
                },
                "inventory_availability": {
                    "available_impressions_24h": random.randint(500000, 5000000),
                    "demand_supply_ratio": round(random.uniform(0.8, 2.5), 2),
                    "inventory_tightness": random.choice(["loose", "normal", "tight", "high"])
                },
                "performance_benchmarks": {
                    "industry_avg_win_rate": round(random.uniform(0.18, 0.32), 3),
                    "industry_avg_ctr": round(random.uniform(0.004, 0.010), 5),
                    "industry_avg_cpm": round(random.uniform(4.50, 7.50), 2),
                    "industry_avg_conversion_rate": round(random.uniform(0.015, 0.045), 4)
                }
            })

    return markets


def generate_trader_profiles():
    """
    Return the five fixed trader profiles used across all POC scenarios.

    Trader profiles drive two behaviors in the agent:
    1. Notification routing — critical_alerts / warning_alerts / info_alerts
       preferences control when and how the agent surfaces issues.
    2. Response personalisation — detail_level (detailed / moderate / brief) and
       risk_tolerance (aggressive / balanced / conservative / moderate) affect
       how the agent frames its recommendations.

    The five traders are:
        trader_alpha    — intermediate, detailed, moderate risk, 62% acceptance rate
        trader_bravo  — senior, brief, conservative, 55% acceptance rate
        trader_delta   — senior, moderate, balanced, 71% acceptance rate (highest success rate)
        trader_echo     — intermediate, detailed, aggressive, 78% acceptance rate
        trader_charlie — intermediate, moderate, moderate, 65% acceptance rate

    In production these records would be stored in DynamoDB and injected into the
    AgentCore Memory session context at conversation start.

    Returns:
        List[dict]: Five trader profile records.
    """
    traders = [
        {
            "trader_id": "trader_alpha",
            "email": "alpha@example.com",
            "slack_user_id": "UALPHA01",
            "name": "Trader Alpha",
            "experience_level": "intermediate",
            "years_experience": 3,
            "active_campaigns": 42,
            "notification_preferences": {
                "critical_alerts": "immediate",
                "warning_alerts": "batched_hourly",
                "info_alerts": "daily_summary"
            },
            "recommendation_preferences": {
                "detail_level": "detailed",
                "risk_tolerance": "moderate",
                "typical_acceptance_rate": 0.62,
                "prefers_explanation_detail": "detailed"
            },
            "historical_performance": {
                "avg_campaign_success_rate": 0.82,
                "recommendations_received_30d": 45,
                "recommendations_accepted_30d": 28,
                "avg_response_time_minutes": 12
            },
            "working_hours": {
                "start": "08:00",
                "end": "18:00",
                "timezone": "America/Chicago"
            },
            "out_of_office": False,
            "backup_trader": "trader_bravo"
        },
        {
            "trader_id": "trader_bravo",
            "email": "bravo@example.com",
            "slack_user_id": "UBRAVO02",
            "name": "Trader Bravo",
            "experience_level": "senior",
            "years_experience": 5,
            "active_campaigns": 38,
            "notification_preferences": {
                "critical_alerts": "immediate",
                "warning_alerts": "immediate",
                "info_alerts": "batched_hourly"
            },
            "recommendation_preferences": {
                "detail_level": "brief",
                "risk_tolerance": "conservative",
                "typical_acceptance_rate": 0.55,
                "prefers_explanation_detail": "brief"
            },
            "historical_performance": {
                "avg_campaign_success_rate": 0.88,
                "recommendations_received_30d": 32,
                "recommendations_accepted_30d": 18,
                "avg_response_time_minutes": 8
            },
            "working_hours": {
                "start": "07:00",
                "end": "17:00",
                "timezone": "America/New_York"
            },
            "out_of_office": False,
            "backup_trader": "trader_delta"
        },
        {
            "trader_id": "trader_delta",
            "email": "delta@example.com",
            "slack_user_id": "UDELTA04",
            "name": "Trader Delta",
            "experience_level": "senior",
            "years_experience": 7,
            "active_campaigns": 52,
            "notification_preferences": {
                "critical_alerts": "immediate",
                "warning_alerts": "batched_hourly",
                "info_alerts": "daily_summary"
            },
            "recommendation_preferences": {
                "detail_level": "moderate",
                "risk_tolerance": "balanced",
                "typical_acceptance_rate": 0.71,
                "prefers_explanation_detail": "moderate"
            },
            "historical_performance": {
                "avg_campaign_success_rate": 0.91,
                "recommendations_received_30d": 58,
                "recommendations_accepted_30d": 41,
                "avg_response_time_minutes": 15
            },
            "working_hours": {
                "start": "08:00",
                "end": "18:00",
                "timezone": "America/Los_Angeles"
            },
            "out_of_office": False,
            "backup_trader": "trader_echo"
        },
        {
            "trader_id": "trader_echo",
            "email": "echo@example.com",
            "slack_user_id": "UDELTA04",
            "name": "Trader Echo",
            "experience_level": "intermediate",
            "years_experience": 4,
            "active_campaigns": 35,
            "notification_preferences": {
                "critical_alerts": "immediate",
                "warning_alerts": "batched_hourly",
                "info_alerts": "daily_summary"
            },
            "recommendation_preferences": {
                "detail_level": "detailed",
                "risk_tolerance": "aggressive",
                "typical_acceptance_rate": 0.78,
                "prefers_explanation_detail": "detailed"
            },
            "historical_performance": {
                "avg_campaign_success_rate": 0.79,
                "recommendations_received_30d": 38,
                "recommendations_accepted_30d": 30,
                "avg_response_time_minutes": 10
            },
            "working_hours": {
                "start": "09:00",
                "end": "19:00",
                "timezone": "America/Denver"
            },
            "out_of_office": False,
            "backup_trader": "trader_charlie"
        },
        {
            "trader_id": "trader_charlie",
            "email": "charlie@example.com",
            "slack_user_id": "UECHO05",
            "name": "Trader Charlie",
            "experience_level": "intermediate",
            "years_experience": 4,
            "active_campaigns": 33,
            "notification_preferences": {
                "critical_alerts": "immediate",
                "warning_alerts": "batched_hourly",
                "info_alerts": "daily_summary"
            },
            "recommendation_preferences": {
                "detail_level": "moderate",
                "risk_tolerance": "moderate",
                "typical_acceptance_rate": 0.65,
                "prefers_explanation_detail": "moderate"
            },
            "historical_performance": {
                "avg_campaign_success_rate": 0.84,
                "recommendations_received_30d": 41,
                "recommendations_accepted_30d": 27,
                "avg_response_time_minutes": 14
            },
            "working_hours": {
                "start": "08:00",
                "end": "18:00",
                "timezone": "America/Phoenix"
            },
            "out_of_office": False,
            "backup_trader": "trader_alpha"
        }
    ]

    return traders


def generate_stream_events_sample(num_events=1000):
    """
    Generate a sample of raw ad-event records as they would arrive from the bid stream.

    Events represent the lowest-level telemetry: individual impressions, clicks, and
    conversions. In production these would be published to a Kinesis Data Stream and
    aggregated in near-real-time (e.g., by a Flink or Lambda consumer) before being
    rolled up into the campaign metrics stored in DynamoDB.

    Event type distribution: 90% impressions, 8% clicks, 2% conversions.

    Each event contains:
        event_id, event_type, timestamp, campaign_id, user_id,
        device_type, geo, cost, bid_amount, won_auction (impressions only),
        creative_id, viewable + time_in_view_seconds (impressions only)

    Note: Events reference random campaign_ids from a pool of 20 and do NOT
    correspond to the campaigns in campaigns.json. This file is included to
    show the stream schema, not to provide consistent end-to-end data.

    Args:
        num_events: Number of events to generate (default 1000).

    Returns:
        List[dict]: Raw event records.
    """
    events = []

    event_types = ["impression", "click", "conversion"]
    campaign_ids = [str(random.randint(4000, 9999)) for _ in range(20)]

    for i in range(num_events):
        event_type = random.choices(
            event_types,
            weights=[0.90, 0.08, 0.02]  # 90% impressions, 8% clicks, 2% conversions
        )[0]

        campaign_id = random.choice(campaign_ids)
        timestamp = datetime.now() - timedelta(seconds=random.randint(0, 3600))

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "campaign_id": campaign_id,
            "user_id": f"user_{random.randint(10000, 99999)}",
            "device_type": random.choice(["desktop", "mobile", "tablet"]),
            "geo": random.choice(GEO_MARKETS),
            "cost": round(random.uniform(0.50, 10.00), 4) if event_type != "conversion" else None,
            "bid_amount": round(random.uniform(3.00, 8.00), 2),
            "won_auction": random.choice([True, False]) if event_type == "impression" else None,
            "creative_id": f"creative_{random.randint(100, 999)}"
        }

        if event_type == "impression":
            event["viewable"] = random.choice([True, False])
            event["time_in_view_seconds"] = random.randint(0, 30) if event["viewable"] else 0

        events.append(event)

    return events


def generate_recommendation_history():
    """
    Generate 50 historical recommendation records covering the full recommendation lifecycle.

    Each record tracks a recommendation from generation through trader decision to outcome
    measurement. This is the data that would be written by the agent and read back by
    measure-recommendation-outcome Lambda to evaluate prediction accuracy.

    Recommendation statuses: accepted (with outcome), rejected (with reason),
    pending (no decision yet), expired (window passed).

    For accepted recommendations, an outcome block is included comparing predicted
    vs. actual win_rate_improvement and delivery_improvement, plus a trader_feedback
    free-text field.

    In production this table would live in DynamoDB and feed:
    - The agent's session context (pending recommendations not yet acted on)
    - The outcome measurement pipeline (actuals vs. predictions at +4h)
    - Retraining data for the ML diagnosis model

    Returns:
        List[dict]: 50 recommendation history records.
    """
    recommendations = []

    statuses = ["accepted", "rejected", "pending", "expired"]
    recommendation_types = ["bid_adjustment", "targeting_expansion", "creative_refresh", "pacing_adjustment"]

    for i in range(50):
        rec_id = f"rec_{uuid.uuid4().hex[:8]}"
        campaign_id = str(random.randint(4000, 9999))
        timestamp = random_date(start_days_ago=30, end_days_ago=0)

        rec_type = random.choice(recommendation_types)
        status = random.choice(statuses)

        if rec_type == "bid_adjustment":
            current_bid = random.uniform(3.50, 7.00)
            recommended_bid = current_bid * random.uniform(1.15, 1.40)

            recommendation = {
                "type": "bid_adjustment",
                "current_value": round(current_bid, 2),
                "recommended_value": round(recommended_bid, 2),
                "change_pct": round((recommended_bid - current_bid) / current_bid, 3)
            }
        else:
            recommendation = {
                "type": rec_type,
                "description": f"Recommendation for {rec_type}"
            }

        rec = {
            "recommendation_id": rec_id,
            "campaign_id": campaign_id,
            "timestamp": timestamp.isoformat(),
            "recommendation_type": rec_type,
            "recommendation": recommendation,
            "confidence_score": round(random.uniform(0.65, 0.95), 2),
            "status": status,
            "trader_id": random.choice(["trader_alpha", "trader_bravo", "trader_delta"]),
            "generated_by": "agent",
            "rationale": "Analysis of campaign performance and market conditions indicated this change would improve delivery.",
            "expected_outcome": {
                "win_rate_improvement": round(random.uniform(0.05, 0.20), 3),
                "delivery_improvement": round(random.uniform(0.10, 0.30), 3),
                "recovery_time_hours": random.randint(12, 48)
            }
        }

        if status == "accepted":
            rec["accepted_at"] = (timestamp + timedelta(minutes=random.randint(5, 120))).isoformat()
            rec["applied_at"] = (timestamp + timedelta(minutes=random.randint(10, 130))).isoformat()

            # Add outcome
            rec["outcome"] = {
                "measured_at": (timestamp + timedelta(hours=random.randint(24, 72))).isoformat(),
                "actual_win_rate_improvement": round(rec["expected_outcome"]["win_rate_improvement"] * random.uniform(0.80, 1.20), 3),
                "actual_delivery_improvement": round(rec["expected_outcome"]["delivery_improvement"] * random.uniform(0.75, 1.15), 3),
                "outcome_status": random.choice(["as_predicted", "better_than_predicted", "worse_than_predicted"]),
                "trader_feedback": random.choice([
                    "Worked well",
                    "Great suggestion",
                    "Helped recover the campaign",
                    "Good call",
                    ""
                ])
            }
        elif status == "rejected":
            rec["rejected_at"] = (timestamp + timedelta(minutes=random.randint(5, 60))).isoformat()
            rec["rejection_reason"] = random.choice([
                "Client restrictions",
                "Budget constraints",
                "Different approach preferred",
                "Timing not right"
            ])

        recommendations.append(rec)

    return recommendations


def main():
    """
    Generate all seven synthetic data files and write them to the data/ directory.

    Run from the repo root:
        python scripts/generate_synthetic_data.py

    Output files (data/):
        campaigns.json            — 50 active campaigns (includes #4782 and #5201)
        campaign_configs.json     — targeting and bidding config for each campaign
        historical_outcomes.json  — 100 past campaigns with interventions and outcomes
        market_intelligence.json  — 70 geo×industry market snapshots
        trader_profiles.json      — 5 trader profiles
        stream_events_sample.json — 1000 raw impression/click/conversion events
        recommendation_history.json — 50 recommendation lifecycle records

    Prints a delivery-status summary after generation so you can verify the
    distribution of at_risk / on_track / ahead campaigns looks reasonable.
    """

    print("Generating synthetic data for Campaign Optimization Agent POC...")
    print()

    # Generate active campaigns
    print("1. Generating active campaigns...")
    campaigns = generate_active_campaigns(NUM_ACTIVE_CAMPAIGNS)
    with open('prototype-v1/data/campaigns.json', 'w') as f:
        json.dump(campaigns, f, indent=2)
    print(f"   * Generated {len(campaigns)} active campaigns")

    # Generate campaign configurations
    print("2. Generating campaign configurations...")
    configs = generate_campaign_configurations(campaigns)
    with open('prototype-v1/data/campaign_configs.json', 'w') as f:
        json.dump(configs, f, indent=2)
    print(f"   * Generated {len(configs)} campaign configurations")

    # Generate historical outcomes
    print("3. Generating historical campaign outcomes...")
    outcomes = generate_historical_outcomes(NUM_HISTORICAL_CAMPAIGNS)
    with open('prototype-v1/data/historical_outcomes.json', 'w') as f:
        json.dump(outcomes, f, indent=2)
    print(f"   * Generated {len(outcomes)} historical outcomes")

    # Generate market intelligence
    print("4. Generating market intelligence data...")
    markets = generate_market_intelligence()
    with open('prototype-v1/data/market_intelligence.json', 'w') as f:
        json.dump(markets, f, indent=2)
    print(f"   * Generated {len(markets)} market segments")

    # Generate trader profiles
    print("5. Generating trader profiles...")
    traders = generate_trader_profiles()
    with open('prototype-v1/data/trader_profiles.json', 'w') as f:
        json.dump(traders, f, indent=2)
    print(f"   * Generated {len(traders)} trader profiles")

    # Generate stream events sample
    print("6. Generating sample stream events...")
    events = generate_stream_events_sample(1000)
    with open('prototype-v1/data/stream_events_sample.json', 'w') as f:
        json.dump(events, f, indent=2)
    print(f"   * Generated {len(events)} sample events")

    # Generate recommendation history
    print("7. Generating recommendation history...")
    recommendations = generate_recommendation_history()
    with open('prototype-v1/data/recommendation_history.json', 'w') as f:
        json.dump(recommendations, f, indent=2)
    print(f"   * Generated {len(recommendations)} historical recommendations")

    print()
    print("* All synthetic data generated successfully!")
    print()
    print("Data files created in data/:")
    print("  - campaigns.json")
    print("  - campaign_configs.json")
    print("  - historical_outcomes.json")
    print("  - market_intelligence.json")
    print("  - trader_profiles.json")
    print("  - stream_events_sample.json")
    print("  - recommendation_history.json")
    print()

    # Print summary statistics
    at_risk = sum(1 for c in campaigns if c['delivery_pct'] < c['expected_pct'] * 0.80)
    on_track = sum(1 for c in campaigns if 0.90 <= c['delivery_pct'] / c['expected_pct'] <= 1.10)
    ahead = sum(1 for c in campaigns if c['delivery_pct'] > c['expected_pct'] * 1.15)

    print("Campaign Summary:")
    print(f"  - At Risk: {at_risk} ({at_risk/len(campaigns)*100:.1f}%)")
    print(f"  - On Track: {on_track} ({on_track/len(campaigns)*100:.1f}%)")
    print(f"  - Ahead: {ahead} ({ahead/len(campaigns)*100:.1f}%)")
    print()
    print("Special campaigns included:")
    print("  - Campaign #4782 (Honda Spring Sale - Chicago) - At Risk - for Journey 1 demo")
    print("  - Campaign #5201 (Luxury Apartments - Miami) - On Track")
    print("  - Campaign #4201, #3890 (historical) - Successful intervention examples")


if __name__ == "__main__":
    main()
