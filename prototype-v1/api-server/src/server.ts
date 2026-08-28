// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import express from 'express';
import cors from 'cors';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 8000;

// Middleware
app.use(cors());
app.use(express.json());

// Data directory
const DATA_DIR = path.join(__dirname, '../../data');

// Helper function to load JSON data
async function loadData(filename: string) {
  const filePath = path.join(DATA_DIR, filename);
  const data = await fs.readFile(filePath, 'utf-8');
  return JSON.parse(data);
}

// Import Python Lambda function logic
// For POC, we'll implement the logic in TypeScript
function getCampaignStatus(campaign: any) {
  if (campaign.delivery_pct < campaign.expected_pct * 0.80) {
    return 'at_risk';
  } else if (campaign.delivery_pct > campaign.expected_pct * 1.15) {
    return 'ahead';
  } else if (campaign.delivery_pct / campaign.expected_pct >= 0.90 &&
             campaign.delivery_pct / campaign.expected_pct <= 1.10) {
    return 'on_track';
  }
  return 'other';
}

// Routes

// Get all campaigns
app.get('/api/campaigns', async (req, res) => {
  try {
    const campaigns = await loadData('campaigns.json');
    res.json(campaigns);
  } catch (error) {
    console.error('Error loading campaigns:', error);
    res.status(500).json({ error: 'Failed to load campaigns' });
  }
});

// Get campaigns by trader
app.get('/api/campaigns/trader/:traderId', async (req, res) => {
  try {
    const campaigns = await loadData('campaigns.json');
    const filtered = campaigns.filter((c: any) => c.trader_id === req.params.traderId);
    res.json(filtered);
  } catch (error) {
    console.error('Error loading campaigns:', error);
    res.status(500).json({ error: 'Failed to load campaigns' });
  }
});

// Get campaign metrics
app.get('/api/campaigns/:campaignId/metrics', async (req, res) => {
  try {
    const campaigns = await loadData('campaigns.json');
    const campaign = campaigns.find((c: any) => c.campaign_id === req.params.campaignId);

    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found' });
    }

    const metrics = {
      campaign_id: campaign.campaign_id,
      campaign_name: campaign.campaign_name,
      status: campaign.status,
      delivery_metrics: {
        impressions_delivered: Math.floor(campaign.impressions_goal * campaign.delivery_pct),
        impressions_goal: campaign.impressions_goal,
        delivery_pct: campaign.delivery_pct,
        expected_pct: campaign.expected_pct,
        on_track: getCampaignStatus(campaign) === 'on_track',
      },
      engagement_metrics: {
        clicks: Math.floor(campaign.impressions_goal * campaign.delivery_pct * campaign.ctr),
        ctr: campaign.ctr,
      },
      financial_metrics: {
        spend: campaign.budget_total * campaign.delivery_pct,
        budget_total: campaign.budget_total,
        avg_cpm: campaign.current_bid,
      },
      auction_metrics: {
        win_rate: campaign.win_rate,
      },
      time_context: {
        days_remaining: campaign.days_remaining,
      },
      data_freshness: new Date().toISOString(),
    };

    res.json(metrics);
  } catch (error) {
    console.error('Error loading metrics:', error);
    res.status(500).json({ error: 'Failed to load metrics' });
  }
});

// Diagnose campaign
app.post('/api/campaigns/:campaignId/diagnose', async (req, res) => {
  try {
    const campaigns = await loadData('campaigns.json');
    const markets = await loadData('market_intelligence.json');
    const campaign = campaigns.find((c: any) => c.campaign_id === req.params.campaignId);

    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found' });
    }

    const marketSegment = `${campaign.industry}_${campaign.geo}`;
    const market = markets.find((m: any) => m.market_segment === marketSegment);

    let diagnosis: any = {
      campaign_id: campaign.campaign_id,
      primary_issue: {},
      evidence: {},
      similar_campaigns: 17,
    };

    // Diagnose bid too low
    if (market && campaign.current_bid < market.pricing_intelligence.current_cpm_floor) {
      diagnosis.primary_issue = {
        type: 'bid_too_low',
        severity: 'high',
        confidence: 0.95,
        description: `Your current bid ($${campaign.current_bid.toFixed(2)}) is below the market floor ($${market.pricing_intelligence.current_cpm_floor.toFixed(2)}). You're only winning ${(campaign.win_rate * 100).toFixed(0)}% of auctions.`,
      };
      diagnosis.evidence = {
        current_bid: campaign.current_bid,
        market_floor: market.pricing_intelligence.current_cpm_floor,
        win_rate: campaign.win_rate,
        industry_avg: market.performance_benchmarks.industry_avg_win_rate,
      };
    } else if (campaign.win_rate < 0.15) {
      diagnosis.primary_issue = {
        type: 'low_win_rate',
        severity: 'high',
        confidence: 0.85,
        description: `Your win rate (${(campaign.win_rate * 100).toFixed(1)}%) is significantly below industry average. Consider increasing your bid.`,
      };
      diagnosis.evidence = {
        win_rate: campaign.win_rate,
        current_bid: campaign.current_bid,
      };
    } else {
      diagnosis.primary_issue = {
        type: 'pacing_issue',
        severity: 'medium',
        confidence: 0.75,
        description: 'Campaign is behind on pacing but no specific technical issue detected.',
      };
      diagnosis.evidence = {
        delivery_pct: campaign.delivery_pct,
        expected_pct: campaign.expected_pct,
      };
    }

    res.json(diagnosis);
  } catch (error) {
    console.error('Error diagnosing campaign:', error);
    res.status(500).json({ error: 'Failed to diagnose campaign' });
  }
});

