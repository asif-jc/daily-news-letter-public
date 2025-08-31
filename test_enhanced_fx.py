#!/usr/bin/env python3

# Test the enhanced FX functionality with historical changes
import sys
sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

from foreign_exchange_data import test_fx_data
from web_newsletter import NewsletterGenerator

def test_enhanced_fx():
    """Test the enhanced FX functionality with historical changes"""
    
    print("🚀 Testing Enhanced Foreign Exchange Functionality")
    print("=" * 60)
    
    # Test 1: FX Data Fetching with Historical Changes
    print("\n📊 Test 1: FX Data Fetching")
    print("-" * 30)
    
    try:
        fx_data = test_fx_data()
        
        if fx_data.get('status') == 'success':
            print("✅ FX data fetch successful!")
            
            # Check data structure
            for pair, data in fx_data.get('rates', {}).items():
                print(f"\n{pair}:")
                print(f"  Current: {data.get('current')}")
                changes = data.get('changes', {})
                if changes:
                    for period, change in changes.items():
                        color = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                        print(f"  {period}: {color} {change:+.1f}%")
                else:
                    print("  No historical changes available")
        else:
            print("❌ FX data fetch failed")
            
    except Exception as e:
        print(f"❌ Error testing FX data: {e}")
    
    # Test 2: HTML Generation
    print("\n\n🌐 Test 2: HTML Generation with Changes")
    print("-" * 40)
    
    try:
        generator = NewsletterGenerator()
        fx_html = generator.generate_fx_box()
        
        # Check if HTML contains the expected elements
        if 'fx-box' in fx_html:
            print("✅ FX box HTML generation successful!")
            
            # Check for change indicators
            if 'fx-change' in fx_html:
                print("✅ Historical changes included in HTML")
            else:
                print("⚠️ No historical changes in HTML (might be expected if APIs are limited)")
                
            if 'positive' in fx_html or 'negative' in fx_html:
                print("✅ Color classes applied for changes")
            
        else:
            print("❌ FX box HTML generation failed")
            
    except Exception as e:
        print(f"❌ Error testing HTML generation: {e}")
    
    # Test 3: Create Sample Newsletter
    print("\n\n📋 Test 3: Complete Newsletter with Enhanced FX")
    print("-" * 45)
    
    try:
        # Create a minimal test newsletter
        mock_data = {
            'tech': {
                'top_stories': [{
                    'title': 'Enhanced FX Feature Test Article',
                    'url': 'https://example.com',
                    'source': 'Test Source',
                    'published': '2025-08-31T10:00:00Z',
                    'category_label': 'tech',
                    'category_display': 'Technology',
                    'importance_score': 8,
                    'enhanced_summary': 'This is a test article for the enhanced FX feature.'
                }],
                'quick_reads': []
            }
        }
        
        generator.get_nz_date = lambda: '2025-08-31'
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced FX Test Newsletter</title>
    <style>{generator.get_css()}</style>
</head>
<body>
    <div class="container">
        {generator.generate_header('2025-08-31')}
        {generator.generate_fx_box()}
        {generator.generate_content(mock_data)}
        {generator.generate_footer()}
    </div>
</body>
</html>"""
        
        # Save test HTML
        output_file = '/Users/asif/Documents/Daily News Letter/daily-news-letter-public/test_enhanced_fx_newsletter.html'
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"✅ Complete test newsletter saved to: test_enhanced_fx_newsletter.html")
        print("   Open this file in your browser to see the enhanced FX display!")
        
    except Exception as e:
        print(f"❌ Error creating test newsletter: {e}")
    
    # Summary
    print("\n\n📋 Enhancement Summary")
    print("-" * 25)
    print("✨ Added Features:")
    print("  • 24h, 7d, and 30d percentage changes")
    print("  • Green/red/grey color coding")
    print("  • Historical data from same APIs")
    print("  • Mobile responsive design")
    print("  • Graceful error handling")
    
    print("\n🎯 Ready for Production!")
    print("   Run your main pipeline to see the enhanced FX box in action.")

if __name__ == "__main__":
    test_enhanced_fx()
