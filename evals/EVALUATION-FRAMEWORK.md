<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Campaign Optimization AI Agent - Evaluation Framework
**Date:** February 18, 2026
**Focus:** Evaluating Non-Deterministic LLM Agent Success

---

## Executive Summary

Evaluating AI agent systems with non-deterministic LLMs requires a **multi-layered approach** that goes beyond traditional software metrics. This framework addresses the unique challenges of measuring:
- **Variable responses** (same query ≠ same answer)
- **Subjective quality** (helpfulness, clarity, trust)
- **Business outcomes** (ROI, adoption, time saved)
- **System reliability** (despite non-determinism)

---

## The Challenge: Non-Determinism in LLM Agents

### What Makes This Hard?

**Traditional Software:**
```python
input("campaign_4782") → always returns same metrics
```

**LLM Agent:**
```python
query("show me campaign 4782")
→ Response A: "Campaign #4782 is 28% behind schedule..."
→ Response B: "Honda Spring Sale - Chicago: Delivery at 29%..."
→ Response C: "Let me pull up #4782 for you. Currently at 29% delivery..."
```

All correct, but **different**. How do you evaluate this?

---

## Evaluation Framework: 5 Layers

```
Layer 1: Data Layer (Deterministic) ✅
    ↓
Layer 2: Agent Behavior (Semi-Deterministic) ⚠️
    ↓
Layer 3: Response Quality (Subjective) 🎯
    ↓
Layer 4: User Experience (Behavioral) 👤
    ↓
Layer 5: Business Impact (Outcome) 💰
```

---

## Layer 1: Data Layer Metrics (Deterministic)

**Goal:** Verify the underlying data and computations are correct.

### Critical Tests

#### 1.1 Function Output Validation
```python
# Test: Does get_campaign_metrics return correct data?
def test_campaign_metrics_accuracy():
    result = get_campaign_metrics("4782")

    assert result["delivery_pct"] == 0.29  # From source data
    assert result["expected_pct"] == 0.43  # Calculated correctly
    assert result["win_rate"] == 0.08     # From bid stream
    assert abs(result["pace_variance"] - (-0.14)) < 0.01  # Math is right

    # Verify timestamps are recent (< 5 min old)
    assert time_since(result["timestamp"]) < 300
```

#### 1.2 Diagnosis Accuracy
```python
# Test: Does diagnosis correctly identify root causes?
def test_diagnosis_accuracy():
    diagnosis = diagnose_campaign_issue("4782")

    # Campaign 4782: bid=4.20, market_floor=5.10
    assert diagnosis["primary_issue"]["type"] == "bid_too_low"
    assert diagnosis["primary_issue"]["confidence"] > 0.90
    assert diagnosis["evidence"]["current_bid"] == 4.20
    assert diagnosis["evidence"]["market_floor"] == 5.10
```

#### 1.3 Recommendation Calculation
```python
# Test: Are recommendations mathematically sound?
def test_recommendation_calculation():
    rec = generate_recommendation("4782")

    # Should recommend bid above market floor
    assert rec["recommendation"]["recommended_value"] > 5.10

    # Change should be within reasonable bounds (10-50%)
    change_pct = rec["recommendation"]["change_pct"]
    assert 0.10 <= change_pct <= 0.50

    # Expected outcomes should be plausible
    assert rec["expected_outcomes"]["expected_win_rate"] > 0.08  # Better than current
    assert rec["expected_outcomes"]["expected_win_rate"] < 0.60  # But realistic
```

### Success Criteria (Layer 1)
- ✅ **Function accuracy:** 99.9% correct data retrieval
- ✅ **Calculation accuracy:** 100% correct math (deterministic)
- ✅ **Data freshness:** <5 minutes lag (P95)
- ✅ **Error rate:** <0.1% for data access functions

**Why This Matters:** If the foundation is wrong, the agent's good communication can't save it.

---

