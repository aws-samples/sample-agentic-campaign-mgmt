# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
deploy_multi_target_gateway.py — Deploy AgentCore Gateway with 4 different target types.

Demonstrates all supported Gateway target integration patterns through a single
MCP endpoint:

  Target 1: Lambda          → diagnose_campaign_issue   (Gateway invokes Lambda directly)
  Target 2: API Gateway     → get_campaign_metrics      (Gateway calls REST API stage)
  Target 3: OpenAPI Schema  → get_market_intelligence   (Gateway reads spec from S3)
  Target 4: MCP Server      → generate_recommendation   (Gateway proxies to MCP server)

Usage:
    uv run python deploy/deploy_multi_target_gateway.py                # deploy all
    uv run python deploy/deploy_multi_target_gateway.py --status       # check status
    uv run python deploy/deploy_multi_target_gateway.py --destroy      # tear down

Prerequisites:
    - AWS credentials with bedrock-agentcore, iam, lambda, apigateway, s3 permissions
    - ML model trained (ml/model/ exists)
"""
import argparse
import io
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
LAMBDA_ROLE_NAME = "campaign-opt-lambda-role"  # reuse existing role

# Lambda function names — one per target type
LAMBDA_DIAGNOSE = "campaign-opt-diagnose-gw"
LAMBDA_METRICS = "campaign-opt-metrics-api"
LAMBDA_MARKET_INTEL = "campaign-opt-market-intel"
LAMBDA_RECOMMEND = "campaign-opt-recommend-mcp"

# API Gateway
API_GW_NAME = "campaign-opt-metrics"
API_GW_STAGE = "prod"

# S3 for OpenAPI spec
S3_BUCKET_PREFIX = "campaign-opt-deploy-"
OPENAPI_SPEC_KEY = "openapi/market-intelligence.json"

# Gateway target names
TARGET_LAMBDA = "DiagnoseLambda"
TARGET_APIGW = "MetricsAPI"
TARGET_OPENAPI = "MarketIntelOpenAPI"
TARGET_MCP = "RecommendMCP"

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "gateway_multi_config.json"

# ── Clients ───────────────────────────────────────────────────────────────────
_clients_cache = {}


def clients():
    if not _clients_cache:
        _clients_cache.update({
            "agentcore": boto3.client("bedrock-agentcore-control", region_name=REGION),
            "iam": boto3.client("iam", region_name=REGION),
            "lambda": boto3.client("lambda", region_name=REGION),
            "apigateway": boto3.client("apigateway", region_name=REGION),
            "s3": boto3.client("s3", region_name=REGION),
            "sts": boto3.client("sts", region_name=REGION),
        })
    return _clients_cache


# ── Lambda zip builder ────────────────────────────────────────────────────────
# All Lambdas share the same zip (all handlers + data + ML model).
# Each Lambda just uses a different handler entry point.

LAMBDA_SOURCE_FILES = [
    ("handler.py", REPO_ROOT / "lambda" / "handler.py"),
    ("gateway_handler.py", REPO_ROOT / "lambda" / "gateway_handler.py"),
    ("apigw_handler.py", REPO_ROOT / "lambda" / "apigw_handler.py"),
    ("market_intel_handler.py", REPO_ROOT / "lambda" / "market_intel_handler.py"),
    ("mcp_server_handler.py", REPO_ROOT / "lambda" / "mcp_server_handler.py"),
    ("ml/__init__.py", REPO_ROOT / "ml" / "__init__.py"),
    ("ml/diagnose_campaign_ml.py", REPO_ROOT / "ml" / "diagnose_campaign_ml.py"),
]

DATA_FILES = [
    "campaigns.json", "campaign_configs.json",
    "market_intelligence.json", "historical_outcomes.json",
]


def _build_lambda_zip():
    """Build a single deployment zip containing all handlers + data + model."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc_path, src_path in LAMBDA_SOURCE_FILES:
            if src_path.exists():
                zf.write(src_path, arc_path)
            else:
                print(f"  WARNING: {src_path} not found, skipping")
        for fname in DATA_FILES:
            src = REPO_ROOT / "data" / fname
            if src.exists():
                zf.write(src, f"data/{fname}")
        model_dir = REPO_ROOT / "ml" / "model"
        if model_dir.exists():
            for f in model_dir.iterdir():
                if f.is_file():
                    zf.write(f, f"ml/model/{f.name}")
    return buf.getvalue()


