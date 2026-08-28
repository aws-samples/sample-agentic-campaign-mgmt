# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
deploy-sagemaker-recommendation.py — Package and deploy the recommendation
models to a SageMaker real-time inference endpoint, then wire the Lambda.

This mirrors deploy-sagemaker.py (diagnosis endpoint) but deploys the
recommendation models (classifier + 5 per-action regressors) as a second endpoint.

What this script does:
  1. Reuses the existing SageMaker execution IAM role
  2. Reuses the existing S3 bucket for model artifacts
  3. Packages all recommendation model artifacts into model.tar.gz and uploads to S3
     - recommendation_model.pkl (RandomForest classifier)
     - recommendation_encoder.pkl (LabelEncoder)
     - regressor_*.pkl (5 GradientBoosting regressors)
  4. Creates a SageMaker Model (custom container + recommendation_inference.py)
  5. Creates an EndpointConfig (instance type: ml.t2.medium)
  6. Creates or updates the SageMaker Endpoint (~5 min to become InService)
  7. Sets SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME env var on the Lambda function

Usage (run from repo root):
  uv run python deploy/deploy_sagemaker_recommendation.py

Override defaults:
  ENDPOINT_NAME=my-rec-ep uv run python deploy/deploy_sagemaker_recommendation.py
"""
import json
import os
import sys
import tarfile
import time
from pathlib import Path

import boto3

# ── Configuration ─────────────────────────────────────────────────────────────
REGION          = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
ENDPOINT_NAME   = os.environ.get("ENDPOINT_NAME", "campaign-opt-recommendation")
FUNCTION_NAME   = os.environ.get("FUNCTION_NAME", "campaign-opt-diagnose-ml")
INSTANCE_TYPE   = os.environ.get("SM_INSTANCE_TYPE", "ml.t2.medium")
SM_ROLE_NAME    = "campaign-opt-sagemaker-role"

# Reuse the same custom container as the diagnosis endpoint.
# Must include sklearn + numpy + joblib (Random Forest needs these).
_DLC_IMAGE = (
    f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-xgboost:1.7-1"
)
CONTAINER_IMAGE = os.environ.get("CUSTOM_IMAGE_URI", _DLC_IMAGE)

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
MODEL_DIR   = REPO_ROOT / "ml" / "model"
SM_CODE_DIR = REPO_ROOT / "ml" / "sagemaker"
ARTIFACTS   = [
    MODEL_DIR / "recommendation_model.pkl",
    MODEL_DIR / "recommendation_encoder.pkl",
    MODEL_DIR / "recommendation_features.json",
    # Per-action GradientBoosting regressors
    MODEL_DIR / "regressor_bid_adjustment.pkl",
    MODEL_DIR / "regressor_targeting_expansion.pkl",
    MODEL_DIR / "regressor_creative_refresh.pkl",
    MODEL_DIR / "regressor_pacing_adjustment.pkl",
    MODEL_DIR / "regressor_budget_reallocation.pkl",
    MODEL_DIR / "regression_features.json",
]

# ── AWS clients ───────────────────────────────────────────────────────────────
iam    = boto3.client("iam",    region_name=REGION)
s3     = boto3.client("s3",     region_name=REGION)
sm     = boto3.client("sagemaker", region_name=REGION)
lam    = boto3.client("lambda", region_name=REGION)
sts    = boto3.client("sts",    region_name=REGION)


def get_account_id() -> str:
    return sts.get_caller_identity()["Account"]


def get_role_arn() -> str:
    """Get the existing SageMaker execution role ARN."""
    role = iam.get_role(RoleName=SM_ROLE_NAME)
    return role["Role"]["Arn"]


def build_and_upload_model(bucket: str, s3_key: str) -> str:
    """Package recommendation model artifacts into model.tar.gz and upload to S3.

    Container compatibility:
      - v2 container: baked-in inference.py expects diagnosis_model.pkl,
        label_encoder.pkl, feature_names.json. We rename classifier artifacts
        to match. Regression is not supported (falls back to heuristic values).
      - v3 container: dynamically loads code/inference.py from model dir.
        Our recommendation_inference.py handles both classification + regression.
        Regressor pkls keep their original names.

    The code/inference.py is always included so v3 can pick it up.
    """
    tar_path = REPO_ROOT / "lambda" / "recommendation_model.tar.gz"
    print(f"  Building {tar_path.name}...")

    # Rename classifier artifacts for v2 container compatibility
    RENAME_MAP = {
        "recommendation_model.pkl":      "diagnosis_model.pkl",
        "recommendation_encoder.pkl":    "label_encoder.pkl",
        "recommendation_features.json":  "feature_names.json",
    }

    with tarfile.open(tar_path, "w:gz") as tar:
        for artifact in ARTIFACTS:
            arcname = RENAME_MAP.get(artifact.name, artifact.name)
            tar.add(artifact, arcname=arcname)
            if arcname != artifact.name:
                # Also include with original name for v3 container
                tar.add(artifact, arcname=artifact.name)
        tar.add(
            SM_CODE_DIR / "recommendation_inference.py",
            arcname="code/inference.py",
        )
        tar.add(SM_CODE_DIR / "requirements.txt", arcname="code/requirements.txt")

    size_mb = tar_path.stat().st_size / 1024 / 1024
    print(f"  recommendation_model.tar.gz: {size_mb:.1f} MB")

    print(f"  Uploading to s3://{bucket}/{s3_key} ...")
    s3.upload_file(str(tar_path), bucket, s3_key)
    tar_path.unlink()

    return f"s3://{bucket}/{s3_key}"


def deploy_endpoint(model_s3_uri: str, role_arn: str) -> None:
    """Create or update the SageMaker Model, EndpointConfig, and Endpoint."""
    model_name  = f"{ENDPOINT_NAME}-model"
    config_name = f"{ENDPOINT_NAME}-config"

    # -- Model --
    try:
        sm.delete_model(ModelName=model_name)
        print(f"  Deleted old SageMaker model: {model_name}")
    except sm.exceptions.ClientError:
        pass

    print(f"  Creating SageMaker model: {model_name}")
    print(f"  Container: {CONTAINER_IMAGE}")
    sm.create_model(
        ModelName=model_name,
        ExecutionRoleArn=role_arn,
        PrimaryContainer={
            "Image":        CONTAINER_IMAGE,
            "ModelDataUrl": model_s3_uri,
            "Environment": {
                "SAGEMAKER_PROGRAM":        "inference.py",
                "SAGEMAKER_SUBMIT_DIRECTORY": model_s3_uri,
            },
        },
    )

    # -- EndpointConfig --
    try:
        sm.delete_endpoint_config(EndpointConfigName=config_name)
        print(f"  Deleted old endpoint config: {config_name}")
    except sm.exceptions.ClientError:
        pass

    print(f"  Creating endpoint config: {config_name} ({INSTANCE_TYPE})")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            "VariantName":          "primary",
            "ModelName":            model_name,
            "InstanceType":         INSTANCE_TYPE,
            "InitialInstanceCount": 1,
        }],
    )

    # -- Endpoint --
    existing = None
    try:
        existing = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)["EndpointStatus"]
    except sm.exceptions.ClientError:
        pass

    if existing in ("Failed", None):
        if existing == "Failed":
            print(f"  Deleting failed endpoint: {ENDPOINT_NAME}")
            sm.delete_endpoint(EndpointName=ENDPOINT_NAME)
            print("  Waiting for endpoint deletion...")
            sm.get_waiter("endpoint_deleted").wait(
                EndpointName=ENDPOINT_NAME,
                WaiterConfig={"Delay": 15, "MaxAttempts": 40},
            )
        print(f"  Creating endpoint: {ENDPOINT_NAME}")
        sm.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name,
        )
    else:
        print(f"  Updating endpoint: {ENDPOINT_NAME} (current status: {existing})")
        sm.update_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name,
        )

    print("  Waiting for endpoint to become InService (~5 min)...")
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=ENDPOINT_NAME, WaiterConfig={"Delay": 20, "MaxAttempts": 30})
    print(f"  Endpoint is InService: {ENDPOINT_NAME}")


def wire_lambda(endpoint_name: str) -> None:
    """Set SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME env var on the Lambda."""
    try:
        cfg = lam.get_function_configuration(FunctionName=FUNCTION_NAME)
        env = cfg.get("Environment", {}).get("Variables", {})
        env["SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME"] = endpoint_name

        lam.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Environment={"Variables": env},
        )
        print(f"  Lambda '{FUNCTION_NAME}' updated: SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME={endpoint_name}")
    except lam.exceptions.ResourceNotFoundException:
        print(
            f"  WARNING: Lambda '{FUNCTION_NAME}' not found. "
            "Deploy the Lambda first, then re-run this script."
        )


def main() -> None:
    """Orchestrate the full SageMaker deployment for recommendation model."""
    for artifact in ARTIFACTS:
        if not artifact.exists():
            print(f"ERROR: {artifact} not found.")
            print("Run first:")
            print("  uv run python ml/generate_recommendation_data.py")
            print("  uv run python ml/train_recommendation_model.py")
            sys.exit(1)

    account_id = get_account_id()
    s3_bucket  = f"campaign-opt-deploy-{account_id}-{REGION}"
    s3_key     = "sagemaker/recommendation_model.tar.gz"

    print("=== Campaign Opt — Recommendation Model SageMaker Deploy ===")
    print(f"Account:  {account_id}")
    print(f"Region:   {REGION}")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Instance: {INSTANCE_TYPE}")
    print(f"Model:    RF classifier + 5 GBR regressors (scikit-learn)")
    print()

    print("--- Step 1: Get IAM role ---")
    role_arn = get_role_arn()
    print(f"  Role ARN: {role_arn}")

    print("\n--- Step 2: Package + upload model ---")
    model_s3_uri = build_and_upload_model(s3_bucket, s3_key)
    print(f"  Model URI: {model_s3_uri}")

    print("\n--- Steps 3-5: SageMaker Model + EndpointConfig + Endpoint ---")
    deploy_endpoint(model_s3_uri, role_arn)

    print("\n--- Step 6: Wire Lambda ---")
    wire_lambda(ENDPOINT_NAME)

    print(f"\n=== Deploy complete: {ENDPOINT_NAME} ===")
    print("Test it:")
    print(f"  aws lambda invoke \\")
    print(f"    --function-name {FUNCTION_NAME} \\")
    print(f"    --payload '{{\"function\":\"generate_recommendation\",\"actionGroup\":\"campaign_analysis\",\"parameters\":[{{\"name\":\"campaign_id\",\"type\":\"string\",\"value\":\"4782\"}}]}}' \\")
    print(f"    --cli-binary-format raw-in-base64-out /tmp/rec_out.json && cat /tmp/rec_out.json")


if __name__ == "__main__":
    main()
