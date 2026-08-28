# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
SageMaker inference script for the campaign diagnosis XGBoost model.

This file is uploaded to SageMaker as part of the model package and provides
the four hooks that the SageMaker sklearn container calls during inference:

  model_fn   — called once at container startup to load model artifacts
  input_fn   — called per request to deserialize the incoming payload
  predict_fn — called per request to run inference
  output_fn  — called per request to serialize the prediction result

Invoked by: lambda/handler.py via sagemaker-runtime.invoke_endpoint()
            (when SAGEMAKER_ENDPOINT_NAME env var is set on the Lambda)

Container: sagemaker-scikit-learn (sklearn + numpy pre-installed)
Extra deps: xgboost, joblib  (installed via requirements.txt in this directory)
"""
import json
import os

import joblib
import numpy as np


# Feature column order must match the training pipeline in ml/train_model.py.
# Loaded from feature_names.json at startup to ensure consistency.
_FEATURE_COLS = None


def model_fn(model_dir: str) -> dict:
    """
    Load model artifacts from the SageMaker model directory.

    Called once when the container starts. SageMaker extracts model.tar.gz
    into model_dir before calling this function.

    Args:
        model_dir: path where SageMaker extracted model.tar.gz contents.
                   Expected files: diagnosis_model.pkl, label_encoder.pkl,
                   feature_names.json

    Returns:
        dict with keys "model", "le", "feature_cols" for use in predict_fn.
    """
    global _FEATURE_COLS

    model = joblib.load(os.path.join(model_dir, "diagnosis_model.pkl"))
    le = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))

    with open(os.path.join(model_dir, "feature_names.json"), encoding="utf-8") as f:
        feature_cols = json.load(f)

    _FEATURE_COLS = feature_cols

    print(f"Model loaded. Classes: {list(le.classes_)}")
    print(f"Features ({len(feature_cols)}): {feature_cols}")

    return {"model": model, "le": le, "feature_cols": feature_cols}


def input_fn(request_body: str, content_type: str = "application/json") -> dict:
    """
    Deserialize the inference request payload.

    Args:
        request_body: raw request body string from the HTTP POST.
        content_type: MIME type of the request (must be application/json).

    Returns:
        Feature dictionary with all keys from FEATURE_COLS.

    Raises:
        ValueError if content_type is not application/json.
    """
    if content_type != "application/json":
        raise ValueError(
            f"Unsupported content type: {content_type}. Use application/json."
        )
    return json.loads(request_body)


def predict_fn(input_data: dict, model_artifacts: dict) -> dict:
    """
    Run XGBoost inference on the feature dictionary.

    Args:
        input_data:      feature dict from input_fn.
        model_artifacts: dict returned by model_fn (model, le, feature_cols).

    Returns:
        dict with primary_issue, confidence, and class_probabilities.

    Raises:
        ValueError if any required feature key is missing from input_data.
    """
    model = model_artifacts["model"]
    le = model_artifacts["le"]
    feature_cols = model_artifacts["feature_cols"]

    missing = [col for col in feature_cols if col not in input_data]
    if missing:
        raise ValueError(
            f"Missing required feature(s): {missing}. "
            f"All required: {feature_cols}"
        )

    features_array = np.array([[input_data[col] for col in feature_cols]])
    proba = model.predict_proba(features_array)[0]
    pred_idx = int(np.argmax(proba))

    return {
        "primary_issue": str(le.classes_[pred_idx]),
        "confidence": round(float(proba[pred_idx]), 4),
        "class_probabilities": {
            str(cls): round(float(p), 4)
            for cls, p in zip(le.classes_, proba)
        },
    }


def output_fn(prediction: dict, accept: str = "application/json") -> tuple:
    """
    Serialize the prediction result for the HTTP response.

    Args:
        prediction: dict returned by predict_fn.
        accept:     requested response MIME type (must be application/json).

    Returns:
        Tuple of (serialized_body, content_type).

    Raises:
        ValueError if accept type is not application/json.
    """
    if accept != "application/json":
        raise ValueError(
            f"Unsupported accept type: {accept}. Use application/json."
        )
    return json.dumps(prediction), "application/json"