# ── Step 1: IAM Roles ────────────────────────────────────────────────────────
GATEWAY_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "GatewayAssumeRole",
        "Effect": "Allow",
        "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
        "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT_ID}},
    }],
}


def ensure_gateway_role(iam):
    """Create or get the Gateway service role with permissions for all target types."""
    try:
        resp = iam.get_role(RoleName=GATEWAY_ROLE_NAME)
        role_arn = resp["Role"]["Arn"]
        print(f"  Gateway role exists: {role_arn}")
    except iam.exceptions.NoSuchEntityException:
        print(f"  Creating Gateway role: {GATEWAY_ROLE_NAME}")
        resp = iam.create_role(
            RoleName=GATEWAY_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(GATEWAY_TRUST_POLICY),
            Description="AgentCore Gateway role — Campaign Optimization (multi-target)",
        )
        role_arn = resp["Role"]["Arn"]
        print(f"  Created: {role_arn}")
        print("  Waiting 10s for IAM propagation...")
        time.sleep(10)

    # Attach inline policy covering Lambda invoke + API Gateway execute + S3 read
    lambda_arns = [
        f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{name}"
        for name in [LAMBDA_DIAGNOSE, LAMBDA_METRICS, LAMBDA_MARKET_INTEL, LAMBDA_RECOMMEND]
    ]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeLambdas",
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": lambda_arns,
            },
            {
                "Sid": "ExecuteAPIGateway",
                "Effect": "Allow",
                "Action": ["execute-api:Invoke"],
                "Resource": [
                    f"arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:*/{API_GW_STAGE}/*"
                ],
            },
            {
                "Sid": "ReadS3Spec",
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [
                    f"arn:aws:s3:::{S3_BUCKET_PREFIX}{ACCOUNT_ID}/{OPENAPI_SPEC_KEY}"
                ],
            },
        ],
    }
    iam.put_role_policy(
        RoleName=GATEWAY_ROLE_NAME,
        PolicyName="GatewayMultiTargetPolicy",
        PolicyDocument=json.dumps(policy),
    )
    return role_arn


# ── Step 2: Deploy Lambda functions ──────────────────────────────────────────
LAMBDA_CONFIGS = [
    {
        "name": LAMBDA_DIAGNOSE,
        "handler": "gateway_handler.lambda_handler",
        "description": "Gateway Lambda target — diagnose_campaign_issue",
    },
    {
        "name": LAMBDA_METRICS,
        "handler": "apigw_handler.lambda_handler",
        "description": "API Gateway backend — get_campaign_metrics",
    },
    {
        "name": LAMBDA_MARKET_INTEL,
        "handler": "market_intel_handler.lambda_handler",
        "description": "OpenAPI backend (Function URL) — get_market_intelligence",
    },
    {
        "name": LAMBDA_RECOMMEND,
        "handler": "mcp_server_handler.lambda_handler",
        "description": "MCP Server (Function URL) — generate_recommendation",
    },
]


