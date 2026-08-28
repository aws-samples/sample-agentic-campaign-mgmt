# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
deploy_gateway.py — Create an AgentCore Gateway and wire the Lambda as an MCP tool.

This script:
  1. Creates (or reuses) an IAM service role for the Gateway
  2. Creates an AgentCore Gateway with IAM authorization
  3. Deploys a Gateway-compatible Lambda function (gateway_handler)
  4. Adds the Lambda as a Gateway target with tool definitions
  5. Saves config to gateway_config.json for agent consumption

Usage:
    uv run python deploy/deploy_gateway.py                # deploy
    uv run python deploy/deploy_gateway.py --status       # check status
    uv run python deploy/deploy_gateway.py --destroy      # tear down

Prerequisites:
    - AWS credentials with bedrock-agentcore, iam, lambda permissions
    - Lambda function campaign-opt-diagnose-ml already deployed (lambda/deploy-zip.py)
"""
import argparse
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ── Configuration ─────────────────────────────────────────────────────────────
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID")
if not ACCOUNT_ID:
    sys.exit("ERROR: Set AWS_ACCOUNT_ID environment variable before running this script.")

GATEWAY_NAME = "campaign-optimization-gateway"
GATEWAY_ROLE_NAME = "AgentCoreGatewayRole-campaign-optimization"
TARGET_NAME = "CampaignTools"

# The existing Lambda deployed by lambda/deploy-zip.py
EXISTING_LAMBDA_NAME = "campaign-opt-diagnose-ml"
# A second Lambda for the Gateway handler (different event format)
GATEWAY_LAMBDA_NAME = "campaign-opt-gateway-tools"
GATEWAY_LAMBDA_ROLE = "campaign-opt-lambda-role"  # reuse existing role
GATEWAY_LAMBDA_RUNTIME = "python3.11"
GATEWAY_LAMBDA_TIMEOUT = 30
GATEWAY_LAMBDA_MEMORY = 512

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "gateway_config.json"

# ── Tool definitions (MCP schema) ────────────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "get_campaign_metrics",
        "description": (
            "Retrieve current performance metrics for a specific campaign "
            "including delivery, engagement, financial, and auction metrics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (e.g. '4782')",
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range: 'current', 'last_24h', 'last_7d'",
                },
            },
            "required": ["campaign_id"],
        },
    },
    {
        "name": "diagnose_campaign_issue",
        "description": (
            "Run ML-powered diagnosis on a campaign to identify issues such as "
            "under-delivery, bid problems, or targeting inefficiencies. Returns "
            "issue type, severity, confidence score, and contributing factors."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID to diagnose (e.g. '4782')",
                },
            },
            "required": ["campaign_id"],
        },
    },
    {
        "name": "generate_recommendation",
        "description": (
            "Generate specific, actionable recommendations to fix campaign "
            "issues. Uses ML diagnosis + market intelligence + historical "
            "outcomes to produce bid adjustments, targeting changes, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The campaign ID (e.g. '4782')",
                },
                "issue_type": {
                    "type": "string",
                    "description": "Optional: specific issue type to address",
                },
            },
            "required": ["campaign_id"],
        },
    },
    {
        "name": "get_market_intelligence",
        "description": (
            "Get current market conditions (CPM floors, competition levels, "
            "inventory availability) for a geo/industry combination or campaign."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "geo": {
                    "type": "string",
                    "description": "Geographic market (e.g. 'Atlanta')",
                },
                "industry": {
                    "type": "string",
                    "description": "Industry vertical (e.g. 'Automotive')",
                },
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign ID (alternative to geo+industry)",
                },
            },
            "required": [],
        },
    },
]


# ── Clients ───────────────────────────────────────────────────────────────────
def _clients():
    return {
        "agentcore": boto3.client("bedrock-agentcore-control", region_name=REGION),
        "iam": boto3.client("iam", region_name=REGION),
        "lambda": boto3.client("lambda", region_name=REGION),
        "sts": boto3.client("sts", region_name=REGION),
    }


# ── Step 1: Gateway service role ─────────────────────────────────────────────
GATEWAY_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "GatewayAssumeRolePolicy",
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": ACCOUNT_ID},
            },
        }
    ],
}


def create_gateway_role(iam):
    """Create or get the Gateway service role."""
    try:
        resp = iam.get_role(RoleName=GATEWAY_ROLE_NAME)
        role_arn = resp["Role"]["Arn"]
        print(f"  Gateway role exists: {role_arn}")
        return role_arn
    except iam.exceptions.NoSuchEntityException:
        pass

    print(f"  Creating Gateway service role: {GATEWAY_ROLE_NAME}")
    resp = iam.create_role(
        RoleName=GATEWAY_ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(GATEWAY_TRUST_POLICY),
        Description="Service role for AgentCore Gateway - Campaign Optimization",
    )
    role_arn = resp["Role"]["Arn"]

    # Attach Lambda invoke permission
    lambda_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{GATEWAY_LAMBDA_NAME}"
    iam.put_role_policy(
        RoleName=GATEWAY_ROLE_NAME,
        PolicyName="GatewayLambdaInvoke",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeCampaignToolsLambda",
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": [lambda_arn],
                }
            ],
        }),
    )

    print(f"  Created role: {role_arn}")
    print("  Waiting 10s for IAM propagation...")
    time.sleep(10)
    return role_arn


# ── Step 2: Deploy Gateway Lambda ────────────────────────────────────────────
GATEWAY_LAMBDA_FILES = [
    # (archive_path, source_path)
    ("gateway_handler.py", REPO_ROOT / "lambda" / "gateway_handler.py"),
    ("handler.py", REPO_ROOT / "lambda" / "handler.py"),
    ("ml/__init__.py", REPO_ROOT / "ml" / "__init__.py"),
    ("ml/diagnose_campaign_ml.py", REPO_ROOT / "ml" / "diagnose_campaign_ml.py"),
    ("ml/recommendation_ml.py", REPO_ROOT / "ml" / "recommendation_ml.py"),
]

# Data files
DATA_FILES = [
    "campaigns.json",
    "campaign_configs.json",
    "market_intelligence.json",
    "historical_outcomes.json",
]

# ML model files
MODEL_DIR = REPO_ROOT / "ml" / "model"


def _build_gateway_lambda_zip() -> bytes:
    """Build the deployment zip for the gateway handler Lambda."""
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Python source files
        for arc_path, src_path in GATEWAY_LAMBDA_FILES:
            if src_path.exists():
                zf.write(src_path, arc_path)
            else:
                print(f"  WARNING: {src_path} not found, skipping")

        # Data files
        for fname in DATA_FILES:
            src = REPO_ROOT / "data" / fname
            if src.exists():
                zf.write(src, f"data/{fname}")

        # ML model files
        if MODEL_DIR.exists():
            for f in MODEL_DIR.iterdir():
                if f.is_file():
                    zf.write(f, f"ml/model/{f.name}")

    return buf.getvalue()


def deploy_gateway_lambda(lam, iam):
    """Deploy or update the Gateway-compatible Lambda function."""
    # Get execution role ARN (reuse existing Lambda role)
    try:
        role_resp = iam.get_role(RoleName=GATEWAY_LAMBDA_ROLE)
        role_arn = role_resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        print(f"  ERROR: Lambda execution role {GATEWAY_LAMBDA_ROLE} not found.")
        print("  Run lambda/deploy-zip.py first to create the role.")
        sys.exit(1)

    zip_bytes = _build_gateway_lambda_zip()
    print(f"  Gateway Lambda zip: {len(zip_bytes):,} bytes")

    try:
        lam.get_function(FunctionName=GATEWAY_LAMBDA_NAME)
        # Update existing
        lam.update_function_code(
            FunctionName=GATEWAY_LAMBDA_NAME,
            ZipFile=zip_bytes,
        )
        print(f"  Updated Lambda: {GATEWAY_LAMBDA_NAME}")
    except lam.exceptions.ResourceNotFoundException:
        # Create new
        lam.create_function(
            FunctionName=GATEWAY_LAMBDA_NAME,
            Runtime=GATEWAY_LAMBDA_RUNTIME,
            Role=role_arn,
            Handler="gateway_handler.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=GATEWAY_LAMBDA_TIMEOUT,
            MemorySize=GATEWAY_LAMBDA_MEMORY,
            Description="Campaign Optimization tools for AgentCore Gateway",
            Environment={"Variables": {"DATA_DIR": "data"}},
        )
        print(f"  Created Lambda: {GATEWAY_LAMBDA_NAME}")
        # Wait for active state
        print("  Waiting for Lambda to become active...")
        waiter = lam.get_waiter("function_active_v2")
        waiter.wait(FunctionName=GATEWAY_LAMBDA_NAME)

    lambda_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{GATEWAY_LAMBDA_NAME}"
    print(f"  Lambda ARN: {lambda_arn}")
    return lambda_arn


# ── Step 3: Create Gateway ───────────────────────────────────────────────────
def create_gateway(agentcore, role_arn):
    """Create the AgentCore Gateway (or return existing)."""
    # Check if gateway already exists
    try:
        resp = agentcore.list_gateways(maxResults=50)
        for gw in resp.get("items", []):
            if gw["name"] == GATEWAY_NAME:
                gw_id = gw["gatewayId"]
                print(f"  Gateway already exists: {gw_id}")
                # Get full details for the URL
                detail = agentcore.get_gateway(gatewayIdentifier=gw_id)
                return {
                    "gatewayId": gw_id,
                    "gatewayUrl": detail.get("gatewayUrl", ""),
                    "gatewayArn": detail.get("gatewayArn", ""),
                    "status": detail.get("status", ""),
                }
    except ClientError as e:
        print(f"  Note: list_gateways error: {e}")

    print(f"  Creating Gateway: {GATEWAY_NAME}")
    resp = agentcore.create_gateway(
        name=GATEWAY_NAME,
        roleArn=role_arn,
        protocolType="MCP",
        authorizerType="AWS_IAM",
        description="Campaign Optimization MCP Gateway - exposes ML diagnosis and analytics tools",
    )

    gw_id = resp["gatewayId"]
    print(f"  Gateway created: {gw_id}")
    print(f"  Status: {resp.get('status', 'CREATING')}")

    # Wait for gateway to become ready
    print("  Waiting for Gateway to become ACTIVE...")
    for _ in range(30):
        detail = agentcore.get_gateway(gatewayIdentifier=gw_id)
        status = detail.get("status", "")
        if status in ("ACTIVE", "READY"):
            break
        if status in ("FAILED", "DELETE_FAILED"):
            print(f"  ERROR: Gateway entered {status} state")
            sys.exit(1)
        time.sleep(5)

    return {
        "gatewayId": gw_id,
        "gatewayUrl": detail.get("gatewayUrl", ""),
        "gatewayArn": detail.get("gatewayArn", ""),
        "status": detail.get("status", ""),
    }


# ── Step 4: Add Lambda target ────────────────────────────────────────────────
def add_lambda_target(agentcore, gateway_id, lambda_arn):
    """Add the Lambda function as a Gateway target with tool definitions."""
    # Check if target already exists
    try:
        resp = agentcore.list_gateway_targets(
            gatewayIdentifier=gateway_id,
            maxResults=50,
        )
        for tgt in resp.get("items", []):
            if tgt["name"] == TARGET_NAME:
                target_id = tgt["targetId"]
                print(f"  Target already exists: {target_id}")
                return target_id
    except ClientError as e:
        print(f"  Note: list_gateway_targets error: {e}")

    print(f"  Adding Lambda target: {TARGET_NAME}")
    resp = agentcore.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=TARGET_NAME,
        targetConfiguration={
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {
                        "inlinePayload": TOOL_DEFINITIONS,
                    },
                }
            }
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    )

    target_id = resp["targetId"]
    print(f"  Target created: {target_id}")

    # Wait for target to be ready
    print("  Waiting for target to sync...")
    for _ in range(20):
        detail = agentcore.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id,
        )
        status = detail.get("status", "")
        if status in ("ACTIVE", "READY"):
            break
        if "FAIL" in status:
            print(f"  ERROR: Target entered {status} state")
            break
        time.sleep(3)

    return target_id


# ── Deploy ────────────────────────────────────────────────────────────────────
def deploy():
    print("=" * 60)
    print("Deploying AgentCore Gateway — Campaign Optimization Tools")
    print("=" * 60)

    clients = _clients()

    print("\n[1/4] Gateway service role")
    role_arn = create_gateway_role(clients["iam"])

    print("\n[2/4] Gateway Lambda function")
    lambda_arn = deploy_gateway_lambda(clients["lambda"], clients["iam"])

    print("\n[3/4] AgentCore Gateway")
    gw = create_gateway(clients["agentcore"], role_arn)

    print("\n[4/4] Lambda target")
    target_id = add_lambda_target(clients["agentcore"], gw["gatewayId"], lambda_arn)

    # Save config
    config = {
        "gateway_id": gw["gatewayId"],
        "gateway_arn": gw.get("gatewayArn", ""),
        "gateway_url": gw["gatewayUrl"],
        "target_id": target_id,
        "target_name": TARGET_NAME,
        "lambda_arn": lambda_arn,
        "region": REGION,
        "auth_type": "AWS_IAM",
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"\nConfig saved to: {CONFIG_FILE}")

    print("\n" + "=" * 60)
    print("Gateway deployed successfully!")
    print(f"  MCP Endpoint: {gw['gatewayUrl']}")
    print(f"  Gateway ID:   {gw['gatewayId']}")
    print(f"  Target:       {TARGET_NAME} ({target_id})")
    print(f"  Auth:         AWS_IAM (use SigV4 signing)")
    print("=" * 60)


# ── Status ────────────────────────────────────────────────────────────────────
def status():
    if not CONFIG_FILE.exists():
        print("No gateway_config.json found. Deploy first.")
        return

    config = json.loads(CONFIG_FILE.read_text())
    clients = _clients()

    print(f"Gateway: {config['gateway_id']}")
    try:
        gw = clients["agentcore"].get_gateway(gatewayIdentifier=config["gateway_id"])
        print(f"  Status:  {gw.get('status', 'UNKNOWN')}")
        print(f"  URL:     {gw.get('gatewayUrl', 'N/A')}")
    except ClientError as e:
        print(f"  Error: {e}")

    print(f"\nTarget: {config.get('target_id', 'N/A')}")
    try:
        tgt = clients["agentcore"].get_gateway_target(
            gatewayIdentifier=config["gateway_id"],
            targetId=config["target_id"],
        )
        print(f"  Status:  {tgt.get('status', 'UNKNOWN')}")
        print(f"  Name:    {tgt.get('name', 'N/A')}")
    except ClientError as e:
        print(f"  Error: {e}")


# ── Destroy ───────────────────────────────────────────────────────────────────
def destroy():
    if not CONFIG_FILE.exists():
        print("No gateway_config.json found. Nothing to destroy.")
        return

    config = json.loads(CONFIG_FILE.read_text())
    clients = _clients()

    # Delete target
    try:
        print(f"Deleting target: {config.get('target_id', 'N/A')}")
        clients["agentcore"].delete_gateway_target(
            gatewayIdentifier=config["gateway_id"],
            targetId=config["target_id"],
        )
        print("  Target deleted.")
    except ClientError as e:
        print(f"  {e}")

    # Delete gateway
    try:
        print(f"Deleting gateway: {config['gateway_id']}")
        clients["agentcore"].delete_gateway(gatewayIdentifier=config["gateway_id"])
        print("  Gateway deleted.")
    except ClientError as e:
        print(f"  {e}")

    # Delete gateway Lambda
    try:
        print(f"Deleting Lambda: {GATEWAY_LAMBDA_NAME}")
        clients["lambda"].delete_function(FunctionName=GATEWAY_LAMBDA_NAME)
        print("  Lambda deleted.")
    except ClientError as e:
        print(f"  {e}")

    # Delete Gateway IAM role
    try:
        print(f"Deleting role: {GATEWAY_ROLE_NAME}")
        clients["iam"].delete_role_policy(
            RoleName=GATEWAY_ROLE_NAME,
            PolicyName="GatewayLambdaInvoke",
        )
        clients["iam"].delete_role(RoleName=GATEWAY_ROLE_NAME)
        print("  Role deleted.")
    except ClientError as e:
        print(f"  {e}")

    CONFIG_FILE.unlink(missing_ok=True)
    print("\nGateway resources destroyed.")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy AgentCore Gateway for campaign tools")
    parser.add_argument("--destroy", action="store_true", help="Tear down all gateway resources")
    parser.add_argument("--status", action="store_true", help="Check gateway status")
    args = parser.parse_args()

    if args.destroy:
        destroy()
    elif args.status:
        status()
    else:
        deploy()
