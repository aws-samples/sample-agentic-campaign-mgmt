# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Train the campaign recommendation models:

1. RandomForestClassifier — classifies the optimal action type (5 classes)
2. Per-action GradientBoostingRegressors — predicts the optimal parameter
   value for each action type

Model choice rationale:
    - RandomForest for classification: ensemble method, distinct from XGBoost
      used for diagnosis, good with mixed features
    - GradientBoosting for regression: learns non-linear relationships between
      market conditions and optimal intervention values, handles small datasets
      well (250 rows per action)

Reads:
    ml/data/recommendation_training_data.csv      (classification)
    ml/data/recommendation_regression_data.csv     (regression)

Writes:
    ml/model/recommendation_model.pkl              — RandomForestClassifier
    ml/model/recommendation_encoder.pkl            — LabelEncoder
    ml/model/recommendation_features.json          — classification feature cols
    ml/model/regressor_bid_adjustment.pkl           — GBR for bid $ prediction
    ml/model/regressor_targeting_expansion.pkl      — GBR for geo expansion factor
    ml/model/regressor_creative_refresh.pkl         — GBR for creative rotation %
    ml/model/regressor_pacing_adjustment.pkl        — GBR for daily budget multiplier
    ml/model/regressor_budget_reallocation.pkl      — GBR for peak shift %
    ml/model/regression_features.json               — regression feature cols

Run:
    python ml/train_recommendation_model.py
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# --- Classification features (19) ---
CLASSIFICATION_FEATURES = [
    "bid_to_floor_ratio", "win_rate", "delivery_pct", "expected_pct",
    "delivery_variance", "days_elapsed_pct", "days_remaining",
    "competitor_count", "competitor_change_24h", "demand_supply_ratio",
    "cpm_change_pct", "ctr", "industry_encoded", "geo_encoded",
    "budget_consumed_pct",
    "diagnosed_issue_encoded", "diagnosis_confidence",
    "historical_success_rate", "budget_remaining_pct",
]

# --- Regression features (25 = 19 classification + 6 action-specific) ---
REGRESSION_FEATURES = CLASSIFICATION_FEATURES + [
    "current_bid", "market_cpm_floor", "market_cpm_p75",
    "budget_daily", "budget_remaining", "impressions_remaining",
]

ACTION_TYPES = [
    "bid_adjustment", "targeting_expansion", "creative_refresh",
    "pacing_adjustment", "budget_reallocation",
]

# Regression target metadata per action type
ACTION_TARGET_META = {
    "bid_adjustment":       {"unit": "CPM $",      "description": "optimal bid"},
    "targeting_expansion":  {"unit": "multiplier",  "description": "geo expansion factor"},
    "creative_refresh":     {"unit": "fraction",    "description": "creative rotation %"},
    "pacing_adjustment":    {"unit": "multiplier",  "description": "daily budget multiplier"},
    "budget_reallocation":  {"unit": "fraction",    "description": "peak shift %"},
}


def train_classifier(data_path: Path, model_dir: Path):
    """Train the RandomForest action-type classifier."""
    print("=" * 60)
    print("STAGE 1: Action Type Classifier (RandomForest)")
    print("=" * 60)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows")

    le = LabelEncoder()
    y = le.fit_transform(df["action_type"])
    X = df[CLASSIFICATION_FEATURES]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_split=5,
        min_samples_leaf=2, random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nTest accuracy: {acc:.3f}")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    joblib.dump(model, model_dir / "recommendation_model.pkl")
    joblib.dump(le, model_dir / "recommendation_encoder.pkl")
    with open(model_dir / "recommendation_features.json", "w") as f:
        json.dump(CLASSIFICATION_FEATURES, f, indent=2)

    print(f"Saved classifier -> {model_dir / 'recommendation_model.pkl'}")
    return model, le


def train_regressors(data_path: Path, model_dir: Path):
    """Train one GradientBoostingRegressor per action type."""
    print("\n" + "=" * 60)
    print("STAGE 2: Per-Action Regressors (GradientBoosting)")
    print("=" * 60)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows (regression dataset)")

    results = {}

    for action_type in ACTION_TYPES:
        print(f"\n--- {action_type} ---")
        meta = ACTION_TARGET_META[action_type]

        subset = df[df["action_type"] == action_type]
        print(f"  Rows: {len(subset)}")

        X = subset[REGRESSION_FEATURES]
        y = subset["target_value"]

        print(f"  Target range: {y.min():.3f} — {y.max():.3f} ({meta['unit']})")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42
        )

        reg = GradientBoostingRegressor(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=42,
        )
        reg.fit(X_train, y_train)

        y_pred = reg.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        print(f"  MAE: {mae:.4f} {meta['unit']}")
        print(f"  R²:  {r2:.4f}")

        # Feature importance (top 5)
        importance = sorted(
            zip(REGRESSION_FEATURES, reg.feature_importances_),
            key=lambda x: x[1], reverse=True
        )
        print(f"  Top features:")
        for feat, score in importance[:5]:
            print(f"    {feat:30s}  {score:.4f}")

        model_path = model_dir / f"regressor_{action_type}.pkl"
        joblib.dump(reg, model_path)
        print(f"  Saved -> {model_path}")

        results[action_type] = {"mae": mae, "r2": r2}

    # Save regression feature list
    with open(model_dir / "regression_features.json", "w") as f:
        json.dump(REGRESSION_FEATURES, f, indent=2)

    print(f"\n{'='*60}")
    print("REGRESSION SUMMARY")
    print(f"{'='*60}")
    for action, r in results.items():
        meta = ACTION_TARGET_META[action]
        print(f"  {action:25s}  MAE={r['mae']:.4f} {meta['unit']:12s}  R²={r['r2']:.4f}")

    return results


def main():
    base = Path(__file__).parent
    cls_path = base / "data" / "recommendation_training_data.csv"
    reg_path = base / "data" / "recommendation_regression_data.csv"
    model_dir = base / "model"
    model_dir.mkdir(exist_ok=True)

    if not cls_path.exists():
        print(f"ERROR: {cls_path} not found.")
        print("Run first:  python ml/generate_recommendation_data.py")
        return

    train_classifier(cls_path, model_dir)

    if reg_path.exists():
        train_regressors(reg_path, model_dir)
    else:
        print(f"\nWARNING: {reg_path} not found — skipping regressors.")
        print("Run:  python ml/generate_recommendation_data.py  to regenerate.")


if __name__ == "__main__":
    main()