def deploy_lambdas(lam, iam):
    """Deploy or update all 4 Lambda functions from a shared zip."""
    try:
        role_resp = iam.get_role(RoleName=LAMBDA_ROLE_NAME)
        role_arn = role_resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        print(f"  ERROR: Lambda role {LAMBDA_ROLE_NAME} not found.")
        print("  Run lambda/deploy-zip.py first to create the role.")
        sys.exit(1)

    zip_bytes = _build_lambda_zip()
    print(f"  Lambda zip: {len(zip_bytes):,} bytes")

    arns = {}
    for cfg in LAMBDA_CONFIGS:
        try:
            lam.get_function(FunctionName=cfg["name"])
            lam.update_function_code(
                FunctionName=cfg["name"], ZipFile=zip_bytes,
            )
            # Wait for update to complete before updating config
            _wait_for_lambda(lam, cfg["name"])
            lam.update_function_configuration(
                FunctionName=cfg["name"],
                Handler=cfg["handler"],
                Environment={"Variables": _lambda_env_vars(cfg["name"])},
            )
            print(f"  Updated: {cfg['name']}")
        except lam.exceptions.ResourceNotFoundException:
            lam.create_function(
                FunctionName=cfg["name"],
                Runtime="python3.11",
                Role=role_arn,
                Handler=cfg["handler"],
                Code={"ZipFile": zip_bytes},
                Timeout=30,
                MemorySize=512,
                Description=cfg["description"],
                Environment={"Variables": _lambda_env_vars(cfg["name"])},
            )
            print(f"  Created: {cfg['name']}")
            waiter = lam.get_waiter("function_active_v2")
            waiter.wait(FunctionName=cfg["name"])

        arns[cfg["name"]] = (
            f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{cfg['name']}"
        )

    return arns


def _lambda_env_vars(name):
    """Env vars for each Lambda (e.g., SageMaker endpoint for ML)."""
    base = {"DATA_DIR": "data"}
    if name == LAMBDA_DIAGNOSE:
        sm_endpoint = os.environ.get("SAGEMAKER_ENDPOINT_NAME", "campaign-opt-diagnosis")
        base["SAGEMAKER_ENDPOINT_NAME"] = sm_endpoint
    return base


