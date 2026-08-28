<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Picking Your ML Model: A Practical Guide

*When to use XGBoost, RandomForest, or GradientBoosting — and why feature selection matters more than any of them.*

This document captures the design decisions and rationale behind the model choices in the Campaign Optimization Agent's three-stage ML pipeline. It's written as a reference for anyone adapting this pattern to their own use case.

## Context: Why Traditional ML in a GenAI Project?

This project uses Claude (a large language model) as the agent's brain for understanding queries, selecting tools, and explaining results. But the actual predictions - "what's wrong?" and "what value?" - are handled by purpose-built ML models. The reasons:

1. **Determinism** - Same campaign features always produce the same diagnosis. LLM outputs vary per call.
2. **Speed** - XGBoost classifies in <10ms. Asking the LLM to classify would add 3-5 seconds per prediction.
3. **Auditability** - Feature importance shows exactly what drove the diagnosis. "The model weighted `bid_to_floor_ratio` at 0.25" is auditable; "the AI determined" is not.
4. **Precision** - GradientBoosting regresses to $5.49 CPM from 25 features. LLMs cannot reliably do constrained numerical optimization.
5. **Cost** - ML inference is effectively free; LLM inference costs per-token.

The models below are the "calculators" that the GenAI agent calls as tools. The agent's job is to understand what the trader wants, call the right model with the right inputs, and explain the result.

---

## Table of Contents

