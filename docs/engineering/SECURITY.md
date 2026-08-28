<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Security Posture — Campaign Optimization PoC

> This document describes the security architecture for the Campaign Optimization AI Agent proof-of-concept. It is intended for security reviewers and architects evaluating this PoC for production readiness.

## PoC Network Posture

| Component | Exposure | Access Control |
|-----------|----------|---------------|
| React UI (prototype-v1/v2) | localhost:3000 | Developer workstation only |
| Express API server | localhost:8000 | Developer workstation only |
| AWS Lambda handlers | VPC-internal or API Gateway | IAM + Cognito JWT |
| SageMaker endpoints | VPC-internal | IAM role-based |
| AgentCore Runtime | AgentCore-managed | IAM SigV4 + Cognito OAuth |
| AgentCore Gateway | AgentCore-managed | IAM SigV4 |

**No public endpoints are exposed by default.** All AWS resources require authenticated access.

## Shared Responsibility Model

| Responsibility | AWS | Customer (PoC Owner) |
|---------------|-----|---------------------|
| Physical infrastructure | Yes | — |
| Network isolation (VPC) | Provides | Configures |
| IAM policy enforcement | Provides | Authors policies |
| Data encryption at rest | Provides (S3 SSE, EBS) | Enables per-service |
| Data encryption in transit | Provides (TLS 1.2+) | Ensures endpoints use HTTPS |
| Model access control | Provides (Bedrock IAM) | Scopes permissions |
| Application logic security | — | Yes |
| Input validation / prompt safety | — | Yes |
| Secrets management | Provides (Secrets Manager) | Uses (no hardcoded creds) |

## Per-Service Security Guidelines

| Service | Guideline | Reference |
|---------|-----------|-----------|
| Amazon Bedrock | Use model-level IAM policies; enable CloudTrail logging | [Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html) |
| AWS Lambda | Least-privilege execution role; no `*` resource permissions | [Lambda Security](https://docs.aws.amazon.com/lambda/latest/dg/lambda-security.html) |
| Amazon SageMaker | VPC endpoints; encrypted model artifacts; no public endpoints | [SageMaker Security](https://docs.aws.amazon.com/sagemaker/latest/dg/security.html) |
| Amazon Cognito | MFA optional for PoC; short token TTL; PKCE for public clients | [Cognito Security](https://docs.aws.amazon.com/cognito/latest/developerguide/security.html) |
| AgentCore Runtime | Container image scanning; read-only filesystem; no root | [AgentCore Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html) |
| AgentCore Gateway | SigV4 auth; tool-level authorization policies | [AgentCore Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html) |

## Threat Model

| Threat | Impact | Mitigation | Residual Risk |
|--------|--------|------------|---------------|
| Prompt injection via user input | Agent executes unintended tools | System prompt guardrails; tool input validation; tool scoping | Medium — LLM-level risk inherent |
| Model hallucination in recommendations | Incorrect campaign actions taken | Human-in-the-loop approval for all changes; ML confidence thresholds | Low — no auto-execution |
| Credential exposure in config files | Account compromise | All config files gitignored; use env vars or Secrets Manager | Low |
| Lambda cold-start timing attacks | Information leakage | Standard Lambda isolation; no timing-sensitive logic | Negligible |
| SageMaker model poisoning | Degraded predictions | Training data validation; model versioning; rollback capability | Low — synthetic data for PoC |
| Cross-tenant data leakage | Privacy violation | Single-tenant PoC; no shared infrastructure | N/A for PoC |

## AI Security Controls

| Control | Implementation |
|---------|---------------|
| **Human-in-the-loop** | Agent recommends actions; user must explicitly approve before execution |
| **Input sanitization** | Tool inputs validated as plain Python types; no shell injection vectors |
| **Output guardrails** | Agent responses are text-only; no code execution in client |
| **Model access** | Bedrock model access scoped to specific model IDs via IAM |
| **Tool scoping** | Agent tools are read-only data access; no write/delete operations |
| **Audit trail** | All agent invocations logged via CloudTrail and AgentCore telemetry |

## Data Classification

| Data Type | Classification | Storage | Encryption |
|-----------|---------------|---------|------------|
| Campaign metrics (synthetic) | Non-sensitive | JSON files / Lambda memory | At rest (S3 SSE) |
| ML training data (synthetic) | Non-sensitive | CSV files / S3 | At rest (S3 SSE) |
| Model artifacts (.pkl) | Internal | S3 / SageMaker | At rest (S3 SSE) |
| User prompts | Internal | In-memory only (not persisted) | In transit (TLS) |
| Agent responses | Internal | In-memory / CloudWatch Logs | At rest (CW encryption) |
| OAuth tokens | Sensitive | Cognito-managed | At rest + in transit |
| AWS credentials | Sensitive | IAM roles / env vars | Never stored in code |

## PoC vs. Production Security Gaps

| Area | PoC State | Production Requirement |
|------|-----------|----------------------|
| Authentication | Cognito with optional MFA | Cognito + mandatory MFA + federation |
| Network | Default VPC / public subnets | Private subnets + VPC endpoints + WAF |
| Logging | CloudTrail default | CloudTrail + GuardDuty + Security Hub |
| Secrets | Environment variables | AWS Secrets Manager with rotation |
| Input validation | Basic type checking | Schema validation + content filtering |
| Rate limiting | None | API Gateway throttling + WAF rules |
| Model governance | Manual versioning | SageMaker Model Registry + approval workflows |
| Disaster recovery | None | Multi-AZ + backup + RTO/RPO targets |
| Compliance | Not assessed | SOC 2 / HIPAA / PCI as required |
