<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Campaign ML Models — Model Cards

This document covers both ML models in the AgentIQ pipeline:

1. [Campaign Diagnosis Model](#campaign-diagnosis-model) — identifies the root cause of underdelivery
2. [Recommendation Model](#recommendation-model) — selects the optimal action and predicts its parameter value

---

## Campaign Diagnosis Model

### Overview

| Property | Value |
| --- | --- |
| **Model type** | XGBoost multi-class classifier (`XGBClassifier`, `multi:softprob`) |
| **Task** | Classify the root cause of campaign underdelivery into one of 6 issue types |
| **Training data** | 1,200 synthetic examples — 200 per class (balanced) |
| **Test split** | 20% stratified (240 rows, 40 per class) |
| **Test accuracy** | 1.000 on synthetic data — see note below |
| **Trained** | 2026-03-23 |
| **Artifact** | `diagnosis_model.pkl` + `label_encoder.pkl` + `feature_names.json` |

> **Note on 1.000 accuracy:** Training data was synthetically generated with intentionally
> non-overlapping feature distributions per class. Perfect separation on synthetic data is
> expected. With real labeled campaign data, expect 75–90% accuracy and some inter-class
> confusion (especially between `bid_too_low` and `competitive_pressure`). Retraining on
> real outcomes from `measure-recommendation-outcome` is the path to production-quality scores.

---

### Output Classes

The model outputs a probability for each of the 6 issue types. The highest-probability class
is the `primary_issue`; others above 0.10 are surfaced as `secondary_issues`.

| Integer label | Issue type | When it applies |
| --- | --- | --- |
| 0 | `bid_too_low` | Current bid is clearly below the market CPM floor |
| 1 | `competitive_pressure` | Bid is near the floor but new competitors have entered, driving the floor up |
| 2 | `creative_fatigue` | Win rate is fine but CTR is declining late in the flight |
| 3 | `inventory_shortage` | Bid and targeting are healthy but not enough impressions exist in this segment |
| 4 | `pacing_issue` | Bid and win rate are fine but the campaign is far behind pace early in the flight |
| 5 | `targeting_too_narrow` | Targeting parameters limit the reachable audience pool despite a competitive bid |

---

### Hyperparameters

| Parameter | Value | Why |
| --- | --- | --- |
| `n_estimators` | 200 | Enough trees to learn subtle patterns without being slow to inference |
| `max_depth` | 5 | Limits tree complexity; prevents memorising individual training rows |
| `learning_rate` | 0.1 | Standard starting point; lower = more conservative boosting steps |
| `subsample` | 0.8 | Each tree sees 80% of rows — adds variance to reduce overfitting |
| `colsample_bytree` | 0.8 | Each tree sees 80% of features — forces trees to use different signals |
| `objective` | `multi:softprob` | Output probabilities for all 6 classes (not just the top class) |
| `random_state` | 42 | Fixed seed for reproducible training runs |

---

### Feature Importance

Scores are XGBoost's built-in `gain` importance — how much each feature reduces prediction
error across all 200 trees. Higher = more relied upon by the model.

| Rank | Feature | Score | Note — what this feature measures | What the score tells us |
| --- | --- | --- | --- | --- |
| 1 | `competitor_change_24h` | 0.2481 | Number of new competitors that entered the auction in the last 24 hours | Strongest single signal. Only `competitive_pressure` has high values (3–8). The model learned this is the clearest separator between competitive pressure and other issues. |
| 2 | `ctr` | 0.1473 | Click-through rate on the campaign's creatives | Distinguishes `creative_fatigue` — the only class where CTR falls to 0.002–0.005 vs. 0.004–0.012 for all other classes. |
| 3 | `delivery_variance` | 0.1149 | `delivery_pct − expected_pct` — how far behind or ahead of expected pace | A broad health signal used across most classes. Negative values indicate underdelivery; the depth of the gap separates critical from moderate issues. |
| 4 | `demand_supply_ratio` | 0.1073 | Ratio of impression demand to available supply in the market segment | Primary signal for `inventory_shortage`, which is the only class with ratios of 2.0–3.5. Normal markets sit at 0.8–1.8. |
| 5 | `win_rate` | 0.1031 | Fraction of auctions the campaign wins | Low for bid-related issues (0.03–0.17), high for fatigue and pacing issues (0.22–0.35). Corroborates the bid_to_floor_ratio signal. |
| 6 | `days_elapsed_pct` | 0.0993 | How far through the campaign flight we are (`days_elapsed / days_total`) | Separates `creative_fatigue` (late in flight: 0.55–0.90) from `pacing_issue` (early in flight: 0.10–0.35). Without this, the two would look similar. |
| 7 | `bid_to_floor_ratio` | 0.0891 | `current_bid / cpm_floor` — how competitive the bid is relative to the market floor | The original rule-based logic treated this as the *only* signal. The model correctly keeps it important but ranks 6 features above it — bid alone is insufficient for diagnosis. |
| 8 | `competitor_count` | 0.0430 | Total number of active competitors in the market segment | Secondary signal for `competitive_pressure` (15–25 competitors vs. 4–18 for other classes). Reinforces `competitor_change_24h`. |
| 9 | `cpm_change_pct` | 0.0227 | How much the CPM floor has risen in the last 24 hours | Supporting signal for `competitive_pressure` — a rising floor confirms new demand, not just noise. |
| 10 | `geo_encoded` | 0.0097 | Integer encoding of the campaign's DMA market | Near zero. Geography does not drive diagnosis — a Chicago campaign and a Dallas campaign with the same metrics get the same diagnosis. This is the expected and correct behaviour. |
| 11 | `delivery_pct` | 0.0061 | Raw delivery percentage (impressions delivered / goal) | Low — redundant with `delivery_variance`, which already captures the gap from expected. |
| 12 | `expected_pct` | 0.0045 | Expected delivery at this point in the flight | Low — redundant with `delivery_variance`. |
| 13 | `days_remaining` | 0.0039 | Absolute days left in the campaign flight | Low — `days_elapsed_pct` already captures flight position in a normalised way. |
| 14 | `industry_encoded` | 0.0009 | Integer encoding of the campaign's industry vertical | Near zero. Industry does not drive diagnosis — an automotive and a healthcare campaign with the same metrics get the same diagnosis. Correct behaviour. |
| 15 | `budget_consumed_pct` | 0.0000 | Fraction of budget spent (proxy for delivery) | **Zero contribution.** Completely redundant with `delivery_variance`. Candidate for removal in the next training iteration to simplify the feature set. |

---

### Key Takeaways for the Next Iteration

1. **`budget_consumed_pct` can be dropped.** It contributed zero importance. Removing it
   simplifies `build_features()` in `diagnose_campaign_ml.py` without affecting model quality.

2. **`delivery_pct` and `expected_pct` can potentially be dropped** in favour of keeping only
   `delivery_variance` (their difference), which ranked 3rd. Test this with real data.

3. **`bid_to_floor_ratio` ranked 7th, not 1st.** This is the key insight over the original
   rule-based approach: bid competitiveness matters, but market dynamics (`competitor_change_24h`,
   `demand_supply_ratio`) and engagement signals (`ctr`, `win_rate`) are equally or more important.

4. **Retrain with real outcome data** from the `measure-recommendation-outcome` Lambda once
   campaigns have been diagnosed and interventions applied. Real data will likely show more
   overlap between classes, which is healthy — it means the model is learning subtle patterns
   rather than cleanly synthetic ones.

---

## Recommendation Model

The recommendation model is a two-stage pipeline that runs after the diagnosis model. Given a diagnosed campaign, it answers: (1) what action to take, and (2) what specific parameter value to use.

### Model Summary

| Property | Value |
| --- | --- |
| **Stage 2 — Action Classifier** | `RandomForestClassifier` (scikit-learn) |
| **Stage 3 — Value Regressors** | 5 × `GradientBoostingRegressor` (scikit-learn), one per action type |
| **Task** | Select optimal action type (5 classes), then predict the optimal numeric parameter |
| **Training data** | 1,250 synthetic examples — 250 per class (balanced) |
| **Test split** | 20% stratified for classifier, 20% per action for regressors |
| **Trained** | 2026-03-25 |
| **Classifier artifact** | `recommendation_model.pkl` + `recommendation_encoder.pkl` + `recommendation_features.json` |
| **Regressor artifacts** | `regressor_bid_adjustment.pkl`, `regressor_targeting_expansion.pkl`, `regressor_creative_refresh.pkl`, `regressor_pacing_adjustment.pkl`, `regressor_budget_reallocation.pkl` + `regression_features.json` |
| **Training script** | `ml/train_recommendation_model.py` |
| **Data generator** | `ml/generate_recommendation_data.py` |

> **Note on synthetic data:** Like the diagnosis model, training data was synthetically generated
> with domain-knowledge formulas. Regression targets (e.g., optimal bid) are computed from
> market conditions, not observed outcomes. With real outcome data from
> `measure-recommendation-outcome`, expect improved calibration of predicted values.

---

### Pipeline Architecture

```text
Diagnosis Model (XGBoost)          Recommendation Classifier (RandomForest)     Per-Action Regressor (GradientBoosting)
──────────────────────────         ────────────────────────────────────────     ────────────────────────────────────────
15 features → 6 issue types   →   19 features → 5 action types            →   25 features → specific parameter value
                                   (adds diagnosed_issue, confidence,           (adds current_bid, cpm_floor, cpm_p75,
                                    historical_success, budget_remaining)         budget_daily, budget_remaining, imps)
```

The classifier uses 19 features (the original 15 diagnosis features + 4 recommendation-specific ones) to pick the action type. The regressors use 25 features (19 + 6 absolute-value features) because predicting a specific dollar amount or multiplier requires absolute figures, not just ratios.

---

### Output Classes (Classifier)

| Integer label | Action type | When it applies |
| --- | --- | --- |
| 0 | `bid_adjustment` | `bid_too_low` or `competitive_pressure` diagnosed; bid-to-floor ratio 0.60–1.00; win rate 0.03–0.15 |
| 1 | `budget_reallocation` | Any issue type; moderate delivery gap; mid-flight; lower diagnosis confidence (0.50–0.75) |
| 2 | `creative_refresh` | `creative_fatigue` diagnosed; high win rate (0.22–0.38); very low CTR (0.001–0.005); late in flight (55–92%) |
| 3 | `pacing_adjustment` | `pacing_issue` diagnosed; early in flight (8–40%); large delivery gap; high budget remaining |
| 4 | `targeting_expansion` | `targeting_too_narrow` or `inventory_shortage` diagnosed; competitive bid but high demand/supply ratio (1.5–3.5) |

Integer labels follow `LabelEncoder` alphabetic sort order.

---

### Regressor Targets

Each regressor is trained only on rows belonging to its action type (250 rows each) and predicts a different unit:

| Action type | Artifact | Target | Unit | Example output |
| --- | --- | --- | --- | --- |
| `bid_adjustment` | `regressor_bid_adjustment.pkl` | Optimal CPM bid | CPM $ | $6.42 |
| `targeting_expansion` | `regressor_targeting_expansion.pkl` | Geo expansion factor | Multiplier | 1.4 (= 40% broader) |
| `creative_refresh` | `regressor_creative_refresh.pkl` | Creative rotation fraction | Fraction 0–1 | 0.6 (= swap 60%) |
| `pacing_adjustment` | `regressor_pacing_adjustment.pkl` | Daily budget multiplier | Multiplier | 1.35 (= +35%) |
| `budget_reallocation` | `regressor_budget_reallocation.pkl` | Peak-hour budget shift | Fraction 0–1 | 0.25 (= shift 25%) |

---

### Classification Features (19)

The first 15 features are shared with the diagnosis model. Four are recommendation-specific additions:

| # | Feature | Source | Description |
| --- | --- | --- | --- |
| 1–15 | *(same as diagnosis model)* | Campaign metrics | `bid_to_floor_ratio`, `win_rate`, `delivery_pct`, `expected_pct`, `delivery_variance`, `days_elapsed_pct`, `days_remaining`, `competitor_count`, `competitor_change_24h`, `demand_supply_ratio`, `cpm_change_pct`, `ctr`, `industry_encoded`, `geo_encoded`, `budget_consumed_pct` |
| 16 | `diagnosed_issue_encoded` | Diagnosis model | Issue type from Stage 1 (0–5) |
| 17 | `diagnosis_confidence` | Diagnosis model | Stage 1 model confidence score |
| 18 | `historical_success_rate` | Historical data | Success rate for same industry + geo historically |
| 19 | `budget_remaining_pct` | Campaign data | `1 - (budget_spent / budget_total)` |

### Additional Regression Features (+6 = 25 total)

Regressors need absolute values to predict specific dollar amounts and multipliers:

| # | Feature | Description |
| --- | --- | --- |
| 20 | `current_bid` | Absolute current CPM bid in dollars |
| 21 | `market_cpm_floor` | Absolute CPM floor from market intelligence |
| 22 | `market_cpm_p75` | 75th percentile CPM from market intelligence |
| 23 | `budget_daily` | Daily budget cap in dollars |
| 24 | `budget_remaining` | Absolute remaining budget in dollars |
| 25 | `impressions_remaining` | Impressions still needed to hit goal |

---

### Classifier Hyperparameters (RandomForest)

| Parameter | Value | Why |
| --- | --- | --- |
| `n_estimators` | 300 | Larger ensemble than diagnosis model; more classes to separate |
| `max_depth` | 8 | Deeper than diagnosis (5) — action selection depends on more feature interactions |
| `min_samples_split` | 5 | Prevents splits on tiny groups |
| `min_samples_leaf` | 2 | Minimum samples in a leaf |
| `n_jobs` | -1 | Parallel training on all cores |
| `random_state` | 42 | Fixed seed for reproducibility |

### Regressor Hyperparameters (GradientBoosting, shared across all 5)

| Parameter | Value | Why |
| --- | --- | --- |
| `n_estimators` | 200 | Handles small datasets (250 rows per action) well |
| `max_depth` | 4 | Shallower than classifier to prevent overfitting on 250 rows |
| `learning_rate` | 0.1 | Standard conservative step size |
| `subsample` | 0.8 | Stochastic boosting; each tree sees 80% of rows |
| `random_state` | 42 | Fixed seed for reproducibility |

---

### Deployment Paths

| Path | When | How |
| --- | --- | --- |
| **Local pkl** (default) | Development, testing | Models lazy-loaded from `ml/model/` on first call, cached in memory. Entry points: `predict_action(features)` and `predict_value(action_type, features)` in `ml/recommendation_ml.py` |
| **SageMaker endpoint** | Production | Set `SAGEMAKER_RECOMMENDATION_ENDPOINT_NAME` env var. Classification: POST 19 features as JSON. Regression: POST 25 features + `{"mode": "regression", "action_type": "<type>"}`. Custom container: `campaign-opt-inference` image. |

Both paths are consumed by:
- `lambda/handler.py` → `generate_recommendation(campaign_id)`
- `agent/tools/analysis.py` → `generate_recommendation` Strands tool

---

### Design Decisions and Next Iteration

1. **Why RandomForest instead of XGBoost?** Deliberate choice to use a different ensemble
   method from the diagnosis model. If both stages used XGBoost, correlated errors in Stage 1
   could propagate unchecked into Stage 2. RandomForest's bagging approach provides diversity.

2. **Why separate regressors instead of one multi-output model?** Each action type has a
   fundamentally different target variable (dollars vs. multipliers vs. fractions). A single
   regressor would conflate these units. Per-action models also allow independent retraining
   as outcome data arrives at different rates per action type.

3. **Retrain regressors first.** The classifier's action selection is likely robust (discrete
   choice), but the regressors' predicted values (exact bid amounts, exact multipliers) are
   the most sensitive to synthetic-vs-real data gaps. Prioritize regressor retraining once
   `measure-recommendation-outcome` collects real before/after metrics.
