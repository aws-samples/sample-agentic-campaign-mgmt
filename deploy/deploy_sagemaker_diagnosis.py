# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
deploy-sagemaker.py — Package and deploy the ML diagnosis model to a
SageMaker real-time inference endpoint, then wire the Lambda to use it.

What this script does:
  1. Creates a SageMaker execution IAM role (if not exists)
  2. Creates an S3 bucket for model artifacts (if not exists)
  3. Packages ml/model/ into model.tar.gz and uploads to S3
  4. Creates a SageMaker Model (sklearn container + inference.py)
  5. Creates an EndpointConfig (instance type: ml.t3.medium)
  6. Creates or updates the SageMaker Endpoint (~5 min to become InService)
  7. Sets SAGEMAKER_ENDPOINT_NAME env var on the Lambda function so it
     routes inference calls to the endpoint instead of the bundled pkl

Usage (run from repo root):
  uv run python deploy/deploy_sagemaker_diagnosis.py

Override defaults via environment variables:
  REGION=us-west-2 ENDPOINT_NAME=my-endpoint uv run python deploy/deploy_sagemaker_diagnosis.py
"""
import json
import os
import sys
import tarfile
import time
from pathlib import Path

import boto3

# ── Configuration ──────────────────────────────────────────────────────────────
REGION          = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
ENDPOINT_NAME   = os.environ.get("ENDPOINT_NAME", "campaign-opt-diagnosis")
FUNCTION_NAME   = os.environ.get("FUNCTION_NAME", "campaign-opt-diagnose-ml")
INSTANCE_TYPE   = os.environ.get("SM_INSTANCE_TYPE", "ml.t2.medium")
SM_ROLE_NAME    = "campaign-opt-sagemaker-role"

# Container image to use for the SageMaker endpoint.
#
# Default: XGBoost 1.7 DLC (xgboost + sklearn + numpy pre-installed).
# If your account's SCP blocks cross-account ECR pulls (confirmed for this
# account — even Admin role cannot pull from AWS DLC registries):
#
#   1. Run lambda/build-inference-container.sh in AWS CloudShell (us-west-2)
#      It builds from python:3.11-slim (DockerHub, no ECR restrictions) and
#      pushes to your own ECR account.
#   2. Set CUSTOM_IMAGE_URI to the printed value and re-run this script:
#        CUSTOM_IMAGE_URI=<your-ecr-uri> uv run python lambda/deploy-sagemaker.py
_DLC_IMAGE = (
    f"683313688378.dkr.ecr.{REGION}.amazonaws.com/sagemaker-xgboost:1.7-1"
)
CONTAINER_IMAGE = os.environ.get("CUSTOM_IMAGE_URI", _DLC_IMAGE)

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
MODEL_DIR   = REPO_ROOT / "ml" / "model"
SM_CODE_DIR = REPO_ROOT / "ml" / "sagemaker"
ARTIFACTS   = [
    MODEL_DIR / "diagnosis_model.pkl",
    MODEL_DIR / "label_encoder.pkl",
    MODEL_DIR / "feature_names.json",
]

# ── AWS clients ────────────────────────────────────────────────────────────────
iam    = boto3.client("iam",    region_name=REGION)
s3     = boto3.client("s3",     region_name=REGION)
sm     = boto3.client("sagemaker", region_name=REGION)
lam    = boto3.client("lambda", region_name=REGION)
sts    = boto3.client("sts",    region_name=REGION)


def get_account_id() -> str:
    """Return the AWS account ID for the active credentials."""
    return sts.get_caller_identity()["Account"]


# ── Step 1: SageMaker execution role ──────────────────────────────────────────

def ensure_sagemaker_role(account_id: str) -> str:
    """
    Create the SageMaker execution role if it does not exist.

    The role trusts sagemaker.amazonaws.com and has policies for S3 read
    (model artifacts), ECR (pull container), and CloudWatch Logs.

    Returns:
        ARN of the SageMaker execution role.
    """
    role_exists = True
    try:
        role = iam.get_role(RoleName=SM_ROLE_NAME)
        print(f"  IAM role already exists: {SM_ROLE_NAME}")
    except iam.exceptions.NoSuchEntityException:
        role_exists = False
        print(f"  Creating IAM role: {SM_ROLE_NAME}")
        role = iam.create_role(
        RoleName=SM_ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        }),
        Description="SageMaker execution role for campaign optimization endpoint",
    )

    if not role_exists:
        print(f"  Waiting 15s for IAM propagation...")
        time.sleep(15)

    # Always ensure all required policies are attached (idempotent).
    for policy_arn in [
        "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    ]:
        try:
            iam.attach_role_policy(RoleName=SM_ROLE_NAME, PolicyArn=policy_arn)
        except iam.exceptions.EntityAlreadyExistsException:
            pass  # already attached

    # Always update the inline ECR policy — covers existing roles too.
    iam.put_role_policy(
        RoleName=SM_ROLE_NAME,
        PolicyName="campaign-opt-sagemaker-ecr-inline",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                "Resource": "*",
            }],
        }),
    )

    print("  Waiting 15s for IAM propagation...")
    time.sleep(15)
    return role["Role"]["Arn"]


# ── Step 2: S3 bucket ──────────────────────────────────────────────────────────

def ensure_s3_bucket(bucket: str) -> None:
    """
    Create the S3 bucket used for model artifact storage if it does not exist.

    Args:
        bucket: bucket name to create.
    """
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  S3 bucket already exists: {bucket}")
    except s3.exceptions.ClientError:
        print(f"  Creating S3 bucket: {bucket}")
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )


# ── Step 3: model.tar.gz ───────────────────────────────────────────────────────

def build_and_upload_model(bucket: str, s3_key: str) -> str:
    """
    Package model artifacts and the inference script into model.tar.gz
    and upload to S3.

    SageMaker extracts this tarball into /opt/ml/model/ on the container.
    The inference.py and requirements.txt go into code/ so SageMaker
    finds them automatically.

    Args:
        bucket: S3 bucket name.
        s3_key: S3 key for the uploaded tarball.

    Returns:
        S3 URI of the uploaded model artifact (s3://bucket/key).
    """
    tar_path = REPO_ROOT / "lambda" / "model.tar.gz"
    print(f"  Building {tar_path.name}...")

    with tarfile.open(tar_path, "w:gz") as tar:
        # Model pkl files and feature metadata (extracted to /opt/ml/model/)
        for artifact in ARTIFACTS:
            tar.add(artifact, arcname=artifact.name)

        # Inference script and extra requirements
        # SageMaker looks for code/ inside the tarball for BYOS (bring-your-own-script)
        tar.add(SM_CODE_DIR / "inference.py",    arcname="code/inference.py")
        tar.add(SM_CODE_DIR / "requirements.txt", arcname="code/requirements.txt")

    size_mb = tar_path.stat().st_size / 1024 / 1024
    print(f"  model.tar.gz: {size_mb:.1f} MB")

    print(f"  Uploading to s3://{bucket}/{s3_key} ...")
    s3.upload_file(str(tar_path), bucket, s3_key)
    tar_path.unlink()  # clean up local copy

    return f"s3://{bucket}/{s3_key}"


# ── Step 4–6: SageMaker Model + EndpointConfig + Endpoint ────────────────────

def deploy_endpoint(model_s3_uri: str, role_arn: str) -> None:
    """
    Create or update the SageMaker Model, EndpointConfig, and Endpoint.

    - Model:          points to model.tar.gz on S3 + sklearn container image
    - EndpointConfig: single instance of INSTANCE_TYPE
    - Endpoint:       created if absent; updated in-place if already exists

    Args:
        model_s3_uri: S3 URI of model.tar.gz (output of build_and_upload_model).
        role_arn:     ARN of the SageMaker execution role.
    """
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
            "Image":           CONTAINER_IMAGE,
            "ModelDataUrl":    model_s3_uri,
            "Environment": {
                # Tell the container which script to use as the entry point
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
            "VariantName":         "primary",
            "ModelName":           model_name,
            "InstanceType":        INSTANCE_TYPE,
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

    # Wait for InService
    print("  Waiting for endpoint to become InService (~5 min)...")
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=ENDPOINT_NAME, WaiterConfig={"Delay": 20, "MaxAttempts": 30})
    print(f"  Endpoint is InService: {ENDPOINT_NAME}")


# ── Step 7: Wire Lambda to the endpoint ───────────────────────────────────────

def wire_lambda(endpoint_name: str) -> None:
    """
    Set SAGEMAKER_ENDPOINT_NAME environment variable on the Lambda function.

    Once set, lambda/handler.py's diagnose_campaign_ml.py will route
    inference calls to the SageMaker endpoint instead of the bundled pkl.

    Args:
        endpoint_name: name of the SageMaker endpoint to call.
    """
    try:
        cfg = lam.get_function_configuration(FunctionName=FUNCTION_NAME)
        env = cfg.get("Environment", {}).get("Variables", {})
        env["SAGEMAKER_ENDPOINT_NAME"] = endpoint_name

        lam.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Environment={"Variables": env},
        )
        print(f"  Lambda '{FUNCTION_NAME}' updated: SAGEMAKER_ENDPOINT_NAME={endpoint_name}")
    except lam.exceptions.ResourceNotFoundException:
        print(
            f"  WARNING: Lambda '{FUNCTION_NAME}' not found. "
            "Deploy the Lambda first (bash lambda/deploy-zip.sh), "
            "then re-run this script."
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Orchestrate the full SageMaker deployment."""
    # Validate model artifacts exist before doing anything in AWS
    for artifact in ARTIFACTS:
        if not artifact.exists():
            print(f"ERROR: {artifact} not found.")
            print("Run first: uv run python ml/train_model.py")
            sys.exit(1)

    account_id = get_account_id()
    # Region-scoped bucket — SageMaker requires model artifacts in the same
    # region as the endpoint. Using account+region avoids cross-region failures.
    s3_bucket  = f"campaign-opt-deploy-{account_id}-{REGION}"
    s3_key     = "sagemaker/model.tar.gz"

    print("=== Campaign Opt — SageMaker Deploy ===")
    print(f"Account:  {account_id}")
    print(f"Region:   {REGION}")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Instance: {INSTANCE_TYPE}")
    print()

    print("--- Step 1: IAM role ---")
    role_arn = ensure_sagemaker_role(account_id)
    print(f"  Role ARN: {role_arn}")

    print("\n--- Step 2: S3 bucket ---")
    ensure_s3_bucket(s3_bucket)

    print("\n--- Step 3: Package + upload model ---")
    model_s3_uri = build_and_upload_model(s3_bucket, s3_key)
    print(f"  Model URI: {model_s3_uri}")

    print("\n--- Steps 4–6: SageMaker Model + EndpointConfig + Endpoint ---")
    deploy_endpoint(model_s3_uri, role_arn)

    print("\n--- Step 7: Wire Lambda ---")
    wire_lambda(ENDPOINT_NAME)

    print(f"\n=== Deploy complete: {ENDPOINT_NAME} ===")
    print(f"Test it:")
    print(f"  aws lambda invoke \\")
    print(f"    --function-name {FUNCTION_NAME} \\")
    print(f"    --payload '{{\"function\":\"diagnose_campaign_issue\",\"actionGroup\":\"campaign_analysis\",\"parameters\":[{{\"name\":\"campaign_id\",\"type\":\"string\",\"value\":\"4782\"}}]}}' \\")
    print(f"    --cli-binary-format raw-in-base64-out /tmp/out.json && cat /tmp/out.json")


if __name__ == "__main__":
    main()
