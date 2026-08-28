# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
ML-backed diagnosis engine for campaign issues.

Two public entry points:

1. predict(features: dict) -> dict
   Pure ML inference. Takes a feature dictionary, returns the diagnosed issue.
   No file I/O. Use this for unit tests and exploratory what-if inputs.

2. diagnose_campaign_issue_ml(campaign_id: str) -> dict
   Drop-in replacement for diagnose_campaign_issue() in sample_lambda_function.py.
   Loads campaign + market data from the data/ JSON files, assembles the feature
   dict, and calls predict(). Returns the same response schema as the original.

Requirements:
    pip install xgboost scikit-learn joblib
"""
import json
import os
from pathlib import Path
from typing import Any, Dict

# joblib and numpy are imported lazily inside _get_model() so that Lambda
# can import this module without them installed (SageMaker path uses only boto3).

# --- Paths ---
_ML_DIR    = Path(__file__).parent
_DATA_DIR  = Path(os.environ.get("DATA_DIR", str(_ML_DIR.parent / "prototype-v1" / "data")))
_MODEL_DIR = _ML_DIR / "model"

# --- Encoding maps (must match generate_training_data.py) ---
INDUSTRIES = [
    "automotive", "retail", "financial", "healthcare",
    "travel", "entertainment", "food_beverage",
]
GEO_MARKETS = [
    "Chicago", "New York", "Los Angeles", "Miami", "Dallas",
    "Atlanta", "Phoenix", "Denver", "Seattle", "Boston",
]
INDUSTRY_ENCODING = {v: i for i, v in enumerate(INDUSTRIES)}
GEO_ENCODING      = {v: i for i, v in enumerate(GEO_MARKETS)}

# --- Feature column order (must match train_model.py FEATURE_COLS) ---
FEATURE_COLS = [
    "bid_to_floor_ratio",
    "win_rate",
    "delivery_pct",
    "expected_pct",
    "delivery_variance",
    "days_elapsed_pct",
    "days_remaining",
    "competitor_count",
    "competitor_change_24h",
    "demand_supply_ratio",
    "cpm_change_pct",
    "ctr",
    "industry_encoded",
    "geo_encoded",
    "budget_consumed_pct",
]

# --- Lazy-loaded model cache (avoids globals and module-level constants) ---
_CACHE: Dict[str, Any] = {"model": None, "le": None}


def _get_model():
    """Load model and label encoder from disk on first call; return cached instances."""
    if _CACHE["model"] is None:
        model_path = _MODEL_DIR / "diagnosis_model.pkl"
        le_path    = _MODEL_DIR / "label_encoder.pkl"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}.\n"
                "Run these steps first:\n"
                "  python ml/generate_training_data.py\n"
                "  python ml/train_model.py"
            )
        import joblib
        _CACHE["model"] = joblib.load(model_path)
        _CACHE["le"]    = joblib.load(le_path)
    return _CACHE["model"], _CACHE["le"]


# =============================================================================
# SageMaker remote inference (used when SAGEMAKER_ENDPOINT_NAME is set)
# =============================================================================

def _invoke_sagemaker(features: Dict[str, Any], endpoint_name: str) -> Dict:
    """
    Call a SageMaker real-time endpoint instead of the local pkl model.

    Sends the feature dict as JSON and returns the same response schema
    as the local predict() path so callers see no difference.

    Args:
        features:      feature dict with all FEATURE_COLS keys.
        endpoint_name: SageMaker endpoint name from SAGEMAKER_ENDPOINT_NAME env var.

    Returns:
        dict with primary_issue, confidence, class_probabilities, features_used.
    """
    import boto3  # imported here so boto3 is only required when this path is active

    client = boto3.client("sagemaker-runtime")
    payload = json.dumps({col: features[col] for col in FEATURE_COLS})

    response = client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Accept="application/json",
        Body=payload,
    )
    result = json.loads(response["Body"].read())
    result["features_used"] = {k: features[k] for k in FEATURE_COLS}
    return result


# =============================================================================
# Public API
# =============================================================================

def predict(features: Dict[str, Any]) -> Dict:
    """
    Run ML diagnosis on a hand-crafted feature dictionary.

    Args:
        features: dict with all keys in FEATURE_COLS. Example:
            {
                "bid_to_floor_ratio":    0.78,   # current_bid / cpm_floor
                "win_rate":              0.07,
                "delivery_pct":          0.20,
                "expected_pct":          0.43,
                "delivery_variance":    -0.23,   # delivery_pct - expected_pct
                "days_elapsed_pct":      0.43,   # days_elapsed / days_total
                "days_remaining":        4,
                "competitor_count":      10,
                "competitor_change_24h": 1,
                "demand_supply_ratio":   1.4,
                "cpm_change_pct":        0.03,   # (floor_today - floor_yesterday) / floor_yesterday
                "ctr":                   0.007,
                "industry_encoded":      0,      # 0=automotive, see INDUSTRY_ENCODING
                "geo_encoded":           0,      # 0=Chicago, see GEO_ENCODING
                "budget_consumed_pct":   0.20,
            }

    Returns:
        {
            "primary_issue":       "bid_too_low",
            "confidence":          0.91,
            "class_probabilities": {"bid_too_low": 0.91, "competitive_pressure": 0.04, ...},
            "features_used":       {<the input features>},
        }

    Raises:
        ValueError  if a required feature key is missing
        FileNotFoundError  if the model artifact has not been trained yet
    """
    # If a SageMaker endpoint is configured, delegate inference there.
    # Set SAGEMAKER_ENDPOINT_NAME on the Lambda to enable this path.
    endpoint_name = os.environ.get("SAGEMAKER_ENDPOINT_NAME")
    if endpoint_name:
        return _invoke_sagemaker(features, endpoint_name)

    model, le = _get_model()

    missing = [col for col in FEATURE_COLS if col not in features]
    if missing:
        raise ValueError(
            f"Missing required feature(s): {missing}\n"
            f"All required features: {FEATURE_COLS}"
        )

    import numpy as np
    features_array = np.array([[features[col] for col in FEATURE_COLS]])
    proba = model.predict_proba(features_array)[0]
    pred_idx = int(np.argmax(proba))

    class_probs = {
        str(cls): round(float(p), 4)
        for cls, p in zip(le.classes_, proba)
    }

    return {
        "primary_issue":       str(le.classes_[pred_idx]),
        "confidence":          round(float(proba[pred_idx]), 4),
        "class_probabilities": class_probs,
        "features_used":       {k: features[k] for k in FEATURE_COLS},
    }


def build_features(campaign: Dict, market: Dict) -> Dict[str, Any]:
    """
    Assemble the feature dictionary from raw campaign and market data objects.

    Exposed separately so callers can inspect or override individual features
    before calling predict() — useful for what-if scenarios.
    """
    cpm_floor      = market["pricing_intelligence"]["current_cpm_floor"]
    cpm_floor_prev = market["pricing_intelligence"].get("cpm_floor_24h_ago", cpm_floor)

    elapsed        = campaign["days_elapsed"]
    remaining      = campaign["days_remaining"]
    days_total     = campaign.get("days_total") or (elapsed + remaining)
    days_elapsed_pct  = elapsed / days_total if days_total > 0 else 0.5
    delivery_variance = campaign["delivery_pct"] - campaign["expected_pct"]

    bid_ratio = (
        round(campaign["current_bid"] / cpm_floor, 4) if cpm_floor else 1.0
    )
    cpm_change = (
        round((cpm_floor - cpm_floor_prev) / cpm_floor_prev, 4)
        if cpm_floor_prev else 0.0
    )

    return {
        "bid_to_floor_ratio":    bid_ratio,
        "win_rate":              campaign["win_rate"],
        "delivery_pct":          campaign["delivery_pct"],
        "expected_pct":          campaign["expected_pct"],
        "delivery_variance":     round(delivery_variance, 4),
        "days_elapsed_pct":      round(days_elapsed_pct, 4),
        "days_remaining":        remaining,
        "competitor_count":      market["competitive_landscape"]["active_competitors"],
        "competitor_change_24h": market["competitive_landscape"]["competitor_change_24h"],
        "demand_supply_ratio":   market["inventory_availability"]["demand_supply_ratio"],
        "cpm_change_pct":        cpm_change,
        "ctr":                   campaign["ctr"],
        "industry_encoded":      INDUSTRY_ENCODING.get(campaign.get("industry", ""), 0),
        "geo_encoded":           GEO_ENCODING.get(campaign.get("geo", ""), 0),
        "budget_consumed_pct":   round(min(1.0, campaign["delivery_pct"]), 4),
    }


def diagnose_campaign_issue_ml(campaign_id: str) -> Dict:
    """
    Drop-in replacement for diagnose_campaign_issue() in sample_lambda_function.py.

    Loads campaign and market data from the data/ JSON files, assembles features,
    and calls predict(). Returns the same response schema as the original function.
    """
    with open(_DATA_DIR / "campaigns.json", encoding="utf-8") as f:
        campaigns = json.load(f)
    with open(_DATA_DIR / "market_intelligence.json", encoding="utf-8") as f:
        markets = json.load(f)

    campaign = next((c for c in campaigns if c["campaign_id"] == campaign_id), None)
    if not campaign:
        return {"error": "Campaign not found", "campaign_id": campaign_id}

    market_key = f"{campaign['industry']}_{campaign['geo'].lower().replace(' ', '_')}_dma"
    market = next((m for m in markets if m["market_segment"] == market_key), None)
    if not market:
        return {
            "error": f"Market data not found for {campaign['geo']} + {campaign['industry']}"
        }

    features = build_features(campaign, market)
    result   = predict(features)

    primary    = result["primary_issue"]
    confidence = result["confidence"]
    has_issues = campaign["delivery_pct"] < campaign["expected_pct"] * 0.95

    if has_issues:
        health_score = 30 if confidence > 0.80 else 55
    else:
        health_score = 100

    return {
        "campaign_id":         campaign_id,
        "diagnosis_timestamp": "ml_inference",
        "has_issues":          has_issues,
        "primary_issue": {
            "issue_type":  primary,
            "severity":    "critical" if confidence > 0.80 and has_issues else "high",
            "confidence":  confidence,
            "description": _issue_description(primary, campaign, market),
            "evidence":    features,
        },
        "secondary_issues": [
            {"issue_type": k, "confidence": v}
            for k, v in result["class_probabilities"].items()
            if k != primary and v > 0.10
        ],
        "overall_health_score": health_score,
        "model": "xgboost_v1",
    }


def _issue_description(issue_type: str, campaign: Dict, market: Dict) -> str:
    """Return a human-readable explanation for the diagnosed issue type."""
    pricing   = market["pricing_intelligence"]
    landscape = market["competitive_landscape"]
    inventory = market["inventory_availability"]

    descriptions = {
        "bid_too_low": (
            f"Bid (${campaign['current_bid']:.2f}) is below the market floor "
            f"(${pricing['current_cpm_floor']:.2f}), causing low auction win rate."
        ),
        "competitive_pressure": (
            f"Market competition increased significantly "
            f"({landscape['competitor_change_24h']:+d} competitors in 24h), "
            f"pushing win rate down despite an adequate bid."
        ),
        "inventory_shortage": (
            f"Insufficient inventory in this segment "
            f"(demand/supply ratio: {inventory['demand_supply_ratio']:.1f}x). "
            f"Bid and targeting are not the primary issue."
        ),
        "creative_fatigue": (
            f"CTR ({campaign['ctr']:.3%}) is declining — likely creative saturation "
            f"given campaign is {campaign['days_elapsed']} days into its flight."
        ),
        "targeting_too_narrow": (
            "Targeting parameters are restricting the reachable audience pool. "
            "Win rate is mediocre despite a competitive bid."
        ),
        "pacing_issue": (
            f"Campaign is significantly behind pacing early in the flight "
            f"({campaign['days_elapsed']} of {campaign.get('days_total', '?')} days elapsed). "
            f"Bid and market conditions appear healthy."
        ),
    }
    return descriptions.get(issue_type, f"ML-diagnosed issue: {issue_type}")
