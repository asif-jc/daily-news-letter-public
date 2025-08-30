import os
import sys
import feedparser
import requests
import re
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from urllib.parse import urljoin
import time

sys.path.append(os.getcwd())

from src.mvp_news_aggregator.sources import RSS_FEEDS
# from database import NewsletterDB  # Removed for JSON migration

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticleCollector:
    def __init__(self, sources: Dict):
        self.sources = sources
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Daily Brief Newsletter/1.0 (https://example.com)'
        })
    
    def generate_article_id(self, title: str, url: str) -> str:
        """Generate consistent hash-based ID for articles"""
        # Normalize input for consistent hashing
        normalized_title = title.strip().lower()
        content = f"{normalized_title}|{url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def fetch_feed(self, feed_url: str, source_name: str) -> List[Dict]:
        """Fetch and parse a single RSS feed"""
        try:
            logger.info(f"Fetching feed: {source_name} ({feed_url})")
            
            # Use requests session for better control
            response = self.session.get(feed_url, timeout=10)
            response.raise_for_status()
            
            # Parse with feedparser
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {source_name}: {feed.bozo_exception}")
            
            articles = []
            for entry in feed.entries[:50]:  # Limit to 10 most recent
                article = self._parse_entry(entry, source_name)
                if article:
                    articles.append(article)
            
            logger.info(f"Collected {len(articles)} articles from {source_name}")
            return articles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching {source_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing feed {source_name}: {e}")
            return []
    
    def _parse_entry(self, entry, source_name: str) -> Optional[Dict]:
        """Parse a single RSS entry into our article format"""
        try:
            # Handle different date formats
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(timezone.utc)
            
            # Clean up description/summary
            description = ""
            if hasattr(entry, 'summary'):
                description = self._clean_html(entry.summary)
            elif hasattr(entry, 'description'):
                description = self._clean_html(entry.description)
            
            # Generate unique ID for the article
            title = entry.title.strip() if hasattr(entry, 'title') else 'No Title'
            url = entry.link if hasattr(entry, 'link') else ''
            article_id = self.generate_article_id(title, url)
            
            return {
                'id': article_id,  # Add unique ID for JSON-based processing
                'title': title,
                'url': url,
                'description': description[:500],  # Limit description length
                'source': source_name,
                'published': published.isoformat(),  # Convert datetime to ISO string for JSON
                'fetched_at': datetime.now(timezone.utc).isoformat()  # Convert datetime to ISO string for JSON
            }
        except Exception as e:
            logger.error(f"Error parsing entry from {source_name}: {e}")
            return None
    
    def _clean_html(self, html_text: str) -> str:
        """Basic HTML cleaning - remove tags but keep text"""
        # Remove HTML tags
        clean = re.sub('<[^<]+?>', '', html_text)
        # Clean up whitespace
        clean = ' '.join(clean.split())
        return clean
    
    def collect_by_category(self, category: str) -> List[Dict]:
        """Collect articles for a specific category"""
        if category not in self.sources:
            logger.warning(f"Category '{category}' not found in sources")
            return []
        
        all_articles = []
        category_sources = self.sources[category]
        
        for source in category_sources:
            articles = self.fetch_feed(source['url'], source['name'])
            # Add category to each article
            for article in articles:
                article['category'] = category
            all_articles.extend(articles)
            
            # Be nice to servers - small delay between requests
            time.sleep(1)
        
        return all_articles
    
    def collect_all(self) -> Dict[str, List[Dict]]:
        """Collect articles from all categories"""
        results = {}
        
        for category in self.sources.keys():
            logger.info(f"Collecting articles for category: {category}")
            results[category] = self.collect_by_category(category)
        
        # Summary logging
        total_articles = sum(len(articles) for articles in results.values())
        logger.info(f"Collection complete: {total_articles} total articles across {len(results)} categories")
        
        return results
    
    # def collect_and_store_all(self, db_path: str = "data/newsletter.db") -> Dict[str, int]:
    #     """Collect all articles and store them in database"""
    #     all_results = self.collect_all()
    #     storage_results = {}
        
    #     db = NewsletterDB(db_path)
        
    #     for category, articles in all_results.items():
    #         if articles:
    #             inserted_count = db.insert_articles_batch(articles)
    #             storage_results[category] = inserted_count
    #             logger.info(f"Stored {inserted_count} articles for {category}")
        
    #     return storage_results


# # Test function
# def test_collector():
#     """Test the collector with our sources"""
    
#     collector = ArticleCollector(RSS_FEEDS)
    
#     # Test single category
#     print("Testing tech category...")
#     tech_articles = collector.collect_by_category('nz')
    
#     for article in tech_articles:  # Show first 3
#         print(f"Title: {article['title']}")
#         print(f"Source: {article['source']}")
#         print(f"Category: {article['category']}")
#         print(f"Description: {article['description']}")
#         print(f"URL: {article['url']}")
#         print(f"Published: {article['published']}")
#         print("-" * 50)
#     print(tech_articles[0].keys())

# if __name__ == "__main__":
#     test_collector()