from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import time
import os

# from database import NewsletterDB

if True:
    load_dotenv("../env/config.env")

logger = logging.getLogger(__name__)

class ArticleCurator:
    def __init__(self, db_path: str = "data/newsletter.db", use_llm: bool = True):
        # self.db = NewsletterDB(db_path)
        self.use_llm = use_llm
        
        if self.use_llm:
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            print("🚫 LLM disabled - using simple fallback selection")
        

    def curate_newsletter(self, results, hours: int = 24) -> Dict:
        """Complete curation pipeline using passed article data"""
        
        print(f"Received results with categories: {list(results.keys())}")
        
        # Filter recent articles from passed results (no database query)
        articles = self.get_recent_articles_from_results(results, hours)
        print(f"Found {len(articles)} recent articles after time filtering")
        
        # Continue with existing pipeline
        clean_articles = self.basic_filter(articles)
        print(f"Found {len(clean_articles)} articles after basic filtering")
        
        curated = self.llm_curate(clean_articles)
        print(f"LLM curated articles for categories: {list(curated.keys())}")
        
        self.add_content_to_top_stories(curated)
        print("Enhanced top stories with scraped content")
        
        self.save_to_json(curated)  # Save to JSON instead of database
        print("Saved curated data to JSON")
        
        return curated
    

    def get_recent_articles_from_results(self, results: Dict[str, List[Dict]], hours: int) -> List[Dict]:
        """Filter recent articles from collector results (replaces database query)"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_articles = []
        for category, cat_articles in results.items():
            for article in cat_articles:
                # Ensure article has category field
                article['category'] = category
                
                # Check if article is recent enough
                article_date = article.get('published')
                if isinstance(article_date, str):
                    # Parse string datetime if needed
                    try:
                        article_date = datetime.fromisoformat(article_date.replace('Z', '+00:00'))
                    except:
                        article_date = datetime.now(timezone.utc)
                
                if article_date >= cutoff:
                    recent_articles.append(article)
        
        logger.info(f"Filtered to {len(recent_articles)} recent articles from last {hours} hours")
        return recent_articles

    def save_to_json(self, curated_data: Dict, newsletter_date: str = None):
        """Save curated newsletter data to JSON file (replaces database storage)"""
        if not newsletter_date:
            newsletter_date = datetime.now().strftime('%Y-%m-%d')
        
        # Ensure data directory exists
        os.makedirs('data/loading', exist_ok=True)
        
        # Save to JSON file
        json_path = 'data/loading/newsletter_curated.json'
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(curated_data, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Saved curated newsletter data to {json_path} for {newsletter_date}")
            
            # Also save a dated backup copy
            backup_path = f'data/loading/newsletter_curated_{newsletter_date}.json'
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(curated_data, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Created backup at {backup_path}")
            
        except Exception as e:
            logger.error(f"Error saving curated data to JSON: {e}")
            raise
    
    def basic_filter(self, articles: List[Dict]) -> List[Dict]:
        """Remove junk articles"""
        filtered = []
        for article in articles:
            if (article.get('description') and 
                len(article['description'].strip()) > 30 and
                'sponsored' not in article['title'].lower()):
                filtered.append(article)
        logger.info(f"Filtered {len(articles)} → {len(filtered)} articles")
        return filtered
    
    def llm_curate(self, articles: List[Dict]) -> Dict:
        """LLM curation for all categories"""
        # Group by category
        by_category = {}
        for article in articles:
            cat = article['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(article)
        
        # Curate each category
        result = {}
        for category, cat_articles in by_category.items():
            result[category] = self.curate_one_category(cat_articles, category)
        
        return result
    
    def curate_one_category(self, articles: List[Dict], category: str) -> Dict:
        """Curate one category with LLM or simple fallback"""
        if not articles:
            return {"top_stories": [], "quick_reads": []}
        
        if not self.use_llm:
            # Simple fallback: take most recent articles
            print(f"📰 Simple curation for {category}: taking {min(3, len(articles))} top stories, {min(5, len(articles)-3)} quick reads")
            return {
                "top_stories": articles[:3],  # Most recent 3
                "quick_reads": articles[3:8]   # Next 5
            }
            
        # Prepare articles for LLM (just id + title)
        article_list = [{"id": a['id'], "title": a['title']} for a in articles]
        
        prompt = f"""
        You are curating {category} news for informed professionals who need to understand developments that truly matter.

        SELECTION CRITERIA:
        - Prioritize stories with genuine impact on industries, markets, or society
        - Focus on developments that signal meaningful change or disruption
        - Avoid routine announcements, minor updates, or superficial coverage
        - Look for stories that reveal underlying trends or shifts in power/technology/economics

        Select exactly:
        - TOP 3 STORIES: Major developments with broad implications that professionals should understand
        - QUICK READS 5 STORIES: Noteworthy but secondary developments worth monitoring

        For TOP stories, explain WHY this matters beyond the immediate headline - what are the broader implications?
        For QUICK READS, briefly note why this development is worth tracking.

        Return JSON:
        {{"top_stories": [{{"id": 123, "summary": "Brief explanation of why this represents significant change or impact", "score": 8}}], 
        "quick_reads": [{{"id": 456, "reason": "Why this development is worth monitoring"}}]}}

        Articles: {json.dumps(article_list)}
        """
        
        try:
            response = self.model.generate_content(prompt)
            llm_result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
            
            # Map back to full articles
            article_lookup = {a['id']: a for a in articles}
            
            result = {"top_stories": [], "quick_reads": []}
            
            for story in llm_result.get('top_stories', []):
                if story['id'] in article_lookup:
                    full_article = article_lookup[story['id']].copy()
                    full_article['llm_summary'] = story.get('summary', '')
                    full_article['importance_score'] = story.get('score', 5)
                    result['top_stories'].append(full_article)
            
            for read in llm_result.get('quick_reads', []):
                if read['id'] in article_lookup:
                    full_article = article_lookup[read['id']].copy()
                    full_article['llm_reason'] = read.get('reason', '')
                    result['quick_reads'].append(full_article)
            
            return result
            
        except Exception as e:
            logger.error(f"LLM error for {category}: {e}")
            # Fallback: just take first few articles
            return {
                "top_stories": articles[:3],
                "quick_reads": articles[3:8]
            }
    
    def add_content_to_top_stories(self, curated: Dict):
        """Scrape content for top stories only"""
        for category, data in curated.items():
            for story in data['top_stories']:
                if self.use_llm:
                    # Only scrape if we're going to use LLM for enhancement
                    content = self.scrape_content(story['url'])
                    if content:
                        # Store scraped content and generate enhanced summary
                        story['scraped_content'] = content
                        enhanced = self.enhance_summary(story['title'], content, category)
                        if enhanced:
                            story['enhanced_summary'] = enhanced
                    time.sleep(1)  # Be nice to servers
                else:
                    print(f"⚡ Skipping content scraping for: {story['title'][:50]}...")
    
    def scrape_content(self, url: str) -> Optional[str]:
        """Simple content scraper with debugging"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            print(f"Scraping: {url}")
            
            # Try common content selectors
            for selector in ['article', '.article-content', '.post-content', '.story-body']:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(separator=' ', strip=True)
                    print(f"Found content with selector '{selector}': {len(text)} chars")
                    return self.optimize_content_for_llm(text, url) if text else None
            
            # Fallback: all paragraphs
            paragraphs = soup.find_all('p')
            text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            print(f"Fallback paragraphs: {len(text)} chars")
            
            if not text:
                print("No content found - checking page structure...")
                print(f"Page title: {soup.title.string if soup.title else 'No title'}")
                # Print first few divs to see structure
                divs = soup.find_all('div')[:5]
                for i, div in enumerate(divs):
                    if div.get('class'):
                        print(f"Div {i}: class={div.get('class')}")
            
            return self.optimize_content_for_llm(text, url) if text else None
            
        except Exception as e:
            print(f"Scraping error for {url}: {e}")
            return None

    def optimize_content_for_llm(self, raw_content: str, url: str) -> str:
        """Clean and optimize scraped content for LLM processing"""
        original_length = len(raw_content)
        
        # Step 1: Remove common junk patterns
        junk_patterns = [
            r'subscribe\s+to\s+our\s+newsletter',
            r'follow\s+us\s+on\s+social\s+media', 
            r'advertisement\s*:?',
            r'related\s+articles?:?',
            r'more\s+from\s+\w+:?',
            r'read\s+more\s+about',
            r'sign\s+up\s+for',
            r'cookies?\s+policy',
            r'terms\s+of\s+service',
            r'privacy\s+policy',
            r'share\s+this\s+article',
            r'\bshare\b.*\bfacebook\b.*\btwitter\b',
            r'loading\.\.\.?',
        ]
        
        cleaned = raw_content
        removed_patterns = []
        
        for pattern in junk_patterns:
            matches = re.findall(pattern, cleaned, flags=re.IGNORECASE)
            if matches:
                removed_patterns.extend(matches)
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Step 2: Remove excessive whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Step 3: Smart sentence selection (first 8 complete sentences)
        sentences = [s.strip() + '.' for s in cleaned.split('.') if len(s.strip()) > 20]
        optimized = ' '.join(sentences[:8])
        
        # Debug output
        final_length = len(optimized)
        reduction = ((original_length - final_length) / original_length * 100) if original_length > 0 else 0
        
        print(f"\n📝 Content optimization for {url}:")
        print(f"   Original: {original_length} chars → Optimized: {final_length} chars")
        print(f"   Reduction: {reduction:.1f}%")
        
        if removed_patterns:
            unique_removed = list(set([p.lower() for p in removed_patterns]))
            print(f"   Removed junk: {', '.join(unique_removed[:3])}{'...' if len(unique_removed) > 3 else ''}")
        
        if len(sentences) > 8:
            print(f"   Sentences: kept {len(sentences[:8])}/{len(sentences)} best sentences")
        
        return optimized
        
    def enhance_summary(self, title: str, content: str, category: str) -> Optional[str]:
        """Create better summary with full content or return None if LLM disabled"""
        if not self.use_llm:
            return None  # Skip enhanced summaries when LLM disabled
        
        print(f"\n🤖 LLM Enhancement: {title[:50]}...")
        print(f"   Input length: {len(content)} chars")
            
        prompt = f"""
        Analyze this {category} article and create a 3 sentence summary for tech professionals with this structure:
        
        1. FIRST SENTENCE: Start with a clear, simple statement of why this matters - the core significance in plain language
        2. Explain what actually happened (the key facts)
        3. Analyze the broader implications or consequences
        4. Connect it to larger industry trends or shifts
        
        The opening sentence should immediately convey importance without hyperbole - think "This changes how companies handle X" or "This signals a shift in Y market" rather than generic statements.
        
        Title: {title}
        Content: {content}
        
        Summary:
        """
        
        try:
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            print(f"   LLM output length: {len(result)} chars")
            return result
        except Exception as e:
            print(f"   LLM error: {e}")
            return None

    def save_to_json(self, curated_data: Dict, newsletter_date: str = None):
        """Save curated newsletter data to JSON file (replaces database storage)"""
        if not newsletter_date:
            newsletter_date = datetime.now().strftime('%Y-%m-%d')
        
        # Ensure data directory exists
        os.makedirs('data/loading', exist_ok=True)
        
        # Add metadata and clean up structure for JSON storage
        output = {}
        for category, data in curated_data.items():
            output[category] = {
                'top_stories': data.get('top_stories', []),
                'quick_reads': data.get('quick_reads', [])
            }
        
        # Save to JSON file
        json_path = 'data/loading/newsletter_curated.json'
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Saved curated newsletter data to {json_path} for {newsletter_date}")
            
            # Also save a dated backup copy
            backup_path = f'data/loading/newsletter_curated_{newsletter_date}.json'
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, default=str, ensure_ascii=False)
            
            logger.info(f"Created backup at {backup_path}")
            
        except Exception as e:
            logger.error(f"Error saving curated data to JSON: {e}")
            raise