## Layer 2: Agent Behavior Metrics (Semi-Deterministic)

**Goal:** Verify the agent calls the right functions and follows instructions.

### Critical Tests

#### 2.1 Tool Selection Accuracy
```python
# Test: Does agent call appropriate functions for queries?
test_cases = [
    {
        "query": "show me campaign 4782",
        "expected_functions": ["get_campaign_metrics"],
        "required_params": {"campaign_id": "4782"}
    },
    {
        "query": "what's wrong with campaign 4782?",
        "expected_functions": ["get_campaign_metrics", "diagnose_campaign_issue"],
        "required_params": {"campaign_id": "4782"}
    },
    {
        "query": "give me recommendations for 4782",
        "expected_functions": ["diagnose_campaign_issue", "generate_recommendation"],
        "required_params": {"campaign_id": "4782"}
    },
    {
        "query": "show me all at-risk campaigns",
        "expected_functions": ["get_trader_campaigns"],
        "required_params": {"filter_status": "at_risk"}
    }
]

def test_tool_selection():
    for test in test_cases:
        response = agent.invoke(test["query"])

        # Check: Did agent call expected functions?
        for func in test["expected_functions"]:
            assert func in response.function_calls

        # Check: Were parameters extracted correctly?
        for param, value in test["required_params"].items():
            assert response.params[param] == value
```

#### 2.2 Context Retention (Multi-Turn)
```python
# Test: Does agent maintain conversation context?
def test_context_retention():
    session = agent.create_session()

    # Turn 1: Establish context
    r1 = session.send("show me campaign 4782")
    assert "4782" in r1.response

    # Turn 2: Use implicit reference
    r2 = session.send("what's wrong with it?")
    # Agent should understand "it" = campaign 4782
    assert r2.function_calls[0].params["campaign_id"] == "4782"

    # Turn 3: Implicit comparison
    r3 = session.send("how does 5201 compare?")
    # Agent should compare 5201 to 4782 (previous context)
    assert "4782" in r3.function_calls or "compare" in r3.function_calls
```

#### 2.3 Hallucination Prevention
```python
# Test: Agent NEVER invents data
def test_hallucination_prevention():
    # Query about non-existent campaign
    response = agent.invoke("show me campaign 9999")

    # Agent should NOT make up data
    assert "Campaign 9999" not in response.text or "not found" in response.text.lower()

    # Agent should call get_campaign_metrics even if it fails
    assert "get_campaign_metrics" in response.function_calls

    # Test: Query for data we don't have
    response = agent.invoke("what's the sentiment of campaign 4782 creative?")

    # Should explicitly say we don't have that data
    assert any(phrase in response.text.lower() for phrase in [
        "don't have",
        "not available",
        "cannot access",
        "no data for"
    ])
```

#### 2.4 Instruction Following
```python
# Test: Agent follows system instructions
def test_instruction_compliance():
    # System instruction: Always cite data sources
    response = agent.invoke("what's the win rate for 4782?")

    # Should include timestamp or "current" or "as of"
    assert any(indicator in response.text.lower() for indicator in [
        "as of",
        "currently",
        "latest",
        "timestamp"
    ])

    # Should call function (not guess)
    assert len(response.function_calls) > 0
```

### Success Criteria (Layer 2)
- ✅ **Tool selection accuracy:** >95% (agent picks right function)
- ✅ **Parameter extraction:** >90% (extracts campaign IDs, dates correctly)
- ✅ **Context retention:** >85% (handles "it", "that campaign" correctly)
- ✅ **Hallucination rate:** <2% (never invents data)
- ✅ **Instruction compliance:** >95% (follows system rules)

**Why This Matters:** Good behavior = trustworthy agent. Bad behavior = traders stop using it.

---

## Layer 3: Response Quality Metrics (Subjective)

**Goal:** Evaluate the quality of natural language responses.

### 3.1 Automated Quality Checks

