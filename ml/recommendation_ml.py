# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
ML-backed recommendation engine for campaign optimization.

Three-stage pipeline:
    1. XGBoost diagnosis -> identifies the issue type
    2. RandomForest classifier -> selects the best action type
    3. Per-action GradientBoostingRegressor -> predicts the optimal parameter value

Two public entry points:

1. predict_action(features: dict) -> dict
   Runs the classifier. Takes a 19-feature dict, returns action type + confidence.

2. generate_recommendation_ml(campaign_id: str, issue_type: str = None) -> dict
   End-to-end pipeline. Loads data, runs all three stages, returns actionable
   recommendation with ML-predicted parameter values.

Deploy: local pkl fallback or SageMaker endpoint (SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME)
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ml.diagnose_campaign_ml import (
    build_features as build_diagnosis_features,
    predict as predict_diagnosis,
)

_ML_DIR    = Path(__file__).parent
_DATA_DIR  = Path(os.environ.get("DATA_DIR", str(_ML_DIR.parent / "prototype-v1" / "data")))
_MODEL_DIR = _ML_DIR / "model"

# --- Classification features (19) ---
FEATURE_COLS = [
    "bid_to_floor_ratio", "win_rate", "delivery_pct", "expected_pct",
    "delivery_variance", "days_elapsed_pct", "days_remaining",
    "competitor_count", "competitor_change_24h", "demand_supply_ratio",
    "cpm_change_pct", "ctr", "industry_encoded", "geo_encoded",
    "budget_consumed_pct",
    "diagnosed_issue_encoded", "diagnosis_confidence",
    "historical_success_rate", "budget_remaining_pct",
]

# --- Regression features (25 = 19 classification + 6 action-specific) ---
REGRESSION_FEATURE_COLS = FEATURE_COLS + [
    "current_bid", "market_cpm_floor", "market_cpm_p75",
    "budget_daily", "budget_remaining", "impressions_remaining",
]

# Issue type -> encoded integer (must match generate_recommendation_data.py)
ISSUE_TYPES = [
    "bid_too_low", "competitive_pressure", "inventory_shortage",
    "creative_fatigue", "targeting_too_narrow", "pacing_issue",
]
ISSUE_ENCODING = {v: i for i, v in enumerate(ISSUE_TYPES)}

# Action type descriptions for human-readable output
ACTION_DESCRIPTIONS = {
    "bid_adjustment": "Adjust bid to match current market floor and competitive landscape",
    "targeting_expansion": "Broaden geographic or audience targeting to increase reachable inventory",
    "creative_refresh": "Rotate or replace ad creatives to combat audience fatigue",
    "pacing_adjustment": "Modify daily pacing caps to improve delivery velocity",
    "budget_reallocation": "Shift budget across dayparts or channels for better efficiency",
}

# Regression target metadata per action type
ACTION_TARGET_META = {
    "bid_adjustment":       {"unit": "CPM $",      "label": "recommended_bid"},
    "targeting_expansion":  {"unit": "multiplier",  "label": "geo_expansion_factor"},
    "creative_refresh":     {"unit": "fraction",    "label": "creative_rotation_pct"},
    "pacing_adjustment":    {"unit": "multiplier",  "label": "daily_budget_multiplier"},
    "budget_reallocation":  {"unit": "fraction",    "label": "peak_shift_pct"},
}

_CACHE: Dict[str, Any] = {"model": None, "le": None, "regressors": {}}


def _get_model():
    """Load recommendation classifier and label encoder from disk on first call."""
    if _CACHE["model"] is None:
        model_path = _MODEL_DIR / "recommendation_model.pkl"
        le_path    = _MODEL_DIR / "recommendation_encoder.pkl"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Recommendation model not found at {model_path}.\n"
                "Run these steps first:\n"
                "  python ml/generate_recommendation_data.py\n"
                "  python ml/train_recommendation_model.py"
            )
        import joblib
        _CACHE["model"] = joblib.load(model_path)
        _CACHE["le"]    = joblib.load(le_path)
    return _CACHE["model"], _CACHE["le"]


def _get_regressor(action_type: str):
    """Load the per-action GradientBoostingRegressor from disk on first call."""
    if action_type not in _CACHE["regressors"]:
        reg_path = _MODEL_DIR / f"regressor_{action_type}.pkl"
        if not reg_path.exists():
            return None
        import joblib
        _CACHE["regressors"][action_type] = joblib.load(reg_path)
    return _CACHE["regressors"][action_type]


