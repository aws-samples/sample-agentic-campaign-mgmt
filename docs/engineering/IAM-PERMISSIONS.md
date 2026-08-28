<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# IAM Permissions

> Minimum IAM permissions required to deploy and run the Campaign Optimization PoC.

## Developer / Deployer Role

The developer running deploy scripts needs these permissions:

### Amazon Bedrock

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream",
    "bedrock:ListFoundationModels"
  ],
  "Resource": "arn:aws:bedrock:*:*:foundation-model/anthropic.*"
}
```

### AWS Lambda

```json
{
  "Effect": "Allow",
  "Action": [
    "lambda:CreateFunction",
    "lambda:UpdateFunctionCode",
    "lambda:UpdateFunctionConfiguration",
    "lambda:InvokeFunction",
    "lambda:GetFunction",
    "lambda:PublishLayerVersion"
  ],
  "Resource": "arn:aws:lambda:*:*:function:campaign-*"
}
```

### Amazon SageMaker

```json
{
  "Effect": "Allow",
  "Action": [
    "sagemaker:CreateModel",
    "sagemaker:CreateEndpointConfig",
    "sagemaker:CreateEndpoint",
    "sagemaker:InvokeEndpoint",
    "sagemaker:DescribeEndpoint",
    "sagemaker:DeleteEndpoint",
    "sagemaker:DeleteEndpointConfig",
    "sagemaker:DeleteModel"
  ],
  "Resource": "arn:aws:sagemaker:*:*:*campaign*"
}
```

### Amazon Bedrock AgentCore

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:CreateAgentRuntime",
    "bedrock:UpdateAgentRuntime",
    "bedrock:InvokeAgentRuntime",
    "bedrock:GetAgentRuntime"
  ],
  "Resource": "arn:aws:bedrock:*:*:agent-runtime/campaign-*"
},
{
  "Effect": "Allow",
  "Action": [
    "bedrock:CreateGateway",
    "bedrock:CreateGatewayTarget"
  ],
  "Resource": "arn:aws:bedrock:*:*:gateway/campaign-*"
}
```

### Amazon S3 (Model artifacts)

```json
{
  "Effect": "Allow",
  "Action": [
    "s3:PutObject",
    "s3:GetObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::campaign-*",
    "arn:aws:s3:::campaign-*/*"
  ]
}
```

### Amazon ECR (Container images)

```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken"
  ],
  "Resource": "*"
},
{
  "Effect": "Allow",
  "Action": [
    "ecr:BatchCheckLayerAvailability",
    "ecr:PutImage",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload",
    "ecr:CreateRepository"
  ],
  "Resource": "arn:aws:ecr:*:*:repository/campaign-*"
}
```

## Lambda Execution Role

The Lambda function's execution role needs:

| Permission | Purpose |
|------------|---------|
| `bedrock:InvokeModel` | Call Claude for agent reasoning |
| `sagemaker:InvokeEndpoint` | Call ML models for diagnosis/recommendation |
| `logs:CreateLogGroup`, `logs:PutLogEvents` | CloudWatch logging |

## AgentCore Runtime Role

The AgentCore container's IAM role needs:

| Permission | Purpose |
|------------|---------|
| `bedrock:InvokeModel` | Call Claude Sonnet |
| `sagemaker:InvokeEndpoint` | Call ML endpoints |
| `bedrock:InvokeAgentRuntime` | Self-invocation for sub-agents (if used) |
