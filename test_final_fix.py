#!/usr/bin/env python3

# Quick test after fixes
import sys
import os
sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

print("🧪 Testing Fixed FX System")
print("=" * 30)

from foreign_exchange_data import pull_fx_data

result = pull_fx_data()

if result.get('status') == 'success':
    print(f"\n✅ Success! Results:")
    for pair, data in result.get('rates', {}).items():
        current = data.get('current')
        changes = data.get('changes', {})
        
        if changes:
            change_parts = []
            for period in ['24h', '7d', '30d']:
                if period in changes:
                    change = changes[period]
                    color = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    change_parts.append(f"{period}: {color}{change:+.1f}%")
            
            change_str = f" ({', '.join(change_parts)})" if change_parts else ""
            print(f"  {pair}: {current}{change_str}")
        else:
            print(f"  {pair}: {current} (no historical changes)")
else:
    print(f"❌ Failed: {result.get('error')}")
