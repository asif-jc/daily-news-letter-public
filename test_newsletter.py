#!/usr/bin/env python3

# Test newsletter generation with FX box
import sys
sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

from web_newsletter import NewsletterGenerator

def test_fx_box():
    """Test just the FX box generation"""
    generator = NewsletterGenerator()
    
    print("Testing FX Box Generation...")
    print("=" * 50)
    
    fx_html = generator.generate_fx_box()
    print("FX Box HTML:")
    print(fx_html)
    
    # Test with a simple mock newsletter
    print("\n" + "=" * 50)
    print("Testing Full Newsletter Generation...")
    
    # Create a minimal test data structure
    mock_data = {
        'tech': {
            'top_stories': [{
                'title': 'Test Article',
                'url': 'https://example.com',
                'source': 'Test Source',
                'published': '2025-08-31T10:00:00Z',
                'category_label': 'tech',
                'category_display': 'Technology',
                'importance_score': 8,
                'enhanced_summary': 'This is a test article summary.'
            }],
            'quick_reads': []
        }
    }
    
    content_html = generator.generate_content(mock_data)
    print("Content generated successfully!")
    
    # Generate full HTML
    generator.get_nz_date = lambda: '2025-08-31'
    
    html = f"""<!DOCTYPE html>
<html>
<head><style>{generator.get_css()}</style></head>
<body>
<div class="container">
{generator.generate_header('2025-08-31')}
{fx_html}
{content_html}
{generator.generate_footer()}
</div>
</body>
</html>"""
    
    # Save test HTML
    with open('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/test_newsletter_with_fx.html', 'w') as f:
        f.write(html)
    
    print("Test newsletter saved to: test_newsletter_with_fx.html")

if __name__ == "__main__":
    test_fx_box()
