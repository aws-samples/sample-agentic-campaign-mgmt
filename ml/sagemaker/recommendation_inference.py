# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
SageMaker inference script for the campaign recommendation models.

Supports two modes via the JSON request payload:

  Classification (default):
    Input:  {"bid_to_floor_ratio": ..., "win_rate": ..., ...}   (19 features)
    Output: {"recommended_action": "bid_adjustment", "confidence": 0.87, ...}

  Regression:
    Input:  {"mode": "regression", "action_type": "bid_adjustment",
             "bid_to_floor_ratio": ..., ..., "current_bid": ..., ...}  (25 features)
    Output: {"predicted_value": 5.42, "action_type": "bid_adjustment", ...}

Models loaded at startup:
  - recommendation_model.pkl  (RandomForestClassifier)
  - recommendation_encoder.pkl (LabelEncoder)
  - regressor_*.pkl           (5 GradientBoostingRegressors, one per action type)

Container: custom campaign-opt-inference (sklearn + numpy pre-installed)
Invoked by: lambda/handler.py via sagemaker-runtime.invoke_endpoint()
"""
import json
import os

import joblib
import numpy as np

CLASSIFICATION_FEATURES = [
    "bid_to_floor_ratio", "win_rate", "delivery_pct", "expected_pct",
    "delivery_variance", "days_elapsed_pct", "days_remaining",
    "competitor_count", "competitor_change_24h", "demand_supply_ratio",
    "cpm_change_pct", "ctr", "industry_encoded", "geo_encoded",
    "budget_consumed_pct",
    "diagnosed_issue_encoded", "diagnosis_confidence",
    "historical_success_rate", "budget_remaining_pct",
]

REGRESSION_FEATURES = CLASSIFICATION_FEATURES + [
    "current_bid", "market_cpm_floor", "market_cpm_p75",
    "budget_daily", "budget_remaining", "impressions_remaining",
]

ACTION_TYPES = [
    "bid_adjustment", "targeting_expansion", "creative_refresh",
    "pacing_adjustment", "budget_reallocation",
]


def model_fn(model_dir: str) -> dict:
    """Load all model artifacts at container startup."""
    model = joblib.load(os.path.join(model_dir, "recommendation_model.pkl"))
    le = joblib.load(os.path.join(model_dir, "recommendation_encoder.pkl"))
    print(f"Classifier loaded. Classes: {list(le.classes_)}")

    regressors = {}
    for action_type in ACTION_TYPES:
        path = os.path.join(model_dir, f"regressor_{action_type}.pkl")
        if os.path.exists(path):
            regressors[action_type] = joblib.load(path)
            print(f"Regressor loaded: {action_type}")

    print(f"Total regressors: {len(regressors)}")
    return {"model": model, "le": le, "regressors": regressors}


def input_fn(request_body: str, content_type: str = "application/json") -> dict:
    """Deserialize JSON request body."""
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    return json.loads(request_body)


def predict_fn(input_data: dict, model_artifacts: dict) -> dict:
    """Route to classification or regression based on 'mode' field."""
    mode = input_data.get("mode", "classification")

    if mode == "regression":
        return _predict_regression(input_data, model_artifacts)
    return _predict_classification(input_data, model_artifacts)


def _predict_classification(input_data: dict, model_artifacts: dict) -> dict:
    """Run RandomForest classifier inference."""
    model = model_artifacts["model"]
    le = model_artifacts["le"]

    missing = [col for col in CLASSIFICATION_FEATURES if col not in input_data]
    if missing:
        raise ValueError(f"Missing required feature(s): {missing}")

    features_array = np.array([[input_data[col] for col in CLASSIFICATION_FEATURES]])
    proba = model.predict_proba(features_array)[0]
    pred_idx = int(np.argmax(proba))

    return {
        "mode": "classification",
        "primary_issue": str(le.classes_[pred_idx]),
        "confidence": round(float(proba[pred_idx]), 4),
        "class_probabilities": {
            str(cls): round(float(p), 4)
            for cls, p in zip(le.classes_, proba)
        },
    }


def _predict_regression(input_data: dict, model_artifacts: dict) -> dict:
    """Run per-action GradientBoosting regressor inference."""
    action_type = input_data.get("action_type")
    if not action_type or action_type not in ACTION_TYPES:
        raise ValueError(f"Invalid action_type: {action_type}. Must be one of {ACTION_TYPES}")

    regressors = model_artifacts.get("regressors", {})
    regressor = regressors.get(action_type)
    if regressor is None:
        raise ValueError(f"No regressor loaded for action_type: {action_type}")

    missing = [col for col in REGRESSION_FEATURES if col not in input_data]
    if missing:
        raise ValueError(f"Missing required regression feature(s): {missing}")

    features_array = np.array([[input_data[col] for col in REGRESSION_FEATURES]])
    predicted = float(regressor.predict(features_array)[0])

    return {
        "mode": "regression",
        "action_type": action_type,
        "predicted_value": round(predicted, 4),
    }


def output_fn(prediction: dict, accept: str = "application/json") -> tuple:
    """Serialize prediction result to JSON."""
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps(prediction), "application/json"
