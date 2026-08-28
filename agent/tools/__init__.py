# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from agent.tools.campaign_data import (
    get_campaign_metrics,
    get_campaign_configuration,
    get_trader_campaigns,
    get_campaign_history,
)
from agent.tools.analysis import (
    diagnose_campaign_issue,
    generate_recommendation,
    calculate_what_if_scenario,
)
from agent.tools.market_intel import (
    get_market_intelligence,
    get_benchmark_comparison,
    find_similar_campaigns,
)

ALL_TOOLS = [
    get_campaign_metrics,
    get_campaign_configuration,
    get_trader_campaigns,
    get_campaign_history,
    diagnose_campaign_issue,
    generate_recommendation,
    calculate_what_if_scenario,
    get_market_intelligence,
    get_benchmark_comparison,
    find_similar_campaigns,
]
