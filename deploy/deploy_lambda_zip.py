# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
deploy-zip.py - Deploy the ML diagnosis Lambda as a zip package.

No Docker, no Git Bash, no zip.exe required. Uses boto3 and Python's
built-in zipfile module. Run from repo root with:

    uv run python deploy/deploy_lambda_zip.py

What this script does:
  1. Creates Lambda execution IAM role (if not exists)
  2. Creates S3 bucket for artifacts (if not exists)
  3. Packages function code into function.zip
     (Python code + JSON data only — no .pkl model files;
      ML inference runs on SageMaker endpoints, not in Lambda)
  4. Creates or updates the Lambda function
  5. Runs a smoke test

Override defaults via environment variables:
  REGION=us-west-2 FUNCTION_NAME=my-fn uv run python deploy/deploy_lambda_zip.py
"""
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3

# Configuration
REGION        = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
FUNCTION_NAME = os.environ.get("FUNCTION_NAME", "campaign-opt-diagnose-ml")
ROLE_NAME     = "campaign-opt-lambda-role"
RUNTIME       = "python3.11"
TIMEOUT       = 30
MEMORY_MB     = 512

REPO_ROOT = Path(__file__).parent.parent

# Files to include in the Lambda zip: (archive path, source path)
FUNCTION_FILES = [
    ("handler.py",                       REPO_ROOT / "lambda" / "handler.py"),
    ("ml/__init__.py",                   REPO_ROOT / "ml" / "__init__.py"),
    # ML inference modules — call SageMaker endpoints via boto3 (no .pkl files bundled;
    # models live on SageMaker, deployed via deploy_sagemaker_diagnosis.py / deploy_sagemaker_recommendation.py)
    ("ml/diagnose_campaign_ml.py",       REPO_ROOT / "ml" / "diagnose_campaign_ml.py"),
    ("ml/recommendation_ml.py",          REPO_ROOT / "ml" / "recommendation_ml.py"),
    # Data files (simulates DynamoDB / Redis in PoC)
    ("data/campaigns.json",              REPO_ROOT / "data" / "campaigns.json"),
    ("data/campaign_configs.json",       REPO_ROOT / "data" / "campaign_configs.json"),
    ("data/market_intelligence.json",    REPO_ROOT / "data" / "market_intelligence.json"),
    ("data/historical_outcomes.json",    REPO_ROOT / "data" / "historical_outcomes.json"),
    ("data/trader_profiles.json",        REPO_ROOT / "data" / "trader_profiles.json"),
    ("data/recommendation_history.json", REPO_ROOT / "data" / "recommendation_history.json"),
]

# AWS clients
iam = boto3.client("iam",    region_name=REGION)
s3  = boto3.client("s3",     region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
sts = boto3.client("sts",    region_name=REGION)


def get_account_id() -> str:
    return sts.get_caller_identity()["Account"]


def ensure_lambda_role(account_id: str) -> str:
    """
    Create the Lambda execution role if needed, and ensure all required
    policies are attached (idempotent — safe to call on an existing role).
    """
    try:
        role = iam.get_role(RoleName=ROLE_NAME)
        print(f"  IAM role already exists: {ROLE_NAME}")
    except iam.exceptions.NoSuchEntityException:
        print(f"  Creating IAM role: {ROLE_NAME}")
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }],
            }),
            Description="Lambda execution role for campaign optimization",
        )
        print("  Waiting 15s for IAM propagation...")
        time.sleep(15)

    # Always ensure required managed policies are attached (idempotent).
    try:
        iam.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        print("  Attached: AWSLambdaBasicExecutionRole")
    except iam.exceptions.EntityAlreadyExistsException:
        pass

    # Least-privilege SageMaker access: InvokeEndpoint only, scoped to campaign-opt-* endpoints.
    sagemaker_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "sagemaker:InvokeEndpoint",
            "Resource": f"arn:aws:sagemaker:{REGION}:*:endpoint/campaign-opt-*",
        }],
    })
    try:
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="SageMakerInvokeEndpointOnly",
            PolicyDocument=sagemaker_policy,
        )
        print("  Attached inline: SageMakerInvokeEndpointOnly (sagemaker:InvokeEndpoint on campaign-opt-*)")
    except Exception as e:
        print(f"  Warning: could not attach SageMaker inline policy: {e}")

    return role["Role"]["Arn"]


def ensure_s3_bucket(bucket: str) -> None:
    """Create the S3 bucket if it does not exist."""
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  S3 bucket already exists: {bucket}")
    except Exception:
        print(f"  Creating S3 bucket: {bucket}")
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )


def build_zip() -> bytes:
    """
    Package Lambda function files into a zip and return raw bytes.

    No layer required -- the function calls the SageMaker endpoint via
    boto3 (pre-installed in every Lambda runtime).
    """
    zip_path = REPO_ROOT / "lambda" / "function.zip"
    print(f"  Building {zip_path.name}...")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc_name, src_path in FUNCTION_FILES:
            zf.write(src_path, arc_name)

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"  function.zip: {size_mb:.1f} MB")
    return zip_path.read_bytes()


def deploy_function(zip_bytes: bytes, role_arn: str) -> None:
    """Create or update the Lambda function."""
    try:
        lam.get_function(FunctionName=FUNCTION_NAME)
        exists = True
    except lam.exceptions.ResourceNotFoundException:
        exists = False

    if exists:
        print(f"  Updating function code: {FUNCTION_NAME}")
        lam.update_function_code(
            FunctionName=FUNCTION_NAME,
            ZipFile=zip_bytes,
        )
        waiter = lam.get_waiter("function_updated")
        waiter.wait(FunctionName=FUNCTION_NAME)
    else:
        print(f"  Creating function: {FUNCTION_NAME}")
        lam.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime=RUNTIME,
            Handler="handler.lambda_handler",
            Role=role_arn,
            Code={"ZipFile": zip_bytes},
            Timeout=TIMEOUT,
            MemorySize=MEMORY_MB,
            Environment={"Variables": {"DATA_DIR": "data"}},
        )
        waiter = lam.get_waiter("function_active")
        waiter.wait(FunctionName=FUNCTION_NAME)

    print(f"  Function deployed: {FUNCTION_NAME}")


def smoke_test() -> None:
    """Invoke the function with a sample campaign_id and print the result."""
    payload = json.dumps({
        "function": "diagnose_campaign_issue",
        "actionGroup": "campaign_analysis",
        "parameters": [{"name": "campaign_id", "type": "string", "value": "4782"}],
    })
    response = lam.invoke(
        FunctionName=FUNCTION_NAME,
        Payload=payload.encode(),
    )
    result = json.loads(response["Payload"].read())
    body = json.loads(
        result["response"]["functionResponse"]["responseBody"]["TEXT"]["body"]
    )
    print(json.dumps(body, indent=2))


def main() -> None:
    """Orchestrate the full Lambda zip deployment."""
    for _, src in FUNCTION_FILES:
        if not src.exists():
            print(f"ERROR: {src} not found.")
            sys.exit(1)

    account_id = get_account_id()
    s3_bucket  = f"campaign-opt-deploy-{account_id}-{REGION}"

    print("=== Campaign Opt — Lambda Zip Deploy ===")
    print(f"Account:  {account_id}")
    print(f"Region:   {REGION}")
    print(f"Function: {FUNCTION_NAME}")
    print()

    print("--- Step 1: IAM role ---")
    role_arn = ensure_lambda_role(account_id)
    print(f"  Role ARN: {role_arn}")

    print("\n--- Step 2: S3 bucket ---")
    ensure_s3_bucket(s3_bucket)

    print("\n--- Step 3: Package function ---")
    zip_bytes = build_zip()

    print("\n--- Step 4: Deploy Lambda ---")
    deploy_function(zip_bytes, role_arn)

    print("\n--- Step 5: Smoke test ---")
    try:
        smoke_test()
        print("\n  Smoke test passed — SageMaker endpoints are wired and responding.")
    except Exception as exc:
        print(f"\n  Smoke test failed: {exc}")
        print("  This is expected on first deploy. Wire the SageMaker endpoints next:")
        print("    uv run python deploy/deploy_sagemaker_diagnosis.py")
        print("    uv run python deploy/deploy_sagemaker_recommendation.py")

    print(f"\n=== Deploy complete: {FUNCTION_NAME} ===")


if __name__ == "__main__":
    main()
