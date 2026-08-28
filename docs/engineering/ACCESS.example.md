<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Access Configuration — Example

> Copy this file to `ACCESS.md` and fill in your account-specific values.

## AWS Account

| Field | Value |
|-------|-------|
| Account ID | `123456789012` |
| Region | `us-east-1` |
| AWS Profile | `my-profile` |

## Amazon Bedrock

| Field | Value |
|-------|-------|
| Model ID | `us.anthropic.claude-sonnet-4-20250514` |
| Model access | Enabled via Bedrock console |

## Amazon Cognito (if using OAuth)

| Field | Value |
|-------|-------|
| User Pool ID | `us-east-1_XXXXXXXXX` |
| App Client ID | `xxxxxxxxxxxxxxxxxxxxxxxxxx` |
| Domain | `https://your-domain.auth.us-east-1.amazoncognito.com` |

## SageMaker Endpoints

| Endpoint | Name |
|----------|------|
| Diagnosis model | `campaign-diagnosis-endpoint` |
| Recommendation model | `campaign-recommendation-endpoint` |

## AgentCore

| Field | Value |
|-------|-------|
| Runtime ID | `rt-xxxxxxxxxx` |
| Gateway ID | `gw-xxxxxxxxxx` |
