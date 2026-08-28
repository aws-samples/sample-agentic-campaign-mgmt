#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# build-inference-container.sh
#
# Standard pattern for building and pushing a SageMaker inference container
# for this project. Run this in AWS CloudShell (us-west-2).
#
# WHY a custom container (not AWS DLC):
#   This account's SCP blocks all cross-account ECR pulls, including AWS's
#   own Deep Learning Container (DLC) registries (683313688378, 246618743249).
#   Even Admin role cannot pull from those registries. Building from
#   python:3.11-slim (DockerHub) sidesteps the restriction entirely.
#
# HOW SAGEMAKER STARTS THE CONTAINER:
#   SageMaker runs: docker run <image> serve
#   This passes "serve" as the CMD override. The container must have an
#   executable named "serve" in PATH. We install it at /usr/local/bin/serve
#   so gunicorn starts when SageMaker invokes the container.
#   The Flask app is in wsgi.py (not serve.py) to avoid a naming conflict
#   with the serve executable.
#
# WHEN TO RE-RUN:
#   - Adding a new ML model to the project (new FEATURE_COLS / model type)
#   - Upgrading xgboost, scikit-learn, or numpy versions
#   - Changing the inference server logic (inference.py / wsgi.py)
#   Increment IMAGE_TAG each time (custom-v2, custom-v3, ...) to avoid
#   overwriting a working image that a live endpoint depends on.
#
# HOW TO USE:
#   1. Open AWS Console -> CloudShell, set region to us-west-2
#   2. Paste and run this script
#   3. Copy the printed CUSTOM_IMAGE_URI
#   4. On your laptop:
#        CUSTOM_IMAGE_URI=<value> uv run python deploy/deploy_sagemaker_diagnosis.py

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-west-2}"
REPO_NAME="campaign-opt-xgboost-inference"
IMAGE_TAG="v3"                  # ← v3: dynamic inference loading (loads code/inference.py from model.tar.gz)

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
TARGET="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

echo "=== Campaign Opt — Build SageMaker Inference Container ==="
echo "Target: ${TARGET}"
echo ""

mkdir -p ~/campaign-opt-sm && cd ~/campaign-opt-sm

# ── inference.py ───────────────────────────────────────────────────────────────
# Model-agnostic inference script (v2): reads feature_names.json from the model
# directory at startup. Works for both the diagnosis XGBoost and recommendation
# Random Forest models — the same container image serves both endpoints.
cat > inference.py << 'PYEOF'
import json
import os

import joblib
import numpy as np

# Loaded from feature_names.json at container startup (model-agnostic).
_FEATURE_COLS = None


def model_fn(model_dir):
    """Load model artifacts once at container startup.

    Reads feature_names.json to discover the feature column order,
    making this script work for any sklearn-compatible model that
    ships a feature_names.json alongside its pkl files.
    """
    global _FEATURE_COLS

    model = joblib.load(os.path.join(model_dir, "diagnosis_model.pkl"))
    le = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))

    feat_path = os.path.join(model_dir, "feature_names.json")
    with open(feat_path, encoding="utf-8") as f:
        _FEATURE_COLS = json.load(f)

    print(f"Model loaded. Classes: {list(le.classes_)}")
    print(f"Features ({len(_FEATURE_COLS)}): {_FEATURE_COLS}")

    return {"model": model, "le": le, "feature_cols": _FEATURE_COLS}


def input_fn(body, content_type="application/json"):
    """Deserialize JSON request body to a feature dict."""
    return json.loads(body)


def predict_fn(data, artifacts):
    """Run classifier inference and return classification result."""
    model, le = artifacts["model"], artifacts["le"]
    feature_cols = artifacts.get("feature_cols", _FEATURE_COLS)
    X = np.array([[data[c] for c in feature_cols]])
    proba = model.predict_proba(X)[0]
    idx = int(np.argmax(proba))
    return {
        "primary_issue": str(le.classes_[idx]),
        "confidence": round(float(proba[idx]), 4),
        "class_probabilities": {
            str(c): round(float(p), 4)
            for c, p in zip(le.classes_, proba)
        },
    }


def output_fn(prediction, accept="application/json"):
    """Serialize prediction result to JSON."""
    return json.dumps(prediction), "application/json"
PYEOF