#### Response Completeness
```python
# Test: Does response contain necessary information?
def test_response_completeness():
    query = "what's wrong with campaign 4782?"
    response = agent.invoke(query)

    # Should include:
    required_elements = [
        "campaign_id": "4782",
        "issue_identified": True,  # "bid too low", "creative fatigue", etc.
        "evidence_provided": True,  # Numbers, comparisons
        "explanation": True         # Why this is the problem
    ]

    # Extract structured data from response
    analysis = analyze_response(response.text)

    for element, expected in required_elements.items():
        assert analysis[element] == expected
```

#### Clarity Score (via LLM-as-Judge)
```python
# Use a second LLM to evaluate the first LLM's response
def test_clarity_score():
    agent_response = agent.invoke("what's wrong with campaign 4782?")

    judge_prompt = f"""
    Evaluate this agent response for clarity and helpfulness:

    USER QUERY: "what's wrong with campaign 4782?"
    AGENT RESPONSE: {agent_response.text}

    Score 1-5 on:
    1. Clarity (easy to understand?)
    2. Specificity (concrete details vs vague?)
    3. Actionability (does trader know what to do?)
    4. Professional tone (appropriate for work?)

    Return JSON: {{"clarity": X, "specificity": X, "actionability": X, "tone": X}}
    """

    scores = judge_llm.invoke(judge_prompt)

    # All scores should be ≥ 4
    assert all(score >= 4 for score in scores.values())
```

#### Consistency Check
```python
# Test: Similar queries → similar structure (not identical text)
def test_response_consistency():
    # Ask same question 5 times
    responses = [
        agent.invoke("show me campaign 4782")
        for _ in range(5)
    ]

    # Extract key facts from each response
    facts = [extract_facts(r.text) for r in responses]

    # All should contain same facts (deterministic layer)
    core_facts = ["delivery_pct", "expected_pct", "win_rate", "current_bid"]
    for response_facts in facts:
        for fact in core_facts:
            assert fact in response_facts
            # Values should be identical across responses
            assert response_facts[fact] == facts[0][fact]

    # Text can differ (non-deterministic layer) - that's OK!
    # As long as facts are consistent
```

### 3.2 Human Evaluation (Gold Standard)

#### Weekly Response Review
```python
# Sample 50 random agent responses per week
# Have 3 reviewers rate each response 1-5 on:

rating_criteria = {
    "accuracy": "Are all facts correct?",
    "clarity": "Is explanation clear and easy to understand?",
    "completeness": "Does it answer the full question?",
    "conciseness": "Right level of detail (not too much/little)?",
    "helpfulness": "Would this actually help the trader?",
    "professionalism": "Appropriate tone for workplace?"
}

# Calculate inter-rater reliability
# Target: Fleiss' Kappa > 0.6 (substantial agreement)
```

#### A/B Testing
```python
# Test different agent instruction sets
def run_ab_test():
    # Variant A: Detailed explanations
    # Variant B: Concise summaries

    # Randomly assign 50% of queries to each
    # Measure:
    # - Trader satisfaction (thumbs up/down)
    # - Follow-up question rate (lower = better initial response)
    # - Time to decision (accept recommendation)

    # Winner: Variant with higher satisfaction + lower follow-ups
```

### Success Criteria (Layer 3)
- ✅ **Automated completeness:** >90% of responses include required elements
- ✅ **LLM-as-judge clarity:** Average score ≥4.0/5.0
- ✅ **Fact consistency:** 100% (same query → same facts)
- ✅ **Human quality rating:** Average ≥4.0/5.0
- ✅ **Inter-rater reliability:** Kappa >0.6

**Why This Matters:** Technically correct but poorly communicated = not useful.

---

## Layer 4: User Experience Metrics (Behavioral)

**Goal:** Measure how traders actually interact with the agent.

### 4.1 Engagement Metrics

