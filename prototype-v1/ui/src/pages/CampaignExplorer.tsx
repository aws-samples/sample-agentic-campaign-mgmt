// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Search, TrendingUp, AlertTriangle, Lightbulb, BarChart3, CheckCircle, Pencil, XCircle } from 'lucide-react';
import { campaignApi } from '../api/client';
import { getCampaignStatus, formatCurrency, formatPercent, formatNumber } from '../utils/campaignUtils';
import type { Campaign } from '../types';

interface CampaignExplorerProps {
  traderId: string;
}

function CampaignExplorer({ traderId }: CampaignExplorerProps) {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('4782');
  const [activeTab, setActiveTab] = useState<'overview' | 'diagnosis' | 'recommendation' | 'market'>('overview');

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', traderId],
    queryFn: () => campaignApi.getCampaignsByTrader(traderId),
  });

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metrics', selectedCampaignId],
    queryFn: () => campaignApi.getCampaignMetrics(selectedCampaignId),
    enabled: !!selectedCampaignId,
  });

  const diagnosisMutation = useMutation({
    mutationFn: (campaignId: string) => campaignApi.diagnoseCampaign(campaignId),
  });

  const recommendationMutation = useMutation({
    mutationFn: (campaignId: string) => campaignApi.getRecommendation(campaignId),
  });

  const marketMutation = useMutation({
    mutationFn: ({ industry, geo }: { industry: string; geo: string }) =>
      campaignApi.getMarketIntelligence(industry, geo),
  });

  const selectedCampaign = campaigns.find((c) => c.campaign_id === selectedCampaignId);
  const campaignStatus = selectedCampaign ? getCampaignStatus(selectedCampaign) : null;

  const handleDiagnose = () => {
    setActiveTab('diagnosis');
    diagnosisMutation.mutate(selectedCampaignId);
  };

  const handleGetRecommendation = () => {
    setActiveTab('recommendation');
    recommendationMutation.mutate(selectedCampaignId);
  };

  const handleGetMarket = () => {
    if (selectedCampaign) {
      setActiveTab('market');
      marketMutation.mutate({
        industry: selectedCampaign.industry,
        geo: selectedCampaign.geo,
      });
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">🎯 Campaign Explorer</h1>
        <p className="text-gray-600">Detailed campaign analysis and actions</p>
      </div>

      <div className="p-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Campaign List */}
            <div className="lg:col-span-1">
              <div className="card h-full">
                <div className="flex items-center space-x-2 mb-4">
                  <Search className="w-5 h-5 text-gray-400" />
                  <h3 className="text-lg font-semibold text-gray-900">Select Campaign</h3>
                </div>

                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {campaigns.map((campaign) => {
                    const status = getCampaignStatus(campaign);
                    const isSelected = campaign.campaign_id === selectedCampaignId;

                    return (
                      <button
                        key={campaign.campaign_id}
                        onClick={() => setSelectedCampaignId(campaign.campaign_id)}
                        className={`w-full text-left p-3 rounded-lg border-2 transition-all ${
                          isSelected
                            ? 'border-primary-500 bg-primary-50'
                            : 'border-transparent hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="font-medium text-gray-900">
                            #{campaign.campaign_id}
                          </div>
                          <span className={`badge badge-${status.color} text-xs`}>
                            {status.emoji}
                          </span>
                        </div>
                        <div className="text-sm text-gray-700 truncate mb-2">
                          {campaign.campaign_name}
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{formatPercent(campaign.delivery_pct)}</span>
                          <span>{campaign.days_remaining}d left</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Campaign Details */}
            <div className="lg:col-span-2">
              {selectedCampaign && (
                <>
                  {/* Campaign Header */}
                  <div className="card mb-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h2 className="text-2xl font-bold text-gray-900 mb-1">
                          {selectedCampaign.campaign_name}
                        </h2>
                        <p className="text-gray-600">
                          Campaign #{selectedCampaign.campaign_id} •{' '}
                          {selectedCampaign.industry} • {selectedCampaign.geo.replace('_', ' ')}
                        </p>
                      </div>
                      {campaignStatus && (
                        <span className={`badge badge-${campaignStatus.color}`}>
                          {campaignStatus.emoji} {campaignStatus.status}
                        </span>
                      )}
                    </div>

                    {/* Key Metrics */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div>
                        <div className="text-sm text-gray-600">Delivery</div>
                        <div className="text-xl font-bold text-gray-900">
                          {formatPercent(selectedCampaign.delivery_pct)}
                        </div>
                        <div className="text-xs text-gray-500">
                          Expected: {formatPercent(selectedCampaign.expected_pct)}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-600">Win Rate</div>
                        <div className="text-xl font-bold text-gray-900">
                          {formatPercent(selectedCampaign.win_rate)}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-600">Current Bid</div>
                        <div className="text-xl font-bold text-gray-900">
                          ${selectedCampaign.current_bid.toFixed(2)}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-600">Days Left</div>
                        <div className="text-xl font-bold text-gray-900">
                          {selectedCampaign.days_remaining}
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="grid grid-cols-3 gap-3">
                      <button
                        onClick={handleDiagnose}
                        className="btn btn-primary flex items-center justify-center space-x-2"
                      >
                        <AlertTriangle className="w-4 h-4" />
                        <span>Diagnose</span>
                      </button>
                      <button
                        onClick={handleGetRecommendation}
                        className="btn btn-primary flex items-center justify-center space-x-2"
                      >
                        <Lightbulb className="w-4 h-4" />
                        <span>Recommend</span>
                      </button>
                      <button
                        onClick={handleGetMarket}
                        className="btn btn-primary flex items-center justify-center space-x-2"
                      >
                        <BarChart3 className="w-4 h-4" />
                        <span>Market</span>
                      </button>
                    </div>
                  </div>

                  {/* Tabs */}
                  <div className="card">
                    <div className="border-b border-gray-200 mb-4">
                      <div className="flex space-x-4">
                        {[
                          { id: 'overview', label: 'Overview' },
                          { id: 'diagnosis', label: 'Diagnosis' },
                          { id: 'recommendation', label: 'Recommendation' },
                          { id: 'market', label: 'Market' },
                        ].map((tab) => (
                          <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as any)}
                            className={`py-3 px-4 border-b-2 font-medium transition-colors ${
                              activeTab === tab.id
                                ? 'border-primary-600 text-primary-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700'
                            }`}
                          >
                            {tab.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Tab Content */}
                    <div className="min-h-[300px]">
                      {activeTab === 'overview' && metrics && (
                        <OverviewTab metrics={metrics} campaign={selectedCampaign} />
                      )}

                      {activeTab === 'diagnosis' && (
                        <div>
                          {diagnosisMutation.isPending && <LoadingSpinner />}
                          {diagnosisMutation.data && (
                            <DiagnosisTab diagnosis={diagnosisMutation.data} />
                          )}
                          {!diagnosisMutation.isPending && !diagnosisMutation.data && (
                            <EmptyState message="Click 'Diagnose' to analyze this campaign" />
                          )}
                        </div>
                      )}

                      {activeTab === 'recommendation' && (
                        <div>
                          {recommendationMutation.isPending && <LoadingSpinner />}
                          {recommendationMutation.data && (
                            <RecommendationTab recommendation={recommendationMutation.data} />
                          )}
                          {!recommendationMutation.isPending && !recommendationMutation.data && (
                            <EmptyState message="Click 'Recommend' to get AI-powered suggestions" />
                          )}
                        </div>
                      )}

                      {activeTab === 'market' && (
                        <div>
                          {marketMutation.isPending && <LoadingSpinner />}
                          {marketMutation.data && (
                            <MarketTab market={marketMutation.data} />
                          )}
                          {!marketMutation.isPending && !marketMutation.data && (
                            <EmptyState message="Click 'Market' to view market intelligence" />
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function OverviewTab({ metrics, campaign }: { metrics: any; campaign: Campaign }) {
  return (
    <div className="space-y-6">
      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Performance Metrics</h4>
        <div className="grid grid-cols-2 gap-4">
          <MetricItem
            label="Impressions"
            value={`${formatNumber(metrics.delivery_metrics.impressions_delivered)} / ${formatNumber(metrics.delivery_metrics.impressions_goal)}`}
          />
          <MetricItem
            label="Budget"
            value={`${formatCurrency(metrics.financial_metrics.spend)} / ${formatCurrency(metrics.financial_metrics.budget_total)}`}
          />
          <MetricItem label="CTR" value={formatPercent(metrics.engagement_metrics.ctr)} />
          <MetricItem
            label="Avg CPM"
            value={formatCurrency(metrics.financial_metrics.avg_cpm)}
          />
        </div>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Campaign Details</h4>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Client:</span>
            <span className="font-medium text-gray-900">{campaign.client_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Objective:</span>
            <span className="font-medium text-gray-900">{campaign.objective}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Flight Period:</span>
            <span className="font-medium text-gray-900">
              {campaign.days_elapsed} / {campaign.days_total} days
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DiagnosisTab({ diagnosis }: { diagnosis: any }) {
  return (
    <div className="space-y-4">
      <div className="p-4 bg-danger-50 border border-danger-200 rounded-lg">
        <h4 className="font-semibold text-danger-900 mb-2">
          {diagnosis.primary_issue.type.replace('_', ' ').toUpperCase()}
        </h4>
        <p className="text-danger-800 mb-3">{diagnosis.primary_issue.description}</p>
        <div className="flex items-center justify-between text-sm">
          <span className="text-danger-700">Confidence:</span>
          <span className="font-semibold text-danger-900">
            {(diagnosis.primary_issue.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Evidence</h4>
        <div className="space-y-2">
          {Object.entries(diagnosis.evidence).map(([key, value]: [string, any]) => (
            <div key={key} className="flex justify-between text-sm">
              <span className="text-gray-600">{key.replace('_', ' ')}:</span>
              <span className="font-medium text-gray-900">
                {typeof value === 'number' ? value.toFixed(2) : value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function RecommendationTab({ recommendation }: { recommendation: any }) {
  return (
    <div className="space-y-4">
      <div className="p-4 bg-primary-50 border border-primary-200 rounded-lg">
        <h4 className="font-semibold text-primary-900 mb-2">
          {recommendation.recommendation.action.replace('_', ' ').toUpperCase()}
        </h4>
        <div className="grid grid-cols-3 gap-4 mb-3">
          <div>
            <div className="text-xs text-primary-700">Current</div>
            <div className="text-lg font-bold text-primary-900">
              ${recommendation.recommendation.current_value.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs text-primary-700">Recommended</div>
            <div className="text-lg font-bold text-primary-900">
              ${recommendation.recommendation.recommended_value.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs text-primary-700">Change</div>
            <div className="text-lg font-bold text-primary-900">
              {(recommendation.recommendation.change_pct * 100).toFixed(1)}%
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-primary-700">Confidence:</span>
          <span className="font-semibold text-primary-900">
            {(recommendation.confidence_score * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Expected Outcomes</h4>
        <div className="space-y-2">
          <MetricItem
            label="Win Rate"
            value={`${formatPercent(recommendation.expected_outcomes.current_win_rate)} → ${formatPercent(recommendation.expected_outcomes.expected_win_rate)}`}
          />
          <MetricItem
            label="Final Delivery"
            value={formatPercent(recommendation.expected_outcomes.expected_final_delivery)}
          />
          <MetricItem
            label="Budget Impact"
            value={formatCurrency(recommendation.expected_outcomes.budget_impact)}
          />
          <MetricItem
            label="Recovery Time"
            value={`~${recommendation.expected_outcomes.recovery_time_hours} hours`}
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <button className="btn flex items-center justify-center space-x-2 bg-green-600 hover:bg-green-700 text-white">
          <CheckCircle className="w-4 h-4" />
          <span>Accept & Apply</span>
        </button>
        <button className="btn flex items-center justify-center space-x-2 bg-amber-500 hover:bg-amber-600 text-white">
          <Pencil className="w-4 h-4" />
          <span>Modify</span>
        </button>
        <button className="btn flex items-center justify-center space-x-2 bg-red-500 hover:bg-red-600 text-white">
          <XCircle className="w-4 h-4" />
          <span>Reject</span>
        </button>
      </div>
    </div>
  );
}

function MarketTab({ market }: { market: any }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Competition</h4>
        <div className="space-y-2">
          <MetricItem
            label="Active Competitors"
            value={`${market.competitive_landscape.active_competitors} (${market.competitive_landscape.competitor_change_24h >= 0 ? '+' : ''}${market.competitive_landscape.competitor_change_24h})`}
          />
          <MetricItem
            label="Competition Level"
            value={market.competitive_landscape.competition_level}
          />
        </div>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Pricing</h4>
        <div className="space-y-2">
          <MetricItem
            label="CPM Floor"
            value={`$${market.pricing_intelligence.current_cpm_floor.toFixed(2)} (${(market.pricing_intelligence.cpm_change_pct * 100).toFixed(1)}%)`}
          />
          <MetricItem
            label="P25 / P50 / P90"
            value={`$${market.pricing_intelligence.cpm_percentiles.p25.toFixed(2)} / $${market.pricing_intelligence.cpm_percentiles.p50.toFixed(2)} / $${market.pricing_intelligence.cpm_percentiles.p90.toFixed(2)}`}
          />
        </div>
      </div>

      <div>
        <h4 className="font-semibold text-gray-900 mb-3">Inventory</h4>
        <div className="space-y-2">
          <MetricItem
            label="Available (24h)"
            value={formatNumber(market.inventory_availability.available_impressions_24h)}
          />
          <MetricItem
            label="Demand/Supply"
            value={market.inventory_availability.demand_supply_ratio.toFixed(1)}
          />
          <MetricItem
            label="Tightness"
            value={market.inventory_availability.inventory_tightness}
          />
        </div>
      </div>
    </div>
  );
}

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <p className="text-gray-500">{message}</p>
    </div>
  );
}

export default CampaignExplorer;