def _wait_for_lambda(lam, name, max_wait=60):
    """Wait for Lambda to leave 'Pending' state after code update."""
    for _ in range(max_wait // 2):
        resp = lam.get_function_configuration(FunctionName=name)
        if resp.get("LastUpdateStatus", "Successful") == "Successful":
            return
        time.sleep(2)


# ── Step 3: Create API Gateway REST API ──────────────────────────────────────
def create_api_gateway(apigw, lam, lambda_arns):
    """Create API Gateway REST API with Lambda proxy for get_campaign_metrics."""
    # Check if API already exists
    rest_api_id = None
    for api in apigw.get_rest_apis(limit=100).get("items", []):
        if api["name"] == API_GW_NAME:
            rest_api_id = api["id"]
            print(f"  API Gateway exists: {rest_api_id}")
            break

    if not rest_api_id:
        resp = apigw.create_rest_api(
            name=API_GW_NAME,
            description="Campaign metrics REST API for AgentCore Gateway",
            endpointConfiguration={"types": ["REGIONAL"]},
        )
        rest_api_id = resp["id"]
        print(f"  Created API Gateway: {rest_api_id}")

    # Get root resource
    resources = apigw.get_resources(restApiId=rest_api_id).get("items", [])
    root_id = next(r["id"] for r in resources if r["path"] == "/")

    # Create /campaign-metrics resource (if not exists)
    resource_id = None
    for r in resources:
        if r.get("pathPart") == "campaign-metrics":
            resource_id = r["id"]
            break

    if not resource_id:
        resp = apigw.create_resource(
            restApiId=rest_api_id,
            parentId=root_id,
            pathPart="campaign-metrics",
        )
        resource_id = resp["id"]

    lambda_uri = (
        f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/"
        f"{lambda_arns[LAMBDA_METRICS]}/invocations"
    )

    # Set up POST method with integration + response (Gateway needs responses defined)
    for method in ["POST", "GET"]:
        try:
            apigw.put_method(
                restApiId=rest_api_id,
                resourceId=resource_id,
                httpMethod=method,
                authorizationType="AWS_IAM",
            )
        except ClientError:
            pass  # method may already exist

        try:
            apigw.put_integration(
                restApiId=rest_api_id,
                resourceId=resource_id,
                httpMethod=method,
                type="AWS_PROXY",
                integrationHttpMethod="POST",
                uri=lambda_uri,
            )
        except ClientError:
            pass

        # Gateway parses the API's OpenAPI spec and requires response definitions
        try:
            apigw.put_method_response(
                restApiId=rest_api_id,
                resourceId=resource_id,
                httpMethod=method,
                statusCode="200",
                responseModels={"application/json": "Empty"},
            )
        except ClientError:
            pass

    # Grant API Gateway permission to invoke Lambda
    try:
        lam.add_permission(
            FunctionName=LAMBDA_METRICS,
            StatementId="apigateway-invoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:{rest_api_id}/*",
        )
    except ClientError as e:
        if "ResourceConflictException" not in str(type(e)):
            print(f"  Note: add_permission: {e}")

    # Deploy to stage
    apigw.create_deployment(restApiId=rest_api_id, stageName=API_GW_STAGE)
    print(f"  Deployed stage: {API_GW_STAGE}")

    return rest_api_id


# ── Step 4: Create Lambda Function URLs ──────────────────────────────────────
def create_function_urls(lam, gateway_role_arn=""):
    """Create Function URLs for the OpenAPI and MCP Server Lambda backends."""
    urls = {}
    gateway_role_arn = gateway_role_arn or os.environ.get("GATEWAY_ROLE_ARN", "")
    if not gateway_role_arn:
        print("  WARNING: GATEWAY_ROLE_ARN not set; Lambda URL permissions may be incomplete")

    for func_name in [LAMBDA_MARKET_INTEL, LAMBDA_RECOMMEND]:
        try:
            resp = lam.get_function_url_config(FunctionName=func_name)
            url = resp["FunctionUrl"]
            print(f"  Function URL exists: {func_name} -> {url}")
        except lam.exceptions.ResourceNotFoundException:
            resp = lam.create_function_url_config(
                FunctionName=func_name,
                AuthType="AWS_IAM",
            )
            url = resp["FunctionUrl"]
            print(f"  Created Function URL: {func_name} -> {url}")

            # Grant invoke only to the Gateway's IAM role
            if gateway_role_arn:
                try:
                    lam.add_permission(
                        FunctionName=func_name,
                        StatementId="AllowGatewayInvoke",
                        Action="lambda:InvokeFunctionUrl",
                        Principal=gateway_role_arn,
                        FunctionUrlAuthType="AWS_IAM",
                    )
                except ClientError:
                    pass

        urls[func_name] = url
    return urls


# ── Step 5: Upload OpenAPI spec to S3 ────────────────────────────────────────
def upload_openapi_spec(s3, function_url):
    """Upload the OpenAPI spec to S3, replacing the placeholder server URL."""
    bucket = f"{S3_BUCKET_PREFIX}{ACCOUNT_ID}"

    # Ensure bucket exists
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        print(f"  Created S3 bucket: {bucket}")

    # Load spec template and inject the real Function URL
    spec_path = REPO_ROOT / "deploy" / "openapi_market_intelligence.json"
    spec = json.loads(spec_path.read_text())

    # Remove trailing slash from Function URL for clean server URL
    clean_url = function_url.rstrip("/")
    spec["servers"][0]["url"] = clean_url

    spec_body = json.dumps(spec, indent=2)
    s3.put_object(
        Bucket=bucket,
        Key=OPENAPI_SPEC_KEY,
        Body=spec_body.encode(),
        ContentType="application/json",
    )
    s3_uri = f"s3://{bucket}/{OPENAPI_SPEC_KEY}"
    print(f"  Uploaded OpenAPI spec: {s3_uri}")
    return s3_uri


# ── Step 6: Create AgentCore Gateway ─────────────────────────────────────────
def create_gateway(agentcore, role_arn):
    """Create or get the AgentCore Gateway."""
    try:
        for gw in agentcore.list_gateways(maxResults=50).get("items", []):
            if gw["name"] == GATEWAY_NAME:
                gw_id = gw["gatewayId"]
                detail = agentcore.get_gateway(gatewayIdentifier=gw_id)
                print(f"  Gateway exists: {gw_id}")
                return {
                    "gatewayId": gw_id,
                    "gatewayUrl": detail.get("gatewayUrl", ""),
                    "status": detail.get("status", ""),
                }
    except ClientError as e:
        print(f"  Note: {e}")

    print(f"  Creating Gateway: {GATEWAY_NAME}")
    resp = agentcore.create_gateway(
        name=GATEWAY_NAME,
        roleArn=role_arn,
        protocolType="MCP",
        authorizerType="AWS_IAM",
        description=(
            "Campaign Optimization Gateway — demonstrates 4 target types: "
            "Lambda, API Gateway, OpenAPI Schema, MCP Server"
        ),
    )
    gw_id = resp["gatewayId"]
    print(f"  Gateway created: {gw_id}")

    # Wait for ACTIVE
    print("  Waiting for Gateway to become ACTIVE...")
    detail = {}
    for _ in range(30):
        detail = agentcore.get_gateway(gatewayIdentifier=gw_id)
        status = detail.get("status", "")
        if status in ("ACTIVE", "READY"):
            break
        if "FAIL" in status:
            print(f"  ERROR: Gateway {status}")
            sys.exit(1)
        time.sleep(5)

    return {
        "gatewayId": gw_id,
        "gatewayUrl": detail.get("gatewayUrl", ""),
        "status": detail.get("status", ""),
    }


# ── Step 7: Add 4 Gateway targets ────────────────────────────────────────────
def _existing_targets(agentcore, gw_id):
    """Get map of existing target names to IDs."""
    targets = {}
    try:
        for t in agentcore.list_gateway_targets(
            gatewayIdentifier=gw_id, maxResults=50
        ).get("items", []):
            targets[t["name"]] = t["targetId"]
    except ClientError:
        pass
    return targets


OPENAPI_API_KEY_NAME = "campaign-opt-market-intel-key"


def _ensure_api_key_provider(agentcore):
    """Create or get an API key credential provider for the OpenAPI target."""
    try:
        resp = agentcore.get_api_key_credential_provider(
            name=OPENAPI_API_KEY_NAME,
        )
        arn = resp["credentialProviderArn"]
        print(f"  API key provider exists: {arn}")
        return arn
    except ClientError:
        pass

    api_key = os.environ.get("AGENTCORE_API_KEY")
    if not api_key:
        raise ValueError(
            "AGENTCORE_API_KEY environment variable is required. "
            "Set it to the API key value for the OpenAPI target credential provider."
        )

    resp = agentcore.create_api_key_credential_provider(
        name=OPENAPI_API_KEY_NAME,
        apiKey=api_key,
    )
    arn = resp["credentialProviderArn"]
    print(f"  Created API key provider: {arn}")
    return arn


def _wait_target(agentcore, gw_id, target_id):
    for _ in range(20):
        detail = agentcore.get_gateway_target(
            gatewayIdentifier=gw_id, targetId=target_id,
        )
        if detail.get("status") in ("ACTIVE", "READY"):
            return
        if "FAIL" in detail.get("status", ""):
            print(f"  WARNING: target {target_id} status={detail['status']}")
            return
        time.sleep(3)


def add_target_lambda(agentcore, gw_id, lambda_arn):
    """Target 1: Lambda → diagnose_campaign_issue."""
    existing = _existing_targets(agentcore, gw_id)
    if TARGET_LAMBDA in existing:
        print(f"  Target '{TARGET_LAMBDA}' exists: {existing[TARGET_LAMBDA]}")
        return existing[TARGET_LAMBDA]

    resp = agentcore.create_gateway_target(
        gatewayIdentifier=gw_id,
        name=TARGET_LAMBDA,
        targetConfiguration={
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {
                        "inlinePayload": [{
                            "name": "diagnose_campaign_issue",
                            "description": (
                                "Run ML-powered diagnosis on a campaign to identify "
                                "issues such as under-delivery, bid problems, or "
                                "targeting inefficiencies. Returns issue type, severity, "
                                "confidence score, and contributing factors."
                            ),
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "campaign_id": {
                                        "type": "string",
                                        "description": "Campaign ID to diagnose (e.g. '4782')",
                                    },
                                },
                                "required": ["campaign_id"],
                            },
                        }],
                    },
                },
            },
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"},
        ],
    )
    target_id = resp["targetId"]
    print(f"  Created Lambda target: {target_id}")
    _wait_target(agentcore, gw_id, target_id)
    return target_id


