#!/usr/bin/env python3

# Quick test of the foreign exchange functionality
import sys
sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

from foreign_exchange_data import test_fx_data

if __name__ == "__main__":
    print("Testing Foreign Exchange Data...")
    print("=" * 50)
    test_fx_data()