#### Usage Patterns
```python
metrics = {
    "daily_active_users": "How many traders use it daily?",
    "queries_per_trader_per_day": "How often do they ask questions?",
    "session_length": "How long do they engage?",
    "return_rate": "Do they come back?",

    # Target values:
    "target_dau_percentage": 0.70,  # 70% of traders use daily
    "target_queries_per_day": 8,    # 8+ queries per trader
    "target_return_rate": 0.85      # 85% return next day
}
```

#### Conversation Depth
```python
# Measure multi-turn conversations
conversation_metrics = {
    "avg_turns_per_session": "How many back-and-forth exchanges?",
    "max_turn_depth": "Longest conversation?",
    "follow_up_rate": "% of queries that lead to follow-ups",

    # Good sign: Traders engage deeply
    "target_avg_turns": 3.5,        # 3-4 turns per conversation
    "target_follow_up_rate": 0.40   # 40% lead to follow-ups
}
```

### 4.2 Satisfaction Metrics

#### Explicit Feedback
```python
# Thumbs up/down on every response
feedback = {
    "positive_rate": "% of thumbs up",
    "negative_rate": "% of thumbs down",
    "feedback_provided_rate": "% who bother to rate",

    # Target: >70% positive, <5% negative, >40% provide feedback
}

# Net Promoter Score (monthly survey)
nps_question = "How likely are you to recommend this agent to a colleague?"
# Target: NPS >40 (anything >30 is "good")
```

#### Implicit Feedback
```python
implicit_signals = {
    "recommendation_acceptance_rate": "% of times trader accepts AI recommendation",
    "action_completion_rate": "% of times trader follows through",
    "error_recovery_rate": "% of times trader asks clarifying question vs gives up",

    # Strong signals:
    "target_acceptance_rate": 0.50,  # 50%+ accept recommendations
    "target_completion_rate": 0.90,  # 90% follow through when accepted
    "target_recovery_rate": 0.80     # 80% ask for clarification vs abandon
}
```

### 4.3 Efficiency Metrics

#### Time Savings
```python
# Compare time spent on tasks before/after agent
efficiency = {
    "time_to_diagnose_issue": {
        "before": "15 minutes (manual investigation)",
        "after": "30 seconds (ask agent)",
        "savings": "14.5 minutes per issue"
    },
    "time_to_get_recommendation": {
        "before": "20 minutes (research similar campaigns)",
        "after": "45 seconds (agent provides with evidence)",
        "savings": "19.25 minutes"
    },
    "total_time_saved_per_trader_per_day": "~30 minutes"
}
```

#### Query Resolution Rate
```python
# First Response Resolution Rate
resolution = {
    "resolved_in_1_query": 0.65,    # 65% get answer immediately
    "resolved_in_2_queries": 0.25,  # 25% need 1 follow-up
    "resolved_in_3+_queries": 0.08, # 8% need 2+ follow-ups
    "unresolved": 0.02              # 2% give up
}

# Target: >90% resolved within 2 queries
```

### Success Criteria (Layer 4)
- ✅ **Daily active usage:** >70% of traders use daily
- ✅ **Positive feedback rate:** >70% thumbs up
- ✅ **NPS:** >40
- ✅ **Recommendation acceptance:** >50%
- ✅ **Time saved:** >20 min/trader/day
- ✅ **First response resolution:** >65%

**Why This Matters:** Traders vote with their time. If it's not useful, they stop using it.

---

## Layer 5: Business Impact Metrics (Outcomes)

**Goal:** Prove ROI and business value.

### 5.1 Campaign Performance Impact