def add_target_apigw(agentcore, gw_id, rest_api_id):
    """Target 2: API Gateway → get_campaign_metrics."""
    existing = _existing_targets(agentcore, gw_id)
    if TARGET_APIGW in existing:
        print(f"  Target '{TARGET_APIGW}' exists: {existing[TARGET_APIGW]}")
        return existing[TARGET_APIGW]

    resp = agentcore.create_gateway_target(
        gatewayIdentifier=gw_id,
        name=TARGET_APIGW,
        targetConfiguration={
            "mcp": {
                "apiGateway": {
                    "restApiId": rest_api_id,
                    "stage": API_GW_STAGE,
                    "apiGatewayToolConfiguration": {
                        "toolFilters": [{
                            "filterPath": "/campaign-metrics",
                            "methods": ["POST"],
                        }],
                        "toolOverrides": [{
                            "path": "/campaign-metrics",
                            "method": "POST",
                            "name": "get_campaign_metrics",
                            "description": (
                                "Retrieve current performance metrics for a specific "
                                "campaign including delivery, engagement, financial, "
                                "and auction metrics."
                            ),
                        }],
                    },
                },
            },
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"},
        ],
    )
    target_id = resp["targetId"]
    print(f"  Created API Gateway target: {target_id}")
    _wait_target(agentcore, gw_id, target_id)
    return target_id


