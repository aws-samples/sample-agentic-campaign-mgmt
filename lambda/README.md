<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Lambda — Serverless Handlers

> AWS Lambda function handlers for the campaign optimization agent and supporting services.

## Handlers

| File | Purpose | Trigger |
|------|---------|---------|
| `handler.py` | Main agent handler — routes prompts to Strands agent | API Gateway / direct invoke |
| `gateway_handler.py` | AgentCore Gateway integration handler | AgentCore Gateway |
| `apigw_handler.py` | API Gateway REST proxy handler | API Gateway HTTP |
| `market_intel_handler.py` | Market intelligence data endpoint | API Gateway |
| `mcp_server_handler.py` | MCP server protocol handler for tool exposure | AgentCore Gateway |
| `smoke_test.py` | Quick validation script for deployed functions | Manual / CI |

## Structure

```
lambda/
├── handler.py                 # Main agent entry point
├── gateway_handler.py         # AgentCore Gateway adapter
├── apigw_handler.py           # REST API proxy
├── market_intel_handler.py    # Market data endpoint
├── mcp_server_handler.py      # MCP protocol server
├── smoke_test.py              # Deployment validation
└── layer/                     # Lambda layer (gitignored, built by deploy scripts)
```

## Deployment

```bash
# Package and deploy via deploy script
uv run python deploy/deploy_lambda_zip.py

# Smoke test after deployment
uv run python lambda/smoke_test.py
```
