<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Deploy — Boto3 Deployment Scripts

> One script per AWS resource. No CDK/CloudFormation — pure boto3 for rapid PoC iteration.

## Scripts

| Script | Resource | Description |
|--------|----------|-------------|
| `deploy_lambda_zip.py` | AWS Lambda | Package and deploy agent handler as zip |
| `deploy_gateway.py` | AgentCore Gateway | Single-target MCP gateway |
| `deploy_multi_target_gateway.py` | AgentCore Gateway | Multi-target gateway with routing |
| `deploy_sagemaker_diagnosis.py` | SageMaker Endpoint | XGBoost diagnosis model |
| `deploy_sagemaker_recommendation.py` | SageMaker Endpoint | Recommendation model |
| `deploy_agentcore.py` | AgentCore Runtime | Container-based agent runtime |
| `invoke_agentcore.py` | AgentCore Runtime | Test invocation script |

## Configuration

Deploy scripts read/write config JSON files that are gitignored (contain account-specific ARNs):

- `cognito_oauth_config.json` — Cognito pool/client IDs
- `gateway_config.json` — Gateway endpoint URLs
- `gateway_multi_config.json` — Multi-target gateway config

## Prerequisites

1. **AWS credentials** configured (profile or environment variables)
2. **Data symlink** - deploy scripts read JSON data from `<repo-root>/data/`. After cloning, create a symlink to the actual data location:
   - Linux/macOS: `ln -s prototype-v1/data data`
   - Windows: `mklink /J data prototype-v1\data`
3. **ML models trained** - run `uv run python ml/generate_training_data.py && uv run python ml/train_model.py` (and the recommendation equivalents)
4. **SageMaker inference container built** - run `ml/sagemaker/build-inference-container.sh` in AWS CloudShell (us-west-2) before deploying SageMaker endpoints. This builds a custom container because most accounts' SCPs block cross-account ECR pulls from AWS DLC registries. Copy the printed `CUSTOM_IMAGE_URI` for use below.

## Required Environment Variables

| Variable | Required | Used By | Description |
|----------|----------|---------|-------------|
| `AWS_ACCOUNT_ID` | Yes | `deploy_multi_target_gateway.py`, `deploy_gateway.py` | Your 12-digit AWS account ID |
| `CUSTOM_IMAGE_URI` | Yes | `deploy_sagemaker_*.py` | ECR URI from CloudShell container build |
| `AGENTCORE_API_KEY` | Yes (multi-target only) | `deploy_multi_target_gateway.py` | API key for the OpenAPI target credential provider |
| `AWS_DEFAULT_REGION` | No (default: us-west-2) | All scripts | AWS region for deployment |
| `GATEWAY_ROLE_ARN` | No (auto-resolved) | `deploy_multi_target_gateway.py` | Gateway role ARN; auto-resolved from Step 1 if omitted |
| `SAGEMAKER_ENDPOINT_NAME` | No (auto-set) | `deploy_sagemaker_diagnosis.py` | Set automatically on Lambda after SageMaker deploy |

## Usage

Deploy in this order (each step depends on the previous):

```bash
# 1. Deploy Lambda function (creates IAM role + function)
uv run python deploy/deploy_lambda_zip.py

# 2. Deploy SageMaker endpoints (~5 min each)
#    Requires CUSTOM_IMAGE_URI from CloudShell container build
CUSTOM_IMAGE_URI=<your-ecr-uri> uv run python deploy/deploy_sagemaker_diagnosis.py
CUSTOM_IMAGE_URI=<your-ecr-uri> uv run python deploy/deploy_sagemaker_recommendation.py

# 3. Deploy AgentCore Gateway (single-target, simpler)
AWS_ACCOUNT_ID=<account-id> uv run python deploy/deploy_gateway.py

# 4. OR deploy multi-target gateway (demonstrates all 4 target types)
AWS_ACCOUNT_ID=<account-id> AGENTCORE_API_KEY=<key> uv run python deploy/deploy_multi_target_gateway.py

# 5. (Optional) Deploy AgentCore Runtime container
uv run python deploy/deploy_agentcore.py

# 6. Test invocation
uv run python deploy/invoke_agentcore.py
```

## Deployment Architecture

```text
Lambda (pass-through) --> SageMaker Endpoints (ML inference)
     ^
     |
AgentCore Gateway (MCP protocol, AWS_IAM auth) --> Lambda
     ^
     |
Strands Agent (Claude on Bedrock)
```

The Lambda functions do not bundle ML dependencies. They forward inference requests to SageMaker endpoints via boto3. The `DATA_DIR` environment variable (set automatically by deploy scripts) tells the Lambda where to find JSON data files within the zip package.
