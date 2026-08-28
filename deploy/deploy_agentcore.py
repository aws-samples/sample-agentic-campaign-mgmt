# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Deploy the Campaign Optimization Agent to Amazon Bedrock AgentCore Runtime.

This script provides a programmatic alternative to the CLI-based deployment
(`agentcore launch`). It uploads a ZIP deployment package to S3 and creates
an AgentCore Runtime using the boto3 SDK.

Prerequisites:
    - AWS credentials configured with appropriate permissions
    - S3 bucket: bedrock-agentcore-code-{ACCOUNT_ID}-{REGION}
    - IAM role: AmazonBedrockAgentCoreSDKRuntime-{REGION}
    - ML model trained: ml/model/diagnosis_model.pkl

Usage:
    uv run python deploy/deploy_agentcore.py                    # deploy
    uv run python deploy/deploy_agentcore.py --destroy          # tear down
    uv run python deploy/deploy_agentcore.py --status           # check status
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_NAME = "campaign-optimization-agent"
REGION = os.environ.get("AWS_REGION", "us-west-2")
PYTHON_RUNTIME = "PYTHON_3_13"
ENTRYPOINT = "agent/runtime.py"


def get_account_id() -> str:
    sts = boto3.client("sts", region_name=REGION)
    return sts.get_caller_identity()["Account"]


def build_deployment_package(output_path: Path) -> Path:
    """Build a ZIP deployment package with agent code, data, and ML model."""
    print("Building deployment package...")

    with tempfile.TemporaryDirectory() as tmpdir:
        staging = Path(tmpdir) / "staging"

        # Copy project files needed at runtime
        dirs_to_copy = ["agent", "data", "ml"]
        for d in dirs_to_copy:
            src = PROJECT_ROOT / d
            if src.exists():
                shutil.copytree(src, staging / d)
                print(f"  Copied {d}/")

        # Install ARM64-compatible dependencies into the package
        print("  Installing ARM64 dependencies via uv...")
        deps_dir = staging / "deps"
        req_file = str(PROJECT_ROOT / "pyproject.toml")
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        subprocess.run(  # nosec B603
            ["uv", "pip", "install",
             "--python-platform", "aarch64-manylinux2014",
             "--python-version", "3.13",
             "--target", str(deps_dir),
             "--only-binary=:all:",
             "-r", req_file],
            check=True,
            cwd=str(PROJECT_ROOT),
        )

        # Create the ZIP
        zip_path = shutil.make_archive(str(output_path.with_suffix("")), "zip", str(staging))
        print(f"  Package: {zip_path} ({Path(zip_path).stat().st_size / 1024 / 1024:.1f} MB)")
        return Path(zip_path)


def upload_to_s3(zip_path: Path, account_id: str) -> str:
    """Upload deployment package to the AgentCore S3 bucket."""
    bucket = f"bedrock-agentcore-code-{account_id}-{REGION}"
    key = f"{AGENT_NAME}/deployment_package.zip"

    print(f"Uploading to s3://{bucket}/{key} ...")
    s3 = boto3.client("s3", region_name=REGION)
    s3.upload_file(
        str(zip_path),
        bucket,
        key,
        ExtraArgs={"ExpectedBucketOwner": account_id},
    )
    print("  Upload complete.")
    return bucket, key


def create_runtime(account_id: str, bucket: str, key: str) -> dict:
    """Create an AgentCore Runtime with the deployment package."""
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    role_arn = f"arn:aws:iam::{account_id}:role/AmazonBedrockAgentCoreSDKRuntime-{REGION}"

    print(f"Creating AgentCore Runtime '{AGENT_NAME}'...")
    response = client.create_agent_runtime(
        agentRuntimeName=AGENT_NAME,
        agentRuntimeArtifact={
            "codeConfiguration": {
                "code": {
                    "s3": {
                        "bucket": bucket,
                        "prefix": key,
                    }
                },
                "runtime": PYTHON_RUNTIME,
                "entryPoint": [ENTRYPOINT],
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
        lifecycleConfiguration={
            "idleRuntimeSessionTimeout": 300,
            "maxLifetime": 1800,
        },
    )
    print(f"  ARN: {response['agentRuntimeArn']}")
    print(f"  Status: {response['status']}")
    return response


def get_status():
    """Check the status of the deployed runtime."""
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    try:
        runtimes = client.list_agent_runtimes()
        for rt in runtimes.get("agentRuntimeSummaries", []):
            if rt["agentRuntimeName"] == AGENT_NAME:
                print(f"Runtime: {rt['agentRuntimeName']}")
                print(f"  ARN:    {rt['agentRuntimeArn']}")
                print(f"  Status: {rt['status']}")
                return rt
        print(f"No runtime found with name '{AGENT_NAME}'")
    except Exception as e:
        print(f"Error checking status: {e}")
    return None


def destroy():
    """Delete the deployed runtime."""
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    rt = get_status()
    if rt:
        print(f"Deleting runtime {rt['agentRuntimeArn']}...")
        client.delete_agent_runtime(agentRuntimeId=rt["agentRuntimeArn"].split("/")[-1])
        print("  Deleted.")


def deploy():
    """Full deployment: build, upload, create runtime."""
    account_id = get_account_id()
    print(f"Account: {account_id}, Region: {REGION}\n")

    output_path = PROJECT_ROOT / "deploy" / "deployment_package.zip"
    zip_path = build_deployment_package(output_path)
    bucket, key = upload_to_s3(zip_path, account_id)
    response = create_runtime(account_id, bucket, key)

    print(f"\nDeployment complete!")
    print(f"Invoke with:")
    print(f'  agentcore invoke \'{{"prompt": "Show me metrics for campaign 4782"}}\'')
    print(f"\nOr programmatically:")
    print(f"  uv run python deploy/invoke_agentcore.py")

    return response


def main():
    parser = argparse.ArgumentParser(description="Deploy Campaign Optimization Agent to AgentCore")
    parser.add_argument("--destroy", action="store_true", help="Delete the deployed runtime")
    parser.add_argument("--status", action="store_true", help="Check deployment status")
    args = parser.parse_args()

    if args.destroy:
        destroy()
    elif args.status:
        get_status()
    else:
        deploy()


if __name__ == "__main__":
    main()
