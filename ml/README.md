<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# ML — Machine Learning Pipeline

> Traditional ML models (XGBoost, RandomForest, GradientBoosting) for campaign diagnosis and recommendation optimization.

## Why Traditional ML Instead of the LLM?

This project uses Claude (GenAI) for orchestration and communication, but relies on traditional ML for predictions. The split is deliberate:

| Requirement | Why Traditional ML Wins |
|---|---|
| **Reproducibility** | Same input always produces the same diagnosis. An LLM would give different confidence scores on each call. |
| **Latency** | XGBoost inference is <10ms. LLM inference is 2-10s. For a 10-tool agent loop, ML keeps total latency manageable. |
| **Auditability** | Feature importance and decision paths are inspectable. Regulators and clients can verify why a diagnosis was made. |
| **Cost** | ML inference is effectively free at PoC scale. Each LLM call costs tokens; offloading numerical work to ML reduces spend. |
| **Precision** | GBR regression predicts $5.49 CPM from 25 features. LLMs struggle with precise numerical optimization. |

The LLM's job is to understand the trader's question, decide which tools (including ML) to call, and synthesize results into actionable advice. It never predicts confidence scores or optimal bid values directly.

## Models

| Model | File | Algorithm | Purpose |
|-------|------|-----------|---------|
| Campaign Diagnosis | `diagnose_campaign_ml.py` | XGBoost Classifier | Classify campaign delivery issues |
| Recommendation | `recommendation_ml.py` | RandomForest + GradientBoosting | Predict optimal actions and values |

## Pipeline

```
generate_training_data.py  →  train_model.py  →  model/*.pkl
generate_recommendation_data.py  →  train_recommendation_model.py  →  model/*.pkl
```

## Structure

```
ml/
├── diagnose_campaign_ml.py           # Diagnosis model logic
├── recommendation_ml.py              # Recommendation model logic
├── generate_training_data.py         # Synthetic training data generator
├── generate_recommendation_data.py   # Recommendation training data
├── train_model.py                    # Train diagnosis model
├── train_recommendation_model.py     # Train recommendation model
├── data/                             # Generated CSVs (gitignored)
├── model/                            # Serialized .pkl models (gitignored)
└── sagemaker/                        # SageMaker inference containers
    ├── inference.py                  # Diagnosis endpoint (Flask)
    ├── recommendation_inference.py   # Recommendation endpoint (Flask)
    ├── build-inference-container.sh  # Docker build script
    └── requirements.txt              # Container dependencies
```

## Usage

```bash
# Generate training data
uv run python ml/generate_training_data.py
uv run python ml/generate_recommendation_data.py

# Train models
uv run python ml/train_model.py
uv run python ml/train_recommendation_model.py

# Deploy to SageMaker
uv run python deploy/deploy_sagemaker_diagnosis.py
uv run python deploy/deploy_sagemaker_recommendation.py
```
