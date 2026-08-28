// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MessageSquare, LayoutDashboard, Search, User, TrendingUp, Sun, Moon } from 'lucide-react';
import { traderApi, campaignApi } from '../api/client';
import { getCampaignStatus } from '../utils/campaignUtils';
import { useTheme } from '../hooks/useTheme';

interface LayoutProps {
  children: ReactNode;
  selectedTrader: string;
  onTraderChange: (traderId: string) => void;
}

function Layout({ children, selectedTrader, onTraderChange }: LayoutProps) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const { data: traders = [] } = useQuery({
    queryKey: ['traders'],
    queryFn: traderApi.getTraders,
  });

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', selectedTrader],
    queryFn: () => campaignApi.getCampaignsByTrader(selectedTrader),
    enabled: !!selectedTrader,
  });

  const trader = traders.find((t) => t.trader_id === selectedTrader);

  const atRiskCount = campaigns.filter(
    (c) => c.delivery_pct < c.expected_pct * 0.80
  ).length;

  const onTrackCount = campaigns.filter((c) => {
    const ratio = c.delivery_pct / c.expected_pct;
    return ratio >= 0.90 && ratio <= 1.10;
  }).length;

  const navItems = [
    { path: '/chat', icon: MessageSquare, label: 'Chat Assistant' },
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/campaigns', icon: Search, label: 'Campaign Explorer' },
  ];

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-gray-900 dark:text-white">Campaign Agent</h1>
                <p className="text-xs text-gray-500 dark:text-gray-400">AI Optimization</p>
              </div>
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 transition-colors"
              aria-label="Toggle theme"
            >
              {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Trader Profile & Stats */}
        <div className="p-4 border-t border-gray-200 space-y-4">
          {/* Trader Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">
              <User className="w-3 h-3 inline mr-1" />
              Trader Profile
            </label>
            <select
              aria-label="Trader Profile"
              value={selectedTrader}
              onChange={(e) => onTraderChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              {traders.map((t) => (
                <option key={t.trader_id} value={t.trader_id}>
                  {t.name} ({t.experience_level})
                </option>
              ))}
            </select>
          </div>

          {/* Trader Stats */}
          {trader && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Active Campaigns</span>
                <span className="font-semibold text-gray-900">{campaigns.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Success Rate</span>
                <span className="font-semibold text-green-600">
                  {(trader.historical_performance.avg_campaign_success_rate * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          )}

          {/* Quick Stats */}
          <div className="space-y-2 pt-2 border-t border-gray-200">
            <div className="flex items-center justify-between p-3 bg-danger-50 rounded-lg">
              <span className="text-sm font-medium text-danger-700">At Risk</span>
              <span className="text-xl font-bold text-danger-700">{atRiskCount}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-success-50 rounded-lg">
              <span className="text-sm font-medium text-success-700">On Track</span>
              <span className="text-xl font-bold text-success-700">{onTrackCount}</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}

export default Layout;
