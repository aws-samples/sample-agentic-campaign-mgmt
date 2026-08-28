# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Data Exploration Utility

Quick script to explore and query the synthetic data.

Usage:
    python explore_data.py
"""

import json
from typing import List, Dict


def load_data():
    """Load all data files"""
    data = {}

    files = [
        'campaigns',
        'campaign_configs',
        'historical_outcomes',
        'market_intelligence',
        'trader_profiles',
        'stream_events_sample',
        'recommendation_history'
    ]

    for file in files:
        with open(f'prototype-v1/data/{file}.json', 'r') as f:
            data[file] = json.load(f)

    return data


def show_campaign_summary(data):
    """Show campaign statistics"""
    campaigns = data['campaigns']

    print("\n" + "="*70)
    print("CAMPAIGN SUMMARY")
    print("="*70)

    # Overall stats
    print(f"\nTotal Campaigns: {len(campaigns)}")

    # By status
    statuses = {}
    for c in campaigns:
        status = "At Risk" if c['delivery_pct'] < c['expected_pct'] * 0.80 else \
                 "On Track" if 0.90 <= c['delivery_pct'] / c['expected_pct'] <= 1.10 else \
                 "Ahead" if c['delivery_pct'] > c['expected_pct'] * 1.15 else "Other"
        statuses[status] = statuses.get(status, 0) + 1

    print("\nBy Status:")
    for status, count in sorted(statuses.items()):
        pct = count / len(campaigns) * 100
        print(f"  {status:15} {count:3} ({pct:5.1f}%)")

    # By trader
    traders = {}
    for c in campaigns:
        traders[c['trader_id']] = traders.get(c['trader_id'], 0) + 1

    print("\nBy Trader:")
    for trader, count in sorted(traders.items()):
        print(f"  {trader:20} {count:3} campaigns")

    # By industry
    industries = {}
    for c in campaigns:
        industries[c['industry']] = industries.get(c['industry'], 0) + 1

    print("\nBy Industry:")
    for industry, count in sorted(industries.items(), key=lambda x: -x[1]):
        print(f"  {industry:20} {count:3} campaigns")


def show_at_risk_campaigns(data):
    """Show at-risk campaigns details"""
    campaigns = data['campaigns']

    at_risk = [
        c for c in campaigns
        if c['delivery_pct'] < c['expected_pct'] * 0.80
    ]

    print("\n" + "="*70)
    print("AT-RISK CAMPAIGNS")
    print("="*70)

    print(f"\nFound {len(at_risk)} at-risk campaigns:\n")

    for c in sorted(at_risk, key=lambda x: x['delivery_pct'] / x['expected_pct']):
        variance = (c['delivery_pct'] - c['expected_pct']) / c['expected_pct']
        print(f"Campaign #{c['campaign_id']} - {c['campaign_name'][:40]}")
        print(f"  Delivery: {c['delivery_pct']:.1%} (expected {c['expected_pct']:.1%}) - {variance:+.1%}")
        print(f"  Win Rate: {c['win_rate']:.1%} | Bid: ${c['current_bid']:.2f}")
        print(f"  Days Remaining: {c['days_remaining']}")
        print()


def show_special_campaigns(data):
    """Show the special test campaigns"""
    campaigns = data['campaigns']

    print("\n" + "="*70)
    print("SPECIAL TEST CAMPAIGNS")
    print("="*70)

    special_ids = ['4782', '5201']

    for cid in special_ids:
        c = next((x for x in campaigns if x['campaign_id'] == cid), None)
        if c:
            print(f"\nCampaign #{c['campaign_id']} - {c['campaign_name']}")
            print(f"  Status: {'At Risk' if c['delivery_pct'] < c['expected_pct'] * 0.80 else 'On Track'}")
            print(f"  Trader: {c['trader_id']}")
            print(f"  Industry: {c['industry']} | Geo: {c['geo']}")
            print(f"  Budget: ${c['budget_total']:,.0f} (${c['spend'] if 'spend' in c else c['budget_total'] * c['delivery_pct']:,.0f} spent)")
            print(f"  Delivery: {c['delivery_pct']:.1%} vs Expected {c['expected_pct']:.1%}")
            print(f"  Impressions: {int(c['impressions_goal'] * c['delivery_pct']):,} / {c['impressions_goal']:,}")
            print(f"  Win Rate: {c['win_rate']:.1%} | CTR: {c['ctr']:.2%}")
            print(f"  Current Bid: ${c['current_bid']:.2f}")
            print(f"  Days: {c['days_elapsed']} elapsed, {c['days_remaining']} remaining")


def show_historical_examples(data):
    """Show historical success examples"""
    outcomes = data['historical_outcomes']

    print("\n" + "="*70)
    print("HISTORICAL SUCCESS EXAMPLES")
    print("="*70)

    special_ids = ['4201', '3890']

    for cid in special_ids:
        c = next((x for x in outcomes if x['campaign_id'] == cid), None)
        if c:
            print(f"\nCampaign #{c['campaign_id']} - {c['campaign_name']}")
            print(f"  Run Date: {c['run_date']}")
            print(f"  Industry: {c['industry']} | Geo: {c['geo']}")
            print(f"  Budget: ${c['budget_total']:,}")
            print(f"\n  Initial Problem:")
            init = c['initial_state']
            day_key = [k for k in init.keys() if 'delivery' in k][0]
            print(f"    - Delivery: {init[day_key]:.1%}")
            print(f"    - Bid: ${init[[k for k in init.keys() if 'bid' in k][0]]:.2f}")
            print(f"    - Market Floor: ${init[[k for k in init.keys() if 'market_floor' in k][0]]:.2f}")
            print(f"\n  Intervention:")
            print(f"    - Type: {c['intervention']['type']}")
            print(f"    - Changed bid: ${c['intervention']['from_bid']:.2f} -> ${c['intervention']['to_bid']:.2f}")
            print(f"    - Increase: {c['intervention']['change_pct']:.1%}")
            print(f"\n  Outcome:")
            print(f"    - Final Delivery: {c['outcome']['final_delivery_pct']:.1%}")
            print(f"    - Recovery Time: {c['outcome']['recovery_time_hours']} hours")
            print(f"    - Status: {c['outcome']['outcome_status']}")
            print(f"    - Goal Achieved: {c['outcome']['goal_achieved']}")


def show_market_conditions(data):
    """Show market intelligence for key markets"""
    markets = data['market_intelligence']

    print("\n" + "="*70)
    print("MARKET CONDITIONS")
    print("="*70)

    # Show automotive Chicago (Journey 1 market)
    market = next((m for m in markets if m['market_segment'] == 'automotive_chicago_dma'), None)

    if market:
        print(f"\nMarket: {market['market_segment']}")
        print(f"  Geo: {market['geo']} | Industry: {market['industry']}")
        print(f"\n  Competition:")
        print(f"    - Active Competitors: {market['competitive_landscape']['active_competitors']}")
        print(f"    - Change (24h): {market['competitive_landscape']['competitor_change_24h']:+d}")
        print(f"    - Level: {market['competitive_landscape']['competition_level']}")
        print(f"\n  Pricing:")
        print(f"    - CPM Floor: ${market['pricing_intelligence']['current_cpm_floor']:.2f}")
        print(f"    - Previous (24h): ${market['pricing_intelligence']['cpm_floor_24h_ago']:.2f}")
        print(f"    - Change: {market['pricing_intelligence']['cpm_change_pct']:+.1%}")
        print(f"    - Percentiles: P25=${market['pricing_intelligence']['cpm_percentiles']['p25']:.2f} | " +
              f"P50=${market['pricing_intelligence']['cpm_percentiles']['p50']:.2f} | " +
              f"P90=${market['pricing_intelligence']['cpm_percentiles']['p90']:.2f}")
        print(f"\n  Inventory:")
        print(f"    - Available (24h): {market['inventory_availability']['available_impressions_24h']:,}")
        print(f"    - Demand/Supply: {market['inventory_availability']['demand_supply_ratio']:.1f}")
        print(f"    - Tightness: {market['inventory_availability']['inventory_tightness']}")
        print(f"\n  Benchmarks:")
        print(f"    - Avg Win Rate: {market['performance_benchmarks']['industry_avg_win_rate']:.1%}")
        print(f"    - Avg CTR: {market['performance_benchmarks']['industry_avg_ctr']:.2%}")
        print(f"    - Avg CPM: ${market['performance_benchmarks']['industry_avg_cpm']:.2f}")


def show_traders(data):
    """Show trader profiles"""
    traders = data['trader_profiles']

    print("\n" + "="*70)
    print("TRADER PROFILES")
    print("="*70)

    for trader in traders:
        print(f"\n{trader['name']} ({trader['trader_id']})")
        print(f"  Email: {trader['email']}")
        print(f"  Experience: {trader['experience_level'].title()} ({trader['years_experience']} years)")
        print(f"  Active Campaigns: {trader['active_campaigns']}")
        print(f"  Preferences:")
        print(f"    - Detail Level: {trader['recommendation_preferences']['detail_level']}")
        print(f"    - Risk Tolerance: {trader['recommendation_preferences']['risk_tolerance']}")
        print(f"    - Acceptance Rate: {trader['recommendation_preferences']['typical_acceptance_rate']:.1%}")
        print(f"  Performance:")
        print(f"    - Success Rate: {trader['historical_performance']['avg_campaign_success_rate']:.1%}")
        print(f"    - Avg Response Time: {trader['historical_performance']['avg_response_time_minutes']} min")


def find_campaign(data, campaign_id):
    """Find and display specific campaign"""
    campaigns = data['campaigns']
    configs = data['campaign_configs']

    campaign = next((c for c in campaigns if c['campaign_id'] == campaign_id), None)
    config = next((c for c in configs if c['campaign_id'] == campaign_id), None)

    if not campaign:
        print(f"\nCampaign #{campaign_id} not found")
        return

    print("\n" + "="*70)
    print(f"CAMPAIGN #{campaign_id} DETAILS")
    print("="*70)

    print(f"\n{campaign['campaign_name']}")
    print(f"  Status: {campaign['status'].title()}")
    print(f"  Trader: {campaign['trader_id']}")
    print(f"  Client: {campaign['client_id']}")
    print(f"  Industry: {campaign['industry']} | Objective: {campaign['objective']}")
    print(f"  Geo: {campaign['geo']}")

    print(f"\n  PERFORMANCE:")
    print(f"    Budget: ${campaign['budget_total']:,.0f} (${campaign['budget_total'] * campaign['delivery_pct']:,.0f} spent)")
    print(f"    Delivery: {campaign['delivery_pct']:.1%} vs Expected {campaign['expected_pct']:.1%}")
    variance = (campaign['delivery_pct'] - campaign['expected_pct']) / campaign['expected_pct']
    print(f"    Variance: {variance:+.1%}")
    print(f"    Win Rate: {campaign['win_rate']:.1%}")
    print(f"    CTR: {campaign['ctr']:.2%}")
    if campaign['conversion_rate'] > 0:
        print(f"    Conversion Rate: {campaign['conversion_rate']:.2%}")

    print(f"\n  BIDDING:")
    print(f"    Current Bid: ${campaign['current_bid']:.2f}")

    print(f"\n  TIMELINE:")
    print(f"    Total: {campaign['days_total']} days")
    print(f"    Elapsed: {campaign['days_elapsed']} days")
    print(f"    Remaining: {campaign['days_remaining']} days")
    print(f"    Start: {campaign['flight_start'][:10]}")
    print(f"    End: {campaign['flight_end'][:10]}")

    if config:
        print(f"\n  TARGETING:")
        print(f"    Age: {config['targeting']['demographics']['age_range']}")
        print(f"    Gender: {config['targeting']['demographics']['gender']}")
        print(f"    Devices: {', '.join(config['targeting']['device_types'])}")
        print(f"    Interests: {', '.join(config['targeting']['interests'][:3])}")

        print(f"\n  RESTRICTIONS:")
        print(f"    Geo Locked: {config['client_restrictions']['geo_locked']}")
        print(f"    Budget Locked: {config['client_restrictions']['budget_locked']}")
        if config['client_restrictions']['notes']:
            print(f"    Notes: {config['client_restrictions']['notes']}")


def interactive_menu(data):
    """Interactive menu for exploring data"""

    while True:
        print("\n" + "="*70)
        print("SYNTHETIC DATA EXPLORER")
        print("="*70)
        print("\n1. Campaign Summary")
        print("2. At-Risk Campaigns")
        print("3. Special Test Campaigns")
        print("4. Historical Success Examples")
        print("5. Market Conditions")
        print("6. Trader Profiles")
        print("7. Find Specific Campaign")
        print("8. Exit")

        choice = input("\nSelect option (1-8): ").strip()

        if choice == '1':
            show_campaign_summary(data)
        elif choice == '2':
            show_at_risk_campaigns(data)
        elif choice == '3':
            show_special_campaigns(data)
        elif choice == '4':
            show_historical_examples(data)
        elif choice == '5':
            show_market_conditions(data)
        elif choice == '6':
            show_traders(data)
        elif choice == '7':
            campaign_id = input("Enter campaign ID: ").strip()
            find_campaign(data, campaign_id)
        elif choice == '8':
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice, please try again.")

        input("\nPress Enter to continue...")


def main():
    """Main entry point"""
    print("Loading synthetic data...")
    data = load_data()
    print("Data loaded successfully!")

    interactive_menu(data)


if __name__ == "__main__":
    main()