def add_target_openapi(agentcore, gw_id, s3_uri):
    """Target 3: OpenAPI Schema → get_market_intelligence."""
    existing = _existing_targets(agentcore, gw_id)
    if TARGET_OPENAPI in existing:
        print(f"  Target '{TARGET_OPENAPI}' exists: {existing[TARGET_OPENAPI]}")
        return existing[TARGET_OPENAPI]

    # OpenAPI targets require API_KEY or OAUTH credentials (not GATEWAY_IAM_ROLE).
    # Create an API key credential provider in the token vault.
    api_key_arn = _ensure_api_key_provider(agentcore)

    resp = agentcore.create_gateway_target(
        gatewayIdentifier=gw_id,
        name=TARGET_OPENAPI,
        targetConfiguration={
            "mcp": {
                "openApiSchema": {
                    "s3": {
                        "uri": s3_uri,
                        "bucketOwnerAccountId": ACCOUNT_ID,
                    },
                },
            },
        },
        credentialProviderConfigurations=[{
            "credentialProviderType": "API_KEY",
            "credentialProvider": {
                "apiKeyCredentialProvider": {
                    "providerArn": api_key_arn,
                    "credentialLocation": "HEADER",
                    "credentialParameterName": "X-Api-Key",
                },
            },
        }],
    )
    target_id = resp["targetId"]
    print(f"  Created OpenAPI target: {target_id}")
    _wait_target(agentcore, gw_id, target_id)
    return target_id


def add_target_mcp_server(agentcore, gw_id, mcp_endpoint_url):
    """Target 4: MCP Server → generate_recommendation."""
    existing = _existing_targets(agentcore, gw_id)
    if TARGET_MCP in existing:
        print(f"  Target '{TARGET_MCP}' exists: {existing[TARGET_MCP]}")
        return existing[TARGET_MCP]

    resp = agentcore.create_gateway_target(
        gatewayIdentifier=gw_id,
        name=TARGET_MCP,
        targetConfiguration={
            "mcp": {
                "mcpServer": {
                    "endpoint": mcp_endpoint_url,
                },
            },
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"},
        ],
    )
    target_id = resp["targetId"]
    print(f"  Created MCP Server target: {target_id}")
    _wait_target(agentcore, gw_id, target_id)
    return target_id


