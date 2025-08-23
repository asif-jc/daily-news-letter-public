from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
import pandas as pd
import json
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import time

# from database import NewsletterDB
from db_utils import *

logger = logging.getLogger(__name__)


def scrape_article_content(url: str) -> Optional[str]:
    """Scrape main content from article URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Common content selectors (works for most news sites)
        content_selectors = [
            'article',
            '.article-content',
            '.post-content', 
            '.entry-content',
            '[data-module="ArticleBody"]',
            'div.story-body',
            'div.article-body'
        ]
        
        content = None
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                # Get text and clean it
                content = element.get_text(separator=' ', strip=True)
                break
        
        if not content:
            # Fallback: get all paragraph text
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs])
        
        # Limit content length (save tokens)
        if content and len(content) > 3000:
            content = content[:3000] + "..."
        
        return content
        
    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return None

def enhance_top_stories_with_content(mapped_results: Dict) -> Dict:
    """Scrape content for top stories only"""
    enhanced_results = mapped_results.copy()
    
    for category, category_data in enhanced_results.items():
        logger.info(f"Scraping content for {len(category_data['top_stories'])} top {category} stories")
        
        for story in category_data['top_stories']:
            url = story['url']
            content = scrape_article_content(url)
            
            if content:
                story['scraped_content'] = content
                logger.info(f"Scraped content for: {story['title'][:50]}...")
            else:
                story['scraped_content'] = story.get('description', 'Content not available')
                logger.warning(f"Using description fallback for: {story['title'][:50]}...")
            
            # Be nice to servers
            time.sleep(1)
    
    return enhanced_results