def _invoke_sagemaker(features: Dict[str, Any], endpoint_name: str) -> Dict:
    """Call SageMaker recommendation endpoint instead of local pkl model.

    The shared container inference.py returns generic field names
    (primary_issue, confidence, class_probabilities). We map them to
    the recommendation-specific names expected by callers.
    """
    import boto3

    client = boto3.client("sagemaker-runtime")
    payload = json.dumps({col: features[col] for col in FEATURE_COLS})

    response = client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Accept="application/json",
        Body=payload,
    )
    raw = json.loads(response["Body"].read())

    # Map container's generic field names to recommendation-specific names
    return {
        "recommended_action":  raw["primary_issue"],
        "confidence":          raw["confidence"],
        "class_probabilities": raw["class_probabilities"],
        "features_used":       {k: features[k] for k in FEATURE_COLS},
    }


def predict_action(features: Dict[str, Any]) -> Dict:
    """
    Run Random Forest inference on a feature dictionary.

    Args:
        features: dict with all keys in FEATURE_COLS.

    Returns:
        {
            "recommended_action": "bid_adjustment",
            "confidence": 0.87,
            "class_probabilities": {"bid_adjustment": 0.87, ...},
            "features_used": {<input features>},
        }
    """
    endpoint_name = os.environ.get("SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME")
    if endpoint_name:
        return _invoke_sagemaker(features, endpoint_name)

    model, le = _get_model()

    missing = [col for col in FEATURE_COLS if col not in features]
    if missing:
        raise ValueError(f"Missing required feature(s): {missing}")

    import numpy as np
    features_array = np.array([[features[col] for col in FEATURE_COLS]])
    proba = model.predict_proba(features_array)[0]
    pred_idx = int(np.argmax(proba))

    return {
        "recommended_action":  str(le.classes_[pred_idx]),
        "confidence":          round(float(proba[pred_idx]), 4),
        "class_probabilities": {
            str(cls): round(float(p), 4)
            for cls, p in zip(le.classes_, proba)
        },
        "features_used": {k: features[k] for k in FEATURE_COLS},
    }


def _invoke_sagemaker_regression(
    action_type: str, regression_features: Dict[str, Any], endpoint_name: str
) -> Optional[float]:
    """Call SageMaker recommendation endpoint in regression mode.

    Returns None gracefully if the endpoint doesn't support regression
    (e.g., v2 container without dynamic inference loading).
    """
    import boto3

    client = boto3.client("sagemaker-runtime")
    payload = {col: regression_features[col] for col in REGRESSION_FEATURE_COLS}
    payload["mode"] = "regression"
    payload["action_type"] = action_type

    try:
        response = client.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload),
        )
        raw = json.loads(response["Body"].read())
        return raw.get("predicted_value")
    except Exception:
        # v2 container doesn't support regression mode — fall back to None
        return None


def predict_value(action_type: str, regression_features: Dict[str, Any]) -> Optional[float]:
    """
    Run the per-action GradientBoostingRegressor to predict the optimal parameter value.

    Uses SageMaker endpoint if configured, otherwise falls back to local pkl.

    Args:
        action_type: one of the 5 action types
        regression_features: dict with all 25 regression feature keys

    Returns:
        Predicted value (float), or None if regressor not available.
    """
    endpoint_name = os.environ.get("SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME")
    if endpoint_name:
        return _invoke_sagemaker_regression(action_type, regression_features, endpoint_name)

    regressor = _get_regressor(action_type)
    if regressor is None:
        return None

    import numpy as np
    features_array = np.array([[regression_features[col] for col in REGRESSION_FEATURE_COLS]])
    predicted = float(regressor.predict(features_array)[0])
    return round(predicted, 4)


def build_recommendation_features(
    diagnosis_features: Dict[str, Any],
    diagnosis_result: Dict,
    campaign: Dict,
    historical: list,
) -> Dict[str, Any]:
    """
    Assemble the 19-feature vector for the recommendation classifier.

    Takes the 15 base features from diagnosis, adds the 4 recommendation-
    specific features (diagnosed issue, confidence, historical success rate,
    budget remaining).
    """
    primary_issue = diagnosis_result.get("primary_issue", "bid_too_low")
    if isinstance(primary_issue, dict):
        primary_issue = primary_issue.get("issue_type", "bid_too_low")

    similar_successes = [
        h for h in historical
        if h.get("industry") == campaign.get("industry")
        and h.get("geo") == campaign.get("geo")
        and h.get("outcome", {}).get("outcome_status") == "success"
    ]
    success_rate = (
        len([h for h in similar_successes if h.get("outcome", {}).get("goal_achieved")])
        / max(len(similar_successes), 1)
    )

    budget_total = campaign.get("budget_total", 1)
    budget_spent = budget_total * campaign.get("delivery_pct", 0)
    budget_remaining_pct = max(0, 1.0 - budget_spent / budget_total) if budget_total > 0 else 0

    features = dict(diagnosis_features)
    features.update({
        "diagnosed_issue_encoded":  ISSUE_ENCODING.get(primary_issue, 0),
        "diagnosis_confidence":     diagnosis_result.get("confidence", 0.5),
        "historical_success_rate":  round(success_rate, 4),
        "budget_remaining_pct":     round(budget_remaining_pct, 4),
    })
    return features


