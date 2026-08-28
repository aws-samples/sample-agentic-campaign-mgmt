// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

export interface Campaign {
  campaign_id: string;
  campaign_name: string;
  client_id: string;
  trader_id: string;
  status: string;
  industry: string;
  objective: string;
  geo: string;
  budget_total: number;
  impressions_goal: number;
  delivery_pct: number;
  expected_pct: number;
  win_rate: number;
  ctr: number;
  current_bid: number;
  conversion_rate?: number;
  days_elapsed: number;
  days_remaining: number;
  days_total: number;
  flight_start: string;
  flight_end: string;
}

export interface CampaignMetrics {
  campaign_id: string;
  campaign_name: string;
  status: string;
  delivery_metrics: {
    impressions_delivered: number;
    impressions_goal: number;
    delivery_pct: number;
    expected_pct: number;
    on_track: boolean;
  };
  engagement_metrics: {
    clicks: number;
    ctr: number;
  };
  financial_metrics: {
    spend: number;
    budget_total: number;
    avg_cpm: number;
  };
  auction_metrics: {
    win_rate: number;
  };
  time_context: {
    days_remaining: number;
  };
  data_freshness: string;
}

export interface Diagnosis {
  campaign_id: string;
  primary_issue: {
    type: string;
    severity: string;
    confidence: number;
    description: string;
  };
  evidence: Record<string, any>;
  secondary_issues?: Array<{
    type: string;
    severity: string;
    impact: string;
  }>;
  similar_campaigns?: number;
}

export interface Recommendation {
  recommendation_id: string;
  campaign_id: string;
  recommendation_type: string;
  recommendation: {
    action: string;
    current_value: number;
    recommended_value: number;
    change_pct: number;
  };
  expected_outcomes: {
    current_win_rate: number;
    expected_win_rate: number;
    expected_final_delivery: number;
    budget_impact: number;
    recovery_time_hours: number;
  };
  confidence_score: number;
  rationale: {
    diagnosis_summary: string;
    similar_campaign_count: number;
    calculation_method: string;
  };
}

export interface MarketIntelligence {
  market_segment: string;
  timestamp: string;
  industry: string;
  geo: string;
  competitive_landscape: {
    active_competitors: number;
    competitor_change_24h: number;
    competition_level: string;
  };
  pricing_intelligence: {
    current_cpm_floor: number;
    cpm_floor_24h_ago: number;
    cpm_change_pct: number;
    cpm_percentiles: {
      p25: number;
      p50: number;
      p75: number;
      p90: number;
    };
  };
  inventory_availability: {
    available_impressions_24h: number;
    demand_supply_ratio: number;
    inventory_tightness: string;
  };
  performance_benchmarks: {
    industry_avg_win_rate: number;
    industry_avg_ctr: number;
    industry_avg_cpm: number;
  };
}

export interface TraderProfile {
  trader_id: string;
  name: string;
  email: string;
  experience_level: string;
  years_experience: number;
  active_campaigns: number;
  recommendation_preferences: {
    detail_level: string;
    risk_tolerance: string;
    typical_acceptance_rate: number;
  };
  historical_performance: {
    avg_campaign_success_rate: number;
    avg_response_time_minutes: number;
  };
}

export interface ChatMessage {
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
}

export interface CampaignStatus {
  status: 'At Risk' | 'On Track' | 'Ahead' | 'Other';
  emoji: string;
  color: string;
}
