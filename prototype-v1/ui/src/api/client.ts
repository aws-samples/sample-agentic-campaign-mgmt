// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import axios from 'axios';
import type {
  Campaign,
  CampaignMetrics,
  Diagnosis,
  Recommendation,
  MarketIntelligence,
  TraderProfile,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const campaignApi = {
  // Get all campaigns
  getCampaigns: async (): Promise<Campaign[]> => {
    const response = await apiClient.get('/campaigns');
    return response.data;
  },

  // Get campaigns by trader
  getCampaignsByTrader: async (traderId: string): Promise<Campaign[]> => {
    const response = await apiClient.get(`/campaigns/trader/${traderId}`);
    return response.data;
  },

  // Get campaign metrics
  getCampaignMetrics: async (campaignId: string): Promise<CampaignMetrics> => {
    const response = await apiClient.get(`/campaigns/${campaignId}/metrics`);
    return response.data;
  },

  // Diagnose campaign
  diagnoseCampaign: async (campaignId: string): Promise<Diagnosis> => {
    const response = await apiClient.post(`/campaigns/${campaignId}/diagnose`);
    return response.data;
  },

  // Get recommendation
  getRecommendation: async (campaignId: string): Promise<Recommendation> => {
    const response = await apiClient.post(`/campaigns/${campaignId}/recommend`);
    return response.data;
  },

  // Get market intelligence
  getMarketIntelligence: async (industry: string, geo: string): Promise<MarketIntelligence> => {
    const response = await apiClient.get(`/market/${industry}/${geo}`);
    return response.data;
  },
};

export const traderApi = {
  // Get all traders
  getTraders: async (): Promise<TraderProfile[]> => {
    const response = await apiClient.get('/traders');
    return response.data;
  },

  // Get trader by ID
  getTrader: async (traderId: string): Promise<TraderProfile> => {
    const response = await apiClient.get(`/traders/${traderId}`);
    return response.data;
  },
};

export const chatApi = {
  // Send chat message and get response
  sendMessage: async (message: string, context?: any): Promise<string> => {
    const response = await apiClient.post('/chat', { message, context });
    return response.data.response;
  },
};

export default apiClient;