- [The Three Problems, Three Models](#the-three-problems-three-models)
- [Decision Flowchart: Which Model to Use](#decision-flowchart-which-model-to-use)
- [XGBoost (Boosting) — Deep Dive](#xgboost-boosting--deep-dive)
- [RandomForest (Bagging) — Deep Dive](#randomforest-bagging--deep-dive)
- [GradientBoosting Regression — Deep Dive](#gradientboosting-regression--deep-dive)
- [Feature Selection: The Step That Matters Most](#feature-selection-the-step-that-matters-most)
- [Feature Interactions: When Combinations Matter More Than Individual Features](#feature-interactions-when-combinations-matter-more-than-individual-features)
- [Handling Multi-Issue Diagnosis (Correlated Problems)](#handling-multi-issue-diagnosis-correlated-problems)
- [Summary: Model Selection Cheat Sheet](#summary-model-selection-cheat-sheet)

---

## The Three Problems, Three Models

Our pipeline solves three distinct problems. Each requires a different model because the *nature of the question* differs:

| Stage | Question | Model | Why This Model |
|---|---|---|---|
| 1. Diagnosis | "What's wrong?" | XGBoost | Sharp decision boundaries, maximum accuracy |
| 2. Classification | "What to do?" | RandomForest | Calibrated probabilities, multiple valid answers |
| 3. Regression | "How much?" | GradientBoosting | Continuous value prediction, per-action specialization |

### Confirmed Results (Campaign 4782)

| Stage | Model | Input | Output | Result |
|---|---|---|---|---|
| 1. Diagnosis | XGBoost | 15 features | Issue type (6 classes) | `bid_too_low` — 99.7% confidence |
| 2. Classification | RandomForest | 19 features | Action type (5 classes) | `bid_adjustment` — 97.7% confidence |
| 3. Regression | GradientBoosting | 25 features | Optimal value | `$5.49 CPM` — ML-predicted bid |

---

## Decision Flowchart: Which Model to Use

```
START: "I have a structured data problem"
  |
  v
Is it CLASSIFICATION (predict a category)
or REGRESSION (predict a number)?
  |
  +-- REGRESSION --> GradientBoosting Regressor
  |                  (or XGBoost Regressor, or RandomForest Regressor)
  |                  See "GradientBoosting Regression" section below.
  |
  +-- CLASSIFICATION --> Continue:
          |
          v
    Do you need CALIBRATED PROBABILITIES?
    (i.e., confidence scores matter as much as the prediction;
     downstream decisions depend on the probability distribution,
     not just the top class)
          |
          +-- YES --> RandomForest
          |           Examples:
          |           - Ranking multiple valid options
          |           - Risk scoring with threshold-based actions
          |           - Agent pipelines where confidence is surfaced to users
          |           - Medical triage (70% vs 95% changes treatment)
          |
          +-- NO --> Do you need MAXIMUM ACCURACY?
                     (getting the right label matters most;
                      confidence score is secondary)
                       |
                       +-- YES --> XGBoost
                       |           Examples:
                       |           - Root cause diagnosis (what's THE problem?)
                       |           - Fraud detection (fraud or not?)
                       |           - Spam classification
                       |           - Any binary/categorical where the label is the decision
                       |
                       +-- NOT SURE --> Tiebreakers:
                               |
                               v
                         +------------------------------------------+
                         | TIEBREAKER QUESTIONS                     |
                         |                                          |
                         | 1. Data NOISY or SMALL?                  |
                         |    YES -> RandomForest (robust to noise, |
                         |           harder to overfit)              |
                         |    NO  -> XGBoost (squeezes more signal) |
                         |                                          |
                         | 2. TIME TO TUNE hyperparameters?         |
                         |    NO  -> RandomForest (good defaults,   |
                         |           fewer knobs)                   |
                         |    YES -> XGBoost (more knobs = higher   |
                         |           ceiling with tuning)           |
                         |                                          |
                         | 3. FAST TRAINING needed?                 |
                         |    YES -> RandomForest (parallelizable)  |
                         |    NO  -> XGBoost (sequential, slower)   |
                         |                                          |
                         | 4. INFERENCE SPEED critical?             |
                         |    Both are fast (<10ms). Tie.           |
                         +------------------------------------------+
```

### The One-Sentence Rule

> **If you care about the ranking/confidence across all classes, use RandomForest. If you care about the single best answer, use XGBoost.**

---

## XGBoost (Boosting) — Deep Dive

### How It Works

XGBoost builds decision trees **sequentially**. Each new tree learns from the mistakes of all previous trees:

```
Training Data: 1,200 rows x 15 features
        |
        v
     Tree 1 --> predicts --> residual errors (what Tree 1 got wrong)
                                    |
                                    v
                                 Tree 2 --> predicts --> residual errors
                                                              |
                                                              v
                                                           Tree 3 --> ...

Combined prediction = Tree 1 + Tree 2 + Tree 3 + ... + Tree N
                      (each tree adds a small correction)
```

**Tree 1** makes a first attempt at classifying all rows. It gets most right but makes mistakes.

**Tree 2** doesn't see the original labels. It sees "how wrong was Tree 1 about each row?" and tries to predict those errors. If Tree 1 confused `competitive_pressure` with `bid_too_low`, Tree 2 learns to distinguish them.

**Tree 3** fixes what Tree 1 + Tree 2 still get wrong. And so on for 100+ trees.

### Why It Produces Sharp Decisions

Because each tree targets exactly what's still wrong, the model converges aggressively on the right answer for every training example. After 100 trees of focused correction, even rare edge cases get attention.

**Analogy:** 100 reviewers read a paper sequentially. Reviewer 1 reads the whole thing. Reviewer 2 only looks at the issues Reviewer 1 missed. Reviewer 3 only looks at what's still wrong after Reviewer 1 + 2. By Reviewer 100, every subtle issue has been addressed.

### Why It Can Produce Overconfident Probabilities

The trees are **correlated** — each one trained on the previous one's errors. They tend to converge aggressively on a single answer. When XGBoost says 99.7% confidence, that's because all 100 trees were systematically steered toward that answer. The probability reflects the **model's certainty**, not necessarily the **true ambiguity** in the data. Dissent gets corrected away by later trees.

### When to Use XGBoost

- Root cause diagnosis ("what's THE problem?")
- Fraud detection (binary: fraud or not)
- Spam classification
- Any classification where **getting the right label** matters more than the confidence distribution
- When you have time to tune hyperparameters (learning rate, max depth, regularization)

---

## RandomForest (Bagging) — Deep Dive

### How It Works

RandomForest builds decision trees **independently and in parallel**. Each tree gets a different random view of the data:

```
Training Data: 1,250 rows x 19 features
                    |
        +-----------+-----------+
        v           v           v
     Tree 1      Tree 2      Tree 3  ...  Tree 100
   ~1,250 rows  ~1,250 rows  ~1,250 rows
   (bootstrap)  (bootstrap)  (bootstrap)
   ~63% unique  ~63% unique  ~63% unique
   4 features   4 features   4 features
   per split    per split    per split

Final prediction = MAJORITY VOTE across all 100 trees
Probability = fraction of trees voting for each class
```

Each tree gets:

1. **Random rows** — a bootstrap sample (random sample *with replacement*) of the training data. Each tree sees ~63% unique rows and ~37% duplicates. Different trees see different subsets.

2. **Random features** — at each split within a tree, it only considers a random subset of features (typically sqrt(n), e.g., 4 out of 19). So even if two trees get similar rows, they make different split decisions.

### Root Nodes Vary Across Trees

Because each tree sees different features at each split, different trees pick **different root features**:

```
Tree 1 (sees: bid_to_floor_ratio, ctr, competitor_count, days_remaining)
  --> Root: bid_to_floor_ratio < 0.85?

Tree 2 (sees: win_rate, delivery_variance, demand_supply_ratio, budget_remaining_pct)
  --> Root: win_rate < 0.12?

Tree 3 (sees: competitor_change_24h, cpm_change_pct, ctr, diagnosed_issue_encoded)
  --> Root: diagnosed_issue_encoded == 0?
```

This diversity is the whole point. If all 100 trees had the same root node and made the same decisions, averaging them would be pointless. The randomness forces each tree to find **different patterns** in the data. When you average all 100 perspectives, robust patterns survive and noise cancels out.

### Why It Produces Calibrated Probabilities

97.7% confidence means **97 out of 100 independent trees agreed** on `bid_adjustment`. The remaining 3 trees genuinely saw different patterns in their feature subsets and voted for alternatives. That 2.3% minority isn't noise — it reflects real ambiguity in the data where context could tip the decision the other way.

This is fundamentally different from XGBoost's 99.7%, where later trees systematically correct dissent. RandomForest preserves dissent as probability mass across alternatives.

### When to Use RandomForest

- Action classification where multiple options may be valid
- Risk scoring with threshold-based downstream actions
- Agent pipelines where confidence scores are surfaced to users
- Medical/legal domains where calibrated uncertainty matters
- When data is noisy or small (robust to overfitting)
- When you need good results with minimal hyperparameter tuning

---

## GradientBoosting Regression — Deep Dive

### How It Works

GradientBoosting for regression works the same way as XGBoost for classification — sequential trees correcting each other's errors — but instead of predicting a class label, it predicts a **continuous number** (e.g., the optimal bid in CPM dollars).

```
Tree 1: predicts bid = $5.00 for all rows (the mean)
         --> actual for Row 42 was $5.50, so residual = +$0.50

Tree 2: predicts the residuals (how far off Tree 1 was)
         --> learns "when market_cpm_floor > $5.10, add $0.40"

Tree 3: predicts remaining residuals after Tree 1 + Tree 2
         --> learns "when competitor_count > 10, add $0.08"

Final prediction = $5.00 + $0.40 + $0.08 + ... = $5.49
```

### Why Per-Action Regressors (5 Separate Models)

We train 5 separate GradientBoosting regressors — one per action type — rather than one combined model. Three reasons:

1. **Different target units.** Bid amounts (dollars), expansion factors (multipliers), rotation percentages (fractions). Mixing them makes error metrics meaningless.

2. **Different feature importance.** For `bid_adjustment`, `market_cpm_floor` dominates (98% importance). For `creative_refresh`, `ctr` dominates (82%). A single model would obscure these per-action dynamics.

3. **Independent tuning.** Each action type can have different hyperparameters, different feature subsets, different training data filters — without affecting the others.

### Regression Results

| Action Type | Target | Unit | MAE | R-squared | Dominant Feature |
|---|---|---|---|---|---|
| `bid_adjustment` | recommended_bid | CPM $ | 0.11 | 0.99 | `market_cpm_floor` (98%) |
| `targeting_expansion` | geo_expansion_factor | multiplier | 0.07 | 0.68 | — |
| `creative_refresh` | creative_rotation_pct | fraction | 0.03 | 0.82 | `ctr` (82%) |
| `pacing_adjustment` | daily_budget_multiplier | multiplier | 0.04 | 0.56 | `delivery_variance` (59%) |
| `budget_reallocation` | peak_shift_pct | fraction | 0.02 | 0.62 | — |

The `bid_adjustment` regressor achieves R-squared=0.99 because bid recommendations are tightly anchored to `market_cpm_floor` — once you know the floor, the optimal bid is highly predictable. The `pacing_adjustment` regressor has lower R-squared=0.56 because delivery variance is a noisier signal.

---

## Feature Selection: The Step That Matters Most

> **The model can only be as good as the features you give it. No algorithm compensates for missing or irrelevant features.**

Feature selection is arguably the most important step in the entire ML pipeline. It determines the **ceiling** of your model's performance. Hyperparameter tuning and model architecture only get you closer to that ceiling — they can't raise it.

### Why Feature Selection Matters

1. **Irrelevant features add noise.** If you include `campaign_name` as a feature, the model will try to learn patterns from it. With enough trees, it will find spurious correlations ("campaigns starting with 'H' tend to be bid_too_low" — because Honda is in the dataset). These correlations don't generalize.

2. **Correlated features dilute importance.** If you include both `budget_spent` and `budget_consumed_pct` (which is just `budget_spent / budget_total`), the model splits its attention between them. Neither feature gets credited with its full importance, and the feature importance chart becomes misleading.

3. **Missing features create a hard ceiling.** Our model's biggest insight came from including `competitor_change_24h` — how many competitors entered the market in the last 24 hours. The rule-based system never considered this feature. No amount of hyperparameter tuning on the original feature set would have discovered this signal — it wasn't in the data.

4. **Fewer features = faster, simpler, more interpretable.** A model with 15 well-chosen features is better than a model with 150 features where 135 are noise. Fewer features means faster inference, simpler deployment, easier debugging, and clearer explanations to stakeholders.

### Feature Selection Techniques

#### 1. Domain Knowledge (Start Here)

The most important feature selection tool is **talking to domain experts**. In our case, traders told us:

- "I always check bid vs market floor first" → `bid_to_floor_ratio`
- "New competitors showing up changes everything" → `competitor_change_24h`
- "CTR dropping usually means creative fatigue" → `ctr`

Domain knowledge tells you which features are **causally related** to the outcome, not just correlated. Start with the features your experts check manually.

#### 2. Feature Importance From the Model Itself

After training, both XGBoost and RandomForest report **feature importance** — how much each feature contributed to predictions:

```
Our XGBoost Diagnosis Model (top features by gain):
  competitor_change_24h   0.31  <-- biggest surprise
  ctr                     0.18
  delivery_variance       0.14
  demand_supply_ratio     0.11
  competitor_count        0.08
  cpm_change_pct          0.06
  bid_to_floor_ratio      0.05  <-- ranked 7th, not 1st!
  ...
```

The biggest surprise: `bid_to_floor_ratio` ranked 7th, not 1st. The rule-based system treated bid as the **only** signal. The ML model discovered that market dynamics — competitor changes, CTR trends, delivery variance — are equally or more important. **That's the whole point of ML over rules.**

#### 3. Ablation Testing (Remove and Measure)

Systematically remove features and measure the impact on accuracy:

```
All 15 features:                         accuracy = 0.99
Remove competitor_change_24h:            accuracy = 0.91  (-0.08)  <-- important!
Remove bid_to_floor_ratio:               accuracy = 0.97  (-0.02)  <-- less than expected
Remove industry_encoded:                 accuracy = 0.99  (-0.00)  <-- can probably drop
```

If removing a feature doesn't hurt accuracy, it's likely noise or redundant with another feature. Drop it.

#### 4. Correlation Analysis (Remove Redundancy)

Check for highly correlated features:

```
budget_spent vs budget_consumed_pct:     correlation = 0.98  <-- redundant, keep one
win_rate vs delivery_pct:                correlation = 0.72  <-- related but different
competitor_count vs demand_supply_ratio:  correlation = 0.45  <-- both useful
```

When two features are correlated above ~0.90, keep the one that's more interpretable or has higher importance. The other is adding noise, not signal.

#### 5. Recursive Feature Elimination (Automated)

Scikit-learn provides `RFE` (Recursive Feature Elimination): train the model, remove the least important feature, retrain, repeat until you reach the desired feature count. Useful when you have many features and want to automate the process.

### Feature Selection in Our Pipeline

| Stage | Features | How We Selected Them |
|---|---|---|
| Diagnosis (XGBoost) | 15 | Domain knowledge (what traders check) + iterative testing |
| Classification (RandomForest) | 19 | 15 base + 4 derived from diagnosis output (issue type, confidence, success rate, budget remaining) |
| Regression (GradientBoosting) | 25 | 19 classification + 6 market/budget features needed for value prediction |

Each stage **builds on** the previous stage's features. The classification features include the diagnosis output. The regression features include the classification features plus market-specific data needed for value sizing. This cascading feature design ensures each stage has the right information for its specific task.

### The Feature Engineering Mindset

> **Spend your time on feature engineering, not hyperparameter tuning.** The features you choose determine your ceiling. The algorithm just gets you closer to it.

Questions to ask when designing features:

- **What would a human expert look at?** Start there.
- **What data is available at inference time?** Don't train on features you won't have when the model runs in production.
- **Are any features leaking the label?** If a feature is derived from the outcome (e.g., `was_bid_adjusted` as a feature for diagnosing `bid_too_low`), the model gets artificially perfect accuracy that won't generalize.
- **Can you create derived features?** `bid_to_floor_ratio` (derived from `current_bid / market_floor`) is more predictive than either raw value alone because it captures the **relationship** between them.
- **What time horizon matters?** `competitor_count` (snapshot) vs `competitor_change_24h` (trend) — the trend was more predictive than the snapshot in our model.

---

## Feature Interactions: When Combinations Matter More Than Individual Features

In the real world, a single feature alone is often meaningless — but *combined* with another feature, it becomes the strongest signal. This is called a **feature interaction**.

### The Problem

With 15 features, there are:
- 105 possible 2-feature combinations
- 455 possible 3-feature combinations
- 3,003 possible 4-feature combinations

You can't manually test them all. And individual feature importance can be misleading — a feature might rank low on its own but be critical in combination with another.

### Example: Interaction in Our Pipeline

```
current_bid = $4.20    --> meaningless alone (is that high or low?)
market_floor = $5.10   --> meaningless alone (relative to what?)
bid_to_floor_ratio = 0.82  --> "18% below market" --> strong signal
```

The ratio captures the **relationship** between two features. Neither value alone tells you the campaign is in trouble. Together, they're the most actionable signal in the dataset.

Similarly:
```
competitor_count = 12      --> is that a lot?
competitor_change_24h = +3 --> 3 new entrants in 24 hours --> market is heating up
```

The *trend* (change) is more predictive than the *snapshot* (count). This is a temporal interaction — the relationship between a feature and its own history.

### Five Levels of Handling Feature Interactions

Practitioners use a ladder of techniques, starting simple and escalating as needed:

#### Level 1: Let the Tree Handle It (Free)

Decision trees **naturally discover interactions** — that's what a tree *is*. Each path from root to leaf is an interaction:

```
Is bid_to_floor_ratio < 0.85?          (feature 1)
  YES --> Is competitor_count > 10?     (feature 2)
    YES --> Is days_remaining < 3?      (feature 3)
      YES --> bid_too_low (99.8%)       <-- 3-feature interaction
```

That path encodes: "low bid + high competition + nearly out of time = almost certainly bid_too_low." The model found this **automatically** — no manual feature engineering needed.

This is why tree-based models (XGBoost, RandomForest, GradientBoosting) are the default for structured data. They discover interactions that linear models (logistic regression) would miss entirely.

**When this is enough:** Most problems. If your tree model is performing well, it's already capturing the important interactions.

#### Level 2: Engineer Derived Features Manually (Moderate Effort)

When domain experts know specific interactions matter, create them explicitly:

```python
# Ratios capture relative relationships
features["bid_to_floor_ratio"] = current_bid / market_floor
features["delivery_variance"]  = delivery_pct - expected_pct
features["budget_consumed_pct"] = spend / budget_total

# Trends capture temporal dynamics
features["competitor_change_24h"] = competitors_now - competitors_yesterday
features["cpm_change_pct"] = (cpm_now - cpm_yesterday) / cpm_yesterday
```

Why bother if trees can find interactions? Because **explicit features are easier for the model to use**. A tree can discover that `bid < floor` matters, but it takes many splits to approximate a ratio. Giving it `bid_to_floor_ratio` directly lets the tree use one clean split instead of a chain of approximations.

**Rule of thumb:** If a domain expert would mentally compute a ratio or difference when looking at two features, create that derived feature explicitly.

#### Level 3: Automated Interaction Discovery (More Effort)

When you have many features and suspect hidden interactions but don't know which:

**3a. Polynomial Feature Generation** — Create all pairwise combinations automatically:

```python
from sklearn.preprocessing import PolynomialFeatures

# Takes 15 features, creates all 2-way interactions
poly = PolynomialFeatures(degree=2, interaction_only=True)
X_interactions = poly.fit_transform(X)
# Now 15 original + 105 interaction features + 1 bias = 121 features
```

Then use feature selection (importance, ablation) to keep only the interactions that matter and drop the rest.

**Warning:** This explodes the feature space. 15 features becomes 121. 25 features becomes 351. Most are noise. Always follow with aggressive feature selection.

**3b. SHAP Interaction Values** — SHAP (SHapley Additive exPlanations) can measure **interaction effects** between pairs of features — not just individual importance:

```python
import shap

explainer = shap.TreeExplainer(model)
shap_interactions = explainer.shap_interaction_values(X)

# Shows: "bid_to_floor_ratio and competitor_count TOGETHER
#         contribute 0.15 to predicting bid_too_low --
#         more than either feature alone"
```

This tells you which feature *pairs* have synergistic effects. If two features together are much more predictive than the sum of their individual contributions, that's a real interaction worth keeping.

**3c. Recursive Feature Elimination with Cross-Validation (RFECV)** — Let the algorithm decide which features to keep:

```python
from sklearn.feature_selection import RFECV

selector = RFECV(estimator=model, step=1, cv=5, scoring="accuracy")
selector.fit(X, y)

print(f"Optimal features: {selector.n_features_}")
print(f"Keep: {[f for f, s in zip(feature_names, selector.support_) if s]}")
print(f"Drop: {[f for f, s in zip(feature_names, selector.support_) if not s]}")
```

#### Level 4: Regularization — Dim Noisy Features Automatically (Low Effort)

Instead of removing features upfront, train the model and **penalize complexity** so that noisy features get ignored during training:

**L1 Regularization (Lasso)** — Sets noisy feature weights to exactly zero:

```python
from sklearn.linear_model import LogisticRegression
model = LogisticRegression(penalty="l1", C=0.1)  # C controls strictness
```

**XGBoost Built-in Regularization** — Multiple knobs that suppress noise:

```python
model = XGBClassifier(
    reg_alpha=1.0,          # L1: pushes unimportant features to zero
    reg_lambda=1.0,         # L2: shrinks all feature weights
    max_depth=4,            # Limits tree depth -- prevents overfitting to noise
    colsample_bytree=0.8,  # Each tree only sees 80% of features
)
```

`colsample_bytree` is particularly interesting — it adds RandomForest-style feature randomness to XGBoost, forcing it to discover alternative feature combinations instead of relying on the same dominant features in every tree.

#### Level 5: Boruta Algorithm — Gold Standard (High Effort)

Boruta is a wrapper around RandomForest that rigorously answers: **"Is this feature more useful than random noise?"**

```
Algorithm:
1. Create "shadow features" -- random shuffles of each real feature
2. Train a RandomForest on real features + shadow features
3. For each real feature: is its importance higher than the BEST shadow feature?
   YES --> keep (confirmed important)
   NO  --> drop (no better than random noise)
4. Repeat until all features are confirmed or rejected
```

This is the gold standard because it accounts for interactions — a feature might be unimportant alone but critical in combination, and Boruta captures that because the underlying RandomForest naturally models interactions.

```python
from boruta import BorutaPy

rf = RandomForestClassifier(n_estimators=100, random_state=42)
boruta = BorutaPy(rf, n_estimators="auto", random_state=42)
boruta.fit(X, y)

print(f"Confirmed: {[f for f, s in zip(feature_names, boruta.support_) if s]}")
print(f"Rejected:  {[f for f, s in zip(feature_names, boruta.support_) if not s]}")
```

### Summary: Feature Interaction Techniques

| Level | Technique | What It Does | Effort | When to Use |
|---|---|---|---|---|
| 1 | Let trees find interactions | Automatic — each tree path IS an interaction | None | Always (it's free) |
| 2 | Manual derived features | Create ratios, trends, differences from domain knowledge | Low | When experts know the relationships |
| 3a | Polynomial features | Generate all pairwise combinations, then prune | Medium | Many features, suspect hidden interactions |
| 3b | SHAP interaction values | Measure synergistic effects between feature pairs | Medium | Need to understand *which* pairs interact |
| 3c | RFECV | Automated keep/drop decisions with cross-validation | Medium | Want rigorous automated selection |
| 4 | Regularization (L1/L2) | Penalize complexity, noisy features get dimmed | Low | Should be standard practice on every model |
| 5 | Boruta algorithm | Test "is each feature better than random noise?" | High | Gold standard for production feature selection |

### What We Used in This Project

| Level | Technique | Applied |
|---|---|---|
| 1 | Tree-based interactions | Yes — all three stages use tree models |
| 2 | Manual derived features | Yes — `bid_to_floor_ratio`, `delivery_variance`, `budget_consumed_pct`, `competitor_change_24h`, `cpm_change_pct` |
| 4 | XGBoost regularization | Yes — `max_depth=4` to prevent overfitting |

For a POC with synthetic data, Levels 1 + 2 + 4 are sufficient. With real data, adding Level 3b (SHAP interactions) and Level 5 (Boruta) would help identify which features are truly earning their keep and which can be dropped.

---

## Handling Multi-Issue Diagnosis (Correlated Problems)

### Co-Occurring Issues

Some campaign issues are not independent — they share root causes:

```
Market gets competitive
    +-- bid becomes relatively too low  (bid_too_low)
    +-- more bidders crowd the auction  (competitive_pressure)
    +-- available inventory shrinks     (inventory_shortage)
```

A single-label classifier is forced to pick one winner. When multiple issues co-occur, the model picks the strongest signal and suppresses the others. The current model already reveals this through `class_probabilities`:

```json
Clean case (one issue):
  { "bid_too_low": 0.997, "competitive_pressure": 0.003, ... }

Ambiguous case (correlated issues):
  { "bid_too_low": 0.52, "competitive_pressure": 0.38, "targeting_too_narrow": 0.10 }
```

### Three Options for Handling Multi-Issue Diagnosis

#### Option 1: Top-K Thresholding (Cheapest — No Retraining)

Keep the current model. Report all issues above a confidence threshold:

```python
threshold = 0.15
issues = [
    {"issue_type": cls, "confidence": prob}
    for cls, prob in class_probabilities.items()
    if prob >= threshold
]
# Returns: [bid_too_low (0.52), competitive_pressure (0.38)]
```

**Pros:** Zero retraining, builds on existing output, easy to implement.
**Cons:** Probabilities from a multi-class model aren't true multi-label probabilities — they sum to 1.0, so a high secondary probability always means a lower primary probability.

#### Option 2: Multi-Label Classification (Best for Production)

Train 6 independent binary classifiers — one per issue type. Each predicts yes/no for its issue independently:

```
bid_too_low classifier:         YES (0.92)
competitive_pressure classifier: YES (0.85)
creative_fatigue classifier:     NO  (0.03)
```

A campaign can have 0, 1, 2, or all 6 issues simultaneously. Probabilities are independent — they don't need to sum to 1.0.

**Pros:** Correctly models co-occurring issues, independent probabilities.
**Cons:** Requires retraining with multi-label annotations, 6 models to maintain.

#### Option 3: Hierarchical Classification (Best for Correlated Features)

Group correlated issues under parent categories:

```
market_dynamics (parent)
+-- bid_too_low
+-- competitive_pressure
+-- inventory_shortage

campaign_health (parent)
+-- creative_fatigue
+-- targeting_too_narrow
+-- pacing_issue
```

First model: "Is this a market problem or a campaign problem?"
Second model: "Which specific issue within that category?"

**Pros:** Separates correlated features into different hierarchy levels, improves accuracy on correlated issues.
**Cons:** More complex architecture, harder to maintain, requires careful taxonomy design.

### Recommendation

For a POC, **Option 1** gets 80% of the value with 5% of the effort. For production with real data where correlated issues are common, invest in **Option 2**.

---

## Summary: Model Selection Cheat Sheet

```
CLASSIFICATION PROBLEMS:
+--------------------------------------------------+
| Need calibrated probabilities?                   |
| (confidence scores matter, multiple valid answers)|
|     --> RandomForest                              |
|                                                  |
| Need maximum accuracy?                           |
| (single right answer, confidence is secondary)   |
|     --> XGBoost                                   |
|                                                  |
| Need multi-label (multiple issues at once)?      |
|     --> 6 independent binary classifiers          |
|         (RandomForest or XGBoost, one per label)  |
+--------------------------------------------------+

REGRESSION PROBLEMS:
+--------------------------------------------------+
| Predict a continuous value?                      |
|     --> GradientBoosting Regressor                |
|                                                  |
| Multiple target types with different units?      |
|     --> Separate per-target regressors            |
|         (not one multi-output model)              |
+--------------------------------------------------+

BEFORE CHOOSING ANY MODEL:
+--------------------------------------------------+
| 1. Talk to domain experts about features         |
| 2. Start with features humans check manually     |
| 3. Create derived features (ratios, trends)      |
| 4. Remove correlated/redundant features          |
| 5. Validate with ablation testing                |
|                                                  |
| Feature selection determines your ceiling.       |
| The algorithm just gets you closer to it.        |
+--------------------------------------------------+
```

---

*This document captures discussions from the Campaign Optimization Agent project. The examples and results reference the three-stage ML pipeline (diagnosis, classification, regression) deployed on SageMaker. See [agent/README.md](../agent/README.md) for the full architecture.*