#### Before/After Analysis
```python
# Compare campaigns managed with agent vs without
analysis = {
    "campaigns_with_agent_intervention": {
        "at_risk_recovery_rate": 0.78,      # 78% recover
        "avg_recovery_time_hours": 18,       # Recover in 18h
        "final_delivery_rate": 0.92          # 92% hit goals
    },
    "campaigns_without_agent": {
        "at_risk_recovery_rate": 0.45,      # 45% recover
        "avg_recovery_time_hours": 48,       # Take 48h
        "final_delivery_rate": 0.71          # 71% hit goals
    },
    "improvement": {
        "recovery_rate_lift": "+73%",
        "time_reduction": "-63%",
        "goal_achievement_lift": "+30%"
    }
}
```

#### Revenue Protected
```python
# Calculate revenue impact
revenue_impact = {
    "at_risk_campaigns_per_day": 50,
    "avg_campaign_value": 10000,
    "recovery_rate_with_agent": 0.78,
    "recovery_rate_without_agent": 0.45,
    "incremental_recovery_rate": 0.33,  # +33%

    "revenue_protected_daily": 50 * 10000 * 0.33,  # $165,000/day
    "revenue_protected_monthly": 165000 * 30,       # $4.95M/month
}
```

### 5.2 Operational Efficiency

#### Labor Cost Savings
```python
cost_savings = {
    "time_saved_per_trader_per_day": 30,  # minutes
    "traders_using_system": 20,
    "total_time_saved_daily": 600,         # minutes = 10 hours
    "working_days_per_month": 22,
    "total_hours_saved_monthly": 220,      # hours

    "avg_trader_cost_per_hour": 75,        # $75/hour fully loaded
    "labor_cost_saved_monthly": 220 * 75,  # $16,500/month
}
```

#### Scalability Metrics
```python
scalability = {
    "campaigns_managed_per_trader": {
        "before_agent": 150,
        "with_agent": 250,
        "increase": "+67%"
    },
    "additional_revenue_capacity": {
        "campaigns_per_trader_increase": 100,
        "traders": 20,
        "additional_campaign_capacity": 2000,
        "avg_revenue_per_campaign": 8000,
        "incremental_revenue_capacity": 2000 * 8000  # $16M
    }
}
```

### 5.3 ROI Calculation

```python
roi = {
    "monthly_costs": {
        "bedrock_agent": 8000,
        "infrastructure": 8800,
        "total": 16800
    },

    "monthly_benefits": {
        "revenue_protected": 4950000,    # $4.95M
        "labor_cost_saved": 16500,       # $16.5K
        "total": 4966500
    },

    "net_benefit": 4966500 - 16800,      # $4,949,700
    "roi_multiple": 4966500 / 16800,     # 296x
    "payback_period_days": 0.1           # <1 day
}
```

### Success Criteria (Layer 5)
- ✅ **At-risk recovery rate:** >75% (vs <50% baseline)
- ✅ **Revenue protected:** >$3M/month
- ✅ **Labor cost saved:** >$10K/month
- ✅ **Campaigns per trader:** +50% capacity
- ✅ **ROI:** >100x
- ✅ **Payback period:** <1 month

**Why This Matters:** This is what executives care about. Technical excellence → business value.

---

## Evaluation Dashboard

### Real-Time Monitoring

```python
# CloudWatch Dashboard - Live Metrics
live_dashboard = {
    "system_health": {
        "uptime": "99.95%",
        "p95_response_time": "2.1s",
        "error_rate": "0.3%"
    },

    "agent_performance": {
        "queries_per_hour": 45,
        "tool_selection_accuracy": "96%",
        "hallucination_rate": "0.8%",
        "avg_confidence_score": 0.87
    },

    "user_engagement": {
        "active_users_now": 12,
        "avg_session_length": "4.2 minutes",
        "positive_feedback_rate": "73%"
    },

    "business_impact": {
        "recommendations_accepted_today": 18,
        "campaigns_recovered_this_week": 42,
        "estimated_revenue_protected_today": "$182K"
    }
}
```

### Weekly Report Card

