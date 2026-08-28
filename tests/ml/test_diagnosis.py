# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the ML diagnosis engine.

Tests call predict() directly with hand-crafted feature dicts — no JSON files,
no campaign_id lookup, no network calls. Each test asserts the model predicts
the expected issue type for a clearly constructed feature profile.

Run all tests:
    uv run python -m pytest tests/ml/ -v

IMPORTANT: Run these two steps once before running tests:
    uv run python ml/generate_training_data.py
    uv run python ml/train_model.py
"""
import sys
import unittest
from pathlib import Path

# Add the ml/ directory to sys.path so we can import diagnose_campaign_ml
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "ml"))

from diagnose_campaign_ml import predict, build_features, FEATURE_COLS, INDUSTRY_ENCODING, GEO_ENCODING


def _base_features() -> dict:
    """
    A healthy baseline campaign — on track, bid above floor, normal market.
    Tests override specific fields to construct each issue scenario.
    """
    return {
        "bid_to_floor_ratio":    1.15,   # bid 15% above floor — healthy
        "win_rate":              0.28,
        "delivery_pct":          0.42,
        "expected_pct":          0.43,
        "delivery_variance":    -0.01,
        "days_elapsed_pct":      0.43,
        "days_remaining":        4,
        "competitor_count":      10,
        "competitor_change_24h": 0,
        "demand_supply_ratio":   1.2,
        "cpm_change_pct":        0.02,
        "ctr":                   0.007,
        "industry_encoded":      INDUSTRY_ENCODING["automotive"],
        "geo_encoded":           GEO_ENCODING["Chicago"],
        "budget_consumed_pct":   0.41,
    }


class TestPredictOutputShape(unittest.TestCase):
    """The response contract — structure and types, regardless of which issue is diagnosed."""

    def test_returns_primary_issue(self):
        result = predict(_base_features())
        self.assertIn("primary_issue", result)
        self.assertIsInstance(result["primary_issue"], str)

    def test_returns_confidence_float(self):
        result = predict(_base_features())
        self.assertIn("confidence", result)
        self.assertIsInstance(result["confidence"], float)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_returns_all_six_class_probabilities(self):
        result = predict(_base_features())
        expected_classes = {
            "bid_too_low", "competitive_pressure", "inventory_shortage",
            "creative_fatigue", "targeting_too_narrow", "pacing_issue",
        }
        self.assertEqual(set(result["class_probabilities"].keys()), expected_classes)

    def test_probabilities_sum_to_one(self):
        result = predict(_base_features())
        total = sum(result["class_probabilities"].values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_returns_features_used(self):
        result = predict(_base_features())
        self.assertIn("features_used", result)
        self.assertEqual(set(result["features_used"].keys()), set(FEATURE_COLS))

    def test_missing_feature_raises_value_error(self):
        incomplete = {k: 0.5 for k in FEATURE_COLS[:-3]}  # drop last 3
        with self.assertRaises(ValueError) as ctx:
            predict(incomplete)
        self.assertIn("Missing required feature", str(ctx.exception))


class TestIssueClassification(unittest.TestCase):
    """
    One test per issue type. Each test constructs a feature profile that clearly
    represents that issue and asserts the model diagnoses it correctly.

    If a test fails, it prints the full result dict so you can see which class
    the model picked instead and what confidence it had.
    """

    def _assert_diagnosed_as(self, issue_type: str, features: dict):
        result = predict(features)
        self.assertEqual(
            result["primary_issue"], issue_type,
            msg=(
                f"\nExpected: {issue_type}"
                f"\nGot:      {result['primary_issue']} (confidence {result['confidence']:.2f})"
                f"\nAll probabilities: {result['class_probabilities']}"
            )
        )
        self.assertGreater(
            result["confidence"], 0.50,
            msg=f"Confidence too low ({result['confidence']:.2f}) for {issue_type}"
        )

    def test_bid_too_low(self):
        """
        Bid is 0.78x the market floor. Win rate is very low (7%).
        Delivery is 20% against an expected 43% — clearly behind.
        """
        features = _base_features()
        features.update({
            "bid_to_floor_ratio":    0.78,
            "win_rate":              0.07,
            "delivery_pct":          0.20,
            "expected_pct":          0.43,
            "delivery_variance":    -0.23,
            "competitor_count":      10,
            "competitor_change_24h": 1,
            "demand_supply_ratio":   1.4,
            "cpm_change_pct":        0.04,
        })
        self._assert_diagnosed_as("bid_too_low", features)

    def test_competitive_pressure(self):
        """
        Bid is near the floor (97%). Win rate is low despite the near-floor bid.
        6 new competitors entered in 24h; floor rising 12%. Market is heating up.
        """
        features = _base_features()
        features.update({
            "bid_to_floor_ratio":    0.97,
            "win_rate":              0.10,
            "delivery_pct":          0.28,
            "expected_pct":          0.50,
            "delivery_variance":    -0.22,
            "competitor_count":      21,
            "competitor_change_24h": 6,
            "demand_supply_ratio":   2.1,
            "cpm_change_pct":        0.12,
        })
        self._assert_diagnosed_as("competitive_pressure", features)

    def test_inventory_shortage(self):
        """
        Bid is 20% above floor (healthy). Win rate is decent at 17%.
        But demand/supply ratio is 2.8 — not enough impressions in this segment.
        """
        features = _base_features()
        features.update({
            "bid_to_floor_ratio":    1.20,
            "win_rate":              0.17,
            "delivery_pct":          0.30,
            "expected_pct":          0.45,
            "delivery_variance":    -0.15,
            "competitor_count":      12,
            "competitor_change_24h": 2,
            "demand_supply_ratio":   2.8,
            "cpm_change_pct":        0.08,
        })
        self._assert_diagnosed_as("inventory_shortage", features)

    def test_creative_fatigue(self):
        """
        Bid is fine (1.18x). Win rate is good (29%). But CTR is 0.003 — well
        below the 0.007 baseline. Campaign is 75% through its flight.
        """
        features = _base_features()
        features.update({
            "bid_to_floor_ratio":    1.18,
            "win_rate":              0.29,
            "delivery_pct":          0.68,
            "expected_pct":          0.75,
            "delivery_variance":    -0.07,
            "days_elapsed_pct":      0.75,
            "days_remaining":        2,
            "competitor_count":      9,
            "competitor_change_24h": 0,
            "demand_supply_ratio":   1.1,
            "cpm_change_pct":        0.01,
            "ctr":                   0.003,   # distinctly low
        })
        self._assert_diagnosed_as("creative_fatigue", features)

    def test_targeting_too_narrow(self):
        """
        Bid is fine (1.15x). Win rate is mediocre (12%) but competition is low
        (only 7 competitors, no new entrants, demand/supply = 1.1). Supply exists
        but the targeted audience pool is too small to win enough impressions.
        CTR is healthy — the audience responds; there just isn't enough of it.
        """
        features = _base_features()
        features.update({
            "bid_to_floor_ratio":    1.15,
            "win_rate":              0.12,
            "delivery_pct":          0.22,
            "expected_pct":          0.45,
            "delivery_variance":    -0.23,
            "competitor_count":      7,
            "competitor_change_24h": 0,
            "demand_supply_ratio":   1.1,
            "cpm_change_pct":        0.01,
            "ctr":                   0.009,   # fine
        })
        self._assert_diagnosed_as("targeting_too_narrow", features)

    def test_pacing_issue(self):
        """
        Bid is fine (1.20x). Win rate is fine (27%). But the campaign is only
        14% through its flight and already 25 percentage points behind expected.
        Market conditions look normal — pacing/budget throttle is the likely cause.
        """
        features = _base_features()
        features.update({
            "bid_to_floor_ratio":    1.20,
            "win_rate":              0.27,
            "delivery_pct":          0.05,
            "expected_pct":          0.30,
            "delivery_variance":    -0.25,
            "days_elapsed_pct":      0.14,   # only 14% through flight
            "days_remaining":        12,
            "competitor_count":      9,
            "competitor_change_24h": 1,
            "demand_supply_ratio":   1.3,
            "cpm_change_pct":        0.02,
        })
        self._assert_diagnosed_as("pacing_issue", features)


class TestBuildFeatures(unittest.TestCase):
    """Verify that build_features() assembles the correct feature keys from raw data objects."""

    def test_build_features_returns_all_feature_cols(self):
        campaign = {
            "campaign_id":   "4782",
            "industry":      "automotive",
            "geo":           "Chicago",
            "current_bid":   4.20,
            "win_rate":      0.08,
            "delivery_pct":  0.29,
            "expected_pct":  0.43,
            "days_elapsed":  3,
            "days_remaining": 4,
            "days_total":    7,
            "ctr":           0.007,
        }
        market = {
            "pricing_intelligence": {
                "current_cpm_floor":  5.10,
                "cpm_floor_24h_ago":  4.85,
            },
            "competitive_landscape": {
                "active_competitors":  12,
                "competitor_change_24h": 3,
            },
            "inventory_availability": {
                "demand_supply_ratio": 1.8,
            },
        }
        features = build_features(campaign, market)
        self.assertEqual(set(features.keys()), set(FEATURE_COLS))

    def test_build_features_bid_to_floor_ratio(self):
        campaign = {
            "industry": "automotive", "geo": "Chicago",
            "current_bid": 4.20, "win_rate": 0.08,
            "delivery_pct": 0.29, "expected_pct": 0.43,
            "days_elapsed": 3, "days_remaining": 4, "days_total": 7, "ctr": 0.007,
        }
        market = {
            "pricing_intelligence": {"current_cpm_floor": 5.10, "cpm_floor_24h_ago": 4.85},
            "competitive_landscape": {"active_competitors": 12, "competitor_change_24h": 3},
            "inventory_availability": {"demand_supply_ratio": 1.8},
        }
        features = build_features(campaign, market)
        expected_ratio = round(4.20 / 5.10, 4)
        self.assertAlmostEqual(features["bid_to_floor_ratio"], expected_ratio, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
