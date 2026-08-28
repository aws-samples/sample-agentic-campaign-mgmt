// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import type { Campaign, CampaignStatus } from '../types';

export function getCampaignStatus(campaign: Campaign): CampaignStatus {
  const ratio = campaign.delivery_pct / campaign.expected_pct;

  if (campaign.delivery_pct < campaign.expected_pct * 0.80) {
    return {
      status: 'At Risk',
      emoji: '🔴',
      color: 'danger',
    };
  } else if (campaign.delivery_pct > campaign.expected_pct * 1.15) {
    return {
      status: 'Ahead',
      emoji: '🟢',
      color: 'success',
    };
  } else if (ratio >= 0.90 && ratio <= 1.10) {
    return {
      status: 'On Track',
      emoji: '🟡',
      color: 'warning',
    };
  }

  return {
    status: 'Other',
    emoji: '⚪',
    color: 'info',
  };
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}

export function getVariance(actual: number, expected: number): number {
  return (actual - expected) / expected;
}