def build_regression_features(
    classification_features: Dict[str, Any],
    campaign: Dict,
    market: Dict,
) -> Dict[str, Any]:
    """
    Extend the 19 classification features with 6 regression-specific features
    to produce the 25-feature vector needed by the per-action regressors.
    """
    pricing = market.get("pricing_intelligence", {})
    floor = pricing.get("current_cpm_floor", campaign.get("current_bid", 5.0))
    p75 = pricing.get("cpm_p75", floor * 1.25)

    budget_daily = campaign.get("budget_daily", campaign.get("budget_total", 10000) / max(campaign.get("days_remaining", 14), 1))
    budget_remaining = campaign.get("budget_total", 10000) * classification_features.get("budget_remaining_pct", 0.5)
    impressions_remaining = campaign.get("impressions_remaining", campaign.get("target_impressions", 500000))

    features = dict(classification_features)
    features.update({
        "current_bid":           campaign.get("current_bid", 5.0),
        "market_cpm_floor":      floor,
        "market_cpm_p75":        p75,
        "budget_daily":          budget_daily,
        "budget_remaining":      budget_remaining,
        "impressions_remaining": impressions_remaining,
    })
    return features


def _build_action_details(
    action_type: str,
    confidence: float,
    predicted_value: Optional[float],
    campaign: Dict,
    market: Optional[Dict],
    config: Optional[Dict],
) -> Dict:
    """Build action-specific recommendation details using ML-predicted parameter values."""
    meta = ACTION_TARGET_META.get(action_type, {})
    details = {
        "type": action_type,
        "description": ACTION_DESCRIPTIONS.get(action_type, action_type),
        "ml_predicted_value": predicted_value,
        "value_unit": meta.get("unit", ""),
        "value_label": meta.get("label", ""),
    }

    if action_type == "bid_adjustment":
        current_bid = campaign.get("current_bid", 5.0)
        recommended_bid = predicted_value if predicted_value else current_bid * 1.08
        recommended_bid = round(recommended_bid, 2)
        details.update({
            "action": f"Adjust bid from ${current_bid:.2f} to ${recommended_bid:.2f}",
            "current_state": {"bid": current_bid},
            "recommended_state": {"bid": recommended_bid},
            "change_summary": (
                f"{'Increase' if recommended_bid > current_bid else 'Decrease'} bid by "
                f"{abs((recommended_bid - current_bid) / current_bid):.1%}"
            ),
        })

    elif action_type == "targeting_expansion":
        factor = predicted_value if predicted_value else 1.4
        factor = round(factor, 2)
        details.update({
            "action": f"Expand targeting reach by {factor:.0%} (factor: {factor}x)",
            "current_state": {"geo": campaign.get("geo", ""), "reach_factor": 1.0},
            "recommended_state": {"geo": f"{campaign.get('geo', '')} + adjacent DMAs", "reach_factor": factor},
            "change_summary": f"Broaden geographic reach by {factor:.2f}x to increase available inventory",
        })

    elif action_type == "creative_refresh":
        rotation_pct = predicted_value if predicted_value else 0.5
        rotation_pct = round(min(1.0, max(0.0, rotation_pct)), 2)
        details.update({
            "action": f"Rotate {rotation_pct:.0%} of ad creatives; pause underperforming units",
            "current_state": {"ctr": campaign.get("ctr", 0), "rotation_pct": 0},
            "recommended_state": {"target_rotation_pct": rotation_pct},
            "change_summary": f"Swap {rotation_pct:.0%} of creatives — CTR {campaign.get('ctr', 0):.3%} indicates fatigue",
        })

    elif action_type == "pacing_adjustment":
        multiplier = predicted_value if predicted_value else 1.35
        multiplier = round(multiplier, 2)
        daily_budget = campaign.get("budget_daily", 0)
        new_daily = round(daily_budget * multiplier, 2)
        details.update({
            "action": f"Increase daily pacing cap from ${daily_budget:.2f} to ${new_daily:.2f} ({multiplier}x)",
            "current_state": {"budget_daily": daily_budget, "pacing_multiplier": 1.0},
            "recommended_state": {"budget_daily": new_daily, "pacing_multiplier": multiplier},
            "change_summary": f"Increase daily pacing by {(multiplier - 1):.0%} to recover delivery gap",
        })

    elif action_type == "budget_reallocation":
        shift_pct = predicted_value if predicted_value else 0.20
        shift_pct = round(min(1.0, max(0.0, shift_pct)), 2)
        details.update({
            "action": f"Shift {shift_pct:.0%} of budget from underperforming dayparts to peak hours",
            "current_state": {"distribution": "uniform", "peak_shift_pct": 0},
            "recommended_state": {"distribution": "peak-weighted", "peak_shift_pct": shift_pct},
            "change_summary": f"Reallocate {shift_pct:.0%} of budget to higher-performing time slots",
        })

    return details


