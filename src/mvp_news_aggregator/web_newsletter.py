from datetime import datetime, timezone
from typing import Dict, List
import json
import os
import pytz
from foreign_exchange_data import get_fx_changes_from_daily_data
from market_data import get_market_changes_from_daily_data

class NewsletterGenerator:
    def __init__(self):
        pass
    
    def get_nz_date(self) -> str:
        """Get current date in New Zealand timezone"""
        nz_tz = pytz.timezone('Pacific/Auckland')
        nz_time = datetime.now(nz_tz)
        return nz_time.strftime('%Y-%m-%d')
    
    def load_curated_data(self, json_path: str = 'data/loading/newsletter_curated.json') -> Dict:
        """Load curated newsletter data from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            newsletter_data = json.load(f)
        
        # Add category labels for display
        category_names = {
            'world': 'Global News',
            'tech': 'Technology',
            'finance': 'Markets & Finance', 
            'nz': 'New Zealand'
        }
        
        # Add display labels to each article
        for category, data in newsletter_data.items():
            for story in data.get('top_stories', []):
                story['category_label'] = category
                story['category_display'] = category_names.get(category, category.title())
            for read in data.get('quick_reads', []):
                read['category_label'] = category
                read['category_display'] = category_names.get(category, category.title())
        
        return newsletter_data
    
    def generate_html(self, json_path: str = 'data/loading/newsletter_curated.json') -> str:
        """Generate complete HTML newsletter from JSON data"""
        data = self.load_curated_data(json_path)
        date = self.get_nz_date()
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily News Feed - {date}</title>
    <style>
        {self.get_css()}
    </style>
</head>
<body>
    <div class="container">
        {self.generate_header(date)}
        {self.generate_fx_box()}
        {self.generate_market_box()}
        {self.generate_content(data)}
        {self.generate_footer()}
    </div>
</body>
</html>"""
        return html
    
    def get_css(self) -> str:
        """Return CSS styles for the newsletter"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header {
            background-image: url('assets/mt_kalash_resize.png');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            color: white;
            padding: 3rem 2rem;
            text-align: center;
            position: relative;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.4);
            z-index: 1;
        }
        
        .header h1 {
            font-size: 2.5rem;
            font-weight: 300;
            margin-bottom: 0.5rem;
            position: relative;
            z-index: 2;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        
        .header .date {
            font-size: 1.1rem;
            opacity: 0.9;
            position: relative;
            z-index: 2;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            margin-bottom: 0.5rem;
        }
        
        .header .last-updated {
            font-size: 0.9rem;
            opacity: 0.8;
            position: relative;
            z-index: 2;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
        }
        
        .content {
            padding: 2rem;
        }
        
        .article {
            margin-bottom: 1.5rem;
            padding: 1.5rem;
            border-radius: 8px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
        }
        
        .article.critical {
            border-left-color: #dc3545;
            background: #fff5f5;
            box-shadow: 0 2px 4px rgba(220,53,69,0.1);
        }
        
        .article.key {
            border-left-color: #667eea;
            background: #f8f9fa;
        }
        
        .article.monitoring {
            border-left-color: #28a745;
            background: #f8fff9;
            padding: 1rem;
        }
        
        .article-header {
            margin-bottom: 0.75rem;
        }
        
        .category-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }
        
        .category-badge.tech {
            background: #e3f2fd;
            color: #1976d2;
        }
        
        .category-badge.world {
            background: #fff3e0;
            color: #f57c00;
        }
        
        .category-badge.finance {
            background: #e8f5e8;
            color: #388e3c;
        }
        
        .category-badge.nz {
            background: #f3e5f5;
            color: #7b1fa2;
        }
        
        .article-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .article-title a {
            color: #2c3e50;
            text-decoration: none;
        }
        
        .article-title a:hover {
            color: #667eea;
            text-decoration: underline;
        }
        
        .article-meta {
            font-size: 0.9rem;
            color: #6c757d;
            margin-bottom: 0.75rem;
        }
        
        .article-summary {
            color: #495057;
            margin-bottom: 0.5rem;
        }
        
        .article-reason {
            color: #28a745;
            font-style: italic;
            font-size: 0.95rem;
        }
        
        .footer {
            background: #2c3e50;
            color: white;
            padding: 2rem 1.5rem;
            text-align: center;
            font-size: 0.9rem;
        }
        
        .footer .mission {
            margin-bottom: 1rem;
            line-height: 1.6;
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .footer .feedback {
            margin-bottom: 1.5rem;
            color: #bdc3c7;
        }
        
        .footer .feedback a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        
        .footer .feedback a:hover {
            text-decoration: underline;
        }
        
        .footer .branding {
            font-weight: 600;
            color: #ecf0f1;
            font-size: 1rem;
        }
        
        .fx-box {
            margin: 1rem 2rem;
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #17a2b8;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .fx-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            cursor: pointer;
            user-select: none;
        }
        
        .fx-header:hover {
            background: rgba(23, 162, 184, 0.05);
            margin: -0.5rem;
            padding: 0.5rem;
            border-radius: 4px;
        }
        
        .fx-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2c3e50;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .collapse-icon {
            font-size: 0.8rem;
            color: #6c757d;
            transition: transform 0.3s ease;
        }
        
        .collapse-icon.collapsed {
            transform: rotate(-90deg);
        }
        
        .fx-timestamp {
            font-size: 0.85rem;
            color: #6c757d;
        }
        
        .fx-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 0.75rem;
        }
        
        .fx-rate {
            text-align: center;
            padding: 0.5rem;
            background: white;
            border-radius: 4px;
            border: 1px solid #e9ecef;
        }
        
        .fx-pair {
            font-size: 0.85rem;
            font-weight: 600;
            color: #495057;
            margin-bottom: 0.25rem;
        }
        
        .fx-value {
            font-size: 0.95rem;
            color: #17a2b8;
            font-weight: 500;
        }
        
        .fx-changes {
            display: flex;
            justify-content: space-around;
            margin-top: 0.5rem;
            font-size: 0.8rem;
            gap: 0.5rem;
        }
        
        .fx-change {
            font-weight: 500;
        }
        
        .fx-change.positive {
            color: #28a745;
        }
        
        .fx-change.negative {
            color: #dc3545;
        }
        
        .fx-change.neutral {
            color: #6c757d;
        }
        
        .collapsible-content {
            transition: max-height 0.3s ease-out, opacity 0.3s ease-out;
            overflow: hidden;
            max-height: 1000px;
            opacity: 1;
        }
        
        .collapsible-content.collapsed {
            max-height: 0;
            opacity: 0;
            margin-bottom: 0;
        }
        
        @media (max-width: 600px) {
            .fx-box {
                margin: 1rem;
                padding: 1rem;
            }
            
            .fx-grid {
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
                gap: 0.5rem;
            }
            
            .fx-changes {
                flex-direction: column;
                gap: 0.25rem;
                align-items: center;
            }
            
            .fx-change {
                font-size: 0.75rem;
            }
        }
        
        .market-box {
            margin: 1rem 2rem;
            padding: 1.5rem;
            background: #f8fff9;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .market-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            cursor: pointer;
            user-select: none;
        }
        
        .market-header:hover {
            background: rgba(40, 167, 69, 0.05);
            margin: -0.5rem;
            padding: 0.5rem;
            border-radius: 4px;
        }
        
        .market-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2c3e50;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .market-timestamp {
            font-size: 0.85rem;
            color: #6c757d;
        }
        
        .market-category {
            margin-bottom: 1rem;
        }
        
        .market-category:last-child {
            margin-bottom: 0;
        }
        
        .market-category-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: #495057;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #e9ecef;
            padding-bottom: 0.25rem;
        }
        
        .market-instrument {
            display: grid;
            grid-template-columns: 1fr auto auto auto auto;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid #f1f3f4;
            gap: 1rem;
        }
        
        .market-instrument:last-child {
            border-bottom: none;
        }
        
        .market-symbol {
            font-size: 0.9rem;
            font-weight: 600;
            color: #2c3e50;
            text-align: left;
        }
        
        .market-price {
            font-size: 0.9rem;
            color: #28a745;
            font-weight: 500;
            text-align: right;
            min-width: 100px;
        }
        
        .market-change {
            font-weight: 500;
            font-size: 0.8rem;
            text-align: center;
            min-width: 70px;
            padding: 0.2rem 0.4rem;
            border-radius: 3px;
        }
        
        .market-change.positive {
            color: #28a745;
            background: rgba(40, 167, 69, 0.1);
        }
        
        .market-change.negative {
            color: #dc3545;
            background: rgba(220, 53, 69, 0.1);
        }
        
        .market-change.neutral {
            color: #6c757d;
            background: rgba(108, 117, 125, 0.1);
        }
        
        @media (max-width: 600px) {
            .market-box {
                margin: 1rem;
                padding: 1rem;
            }
            
            .market-instrument {
                grid-template-columns: 1fr;
                gap: 0.5rem;
                text-align: left;
            }
            
            .market-price {
                text-align: left;
                min-width: auto;
            }
            
            .market-change {
                text-align: left;
                min-width: auto;
                display: inline-block;
                margin-right: 0.5rem;
                margin-bottom: 0.25rem;
            }
        }
        
        @media (max-width: 600px) {
            .container {
                margin: 0;
                box-shadow: none;
            }
            
            .header {
                padding: 1.5rem;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .content {
                padding: 1.5rem;
            }
            
            .article {
                padding: 1rem;
            }
        }
        """
    
    def generate_fx_box(self) -> str:
        """Generate foreign exchange rates box with historical changes"""
        try:
            fx_data = get_fx_changes_from_daily_data()
            
            if fx_data.get('status') != 'success' or not fx_data.get('rates'):
                return '<div class="fx-box"><p>Foreign exchange data currently unavailable</p></div>'
            
            rates_data = fx_data['rates']
            timestamp = fx_data.get('timestamp', 'Unknown')
            
            html = '<div class="fx-box">'
            html += '<div class="fx-header">'
            html += '<h3 class="fx-title">Exchange Rates</h3>'
            html += f'<div class="fx-timestamp">{timestamp}</div>'
            html += '</div>'
            
            html += '<div class="fx-grid">'
            
            # Define the order of currency pairs
            pair_order = ['NZD/USD', 'NZD/AUD', 'NZD/INR', 'NZD/CNY'] # , 'USD/BTC']
            
            for pair in pair_order:
                if pair in rates_data:
                    rate_info = rates_data[pair]
                    current_rate = rate_info['current']
                    changes = rate_info.get('changes', {})
                    
                    html += f'<div class="fx-rate">'
                    html += f'<div class="fx-pair">{pair}</div>'
                    html += f'<div class="fx-value">{current_rate}</div>'
                    
                    # Add percentage changes if available
                    if changes:
                        html += '<div class="fx-changes">'
                        for period in ['24h', '7d', '30d']:
                            if period in changes:
                                change_pct = changes[period]
                                
                                # Determine color class
                                if change_pct > 0.1:
                                    color_class = 'positive'
                                    sign = '+'
                                elif change_pct < -0.1:
                                    color_class = 'negative'
                                    sign = ''
                                else:
                                    color_class = 'neutral'
                                    sign = '+' if change_pct >= 0 else ''
                                
                                html += f'<span class="fx-change {color_class}">{period} {sign}{change_pct:.1f}%</span>'
                        html += '</div>'
                    
                    html += f'</div>'
            
            html += '</div>'
            html += '</div>'
            
            return html
            
        except Exception as e:
            print(f"Error generating FX box: {e}")
            return '<div class="fx-box"><p>Foreign exchange data currently unavailable</p></div>'
    
    def generate_market_box(self) -> str:
        """Generate market data box with historical changes"""
        try:
            market_data = get_market_changes_from_daily_data()
            
            print(f"\n=== MARKET BOX DEBUG ===")
            print(f"Market data status: {market_data.get('status')}")
            print(f"Market data keys: {list(market_data.keys())}")
            
            if market_data.get('status') != 'success':
                print(f"Market data error: {market_data.get('error')}")
                return '<div class="market-box"><p>Market data currently unavailable</p></div>'
            
            if not market_data.get('prices'):
                print("No prices data found")
                return '<div class="market-box"><p>Market data currently unavailable</p></div>'
            
            prices_data = market_data['prices']
            print(f"\nFound {len(prices_data)} instruments in prices_data:")
            for ticker, data in prices_data.items():
                print(f"  {ticker}: {data.get('display_symbol', 'NO_SYMBOL')} | Category: {data.get('category', 'NO_CATEGORY')} | Price: {data.get('current', 'NO_PRICE')}")
            timestamp = market_data.get('timestamp', 'Unknown')
            
            html = '<div class="market-box">'
            html += '<div class="market-header">'
            html += '<h3 class="market-title">Market Data</h3>'
            html += f'<div class="market-timestamp">{timestamp}</div>'
            html += '</div>'
            
            # Group instruments by category
            categories = {
                'US Indices': [],
                'International Indices': [],
                'Commodities': [],
                'ETFs': []
            }
            
            print(f"\nGrouping {len(prices_data)} instruments by category:")
            for ticker, data in prices_data.items():
                category = data['category']
                print(f"  {ticker}: {data['display_symbol']} -> {category}")
                if category in categories:
                    categories[category].append((ticker, data))
                else:
                    print(f"  WARNING: Unknown category '{category}' for {ticker}")
            
            print(f"\nCategory summary:")
            for cat_name, instruments in categories.items():
                print(f"  {cat_name}: {len(instruments)} instruments")
            
            # Display each category
            for category_name, instruments in categories.items():
                if instruments:  # Only show categories that have data
                    html += f'<div class="market-category">'
                    html += f'<div class="market-category-title">{category_name}</div>'
                    
                    # Add table headers
                    html += f'<div class="market-instrument" style="font-weight: 600; color: #6c757d; font-size: 0.8rem; border-bottom: 2px solid #e9ecef; padding: 0.5rem 0;">'
                    html += f'<div class="market-symbol">Instrument</div>'
                    html += f'<div class="market-price">Price</div>'
                    html += f'<div class="market-change">24h</div>'
                    html += f'<div class="market-change">7d</div>'
                    html += f'<div class="market-change">30d</div>'
                    html += f'</div>'
                    
                    for ticker, data in instruments:
                        current_price = data['current']
                        display_symbol = data['display_symbol']
                        currency = data['currency']
                        changes = data.get('changes', {})
                        
                        # Format price: remove decimals, add commas
                        formatted_price = f"{int(current_price):,}"
                        
                        html += f'<div class="market-instrument">'
                        html += f'<div class="market-symbol">{display_symbol}</div>'
                        html += f'<div class="market-price">{formatted_price} {currency}</div>'
                        
                        # Add individual change columns (24h, 7d, 30d)
                        for period in ['24h', '7d', '30d']:
                            if period in changes:
                                change_pct = changes[period]
                                
                                # Determine color class
                                if change_pct > 0.1:
                                    color_class = 'positive'
                                    sign = '+'
                                elif change_pct < -0.1:
                                    color_class = 'negative'
                                    sign = ''
                                else:
                                    color_class = 'neutral'
                                    sign = '+' if change_pct >= 0 else ''
                                
                                html += f'<div class="market-change {color_class}">{sign}{change_pct:.1f}%</div>'
                            else:
                                html += f'<div class="market-change neutral">-</div>'
                        
                        html += f'</div>'
                    
                    html += f'</div>'
            
            html += '</div>'
            
            return html
            
        except Exception as e:
            print(f"Error generating market box: {e}")
            return '<div class="market-box"><p>Market data currently unavailable</p></div>'
    
    def generate_header(self, date: str) -> str:
        """Generate newsletter header"""
        formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
        
        # Get current NZT time for last updated
        nz_tz = pytz.timezone('Pacific/Auckland')
        current_nz_time = datetime.now(nz_tz)
        last_updated = current_nz_time.strftime('%d %b %Y, %-I:%M %p %Z')
        
        return f"""
        <div class="header">
            <h1>Daily News Feed</h1>
            <div class="date">{formatted_date}</div>
            <div class="last-updated">Last Updated: {last_updated}</div>
        </div>
        """
    
    def generate_content(self, data: Dict) -> str:
        """Generate priority-based newsletter content"""
        # Collect ALL stories with importance scores
        all_top_stories = []
        all_quick_reads = []
        
        for category, articles in data.items():
            all_top_stories.extend(articles.get('top_stories', []))
            all_quick_reads.extend(articles.get('quick_reads', []))
        
        # Sort top stories by importance score (highest first)
        all_top_stories.sort(key=lambda x: x.get('importance_score', 5), reverse=True)
        
        # Sort quick reads by category priority: tech, world, finance, nz
        category_priority = {'tech': 1, 'world': 2, 'finance': 3, 'nz': 4}
        all_quick_reads.sort(key=lambda x: category_priority.get(x.get('category_label', ''), 5))
        
        content = '<div class="content">'
        
        # All articles in priority order without section titles
        for story in all_top_stories:
            content += self.generate_mixed_article_html(story, tier="critical" if story in all_top_stories[:5] else "key")
        
        for read in all_quick_reads:
            content += self.generate_mixed_article_html(read, tier="monitoring")
        
        content += '</div>'
        return content
    
    def generate_mixed_article_html(self, article: Dict, tier: str) -> str:
        """Generate HTML for articles in the new priority-based layout"""
        tier_styles = {
            "critical": "article critical",
            "key": "article key", 
            "monitoring": "article monitoring"
        }
        
        css_class = tier_styles.get(tier, "article")
        
        # Format published date - convert to NZT
        try:
            if isinstance(article.get('published'), str):
                # Parse the UTC datetime
                pub_date = datetime.fromisoformat(article['published'].replace('Z', '+00:00'))
                
                # Convert to New Zealand timezone
                nz_tz = pytz.timezone('Pacific/Auckland')
                nz_date = pub_date.astimezone(nz_tz)
                
                # Format as full datetime with timezone
                formatted_date = nz_date.strftime('%d %b %Y, %-I:%M %p %Z')
            else:
                formatted_date = "Recent"
        except Exception as e:
            formatted_date = "Recent"
        
        html = f'<div class="{css_class}">'
        
        # Category badge + title
        html += f'<div class="article-header">'
        html += f'<span class="category-badge {article.get("category_label", "")}">{article.get("category_display", "")}</span>'
        html += f'<div class="article-title"><a href="{article.get("url", "#")}" target="_blank">{article.get("title", "No Title")}</a></div>'
        html += f'</div>'
        
        # Meta info
        html += f'<div class="article-meta">{article.get("source", "Unknown")} • {formatted_date}'
        if tier != "monitoring" and article.get('importance_score'):
            html += f' • Priority: {article["importance_score"]}/10'
        html += f'</div>'
        
        # Content based on tier and available summaries
        if tier == "critical" or tier == "key":
            if article.get('enhanced_summary'):
                html += f'<div class="article-summary">{article["enhanced_summary"]}</div>'
            elif article.get('llm_summary'):
                html += f'<div class="article-summary">{article["llm_summary"]}</div>'
        elif tier == "monitoring" and article.get('llm_reason'):
            html += f'<div class="article-reason">{article["llm_reason"]}</div>'
        
        html += '</div>'
        return html
    
    
    def generate_footer(self) -> str:
        """Generate newsletter footer"""
        return """
        <div class="footer">
            <div class="mission">
                Inform on global events capturing key and interesting events that influence our lives and delivering that information in an easily consumable format.
            </div>
            <div class="feedback">
                Appreciate feedback on source or content curation, new categories, or general queries. Send to: 
                <a href="mailto:asif.ajcanalytics@gmail.com">asif.ajcanalytics@gmail.com</a>
            </div>
            <div class="branding">
                AJC Analytics Limited
            </div>
        </div>
        """
    
    def save_newsletter(self, output_path: str = None, json_path: str = 'data/loading/newsletter_curated.json') -> str:
        """Generate and save newsletter HTML file"""
        if not output_path:
            date = self.get_nz_date()
            output_path = f"archive/newsletter_{date}.html"
        
        html_content = self.generate_html(json_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        with open("newsletter.html", 'w', encoding='utf-8') as f:
            f.write(html_content)

        with open("docs/index.html", 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
def regenerate_newsletter_with_nzt(
    json_path: str = 'data/loading/newsletter_curated.json',
    output_path: str = None
) -> str:
    """
    Regenerate newsletter HTML from existing JSON with NZT formatting.
    No ETL - just processes saved data with updated time display.
    """
    # Initialize generator
    generator = NewsletterGenerator()
    
    # Generate with updated formatting (your new NZT code)
    html_content = generator.generate_html(json_path)
    
    # Save to multiple locations
    if not output_path:
        date = datetime.now().strftime('%Y-%m-%d')
        output_path = f"archive/newsletter_{date}_nzt.html"
    
    # Write to all the usual places
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    with open("newsletter.html", 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    with open("docs/index.html", 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Newsletter regenerated with NZT formatting: {output_path}")
    return output_path



# Usage function
def generate_newsletter():
    """Generate newsletter from JSON file"""
    generator = NewsletterGenerator()
    output_file = generator.save_newsletter()
    print(f"Newsletter generated: {output_file}")
    return output_file




def test_nzt_formatting():
    """Test the NZT conversion on existing data"""
    with open('data/loading/newsletter_curated.json', 'r') as f:
        data = json.load(f)
    
    # Test formatting on first article
    test_article = None
    for category in data.values():
        if category.get('top_stories'):
            test_article = category['top_stories'][0]
            break
    
    if test_article and test_article.get('published'):
        print("Testing NZT conversion:")
        print(f"Original: {test_article['published']}")
        
        # Test the conversion
        pub_date = datetime.fromisoformat(test_article['published'].replace('Z', '+00:00'))
        nz_tz = pytz.timezone('Pacific/Auckland')
        nz_date = pub_date.astimezone(nz_tz)
        formatted_date = nz_date.strftime('%d %b %Y, %-I:%M %p %Z')
        
        print(f"Converted: {formatted_date}")




# if __name__ == "__main__":
#     generate_newsletter()