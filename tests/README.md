<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Tests

## Quick Reference

| Command | What it runs | AWS needed? |
|---------|-------------|-------------|
| `uv run python -m pytest tests/ml/ -v` | ML model unit tests | No |
| `uv run python tests/agent/test_agent.py` | Agent tool-coverage E2E (local tools + local ML) | Yes (Bedrock only) |
| `uv run python tests/test_gateway_e2e.py --local-only` | Gateway handler (local) | No |
| `uv run python tests/test_gateway_e2e.py` | Gateway E2E (all 4 layers) | Yes (Lambda, Gateway, Bedrock) |
| `uv run python lambda/smoke_test.py` | Lambda + SageMaker smoke test | Yes (Lambda, SageMaker) |

## Test Flow Diagrams

### Agent E2E — Local Path (`test_agent.py`)

All tools run locally. Only Bedrock is called over the network.

```mermaid
sequenceDiagram
    participant T as test_agent.py
    participant A as Strands Agent
    participant B as Bedrock Claude
    participant F as Local Tool Functions
    participant M as Local XGBoost Model

    T->>A: prompt (e.g. "Diagnose campaign 4782")
    A->>B: LLM request (system prompt + tools)
    B-->>A: tool_use: get_campaign_metrics
    A->>F: get_campaign_metrics(4782)
    F-->>A: JSON from prototype/data/*.json
    A->>B: tool result
    B-->>A: tool_use: diagnose_campaign_issue
    A->>F: diagnose_campaign_issue(4782)
    F->>M: predict(features) via joblib
    M-->>F: {primary_issue, confidence}
    F-->>A: diagnosis JSON
    A->>B: tool result
    B-->>A: final text response
    A-->>T: response
```

### Gateway E2E — Deployed Path (`test_gateway_e2e.py` Layer 4)

Tools route through AgentCore Gateway to Lambda and SageMaker.

```mermaid
sequenceDiagram
    participant T as test_gateway_e2e.py
    participant A as Strands Agent
    participant B as Bedrock Claude
    participant G as AgentCore Gateway
    participant L1 as Lambda<br/>campaign-opt-gateway-tools
    participant L2 as Lambda<br/>campaign-opt-diagnose-ml
    participant S as SageMaker<br/>campaign-opt-diagnosis

    T->>A: prompt ("Diagnose campaign 4782")
    A->>B: LLM request (system prompt + tools)
    B-->>A: tool_use: diagnose_campaign_issue
    A->>G: MCP tool call (HTTPS + SigV4)
    G->>L1: invoke (tool name in context)
    L1->>L2: invoke diagnose Lambda
    L2->>S: InvokeEndpoint (XGBoost)
    S-->>L2: prediction
    L2-->>L1: diagnosis JSON
    L1-->>G: response
    G-->>A: MCP tool result
    A->>B: tool result
    B-->>A: final text response
    A-->>T: response
```

### Lambda Smoke Test — Inference Path (`lambda/smoke_test.py`)

Tests the deployed ML inference pipeline only (no agent, no Gateway).

```mermaid
sequenceDiagram
    participant T as smoke_test.py
    participant L as Lambda<br/>campaign-opt-diagnose-ml
    participant S as SageMaker<br/>campaign-opt-diagnosis

    T->>L: boto3 invoke (campaign_id=4782)
    L->>S: InvokeEndpoint (feature vector)
    S-->>L: XGBoost prediction
    L-->>T: {has_issues, primary_issue, confidence}
```

### Gateway E2E — Layer-by-Layer Scope

```mermaid
flowchart LR
    subgraph "Layer 1 — Local"
        L1[gateway_handler<br/>functions]
    end
    subgraph "Layer 2 — Lambda"
        L2[boto3 invoke] --> LF[campaign-opt-<br/>gateway-tools]
    end
    subgraph "Layer 3 — MCP"
        L3[MCPClient] --> GW[AgentCore<br/>Gateway] --> LF2[Lambda]
    end
    subgraph "Layer 4 — Full E2E"
        L4[Strands Agent] --> BR[Bedrock] --> GW2[Gateway] --> LF3[Lambda]
    end
```

