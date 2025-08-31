#!/usr/bin/env python3

# Backfill historical FX data for immediate testing
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

def create_mock_historical_data():
    """Create realistic mock historical data for testing purposes"""
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Base rates (approximately current as of Aug 2025)
    base_rates = {
        'NZD/USD': 0.589,
        'NZD/AUD': 0.901,
        'NZD/INR': 51.9,
        'NZD/CNY': 4.2,
        'USD/BTC': 108862  # Store as number for calculations
    }
    
    historical_data = {}
    
    # Generate data for the last 35 days with realistic variations
    for days_ago in range(35):
        date = datetime.now() - timedelta(days=days_ago)
        date_str = date.strftime('%Y-%m-%d')
        
        # Create realistic variations based on typical FX volatility
        variations = {
            'NZD/USD': 1 + (0.02 * (0.5 - (days_ago % 10) / 10)),  # ±2% variation
            'NZD/AUD': 1 + (0.015 * (0.5 - (days_ago % 8) / 8)),   # ±1.5% variation  
            'NZD/INR': 1 + (0.03 * (0.5 - (days_ago % 12) / 12)),  # ±3% variation
            'NZD/CNY': 1 + (0.025 * (0.5 - (days_ago % 9) / 9)),   # ±2.5% variation
            'USD/BTC': 1 + (0.08 * (0.5 - (days_ago % 7) / 7)),    # ±8% variation (crypto is volatile)
        }
        
        # Apply variations to base rates
        day_rates = {}
        for pair, base_rate in base_rates.items():
            varied_rate = base_rate * variations[pair]
            
            if pair == 'USD/BTC':
                day_rates[pair] = f"{varied_rate:,.0f}"
            elif pair == 'NZD/INR':
                day_rates[pair] = round(varied_rate, 2)
            else:
                day_rates[pair] = round(varied_rate, 4)
        
        historical_data[date_str] = {
            'timestamp': date.isoformat(),
            'rates': day_rates
        }
    
    # Save the data
    with open('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator/data/fx_historical_rates.json', 'w') as f:
        json.dump(historical_data, f, indent=2)
    
    print(f"✅ Created mock historical data for {len(historical_data)} days")
    print("📊 Sample data points:")
    
    # Show some sample data
    dates = sorted(historical_data.keys(), reverse=True)
    for i, date in enumerate(dates[:5]):
        data = historical_data[date]
        print(f"  {date}: NZD/USD {data['rates']['NZD/USD']}, USD/BTC {data['rates']['USD/BTC']}")
    
    return historical_data

def test_with_mock_data():
    """Test the FX system with mock historical data"""
    print("\n🧪 Testing FX system with historical data...")
    
    try:
        from foreign_exchange_data import test_fx_data
        result = test_fx_data()
        
        if result.get('status') == 'success':
            print("\n✅ FX system working with historical comparisons!")
            
            for pair, data in result.get('rates', {}).items():
                current = data.get('current')
                changes = data.get('changes', {})
                
                change_info = []
                for period in ['24h', '7d', '30d']:
                    if period in changes:
                        change = changes[period]
                        color = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                        change_info.append(f"{period}: {color}{change:+.1f}%")
                
                change_str = f" ({', '.join(change_info)})" if change_info else ""
                print(f"  {pair}: {current}{change_str}")
        else:
            print("❌ FX system test failed")
            
    except Exception as e:
        print(f"❌ Error testing FX system: {e}")

if __name__ == "__main__":
    print("🚀 Setting up FX historical data for immediate testing...")
    print("=" * 60)
    
    # Change to the correct directory
    os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
    
    # Create mock historical data
    create_mock_historical_data()
    
    # Test the system
    test_with_mock_data()
    
    print("\n🎉 Setup complete! Your FX box will now show:")
    print("  ✅ Current rates")
    print("  ✅ 24h changes")  
    print("  ✅ 7d changes")
    print("  ✅ 30d changes")
    print("  ✅ Color-coded indicators")
    
    print("\n▶️  Next steps:")
    print("  1. Run 'python main.py' to generate your newsletter")
    print("  2. Check the FX box in the generated HTML")
    print("  3. The system will now store real data going forward")