// Get recommendation
app.post('/api/campaigns/:campaignId/recommend', async (req, res) => {
  try {
    const campaigns = await loadData('campaigns.json');
    const markets = await loadData('market_intelligence.json');
    const campaign = campaigns.find((c: any) => c.campaign_id === req.params.campaignId);

    if (!campaign) {
      return res.status(404).json({ error: 'Campaign not found' });
    }

    const marketSegment = `${campaign.industry}_${campaign.geo}`;
    const market = markets.find((m: any) => m.market_segment === marketSegment);

    let recommendedBid = campaign.current_bid * 1.25;
    if (market) {
      recommendedBid = Math.max(
        market.pricing_intelligence.current_cpm_floor * 1.08,
        campaign.current_bid * 1.25
      );
    }

    const changePct = (recommendedBid - campaign.current_bid) / campaign.current_bid;

    const recommendation = {
      recommendation_id: `rec_${Date.now()}`,
      campaign_id: campaign.campaign_id,
      recommendation_type: 'bid_adjustment',
      recommendation: {
        action: 'increase_bid',
        current_value: campaign.current_bid,
        recommended_value: recommendedBid,
        change_pct: changePct,
      },
      expected_outcomes: {
        current_win_rate: campaign.win_rate,
        expected_win_rate: Math.min(campaign.win_rate * (1 + changePct * 0.8), 0.45),
        expected_final_delivery: 0.95,
        budget_impact: campaign.budget_total * changePct,
        recovery_time_hours: 18,
      },
      // expected_outcomes: {
      //   current_win_rate: campaign.win_rate,
      //   expected_win_rate: 0.32,
      //   expected_final_delivery: 0.95,
      //   budget_impact: campaign.budget_total * changePct,
      //   recovery_time_hours: 18,
      // },
      confidence_score: 0.85,
      rationale: {
        diagnosis_summary: 'Bid below market floor',
        similar_campaign_count: 17,
        calculation_method: 'ensemble',
      },
    };

    res.json(recommendation);
  } catch (error) {
    console.error('Error generating recommendation:', error);
    res.status(500).json({ error: 'Failed to generate recommendation' });
  }
});

// Get market intelligence
app.get('/api/market/:industry/:geo', async (req, res) => {
  try {
    const markets = await loadData('market_intelligence.json');
    const marketSegment = `${req.params.industry}_${req.params.geo}`;
    const market = markets.find((m: any) => m.market_segment === marketSegment);

    if (!market) {
      return res.status(404).json({ error: 'Market segment not found' });
    }

    res.json(market);
  } catch (error) {
    console.error('Error loading market intelligence:', error);
    res.status(500).json({ error: 'Failed to load market intelligence' });
  }
});

// Get traders
app.get('/api/traders', async (req, res) => {
  try {
    const traders = await loadData('trader_profiles.json');
    res.json(traders);
  } catch (error) {
    console.error('Error loading traders:', error);
    res.status(500).json({ error: 'Failed to load traders' });
  }
});

// Get trader by ID
app.get('/api/traders/:traderId', async (req, res) => {
  try {
    const traders = await loadData('trader_profiles.json');
    const trader = traders.find((t: any) => t.trader_id === req.params.traderId);

    if (!trader) {
      return res.status(404).json({ error: 'Trader not found' });
    }

    res.json(trader);
  } catch (error) {
    console.error('Error loading trader:', error);
    res.status(500).json({ error: 'Failed to load trader' });
  }
});