# ── Deploy orchestration ─────────────────────────────────────────────────────
def deploy():
    print("=" * 70)
    print("Deploy AgentCore Gateway — 4 Target Types")
    print("=" * 70)

    c = clients()

    # Step 1: IAM
    print("\n[1/7] Gateway IAM role")
    role_arn = ensure_gateway_role(c["iam"])

    # Step 2: Lambdas
    print("\n[2/7] Lambda functions (4)")
    lambda_arns = deploy_lambdas(c["lambda"], c["iam"])

    # Step 3: API Gateway
    print("\n[3/7] API Gateway REST API")
    rest_api_id = create_api_gateway(c["apigateway"], c["lambda"], lambda_arns)

    # Step 4: Function URLs
    print("\n[4/7] Lambda Function URLs")
    func_urls = create_function_urls(c["lambda"], gateway_role_arn=role_arn)

    # Step 5: OpenAPI spec → S3
    print("\n[5/7] OpenAPI spec to S3")
    s3_uri = upload_openapi_spec(c["s3"], func_urls[LAMBDA_MARKET_INTEL])

    # Step 6: Gateway
    print("\n[6/7] AgentCore Gateway")
    gw = create_gateway(c["agentcore"], role_arn)

    # Step 7: Targets
    print("\n[7/7] Gateway targets")

    print("\n  --- Target 1: Lambda (diagnose_campaign_issue) ---")
    t1 = add_target_lambda(c["agentcore"], gw["gatewayId"], lambda_arns[LAMBDA_DIAGNOSE])

    print("\n  --- Target 2: API Gateway (get_campaign_metrics) ---")
    t2 = add_target_apigw(c["agentcore"], gw["gatewayId"], rest_api_id)

    print("\n  --- Target 3: OpenAPI Schema (get_market_intelligence) ---")
    t3 = add_target_openapi(c["agentcore"], gw["gatewayId"], s3_uri)

    print("\n  --- Target 4: MCP Server (generate_recommendation) ---")
    t4 = add_target_mcp_server(c["agentcore"], gw["gatewayId"], func_urls[LAMBDA_RECOMMEND])

    # Save config
    config = {
        "gateway_id": gw["gatewayId"],
        "gateway_url": gw["gatewayUrl"],
        "region": REGION,
        "auth_type": "AWS_IAM",
        "targets": {
            "lambda": {
                "target_id": t1, "target_name": TARGET_LAMBDA,
                "tool": "diagnose_campaign_issue",
                "lambda": LAMBDA_DIAGNOSE,
            },
            "api_gateway": {
                "target_id": t2, "target_name": TARGET_APIGW,
                "tool": "get_campaign_metrics",
                "rest_api_id": rest_api_id, "stage": API_GW_STAGE,
            },
            "openapi": {
                "target_id": t3, "target_name": TARGET_OPENAPI,
                "tool": "get_market_intelligence",
                "s3_uri": s3_uri,
                "function_url": func_urls[LAMBDA_MARKET_INTEL],
            },
            "mcp_server": {
                "target_id": t4, "target_name": TARGET_MCP,
                "tool": "generate_recommendation",
                "function_url": func_urls[LAMBDA_RECOMMEND],
            },
        },
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

    print("\n" + "=" * 70)
    print("Gateway deployed successfully with 4 target types!")
    print(f"  MCP Endpoint: {gw['gatewayUrl']}")
    print(f"  Config:       {CONFIG_FILE}")
    print()
    print("  Targets:")
    print(f"    1. Lambda       → diagnose_campaign_issue   [{t1}]")
    print(f"    2. API Gateway  → get_campaign_metrics      [{t2}]")
    print(f"    3. OpenAPI      → get_market_intelligence   [{t3}]")
    print(f"    4. MCP Server   → generate_recommendation   [{t4}]")
    print("=" * 70)


# ── Status ────────────────────────────────────────────────────────────────────
def status():
    if not CONFIG_FILE.exists():
        print("No gateway_multi_config.json found. Deploy first.")
        return

    config = json.loads(CONFIG_FILE.read_text())
    c = clients()

    print(f"Gateway: {config['gateway_id']}")
    try:
        gw = c["agentcore"].get_gateway(gatewayIdentifier=config["gateway_id"])
        print(f"  Status: {gw.get('status', 'UNKNOWN')}")
        print(f"  URL:    {gw.get('gatewayUrl', 'N/A')}")
    except ClientError as e:
        print(f"  Error: {e}")

    for key, tgt_info in config.get("targets", {}).items():
        print(f"\nTarget: {tgt_info['target_name']} ({key})")
        print(f"  Tool: {tgt_info['tool']}")
        try:
            tgt = c["agentcore"].get_gateway_target(
                gatewayIdentifier=config["gateway_id"],
                targetId=tgt_info["target_id"],
            )
            print(f"  Status: {tgt.get('status', 'UNKNOWN')}")
        except ClientError as e:
            print(f"  Error: {e}")


# ── Destroy ───────────────────────────────────────────────────────────────────
def destroy():
    if not CONFIG_FILE.exists():
        print("No gateway_multi_config.json found. Nothing to destroy.")
        return

    config = json.loads(CONFIG_FILE.read_text())
    c = clients()
    gw_id = config["gateway_id"]

    # Delete targets
    for key, tgt_info in config.get("targets", {}).items():
        try:
            print(f"Deleting target: {tgt_info['target_name']} ({key})")
            c["agentcore"].delete_gateway_target(
                gatewayIdentifier=gw_id,
                targetId=tgt_info["target_id"],
            )
            print("  Deleted.")
        except ClientError as e:
            print(f"  {e}")

    time.sleep(5)

    # Delete gateway
    try:
        print(f"Deleting gateway: {gw_id}")
        c["agentcore"].delete_gateway(gatewayIdentifier=gw_id)
        print("  Deleted.")
    except ClientError as e:
        print(f"  {e}")

    # Delete Function URLs
    for name in [LAMBDA_MARKET_INTEL, LAMBDA_RECOMMEND]:
        try:
            c["lambda"].delete_function_url_config(FunctionName=name)
            print(f"Deleted Function URL: {name}")
        except ClientError:
            pass

    # Delete Lambdas
    for cfg in LAMBDA_CONFIGS:
        try:
            print(f"Deleting Lambda: {cfg['name']}")
            c["lambda"].delete_function(FunctionName=cfg["name"])
            print("  Deleted.")
        except ClientError as e:
            print(f"  {e}")

    # Delete API Gateway
    for api in c["apigateway"].get_rest_apis(limit=100).get("items", []):
        if api["name"] == API_GW_NAME:
            try:
                print(f"Deleting API Gateway: {api['id']}")
                c["apigateway"].delete_rest_api(restApiId=api["id"])
                print("  Deleted.")
            except ClientError as e:
                print(f"  {e}")
            break

    # Delete S3 spec
    bucket = f"{S3_BUCKET_PREFIX}{ACCOUNT_ID}"
    try:
        c["s3"].delete_object(Bucket=bucket, Key=OPENAPI_SPEC_KEY)
        print(f"Deleted S3 object: s3://{bucket}/{OPENAPI_SPEC_KEY}")
    except ClientError:
        pass

    # Delete Gateway IAM role policy (not the role itself — shared)
    try:
        c["iam"].delete_role_policy(
            RoleName=GATEWAY_ROLE_NAME,
            PolicyName="GatewayMultiTargetPolicy",
        )
        c["iam"].delete_role(RoleName=GATEWAY_ROLE_NAME)
        print(f"Deleted role: {GATEWAY_ROLE_NAME}")
    except ClientError as e:
        print(f"  {e}")

    CONFIG_FILE.unlink(missing_ok=True)
    print("\nAll multi-target Gateway resources destroyed.")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy AgentCore Gateway with 4 target types"
    )
    parser.add_argument("--destroy", action="store_true", help="Tear down all resources")
    parser.add_argument("--status", action="store_true", help="Check status")
    args = parser.parse_args()

    if args.destroy:
        destroy()
    elif args.status:
        status()
    else:
        deploy()