# ── wsgi.py ────────────────────────────────────────────────────────────────────
# Minimal Flask app implementing the SageMaker inference protocol.
# Named wsgi.py (not serve.py) to avoid conflict with the /usr/local/bin/serve
# executable that SageMaker calls via: docker run <image> serve
#
# v3 enhancement: dynamically loads code/inference.py from the model directory
# (/opt/ml/model/code/inference.py) if it exists. This lets each model.tar.gz
# ship its own inference logic (e.g., recommendation endpoint with regression
# support) while the diagnosis endpoint continues to use the baked-in inference.py.
#
# SageMaker protocol:
#   GET  /ping        — health check (called before routing traffic)
#   POST /invocations — inference endpoint
cat > wsgi.py << 'PYEOF'
import importlib.util
import os
import sys

from flask import Flask, request, Response

# v3: Try to load code/inference.py from model directory first.
# This lets each endpoint ship its own inference logic in model.tar.gz.
MODEL_DIR = "/opt/ml/model"
MODEL_INFERENCE = os.path.join(MODEL_DIR, "code", "inference.py")

if os.path.exists(MODEL_INFERENCE):
    spec = importlib.util.spec_from_file_location("inference", MODEL_INFERENCE)
    inference = importlib.util.module_from_spec(spec)
    sys.modules["inference"] = inference
    spec.loader.exec_module(inference)
    print(f"[wsgi] Loaded model-specific inference from {MODEL_INFERENCE}")
else:
    import inference
    print(f"[wsgi] Using baked-in inference.py")

app = Flask(__name__)
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = inference.model_fn(MODEL_DIR)
    return _model


@app.route("/ping", methods=["GET"])
def ping():
    """SageMaker health check — return 200 when model is ready."""
    return Response("", status=200)


@app.route("/invocations", methods=["POST"])
def invocations():
    """SageMaker inference endpoint."""
    content_type = request.content_type or "application/json"
    input_data = inference.input_fn(request.data.decode("utf-8"), content_type)
    prediction = inference.predict_fn(input_data, _get_model())
    body, mime = inference.output_fn(prediction, "application/json")
    return Response(body, status=200, mimetype=mime)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
PYEOF

# ── Dockerfile ────────────────────────────────────────────────────────────────
# Uses python:3.11-slim from DockerHub (public, no ECR auth required).
# This avoids the cross-account ECR SCP restriction that blocks AWS DLC images.
#
# KEY: installs /usr/local/bin/serve as an executable script.
# SageMaker starts containers with: docker run <image> serve
# That passes "serve" as the command, overriding CMD. The serve script
# launches gunicorn with the wsgi:app Flask application.
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

RUN pip install --no-cache-dir \
    xgboost \
    scikit-learn \
    numpy \
    joblib \
    flask \
    gunicorn

WORKDIR /opt/program
COPY inference.py wsgi.py ./
ENV PYTHONPATH=/opt/program
EXPOSE 8080

# Install the "serve" executable that SageMaker calls via:
#   docker run <image> serve
# gunicorn serves the Flask wsgi:app; 1 worker keeps the model singleton simple.
RUN printf '#!/bin/bash\nexec gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 60 wsgi:app\n' \
    > /usr/local/bin/serve && chmod +x /usr/local/bin/serve

CMD ["/usr/local/bin/serve"]
EOF

# ── Build ──────────────────────────────────────────────────────────────────────
echo "--- Building container (pulls python:3.11-slim from DockerHub) ---"
docker build -t "${REPO_NAME}:${IMAGE_TAG}" .

# ── Push to ECR ───────────────────────────────────────────────────────────────
echo ""
echo "--- Pushing to ECR ---"
aws ecr create-repository --repository-name "${REPO_NAME}" --region "${REGION}" \
    2>/dev/null && echo "Created ECR repo: ${REPO_NAME}" || echo "ECR repo already exists"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin \
    "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

docker tag "${REPO_NAME}:${IMAGE_TAG}" "${TARGET}"
docker push "${TARGET}"

echo ""
echo "=== Done ==="
echo ""
echo "Now run on your laptop to deploy BOTH endpoints with the v3 container:"
echo ""
echo "  \$env:CUSTOM_IMAGE_URI=\"${TARGET}\""
echo "  uv run python deploy/deploy_sagemaker_diagnosis.py              # diagnosis (XGBoost)"
echo "  uv run python deploy/deploy_sagemaker_recommendation.py       # recommendation (Random Forest)"
echo ""