```python
# Automated weekly summary
weekly_report = {
    "layer_1_data_accuracy": {
        "function_error_rate": "0.1%",
        "data_freshness_p95": "3.2 min",
        "status": "✅ PASS"
    },

    "layer_2_agent_behavior": {
        "tool_selection_accuracy": "95.8%",
        "hallucination_incidents": 3,
        "context_retention_rate": "88%",
        "status": "✅ PASS"
    },

    "layer_3_response_quality": {
        "human_rating_avg": 4.2,
        "llm_judge_score_avg": 4.1,
        "consistency_score": "98%",
        "status": "✅ PASS"
    },

    "layer_4_user_experience": {
        "dau_percentage": "74%",
        "nps_score": 45,
        "recommendation_acceptance": "52%",
        "status": "✅ PASS"
    },

    "layer_5_business_impact": {
        "recovery_rate": "79%",
        "revenue_protected": "$1.21M",
        "roi_multiple": "287x",
        "status": "✅ PASS"
    }
}
```

---

## Testing Strategy for Non-Deterministic Responses

### The Core Problem

**Same query → Different responses (but should all be correct)**

### Solution: Test for Properties, Not Exact Matches

#### ❌ Wrong Approach
```python
# This will fail due to non-determinism
def test_response_text():
    response = agent.invoke("show me campaign 4782")
    assert response.text == "Campaign #4782 is 28% behind schedule..."
    # ❌ FLAKY: Text varies each time
```

#### ✅ Right Approach
```python
# Test for properties and facts
def test_response_properties():
    response = agent.invoke("show me campaign 4782")

    # Property 1: Contains campaign ID
    assert "4782" in response.text

    # Property 2: Mentions delivery status
    assert any(word in response.text.lower() for word in
               ["delivery", "progress", "pacing"])

    # Property 3: Includes numerical facts
    facts = extract_numbers(response.text)
    assert 0.29 in facts or 29 in facts  # delivery_pct

    # Property 4: Called correct function
    assert "get_campaign_metrics" in response.function_calls

    # Property 5: Returned data matches expectations
    assert response.data["delivery_pct"] == 0.29
```

### Golden Dataset Testing

```python
# Create 50 "golden" test cases with expected properties
golden_tests = [
    {
        "query": "what's wrong with campaign 4782?",
        "expected_properties": {
            "mentions_campaign_id": True,
            "identifies_issue": True,
            "provides_evidence": True,
            "calls_diagnose_function": True,
            "issue_type": "bid_too_low"  # This IS deterministic
        }
    },
    # ... 49 more
]

def test_golden_dataset():
    for test in golden_tests:
        response = agent.invoke(test["query"])
        for property, expected in test["expected_properties"].items():
            assert check_property(response, property) == expected
```

### Regression Detection

```python
# Detect when agent behavior significantly changes
def test_regression():
    # Run same 100 queries before and after update
    before_responses = load_baseline_responses("v1.2.3")
    after_responses = [agent.invoke(q) for q in test_queries]

    # Compare properties (not text)
    for before, after in zip(before_responses, after_responses):
        # Functions called should be similar
        assert set(before.functions) == set(after.functions)

        # Core facts should match
        assert before.facts == after.facts

        # Quality scores should not degrade
        assert quality_score(after) >= quality_score(before) * 0.95
```

---

## Red Team Testing: Adversarial Evaluation

### Goal: Break the agent to find edge cases

