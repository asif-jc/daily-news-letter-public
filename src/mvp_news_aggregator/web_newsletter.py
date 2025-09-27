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
    
    def load_quiz_data(self, quiz_path: str = 'data/loading/quiz_today.json') -> Dict:
        """
        Load quiz data from JSON file.
        Returns empty dict if file not found or invalid.
        """
        try:
            if not os.path.exists(quiz_path):
                print(f"Quiz data not found at {quiz_path}")
                return {}
            
            with open(quiz_path, 'r', encoding='utf-8') as f:
                quiz_data = json.load(f)
            
            print(f"Loaded quiz data: {len(quiz_data.get('questions', []))} questions")
            return quiz_data
        except Exception as e:
            print(f"Error loading quiz data: {e}")
            return {}
    
    def generate_quiz_section(self, quiz_data: Dict) -> str:
        """
        Generate daily quiz section with inline answers for bottom of newsletter.
        Returns empty string if no quiz data available.
        """
        if not quiz_data or not quiz_data.get('questions'):
            print("No quiz data available for newsletter")
            return ''
        
        questions = quiz_data['questions']
        metadata = quiz_data.get('metadata', {})
        
        # Create quiz header with metadata
        html = '<div class="quiz-box">'
        html += '<div class="quiz-header">'
        html += '<h3 class="quiz-title">Daily Knowledge Quiz</h3>'
        html += '<div class="quiz-meta">'
        
        if metadata.get('generated_with_llm'):
            html += 'AI Generated • '
        html += f"{len(questions)} Questions • {metadata.get('difficulty', 'medium').title()} Level"
        html += '</div>'
        html += '</div>'
        
        # Add intro note
        html += '<p style="margin-bottom: 1.5rem; color: #6c757d; font-size: 0.9rem;">'
        html += 'Test your knowledge across geography, STEM, history, and general topics. '
        html += 'Click "Show Answer" to reveal the solution with explanation.'
        html += '</p>'
        
        # Generate ALL questions with inline answers
        for i, question in enumerate(questions, 1):
            html += '<div class="quiz-question">'
            
            # Question header with number and category
            html += '<div class="quiz-question-header">'
            html += f'<span class="quiz-question-number">{i}</span>'
            html += f'<span class="quiz-category">{question.get("category", "General")}</span>'
            html += '</div>'
            
            # Question text
            html += f'<div class="quiz-question-text">{question.get("question", "Question not available")}</div>'
            
            # Options
            html += '<div class="quiz-options">'
            for option in question.get('options', []):
                html += f'<div class="quiz-option">{option}</div>'
            html += '</div>'
            
            # Reveal answer button
            html += f'<button class="quiz-reveal-button" id="reveal-{i}" onclick="revealAnswer({i})">Show Answer</button>'
            
            # Hidden answer section
            html += f'<div class="quiz-answer-section" id="answer-{i}">'
            html += f'<div class="quiz-correct-answer">Answer: {question.get("correct_answer", "Not available")}</div>'
            if question.get('explanation'):
                html += f'<div class="quiz-explanation">{question["explanation"]}</div>'
            html += '</div>'
            
            html += '</div>'  # quiz-question
        
        html += '</div>'  # quiz-box
        
        return html
    
    def generate_content_overview(self, data: Dict, quiz_data: Dict) -> str:
        """
        Generate enhanced overview showcasing most important content.
        """
        html = '<div class="content-overview">'
        html += '<div class="overview-title">Today\'s Essential Updates</div>'
        
        # Breaking News - Coming Soon (moved to top)
        html += '<div class="overview-section">'
        html += '<h4 class="overview-section-title">Breaking News</h4>'
        html += '<div class="coming-soon">Real-time alerts coming soon</div>'
        html += '</div>'
        
        # Priority Stories - Show top 5 with highest scores
        top_stories = self._get_top_priority_stories(data, limit=5)
        if top_stories:
            total_stories = sum(len(cat.get('top_stories', [])) + len(cat.get('quick_reads', [])) for cat in data.values())
            remaining = total_stories - 5
            
            html += '<div class="overview-section">'
            html += '<h4 class="overview-section-title">Priority Stories</h4>'
            for story in top_stories:
                time_ago = self._format_time_ago(story.get('published'))
                html += f'<div class="overview-story">'
                html += f'<div class="story-headline">{story.get("title", "Untitled")}</div>'
                html += f'<div class="story-time">{time_ago}</div>'
                html += '</div>'
            
            if remaining > 0:
                html += f'<div class="overview-more">+ {remaining} more updates available</div>'
            html += '</div>'
        
        # FX & Markets
        html += '<div class="overview-section">'
        html += '<h4 class="overview-section-title">Markets Snapshot</h4>'
        html += '<div class="market-snapshot">'
        
        # Get market data
        fx_data = self._get_fx_snapshot()
        market_data = self._get_market_snapshot()
        
        if fx_data.get('NZD/USD'):
            html += f'<div class="snapshot-item">NZD/USD: <span class="value">{fx_data["NZD/USD"]}</span></div>'
        
        if market_data.get('VOO'):
            html += f'<div class="snapshot-item">VOO: <span class="value">${market_data["VOO"]}</span></div>'
            
        if market_data.get('GLD'):
            gold_price = int(float(market_data['GLD']) * 10)
            html += f'<div class="snapshot-item">Gold: <span class="value">{gold_price} USD per Troy ounce</span></div>'
        
        html += '</div>'
        html += '</div>'
        
        # Quiz
        if quiz_data and quiz_data.get('questions'):
            questions = quiz_data['questions']
            metadata = quiz_data.get('metadata', {})
            topics = metadata.get('topics', [])
            
            # Clean up topic names
            topic_display = []
            for topic in topics:
                if topic.lower() == 'stem':
                    topic_display.append('STEM')
                elif topic.lower() == 'general_knowledge':
                    topic_display.append('General Knowledge')
                else:
                    topic_display.append(topic.title())
            
            html += '<div class="overview-section">'
            html += '<h4 class="overview-section-title">Knowledge Quiz</h4>'
            html += f'<div class="quiz-preview">'
            html += f'{len(questions)} questions • {metadata.get("difficulty", "medium").title()} level<br>'
            html += f"Topics: {', '.join(topic_display[:3])}"
            html += '</div>'
            html += '</div>'
        
        html += '</div>'
        return html
    
    def _get_top_priority_stories(self, data: Dict, limit: int = 5) -> List[Dict]:
        """Get top priority stories across all categories sorted by importance score."""
        all_stories = []
        
        for category, articles in data.items():
            for story in articles.get('top_stories', []):
                story['category_name'] = category
                all_stories.append(story)
        
        # Sort by importance score (highest first)
        all_stories.sort(key=lambda x: x.get('importance_score', 0), reverse=True)
        
        return all_stories[:limit]
    
    def _format_time_ago(self, published_str: str) -> str:
        """Format publication time in a smart, readable way."""
        if not published_str:
            return 'Recent'
        
        try:
            from datetime import datetime, timezone
            import pytz
            
            # Parse the published time
            if isinstance(published_str, str):
                pub_time = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            else:
                return 'Recent'
            
            # Get current NZ time
            nz_tz = pytz.timezone('Pacific/Auckland')
            now = datetime.now(nz_tz)
            pub_time_nz = pub_time.astimezone(nz_tz)
            
            # Calculate time difference
            diff = now - pub_time_nz
            hours = diff.total_seconds() / 3600
            
            if hours < 1:
                minutes = int(diff.total_seconds() / 60)
                return f'{minutes}m ago'
            elif hours < 6:
                return f'{int(hours)}h ago'
            elif pub_time_nz.date() == now.date():
                if pub_time_nz.hour < 12:
                    return 'This morning'
                else:
                    return 'This afternoon'
            elif (now.date() - pub_time_nz.date()).days == 1:
                return 'Yesterday'
            else:
                days = (now.date() - pub_time_nz.date()).days
                return f'{days} days ago'
                
        except Exception:
            return 'Recent'
    
    def _get_fx_snapshot(self) -> Dict:
        """Get current FX rates for overview."""
        try:
            from foreign_exchange_data import get_fx_changes_from_daily_data
            fx_data = get_fx_changes_from_daily_data()
            
            if fx_data.get('status') == 'success' and fx_data.get('rates'):
                rates = fx_data['rates']
                if 'NZD/USD' in rates:
                    return {'NZD/USD': rates['NZD/USD']['current']}
            return {}
        except Exception:
            return {}
    
    def _get_market_snapshot(self) -> Dict:
        """Get current market data for overview."""
        try:
            from market_data import get_market_changes_from_daily_data
            market_data = get_market_changes_from_daily_data()
            
            if market_data.get('status') == 'success' and market_data.get('prices'):
                prices = market_data['prices']
                result = {}
                
                # Get VOO price
                if 'VOO' in prices:
                    result['VOO'] = f"{int(prices['VOO']['current']):,}"
                
                # Get GLD price for gold calculation
                if 'GLD' in prices:
                    result['GLD'] = prices['GLD']['current']
                
                return result
            return {}
        except Exception:
            return {}
    
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
        quiz_data = self.load_quiz_data()
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
        {self.generate_content_overview(data, quiz_data)}
        {self.generate_fx_box()}
        {self.generate_market_box()}
        {self.generate_content(data)}
        {self.generate_quiz_section(quiz_data)}
        {self.generate_footer()}
    </div>
    
    <script>
        function toggleCategory(categoryId) {{
            const category = document.querySelector(`[data-category="${{categoryId}}"]`);
            const icon = category.querySelector('.toggle-icon');
            
            if (category.classList.contains('collapsed')) {{
                category.classList.remove('collapsed');
                category.classList.add('expanded');
                icon.textContent = '\u2212';
            }} else {{
                category.classList.remove('expanded');
                category.classList.add('collapsed');
                icon.textContent = '+';
            }}
        }}
        
        function revealAnswer(questionId) {{
            const answerDiv = document.getElementById(`answer-${{questionId}}`);
            const button = document.getElementById(`reveal-${{questionId}}`);
            
            answerDiv.style.display = 'block';
            button.style.display = 'none';
        }}
    </script>
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
            background-image: url('assets/dunder_park.jpg');
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
        
        .why-matters {
            margin-top: 0.75rem;
            padding: 0.75rem;
            background-color: #f0f8ff;
            border-left: 3px solid #007bff;
            font-style: italic;
            font-size: 0.95em;
            color: #495057;
            border-radius: 4px;
        }
        
        .why-matters strong {
            color: #007bff;
            font-weight: 600;
            font-style: normal;
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
        }
        
        .fx-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2c3e50;
            margin: 0;
        }
        
        .fx-timestamp {
            font-size: 0.85rem;
            color: #6c757d;
        }
        
        .fx-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }
        
        .fx-dxy-row {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }
        
        .fx-currencies-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
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
        
        @media (max-width: 600px) {
            .fx-box {
                margin: 1rem;
                padding: 1rem;
            }
            
            .fx-currencies-grid {
                grid-template-columns: repeat(3, 1fr);
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
        
        /* Improved Market Data Styles */
        .market-box {
            margin: 1rem 2rem;
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .market-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .market-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2c3e50;
            margin: 0;
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
        
        .market-category-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            padding: 0.75rem 0;
            border-bottom: 2px solid #e9ecef;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
        }
        
        .market-category-header:hover {
            background-color: rgba(102, 126, 234, 0.05);
            margin: 0 -0.5rem;
            padding: 0.75rem 0.5rem;
            border-radius: 4px;
        }
        
        .market-category-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: #495057;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .toggle-icon {
            font-size: 1.1rem;
            color: #667eea;
            font-weight: bold;
            transition: transform 0.3s ease;
        }
        
        .market-category.collapsed .toggle-icon {
            transform: rotate(-90deg);
        }
        
        .category-count {
            font-size: 0.8rem;
            color: #6c757d;
            font-weight: normal;
            margin-left: 0.25rem;
        }
        
        .market-instruments {
            transition: all 0.3s ease;
            overflow: hidden;
        }
        
        .market-category.collapsed .market-instruments {
            height: 0;
            opacity: 0;
            margin: 0;
        }
        
        .market-instruments-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 0.75rem;
            margin-top: 0.5rem;
        }
        
        .market-instrument-card {
            background: white;
            padding: 1rem;
            border-radius: 6px;
            border: 1px solid #e9ecef;
            transition: all 0.2s ease;
        }
        
        .market-instrument-card:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transform: translateY(-1px);
        }
        
        .market-symbol {
            font-size: 1rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 0.5rem;
        }
        
        .market-price {
            font-size: 1.1rem;
            color: #667eea;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
        
        .market-changes {
            display: flex;
            justify-content: space-between;
            gap: 0.5rem;
        }
        
        .market-change {
            font-weight: 500;
            font-size: 0.8rem;
            text-align: center;
            padding: 0.3rem 0.5rem;
            border-radius: 4px;
            flex: 1;
            min-width: 0;
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
        
        /* Content Overview Styles */
        .content-overview {
            margin: 1rem 2rem;
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #6c757d;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .overview-title {
            font-size: 1.2rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 1.5rem;
            text-align: center;
        }
        
        .overview-section {
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: white;
            border-radius: 6px;
            border: 1px solid #e9ecef;
        }
        
        .overview-section:last-child {
            margin-bottom: 0;
        }
        
        .overview-section-title {
            font-size: 1rem;
            font-weight: 600;
            color: #495057;
            margin-bottom: 0.75rem;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 0.5rem;
        }
        
        .overview-story {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #f8f9fa;
        }
        
        .overview-story:last-child {
            margin-bottom: 0;
            border-bottom: none;
        }
        
        .story-headline {
            font-size: 0.9rem;
            color: #2c3e50;
            flex: 1;
            margin-right: 1rem;
            line-height: 1.3;
        }
        
        .story-time {
            font-size: 0.8rem;
            color: #6c757d;
            white-space: nowrap;
            font-weight: 500;
        }
        
        .overview-more {
            text-align: center;
            font-size: 0.85rem;
            color: #6c757d;
            font-style: italic;
            margin-top: 0.5rem;
        }
        
        .coming-soon {
            font-size: 0.9rem;
            color: #6c757d;
            font-style: italic;
            text-align: center;
            padding: 0.5rem;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .market-snapshot {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.75rem;
        }
        
        .snapshot-item {
            font-size: 0.9rem;
            color: #495057;
        }
        
        .snapshot-item .value {
            font-weight: 600;
            color: #2c3e50;
        }
        
        .quiz-preview {
            font-size: 0.9rem;
            color: #495057;
            line-height: 1.4;
        }
        
        /* Updated Quiz Section Styles */
        .quiz-box {
            margin: 1rem 2rem;
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #fd7e14;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .quiz-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .quiz-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #2c3e50;
            margin: 0;
        }
        
        .quiz-meta {
            font-size: 0.85rem;
            color: #6c757d;
        }
        
        .quiz-question {
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: white;
            border-radius: 6px;
            border: 1px solid #e9ecef;
        }
        
        .quiz-question-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
        }
        
        .quiz-question-number {
            font-size: 0.8rem;
            font-weight: 600;
            color: #fd7e14;
            background: rgba(253, 126, 20, 0.1);
            padding: 0.25rem 0.5rem;
            border-radius: 12px;
            min-width: 2rem;
            text-align: center;
        }
        
        .quiz-category {
            font-size: 0.75rem;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .quiz-question-text {
            font-size: 1rem;
            font-weight: 500;
            color: #2c3e50;
            margin-bottom: 0.75rem;
            line-height: 1.4;
        }
        
        .quiz-options {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.5rem;
        }
        
        .quiz-option {
            padding: 0.5rem 0.75rem;
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .quiz-option:hover {
            background: #e9ecef;
            border-color: #fd7e14;
        }
        
        .quiz-reveal-button {
            margin-top: 0.75rem;
            padding: 0.5rem 1rem;
            background: #fd7e14;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: background 0.2s ease;
        }
        
        .quiz-reveal-button:hover {
            background: #e66b02;
        }
        
        .quiz-answer-section {
            margin-top: 0.75rem;
            padding: 0.75rem;
            background: #fff5f0;
            border-radius: 4px;
            border: 1px solid #fd7e14;
            display: none;
        }
        
        .quiz-correct-answer {
            font-size: 1rem;
            font-weight: 600;
            color: #28a745;
            margin-bottom: 0.5rem;
        }
        
        .quiz-explanation {
            font-size: 0.9rem;
            color: #6c757d;
            line-height: 1.4;
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
            
            .fx-box, .market-box {
                margin: 1rem;
                padding: 1rem;
            }
            
            .market-instruments-grid {
                grid-template-columns: 1fr;
                gap: 0.5rem;
            }
            
            .market-changes {
                flex-direction: column;
                gap: 0.25rem;
            }
            
            .market-change {
                text-align: left;
            }
            
            .quiz-box {
                margin: 1rem;
                padding: 1rem;
            }
            
            .quiz-options {
                grid-template-columns: 1fr;
                gap: 0.5rem;
            }
            
            .content-overview {
                margin: 1rem;
                padding: 1rem;
            }
            
            .overview-story {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.25rem;
            }
            
            .story-headline {
                margin-right: 0;
            }
            
            .market-snapshot {
                grid-template-columns: 1fr;
                gap: 0.5rem;
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
            html += '<h3 class="fx-title">Foreign Exchange Rates</h3>'
            html += f'<div class="fx-timestamp">{timestamp}</div>'
            html += '</div>'
            
            html += '<div class="fx-grid">'            
            
            # DXY row with real data
            html += '<div class="fx-dxy-row">'            
            
            # Get DXY data
            try:
                from foreign_exchange_data import get_dxy_from_market_data
                dxy_data = get_dxy_from_market_data()
                dxy_current = dxy_data['current']
                dxy_changes = dxy_data.get('changes', {})
            except Exception:
                dxy_current = 0.00
                dxy_changes = {}
            
            html += '<div class="fx-rate">'            
            html += '<div class="fx-pair">DXY (US Dollar Index)</div>'            
            html += f'<div class="fx-value">{dxy_current}</div>'            
            html += '<div class="fx-changes">'            
            
            # Add real percentage changes or defaults
            for period in ['24h', '7d', '30d']:
                if period in dxy_changes:
                    change_pct = dxy_changes[period]
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
                else:
                    html += f'<span class="fx-change neutral">{period} +0.0%</span>'
            
            html += '</div>'            
            html += '</div>'            
            html += '</div>'            
            
            # Currency pairs in rows of 3
            html += '<div class="fx-currencies-grid">'
            
            # Define the order of currency pairs
            pair_order = ['NZD/USD', 'NZD/AUD', 'NZD/INR', 'NZD/CNY', 'NZD/THB'] # , 'USD/BTC']
            
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
            
            html += '</div>'  # fx-currencies-grid
            html += '</div>'  # fx-grid
            html += '</div>'
            
            return html
            
        except Exception as e:
            print(f"Error generating FX box: {e}")
            return '<div class="fx-box"><p>Foreign exchange data currently unavailable</p></div>'
    
    def generate_market_box(self) -> str:
        """Generate market data box with collapsible categories and card layout"""
        try:
            market_data = get_market_changes_from_daily_data()
            
            if market_data.get('status') != 'success' or not market_data.get('prices'):
                return '<div class="market-box"><p>Market data currently unavailable</p></div>'
            
            prices_data = market_data['prices']
            timestamp = market_data.get('timestamp', 'Unknown')
            
            html = '<div class="market-box">'
            html += '<div class="market-header">'
            html += '<h3 class="market-title">Market Data</h3>'
            html += f'<div class="market-timestamp">{timestamp}</div>'
            html += '</div>'
            
            # Group instruments by category
            categories = {
                'US Indices': [],
                'Currency Indices': [],
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
            
            # Category ID mapping for JavaScript
            category_ids = {
                'US Indices': 'us-indices',
                'Currency Indices': 'currency-indices',
                'International Indices': 'international',
                'Commodities': 'commodities',
                'ETFs': 'etfs'
            }
            
            # Display each category with collapsible design
            for category_name, instruments in categories.items():
                if instruments:  # Only show categories that have data
                    category_id = category_ids.get(category_name, category_name.lower().replace(' ', '-'))
                    count = len(instruments)
                    
                    html += f'<div class="market-category collapsed" data-category="{category_id}">'
                    html += f'<div class="market-category-header" onclick="toggleCategory(\'{category_id}\')">' 
                    html += f'<div class="market-category-title">'
                    html += f'<span class="toggle-icon">+</span>'
                    html += f'{category_name}'
                    html += f'<span class="category-count">({count})</span>'
                    html += f'</div>'
                    html += f'</div>'
                    
                    html += f'<div class="market-instruments">'
                    html += f'<div class="market-instruments-grid">'
                    
                    for ticker, data in instruments:
                        current_price = data['current']
                        display_symbol = data['display_symbol']
                        currency = data['currency']
                        changes = data.get('changes', {})
                        
                        # Format price: remove decimals, add commas
                        formatted_price = f"{int(current_price):,}"
                        
                        html += f'<div class="market-instrument-card">'
                        html += f'<div class="market-symbol">{display_symbol}</div>'
                        html += f'<div class="market-price">{formatted_price} {currency}</div>'
                        html += f'<div class="market-changes">'
                        
                        # Add individual change periods (24h, 7d, 30d)
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
                                
                                html += f'<div class="market-change {color_class}">{period} {sign}{change_pct:.1f}%</div>'
                            else:
                                html += f'<div class="market-change neutral">{period} -</div>'
                        
                        html += f'</div>'  # market-changes
                        html += f'</div>'  # market-instrument-card
                    
                    html += f'</div>'  # market-instruments-grid
                    html += f'</div>'  # market-instruments
                    html += f'</div>'  # market-category
            
            html += '</div>'  # market-box
            
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
                if article.get('why_matters'):
                    html += f'<div class="why-matters"><strong>Why this matters:</strong> {article["why_matters"]}</div>'
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