# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Generate synthetic labeled training data for the campaign diagnosis XGBoost model.

Each row is a campaign snapshot at diagnosis time. Features come from campaign
metrics + market intelligence. The label is the ground-truth issue type.

Since real labeled data only covers bid_too_low, we generate synthetic examples
for all 6 issue types using domain knowledge about which feature profiles
characterise each issue in programmatic CTV/OTT advertising.

Run:
    python ml/generate_training_data.py

Output:
    ml/data/training_data.csv
"""
import csv
import os
import random
from pathlib import Path
from typing import List, Dict

ISSUE_TYPES = [
    "bid_too_low",
    "competitive_pressure",
    "inventory_shortage",
    "creative_fatigue",
    "targeting_too_narrow",
    "pacing_issue",
]

# Must match diagnose_campaign_ml.py exactly
INDUSTRIES = ["automotive", "retail", "financial", "healthcare", "travel", "entertainment", "food_beverage"]
GEO_MARKETS = ["Chicago", "New York", "Los Angeles", "Miami", "Dallas", "Atlanta", "Phoenix", "Denver", "Seattle", "Boston"]
INDUSTRY_ENCODING = {v: i for i, v in enumerate(INDUSTRIES)}
GEO_ENCODING = {v: i for i, v in enumerate(GEO_MARKETS)}

SAMPLES_PER_CLASS = 200  # 1200 total rows, balanced
RANDOM_SEED = 42


def _generate_row(issue_type: str) -> Dict:
    """
    One synthetic training example for the given issue type.

    Feature distributions encode domain knowledge:
    - bid_too_low:           bid clearly below market floor, win rate suffers
    - competitive_pressure:  bid near floor, many new entrants, floor rising fast
    - inventory_shortage:    bid fine, high demand/supply ratio, not enough impressions available
    - creative_fatigue:      bid fine, win rate fine, but CTR declining late in flight
    - targeting_too_narrow:  bid fine, mediocre win rate, low competition (audience pool is small)
    - pacing_issue:          bid fine, win rate fine, early in flight but badly behind pace
    """
    industry = random.choice(INDUSTRIES)
    geo = random.choice(GEO_MARKETS)
    days_total = random.choice([7, 10, 14, 21, 30])

    if issue_type == "bid_too_low":
        bid_to_floor_ratio   = random.uniform(0.60, 0.90)
        win_rate             = random.uniform(0.03, 0.14)
        delivery_variance    = random.uniform(-0.40, -0.15)
        days_elapsed_pct     = random.uniform(0.20, 0.70)
        competitor_count     = random.randint(5, 15)
        competitor_change    = random.randint(-1, 3)
        demand_supply_ratio  = random.uniform(1.0, 2.0)
        cpm_change_pct       = random.uniform(-0.02, 0.10)
        ctr                  = random.uniform(0.004, 0.009)

    elif issue_type == "competitive_pressure":
        bid_to_floor_ratio   = random.uniform(0.88, 1.05)
        win_rate             = random.uniform(0.05, 0.17)
        delivery_variance    = random.uniform(-0.30, -0.08)
        days_elapsed_pct     = random.uniform(0.20, 0.70)
        competitor_count     = random.randint(15, 25)   # many competitors
        competitor_change    = random.randint(3, 8)     # significant new entrants
        demand_supply_ratio  = random.uniform(1.5, 2.5)
        cpm_change_pct       = random.uniform(0.05, 0.20)  # floor rising fast
        ctr                  = random.uniform(0.004, 0.009)

    elif issue_type == "inventory_shortage":
        bid_to_floor_ratio   = random.uniform(1.05, 1.30)
        win_rate             = random.uniform(0.12, 0.22)
        delivery_variance    = random.uniform(-0.25, -0.05)
        days_elapsed_pct     = random.uniform(0.20, 0.70)
        competitor_count     = random.randint(8, 18)
        competitor_change    = random.randint(0, 3)
        demand_supply_ratio  = random.uniform(2.0, 3.5)  # demand >> supply
        cpm_change_pct       = random.uniform(0.03, 0.15)
        ctr                  = random.uniform(0.005, 0.010)

    elif issue_type == "creative_fatigue":
        bid_to_floor_ratio   = random.uniform(1.05, 1.30)
        win_rate             = random.uniform(0.22, 0.35)
        delivery_variance    = random.uniform(-0.18, -0.03)
        days_elapsed_pct     = random.uniform(0.55, 0.90)  # late in flight
        competitor_count     = random.randint(6, 16)
        competitor_change    = random.randint(-2, 2)
        demand_supply_ratio  = random.uniform(0.8, 1.5)
        cpm_change_pct       = random.uniform(-0.03, 0.05)
        ctr                  = random.uniform(0.002, 0.005)  # distinctly low CTR

    elif issue_type == "targeting_too_narrow":
        bid_to_floor_ratio   = random.uniform(1.05, 1.25)
        win_rate             = random.uniform(0.08, 0.18)
        delivery_variance    = random.uniform(-0.35, -0.10)
        days_elapsed_pct     = random.uniform(0.20, 0.70)
        competitor_count     = random.randint(4, 12)    # low competition
        competitor_change    = random.randint(-2, 2)
        demand_supply_ratio  = random.uniform(0.8, 1.4) # supply exists but audience is narrow
        cpm_change_pct       = random.uniform(-0.02, 0.06)
        ctr                  = random.uniform(0.006, 0.012)  # CTR is fine

    elif issue_type == "pacing_issue":
        bid_to_floor_ratio   = random.uniform(1.05, 1.30)
        win_rate             = random.uniform(0.22, 0.35)
        delivery_variance    = random.uniform(-0.40, -0.20)
        days_elapsed_pct     = random.uniform(0.10, 0.35)  # early in flight
        competitor_count     = random.randint(5, 15)
        competitor_change    = random.randint(-1, 3)
        demand_supply_ratio  = random.uniform(1.0, 1.8)
        cpm_change_pct       = random.uniform(-0.02, 0.08)
        ctr                  = random.uniform(0.005, 0.010)

    else:
        raise ValueError(f"Unknown issue_type: {issue_type}")

    # Derive dependent features
    expected_pct        = random.uniform(0.20, 0.80)
    delivery_pct        = max(0.01, expected_pct + delivery_variance)
    days_remaining      = max(1, int(days_total * (1 - days_elapsed_pct)))
    budget_consumed_pct = min(1.0, max(0.0, delivery_pct * random.uniform(0.90, 1.10)))

    return {
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
        "issue_type":            issue_type,
    }


def generate_training_data(samples_per_class: int = SAMPLES_PER_CLASS) -> List[Dict]:
    """
    Generate a balanced, shuffled dataset of labeled training examples.

    Calls _generate_row() for each issue type, producing an equal number of
    examples per class (balanced dataset). The rows are shuffled so that class
    order does not bias the train/test split in train_model.py.

    Args:
        samples_per_class: Number of examples to generate per issue type (default 200).
                           With 6 classes this yields 1200 total rows by default.

    Returns:
        List[dict]: Shuffled rows, each containing 15 feature columns and
                    an "issue_type" label column.
    """
    rows = []
    for issue_type in ISSUE_TYPES:
        for _ in range(samples_per_class):
            rows.append(_generate_row(issue_type))
    random.shuffle(rows)
    return rows


def main():
    """
    Entry point: generate training data and write it to ml/data/training_data.csv.

    Sets a fixed random seed for reproducibility. Creates the ml/data/ directory
    if it does not exist. Prints a class-count summary after writing so you can
    confirm the dataset is balanced before training.
    """
    random.seed(RANDOM_SEED)

    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "training_data.csv"

    rows = generate_training_data()

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} training examples -> {output_path}")

    from collections import Counter
    counts = Counter(r["issue_type"] for r in rows)
    for issue, count in sorted(counts.items()):
        print(f"  {issue}: {count}")


if __name__ == "__main__":
    main()
