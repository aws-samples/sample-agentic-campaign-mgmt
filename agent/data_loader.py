# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared data loading utilities for agent tools.

In the POC, tools read from local JSON files under data/.
In production, these would be replaced with DynamoDB / Redis / Athena calls.
"""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "prototype-v1" / "data"


@lru_cache(maxsize=None)
def _load_json(filename: str) -> list:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def load_campaigns() -> list:
    return _load_json("campaigns.json")


def load_campaign_configs() -> list:
    return _load_json("campaign_configs.json")


def load_market_intelligence() -> list:
    return _load_json("market_intelligence.json")


def load_historical_outcomes() -> list:
    return _load_json("historical_outcomes.json")


def load_trader_profiles() -> list:
    return _load_json("trader_profiles.json")


def load_recommendation_history() -> list:
    return _load_json("recommendation_history.json")


def find_campaign(campaign_id: str) -> dict | None:
    return next((c for c in load_campaigns() if c["campaign_id"] == campaign_id), None)


def find_config(campaign_id: str) -> dict | None:
    return next((c for c in load_campaign_configs() if c["campaign_id"] == campaign_id), None)


def find_market(industry: str, geo: str) -> dict | None:
    segment = f"{industry}_{geo.lower().replace(' ', '_')}_dma"
    return next((m for m in load_market_intelligence() if m["market_segment"] == segment), None)