```python
adversarial_tests = {
    "edge_cases": [
        "Show campaign 9999",  # Non-existent
        "What if I set bid to $0.01?",  # Nonsensical
        "Campaign 4782 4782 4782 4782",  # Repeated
        "",  # Empty query
        "asdfghjkl",  # Random text
    ],

    "ambiguous_queries": [
        "What about that one?",  # No context
        "The automotive campaign",  # Multiple matches
        "Is it good?",  # Vague
    ],

    "contradiction_tests": [
        # Turn 1: "Campaign 4782 is at risk"
        # Turn 2: "No, I meant 5201"
        # Agent should handle correction
    ],

    "hallucination_bait": [
        "What's the sentiment of campaign 4782?",  # We don't track sentiment
        "Who is the creative designer for 4782?",  # Not in data
        "What did the client say about this?",  # No client feedback data
    ]
}

def test_adversarial():
    for category, tests in adversarial_tests.items():
        for test_query in tests:
            response = agent.invoke(test_query)

            # Should gracefully handle, not crash
            assert response.status != "error"

            # Should not hallucinate data
            assert not contains_fabricated_data(response)

            # Should ask for clarification when appropriate
            if is_ambiguous(test_query):
                assert "clarify" in response.text.lower() or \
                       "which campaign" in response.text.lower()
```

---

## Continuous Evaluation Pipeline

### Automated Testing (Daily)

```python
# Run every night at 2 AM
daily_evaluation = {
    "layer_1_tests": "Run 500 function tests",
    "layer_2_tests": "Run 200 agent behavior tests",
    "golden_dataset": "Run 50 golden test cases",
    "regression_tests": "Compare to baseline",
    "adversarial_tests": "Run 100 edge cases",

    "alert_conditions": {
        "function_error_rate > 1%": "page_oncall",
        "hallucination_rate > 3%": "page_oncall",
        "tool_selection_accuracy < 90%": "slack_alert",
        "quality_score < 4.0": "email_team"
    }
}
```

### Human Review (Weekly)

```python
# Sample random responses for human evaluation
weekly_review = {
    "sample_size": 50,
    "sampling_strategy": "stratified",  # Mix of successful/failed, short/long, etc.
    "reviewers": 3,  # 3 independent ratings per response
    "review_time": "~2 hours total",

    "findings": "Feed back into training data / instruction tuning"
}
```

### A/B Testing (Ongoing)

```python
# Always be testing improvements
ab_tests = {
    "current_test": "Concise vs detailed explanations",
    "traffic_split": "50/50",
    "primary_metric": "Recommendation acceptance rate",
    "secondary_metrics": ["NPS", "Time to decision", "Follow-up rate"],
    "duration": "2 weeks",
    "decision_criteria": "5% improvement + statistical significance"
}
```

---

## Key Takeaways

### What Makes This Framework Work

1. **Multi-Layered:** Don't rely on single metric type
2. **Properties Over Exact Matches:** Test what matters, not exact text
3. **Behavioral Truth:** Usage patterns reveal true quality
4. **Business Outcomes:** Tie to revenue/efficiency
5. **Continuous:** Automated daily + human weekly
6. **Adversarial:** Actively try to break it

### Red Flags to Watch

```python
warning_signs = {
    "declining_usage": "DAU drops >10% in a week",
    "negative_feedback_spike": "Thumbs down rate >15%",
    "acceptance_rate_drop": "Recommendation acceptance <40%",
    "hallucination_increase": "Rate >3%",
    "performance_degradation": "P95 response time >5s",
    "error_rate_spike": ">2% errors"
}
```

### Success Indicators

```python
healthy_system = {
    "high_engagement": "70%+ DAU, 8+ queries/day",
    "strong_satisfaction": "NPS >40, 70%+ positive feedback",
    "trusted_recommendations": "50%+ acceptance rate",
    "clear_business_value": "ROI >100x, >$3M revenue protected",
    "technical_reliability": "99.9% uptime, <1% errors",
    "quality_consistency": "4.0+ average quality score"
}
```

---

## Next Steps

1. **Week 1:** Implement Layer 1 & 2 automated tests
2. **Week 2:** Set up monitoring dashboard
3. **Week 3:** Establish golden dataset (50 test cases)
4. **Week 4:** Begin human evaluation process
5. **Week 5:** Launch first A/B test
6. **Week 6:** Calculate first business impact report

**Remember:** Non-deterministic doesn't mean unmeasurable. It means we measure what matters: correctness of facts, quality of communication, and business outcomes.