## Test Suites

### ML Unit Tests (`tests/ml/test_diagnosis.py`)

Tests the XGBoost diagnosis engine by calling `predict()` directly with hand-crafted feature dicts. No network calls, no JSON files, no campaign lookups.

**Covers:**
- Response contract (shape, types, probability sums)
- All 6 issue classifications: `bid_too_low`, `competitive_pressure`, `inventory_shortage`, `creative_fatigue`, `targeting_too_narrow`, `pacing_issue`
- Feature builder (`build_features`) correctness
- Error handling for missing features

**Prerequisites (one-time):**

```bash
uv run python ml/generate_training_data.py
uv run python ml/train_model.py
```

### Agent E2E Tests (`tests/agent/test_agent.py`)

Sends a sequence of prompts to a live Strands agent (Claude via Bedrock) and verifies each of the 10 tools gets invoked correctly.

**Important — local execution path:** Despite being an E2E test, all 10 tool functions run **locally as in-process Python**. The ML diagnosis uses the local XGBoost model via joblib (not SageMaker). The only AWS call is to **Bedrock** for LLM reasoning. See the [Agent E2E sequence diagram](#agent-e2e--local-path-test_agentpy) above.

**Covers:**
- Campaign metrics, configuration, trader portfolio, market intelligence
- Full diagnosis + recommendation flow
- Historical analysis, streaming events, multi-tool orchestration

**Prerequisites:** AWS credentials with Bedrock access.

### Gateway E2E Tests (`tests/test_gateway_e2e.py`)

Validates the Agent -> AgentCore Gateway -> Lambda -> ML pipeline at 4 layers of depth. See the [Layer-by-Layer scope diagram](#gateway-e2e--layer-by-layer-scope) and [Layer 4 sequence diagram](#gateway-e2e--deployed-path-test_gateway_e2epy-layer-4) above.

| Layer | Scope | AWS needed? |
|-------|-------|-------------|
| 1 | Local `gateway_handler` functions | No |
| 2 | Lambda invoke via boto3 | Yes |
| 3 | MCP protocol through Gateway endpoint | Yes + Gateway deployed |
| 4 | Full Strands agent with Gateway tools | Yes + Gateway + Bedrock |

```bash
# Layer 1 only (quick, offline)
uv run python tests/test_gateway_e2e.py --local-only

# Specific layer
uv run python tests/test_gateway_e2e.py --layer 2

# All layers
uv run python tests/test_gateway_e2e.py
```

**Prerequisites:** `deploy/deploy_gateway.py` must be run first for layers 2-4.

### Lambda Smoke Test (`lambda/smoke_test.py`)

Invokes the deployed Lambda which calls the SageMaker endpoint for XGBoost inference. Validates the full deploy pipeline is wired correctly. See the [Smoke Test sequence diagram](#lambda-smoke-test--inference-path-lambdasmoke_testpy) above.

```bash
uv run python lambda/smoke_test.py
uv run python lambda/smoke_test.py --campaign-id 1234
```

**Prerequisites:** Lambda and SageMaker endpoints deployed via `deploy/deploy_lambda_zip.py`.

## Coverage Summary

```text
Layer               What's tested                           Local?
-----------------------------------------------------------------
ML model            predict(), build_features(), 6 classes  Yes
Agent tools         All 10 tools via live agent prompts      No (Bedrock)
Gateway handler     4 dispatch functions locally              Yes
Gateway Lambda      Lambda invocation + response shape        No (Lambda)
Gateway MCP         Tool listing + tool calls via MCP         No (Gateway)
Agent + Gateway     Full agent E2E through Gateway            No (all AWS)
Lambda + SageMaker  Deployed inference pipeline               No (Lambda + SM)
```

## Run All Tests (Step by Step)

### How test scope expands at each step

Each step adds more components to the test boundary. Grey boxes are not exercised at that step.

```mermaid
flowchart LR
    subgraph STEP1["Step 1: ML Unit Tests"]
        direction LR
        M1["XGBoost\npredict()"]
    end

    subgraph STEP2["Step 2: Gateway Layer 1"]
        direction LR
        H2["Lambda Handler\n(dispatch)"] --> M2["ML Models\n(local .pkl)"]
        H2 --> D2["JSON Data\n(prototype-v1/)"]
    end

    subgraph STEP3["Step 3: Agent E2E"]
        direction LR
        A3["Strands Agent"] --> B3["Bedrock\n(Claude)"]
        B3 --> T3["10 Local Tools"]
        T3 --> M3["ML Models\n(local .pkl)"]
        T3 --> D3["JSON Data"]
    end

    subgraph STEP4["Step 4: Deployed E2E"]
        direction LR
        A4["Strands Agent"] --> B4["Bedrock"]
        B4 --> G4["AgentCore\nGateway"]
        G4 --> L4["Lambda"]
        L4 --> S4["SageMaker\n(XGBoost)"]
    end

    subgraph STEP5["Step 5: Smoke Test"]
        direction LR
        L5["Lambda"] --> S5["SageMaker\n(endpoint)"]
    end

    style STEP1 fill:#4A6FA5,stroke:#3A5A8A,color:#fff
    style STEP2 fill:#5B9279,stroke:#4A7A64,color:#fff
    style STEP3 fill:#7B6B8D,stroke:#5F5570,color:#fff
    style STEP4 fill:#C17C4E,stroke:#A0663D,color:#fff
    style STEP5 fill:#B8A44C,stroke:#9A8A3D,color:#fff
    style M1 fill:#4A6FA5,stroke:#3A5A8A,color:#fff
    style H2 fill:#5B9279,stroke:#4A7A64,color:#fff
    style M2 fill:#5B9279,stroke:#4A7A64,color:#fff
    style D2 fill:#5B9279,stroke:#4A7A64,color:#fff
    style A3 fill:#7B6B8D,stroke:#5F5570,color:#fff
    style B3 fill:#7B6B8D,stroke:#5F5570,color:#fff
    style T3 fill:#7B6B8D,stroke:#5F5570,color:#fff
    style M3 fill:#7B6B8D,stroke:#5F5570,color:#fff
    style D3 fill:#7B6B8D,stroke:#5F5570,color:#fff
    style A4 fill:#C17C4E,stroke:#A0663D,color:#fff
    style B4 fill:#C17C4E,stroke:#A0663D,color:#fff
    style G4 fill:#C17C4E,stroke:#A0663D,color:#fff
    style L4 fill:#C17C4E,stroke:#A0663D,color:#fff
    style S4 fill:#C17C4E,stroke:#A0663D,color:#fff
    style L5 fill:#B8A44C,stroke:#9A8A3D,color:#fff
    style S5 fill:#B8A44C,stroke:#9A8A3D,color:#fff

    linkStyle default stroke:#4A5568,stroke-width:2px
```

The diagram below shows the same progression as a call chain, highlighting where the network boundary sits at each step:

```mermaid
sequenceDiagram
    participant Test as Test Runner
    participant Agent as Strands Agent
    participant LLM as Bedrock (Claude)
    participant GW as AgentCore Gateway
    participant Lambda as Lambda
    participant ML as SageMaker / Local ML

    rect rgb(74, 111, 165)
        Note over Test, ML: Step 1 — ML Unit Tests (no network)
        Test->>ML: predict(features)
        ML-->>Test: {issue_type, confidence}
    end

    rect rgb(91, 146, 121)
        Note over Test, ML: Step 2 — Gateway Layer 1 (no network)
        Test->>Lambda: DISPATCH["diagnose..."](campaign_id)
        Lambda->>ML: local .pkl inference
        ML-->>Lambda: prediction
        Lambda-->>Test: result JSON
    end

    rect rgb(123, 107, 141)
        Note over Test, ML: Step 3 — Agent E2E (network: Bedrock only)
        Test->>Agent: prompt
        Agent->>LLM: tool selection
        LLM-->>Agent: tool_use: diagnose_campaign_issue
        Agent->>ML: local tool → local .pkl
        ML-->>Agent: diagnosis
        Agent->>LLM: tool result
        LLM-->>Agent: final response
        Agent-->>Test: response text
    end

    rect rgb(193, 124, 78)
        Note over Test, ML: Step 4 — Deployed E2E (network: all AWS)
        Test->>Agent: prompt
        Agent->>LLM: tool selection
        LLM-->>Agent: tool_use
        Agent->>GW: MCP call (SigV4)
        GW->>Lambda: invoke
        Lambda->>ML: SageMaker endpoint
        ML-->>Lambda: prediction
        Lambda-->>GW: response
        GW-->>Agent: MCP result
        Agent-->>Test: response
    end
```

**What each step proves:**

| Step | Boundary | What passes means | What fails means |
|------|----------|-------------------|------------------|
| 1 | ML model in isolation | Model loaded, predictions are correct shape/class | Broken .pkl, missing training data |
| 2 | Handler + ML + data | Full tool dispatch works locally end-to-end | Data path broken, handler logic bug |
| 3 | Agent + Bedrock + local tools | LLM selects correct tools, tools return valid results | Bedrock auth issue, tool signature mismatch, prompt regression |
| 4 | Agent + Gateway + Lambda + SageMaker | Deployed infrastructure wired correctly | Deploy not run, IAM permissions, endpoint down |
| 5 | Lambda + SageMaker only | Inference pipeline works without the agent | Lambda code bug, SageMaker endpoint not serving |

### One-time setup

Train the ML models locally (generates training data + serializes `.pkl` files):

```bash
uv run python ml/generate_training_data.py
uv run python ml/train_model.py
uv run python ml/generate_recommendation_data.py
uv run python ml/train_recommendation_model.py
```

### Local tests (no AWS credentials needed)

```bash
# ML unit tests — XGBoost predict, feature builder, all 6 issue classes
uv run python -m pytest tests/ml/ -v

# Gateway Layer 1 — handler dispatch functions in-process
uv run python tests/test_gateway_e2e.py --local-only
```

### Agent E2E (requires Bedrock access only)

All 10 tools run locally as in-process Python. The only network call is to Bedrock for LLM reasoning.

```bash
uv run python tests/agent/test_agent.py
```

### Deployed E2E (requires Lambda + Gateway + SageMaker + Bedrock)

Prerequisites: deploy the stack first (see `deploy/README.md`):

```bash
uv run python deploy/deploy_lambda_zip.py
uv run python deploy/deploy_sagemaker_diagnosis.py
uv run python deploy/deploy_sagemaker_recommendation.py
uv run python deploy/deploy_multi_target_gateway.py
```

Then run the full 4-layer gateway test and Lambda smoke test:

```bash
# All 4 layers: local → Lambda → MCP → full agent
uv run python tests/test_gateway_e2e.py

# Or a specific layer (1-4)
uv run python tests/test_gateway_e2e.py --layer 2

# Lambda + SageMaker inference pipeline
uv run python lambda/smoke_test.py
uv run python lambda/smoke_test.py --campaign-id 1234
```

### Quick summary

| Step | Command | AWS? |
|------|---------|------|
| 1 | `uv run python -m pytest tests/ml/ -v` | No |
| 2 | `uv run python tests/test_gateway_e2e.py --local-only` | No |
| 3 | `uv run python tests/agent/test_agent.py` | Bedrock |
| 4 | `uv run python tests/test_gateway_e2e.py` | All |
| 5 | `uv run python lambda/smoke_test.py` | Lambda + SM |