def generate_recommendation_ml(
    campaign_id: str, issue_type: str = None
) -> Dict:
    """
    End-to-end ML recommendation pipeline.

    Three-stage pipeline:
        1. Load campaign + market + historical data
        2. XGBoost diagnosis -> issue type
        3. RandomForest classifier -> action type
        4. GradientBoosting regressor -> optimal parameter value
        5. Build action details with ML-predicted values

    Returns the same response schema as the original rule-based function.
    """
    with open(_DATA_DIR / "campaigns.json", encoding="utf-8") as f:
        campaigns = json.load(f)
    with open(_DATA_DIR / "market_intelligence.json", encoding="utf-8") as f:
        markets = json.load(f)
    with open(_DATA_DIR / "campaign_configs.json", encoding="utf-8") as f:
        configs = json.load(f)
    with open(_DATA_DIR / "historical_outcomes.json", encoding="utf-8") as f:
        historical = json.load(f)

    campaign = next((c for c in campaigns if c["campaign_id"] == campaign_id), None)
    config = next((c for c in configs if c["campaign_id"] == campaign_id), None)

    if not campaign or not config:
        return {"error": "Campaign not found", "campaign_id": campaign_id}

    market_key = f"{campaign['industry']}_{campaign['geo'].lower().replace(' ', '_')}_dma"
    market = next((m for m in markets if m["market_segment"] == market_key), None)

    if not market:
        return {"error": f"Market data not found for {campaign['geo']} + {campaign['industry']}"}

    # Stage 1: Run XGBoost diagnosis model
    diagnosis_features = build_diagnosis_features(campaign, market)
    diagnosis_result = predict_diagnosis(diagnosis_features)

    has_issues = campaign["delivery_pct"] < campaign["expected_pct"] * 0.95
    if not has_issues:
        return {
            "campaign_id": campaign_id,
            "recommendation": None,
            "message": "Campaign is performing well, no recommendations needed",
        }

    # Stage 2: Run RandomForest classifier -> action type
    rec_features = build_recommendation_features(
        diagnosis_features, diagnosis_result, campaign, historical
    )
    rec_result = predict_action(rec_features)

    action_type = rec_result["recommended_action"]
    action_confidence = rec_result["confidence"]

    # Stage 3: Run per-action GradientBoosting regressor -> optimal value
    reg_features = build_regression_features(rec_features, campaign, market)
    predicted_value = predict_value(action_type, reg_features)

    # Build detailed recommendation with ML-predicted values
    action_details = _build_action_details(
        action_type, action_confidence, predicted_value, campaign, market, config
    )

    # Historical context
    similar = [
        h for h in historical
        if h["industry"] == campaign["industry"]
        and h["geo"] == campaign["geo"]
        and h["outcome"]["outcome_status"] == "success"
    ][:10]
    success_rate = (
        len([h for h in similar if h["outcome"]["goal_achieved"]])
        / max(len(similar), 1)
    )

    return {
        "recommendation_id": f"rec_{campaign_id}_{action_type}",
        "campaign_id": campaign_id,
        "generated_at": "2026-02-17T09:00:35Z",
        "recommendation": action_details,
        "rationale": {
            "diagnosis": {
                "issue_type": diagnosis_result["primary_issue"],
                "confidence": diagnosis_result["confidence"],
            },
            "ml_action_prediction": {
                "model": "random_forest_v1",
                "recommended_action": action_type,
                "confidence": action_confidence,
                "class_probabilities": rec_result["class_probabilities"],
            },
            "ml_value_prediction": {
                "model": f"gradient_boosting_{action_type}_v1",
                "predicted_value": predicted_value,
                "value_label": ACTION_TARGET_META.get(action_type, {}).get("label", ""),
                "value_unit": ACTION_TARGET_META.get(action_type, {}).get("unit", ""),
            },
            "similar_campaigns": len(similar),
            "historical_success_rate": round(success_rate, 2),
        },
        "expected_outcomes": {
            "delivery_improvement": round(0.15 + action_confidence * 0.15, 2),
            "recovery_time_hours": 24 if action_type != "creative_refresh" else 48,
            "success_probability": round(success_rate * action_confidence, 2),
        },
        "confidence_score": action_confidence,
        "model": "three_stage_pipeline_v1",
    }
