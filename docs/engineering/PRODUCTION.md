<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Production Readiness Guide

> What changes between this PoC and a production deployment. Use as a checklist when planning the transition.

## Overview

This PoC demonstrates the architecture and UX patterns. Production requires hardening across security, reliability, observability, and data management.

## Gap Analysis: PoC vs. Production

| Area | PoC State | Production Requirement | Effort |
|------|-----------|----------------------|--------|
| **Authentication** | Cognito with optional MFA | Cognito + mandatory MFA + SAML federation | Medium |
| **Network** | Default VPC / public subnets | Private subnets + VPC endpoints + WAF | High |
| **Data** | Synthetic JSON files | Real-time data pipeline (Kinesis/EventBridge) | High |
| **ML Models** | Local training, manual deploy | SageMaker Pipelines + Model Registry + A/B | High |
| **Logging** | CloudTrail default | CloudTrail + GuardDuty + Security Hub + SIEM | Medium |
| **Secrets** | Environment variables | AWS Secrets Manager with rotation | Low |
| **Input validation** | Basic type checking | Schema validation + content filtering + guardrails | Medium |
| **Rate limiting** | None | API Gateway throttling + WAF rules | Low |
| **Disaster recovery** | None | Multi-AZ + backup + RTO/RPO targets | High |
| **Compliance** | Not assessed | SOC 2 / HIPAA / PCI as required | High |
| **Observability** | Console logs | X-Ray tracing + CloudWatch dashboards + alarms | Medium |
| **CI/CD** | Manual deploy scripts | CodePipeline / GitHub Actions + staged rollout | Medium |
| **Multi-tenancy** | Single-tenant | Tenant isolation (row-level or account-level) | High |
| **Cost controls** | None | Budgets + anomaly detection + reserved capacity | Low |

## Recommended Production Architecture Changes

### 1. Data Layer

- Replace file-based JSON with Amazon DynamoDB or Aurora PostgreSQL
- Add Amazon Kinesis Data Streams for real-time campaign event ingestion
- Implement Amazon EventBridge for event-driven agent triggers

### 2. ML Pipeline

- Move training to SageMaker Pipelines with automated retraining
- Add SageMaker Model Monitor for data/model drift detection
- Implement A/B testing for model versions via endpoint variants

### 3. Agent Runtime

- Deploy AgentCore Runtime behind a Gateway with rate limiting
- Add input/output guardrails (Amazon Bedrock Guardrails)
- Implement conversation memory via AgentCore Memory

### 4. Frontend

- Deploy React app to Amazon CloudFront + S3
- Add Amazon Cognito hosted UI for authentication
- Implement WebSocket for streaming agent responses

### 5. Observability

- AWS X-Ray for distributed tracing across Lambda → Bedrock → SageMaker
- CloudWatch Logs Insights for agent tool invocation analytics
- Custom CloudWatch metrics for: agent response time, tool selection accuracy, recommendation acceptance rate

## Migration Priority (Recommended Order)

1. **Security hardening** — VPC, IAM scoping, secrets rotation
2. **Data pipeline** — Replace synthetic data with real integrations
3. **CI/CD** — Automated testing and deployment
4. **Observability** — Tracing and alerting
5. **ML pipeline** — Automated retraining and monitoring
6. **Multi-tenancy** — If serving multiple customers
