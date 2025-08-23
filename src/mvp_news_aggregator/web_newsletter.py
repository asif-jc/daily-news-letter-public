from datetime import datetime
from typing import Dict, List
import json
import os

class NewsletterGenerator:
    def __init__(self):
        pass
    
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
        date = datetime.now().strftime('%Y-%m-%d')
        
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
            background-image: url('assets/windows_hills.png');
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
    
    def generate_header(self, date: str) -> str:
        """Generate newsletter header"""
        formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')
        return f"""
        <div class="header">
            <h1>Daily News Feed</h1>
            <div class="date">{formatted_date}</div>
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
        
        # Format published date
        try:
            if isinstance(article.get('published'), str):
                pub_date = datetime.fromisoformat(article['published'].replace('Z', '+00:00'))
                formatted_date = pub_date.strftime('%H:%M')
            else:
                formatted_date = "Recent"
        except:
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
            date = datetime.now().strftime('%Y-%m-%d')
            output_path = f"archive/newsletter_{date}.html"
        
        html_content = self.generate_html(json_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        with open("newsletter.html", 'w', encoding='utf-8') as f:
            f.write(html_content)

        with open(".github/workflows/docs/index.html", 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path

# Usage function
def generate_newsletter():
    """Generate newsletter from JSON file"""
    generator = NewsletterGenerator()
    output_file = generator.save_newsletter()
    print(f"Newsletter generated: {output_file}")
    return output_file

# if __name__ == "__main__":
#     generate_newsletter()