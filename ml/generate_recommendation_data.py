# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Generate synthetic labeled training data for the campaign recommendation models.

Two datasets are generated:
1. Classification data — action type labels (used by RandomForestClassifier)
2. Regression data — per-action optimal parameter values (used by per-action
   GradientBoostingRegressors)

The regression targets are action-type-specific:
    bid_adjustment        → recommended_bid ($)
    targeting_expansion   → geo_expansion_factor (multiplier, e.g. 1.4 = 40% broader)
    creative_refresh      → creative_rotation_pct (fraction, e.g. 0.6 = swap 60%)
    pacing_adjustment     → daily_budget_multiplier (e.g. 1.35 = +35%)
    budget_reallocation   → peak_shift_pct (fraction, e.g. 0.25 = shift 25% to peak)

Run:
    python ml/generate_recommendation_data.py

Output:
    ml/data/recommendation_training_data.csv      (classification)
    ml/data/recommendation_regression_data.csv     (regression — includes target values)
"""
import csv
import random
from pathlib import Path
from typing import Dict, List

# --- Action types (labels) ---------------------------------------------------
ACTION_TYPES = [
    "bid_adjustment",
    "targeting_expansion",
    "creative_refresh",
    "pacing_adjustment",
    "budget_reallocation",
]

# --- Issue types from the diagnosis model ------------------------------------
ISSUE_TYPES = [
    "bid_too_low",
    "competitive_pressure",
    "inventory_shortage",
    "creative_fatigue",
    "targeting_too_narrow",
    "pacing_issue",
]
ISSUE_ENCODING = {v: i for i, v in enumerate(ISSUE_TYPES)}

# --- Reuse the same industry/geo encodings as diagnosis ----------------------
INDUSTRIES = [
    "automotive", "retail", "financial", "healthcare",
    "travel", "entertainment", "food_beverage",
]
GEO_MARKETS = [
    "Chicago", "New York", "Los Angeles", "Miami", "Dallas",
    "Atlanta", "Phoenix", "Denver", "Seattle", "Boston",
]
INDUSTRY_ENCODING = {v: i for i, v in enumerate(INDUSTRIES)}
GEO_ENCODING = {v: i for i, v in enumerate(GEO_MARKETS)}

# --- Configuration -----------------------------------------------------------
SAMPLES_PER_CLASS = 250   # 1250 total rows, balanced across 5 action types
RANDOM_SEED = 123


def _generate_row(action_type: str) -> Dict:
    """
    One synthetic training example for the given action type.

    Generates both the classification features AND the regression target value.
    The regression target is computed from the feature profile using domain
    knowledge about what optimal interventions look like.
    """
    industry = random.choice(INDUSTRIES)
    geo = random.choice(GEO_MARKETS)
    days_total = random.choice([7, 10, 14, 21, 30])

    if action_type == "bid_adjustment":
        diagnosed_issue = random.choice(["bid_too_low", "competitive_pressure"])
        bid_to_floor_ratio = random.uniform(0.60, 1.00)
        win_rate = random.uniform(0.03, 0.15)
        delivery_variance = random.uniform(-0.40, -0.10)
        days_elapsed_pct = random.uniform(0.20, 0.75)
        competitor_count = random.randint(8, 22)
        competitor_change = random.randint(0, 6)
        demand_supply_ratio = random.uniform(1.0, 2.5)
        cpm_change_pct = random.uniform(0.00, 0.15)
        ctr = random.uniform(0.004, 0.009)
        diagnosis_confidence = random.uniform(0.70, 0.96)
        historical_success_rate = random.uniform(0.60, 0.90)
        budget_remaining_pct = random.uniform(0.30, 0.80)
        # Regression-specific features
        current_bid = random.uniform(3.00, 6.00)
        market_cpm_floor = current_bid / bid_to_floor_ratio
        market_cpm_p75 = market_cpm_floor * random.uniform(1.15, 1.40)
        budget_daily = random.uniform(1000, 5000)
        budget_remaining = budget_daily * days_total * budget_remaining_pct
        impressions_remaining = random.randint(100000, 800000)

        # Regression target: optimal bid
        # Domain logic: floor + competitive buffer (5-12%) scaled by urgency
        urgency = min(1.0, abs(delivery_variance) * 2)
        buffer_pct = 0.05 + urgency * 0.07
        recommended_bid = round(market_cpm_floor * (1 + buffer_pct), 2)
        # Clamp to not exceed p75
        recommended_bid = min(recommended_bid, market_cpm_p75 * 0.95)
        # Add noise
        recommended_bid = round(recommended_bid * random.uniform(0.97, 1.03), 2)
        target_value = recommended_bid

    elif action_type == "targeting_expansion":
        diagnosed_issue = random.choice(["targeting_too_narrow", "inventory_shortage"])
        bid_to_floor_ratio = random.uniform(1.00, 1.30)
        win_rate = random.uniform(0.08, 0.20)
        delivery_variance = random.uniform(-0.35, -0.08)
        days_elapsed_pct = random.uniform(0.15, 0.65)
        competitor_count = random.randint(4, 16)
        competitor_change = random.randint(-2, 3)
        demand_supply_ratio = random.uniform(1.5, 3.5)
        cpm_change_pct = random.uniform(-0.02, 0.10)
        ctr = random.uniform(0.005, 0.011)
        diagnosis_confidence = random.uniform(0.65, 0.92)
        historical_success_rate = random.uniform(0.50, 0.80)
        budget_remaining_pct = random.uniform(0.35, 0.85)
        current_bid = random.uniform(4.00, 8.00)
        market_cpm_floor = current_bid / bid_to_floor_ratio
        market_cpm_p75 = market_cpm_floor * random.uniform(1.15, 1.40)
        budget_daily = random.uniform(1000, 5000)
        budget_remaining = budget_daily * days_total * budget_remaining_pct
        impressions_remaining = random.randint(150000, 900000)

        # Regression target: geo expansion factor (1.0 = no change, 2.0 = double reach)
        # More expansion needed when demand/supply is high and delivery gap is large
        base_expansion = 1.2 + abs(delivery_variance) * 0.8
        base_expansion += (demand_supply_ratio - 1.5) * 0.15
        target_value = round(min(2.5, max(1.1, base_expansion * random.uniform(0.92, 1.08))), 2)

    elif action_type == "creative_refresh":
        diagnosed_issue = "creative_fatigue"
        bid_to_floor_ratio = random.uniform(1.05, 1.35)
        win_rate = random.uniform(0.22, 0.38)
        delivery_variance = random.uniform(-0.20, -0.02)
        days_elapsed_pct = random.uniform(0.55, 0.92)
        competitor_count = random.randint(5, 18)
        competitor_change = random.randint(-2, 2)
        demand_supply_ratio = random.uniform(0.7, 1.5)
        cpm_change_pct = random.uniform(-0.03, 0.05)
        ctr = random.uniform(0.001, 0.005)
        diagnosis_confidence = random.uniform(0.72, 0.95)
        historical_success_rate = random.uniform(0.55, 0.85)
        budget_remaining_pct = random.uniform(0.10, 0.50)
        current_bid = random.uniform(4.00, 8.00)
        market_cpm_floor = current_bid / bid_to_floor_ratio
        market_cpm_p75 = market_cpm_floor * random.uniform(1.15, 1.40)
        budget_daily = random.uniform(1000, 5000)
        budget_remaining = budget_daily * days_total * budget_remaining_pct
        impressions_remaining = random.randint(50000, 500000)

        # Regression target: creative rotation % (0.3-0.8 of creatives to swap)
        # More rotation when CTR is lower and flight is further along
        ctr_severity = max(0, (0.005 - ctr) / 0.005)  # 0=fine, 1=very bad
        target_value = round(min(0.85, max(0.25, 0.35 + ctr_severity * 0.3 + days_elapsed_pct * 0.15)) * random.uniform(0.92, 1.08), 2)

    elif action_type == "pacing_adjustment":
        diagnosed_issue = "pacing_issue"
        bid_to_floor_ratio = random.uniform(1.05, 1.30)
        win_rate = random.uniform(0.22, 0.38)
        delivery_variance = random.uniform(-0.45, -0.18)
        days_elapsed_pct = random.uniform(0.08, 0.40)
        competitor_count = random.randint(5, 16)
        competitor_change = random.randint(-1, 3)
        demand_supply_ratio = random.uniform(0.9, 1.8)
        cpm_change_pct = random.uniform(-0.02, 0.08)
        ctr = random.uniform(0.005, 0.010)
        diagnosis_confidence = random.uniform(0.68, 0.93)
        historical_success_rate = random.uniform(0.65, 0.88)
        budget_remaining_pct = random.uniform(0.65, 0.95)
        current_bid = random.uniform(4.00, 8.00)
        market_cpm_floor = current_bid / bid_to_floor_ratio
        market_cpm_p75 = market_cpm_floor * random.uniform(1.15, 1.40)
        budget_daily = random.uniform(1000, 5000)
        budget_remaining = budget_daily * days_total * budget_remaining_pct
        impressions_remaining = random.randint(200000, 900000)

        # Regression target: daily budget multiplier (1.1-1.8)
        # More aggressive pacing when delivery gap is larger and more time remains
        gap_severity = min(1.0, abs(delivery_variance) / 0.40)
        time_buffer = 1.0 - days_elapsed_pct  # more room = more aggressive
        target_value = round(min(1.8, max(1.1, 1.15 + gap_severity * 0.35 + time_buffer * 0.15)) * random.uniform(0.95, 1.05), 2)

    elif action_type == "budget_reallocation":
        diagnosed_issue = random.choice(ISSUE_TYPES)
        bid_to_floor_ratio = random.uniform(0.90, 1.20)
        win_rate = random.uniform(0.12, 0.28)
        delivery_variance = random.uniform(-0.20, -0.03)
        days_elapsed_pct = random.uniform(0.30, 0.70)
        competitor_count = random.randint(6, 16)
        competitor_change = random.randint(-1, 3)
        demand_supply_ratio = random.uniform(0.9, 1.6)
        cpm_change_pct = random.uniform(-0.03, 0.06)
        ctr = random.uniform(0.004, 0.009)
        diagnosis_confidence = random.uniform(0.50, 0.75)
        historical_success_rate = random.uniform(0.45, 0.70)
        budget_remaining_pct = random.uniform(0.40, 0.75)
        current_bid = random.uniform(3.50, 7.00)
        market_cpm_floor = current_bid / bid_to_floor_ratio
        market_cpm_p75 = market_cpm_floor * random.uniform(1.15, 1.40)
        budget_daily = random.uniform(1000, 5000)
        budget_remaining = budget_daily * days_total * budget_remaining_pct
        impressions_remaining = random.randint(100000, 600000)

        # Regression target: peak shift % (0.10-0.40 of budget to shift to peak hours)
        # More shift when delivery gap is moderate and budget is available
        target_value = round(min(0.40, max(0.10, 0.15 + abs(delivery_variance) * 0.5 + budget_remaining_pct * 0.1)) * random.uniform(0.90, 1.10), 2)

    else:
        raise ValueError(f"Unknown action_type: {action_type}")

    # Derive dependent features
    expected_pct = random.uniform(0.20, 0.80)
    delivery_pct = max(0.01, expected_pct + delivery_variance)
    days_remaining = max(1, int(days_total * (1 - days_elapsed_pct)))
    budget_consumed_pct = min(1.0, max(0.0, delivery_pct * random.uniform(0.90, 1.10)))

    return {
        # --- 15 base features (same as diagnosis model) ---
        "bid_to_floor_ratio":    round(bid_to_floor_ratio, 4),
        "win_rate":              round(win_rate, 4),
        "delivery_pct":          round(delivery_pct, 4),
        "expected_pct":          round(expected_pct, 4),
        "delivery_variance":     round(delivery_variance, 4),
        "days_elapsed_pct":      round(days_elapsed_pct, 4),
        "days_remaining":        days_remaining,
        "competitor_count":      competitor_count,
        "competitor_change_24h": competitor_change,
        "demand_supply_ratio":   round(demand_supply_ratio, 4),
        "cpm_change_pct":        round(cpm_change_pct, 4),
        "ctr":                   round(ctr, 6),
        "industry_encoded":      INDUSTRY_ENCODING[industry],
        "geo_encoded":           GEO_ENCODING[geo],
        "budget_consumed_pct":   round(budget_consumed_pct, 4),
        # --- Classification features (4 extras) ---
        "diagnosed_issue_encoded":  ISSUE_ENCODING[diagnosed_issue],
        "diagnosis_confidence":     round(diagnosis_confidence, 4),
        "historical_success_rate":  round(historical_success_rate, 4),
        "budget_remaining_pct":     round(budget_remaining_pct, 4),
        # --- Regression features (6 extras) ---
        "current_bid":           round(current_bid, 2),
        "market_cpm_floor":      round(market_cpm_floor, 2),
        "market_cpm_p75":        round(market_cpm_p75, 2),
        "budget_daily":          round(budget_daily, 2),
        "budget_remaining":      round(budget_remaining, 2),
        "impressions_remaining": impressions_remaining,
        # --- Labels ---
        "action_type":           action_type,
        "target_value":          round(target_value, 4),
    }


def generate_training_data(samples_per_class: int = SAMPLES_PER_CLASS) -> List[Dict]:
    """Generate a balanced, shuffled dataset of labeled recommendation examples."""
    rows = []
    for action_type in ACTION_TYPES:
        for _ in range(samples_per_class):
            rows.append(_generate_row(action_type))
    random.shuffle(rows)
    return rows


def main():
    random.seed(RANDOM_SEED)

    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    rows = generate_training_data()
    fieldnames = list(rows[0].keys())

    # Write classification dataset (excludes regression-specific features and target_value)
    classification_cols = [c for c in fieldnames if c not in [
        "current_bid", "market_cpm_floor", "market_cpm_p75",
        "budget_daily", "budget_remaining", "impressions_remaining",
        "target_value",
    ]]
    cls_path = output_dir / "recommendation_training_data.csv"
    with open(cls_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=classification_cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in classification_cols})

    # Write regression dataset (all features + target_value)
    reg_path = output_dir / "recommendation_regression_data.csv"
    with open(reg_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} training examples")
    print(f"  Classification -> {cls_path}")
    print(f"  Regression     -> {reg_path}")

    from collections import Counter
    counts = Counter(r["action_type"] for r in rows)
    for action, count in sorted(counts.items()):
        print(f"  {action}: {count}")

    # Show regression target stats per action type
    print("\nRegression target stats:")
    for action in ACTION_TYPES:
        vals = [r["target_value"] for r in rows if r["action_type"] == action]
        print(f"  {action:25s}  min={min(vals):.2f}  max={max(vals):.2f}  mean={sum(vals)/len(vals):.2f}")


if __name__ == "__main__":
    main()
