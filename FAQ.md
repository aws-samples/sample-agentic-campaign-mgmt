<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# FAQ -- Deep-Dive Reference

Jump to a question:
[1. Programmatic advertising](#faq-1-what-is-programmatic-advertising) | [2. DSP](#faq-2-what-is-a-dsp) | [3. MCP](#faq-3-what-is-mcp-model-context-protocol) | [4. AgentCore](#faq-4-what-is-amazon-bedrock-agentcore) | [5. Parallel vs sequential](#faq-5-how-does-the-agent-decide-which-tools-to-call-in-parallel-vs-sequentially) | [6. Why not GenAI for diagnosis?](#faq-6-why-not-just-ask-claude-to-diagnose-the-campaign-directly) | [7. Why XGBoost?](#faq-7-why-xgboost-over-a-neural-network-or-random-forest) | [8. Synthetic data](#faq-8-is-synthetic-training-data-cheating) | [9. ReAct pattern](#faq-9-what-is-the-react-pattern) | [10. Prompt vs tool descriptions](#faq-10-how-does-the-system-prompt-differ-from-tool-descriptions) | [11. When the agent is wrong](#faq-11-what-happens-when-the-agent-is-wrong)

---

### FAQ 1: What is programmatic advertising?

Automated buying and selling of digital ad inventory through real-time auctions. When you see an ad on a website or streaming service, it was likely bought and placed in milliseconds through a programmatic auction. Advertisers set budgets, targeting criteria, and bid amounts. The system handles the rest -- finding available ad slots, bidding against other advertisers, and placing the winning ad.

Think of it like stock trading, but for ad impressions. The "stock exchange" is called an ad exchange. The tool traders use to buy is called a DSP.

### FAQ 2: What is a DSP?

A Demand-Side Platform -- the tool media traders use to set bids, define targeting (geography, demographics, interests), manage budgets, and monitor campaign delivery. It's like a trading terminal for advertising. Nexalith Ads uses a DSP to manage their 50,000 daily campaigns.

### FAQ 3: What is MCP (Model Context Protocol)?

An open standard for connecting AI agents to tools and data sources. Think of it like USB for AI -- any tool that speaks MCP can plug into any agent that speaks MCP, regardless of the framework.

In our system, the agent's 10 tools are registered as MCP endpoints via AgentCore Gateway. The agent calls them using a standard protocol. If we swap the agent framework tomorrow, the tools don't change. If we add a new tool, the agent discovers it automatically from the MCP catalog.

### FAQ 4: What is Amazon Bedrock AgentCore?

AWS's infrastructure for running AI agents. Three components matter here:

- **AgentCore Runtime** -- where the agent code runs (our Claude-powered orchestrator)
- **AgentCore Gateway** -- how the agent connects to tools (MCP-native)
- **AgentCore Memory** -- manages conversation history per trader session

AgentCore is *not* the same as "Bedrock Agents" (the older, console-configured approach). AgentCore is code-first: you own the agent logic, deploy it as a container, and choose your framework. More [here: Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/).

### FAQ 5: How does the agent decide which tools to call in parallel vs sequentially?

The agent reasons about data dependencies. If two tools don't need each other's output, it fires both in a single inference step:

- `get_campaign_metrics` and `get_market_intelligence` are **independent** -- fire simultaneously
- `diagnose_campaign_issue` **depends on** both results -- must wait for them
- `generate_recommendation` **depends on** the diagnosis -- must wait for it

This is the ReAct loop in action. At each step, the agent asks: "Do I have enough information to proceed, or do I need another tool call?" If it can fire multiple calls at once, it does. If one call depends on another's output, it chains them.

The result: for our campaign 4782 query, the agent makes **4 tool calls in 3 inference steps** (not 4), because the first two calls run in parallel.

### FAQ 6: Why not just ask Claude to diagnose the campaign directly?

1. **LLMs hallucinate numbers.** If you ask Claude "is the bid too low?", it might say yes with a plausible-sounding confidence score that it made up. An ML model trained on labeled data returns calibrated probabilities tied to specific input features.

2. **Auditability.** The ML model outputs a probability distribution across 6 classes, traceable to specific features with known importance weights. You can explain *exactly* why it said `bid_too_low` with 99.7% confidence. An LLM's reasoning is opaque by comparison.

GenAI is better at *synthesis and communication*. ML is better at *structured classification*. Use each where it's strong.

### FAQ 7: Why XGBoost over a neural network or random forest?

For this problem -- 15 numeric/categorical features, 6 output classes, fast inference required -- XGBoost is the right tool:

- **Interpretable.** Feature importance is built in. We know `competitor_change_24h` is the strongest signal without any extra tooling.
- **Fast.** Under 10ms inference, easily fits within a Lambda or SageMaker invocation budget.
- **Handles mixed types.** Numeric features (bid ratio, win rate) and categorical features (industry, geo) work natively.
- **No GPU required.** Runs on a `ml.t2.medium` instance -- roughly $0.05/hour.

Neural networks shine when you have 1,000+ features, unstructured data (images, text), or need to learn complex non-linear representations. For a structured classification problem with 15 features, they're overkill -- harder to interpret, slower to train, and require GPU infrastructure.

Random forests would also work here, but XGBoost typically achieves higher accuracy with the same data by learning from the mistakes of previous trees (boosting vs bagging).

### FAQ 8: Is synthetic training data cheating?

For a POC, no. It's the responsible way to start.

Synthetic data lets you validate the full pipeline end-to-end -- training, inference, deployment, smoke testing -- before real labeled data exists. We generated 1,200 rows with intentionally non-overlapping feature distributions per class. The model achieves 1.000 accuracy on this data, which is *expected and correct* for cleanly separated synthetic classes.

When adapting this for your own use case, you'd retrain on real feedback: when a user accepts or rejects a recommendation, that's a labeled training example. Expect 75-90% accuracy with real data, as some issue types may overlap (e.g., `bid_too_low` and `competitive_pressure` share similar symptoms). That overlap is healthy -- it means the model is learning subtle patterns, not memorizing artificial boundaries.

The key is that the *pipeline* is the same. Same feature engineering, same model architecture, same deployment path. Only the training data changes.

### FAQ 9: What is the ReAct pattern?

ReAct stands for **Reason-Act-Observe**. It's a loop:

<div align="center">

![ReAct pattern — Reason, Act, Observe loop](images/08-react-pattern.png)

</div>

At each step, the agent:
1. **Reasons** about what it knows and what it still needs
2. **Acts** by calling one or more tools
3. **Observes** the results

It repeats until it has enough information to synthesize a final response. There's no hard-coded workflow -- the agent decides dynamically based on the question and the data it receives.

This is what makes agents different from chatbots. A chatbot generates text. An agent *takes actions* based on reasoning, observes results, and adapts.

### FAQ 10: How does the system prompt differ from tool descriptions?

They have different jobs:

<div align="center">

![System prompt vs tool descriptions](images/t06-prompt-vs-tools.png)

</div>

The system prompt answers: *"How should the agent behave across the entire session?"* -- guardrails, output format, confidence thresholds, autonomy boundaries.

Tool descriptions answer: *"What does this specific tool do, when should I call it, and what inputs does it need?"* -- including dependency ordering (call A before B) and parallelism hints (call A and B simultaneously).

Mixing them causes maintenance drift. If you put "call `get_metrics` before `diagnose`" in both places, they'll eventually disagree when someone updates one but not the other. We follow a strict split: **system prompt = behavior, tool descriptions = per-tool instructions**.

**5 anti-patterns we avoided:**

<div align="center">

![5 anti-patterns we avoided](images/t07-anti-patterns.png)

</div>

Our draft system prompt covers four areas: **role definition** (expert advisor, not chatbot -- lead with numbers, skip filler), **tool-calling rules** (don't over-call, use what-if tool for projections, pull trader_id from session context), **response format** (the 5-part structure shown in the [sample agent response](blog-v5.md#walking-through-a-real-query) above), and **guardrails** (never apply changes without confirmation, flag low confidence, never fabricate numbers). The full system prompt is available in the companion repository.

### FAQ 11: What happens when the agent is wrong?

Every recommendation requires trader approval. The agent presents three options:

- **Accept & Apply** -- the change goes through, gets logged, and a 4-hour follow-up is scheduled
- **Modify** -- the trader adjusts the recommendation (e.g., different bid amount) and the agent recalculates projected outcomes
- **Reject** -- the trader disagrees; the agent logs the reason

The confidence score is always visible. When it's below 0.70, the agent explicitly flags uncertainty: *"I'm less certain here (confidence: 0.62) -- I'd recommend checking with the account team before acting."*

Rejections are valuable training data. Each rejection is a labeled example that improves the model in the next training cycle. Over time, the model learns from its mistakes.
