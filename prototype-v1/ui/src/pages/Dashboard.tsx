// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, AlertCircle, CheckCircle } from 'lucide-react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { campaignApi } from '../api/client';
import { getCampaignStatus, formatCurrency, formatPercent } from '../utils/campaignUtils';
import type { Campaign } from '../types';

interface DashboardProps {
  traderId: string;
}

function Dashboard({ traderId }: DashboardProps) {
  const { data: campaigns = [], isLoading } = useQuery({
    queryKey: ['campaigns', traderId],
    queryFn: () => campaignApi.getCampaignsByTrader(traderId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // Calculate metrics
  const totalBudget = campaigns.reduce((sum, c) => sum + c.budget_total, 0);
  const avgDelivery = campaigns.reduce((sum, c) => sum + c.delivery_pct, 0) / campaigns.length;
  const atRiskCampaigns = campaigns.filter((c) => c.delivery_pct < c.expected_pct * 0.80);
  const onTrackCampaigns = campaigns.filter((c) => {
    const ratio = c.delivery_pct / c.expected_pct;
    return ratio >= 0.90 && ratio <= 1.10;
  });
  const aheadCampaigns = campaigns.filter((c) => c.delivery_pct > c.expected_pct * 1.15);
  const avgWinRate = campaigns.reduce((sum, c) => sum + c.win_rate, 0) / campaigns.length;

  // Status distribution
  const statusData = [
    { name: 'At Risk', value: atRiskCampaigns.length, color: '#ef4444' },
    { name: 'On Track', value: onTrackCampaigns.length, color: '#f59e0b' },
    { name: 'Ahead', value: aheadCampaigns.length, color: '#22c55e' },
  ];

  // Top 10 campaigns by delivery variance
  const campaignsByVariance = [...campaigns]
    .sort((a, b) => (a.delivery_pct - a.expected_pct) - (b.delivery_pct - b.expected_pct))
    .slice(0, 10)
    .map((c) => ({
      id: c.campaign_id,
      name: c.campaign_name.substring(0, 25),
      delivery: c.delivery_pct * 100,
      expected: c.expected_pct * 100,
      variance: ((c.delivery_pct - c.expected_pct) / c.expected_pct) * 100,
    }));

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">📊 Dashboard</h1>
        <p className="text-gray-600">Campaign performance overview</p>
      </div>

      <div className="p-6 space-y-6">
        <div className="max-w-7xl mx-auto">
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <MetricCard
              title="Total Budget"
              value={formatCurrency(totalBudget)}
              icon={<TrendingUp className="w-6 h-6" />}
              color="blue"
            />
            <MetricCard
              title="Avg Delivery"
              value={formatPercent(avgDelivery)}
              icon={<CheckCircle className="w-6 h-6" />}
              color="green"
            />
            <MetricCard
              title="At Risk"
              value={atRiskCampaigns.length.toString()}
              subtitle={`${campaigns.length} total campaigns`}
              icon={<AlertCircle className="w-6 h-6" />}
              color="red"
              change={-atRiskCampaigns.length}
            />
            <MetricCard
              title="Avg Win Rate"
              value={formatPercent(avgWinRate)}
              icon={<TrendingUp className="w-6 h-6" />}
              color="purple"
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Status Distribution */}
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Campaign Status Distribution
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={(entry) => `${entry.name}: ${entry.value}`}
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-3 gap-2 mt-4">
                {statusData.map((status) => (
                  <div key={status.name} className="text-center">
                    <div
                      className="w-4 h-4 rounded-full mx-auto mb-1"
                      style={{ backgroundColor: status.color }}
                    />
                    <div className="text-sm text-gray-600">{status.name}</div>
                    <div className="text-lg font-bold text-gray-900">{status.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Delivery vs Expected */}
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Top 10: Delivery vs Expected
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={campaignsByVariance}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="id" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="expected" fill="#93c5fd" name="Expected %" />
                  <Bar dataKey="delivery" fill="#3b82f6" name="Actual %" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Campaign Table */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Campaign Details</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      ID
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      Campaign
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      Status
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">
                      Delivery
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">
                      Expected
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">
                      Win Rate
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">
                      Bid
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-700">
                      Days Left
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((campaign) => {
                    const status = getCampaignStatus(campaign);
                    const variance = campaign.delivery_pct - campaign.expected_pct;

                    return (
                      <tr key={campaign.campaign_id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-4 text-sm font-medium text-gray-900">
                          #{campaign.campaign_id}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-700 max-w-xs truncate">
                          {campaign.campaign_name}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`badge badge-${status.color}`}>
                            {status.emoji} {status.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-sm text-right font-medium text-gray-900">
                          {formatPercent(campaign.delivery_pct)}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-gray-700">
                          {formatPercent(campaign.expected_pct)}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-gray-700">
                          {formatPercent(campaign.win_rate)}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-gray-700">
                          ${campaign.current_bid.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-sm text-right text-gray-700">
                          {campaign.days_remaining}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  color: 'blue' | 'green' | 'red' | 'purple';
  change?: number;
}

function MetricCard({ title, value, subtitle, icon, color, change }: MetricCardProps) {
  const colorClasses = {
    blue: 'bg-primary-50 text-primary-600',
    green: 'bg-success-50 text-success-600',
    red: 'bg-danger-50 text-danger-600',
    purple: 'bg-purple-50 text-purple-600',
  };

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
          {change !== undefined && (
            <div className="flex items-center mt-2">
              {change < 0 ? (
                <TrendingDown className="w-4 h-4 text-red-500 mr-1" />
              ) : (
                <TrendingUp className="w-4 h-4 text-green-500 mr-1" />
              )}
              <span className={`text-sm font-medium ${change < 0 ? 'text-red-600' : 'text-green-600'}`}>
                {Math.abs(change)}
              </span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>{icon}</div>
      </div>
    </div>
  );
}

export default Dashboard;