// Chat endpoint - simulates Bedrock Agent responses
app.post('/api/chat', async (req, res) => {
  try {
    const { message, context } = req.body;
    const messageLower = message.toLowerCase();

    // Extract campaign ID if present
    const campaignIdMatch = message.match(/\b\d{4}\b/);
    const campaignId = campaignIdMatch ? campaignIdMatch[0] : null;

    let response = '';

    if (campaignId) {
      const campaigns = await loadData('campaigns.json');
      const campaign = campaigns.find((c: any) => c.campaign_id === campaignId);

      if (campaign) {
        if (messageLower.includes('wrong') || messageLower.includes('issue') || messageLower.includes('problem')) {
          // Diagnose
          response = `## 🔍 Campaign #${campaignId} Diagnosis\n\n`;
          response += `**Campaign:** ${campaign.campaign_name}\n\n`;
          response += `Your campaign is **${((1 - campaign.delivery_pct / campaign.expected_pct) * 100).toFixed(0)}% behind schedule**.\n\n`;
          response += `**Primary Issue:** Bid too low\n`;
          response += `- Current bid: $${campaign.current_bid.toFixed(2)}\n`;
          response += `- Win rate: ${(campaign.win_rate * 100).toFixed(1)}%\n\n`;
          response += `Based on similar campaigns, I recommend increasing your bid.`;
        } else if (messageLower.includes('recommend') || messageLower.includes('do') || messageLower.includes('fix')) {
          // Recommend
          const recommendedBid = campaign.current_bid * 1.30;
          response = `## 💡 Recommendation for Campaign #${campaignId}\n\n`;
          response += `**Increase Bid:**\n`;
          response += `- Current: $${campaign.current_bid.toFixed(2)}\n`;
          response += `- Recommended: $${recommendedBid.toFixed(2)} (+${((recommendedBid / campaign.current_bid - 1) * 100).toFixed(0)}%)\n\n`;
          response += `**Expected Outcomes:**\n`;
          response += `- Win rate: ${(campaign.win_rate * 100).toFixed(0)}% → 32%\n`;
          response += `- Final delivery: 95%\n`;
          response += `- Recovery time: ~18 hours\n\n`;
          response += `**Confidence:** 85% based on 17 similar campaigns`;
        } else {
          // Show metrics
          response = `## Campaign #${campaignId}: ${campaign.campaign_name}\n\n`;
          response += `**Status:** ${getCampaignStatus(campaign) === 'at_risk' ? '🔴 At Risk' : '🟢 On Track'}\n\n`;
          response += `**Performance:**\n`;
          response += `- Delivery: ${(campaign.delivery_pct * 100).toFixed(1)}% (expected ${(campaign.expected_pct * 100).toFixed(1)}%)\n`;
          response += `- Win Rate: ${(campaign.win_rate * 100).toFixed(1)}%\n`;
          response += `- Current Bid: $${campaign.current_bid.toFixed(2)}\n`;
          response += `- Days Remaining: ${campaign.days_remaining}\n\n`;
          response += `Ask me to diagnose issues or get recommendations!`;
        }
      } else {
        response = `Campaign #${campaignId} not found.`;
      }
    } else if (messageLower.includes('at risk') || messageLower.includes('at-risk')) {
      // Show at-risk campaigns
      const campaigns = await loadData('campaigns.json');
      const atRisk = campaigns.filter((c: any) => c.delivery_pct < c.expected_pct * 0.80);

      response = `## 🚨 At-Risk Campaigns (${atRisk.length} found)\n\n`;
      atRisk.slice(0, 5).forEach((c: any) => {
        const variance = ((c.delivery_pct - c.expected_pct) / c.expected_pct * 100).toFixed(0);
        response += `**#${c.campaign_id}:** ${c.campaign_name}\n`;
        response += `- Delivery: ${(c.delivery_pct * 100).toFixed(1)}% (${variance}% variance)\n`;
        response += `- Days left: ${c.days_remaining}\n\n`;
      });
    } else {
      response = `I can help you with:\n\n`;
      response += `- Campaign status: "Show me campaign 4782"\n`;
      response += `- Diagnosis: "What's wrong with campaign 4782?"\n`;
      response += `- Recommendations: "Give me recommendations for 4782"\n`;
      response += `- At-risk campaigns: "Show me all at-risk campaigns"\n\n`;
      response += `What would you like to know?`;
    }

    res.json({ response });
  } catch (error) {
    console.error('Error processing chat:', error);
    res.status(500).json({ error: 'Failed to process chat message' });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Campaign Optimization API server running on port ${PORT}`);
  console.log(`📊 Data directory: ${DATA_DIR}`);
  console.log(`🔗 API: http://localhost:${PORT}/api`);
});
