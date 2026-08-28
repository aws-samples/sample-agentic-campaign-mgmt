<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Evaluation & Success Metrics

This folder contains evaluation frameworks, testing strategies, and success measurement approaches for the Campaign Optimization AI Agent with non-deterministic LLM components.

---

## 📊 Files

### [EVALUATION-FRAMEWORK.md](EVALUATION-FRAMEWORK.md)
**Comprehensive evaluation framework** for measuring success with non-deterministic LLM agents.

**Key Contents:**
- 5-layer evaluation approach (Data → Behavior → Quality → UX → Business)
- Testing strategies for non-deterministic responses
- Golden dataset methodology
- Red team/adversarial testing
- Continuous evaluation pipeline
- Success metrics and KPIs

**Use Cases:**
- Proving ROI to stakeholders
- Measuring agent performance over time
- Identifying quality regressions
- A/B testing agent improvements
- Validating recommendation accuracy

---

## 🎯 The Challenge: Non-Deterministic Systems

Traditional software testing doesn't work with LLM agents:

**Traditional:**
```python
assert response == "Expected exact text"  # ❌ Fails with LLMs
```

**LLM Agent:**
```python
# Same query → Different responses (all correct!)
assert contains_campaign_id(response)     # ✅ Test properties
assert facts_match(response, expected)    # ✅ Test facts
assert quality_score(response) >= 4.0     # ✅ Test quality
```

---

## 📈 5-Layer Evaluation Framework

### **Layer 1: Data Layer (Deterministic) ✅**
- Function outputs are correct
- Calculations are accurate
- Data is fresh (<5 min)
- **Success:** 99.9% accuracy

### **Layer 2: Agent Behavior (Semi-Deterministic) ⚠️**
- Agent calls correct functions
- Parameters extracted correctly
- Context maintained across turns
- Hallucination rate <2%
- **Success:** >95% tool selection accuracy

### **Layer 3: Response Quality (Subjective) 🎯**
- Automated completeness checks
- LLM-as-judge clarity scoring
- Human quality ratings
- Consistency of facts
- **Success:** 4.0/5.0 average quality

### **Layer 4: User Experience (Behavioral) 👤**
- Daily active usage (>70%)
- Positive feedback rate (>70%)
- Recommendation acceptance (>50%)
- Time saved (>20 min/day)
- **Success:** High engagement + satisfaction

### **Layer 5: Business Impact (Outcomes) 💰**
- Campaign recovery rate (>75%)
- Revenue protected (>$3M/month)
- ROI (>100x)
- Labor cost savings
- **Success:** Clear business value

---

## 🧪 Testing Strategies

### **Golden Dataset Testing**
50 carefully crafted test cases with expected properties:
```python
{
  "query": "what's wrong with campaign 4782?",
  "expected_properties": {
    "mentions_campaign_id": True,
    "identifies_issue": True,
    "calls_diagnose_function": True,
    "issue_type": "bid_too_low"  # This IS deterministic
  }
}
```

### **Property-Based Testing**
Test for characteristics, not exact text:
```python
# ❌ Don't do this
assert response.text == "Campaign #4782 is 28% behind..."

# ✅ Do this
assert "4782" in response.text
assert response.data["delivery_pct"] == 0.29
assert "get_campaign_metrics" in response.functions_called
```

### **Regression Detection**
Compare agent behavior across versions:
```python
# Functions called should be similar
assert set(v1.functions) == set(v2.functions)

# Core facts must match
assert v1.facts == v2.facts

# Quality should not degrade
assert quality(v2) >= quality(v1) * 0.95
```

### **Adversarial Testing**
Try to break the agent:
- Non-existent campaigns ("show 9999")
- Ambiguous queries ("what about that one?")
- Hallucination bait ("what's the sentiment?")
- Edge cases (empty query, random text)

---

## 📊 Key Success Metrics

### **Technical Health**
- Uptime: 99.9%
- Response time (P95): <3s
- Function error rate: <1%
- Hallucination rate: <2%

### **User Adoption**
- Daily active users: >70%
- NPS score: >40
- Recommendation acceptance: >50%
- Time saved per trader: >20 min/day

### **Business Outcomes**
- At-risk recovery rate: >75% (vs <50% baseline)
- Revenue protected: >$3M/month
- ROI: >100x
- Campaign capacity per trader: +50%

---

## 🔄 Continuous Evaluation

### **Automated (Daily)**
```bash
# Run full test suite nightly
- 500 function tests (Layer 1)
- 200 agent behavior tests (Layer 2)
- 50 golden dataset tests (Layer 3)
- Regression tests vs. baseline
- Adversarial edge cases
```

### **Human Review (Weekly)**
```bash
# Sample 50 random responses
- 3 independent reviewers
- Rate on 6 quality dimensions
- Inter-rater reliability (Kappa >0.6)
- Findings → instruction tuning
```

### **A/B Testing (Ongoing)**
```bash
# Always be testing improvements
- Current test: Detailed vs. Concise explanations
- Traffic split: 50/50
- Primary metric: Recommendation acceptance
- Duration: 2 weeks
- Decision: 5% improvement + statistical significance
```

---

## 🚨 Red Flags to Watch

| Warning Sign | Threshold | Action |
|-------------|-----------|--------|
| Declining usage | DAU drops >10% in a week | Investigate UX issues |
| Negative feedback spike | Thumbs down >15% | Review recent responses |
| Acceptance rate drop | <40% | Check recommendation quality |
| Hallucination increase | >3% | Update instructions, add validation |
| Performance degradation | P95 >5s | Optimize infrastructure |
| Error rate spike | >2% | Check function implementations |

---

## 🎯 Implementation Roadmap

### **Week 1-2: Foundation**
- Implement Layer 1 & 2 automated tests
- Set up monitoring dashboard (CloudWatch)
- Create baseline metrics

### **Week 3-4: Quality Measurement**
- Establish golden dataset (50 test cases)
- Implement LLM-as-judge scoring
- Set up human evaluation process

### **Week 5-6: User Feedback**
- Launch beta with 5 traders
- Collect usage metrics
- Measure satisfaction (thumbs up/down, NPS)

### **Week 7-8: Business Impact**
- Calculate baseline recovery rates
- Track revenue protected
- Measure time savings
- Calculate ROI

### **Ongoing:**
- Daily automated testing
- Weekly human review
- Monthly business impact reports
- Quarterly A/B tests for improvements

---

## 📚 Related Documents

- **[../requirements.md](../requirements.md)** - AgentPath kickoff & requirements
- **[../architecture-viewpoint.md](../architecture-viewpoint.md)** - Complete architecture design
- **[../discovery/](../discovery/)** - Discovery materials for stakeholders

---

## 🔑 Key Takeaways

1. **Non-deterministic ≠ Unmeasurable** - Test properties, not exact text
2. **Multi-layered approach** - Data, behavior, quality, UX, business
3. **Continuous evaluation** - Automated daily + human weekly
4. **Business outcomes matter most** - ROI, revenue, efficiency
5. **Behavioral truth** - Usage patterns reveal real quality
6. **Trust the process** - LLM agents can be reliable and measurable

---

**Last Updated:** February 18, 2026
